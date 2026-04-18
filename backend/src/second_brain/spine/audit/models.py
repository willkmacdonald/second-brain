"""Pydantic models for the audit_correlation MCP tool / spine endpoint.

Verdict precedence per trace:
  - broken: any missing_required OR any misattribution.check == "outcome"
  - warn:   any unexpected OR any non-outcome misattribution OR any orphans
  - clean:  none of the above

Per report: broken > warn > clean across the trace list.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from second_brain.spine.models import CorrelationKind

Verdict = Literal["clean", "warn", "broken"]
MisattributionCheck = Literal["outcome", "operation", "time_window"]


class TimeWindow(BaseModel):
    """Earliest -> latest spine_event timestamp for a single trace."""

    start: datetime
    end: datetime


class Misattribution(BaseModel):
    """One sub-check failure during the mis-attribution check."""

    segment_id: str
    check: MisattributionCheck
    spine_value: str
    native_value: str
    reason: str


class OrphanReport(BaseModel):
    """Per-segment count of native operations with no matching spine event."""

    segment_id: str
    orphan_count: int
    sample_operations: list[str] = Field(default_factory=list)


class TraceAudit(BaseModel):
    """Per-trace audit result."""

    correlation_kind: CorrelationKind
    correlation_id: str
    verdict: Verdict
    headline: str

    missing_required: list[str] = Field(default_factory=list)
    present_optional: list[str] = Field(default_factory=list)
    unexpected: list[str] = Field(default_factory=list)

    misattributions: list[Misattribution] = Field(default_factory=list)
    orphans: list[OrphanReport] = Field(default_factory=list)

    trace_window: TimeWindow
    native_links: dict[str, str] = Field(default_factory=dict)


class AuditSummary(BaseModel):
    """Roll-up across all sampled traces."""

    clean_count: int
    warn_count: int
    broken_count: int

    segments_with_missing_required: dict[str, int] = Field(default_factory=dict)
    segments_with_misattribution: dict[str, int] = Field(default_factory=dict)
    segments_with_orphans: dict[str, int] = Field(default_factory=dict)

    overall_verdict: Verdict
    headline: str


class AuditReport(BaseModel):
    """Top-level response from POST /api/spine/audit/correlation."""

    correlation_kind: CorrelationKind
    sample_size_requested: int
    sample_size_returned: int
    time_range_seconds: int

    traces: list[TraceAudit] = Field(default_factory=list)
    summary: AuditSummary
    instrumentation_warning: str | None = None


def roll_up_trace_verdict(
    *,
    missing_required: list[str],
    misattributions: list[Misattribution],
    orphans: list[OrphanReport],
    unexpected: list[str],
) -> Verdict:
    """Apply the per-trace verdict precedence rules."""
    if missing_required:
        return "broken"
    if any(m.check == "outcome" for m in misattributions):
        return "broken"
    if unexpected or orphans or misattributions:
        return "warn"
    return "clean"


def roll_up_report_verdict(traces: list[TraceAudit]) -> Verdict:
    """Apply the per-report verdict precedence rules."""
    if any(t.verdict == "broken" for t in traces):
        return "broken"
    if any(t.verdict == "warn" for t in traces):
        return "warn"
    return "clean"


def build_summary(traces: list[TraceAudit]) -> AuditSummary:
    """Aggregate per-trace audits into a report-level summary."""
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
    """Human-readable one-liner for the report summary."""
    if total == 0:
        return "no traces sampled"
    if overall == "broken":
        return f"{broken} of {total} traces broken"
    if overall == "warn":
        return f"{warn} of {total} traces have warnings"
    return f"all {total} traces clean"
