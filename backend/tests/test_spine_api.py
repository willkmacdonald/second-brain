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
