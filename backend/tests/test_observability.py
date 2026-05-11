"""Tests for Phase 17.4 observability features.

Covers: health endpoint cache, warmup self-heal, investigation timeout.

Phase 24 plan 24-18 cleanup: the parameterized-middleware tests previously
in this file have been REMOVED because they exercised the RC-era
`AuditAgentMiddleware` class in `agents/middleware.py`, which is deleted
by plan 24-18 (F-17). The replacement GA middleware lives at
`agents/agent_middleware/capture_trace.py` (`CaptureTraceAgentMiddleware` /
`CaptureTraceFunctionMiddleware`). The GA classes do NOT take an
`agent_name` constructor arg -- they read `capture.trace_id` from a
ContextVar instead -- so the assertions about `_span_name == "classifier_agent_run"`
no longer apply. Coverage of the GA middleware lives in
`tests/test_agent_middleware_capture_trace.py` (added in plan 24-03).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from second_brain.api.health import router
from second_brain.warmup import MAX_CONSECUTIVE_FAILURES, agent_warmup_loop

# ---------------------------------------------------------------------------
# Health endpoint helpers (GA-shape — Phase 24 plan 24-22)
# ---------------------------------------------------------------------------
#
# Phase 24 plan 24-19 retired the RC `AzureAIAgentClient` (formerly
# `app.state.foundry_client`); the /health probe was rewritten in plan 24-22
# (post-deploy hotfix) to read per-agent readiness from
# `app.state.classifier_agent` / `admin_agent` / `investigation_agent`
# (the GA `Agent` instances built via `build_*_agent` factories). The legacy
# `_FOUNDRY_CACHE_TTL` + list_agents TTL cache + foundry_client probe no
# longer exist. Health is now a pure attribute presence check.


def _make_health_app(
    *,
    classifier_agent: object | None = None,
    admin_agent: object | None = None,
    investigation_agent: object | None = None,
    cosmos_manager: object | None = None,
) -> FastAPI:
    """Build a minimal FastAPI app with the health router and mock state."""
    app = FastAPI()
    app.include_router(router)
    app.state.classifier_agent = classifier_agent
    app.state.admin_agent = admin_agent
    app.state.investigation_agent = investigation_agent
    app.state.cosmos_manager = cosmos_manager
    return app


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------


def test_health_ok_when_all_three_agents_present() -> None:
    """All three GA agents on app.state -> foundry=connected, status=ok."""
    app = _make_health_app(
        classifier_agent=MagicMock(),
        admin_agent=MagicMock(),
        investigation_agent=MagicMock(),
        cosmos_manager=MagicMock(),
    )

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["foundry"] == "connected"
        assert data["cosmos"] == "connected"
        assert data["admin_agent"] == "ready"
        assert data["investigation_agent"] == "ready"


def test_health_degraded_when_any_agent_missing() -> None:
    """If at least one but not all three agents present -> foundry=degraded."""
    app = _make_health_app(
        classifier_agent=MagicMock(),
        admin_agent=None,  # missing
        investigation_agent=MagicMock(),
    )

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["foundry"] == "degraded"
        assert data["status"] == "degraded"
        assert data["admin_agent"] == "not_initialized"
        assert data["investigation_agent"] == "ready"


def test_health_not_configured_when_no_agents() -> None:
    """No agents on app.state -> foundry=not_configured, status=degraded."""
    app = _make_health_app()

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["foundry"] == "not_configured"
        assert data["status"] == "degraded"
        assert data["admin_agent"] == "not_initialized"
        assert data["investigation_agent"] == "not_initialized"


def test_health_investigation_agent_status_toggles_with_attr() -> None:
    """investigation_agent field reflects app.state.investigation_agent presence."""
    app_ready = _make_health_app(investigation_agent=MagicMock())
    with TestClient(app_ready) as client:
        assert client.get("/health").json()["investigation_agent"] == "ready"

    app_missing = _make_health_app(investigation_agent=None)
    with TestClient(app_missing) as client:
        assert client.get("/health").json()["investigation_agent"] == "not_initialized"


# ---------------------------------------------------------------------------
# Warmup self-heal tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_warmup_recreates_agent_after_consecutive_failures() -> None:
    """After MAX_CONSECUTIVE_FAILURES pings fail, factory is called.

    Phase 24 plan 24-19: warmup loop migrated to GA. The loop now pings via
    ``agent.run("ping")`` instead of ``client.get_response(...)``; the
    self-heal factory rebuilds an ``Agent`` rather than an ``AzureAIAgentClient``.
    """
    failing_agent = AsyncMock()
    failing_agent.run = AsyncMock(side_effect=ConnectionError("down"))

    new_agent = MagicMock()
    factory = MagicMock(return_value=new_agent)
    on_recreate = MagicMock()

    agents: list[tuple[str, object]] = [("test_agent", failing_agent)]
    iteration = 0

    async def _fake_sleep(seconds: float) -> None:
        nonlocal iteration
        iteration += 1
        if iteration > MAX_CONSECUTIVE_FAILURES:
            raise asyncio.CancelledError  # break the loop

    with (
        patch("second_brain.warmup.asyncio.sleep", side_effect=_fake_sleep),
        pytest.raises(asyncio.CancelledError),
    ):
        await agent_warmup_loop(
            agents=agents,
            interval_seconds=1,
            agent_factories={"test_agent": factory},
            on_recreate=on_recreate,
        )

    factory.assert_called_once()
    on_recreate.assert_called_once_with("test_agent", new_agent)


@pytest.mark.asyncio
async def test_warmup_resets_failure_count_on_success() -> None:
    """Success between failures resets the counter — no recreation.

    Phase 24 plan 24-19 GA signature: ``agent.run("ping")`` is the ping path.
    """
    call_count = 0

    async def _alternating_response(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal call_count
        call_count += 1
        # Fail twice, succeed once, fail twice — never hits 3 consecutive
        if call_count in (1, 2, 4, 5):
            raise ConnectionError("down")

    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(side_effect=_alternating_response)

    factory = MagicMock()
    agents: list[tuple[str, object]] = [("test_agent", mock_agent)]
    iteration = 0

    async def _fake_sleep(seconds: float) -> None:
        nonlocal iteration
        iteration += 1
        if iteration > 5:
            raise asyncio.CancelledError

    with (
        patch("second_brain.warmup.asyncio.sleep", side_effect=_fake_sleep),
        pytest.raises(asyncio.CancelledError),
    ):
        await agent_warmup_loop(
            agents=agents,
            interval_seconds=1,
            agent_factories={"test_agent": factory},
        )

    # Factory never called because success at call 3 resets counter
    factory.assert_not_called()


# ---------------------------------------------------------------------------
# Investigation timeout
# ---------------------------------------------------------------------------


def test_investigate_timeout_is_30s() -> None:
    """Investigation adapter uses a 30-second timeout."""
    import inspect

    import second_brain.streaming.investigation_adapter as mod

    source = inspect.getsource(mod.stream_investigation)
    assert "timeout(30)" in source
