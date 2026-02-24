"""Tests for API key authentication middleware.

All tests use a minimal FastAPI app with the APIKeyMiddleware applied.
No real Azure calls are made.
"""

import logging

import httpx
import pytest
from fastapi import FastAPI

from second_brain.auth import APIKeyMiddleware

TEST_API_KEY = "test-api-key-12345"


@pytest.fixture
def auth_app() -> FastAPI:
    """Create a FastAPI app with API key middleware and test routes."""
    app = FastAPI()

    # Set API key on app.state (middleware reads it lazily)
    app.state.api_key = TEST_API_KEY

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/ag-ui")
    async def agui():
        return {"message": "success"}

    @app.get("/docs")
    async def docs():
        return {"docs": True}

    @app.get("/openapi.json")
    async def openapi():
        return {"openapi": "3.0"}

    app.add_middleware(APIKeyMiddleware)
    return app


@pytest.mark.asyncio
async def test_missing_api_key_returns_401(auth_app: FastAPI) -> None:
    """POST /api/ag-ui with no Authorization header returns 401."""
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/ag-ui")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


@pytest.mark.asyncio
async def test_invalid_api_key_returns_401(auth_app: FastAPI) -> None:
    """POST with Authorization: Bearer wrong-key returns 401."""
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/ag-ui",
            headers={"Authorization": "Bearer wrong-key"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


@pytest.mark.asyncio
async def test_valid_api_key_passes(auth_app: FastAPI) -> None:
    """POST with correct Authorization: Bearer <key> returns 200."""
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/ag-ui",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    assert response.json() == {"message": "success"}


@pytest.mark.asyncio
async def test_health_no_auth_required(auth_app: FastAPI) -> None:
    """GET /health with no auth header returns 200."""
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_malformed_auth_header_returns_401(auth_app: FastAPI) -> None:
    """POST with Authorization: NotBearer key returns 401."""
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/ag-ui",
            headers={"Authorization": "NotBearer some-key"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


@pytest.mark.asyncio
async def test_failed_auth_logs_ip_and_timestamp(
    auth_app: FastAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failed auth attempts should log AUTH_FAILED with IP and ISO timestamp."""
    transport = httpx.ASGITransport(app=auth_app)
    with caplog.at_level(logging.WARNING, logger="second_brain.auth"):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            await client.post("/api/ag-ui")

    # Verify log contains expected security information
    assert len(caplog.records) >= 1
    log_message = caplog.records[0].message
    assert "AUTH_FAILED" in log_message
    assert "ip=" in log_message
    assert "timestamp=" in log_message
    assert "path=/api/ag-ui" in log_message
