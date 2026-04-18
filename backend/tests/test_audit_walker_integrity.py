"""Tests for CorrelationAuditor — Check 1 (correlation integrity)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from second_brain.spine.audit.walker import CorrelationAuditor

NOW = datetime(2026, 4, 18, 12, 5, 0, tzinfo=UTC)


def _corr_record(segment_id: str, ts: str = "2026-04-18T12:00:00+00:00"):
    return {
        "correlation_kind": "capture",
        "correlation_id": "abc-123",
        "segment_id": segment_id,
        "timestamp": ts,
        "status": "green",
        "headline": f"{segment_id} ok",
    }


@pytest.mark.asyncio
async def test_clean_chain_no_misattribution_no_orphans():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.verdict == "clean"
    assert result.missing_required == []
    assert result.unexpected == []


@pytest.mark.asyncio
async def test_missing_required_classifier_marks_broken():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        # classifier missing
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.verdict == "broken"
    assert "classifier" in result.missing_required


@pytest.mark.asyncio
async def test_unexpected_segment_marks_warn():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
        _corr_record("some_unknown_segment"),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert "some_unknown_segment" in result.unexpected
    assert result.verdict == "warn"


@pytest.mark.asyncio
async def test_present_optional_listed():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture"),
        _corr_record("backend_api"),
        _corr_record("classifier"),
        _corr_record("admin"),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert "admin" in result.present_optional
    assert result.verdict == "clean"


@pytest.mark.asyncio
async def test_trace_window_spans_correlation_records():
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        _corr_record("mobile_capture", ts="2026-04-18T12:00:00+00:00"),
        _corr_record("backend_api", ts="2026-04-18T12:00:30+00:00"),
        _corr_record("classifier", ts="2026-04-18T12:00:45+00:00"),
    ]
    repo.get_recent_events.return_value = []
    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup, now=lambda: NOW)
    result = await auditor.audit("capture", "abc-123", time_range_seconds=3600)

    assert result.trace_window.start == datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC)
    assert result.trace_window.end == datetime(2026, 4, 18, 12, 0, 45, tzinfo=UTC)
