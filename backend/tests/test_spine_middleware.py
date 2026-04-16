"""Tests for SpineWorkloadMiddleware: emits workload event per FastAPI request."""

import contextlib
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from second_brain.spine.middleware import SpineWorkloadMiddleware


@pytest.fixture
def app_with_middleware():
    app = FastAPI()
    repo = AsyncMock()
    app.add_middleware(
        SpineWorkloadMiddleware,
        repo=repo,
        segment_id="backend_api",
    )

    @app.get("/healthy")
    async def healthy() -> dict:
        return {"ok": True}

    @app.get("/boom")
    async def boom() -> dict:
        raise RuntimeError("Boom")

    return app, repo


@pytest.mark.asyncio
async def test_successful_request_emits_success_workload(app_with_middleware) -> None:
    app, repo = app_with_middleware
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/healthy")
    assert response.status_code == 200
    repo.record_event.assert_called_once()
    event = repo.record_event.call_args.args[0]
    assert event.root.event_type == "workload"
    assert event.root.payload.outcome == "success"
    assert event.root.payload.operation == "GET /healthy"


@pytest.mark.asyncio
async def test_failing_request_emits_failure_workload(app_with_middleware) -> None:
    app, repo = app_with_middleware
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with contextlib.suppress(Exception):
            await client.get("/boom")
    # Middleware should still have recorded a failure event before exception propagation
    repo.record_event.assert_called()
    event = repo.record_event.call_args.args[0]
    assert event.root.payload.outcome == "failure"
    assert event.root.payload.error_class == "RuntimeError"
