"""Integration tests for _wire_spine in main.py.

second_brain.main calls configure_azure_monitor() at module scope, which
requires a live Application Insights connection string. We neutralise it by
importing azure.monitor.opentelemetry first and replacing configure_azure_monitor
with a no-op on the already-cached module object before second_brain.main is
imported. This is safe because the real package is installed and importable;
it is only the call that requires a connection string.
"""

from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Neutralise configure_azure_monitor BEFORE importing second_brain.main.
# Import the real package so sys.modules is populated, then replace the
# callable with a no-op. main.py does `from azure.monitor.opentelemetry
# import configure_azure_monitor` — Python resolves that from sys.modules,
# picking up the patched attribute.
# ---------------------------------------------------------------------------
import azure.monitor.opentelemetry as _az_monitor_otel  # noqa: E402
import pytest
from fastapi import FastAPI

_az_monitor_otel.configure_azure_monitor = lambda *a, **kw: None  # type: ignore[attr-defined]

from second_brain.main import _wire_spine  # noqa: E402
from second_brain.main import app as production_app  # noqa: E402
from second_brain.spine.storage import SpineRepository  # noqa: E402

# ---------------------------------------------------------------------------
# Production middleware ordering (C1 regression)
# ---------------------------------------------------------------------------


def test_production_app_has_api_key_middleware_outermost() -> None:
    """C1 regression: APIKeyMiddleware must be the OUTERMOST middleware so
    auth gates before SpineWorkloadMiddleware observes a request. If spine
    sits outside auth, 401s from unauthenticated requests still flow through
    spine and pollute the backend_api workload dataset.

    Starlette's `add_middleware` PREPENDS to `app.user_middleware` — so the
    LAST-registered call becomes index 0 (outermost, runs first on inbound).
    For auth to be outermost: APIKeyMiddleware must be registered AFTER
    SpineWorkloadMiddleware in main.py, which places it at user_middleware[0].

    Red against commit 41ac1a0 where the order was reversed (spine at [0]).
    """
    from second_brain.auth import APIKeyMiddleware
    from second_brain.spine.middleware import SpineWorkloadMiddleware

    stack_classes = [m.cls for m in production_app.user_middleware]
    assert APIKeyMiddleware in stack_classes, (
        "APIKeyMiddleware missing from production app"
    )
    assert SpineWorkloadMiddleware in stack_classes, (
        "SpineWorkloadMiddleware missing from production app"
    )
    # Index 0 of user_middleware is the OUTERMOST (runs first on inbound).
    auth_idx = stack_classes.index(APIKeyMiddleware)
    spine_idx = stack_classes.index(SpineWorkloadMiddleware)
    assert auth_idx < spine_idx, (
        "Middleware order wrong: APIKeyMiddleware must be OUTERMOST "
        "(user_middleware[0]) so auth gates before spine observes. "
        "Fix by registering SpineWorkloadMiddleware BEFORE APIKeyMiddleware "
        "in main.py (so APIKeyMiddleware's add_middleware call runs LAST, "
        f"prepending it to index 0). Got stack (outermost first): {stack_classes}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_cosmos_manager_with_containers() -> MagicMock:
    mgr = MagicMock()
    mgr.get_container.side_effect = lambda name: AsyncMock(name=f"container:{name}")
    return mgr


@pytest.fixture
def settings_stub() -> SimpleNamespace:
    return SimpleNamespace(log_analytics_workspace_id="ws-id")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_wire_spine_skipped_when_cosmos_manager_none(settings_stub) -> None:
    """Cosmos-unavailable skip: returns (None, None) and sets no spine state."""
    app = FastAPI()
    app.state.cosmos_manager = None
    app.state.logs_client = AsyncMock()

    evaluator_task, liveness_tasks = await _wire_spine(app, settings_stub)

    assert evaluator_task is None
    assert liveness_tasks == []
    assert getattr(app.state, "spine_repo", None) is None
    # No spine routes mounted
    assert not any(getattr(r, "path", "").startswith("/api/spine") for r in app.routes)


async def test_wire_spine_without_logs_client_omits_backend_api_adapter(
    settings_stub,
) -> None:
    """Logs-unavailable degradation: tasks still start, but BackendApiAdapter absent."""
    app = FastAPI()
    app.state.cosmos_manager = _fake_cosmos_manager_with_containers()
    app.state.logs_client = None  # logs unavailable

    evaluator_task, liveness_tasks = await _wire_spine(app, settings_stub)
    try:
        assert isinstance(evaluator_task, asyncio.Task)
        assert len(liveness_tasks) > 0
        assert isinstance(app.state.spine_repo, SpineRepository)
        # BackendApiAdapter not wired because logs_client is None
        assert not app.state.spine_adapter_registry.has("backend_api")
        # Spine router is still mounted
        assert any(getattr(r, "path", "").startswith("/api/spine") for r in app.routes)
    finally:
        for t in [evaluator_task, *liveness_tasks]:
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t


async def test_wire_spine_full_happy_path(settings_stub) -> None:
    """Full wiring: tasks, repo, and BackendApiAdapter all present."""
    app = FastAPI()
    app.state.cosmos_manager = _fake_cosmos_manager_with_containers()
    app.state.logs_client = AsyncMock()

    evaluator_task, liveness_tasks = await _wire_spine(app, settings_stub)
    try:
        assert isinstance(evaluator_task, asyncio.Task)
        # 6 liveness emitters (all segments except container_app)
        assert len(liveness_tasks) == 6
        assert isinstance(app.state.spine_repo, SpineRepository)
        assert app.state.spine_adapter_registry.has("backend_api")
        # Spine router mounted
        assert any(getattr(r, "path", "").startswith("/api/spine") for r in app.routes)
    finally:
        for t in [evaluator_task, *liveness_tasks]:
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t


async def test_wire_spine_shutdown_cancels_tasks_cleanly(settings_stub) -> None:
    """Shutdown: cancel tasks after loop entry; no CancelledError leaks."""
    app = FastAPI()
    app.state.cosmos_manager = _fake_cosmos_manager_with_containers()
    app.state.logs_client = AsyncMock()

    evaluator_task, liveness_tasks = await _wire_spine(app, settings_stub)
    # Let the tasks enter their loop at least once
    await asyncio.sleep(0)

    all_tasks = [evaluator_task, *liveness_tasks]
    for t in all_tasks:
        t.cancel()
    for t in all_tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await t
    # All tasks done after cancellation
    assert evaluator_task.done()
    assert all(t.done() for t in liveness_tasks)


async def test_wire_spine_partial_failure_leaves_no_stale_state(
    settings_stub, monkeypatch
) -> None:
    """I1 + I2: if wiring fails AFTER tasks are created (e.g. build_spine_router
    raises), the `except` block must cancel in-flight tasks, null both
    app.state.spine_repo and app.state.spine_adapter_registry, and leave no
    spine routes mounted.

    Injection site: monkeypatch second_brain.spine.api.build_spine_router to
    raise. That's the module _wire_spine imports-from (deferred); patching
    there is seen by the fresh import inside _wire_spine.
    """
    app = FastAPI()
    app.state.cosmos_manager = _fake_cosmos_manager_with_containers()
    app.state.logs_client = AsyncMock()

    import second_brain.spine.api as spine_api_mod

    def _boom(*a, **kw):
        raise RuntimeError("simulated build_spine_router failure")

    monkeypatch.setattr(spine_api_mod, "build_spine_router", _boom)

    evaluator_task, liveness_tasks = await _wire_spine(app, settings_stub)

    assert evaluator_task is None
    assert liveness_tasks == []
    assert app.state.spine_repo is None
    assert app.state.spine_adapter_registry is None
    assert not any(getattr(r, "path", "").startswith("/api/spine") for r in app.routes)
