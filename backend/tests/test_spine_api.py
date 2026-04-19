"""Tests for spine HTTP endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from second_brain.spine.api import build_spine_router


@pytest.fixture
def client_factory():
    """Build a FastAPI test client with mocked spine dependencies."""

    def _build(repo=None, evaluator=None, adapters=None, registry=None, auth_ok=True):
        repo = repo or AsyncMock()
        evaluator = evaluator or AsyncMock()
        adapters = adapters or MagicMock()
        registry = registry or MagicMock()

        app = FastAPI()
        # Override auth to no-op for tests

        async def fake_auth():
            if not auth_ok:
                raise HTTPException(401, "unauthorized")

        router = build_spine_router(
            repo=repo,
            evaluator=evaluator,
            adapter_registry=adapters,
            segment_registry=registry,
            auth_dependency=fake_auth,
        )
        app.include_router(router)
        return app, repo, evaluator, adapters, registry

    return _build


@pytest.mark.asyncio
async def test_status_endpoint_returns_envelope_and_segments(client_factory) -> None:
    repo = AsyncMock()
    repo.get_all_segment_states.return_value = [
        {
            "id": "backend_api",
            "segment_id": "backend_api",
            "status": "green",
            "headline": "Healthy",
            "last_updated": "2026-04-14T12:00:00Z",
            "evaluator_inputs": {"workload_failure_rate": 0.0},
        }
    ]
    registry = MagicMock()
    cfg = MagicMock(display_name="Backend API", host_segment="container_app")
    registry.all.return_value = [cfg]
    registry.get.return_value = cfg
    cfg.segment_id = "backend_api"
    cfg.name_or_id.return_value = "Backend API"

    app, *_ = client_factory(repo=repo, registry=registry)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/status")
    assert response.status_code == 200
    body = response.json()
    assert "segments" in body
    assert "envelope" in body
    assert body["envelope"]["generated_at"] is not None


@pytest.mark.asyncio
async def test_ingest_endpoint_records_event(client_factory) -> None:
    app, repo, *_ = client_factory()
    payload = {
        "segment_id": "backend_api",
        "event_type": "liveness",
        "timestamp": "2026-04-14T12:00:00Z",
        "payload": {"instance_id": "abc"},
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/spine/ingest", json=payload)
    assert response.status_code == 204
    repo.record_event.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_unauthorized_returns_401(client_factory) -> None:
    app, *_ = client_factory(auth_ok=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/spine/ingest",
            json={
                "segment_id": "backend_api",
                "event_type": "liveness",
                "timestamp": "2026-04-14T12:00:00Z",
                "payload": {"instance_id": "abc"},
            },
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ingest_malformed_payload_returns_422(client_factory) -> None:
    app, repo, *_ = client_factory()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/spine/ingest", json={"event_type": "bogus"})
    assert response.status_code == 422
    repo.record_event.assert_not_called()


@pytest.mark.asyncio
async def test_segment_detail_dispatches_to_adapter(client_factory) -> None:
    adapter = AsyncMock()
    adapter.fetch_detail.return_value = {
        "schema": "azure_monitor_app_insights",
        "app_exceptions": [],
        "app_requests": [],
        "native_url": "https://portal.azure.com",
    }
    adapters = MagicMock()
    adapters.get.return_value = adapter

    app, *_ = client_factory(adapters=adapters)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/segment/backend_api")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["schema"] == "azure_monitor_app_insights"
    assert body["envelope"]["native_url"] == "https://portal.azure.com"


@pytest.mark.asyncio
async def test_segment_detail_unknown_segment_returns_404(client_factory) -> None:
    adapters = MagicMock()
    adapters.get.return_value = None
    app, *_ = client_factory(adapters=adapters)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/segment/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_correlation_endpoint_returns_timeline(client_factory) -> None:
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        {
            "correlation_kind": "capture",
            "correlation_id": "trace-1",
            "segment_id": "backend_api",
            "timestamp": "2026-04-14T12:00:00Z",
            "status": "green",
            "headline": "OK",
        }
    ]
    app, *_ = client_factory(repo=repo)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/correlation/capture/trace-1")
    assert response.status_code == 200
    body = response.json()
    assert body["correlation_kind"] == "capture"
    assert body["correlation_id"] == "trace-1"
    assert len(body["events"]) == 1


# ---------------------------------------------------------------------------
# Phase 19.2-03: transaction ledger routes
# ---------------------------------------------------------------------------


def _cosmos_workload_row(
    segment_id: str,
    timestamp: str,
    *,
    operation: str = "do_thing",
    outcome: str = "success",
    duration_ms: int = 50,
    correlation_kind: str | None = "capture",
    correlation_id: str | None = "trace-1",
    error_class: str | None = None,
) -> dict:
    """Build a Cosmos-shaped workload event row for fake repo returns."""
    payload: dict = {
        "operation": operation,
        "outcome": outcome,
        "duration_ms": duration_ms,
    }
    if correlation_kind is not None:
        payload["correlation_kind"] = correlation_kind
    if correlation_id is not None:
        payload["correlation_id"] = correlation_id
    if error_class is not None:
        payload["error_class"] = error_class
    return {
        "id": f"row-{segment_id}-{timestamp}",
        "segment_id": segment_id,
        "event_type": "workload",
        "timestamp": timestamp,
        "payload": payload,
    }


@pytest.mark.asyncio
async def test_segment_ledger_returns_transaction_rows_for_segment(
    client_factory,
) -> None:
    repo = AsyncMock()
    repo.get_recent_transaction_events.return_value = [
        _cosmos_workload_row(
            "backend_api",
            "2026-04-14T12:00:01Z",
            operation="POST /api/capture",
            outcome="success",
            duration_ms=120,
            correlation_kind="capture",
            correlation_id="trace-1",
        ),
    ]
    app, *_ = client_factory(repo=repo)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/spine/ledger/segment/backend_api?window_seconds=3600&limit=10"
        )
    assert response.status_code == 200
    body = response.json()
    assert body["segment_id"] == "backend_api"
    assert body["mode"] == "transactional"
    assert body["empty_state_reason"] is None
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["segment_id"] == "backend_api"
    assert row["operation"] == "POST /api/capture"
    assert row["outcome"] == "success"
    assert row["duration_ms"] == 120
    assert row["correlation_kind"] == "capture"
    assert row["correlation_id"] == "trace-1"


@pytest.mark.asyncio
async def test_segment_ledger_honors_limit_query_param(client_factory) -> None:
    repo = AsyncMock()
    repo.get_recent_transaction_events.return_value = [
        _cosmos_workload_row("backend_api", f"2026-04-14T12:00:{i:02d}Z")
        for i in range(3)
    ]
    app, *_ = client_factory(repo=repo)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/ledger/segment/backend_api?limit=3")
    assert response.status_code == 200
    body = response.json()
    assert len(body["rows"]) == 3
    # Confirm the limit query param propagated into the repo call
    repo.get_recent_transaction_events.assert_called_once()
    call_kwargs = repo.get_recent_transaction_events.call_args.kwargs
    assert call_kwargs["limit"] == 3


@pytest.mark.asyncio
async def test_segment_ledger_requires_auth(client_factory) -> None:
    app, *_ = client_factory(auth_ok=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/ledger/segment/backend_api")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_segment_ledger_returns_native_only_metadata_for_native_only_segment(
    client_factory,
) -> None:
    """For segments that are native-only by design (cosmos, container_app,
    mobile_ui), the response must carry mode='native_only' + a non-empty
    empty_state_reason so the UI can render a purposeful empty state."""
    repo = AsyncMock()
    repo.get_recent_transaction_events.return_value = []  # native-only = 0 rows
    app, *_ = client_factory(repo=repo)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/ledger/segment/cosmos")
    assert response.status_code == 200
    body = response.json()
    assert body["segment_id"] == "cosmos"
    assert body["mode"] == "native_only"
    assert body["empty_state_reason"]
    assert (
        "native-only" in body["empty_state_reason"].lower()
        or "diagnostics" in body["empty_state_reason"].lower()
    )
    assert body["rows"] == []


@pytest.mark.asyncio
async def test_transaction_path_enriches_with_operation_and_duration(
    client_factory,
) -> None:
    """Correlation rows carry headline/status; raw events carry
    operation/duration. The route must join them by (segment_id, timestamp)."""
    repo = AsyncMock()
    # "Which segments" — from spine_correlation
    repo.get_correlation_events.return_value = [
        {
            "correlation_kind": "capture",
            "correlation_id": "trace-1",
            "segment_id": "classifier",
            "timestamp": "2026-04-14T12:00:00Z",
            "status": "green",
            "headline": "classify success",
        },
    ]
    # "Operation/duration" — from spine_events filtered by correlation
    repo.get_workload_events_for_correlation.return_value = [
        _cosmos_workload_row(
            "classifier",
            "2026-04-14T12:00:00Z",
            operation="classify",
            outcome="success",
            duration_ms=250,
        ),
    ]
    app, *_ = client_factory(repo=repo)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/ledger/correlation/capture/trace-1")
    assert response.status_code == 200
    body = response.json()
    assert body["correlation_kind"] == "capture"
    assert body["correlation_id"] == "trace-1"
    assert len(body["events"]) == 1
    event = body["events"][0]
    assert event["segment_id"] == "classifier"
    assert event["headline"] == "classify success"
    # Enrichment — these must come from the raw event
    assert event["operation"] == "classify"
    assert event["outcome"] == "success"
    assert event["duration_ms"] == 250


@pytest.mark.asyncio
async def test_transaction_path_reports_missing_required_segments_from_ledger_policy(
    client_factory,
) -> None:
    """Capture chain requires mobile_capture, backend_api, classifier.
    Correlation only shows backend_api — the other two required segments
    must surface in missing_required."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        {
            "correlation_kind": "capture",
            "correlation_id": "trace-99",
            "segment_id": "backend_api",
            "timestamp": "2026-04-14T12:00:00Z",
            "status": "green",
            "headline": "ok",
        },
    ]
    repo.get_workload_events_for_correlation.return_value = []
    app, *_ = client_factory(repo=repo)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/ledger/correlation/capture/trace-99")
    assert response.status_code == 200
    body = response.json()
    assert "classifier" in body["missing_required"]
    assert "mobile_capture" in body["missing_required"]
    # backend_api IS seen, so it must NOT appear in missing_required
    assert "backend_api" not in body["missing_required"]


@pytest.mark.asyncio
async def test_transaction_path_reports_unexpected_segments(client_factory) -> None:
    """A segment not listed in the capture chain must show up as unexpected."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        {
            "correlation_kind": "capture",
            "correlation_id": "trace-77",
            "segment_id": "investigation",  # investigation is NOT in capture chain
            "timestamp": "2026-04-14T12:00:00Z",
            "status": "green",
            "headline": "unexpected",
        },
    ]
    repo.get_workload_events_for_correlation.return_value = []
    app, *_ = client_factory(repo=repo)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/ledger/correlation/capture/trace-77")
    assert response.status_code == 200
    body = response.json()
    assert "investigation" in body["unexpected"]


@pytest.mark.asyncio
async def test_transaction_path_reports_present_optional(client_factory) -> None:
    """Optional segments in the chain that DID appear are surfaced in
    present_optional so the UI can confirm the happy-path drift."""
    repo = AsyncMock()
    repo.get_correlation_events.return_value = [
        {
            "correlation_kind": "capture",
            "correlation_id": "trace-ok",
            "segment_id": "admin",  # optional in the capture chain
            "timestamp": "2026-04-14T12:00:00Z",
            "status": "green",
            "headline": "admin handoff",
        },
    ]
    repo.get_workload_events_for_correlation.return_value = []
    app, *_ = client_factory(repo=repo)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/ledger/correlation/capture/trace-ok")
    assert response.status_code == 200
    body = response.json()
    assert "admin" in body["present_optional"]


@pytest.mark.asyncio
async def test_transaction_path_requires_auth(client_factory) -> None:
    app, *_ = client_factory(auth_ok=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/ledger/correlation/capture/trace-1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_segment_ledger_rejects_out_of_bounds_window_seconds(
    client_factory,
) -> None:
    """Bounded time-range — unbounded Cosmos queries would RU-throttle."""
    app, *_ = client_factory()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1d is max
        response = await client.get(
            "/api/spine/ledger/segment/backend_api?window_seconds=999999999"
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_status_suppresses_red_children_of_red_host(client_factory) -> None:
    repo = AsyncMock()
    repo.get_all_segment_states.return_value = [
        {
            "id": "container_app",
            "segment_id": "container_app",
            "status": "red",
            "headline": "host down",
            "last_updated": "2026-04-14T12:00:00Z",
            "evaluator_inputs": {},
        },
        {
            "id": "backend_api",
            "segment_id": "backend_api",
            "status": "red",
            "headline": "api failing",
            "last_updated": "2026-04-14T12:00:00Z",
            "evaluator_inputs": {},
        },
    ]
    registry = MagicMock()
    host_cfg = MagicMock(host_segment=None)
    host_cfg.segment_id = "container_app"
    host_cfg.name_or_id.return_value = "Container App"
    child_cfg = MagicMock(host_segment="container_app")
    child_cfg.segment_id = "backend_api"
    child_cfg.name_or_id.return_value = "Backend API"
    registry.all.return_value = [host_cfg, child_cfg]

    app, *_ = client_factory(repo=repo, registry=registry)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/spine/status")
    assert response.status_code == 200
    body = response.json()
    segments = {s["id"]: s for s in body["segments"]}
    assert segments["backend_api"]["rollup"]["suppressed"] is True
    assert segments["backend_api"]["rollup"]["suppressed_by"] == "container_app"
    assert segments["backend_api"]["rollup"]["raw_status"] == "red"
    assert segments["container_app"]["rollup"]["suppressed"] is False
    assert segments["container_app"]["rollup"]["suppressed_by"] is None
