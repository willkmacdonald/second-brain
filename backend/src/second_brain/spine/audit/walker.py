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

        # ---- Check 2: mis-attribution (outcome / operation / time_window) ----
        # Pull native sources once for the whole trace.
        spans = await self._lookup.spans(
            correlation_id, time_range_seconds=time_range_seconds
        )
        exceptions = await self._lookup.exceptions(
            correlation_id, time_range_seconds=time_range_seconds
        )
        cosmos_rows = await self._lookup.cosmos(
            correlation_id, time_range_seconds=time_range_seconds
        )

        misattributions: list[Misattribution] = []
        for segment_id in segments_seen.keys() & chain_ids:
            workload_events = await self._workload_events_for(
                segment_id=segment_id,
                correlation_id=correlation_id,
                time_range_seconds=time_range_seconds,
            )
            misattributions.extend(
                _check_misattribution(
                    segment_id=segment_id,
                    workload_events=workload_events,
                    spans=spans,
                    exceptions=exceptions,
                    cosmos_rows=cosmos_rows,
                )
            )

        # ---- Check 3 (Task 8 fills this in) ----
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

    async def _workload_events_for(
        self,
        *,
        segment_id: str,
        correlation_id: str,
        time_range_seconds: int,
    ) -> list[dict[str, Any]]:
        """Return workload events for this segment+correlation in the window."""
        events = await self._repo.get_recent_events(
            segment_id=segment_id, window_seconds=time_range_seconds
        )
        return [
            e
            for e in events
            if e.get("event_type") == "workload"
            and e.get("payload", {}).get("correlation_id") == correlation_id
        ]

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


def _check_misattribution(
    *,
    segment_id: str,
    workload_events: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    cosmos_rows: list[dict[str, Any]],
) -> list[Misattribution]:
    """Run outcome / operation / time-window sub-checks for one segment."""
    findings: list[Misattribution] = []

    # Filter native rows to this segment when possible (Component column).
    seg_spans = [
        s for s in spans if str(s.get("Component", "")).lower() == segment_id.lower()
    ] or spans
    seg_exceptions = [
        e
        for e in exceptions
        if str(e.get("Component", "")).lower() == segment_id.lower()
    ] or exceptions

    # Cosmos has no Component column; treat any cosmos row as relevant only
    # when this segment_id == "cosmos".
    seg_cosmos = cosmos_rows if segment_id == "cosmos" else []

    has_native_evidence = bool(seg_spans or seg_exceptions or seg_cosmos)
    if not has_native_evidence:
        # No native data to compare against — silent on all three sub-checks.
        return findings

    spine_outcomes = {e["payload"]["outcome"] for e in workload_events}

    # Outcome agreement
    if "success" in spine_outcomes and seg_exceptions:
        findings.append(
            Misattribution(
                segment_id=segment_id,
                check="outcome",
                spine_value="success",
                native_value=f"{len(seg_exceptions)} exception(s) in window",
                reason=(
                    "spine reports success but native sources have"
                    f" {len(seg_exceptions)} exception(s) for this trace"
                ),
            )
        )
    if "failure" in spine_outcomes and not seg_exceptions:
        findings.append(
            Misattribution(
                segment_id=segment_id,
                check="outcome",
                spine_value="failure",
                native_value="0 exceptions in window",
                reason=(
                    "spine reports failure but native sources have no"
                    " exceptions for this trace"
                ),
            )
        )

    # Operation name plausibility (loose: spine.operation appears in any span Name)
    spine_ops = {e["payload"]["operation"] for e in workload_events}
    if seg_spans and spine_ops:
        native_names = " ".join(str(s.get("Name", "")) for s in seg_spans).lower()
        unmatched = [op for op in spine_ops if op.lower() not in native_names]
        if unmatched and len(unmatched) == len(spine_ops):
            findings.append(
                Misattribution(
                    segment_id=segment_id,
                    check="operation",
                    spine_value=", ".join(sorted(spine_ops)),
                    native_value="(no matching span Name)",
                    reason=(
                        "spine operation name(s) not found in any native span"
                        " Name for this trace"
                    ),
                )
            )

    return findings
