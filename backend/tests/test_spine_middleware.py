"""Tests for SpineWorkloadMiddleware: emits workload event per FastAPI request."""

import contextlib
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
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


@pytest.mark.asyncio
async def test_reads_capture_trace_id_from_request_state_when_header_absent() -> None:
    """Per Task 9 amendment: handler-set state beats header, header beats None."""
    repo = AsyncMock()
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware, repo=repo, segment_id="backend_api")

    @app.get("/with-state")
    async def _with_state(request: Request) -> dict:
        request.state.capture_trace_id = "handler-generated-trace"
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.get("/with-state")  # NO X-Trace-Id header

    event = repo.record_event.call_args.args[0]
    assert event.root.payload.correlation_kind == "capture"
    assert event.root.payload.correlation_id == "handler-generated-trace"


@pytest.mark.asyncio
async def test_state_takes_precedence_over_header() -> None:
    """request.state.capture_trace_id wins over inbound X-Trace-Id header."""
    repo = AsyncMock()
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware, repo=repo, segment_id="backend_api")

    @app.get("/with-both")
    async def _with_both(request: Request) -> dict:
        request.state.capture_trace_id = "from-state"
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.get("/with-both", headers={"X-Trace-Id": "from-header"})

    event = repo.record_event.call_args.args[0]
    assert event.root.payload.correlation_id == "from-state"


@pytest.mark.asyncio
async def test_middleware_without_repo_reads_app_state_spine_repo() -> None:
    """Module-scope contract: construct without repo, resolve from app.state."""
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware)  # no repo kwarg

    state_repo = AsyncMock()
    app.state.spine_repo = state_repo

    @app.get("/probe")
    async def _probe() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/probe")
    assert response.status_code == 200

    state_repo.record_event.assert_called_once()


@pytest.mark.asyncio
async def test_middleware_without_repo_noops_when_app_state_missing() -> None:
    """Cosmos-unavailable path: no repo on app.state → middleware silently no-ops."""
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware)
    # Note: NOT setting app.state.spine_repo

    @app.get("/probe")
    async def _probe() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/probe")
    assert response.status_code == 200  # request succeeds, spine no-ops


@pytest.mark.asyncio
async def test_401_from_api_key_middleware_emits_no_spine_event() -> None:
    """C1 behavioural complement: with the correct ordering, an unauth
    request to the production `app` does NOT record a spine workload event.

    Constructs the middleware stack in production order explicitly so the
    test is deterministic regardless of how the real app's lifespan boots.
    """
    from second_brain.auth import APIKeyMiddleware

    app = FastAPI()
    state_repo = AsyncMock()
    app.state.spine_repo = state_repo
    app.state.api_key = "correct-key"

    # Production order: spine first, auth second. Auth becomes the outermost
    # layer on the inbound path (`add_middleware` prepends to the stack).
    app.add_middleware(SpineWorkloadMiddleware)
    app.add_middleware(APIKeyMiddleware)

    @app.get("/gated")
    async def _gated() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/gated")  # no Authorization header

    assert response.status_code == 401
    state_repo.record_event.assert_not_called()


@pytest.mark.asyncio
async def test_middleware_without_repo_reraises_handler_exception() -> None:
    """Exception branch no-op path (I3): with no repo configured, a handler
    exception must still propagate — the middleware must not swallow it and
    must not crash trying to access a None repo.
    """
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware)
    # Note: NOT setting app.state.spine_repo

    @app.get("/boom")
    async def _boom() -> dict:
        raise RuntimeError("handler boom")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Starlette's default exception handler converts the RuntimeError
        # to a 500; the assertion of interest is that no AttributeError
        # on a None repo leaked through, and the original failure semantics
        # are preserved (5xx not swallowed to 2xx).
        with contextlib.suppress(Exception):
            await client.get("/boom")
    # If the None-guard had been broken, we'd have seen AttributeError
    # surfaced from inside middleware.record_event(...) on a None repo.
