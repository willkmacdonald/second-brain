"""Tests for the /health endpoint."""

from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI

from second_brain.api.health import router


@pytest.fixture
def health_app() -> FastAPI:
    """Create a minimal FastAPI app with just the health router.

    No foundry_client or cosmos_manager on app.state -- simulates
    a startup where Foundry is not configured.
    """
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def health_app_with_foundry() -> FastAPI:
    """Create a FastAPI app with foundry_client set on app.state."""
    app = FastAPI()
    app.include_router(router)
    app.state.foundry_client = MagicMock()
    return app


@pytest.fixture
def health_app_fully_connected() -> FastAPI:
    """Create a FastAPI app with both foundry_client and cosmos_manager set."""
    app = FastAPI()
    app.include_router(router)
    app.state.foundry_client = MagicMock()
    app.state.cosmos_manager = MagicMock()
    return app


@pytest.mark.asyncio
async def test_health_degraded_when_foundry_not_configured(
    health_app: FastAPI,
) -> None:
    """GET /health without foundry_client should return degraded status."""
    transport = httpx.ASGITransport(app=health_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["foundry"] == "not_configured"
    assert data["cosmos"] == "not_configured"


@pytest.mark.asyncio
async def test_health_ok_when_foundry_connected(
    health_app_with_foundry: FastAPI,
) -> None:
    """GET /health with foundry_client should return ok status and foundry connected."""
    transport = httpx.ASGITransport(app=health_app_with_foundry)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["foundry"] == "connected"
    assert data["cosmos"] == "not_configured"


@pytest.mark.asyncio
async def test_health_fully_connected(
    health_app_fully_connected: FastAPI,
) -> None:
    """GET /health with both clients should report all connected."""
    transport = httpx.ASGITransport(app=health_app_fully_connected)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["foundry"] == "connected"
    assert data["cosmos"] == "connected"


@pytest.mark.asyncio
async def test_health_via_app_with_mocks_is_degraded(
    async_client: httpx.AsyncClient,
) -> None:
    """The app_with_mocks fixture does not run lifespan, so foundry is not set."""
    response = await async_client.get(
        "/health",
        headers={"Authorization": "Bearer test-api-key-12345"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["foundry"] == "not_configured"
