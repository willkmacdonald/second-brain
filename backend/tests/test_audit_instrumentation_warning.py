"""Tests for the instrumentation_warning sanity check on AuditReport."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.audit.walker import CorrelationAuditor


def _corr_record(segment_id: str, correlation_id: str = "abc-1"):
    return {
        "correlation_kind": "capture",
        "correlation_id": correlation_id,
        "segment_id": segment_id,
        "timestamp": "2026-04-18T12:00:00+00:00",
        "status": "green",
        "headline": f"{segment_id} ok",
    }


@pytest.mark.asyncio
async def test_instrumentation_warning_when_required_segment_absent_from_all_native():
    """When backend_api appears in every trace's spine chain but native lookup
    returns zero spans for backend_api in every trace, the report flags a
    likely instrumentation regression (e.g., correlation_id tagging dropped).
    """
    repo = AsyncMock()
    repo.get_recent_correlation_ids.return_value = ["abc-1", "abc-2"]
    repo.get_correlation_events.side_effect = lambda kind, cid: [
        _corr_record("mobile_capture", cid),
        _corr_record("backend_api", cid),
        _corr_record("classifier", cid),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    # Native lookup returns spans for mobile_capture + classifier but never
    # backend_api — that's the instrumentation regression we want to surface.
    lookup.spans.return_value = [
        {"Component": "mobile_capture", "Name": "capture_button_press"},
        {"Component": "classifier", "Name": "classify"},
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup)
    report = await auditor.audit_sample(
        kind="capture", sample_size=2, time_range_seconds=86400
    )

    assert report.instrumentation_warning is not None
    assert "backend_api" in report.instrumentation_warning


@pytest.mark.asyncio
async def test_no_instrumentation_warning_when_at_least_one_trace_has_native_data():
    repo = AsyncMock()
    repo.get_recent_correlation_ids.return_value = ["abc-1", "abc-2"]
    repo.get_correlation_events.side_effect = lambda kind, cid: [
        _corr_record("mobile_capture", cid),
        _corr_record("backend_api", cid),
        _corr_record("classifier", cid),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    # backend_api has native data, just no exceptions → no warning expected.
    lookup.spans.return_value = [
        {"Component": "backend_api", "Name": "POST /api/capture"},
        {"Component": "classifier", "Name": "classify"},
    ]
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup)
    report = await auditor.audit_sample(
        kind="capture", sample_size=2, time_range_seconds=86400
    )
    assert report.instrumentation_warning is None
