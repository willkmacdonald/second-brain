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
    Misattribution,
    OrphanReport,
    TimeWindow,
    TraceAudit,
    build_summary,
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

# Segments expected to emit App Insights spans/exceptions. When `_check_misattribution`
# can't find a segment-tagged span via Properties.component, it falls back to all spans
# in the trace — but ONLY for these segments. Mobile segments are Sentry-sourced and
# never appear in App Insights, so the fallback would produce cross-segment false
# positives (e.g. mobile_capture inheriting backend_api's POST /api/capture span).
_APPINSIGHTS_SEGMENTS: frozenset[str] = frozenset(
    {
        "backend_api",
        "classifier",
        "admin",
        "investigation",
        "external_services",
        "container_app",
    }
)

# Tracks per-trace which segments had any native data returned by the lookup.
# Keyed by correlation_id → set of segment_ids with non-empty native results.
SegmentNativeMap = dict[str, set[str]]


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
        trace, _ = await self._audit_with_native_presence(
            kind, correlation_id, time_range_seconds=time_range_seconds
        )
        return trace

    async def _audit_with_native_presence(
        self,
        kind: CorrelationKind,
        correlation_id: str,
        *,
        time_range_seconds: int,
    ) -> tuple[TraceAudit, set[str]]:
        """Internal: returns the audit + which segments had any native data."""
        records = await self._repo.get_correlation_events(kind, correlation_id)
        segments_seen: dict[str, list[dict[str, Any]]] = {}
        for r in records:
            segments_seen.setdefault(r["segment_id"], []).append(r)

        chain = EXPECTED_CHAINS[kind]
        chain_ids = {s.segment_id for s in chain}
        required = {s.segment_id for s in chain if s.required}
        optional = {s.segment_id for s in chain if not s.required}

        missing_required = sorted(required - segments_seen.keys())
        present_optional = sorted(optional & segments_seen.keys())
        unexpected = sorted(set(segments_seen.keys()) - chain_ids)

        timestamps = [parse_cosmos_ts(r["timestamp"]) for r in records]
        if timestamps:
            window = TimeWindow(start=min(timestamps), end=max(timestamps))
        else:
            # No spine records for this trace — `missing_required` will already
            # mark this broken; the window is a placeholder, not a meaningful
            # range. Don't add downstream guards against zero-duration windows.
            now = self._now()
            window = TimeWindow(start=now, end=now)

        # ---- Check 2: mis-attribution ----
        spans = await self._lookup.spans(
            correlation_id, time_range_seconds=time_range_seconds
        )
        exceptions = await self._lookup.exceptions(
            correlation_id, time_range_seconds=time_range_seconds
        )
        cosmos_rows = await self._lookup.cosmos(
            correlation_id, time_range_seconds=time_range_seconds
        )

        workload_by_segment: dict[str, list[dict[str, Any]]] = {}
        misattributions: list[Misattribution] = []
        native_present: set[str] = set()

        for segment_id in segments_seen.keys() & chain_ids:
            workload_events = await self._workload_events_for(
                segment_id=segment_id,
                correlation_id=correlation_id,
                time_range_seconds=time_range_seconds,
            )
            workload_by_segment[segment_id] = workload_events
            if _segment_has_native_data(segment_id, spans, exceptions, cosmos_rows):
                native_present.add(segment_id)
            misattributions.extend(
                _check_misattribution(
                    segment_id=segment_id,
                    workload_events=workload_events,
                    spans=spans,
                    exceptions=exceptions,
                    cosmos_rows=cosmos_rows,
                )
            )

        # ---- Check 3: orphans ----
        orphans: list[OrphanReport] = []
        for segment_id, workload_events in workload_by_segment.items():
            orphan_report = _detect_orphans(
                segment_id=segment_id,
                workload_events=workload_events,
                spans=spans,
            )
            if orphan_report and orphan_report.orphan_count > 0:
                orphans.append(orphan_report)

        verdict = roll_up_trace_verdict(
            missing_required=missing_required,
            misattributions=misattributions,
            orphans=orphans,
            unexpected=unexpected,
        )

        trace = TraceAudit(
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
        return trace, native_present

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
        results = await asyncio.gather(
            *(
                self._audit_with_native_presence(
                    kind, cid, time_range_seconds=time_range_seconds
                )
                for cid in ids
            )
        )
        traces = [trace for trace, _ in results]
        per_trace_native = [native_present for _, native_present in results]

        warning = _instrumentation_warning(kind, traces, per_trace_native)
        return AuditReport(
            correlation_kind=kind,
            sample_size_requested=sample_size,
            sample_size_returned=len(traces),
            time_range_seconds=time_range_seconds,
            traces=traces,
            summary=build_summary(traces),
            instrumentation_warning=warning,
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


def _check_misattribution(
    *,
    segment_id: str,
    workload_events: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    cosmos_rows: list[dict[str, Any]],
) -> list[Misattribution]:
    """Run outcome / operation sub-checks for one segment.

    Filtering rules:
    - Per-segment Component filter on spans/exceptions; cross-trace fallback
      ONLY for App-Insights-instrumented segments (mobile is Sentry-only and
      will never have AppInsights coverage).
    - Cosmos rows are relevant only when segment_id == "cosmos". For that
      segment, non-2xx statusCode_s rows count as exception-equivalent
      evidence for the outcome check.

    Note on thresholds:
    - Operation check fires only when EVERY spine operation is unmatched
      across all native span Names. Loose discipline by design — partial
      matches don't flag.
    - Outcome check uses set semantics on `spine_outcomes`. A retry pattern
      (failure then success for the same segment+trace) can fire BOTH
      checks. Surfacing both is intentional: the agent can decide whether
      the retry pattern is benign.
    """
    findings: list[Misattribution] = []

    # Filter native rows to this segment when possible (Component column).
    seg_spans_filtered = [
        s for s in spans if str(s.get("Component", "")).lower() == segment_id.lower()
    ]
    seg_exceptions_filtered = [
        e
        for e in exceptions
        if str(e.get("Component", "")).lower() == segment_id.lower()
    ]

    # Fall back to all spans/exceptions ONLY for AppInsights-instrumented
    # segments. Mobile segments never appear in AppInsights — using the
    # full trace as fallback creates spurious cross-segment misattributions.
    if segment_id in _APPINSIGHTS_SEGMENTS:
        seg_spans = seg_spans_filtered or spans
        seg_exceptions = seg_exceptions_filtered or exceptions
    else:
        seg_spans = seg_spans_filtered
        seg_exceptions = seg_exceptions_filtered

    # Cosmos rows belong to the cosmos segment exclusively. Non-2xx status
    # codes count as exception-equivalent evidence for that segment's
    # outcome check.
    seg_cosmos = cosmos_rows if segment_id == "cosmos" else []
    cosmos_errors = [
        r for r in seg_cosmos if not str(r.get("statusCode_s", "")).startswith("2")
    ]

    # An "exception-equivalent" set: AppInsights exceptions plus, for cosmos,
    # any non-2xx Cosmos diagnostic rows.
    error_evidence_count = len(seg_exceptions) + len(cosmos_errors)

    has_native_evidence = bool(seg_spans or seg_exceptions or seg_cosmos)
    if not has_native_evidence:
        # No native data to compare against — silent on all sub-checks.
        return findings

    spine_outcomes = {e["payload"]["outcome"] for e in workload_events}

    # Outcome agreement
    if "success" in spine_outcomes and error_evidence_count > 0:
        findings.append(
            Misattribution(
                segment_id=segment_id,
                check="outcome",
                spine_value="success",
                native_value=f"{error_evidence_count} error indicator(s) in window",
                reason=(
                    "spine reports success but native sources have"
                    f" {error_evidence_count} error indicator(s) for this trace"
                ),
            )
        )
    if "failure" in spine_outcomes and error_evidence_count == 0:
        findings.append(
            Misattribution(
                segment_id=segment_id,
                check="outcome",
                spine_value="failure",
                native_value="0 error indicators in window",
                reason=(
                    "spine reports failure but native sources have no"
                    " error indicators for this trace"
                ),
            )
        )

    # Operation name plausibility (loose: spine.operation appears in any span Name).
    # Only fires when ALL spine ops are unmatched — partial matches don't flag.
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


def _detect_orphans(
    *,
    segment_id: str,
    workload_events: list[dict[str, Any]],
    spans: list[dict[str, Any]],
) -> OrphanReport | None:
    """Return an OrphanReport if the segment has more native spans than workload events.

    Orphans are spans tagged with this trace's correlation_id whose Name is not
    plausibly covered by any spine workload event for this segment.

    Matching note: this checks `span_name in spine_ops_blob` (reverse of
    Check 2's `spine_op in native_names`). That direction creates a known
    false-negative class — decorated span Names like "POST /api/capture 200"
    will not match a spine ops blob containing the bare "POST /api/capture",
    so real orphans get under-reported. Acceptable per spec's "best-effort,
    not authoritative" framing — surface in the report, let the agent judge.

    Cosmos segment always returns None: cosmos diagnostics live in
    AzureDiagnostics rows, not App Insights spans, so the Component filter
    yields nothing. Cosmos orphan detection is out of scope for v1.
    """
    seg_spans = [
        s for s in spans if str(s.get("Component", "")).lower() == segment_id.lower()
    ]
    if not seg_spans:
        return None

    spine_ops_blob = " ".join(
        str(e["payload"]["operation"]) for e in workload_events
    ).lower()

    orphan_names: list[str] = []
    for span in seg_spans:
        name = str(span.get("Name", ""))
        if not name:
            continue
        if name.lower() not in spine_ops_blob:
            orphan_names.append(name)

    if not orphan_names:
        return None
    return OrphanReport(
        segment_id=segment_id,
        orphan_count=len(orphan_names),
        sample_operations=orphan_names[:3],
    )


def _segment_has_native_data(
    segment_id: str,
    spans: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    cosmos_rows: list[dict[str, Any]],
) -> bool:
    """Return True if any native source returned a row attributable to segment_id."""
    if any(str(s.get("Component", "")).lower() == segment_id.lower() for s in spans):
        return True
    if any(
        str(e.get("Component", "")).lower() == segment_id.lower() for e in exceptions
    ):
        return True
    return bool(segment_id == "cosmos" and cosmos_rows)


def _instrumentation_warning(
    kind: CorrelationKind,
    traces: list[TraceAudit],
    per_trace_native: list[set[str]],
) -> str | None:
    """Return a warning if any required segment had zero native data across all traces.

    Only fires for segments that are expected to emit data into the native lookup
    sources (App Insights spans/exceptions, or Cosmos diagnostics). Mobile segments
    are Sentry-sourced and never appear in the App Insights lookup — they are excluded
    to avoid spurious warnings on every sample.
    """
    if not traces:
        return None

    required = {s.segment_id for s in EXPECTED_CHAINS[kind] if s.required}
    # Only warn about segments the native lookup can actually see.
    # Mobile segments (mobile_capture, mobile_ui) are Sentry-only and will
    # never have App Insights records, so silence is expected, not broken.
    queryable = _APPINSIGHTS_SEGMENTS | {"cosmos"}
    required_and_queryable = required & queryable

    # Only consider segments that were actually present in every trace's spine
    # chain — otherwise we'd flag legitimately-missing required segments as an
    # instrumentation issue.
    appeared_everywhere = set(required_and_queryable)
    for trace in traces:
        appeared_everywhere &= set(
            trace.present_optional
            + [s for s in required_and_queryable if s not in trace.missing_required]
        )

    silent_segments: list[str] = []
    for seg in sorted(appeared_everywhere):
        if all(seg not in present for present in per_trace_native):
            silent_segments.append(seg)

    if not silent_segments:
        return None
    return (
        f"{', '.join(silent_segments)} appears to have lost correlation_id"
        " tagging — every sampled trace had spine events for this segment but"
        " zero matching native records"
    )
