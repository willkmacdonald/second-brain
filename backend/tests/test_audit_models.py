"""Tests for audit Pydantic models — round-trip + verdict helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from second_brain.spine.audit.models import (
    AuditReport,
    AuditSummary,
    Misattribution,
    OrphanReport,
    TimeWindow,
    TraceAudit,
    roll_up_trace_verdict,
)


def test_trace_audit_minimal_round_trip():
    audit = TraceAudit(
        correlation_kind="capture",
        correlation_id="abc-123",
        verdict="clean",
        headline="all green",
        missing_required=[],
        present_optional=[],
        unexpected=[],
        misattributions=[],
        orphans=[],
        trace_window=TimeWindow(
            start=datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC),
            end=datetime(2026, 4, 18, 12, 0, 30, tzinfo=UTC),
        ),
        native_links={},
    )
    payload = audit.model_dump(mode="json")
    assert payload["correlation_id"] == "abc-123"
    assert payload["verdict"] == "clean"


def test_misattribution_round_trip():
    m = Misattribution(
        segment_id="classifier",
        check="outcome",
        spine_value="success",
        native_value="exception observed",
        reason="spine reports success but App Insights has 1 exception",
    )
    payload = m.model_dump(mode="json")
    assert payload["check"] == "outcome"


def test_orphan_report_round_trip():
    o = OrphanReport(
        segment_id="backend_api",
        orphan_count=3,
        sample_operations=["POST /api/capture", "GET /api/inbox"],
    )
    payload = o.model_dump(mode="json")
    assert payload["orphan_count"] == 3
    assert len(payload["sample_operations"]) == 2


def test_roll_up_clean():
    verdict = roll_up_trace_verdict(
        missing_required=[],
        misattributions=[],
        orphans=[],
        unexpected=[],
    )
    assert verdict == "clean"


def test_roll_up_warn_on_unexpected():
    verdict = roll_up_trace_verdict(
        missing_required=[],
        misattributions=[],
        orphans=[],
        unexpected=["classifier"],
    )
    assert verdict == "warn"


def test_roll_up_warn_on_orphans():
    verdict = roll_up_trace_verdict(
        missing_required=[],
        misattributions=[],
        orphans=[
            OrphanReport(
                segment_id="backend_api", orphan_count=1, sample_operations=["GET /x"]
            )
        ],
        unexpected=[],
    )
    assert verdict == "warn"


def test_roll_up_warn_on_non_outcome_misattribution():
    misattr = Misattribution(
        segment_id="classifier",
        check="operation",
        spine_value="classify_capture",
        native_value="(no matching span)",
        reason="no native span had a matching operation name",
    )
    verdict = roll_up_trace_verdict(
        missing_required=[],
        misattributions=[misattr],
        orphans=[],
        unexpected=[],
    )
    assert verdict == "warn"


def test_roll_up_broken_on_missing_required():
    verdict = roll_up_trace_verdict(
        missing_required=["classifier"],
        misattributions=[],
        orphans=[],
        unexpected=[],
    )
    assert verdict == "broken"


def test_roll_up_broken_on_outcome_misattribution():
    misattr = Misattribution(
        segment_id="classifier",
        check="outcome",
        spine_value="success",
        native_value="2 exceptions in window",
        reason="outcome disagreement",
    )
    verdict = roll_up_trace_verdict(
        missing_required=[],
        misattributions=[misattr],
        orphans=[],
        unexpected=[],
    )
    assert verdict == "broken"


def test_audit_summary_overall_verdict_precedence():
    summary = AuditSummary(
        clean_count=2,
        warn_count=1,
        broken_count=0,
        segments_with_missing_required={},
        segments_with_misattribution={},
        segments_with_orphans={"backend_api": 1},
        overall_verdict="warn",
        headline="1 of 3 traces have orphan operations",
    )
    payload = summary.model_dump(mode="json")
    assert payload["overall_verdict"] == "warn"


def test_audit_report_round_trip():
    report = AuditReport(
        correlation_kind="capture",
        sample_size_requested=5,
        sample_size_returned=3,
        time_range_seconds=86400,
        traces=[],
        summary=AuditSummary(
            clean_count=0,
            warn_count=0,
            broken_count=0,
            segments_with_missing_required={},
            segments_with_misattribution={},
            segments_with_orphans={},
            overall_verdict="clean",
            headline="no traces sampled",
        ),
        instrumentation_warning=None,
    )
    payload = report.model_dump(mode="json")
    assert payload["sample_size_returned"] == 3
