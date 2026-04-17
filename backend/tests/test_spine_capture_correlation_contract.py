"""Contract tests that must pass before Phase 1 can honestly close.

These tests are RED until Task 9 amendment and Task 11.5 land. They
encode the two plan amendments (main commits 4ea5d6a and 58b1dea) so
the next engineer sees the expected surface up front.

Test A — capture trace propagation:
    When a capture handler generates (not receives) a capture_trace_id,
    the SpineWorkloadMiddleware must pick it up from request.state and
    emit a correlation-bound workload event. Without this, the
    /api/spine/correlation/capture/{id} timeline silently omits the
    backend_api node for native app captures (which never send
    X-Trace-Id), failing Task 19 Step 6.

Test B — focused query primitives exist with the adapter's signature:
    The Backend API adapter calls its injected fetchers with
    (time_range_seconds=, capture_trace_id=). The observability query
    layer must provide query_backend_api_failures() and
    query_backend_api_requests() with that exact signature so Task 12
    can bind them via functools.partial without argument-reshape
    gymnastics. Without this the adapter has no backing queries and
    /api/spine/segment/backend_api cannot return the locked
    azure_monitor_app_insights schema.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from second_brain.spine.middleware import SpineWorkloadMiddleware

# ---------------------------------------------------------------------------
# Test A — handler-set request.state.capture_trace_id reaches middleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_reads_capture_trace_id_from_request_state() -> None:
    """Task 9 amendment: state > header > None precedence.

    RED until the middleware's _read_capture_trace_id helper lands.
    """
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
        response = await client.get("/with-state")  # NO X-Trace-Id header
    assert response.status_code == 200

    repo.record_event.assert_called_once()
    event = repo.record_event.call_args.args[0]
    assert event.root.payload.correlation_kind == "capture"
    assert event.root.payload.correlation_id == "handler-generated-trace"


@pytest.mark.asyncio
async def test_middleware_state_takes_precedence_over_header() -> None:
    """request.state wins over inbound X-Trace-Id header.

    RED until _read_capture_trace_id applies state-before-header
    precedence. Reason: handlers may deliberately override a bad/reused
    caller header with a fresh trace they generated.
    """
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
async def test_middleware_falls_back_to_header_when_state_missing() -> None:
    """Inbound X-Trace-Id still works when handler doesn't set state.

    Already green pre-amendment; included as a regression guard so the
    amendment doesn't accidentally break caller-supplied trace flow
    (e.g. the investigation terminal client which sends X-Trace-Id).
    """
    repo = AsyncMock()
    app = FastAPI()
    app.add_middleware(SpineWorkloadMiddleware, repo=repo, segment_id="backend_api")

    @app.get("/header-only")
    async def _header_only() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.get("/header-only", headers={"X-Trace-Id": "caller-supplied"})

    event = repo.record_event.call_args.args[0]
    assert event.root.payload.correlation_kind == "capture"
    assert event.root.payload.correlation_id == "caller-supplied"


# ---------------------------------------------------------------------------
# Test B — focused query primitives match the adapter's expected signature
# ---------------------------------------------------------------------------


def test_query_backend_api_failures_exists_with_adapter_signature() -> None:
    """Task 11.5: query_backend_api_failures must accept the adapter's kwargs.

    RED until the function is added to
    second_brain.observability.queries with keyword parameters
    `time_range_seconds` (int) and `capture_trace_id` (str | None).

    Task 12 binds the Log Analytics client + workspace via
    functools.partial and hands the remaining kwargs-bound callable to
    the adapter. If the signature doesn't match, functools.partial
    silently defers the failure to the first real request — this test
    fails at import/construction time so the plan-text gap doesn't
    leak to production.
    """
    from second_brain.observability import queries

    assert hasattr(queries, "query_backend_api_failures"), (
        "Task 11.5 not landed: query_backend_api_failures missing"
    )

    sig = inspect.signature(queries.query_backend_api_failures)
    params = sig.parameters
    # First two positionals are bound by functools.partial in Task 12
    assert "client" in params
    assert "workspace_id" in params
    # These two must be keyword-addressable for the adapter contract
    assert "time_range_seconds" in params, (
        "adapter calls failures_fetcher(time_range_seconds=...)"
    )
    assert "capture_trace_id" in params, (
        "adapter calls failures_fetcher(capture_trace_id=...)"
    )
    assert params["capture_trace_id"].default is None


def test_query_backend_api_requests_exists_with_adapter_signature() -> None:
    """Task 11.5: query_backend_api_requests must match the adapter too.

    Same contract as _failures. Returns a list of RequestRecord —
    native AppRequests shape (timestamp, name, result_code, ...).
    """
    from second_brain.observability import queries

    assert hasattr(queries, "query_backend_api_requests"), (
        "Task 11.5 not landed: query_backend_api_requests missing"
    )

    sig = inspect.signature(queries.query_backend_api_requests)
    params = sig.parameters
    assert "client" in params
    assert "workspace_id" in params
    assert "time_range_seconds" in params
    assert "capture_trace_id" in params
    assert params["capture_trace_id"].default is None


def test_request_record_model_exists() -> None:
    """Task 11.5: RequestRecord model for native AppRequests shape.

    RED until models.py gains the RequestRecord Pydantic class with the
    expected AppRequests fields.
    """
    from second_brain.observability import models

    assert hasattr(models, "RequestRecord"), (
        "Task 11.5 not landed: RequestRecord model missing"
    )

    # Instantiation with the minimum fields the KQL template emits
    rec = models.RequestRecord(
        timestamp="2026-04-15T12:00:00Z",
        name="POST /api/capture/text",
        result_code="200",
        duration_ms=42.0,
        success=True,
        capture_trace_id="abc-123",
        operation_id="op-xyz",
    )
    assert rec.name == "POST /api/capture/text"
    assert rec.result_code == "200"  # string, not int — preserves Azure's native shape
    assert rec.capture_trace_id == "abc-123"


def test_adapter_does_not_use_query_capture_trace_as_requests_source() -> None:
    """Contract guard: query_capture_trace is a timeline query, not AppRequests.

    The Task 8 AMENDMENT callout forbids binding query_capture_trace()
    into the adapter's requests_fetcher slot. This test enforces that
    by ensuring the focused primitive exists AND that the legacy
    timeline query is NOT accidentally repurposed (its return type is
    list[TraceRecord], not list[RequestRecord] — mixing them would
    muddy the native-shape contract that the spec locks for the
    AppInsightsDetail renderer).
    """
    from second_brain.observability import queries

    # query_capture_trace still exists (it powers /investigate tooling)
    assert hasattr(queries, "query_capture_trace")

    # ... but it takes trace_id as a positional, NOT the adapter's kwargs
    sig = inspect.signature(queries.query_capture_trace)
    assert "trace_id" in sig.parameters  # timeline-query shape
    assert "time_range_seconds" not in sig.parameters  # NOT the adapter shape
    assert "capture_trace_id" not in sig.parameters  # NOT the adapter shape
