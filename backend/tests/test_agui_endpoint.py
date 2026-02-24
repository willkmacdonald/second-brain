"""Tests for the AG-UI endpoint at /api/ag-ui."""

from collections.abc import AsyncGenerator
from typing import Any

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


class MockAgentFrameworkAgent:
    """Mock AG-UI agent that yields known events without LLM calls."""

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


def _create_mock_endpoint(
    mock_agent: MockAgentFrameworkAgent,
):
    """Create a mock endpoint handler that streams AG-UI events."""

    async def agent_endpoint(
        request_body: AGUIRequest,
    ) -> StreamingResponse:
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

    return agent_endpoint


@pytest.fixture
def agui_app() -> FastAPI:
    """Create a FastAPI app with a mock AG-UI agent endpoint."""
    app = FastAPI()
    mock_agent = MockAgentFrameworkAgent()
    app.post("/api/ag-ui", tags=["AG-UI"])(_create_mock_endpoint(mock_agent))
    return app


SAMPLE_REQUEST = {
    "messages": [
        {
            "id": "msg-user-1",
            "role": "user",
            "content": "Hello, echo!",
        }
    ],
    "thread_id": "test-thread",
    "run_id": "test-run",
}


@pytest.mark.asyncio
async def test_agui_endpoint_returns_sse_stream(
    agui_app: FastAPI,
) -> None:
    """POST /api/ag-ui should return a text/event-stream response."""
    transport = httpx.ASGITransport(app=agui_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/ag-ui", json=SAMPLE_REQUEST)

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_agui_endpoint_contains_expected_events(
    agui_app: FastAPI,
) -> None:
    """POST /api/ag-ui response should contain expected AG-UI events."""
    transport = httpx.ASGITransport(app=agui_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/ag-ui", json=SAMPLE_REQUEST)

    body = response.text

    # AG-UI events are SSE formatted: "event: TYPE\ndata: {...}\n\n"
    assert "RUN_STARTED" in body
    assert "TEXT_MESSAGE_CONTENT" in body
    assert "RUN_FINISHED" in body
    assert "Hello from echo agent!" in body
