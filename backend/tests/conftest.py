"""Shared test fixtures for the Second Brain backend."""

import importlib
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from second_brain.api.health import router as health_router
from second_brain.auth import APIKeyMiddleware
from second_brain.db.cosmos import CONTAINER_NAMES, CosmosManager

# ---------------------------------------------------------------------------
# MCP server module registration
#
# The local mcp/server.py lives outside the backend package but its tests
# run inside the backend test suite. The installed `mcp` pip package also
# occupies the `mcp.server` dotted path (as a sub-package), so we cannot
# rely on sys.path ordering to resolve to the local file.
#
# Strategy:
#   1. Pre-load the installed mcp.server sub-packages (fastmcp, session)
#      so they are cached in sys.modules before we overwrite mcp.server.
#   2. Load the local server.py via importlib with the name 'mcp.server'.
#   3. Restore the cached sub-packages under their original keys so the
#      local server.py's own `from mcp.server.fastmcp import ...` calls
#      still resolve to the installed implementations.
#
# This runs once at session start and is idempotent.
# ---------------------------------------------------------------------------

_LOCAL_SERVER_PATH = Path(__file__).parent.parent.parent / "mcp" / "server.py"


def _register_local_mcp_server() -> None:
    """Load mcp/server.py into sys.modules as 'mcp.server'.

    Safe to call multiple times; no-ops if already registered.
    """
    if "mcp.server" in sys.modules and getattr(
        sys.modules["mcp.server"], "__file__", ""
    ) == str(_LOCAL_SERVER_PATH):
        return  # Already registered — nothing to do

    # Step 1: ensure the installed sub-packages are cached.
    for sub in ("mcp.server.fastmcp", "mcp.server.session"):
        importlib.import_module(sub)
    fastmcp_mod = sys.modules["mcp.server.fastmcp"]
    session_mod = sys.modules["mcp.server.session"]

    # Step 2: load the local file under the mcp.server key.
    spec = importlib.util.spec_from_file_location("mcp.server", _LOCAL_SERVER_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mcp.server"] = mod

    # Step 3: restore sub-package cache before executing the module so its
    # top-level `from mcp.server.fastmcp import ...` lines succeed.
    sys.modules["mcp.server.fastmcp"] = fastmcp_mod
    sys.modules["mcp.server.session"] = session_mod

    spec.loader.exec_module(mod)  # type: ignore[union-attr]


_register_local_mcp_server()

TEST_API_KEY = "test-api-key-12345"


@pytest.fixture
def mock_cosmos_manager() -> CosmosManager:
    """Return a mock CosmosManager with mock containers.

    Each container has async mocks for create_item, read_item,
    and query_items. No real Azure calls are made.
    """
    manager = MagicMock(spec=CosmosManager)

    containers: dict = {}
    for name in CONTAINER_NAMES:
        container = MagicMock()
        container.create_item = AsyncMock()
        container.read_item = AsyncMock()
        container.upsert_item = AsyncMock()
        container.delete_item = AsyncMock()
        container.query_items = MagicMock()  # Returns an async iterator
        containers[name] = container

    manager.containers = containers
    manager.get_container = MagicMock(side_effect=lambda n: containers[n])

    return manager


@pytest.fixture
def app_with_mocks() -> FastAPI:
    """Create a FastAPI app with mocked dependencies.

    Includes:
    - Real APIKeyMiddleware with a known test key
    - Real health router
    - Mocked CosmosManager on app.state
    """
    app = FastAPI()

    # Include the health router
    app.include_router(health_router)

    # Set API key on app.state (middleware reads it lazily)
    app.state.api_key = TEST_API_KEY

    # Add API key middleware
    app.add_middleware(APIKeyMiddleware)

    return app


@pytest.fixture
def async_client(app_with_mocks: FastAPI) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient bound to the app_with_mocks fixture."""
    transport = httpx.ASGITransport(app=app_with_mocks)
    return httpx.AsyncClient(transport=transport, base_url="http://test")
