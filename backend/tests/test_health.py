"""Tests for the /health endpoint."""

import httpx
import pytest
from fastapi import FastAPI

from second_brain.api.health import router


@pytest.fixture
def health_app() -> FastAPI:
    """Create a minimal FastAPI app with just the health router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_health_returns_200(health_app: FastAPI) -> None:
    """GET /health should return 200 with status ok."""
    transport = httpx.ASGITransport(app=health_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
