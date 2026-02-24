"""Tests for DELETE /api/inbox/{item_id} endpoint.

Validates cascade deletion (inbox + bucket), 404 handling,
and missing Cosmos DB error handling.
"""

from unittest.mock import MagicMock

import httpx
import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import FastAPI

from second_brain.api.inbox import router as inbox_router
from second_brain.auth import APIKeyMiddleware

TEST_API_KEY = "test-api-key-12345"

SAMPLE_INBOX_ITEM = {
    "id": "inbox-123",
    "userId": "will",
    "rawText": "Meet Sarah tomorrow at 3pm",
    "title": "Meeting with Sarah",
    "status": "classified",
    "createdAt": "2026-02-23T10:00:00Z",
    "filedRecordId": "bucket-456",
    "classificationMeta": {
        "bucket": "People",
        "confidence": 0.85,
        "allScores": {"People": 0.85, "Projects": 0.10, "Ideas": 0.03, "Admin": 0.02},
        "classifiedBy": "Classifier",
        "agentChain": ["Orchestrator", "Classifier"],
    },
}

SAMPLE_INBOX_ITEM_NO_FILED = {
    "id": "inbox-789",
    "userId": "will",
    "rawText": "asdfghjkl",
    "status": "unclassified",
    "createdAt": "2026-02-23T10:00:00Z",
    "filedRecordId": None,
    "classificationMeta": None,
}


@pytest.fixture
def inbox_app(mock_cosmos_manager: MagicMock) -> FastAPI:
    """Create a FastAPI app with the inbox router and mock Cosmos."""
    app = FastAPI()
    app.include_router(inbox_router)
    app.state.api_key = TEST_API_KEY
    app.state.cosmos_manager = mock_cosmos_manager
    app.add_middleware(APIKeyMiddleware)
    return app


@pytest.mark.asyncio
async def test_delete_inbox_item_with_cascade(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """DELETE removes both inbox and bucket documents (cascade)."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.return_value = SAMPLE_INBOX_ITEM

    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/inbox/inbox-123",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 204

    # Inbox item read to get cascade info
    inbox_container.read_item.assert_called_once_with(
        item="inbox-123", partition_key="will"
    )

    # Bucket cascade delete
    people_container = mock_cosmos_manager.get_container("People")
    people_container.delete_item.assert_called_once_with(
        item="bucket-456", partition_key="will"
    )

    # Inbox delete
    inbox_container.delete_item.assert_called_once_with(
        item="inbox-123", partition_key="will"
    )


@pytest.mark.asyncio
async def test_delete_inbox_item_no_filed_record(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """DELETE on unclassified item (no filedRecordId) skips cascade."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.return_value = SAMPLE_INBOX_ITEM_NO_FILED

    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/inbox/inbox-789",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 204

    # No cascade delete on any bucket container
    for name in ("People", "Projects", "Ideas", "Admin"):
        container = mock_cosmos_manager.get_container(name)
        container.delete_item.assert_not_called()

    # Inbox item deleted
    inbox_container.delete_item.assert_called_once_with(
        item="inbox-789", partition_key="will"
    )


@pytest.mark.asyncio
async def test_delete_inbox_item_not_found(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """DELETE on non-existent item returns 404."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.side_effect = CosmosResourceNotFoundError(
        status_code=404, message="Not found"
    )

    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/inbox/nonexistent",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    # No deletes attempted
    inbox_container.delete_item.assert_not_called()


@pytest.mark.asyncio
async def test_delete_inbox_item_cascade_already_missing(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """DELETE succeeds even when bucket document is already gone."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.return_value = SAMPLE_INBOX_ITEM

    people_container = mock_cosmos_manager.get_container("People")
    people_container.delete_item.side_effect = CosmosResourceNotFoundError(
        status_code=404, message="Not found"
    )

    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/inbox/inbox-123",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    # Still succeeds -- cascade failure is non-fatal
    assert response.status_code == 204

    # Inbox item still deleted
    inbox_container.delete_item.assert_called_once_with(
        item="inbox-123", partition_key="will"
    )


@pytest.mark.asyncio
async def test_delete_inbox_item_requires_auth(
    inbox_app: FastAPI,
) -> None:
    """DELETE without auth returns 401."""
    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/inbox/inbox-123")

    assert response.status_code == 401
