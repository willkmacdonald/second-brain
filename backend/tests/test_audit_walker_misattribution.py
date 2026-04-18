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
