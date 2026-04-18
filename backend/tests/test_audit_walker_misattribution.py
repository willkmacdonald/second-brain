"""Tests for CorrelationAuditor — Check 2 (mis-attribution sub-checks)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from second_brain.spine.audit.walker import CorrelationAuditor

NOW = datetime(2026, 4, 18, 12, 5, 0, tzinfo=UTC)


def _corr_record(segment_id: str, ts: str = "2026-04-18T12:00:30+00:00"):
    return {
        "correlation_kind": "capture",
        "correlation_id": "abc-123",
        "segment_id": segment_id,
        "timestamp": ts,
        "status": "green",
        "headline": f"{segment_id} ok",
    }


def _workload_event(segment_id: str, outcome: str, operation: str = "do_thing"):
    return {
        "id": f"{segment_id}-evt",
        "segment_id": segment_id,
        "event_type": "workload",
        "timestamp": "2026-04-18T12:00:30+00:00",
        "payload": {
            "operation": operation,
            "outcome": outcome,
            "duration_ms": 100,
            "correlation_kind": "capture",
            "correlation_id": "abc-123",
        },
    }


@pytest.mark.asyncio
async def test_outcome_disagreement_marks_broken():
    """Spine says success but App Insights has an exception in window."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = lambda segment_id, window_seconds: {
        "classifier": [_workload_event("classifier", outcome="success")],
    }.get(segment_id, [])

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = [
        {
            "Component": "classifier",
            "ExceptionType": "HttpResponseError",
            "OuterMessage": "boom",
        }
    ]
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.verdict == "broken"
    outcome_misattr = [m for m in result.misattributions if m.check == "outcome"]
    assert any(m.segment_id == "classifier" for m in outcome_misattr)


@pytest.mark.asyncio
async def test_outcome_disagreement_failure_with_no_exceptions():
    """Spine says failure but App Insights has zero exceptions."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = lambda segment_id, window_seconds: {
        "classifier": [_workload_event("classifier", outcome="failure")],
    }.get(segment_id, [])

    lookup = AsyncMock()
    lookup.spans.return_value = [
        {"Component": "classifier", "Name": "do_thing", "DurationMs": 100}
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.verdict == "broken"
    assert any(m.check == "outcome" for m in result.misattributions)


@pytest.mark.asyncio
async def test_operation_name_mismatch_marks_warn():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = lambda segment_id, window_seconds: {
        "classifier": [
            _workload_event("classifier", outcome="success", operation="zzz_unique")
        ],
    }.get(segment_id, [])

    lookup = AsyncMock()
    # Native span exists but doesn't mention the spine-claimed operation.
    lookup.spans.return_value = [
        {
            "Component": "classifier",
            "Name": "POST /something/else",
            "DurationMs": 100,
        }
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert any(m.check == "operation" for m in result.misattributions)
    assert result.verdict == "warn"


@pytest.mark.asyncio
async def test_no_native_data_skips_misattribution_silently():
    """If the lookup returns nothing for a segment we can't compare — don't flag."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = lambda segment_id, window_seconds: {
        "classifier": [_workload_event("classifier", outcome="success")],
    }.get(segment_id, [])

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    # Spine claims success; native shows nothing. We don't flag the *outcome*
    # because we have no native evidence either way. Operation/time_window
    # checks are also skipped when there are no spans.
    assert result.misattributions == []


@pytest.mark.asyncio
async def test_mobile_segment_does_not_inherit_backend_api_spans():
    """mobile_capture is Sentry-sourced. AppInsights spans tagged to backend_api
    must NOT trigger an operation-name misattribution against mobile_capture."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = lambda segment_id, window_seconds: {
        "mobile_capture": [
            _workload_event(
                "mobile_capture",
                outcome="success",
                operation="capture_button_press",
            )
        ],
        "backend_api": [
            _workload_event(
                "backend_api", outcome="success", operation="POST /api/capture"
            )
        ],
    }.get(segment_id, [])

    lookup = AsyncMock()
    # Only backend_api has an AppInsights span. Mobile segments should NOT
    # fall back to using it as their evidence.
    lookup.spans.return_value = [
        {"Component": "backend_api", "Name": "POST /api/capture", "DurationMs": 100},
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    # mobile_capture must NOT have an operation misattribution (would be a
    # cross-segment false positive from inheriting backend_api's span).
    mobile_misattrs = [
        m for m in result.misattributions if m.segment_id == "mobile_capture"
    ]
    assert mobile_misattrs == []


@pytest.mark.asyncio
async def test_cosmos_failure_corroborated_by_non_200_diagnostic_row():
    """cosmos reports failure; cosmos_rows has a 429 row. NO outcome misattribution
    should fire — the failure is corroborated by Cosmos diagnostic evidence."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("backend_api"),
        _corr_record("cosmos"),
    ]
    repo.get_recent_events.side_effect = lambda segment_id, window_seconds: {
        "cosmos": [
            _workload_event("cosmos", outcome="failure", operation="ReadDocument")
        ],
    }.get(segment_id, [])

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = [
        {
            "OperationName": "ReadDocument",
            "statusCode_s": "429",
            "activityId_g": "abc-123",
        },
    ]

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    # NB: this trace is "request" kind so cosmos is required; use that to
    # avoid false-positive missing_required for capture's mobile_capture.
    result = await auditor.audit("request", "abc-123", time_range_seconds=3600)

    # No outcome misattribution for cosmos — the 429 is a legitimate failure indicator.
    cosmos_outcome = [
        m
        for m in result.misattributions
        if m.segment_id == "cosmos" and m.check == "outcome"
    ]
    assert cosmos_outcome == []


@pytest.mark.asyncio
async def test_cosmos_success_with_429_marks_misattribution():
    """cosmos reports success; cosmos_rows has a 429 row. Outcome misattribution fires
    because spine claims success but Cosmos diagnostics show a non-2xx response."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("backend_api"),
        _corr_record("cosmos"),
    ]
    repo.get_recent_events.side_effect = lambda segment_id, window_seconds: {
        "cosmos": [
            _workload_event("cosmos", outcome="success", operation="ReadDocument")
        ],
    }.get(segment_id, [])

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = [
        {
            "OperationName": "ReadDocument",
            "statusCode_s": "429",
            "activityId_g": "abc-123",
        },
    ]

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("request", "abc-123", time_range_seconds=3600)

    cosmos_outcome = [
        m
        for m in result.misattributions
        if m.segment_id == "cosmos" and m.check == "outcome"
    ]
    assert len(cosmos_outcome) == 1
    assert cosmos_outcome[0].spine_value == "success"
