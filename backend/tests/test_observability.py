"""Tests for Phase 17.4 observability features.

Covers: parameterized middleware, health endpoint cache, warmup self-heal,
investigation timeout.
"""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from second_brain.agents.middleware import AuditAgentMiddleware
from second_brain.api.health import _FOUNDRY_CACHE_TTL, router
from second_brain.warmup import MAX_CONSECUTIVE_FAILURES, agent_warmup_loop

# ---------------------------------------------------------------------------
# Parameterized middleware
# ---------------------------------------------------------------------------


def test_parameterized_middleware_sets_distinct_span_names() -> None:
    """Each agent gets its own span name via the agent_name constructor arg."""
    classifier = AuditAgentMiddleware(agent_name="classifier")
    admin = AuditAgentMiddleware(agent_name="admin")
    investigation = AuditAgentMiddleware(agent_name="investigation")

    assert classifier._span_name == "classifier_agent_run"
    assert classifier._agent_name == "classifier"

    assert admin._span_name == "admin_agent_run"
    assert admin._agent_name == "admin"

    assert investigation._span_name == "investigation_agent_run"
    assert investigation._agent_name == "investigation"


def test_parameterized_middleware_default_is_classifier() -> None:
    """Default agent_name is 'classifier' for backwards compat."""
    mw = AuditAgentMiddleware()
    assert mw._agent_name == "classifier"
    assert mw._span_name == "classifier_agent_run"


# ---------------------------------------------------------------------------
# Health endpoint helpers
# ---------------------------------------------------------------------------


def _make_health_app(
    *,
    foundry_client: object | None = None,
    cosmos_manager: object | None = None,
    admin_client: object | None = None,
    investigation_client: object | None = None,
) -> FastAPI:
    """Build a minimal FastAPI app with the health router and mock state."""
    app = FastAPI()
    app.include_router(router)
    app.state.foundry_client = foundry_client
    app.state.cosmos_manager = cosmos_manager
    app.state.admin_client = admin_client
    app.state.investigation_client = investigation_client
    return app


class _FakeAgentsClient:
    """Simulates foundry_client.agents_client.list_agents()."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self._should_fail = should_fail
        self.call_count = 0

    async def list_agents(self, limit: int = 10):  # noqa: ANN201
        self.call_count += 1
        if self._should_fail:
            raise ConnectionError("Foundry is down")
        yield MagicMock()  # async generator yielding one item


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------


def test_health_cache_returns_cached_result_within_ttl() -> None:
    """Second /health call within TTL uses cached result (no Foundry ping)."""
    agents_client = _FakeAgentsClient()
    foundry = SimpleNamespace(agents_client=agents_client)
    app = _make_health_app(foundry_client=foundry)

    with TestClient(app) as client:
        r1 = client.get("/health")
        assert r1.status_code == 200
        assert r1.json()["foundry"] == "connected"

        r2 = client.get("/health")
        assert r2.status_code == 200
        assert r2.json()["foundry"] == "connected"

    # list_agents called only once (second hit cache)
    assert agents_client.call_count == 1


def test_health_cache_expires_after_ttl() -> None:
    """After TTL expires, /health makes a fresh Foundry ping."""
    agents_client = _FakeAgentsClient()
    foundry = SimpleNamespace(agents_client=agents_client)
    app = _make_health_app(foundry_client=foundry)

    with TestClient(app) as client:
        client.get("/health")
        assert agents_client.call_count == 1

        # Fast-forward past TTL
        with patch("second_brain.api.health.time") as mock_time:
            # Return a time well past the TTL
            mock_time.monotonic.return_value = (
                time.monotonic() + _FOUNDRY_CACHE_TTL + 10
            )
            client.get("/health")

    assert agents_client.call_count == 2


def test_health_returns_degraded_when_foundry_ping_fails() -> None:
    """Failed Foundry ping results in 'degraded' status."""
    agents_client = _FakeAgentsClient(should_fail=True)
    foundry = SimpleNamespace(agents_client=agents_client)
    app = _make_health_app(foundry_client=foundry)

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["foundry"] == "degraded"
        assert data["status"] == "degraded"


def test_health_includes_investigation_agent_status() -> None:
    """Investigation agent status is included in health response."""
    # With investigation client
    app = _make_health_app(investigation_client=MagicMock())
    with TestClient(app) as client:
        data = client.get("/health").json()
        assert data["investigation_agent"] == "ready"

    # Without investigation client
    app = _make_health_app(investigation_client=None)
    with TestClient(app) as client:
        data = client.get("/health").json()
        assert data["investigation_agent"] == "not_initialized"


# ---------------------------------------------------------------------------
# Warmup self-heal tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_warmup_recreates_client_after_consecutive_failures() -> None:
    """After MAX_CONSECUTIVE_FAILURES pings fail, factory is called."""
    failing_client = AsyncMock()
    failing_client.get_response = AsyncMock(side_effect=ConnectionError("down"))

    new_client = MagicMock()
    factory = MagicMock(return_value=new_client)
    on_recreate = MagicMock()

    clients: list[tuple[str, object]] = [("test_agent", failing_client)]
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
            clients=clients,
            interval_seconds=1,
            client_factories={"test_agent": factory},
            on_recreate=on_recreate,
        )

    factory.assert_called_once()
    on_recreate.assert_called_once_with("test_agent", new_client)


@pytest.mark.asyncio
async def test_warmup_resets_failure_count_on_success() -> None:
    """Success between failures resets the counter — no recreation."""
    call_count = 0

    async def _alternating_response(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal call_count
        call_count += 1
        # Fail twice, succeed once, fail twice — never hits 3 consecutive
        if call_count in (1, 2, 4, 5):
            raise ConnectionError("down")

    mock_client = AsyncMock()
    mock_client.get_response = AsyncMock(side_effect=_alternating_response)

    factory = MagicMock()
    clients: list[tuple[str, object]] = [("test_agent", mock_client)]
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
            clients=clients,
            interval_seconds=1,
            client_factories={"test_agent": factory},
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
