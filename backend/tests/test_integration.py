"""End-to-end integration tests for the full Phase 1 stack.

Validates the complete middleware -> routing -> agent -> SSE pipeline
using mocked Azure services (no real LLM or Cosmos calls).
"""

import httpx
import pytest

# Same test key as conftest.py app_with_mocks fixture
TEST_API_KEY = "test-api-key-12345"

SAMPLE_AGUI_REQUEST = {
    "messages": [
        {
            "id": "msg-user-1",
            "role": "user",
            "content": "Hello, integration test!",
        }
    ],
    "thread_id": "integration-thread",
    "run_id": "integration-run",
}


@pytest.mark.asyncio
async def test_full_stack_auth_to_sse_response(
    async_client: httpx.AsyncClient,
) -> None:
    """Authenticated POST to /api/ag-ui returns SSE with expected AG-UI events.

    Validates: auth middleware passes -> AG-UI endpoint processes -> SSE response
    with RUN_STARTED and RUN_FINISHED events.
    """
    response = await async_client.post(
        "/api/ag-ui",
        json=SAMPLE_AGUI_REQUEST,
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    body = response.text
    assert "RUN_STARTED" in body
    assert "RUN_FINISHED" in body
    assert "Hello from echo agent!" in body


@pytest.mark.asyncio
async def test_auth_blocks_agui_endpoint(
    async_client: httpx.AsyncClient,
) -> None:
    """Unauthenticated POST to /api/ag-ui returns 401, agent is NOT invoked."""
    response = await async_client.post(
        "/api/ag-ui",
        json=SAMPLE_AGUI_REQUEST,
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}

    # The response body should NOT contain any AG-UI events
    assert "RUN_STARTED" not in response.text
    assert "RUN_FINISHED" not in response.text


@pytest.mark.asyncio
async def test_health_bypasses_auth(
    async_client: httpx.AsyncClient,
) -> None:
    """GET /health without auth returns 200 with status ok."""
    response = await async_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
