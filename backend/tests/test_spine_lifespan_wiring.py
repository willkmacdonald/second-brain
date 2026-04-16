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
from second_brain.spine.storage import SpineRepository  # noqa: E402

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

    evaluator_task, liveness_task = await _wire_spine(app, settings_stub)

    assert evaluator_task is None
    assert liveness_task is None
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

    evaluator_task, liveness_task = await _wire_spine(app, settings_stub)
    try:
        assert isinstance(evaluator_task, asyncio.Task)
        assert isinstance(liveness_task, asyncio.Task)
        assert isinstance(app.state.spine_repo, SpineRepository)
        # BackendApiAdapter not wired because logs_client is None
        assert not app.state.spine_adapter_registry.has("backend_api")
        # Spine router is still mounted
        assert any(getattr(r, "path", "").startswith("/api/spine") for r in app.routes)
    finally:
        for t in (evaluator_task, liveness_task):
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t


async def test_wire_spine_full_happy_path(settings_stub) -> None:
    """Full wiring: tasks, repo, and BackendApiAdapter all present."""
    app = FastAPI()
    app.state.cosmos_manager = _fake_cosmos_manager_with_containers()
    app.state.logs_client = AsyncMock()

    evaluator_task, liveness_task = await _wire_spine(app, settings_stub)
    try:
        assert isinstance(evaluator_task, asyncio.Task)
        assert isinstance(liveness_task, asyncio.Task)
        assert isinstance(app.state.spine_repo, SpineRepository)
        assert app.state.spine_adapter_registry.has("backend_api")
        # Spine router mounted
        assert any(getattr(r, "path", "").startswith("/api/spine") for r in app.routes)
    finally:
        for t in (evaluator_task, liveness_task):
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t


async def test_wire_spine_shutdown_cancels_tasks_cleanly(settings_stub) -> None:
    """Shutdown: cancel tasks after loop entry; no CancelledError leaks."""
    app = FastAPI()
    app.state.cosmos_manager = _fake_cosmos_manager_with_containers()
    app.state.logs_client = AsyncMock()

    evaluator_task, liveness_task = await _wire_spine(app, settings_stub)
    # Let the tasks enter their loop at least once
    await asyncio.sleep(0)

    for t in (evaluator_task, liveness_task):
        t.cancel()
    for t in (evaluator_task, liveness_task):
        with contextlib.suppress(asyncio.CancelledError):
            await t
    # Both tasks done after cancellation
    assert evaluator_task.done()
    assert liveness_task.done()
