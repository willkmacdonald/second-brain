"""Shared test fixtures for the Second Brain backend."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from ag_ui.core import (
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from ag_ui.encoder import EventEncoder
from agent_framework_ag_ui._types import AGUIRequest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

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
        container.query_items = MagicMock()  # Returns an async iterator
        containers[name] = container

    manager.containers = containers
    manager.get_container = MagicMock(side_effect=lambda n: containers[n])

    return manager


class MockAgentFrameworkAgent:
    """Mock AG-UI agent that yields known events without LLM calls.

    Reusable across integration tests. Simulates a complete agent run
    with RUN_STARTED -> message content -> RUN_FINISHED lifecycle.
    """

    async def run_agent(
        self,
        input_data: dict[str, Any],
    ) -> AsyncGenerator:
        """Yield a minimal sequence of AG-UI events."""
        yield RunStartedEvent(thread_id="test-thread", run_id="test-run")
        yield TextMessageStartEvent(message_id="msg-1", role="assistant")
        yield TextMessageContentEvent(
            message_id="msg-1", delta="Hello from echo agent!"
        )
        yield TextMessageEndEvent(message_id="msg-1")
        yield RunFinishedEvent(thread_id="test-thread", run_id="test-run")


@pytest.fixture
def app_with_mocks() -> FastAPI:
    """Create the full FastAPI app with mocked dependencies.

    Includes:
    - Real APIKeyMiddleware with a known test key
    - Real health router
    - Mock AG-UI agent endpoint (no real LLM calls)
    - Mocked CosmosManager on app.state
    """
    app = FastAPI()

    # Include the health router
    app.include_router(health_router)

    # Register mock AG-UI endpoint using the same pattern as test_agui_endpoint.py
    mock_agent = MockAgentFrameworkAgent()

    async def agui_endpoint(request_body: AGUIRequest) -> StreamingResponse:
        async def event_generator() -> AsyncGenerator[str, None]:
            encoder = EventEncoder()
            async for event in mock_agent.run_agent(
                request_body.model_dump(exclude_none=True),
            ):
                yield encoder.encode(event)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    app.post("/api/ag-ui", tags=["AG-UI"])(agui_endpoint)

    # Add API key middleware with known test key
    app.add_middleware(APIKeyMiddleware, api_key=TEST_API_KEY)

    return app


@pytest.fixture
def async_client(app_with_mocks: FastAPI) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient bound to the app_with_mocks fixture."""
    transport = httpx.ASGITransport(app=app_with_mocks)
    return httpx.AsyncClient(transport=transport, base_url="http://test")
