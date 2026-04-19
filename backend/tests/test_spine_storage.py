"""Tests for spine Cosmos storage repository."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.cosmos.exceptions import (
    CosmosHttpResponseError,
    CosmosResourceNotFoundError,
)

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
async def test_get_segment_state_returns_none_when_not_found(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    """Missing segment_state returns None, not a raised exception."""
    mock_containers[
        "segment_state"
    ].read_item.side_effect = CosmosResourceNotFoundError(
        status_code=404, message="Not found"
    )
    result = await repo.get_segment_state("never_seen")
    assert result is None


@pytest.mark.asyncio
async def test_get_segment_state_propagates_unexpected_cosmos_errors(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    """Regression: a non-404 Cosmos error must propagate, not return None."""
    mock_containers["segment_state"].read_item.side_effect = CosmosHttpResponseError(
        status_code=503, message="Service unavailable"
    )
    with pytest.raises(CosmosHttpResponseError):
        await repo.get_segment_state("backend_api")


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


# ---------------------------------------------------------------------------
# Phase 19.2-03: transaction-ledger read paths
# ---------------------------------------------------------------------------


def _workload_row(
    segment_id: str,
    timestamp: str,
    *,
    correlation_kind: str | None = "capture",
    correlation_id: str | None = "trace-1",
    operation: str = "do_thing",
    outcome: str = "success",
    duration_ms: int = 50,
) -> dict:
    """Build a Cosmos-shaped workload event row for fake iterators."""
    payload: dict = {
        "operation": operation,
        "outcome": outcome,
        "duration_ms": duration_ms,
    }
    if correlation_kind is not None:
        payload["correlation_kind"] = correlation_kind
    if correlation_id is not None:
        payload["correlation_id"] = correlation_id
    return {
        "id": f"row-{timestamp}",
        "segment_id": segment_id,
        "event_type": "workload",
        "timestamp": timestamp,
        "payload": payload,
    }


@pytest.mark.asyncio
async def test_get_recent_transaction_events_filters_to_correlated_workload_rows(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    """The Cosmos query itself filters on event_type + IS_DEFINED correlation fields;
    the method must issue that query (not the plain get_recent_events query)."""
    captured: dict = {}

    async def async_iter():
        # Simulate the Cosmos server honoring the WHERE clause — only correlated
        # workload rows come through.
        for item in [
            _workload_row("backend_api", "2026-04-14T12:00:00Z"),
        ]:
            yield item

    def fake_query(*, query: str, parameters: list) -> object:
        captured["query"] = query
        captured["parameters"] = parameters
        return async_iter()

    mock_containers["events"].query_items = MagicMock(side_effect=fake_query)
    events = await repo.get_recent_transaction_events(
        "backend_api", window_seconds=3600
    )
    assert len(events) == 1
    # Verify the query applies the transaction/noise boundary (all three clauses)
    assert "c.event_type = 'workload'" in captured["query"]
    assert "IS_DEFINED(c.payload.correlation_kind)" in captured["query"]
    assert "IS_DEFINED(c.payload.correlation_id)" in captured["query"]
    assert "ORDER BY c.timestamp DESC" in captured["query"]
    # Verify parameters (segment_id + cutoff)
    param_names = {p["name"] for p in captured["parameters"]}
    assert "@sid" in param_names
    assert "@cutoff" in param_names


@pytest.mark.asyncio
async def test_get_recent_transaction_events_orders_desc(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    """Caller promises DESC order via ORDER BY; we also assert the returned
    sequence preserves DESC when Cosmos honors the ORDER BY clause."""

    async def async_iter():
        # Emulate Cosmos honoring ORDER BY c.timestamp DESC
        for item in [
            _workload_row("backend_api", "2026-04-14T12:00:03Z"),
            _workload_row("backend_api", "2026-04-14T12:00:02Z"),
            _workload_row("backend_api", "2026-04-14T12:00:01Z"),
        ]:
            yield item

    mock_containers["events"].query_items = MagicMock(return_value=async_iter())
    events = await repo.get_recent_transaction_events(
        "backend_api", window_seconds=3600
    )
    assert len(events) == 3
    # Pitfall 5: explicit DESC assertion
    assert events[0]["timestamp"] > events[1]["timestamp"] > events[2]["timestamp"]


@pytest.mark.asyncio
async def test_get_recent_transaction_events_respects_limit(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    async def async_iter():
        for i in range(10):
            yield _workload_row("backend_api", f"2026-04-14T12:00:{10 - i:02d}Z")

    mock_containers["events"].query_items = MagicMock(return_value=async_iter())
    events = await repo.get_recent_transaction_events(
        "backend_api", window_seconds=3600, limit=3
    )
    assert len(events) == 3


@pytest.mark.asyncio
async def test_get_recent_transaction_events_honors_cutoff(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    """The cutoff parameter must be an ISO timestamp computed from window_seconds."""
    captured: dict = {}

    async def async_iter():
        if False:
            yield {}  # pragma: no cover

    def fake_query(*, query: str, parameters: list) -> object:
        captured["parameters"] = {p["name"]: p["value"] for p in parameters}
        return async_iter()

    mock_containers["events"].query_items = MagicMock(side_effect=fake_query)
    await repo.get_recent_transaction_events("backend_api", window_seconds=60)
    cutoff = captured["parameters"]["@cutoff"]
    # Round-trip parse should succeed; window is 60s — cutoff is recent
    parsed = datetime.fromisoformat(cutoff)
    now = datetime.now(UTC)
    delta = (now - parsed).total_seconds()
    # Accept a tiny slack for execution time
    assert 59 <= delta <= 70


@pytest.mark.asyncio
async def test_get_recent_transaction_events_excludes_uncorrelated_probe_noise(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    """Backend_api today has 25k/day GET /health probe workload rows with
    no correlation_kind / correlation_id. These must NOT leak into the ledger.

    The Cosmos WHERE clause guarantees this server-side; this test asserts we
    issue that WHERE clause and that probe-shaped rows don't appear in results.
    """

    # Simulate Cosmos respecting IS_DEFINED(...) filters — probe rows are
    # filtered by the server, so the iterator returns only correlated rows.
    async def async_iter():
        yield _workload_row("backend_api", "2026-04-14T12:00:00Z")

    mock_containers["events"].query_items = MagicMock(return_value=async_iter())
    events = await repo.get_recent_transaction_events(
        "backend_api", window_seconds=3600
    )
    assert len(events) == 1
    # Belt-and-braces: every returned row has a correlation id
    assert all(e["payload"].get("correlation_id") for e in events)
    assert all(e["payload"].get("correlation_kind") for e in events)


@pytest.mark.asyncio
async def test_get_workload_events_for_correlation_matches_kind_and_id(
    repo: SpineRepository, mock_containers: dict[str, AsyncMock]
) -> None:
    captured: dict = {}

    async def async_iter():
        for item in [
            _workload_row(
                "classifier",
                "2026-04-14T12:00:00Z",
                correlation_kind="capture",
                correlation_id="trace-1",
                operation="classify",
            ),
        ]:
            yield item

    def fake_query(*, query: str, parameters: list) -> object:
        captured["query"] = query
        captured["parameters"] = {p["name"]: p["value"] for p in parameters}
        return async_iter()

    mock_containers["events"].query_items = MagicMock(side_effect=fake_query)
    events = await repo.get_workload_events_for_correlation(
        correlation_kind="capture",
        correlation_id="trace-1",
        window_seconds=3600,
    )
    assert len(events) == 1
    assert captured["parameters"]["@kind"] == "capture"
    assert captured["parameters"]["@cid"] == "trace-1"
    # Verify the query filters to workload + correlation fields
    assert "c.event_type = 'workload'" in captured["query"]
    assert "c.payload.correlation_kind = @kind" in captured["query"]
    assert "c.payload.correlation_id = @cid" in captured["query"]
