"""Correlation audit walker.

Public surface:
  - CorrelationAuditor.audit(kind, id, time_range_seconds) -> TraceAudit
  - CorrelationAuditor.audit_sample(kind, sample_size, time_range_seconds)
    -> AuditReport

Implements three checks per trace:
  1. Correlation integrity   — required vs. optional vs. unexpected segments
  2. Mis-attribution         — outcome / operation / time-window agreement
  3. Bounded under-reporting — orphaned native operations in the trace window

See docs/superpowers/specs/2026-04-18-per-segment-correlation-audit-design.md.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

from second_brain.spine.audit.chains import EXPECTED_CHAINS
from second_brain.spine.audit.models import (
    AuditReport,
    AuditSummary,
    Misattribution,
    OrphanReport,
    TimeWindow,
    TraceAudit,
    roll_up_report_verdict,
    roll_up_trace_verdict,
)
from second_brain.spine.audit.native_lookup import NativeLookup
from second_brain.spine.models import CorrelationKind, parse_cosmos_ts
from second_brain.spine.storage import SpineRepository

NATIVE_LINK_TEMPLATES: dict[str, str] = {
    "backend_api": "https://portal.azure.com/#blade/AppInsightsExtension",
    "classifier": "https://ai.azure.com/build/agents",
    "admin": "https://ai.azure.com/build/agents",
    "investigation": "https://ai.azure.com/build/agents",
    "external_services": "https://portal.azure.com/#blade/AppInsightsExtension",
    "cosmos": "https://portal.azure.com/#blade/Microsoft_Azure_DocumentDB",
    "mobile_ui": "https://sentry.io",
    "mobile_capture": "https://sentry.io",
    "container_app": "https://portal.azure.com/#blade/AppInsightsExtension",
}


class CorrelationAuditor:
    """Walks the expected chain for one correlation_id and audits it."""

    def __init__(
        self,
        *,
        repo: SpineRepository,
        lookup: NativeLookup,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = repo
        self._lookup = lookup
        self._now = now or (lambda: datetime.now(UTC))

    async def audit(
        self,
        kind: CorrelationKind,
        correlation_id: str,
        *,
        time_range_seconds: int,
    ) -> TraceAudit:
        """Audit a single correlation_id."""
        # ---- Pull spine records for this trace ----
        records = await self._repo.get_correlation_events(kind, correlation_id)
        segments_seen: dict[str, list[dict[str, Any]]] = {}
        for r in records:
            segments_seen.setdefault(r["segment_id"], []).append(r)

        chain = EXPECTED_CHAINS[kind]
        chain_ids = {s.segment_id for s in chain}
        required = {s.segment_id for s in chain if s.required}
        optional = {s.segment_id for s in chain if not s.required}

        # ---- Check 1: correlation integrity ----
        missing_required = sorted(required - segments_seen.keys())
        present_optional = sorted(optional & segments_seen.keys())
        unexpected = sorted(set(segments_seen.keys()) - chain_ids)

        # ---- Trace window from spine record timestamps ----
        timestamps = [parse_cosmos_ts(r["timestamp"]) for r in records]
        if timestamps:
            window = TimeWindow(start=min(timestamps), end=max(timestamps))
        else:
            # No spine records for this trace — `missing_required` will already
            # mark this broken; the window is a placeholder, not a meaningful
            # range. Don't add downstream guards against zero-duration windows.
            now = self._now()
            window = TimeWindow(start=now, end=now)

        # ---- Check 2 + Check 3 (Tasks 7 + 8 fill these in) ----
        misattributions: list[Misattribution] = []
        orphans: list[OrphanReport] = []

        verdict = roll_up_trace_verdict(
            missing_required=missing_required,
            misattributions=misattributions,
            orphans=orphans,
            unexpected=unexpected,
        )

        return TraceAudit(
            correlation_kind=kind,
            correlation_id=correlation_id,
            verdict=verdict,
            headline=_headline_for_trace(
                missing_required, misattributions, orphans, unexpected
            ),
            missing_required=missing_required,
            present_optional=present_optional,
            unexpected=unexpected,
            misattributions=misattributions,
            orphans=orphans,
            trace_window=window,
            native_links=_native_links_for(segments_seen.keys()),
        )

    async def audit_sample(
        self,
        kind: CorrelationKind,
        sample_size: int,
        time_range_seconds: int,
    ) -> AuditReport:
        """Sample the most-recent correlation_ids and audit each."""
        ids = await self._repo.get_recent_correlation_ids(
            kind=kind,
            time_range_seconds=time_range_seconds,
            limit=sample_size,
        )
        traces = list(
            await asyncio.gather(
                *(
                    self.audit(kind, cid, time_range_seconds=time_range_seconds)
                    for cid in ids
                )
            )
        )
        return AuditReport(
            correlation_kind=kind,
            sample_size_requested=sample_size,
            sample_size_returned=len(traces),
            time_range_seconds=time_range_seconds,
            traces=traces,
            summary=_build_summary(traces),
            instrumentation_warning=None,
        )


def _native_links_for(segment_ids: Iterable[str]) -> dict[str, str]:
    return {
        seg: NATIVE_LINK_TEMPLATES[seg]
        for seg in segment_ids
        if seg in NATIVE_LINK_TEMPLATES
    }


def _headline_for_trace(
    missing_required: list[str],
    misattributions: list[Misattribution],
    orphans: list[OrphanReport],
    unexpected: list[str],
) -> str:
    if missing_required:
        return f"missing required segments: {', '.join(missing_required)}"
    if any(m.check == "outcome" for m in misattributions):
        seg = next(m.segment_id for m in misattributions if m.check == "outcome")
        return f"outcome disagreement on {seg}"
    if unexpected:
        return f"unexpected segments emitted: {', '.join(unexpected)}"
    if orphans:
        total = sum(o.orphan_count for o in orphans)
        return f"{total} orphaned native operation(s)"
    if misattributions:
        return f"{len(misattributions)} non-outcome misattribution(s)"
    return "all expected segments present, no discrepancies"


def _build_summary(traces: list[TraceAudit]) -> AuditSummary:
    clean = sum(1 for t in traces if t.verdict == "clean")
    warn = sum(1 for t in traces if t.verdict == "warn")
    broken = sum(1 for t in traces if t.verdict == "broken")

    missing: dict[str, int] = {}
    misattr: dict[str, int] = {}
    orphan_segs: dict[str, int] = {}
    for t in traces:
        for seg in t.missing_required:
            missing[seg] = missing.get(seg, 0) + 1
        for m in t.misattributions:
            misattr[m.segment_id] = misattr.get(m.segment_id, 0) + 1
        for o in t.orphans:
            orphan_segs[o.segment_id] = orphan_segs.get(o.segment_id, 0) + 1

    overall = roll_up_report_verdict(traces)
    headline = _summary_headline(overall, broken, warn, len(traces))

    return AuditSummary(
        clean_count=clean,
        warn_count=warn,
        broken_count=broken,
        segments_with_missing_required=missing,
        segments_with_misattribution=misattr,
        segments_with_orphans=orphan_segs,
        overall_verdict=overall,
        headline=headline,
    )


def _summary_headline(overall: str, broken: int, warn: int, total: int) -> str:
    if total == 0:
        return "no traces sampled"
    if overall == "broken":
        return f"{broken} of {total} traces broken"
    if overall == "warn":
        return f"{warn} of {total} traces have warnings"
    return f"all {total} traces clean"
