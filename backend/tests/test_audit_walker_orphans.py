"""Tests for CorrelationAuditor — Check 3 (bounded under-reporting)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from second_brain.spine.audit.walker import CorrelationAuditor

NOW = datetime(2026, 4, 18, 12, 5, 0, tzinfo=UTC)


def _corr_record(segment_id: str):
    return {
        "correlation_kind": "capture",
        "correlation_id": "abc-123",
        "segment_id": segment_id,
        "timestamp": "2026-04-18T12:00:30+00:00",
        "status": "green",
        "headline": f"{segment_id} ok",
    }


def _workload(segment_id: str, operation: str):
    return {
        "id": f"{segment_id}-evt",
        "segment_id": segment_id,
        "event_type": "workload",
        "timestamp": "2026-04-18T12:00:30+00:00",
        "payload": {
            "operation": operation,
            "outcome": "success",
            "duration_ms": 100,
            "correlation_kind": "capture",
            "correlation_id": "abc-123",
        },
    }


@pytest.mark.asyncio
async def test_orphan_native_operation_marks_warn():
    """Native source has 2 spans for backend_api; spine has 1 workload event."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = lambda segment_id, window_seconds: {
        "backend_api": [_workload("backend_api", operation="POST /api/capture")],
        "classifier": [_workload("classifier", operation="classify")],
    }.get(segment_id, [])

    lookup = AsyncMock()
    lookup.spans.return_value = [
        {"Component": "backend_api", "Name": "POST /api/capture"},
        {"Component": "backend_api", "Name": "GET /api/inbox"},  # orphan
        {"Component": "classifier", "Name": "classify"},
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    backend_orphans = [o for o in result.orphans if o.segment_id == "backend_api"]
    assert backend_orphans
    assert backend_orphans[0].orphan_count == 1
    assert "GET /api/inbox" in backend_orphans[0].sample_operations
    assert result.verdict == "warn"


@pytest.mark.asyncio
async def test_no_orphans_when_spine_covers_native():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.side_effect = lambda segment_id, window_seconds: {
        "backend_api": [_workload("backend_api", operation="POST /api/capture")],
        "classifier": [_workload("classifier", operation="classify")],
    }.get(segment_id, [])
    lookup = AsyncMock()
    lookup.spans.return_value = [
        {"Component": "backend_api", "Name": "POST /api/capture"},
        {"Component": "classifier", "Name": "classify"},
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.orphans == []
    assert result.verdict == "clean"
