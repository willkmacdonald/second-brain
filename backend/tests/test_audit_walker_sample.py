"""Tests for CorrelationAuditor.audit_sample — sample-mode + summary roll-up."""

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
async def test_audit_sample_returns_one_audit_per_id():
    repo = AsyncMock()
    repo.get_recent_correlation_ids.return_value = ["abc-1", "abc-2", "abc-3"]
    repo.get_correlation_events.side_effect = lambda kind, cid: [
        _corr_record("mobile_capture", cid),
        _corr_record("backend_api", cid),
        _corr_record("classifier", cid),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup)
    report = await auditor.audit_sample(
        kind="capture", sample_size=3, time_range_seconds=86400
    )

    assert report.sample_size_requested == 3
    assert report.sample_size_returned == 3
    assert len(report.traces) == 3
    assert report.summary.overall_verdict == "clean"


@pytest.mark.asyncio
async def test_audit_sample_returns_fewer_when_not_enough_traces():
    repo = AsyncMock()
    repo.get_recent_correlation_ids.return_value = ["abc-1"]
    repo.get_correlation_events.side_effect = lambda kind, cid: [
        _corr_record("mobile_capture", cid),
        _corr_record("backend_api", cid),
        _corr_record("classifier", cid),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup)
    report = await auditor.audit_sample(
        kind="capture", sample_size=5, time_range_seconds=86400
    )

    assert report.sample_size_requested == 5
    assert report.sample_size_returned == 1


@pytest.mark.asyncio
async def test_audit_sample_summary_aggregates_missing_required():
    repo = AsyncMock()
    repo.get_recent_correlation_ids.return_value = ["abc-1", "abc-2"]
    # Both traces missing classifier.
    repo.get_correlation_events.side_effect = lambda kind, cid: [
        _corr_record("mobile_capture", cid),
        _corr_record("backend_api", cid),
    ]
    repo.get_recent_events.return_value = []

    lookup = AsyncMock()
    lookup.spans.return_value = []
    lookup.exceptions.return_value = []
    lookup.cosmos.return_value = []

    auditor = CorrelationAuditor(repo=repo, lookup=lookup)
    report = await auditor.audit_sample(
        kind="capture", sample_size=2, time_range_seconds=86400
    )

    assert report.summary.overall_verdict == "broken"
    assert report.summary.broken_count == 2
    assert report.summary.segments_with_missing_required == {"classifier": 2}
