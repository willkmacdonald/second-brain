"""Tests for spine Cosmos storage repository."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from second_brain.spine.models import (
    IngestEvent,
)
from second_brain.spine.storage import SpineRepository


@pytest.fixture
def mock_containers() -> dict[str, AsyncMock]:
    """Four mocked Cosmos container clients."""
    return {
        "events": AsyncMock(),
        "segment_state": AsyncMock(),
        "status_history": AsyncMock(),
        "correlation": AsyncMock(),
    }


@pytest.fixture
def repo(mock_containers: dict[str, AsyncMock]) -> SpineRepository:
    return SpineRepository(
        events_container=mock_containers["events"],
        segment_state_container=mock_containers["segment_state"],
        status_history_container=mock_containers["status_history"],
        correlation_container=mock_containers["correlation"],
    )


@pytest.mark.asyncio
async def test_record_event_writes_to_events_container(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    event = IngestEvent.model_validate(
        {
            "segment_id": "backend_api",
            "event_type": "liveness",
            "timestamp": "2026-04-14T12:00:00Z",
            "payload": {"instance_id": "abc"},
        }
    )
    await repo.record_event(event)
    mock_containers["events"].create_item.assert_called_once()
    body = mock_containers["events"].create_item.call_args.kwargs["body"]
    assert body["segment_id"] == "backend_api"
    assert body["event_type"] == "liveness"


@pytest.mark.asyncio
async def test_record_workload_with_correlation_writes_correlation_record(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    event = IngestEvent.model_validate(
        {
            "segment_id": "backend_api",
            "event_type": "workload",
            "timestamp": "2026-04-14T12:00:00Z",
            "payload": {
                "operation": "POST /api/capture",
                "outcome": "success",
                "duration_ms": 100,
                "correlation_kind": "capture",
                "correlation_id": "trace-1",
            },
        }
    )
    await repo.record_event(event)
    mock_containers["correlation"].upsert_item.assert_called_once()
    corr_body = mock_containers["correlation"].upsert_item.call_args.kwargs["body"]
    assert corr_body["correlation_kind"] == "capture"
    assert corr_body["correlation_id"] == "trace-1"
    assert corr_body["segment_id"] == "backend_api"


@pytest.mark.asyncio
async def test_workload_without_correlation_skips_correlation_write(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    event = IngestEvent.model_validate(
        {
            "segment_id": "backend_api",
            "event_type": "workload",
            "timestamp": "2026-04-14T12:00:00Z",
            "payload": {
                "operation": "background_task",
                "outcome": "success",
                "duration_ms": 100,
            },
        }
    )
    await repo.record_event(event)
    mock_containers["correlation"].upsert_item.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_segment_state_writes_state_container(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    await repo.upsert_segment_state(
        segment_id="backend_api",
        status="green",
        headline="Healthy",
        last_updated=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
        evaluator_inputs={"workload_failure_rate": 0.0},
    )
    mock_containers["segment_state"].upsert_item.assert_called_once()
    body = mock_containers["segment_state"].upsert_item.call_args.kwargs["body"]
    assert body["id"] == "backend_api"
    assert body["status"] == "green"


@pytest.mark.asyncio
async def test_record_status_change_writes_history(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    await repo.record_status_change(
        segment_id="backend_api",
        status="red",
        prev_status="green",
        headline="Errors",
        evaluator_outputs={"workload_failure_rate": 0.6},
        timestamp=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
    )
    mock_containers["status_history"].create_item.assert_called_once()
    body = mock_containers["status_history"].create_item.call_args.kwargs["body"]
    assert body["status"] == "red"
    assert body["prev_status"] == "green"


@pytest.mark.asyncio
async def test_get_recent_events_queries_by_segment_and_window(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    async def async_iter():
        for item in [{"segment_id": "backend_api", "event_type": "workload"}]:
            yield item

    mock_containers["events"].query_items = MagicMock(return_value=async_iter())
    events = await repo.get_recent_events("backend_api", window_seconds=300)
    assert len(events) == 1


@pytest.mark.asyncio
async def test_get_correlation_events_queries_correlation_container(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    async def async_iter():
        for item in [
            {
                "correlation_kind": "capture",
                "correlation_id": "trace-1",
                "segment_id": "backend_api",
                "timestamp": "2026-04-14T12:00:00Z",
                "status": "green",
                "headline": "OK",
            }
        ]:
            yield item

    mock_containers["correlation"].query_items = MagicMock(return_value=async_iter())
    events = await repo.get_correlation_events("capture", "trace-1")
    assert len(events) == 1
    assert events[0]["segment_id"] == "backend_api"
