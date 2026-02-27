"""Shared test fixtures for the Second Brain backend."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from second_brain.api.health import router as health_router
from second_brain.auth import APIKeyMiddleware
from second_brain.config import Settings
from second_brain.db.cosmos import CONTAINER_NAMES, CosmosManager

TEST_API_KEY = "test-api-key-12345"


@pytest.fixture
def settings() -> Settings:
    """Provide test-safe settings with placeholder values."""
    return Settings(
        azure_openai_endpoint="https://test.openai.azure.com/",
        azure_openai_chat_deployment_name="gpt-4o-test",
        cosmos_endpoint="https://test.documents.azure.com:443/",
        key_vault_url="https://test-vault.vault.azure.net/",
        enable_instrumentation=False,
        enable_sensitive_data=False,
    )


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
