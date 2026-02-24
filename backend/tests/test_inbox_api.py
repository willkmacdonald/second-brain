"""Tests for PATCH /api/inbox/{item_id}/recategorize endpoint.

Validates cross-container bucket move: success, same-bucket no-op,
invalid bucket (400), not found (404), and non-fatal old-doc delete failure.
"""

from unittest.mock import MagicMock

import httpx
import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import FastAPI

from second_brain.api.inbox import router as inbox_router
from second_brain.auth import APIKeyMiddleware

TEST_API_KEY = "test-api-key-12345"

SAMPLE_CLASSIFIED_ITEM = {
    "id": "inbox-100",
    "userId": "will",
    "rawText": "Build the new dashboard feature",
    "title": "Dashboard feature",
    "status": "classified",
    "createdAt": "2026-02-23T10:00:00Z",
    "updatedAt": "2026-02-23T10:00:00Z",
    "filedRecordId": "old-bucket-doc-id",
    "classificationMeta": {
        "bucket": "Ideas",
        "confidence": 0.72,
        "allScores": {"People": 0.05, "Projects": 0.20, "Ideas": 0.72, "Admin": 0.03},
        "classifiedBy": "Classifier",
        "agentChain": ["Orchestrator", "Classifier"],
        "classifiedAt": "2026-02-23T10:00:00Z",
    },
}

SAMPLE_PEOPLE_ITEM = {
    "id": "inbox-200",
    "userId": "will",
    "rawText": "Met Sarah at the conference",
    "title": "Sarah from conference",
    "status": "classified",
    "createdAt": "2026-02-23T11:00:00Z",
    "updatedAt": "2026-02-23T11:00:00Z",
    "filedRecordId": "people-doc-id",
    "classificationMeta": {
        "bucket": "People",
        "confidence": 0.90,
        "allScores": {"People": 0.90, "Projects": 0.05, "Ideas": 0.03, "Admin": 0.02},
        "classifiedBy": "Classifier",
        "agentChain": ["Orchestrator", "Classifier"],
        "classifiedAt": "2026-02-23T11:00:00Z",
    },
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
async def test_recategorize_success(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """PATCH moves item from Ideas to Projects: create, update, delete."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.return_value = {**SAMPLE_CLASSIFIED_ITEM}

    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/api/inbox/inbox-100/recategorize",
            json={"new_bucket": "Projects"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["classificationMeta"]["bucket"] == "Projects"
    assert data["classificationMeta"]["classifiedBy"] == "User"
    assert data["status"] == "classified"
    assert data["filedRecordId"] != "old-bucket-doc-id"  # New bucket doc ID

    # Step 1: New bucket container got create_item
    projects_container = mock_cosmos_manager.get_container("Projects")
    projects_container.create_item.assert_called_once()
    created_doc = projects_container.create_item.call_args[1]["body"]
    assert created_doc["rawText"] == "Build the new dashboard feature"
    assert created_doc["title"] == "Dashboard feature"
    assert created_doc["classificationMeta"]["bucket"] == "Projects"
    assert created_doc["inboxRecordId"] == "inbox-100"

    # Step 2: Inbox container got upsert_item
    inbox_container.upsert_item.assert_called_once()

    # Step 3: Old bucket container got delete_item
    ideas_container = mock_cosmos_manager.get_container("Ideas")
    ideas_container.delete_item.assert_called_once_with(
        item="old-bucket-doc-id", partition_key="will"
    )


@pytest.mark.asyncio
async def test_recategorize_same_bucket_noop(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """PATCH with same bucket returns item unchanged, no DB writes."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.return_value = {**SAMPLE_PEOPLE_ITEM}

    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/api/inbox/inbox-200/recategorize",
            json={"new_bucket": "People"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200

    # No writes to any container
    for name in ("People", "Projects", "Ideas", "Admin"):
        container = mock_cosmos_manager.get_container(name)
        container.create_item.assert_not_called()
        container.delete_item.assert_not_called()
    inbox_container.upsert_item.assert_not_called()


@pytest.mark.asyncio
async def test_recategorize_invalid_bucket(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """PATCH with unknown bucket returns 400."""
    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/api/inbox/inbox-100/recategorize",
            json={"new_bucket": "Unknown"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 400
    assert "Invalid bucket" in response.json()["detail"]


@pytest.mark.asyncio
async def test_recategorize_not_found(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """PATCH on non-existent item returns 404."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.side_effect = CosmosResourceNotFoundError(
        status_code=404, message="Not found"
    )

    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/api/inbox/nonexistent/recategorize",
            json={"new_bucket": "Projects"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_recategorize_old_delete_fails_nonfatal(
    inbox_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """PATCH succeeds even when old bucket doc delete fails."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.return_value = {**SAMPLE_CLASSIFIED_ITEM}

    # Make old bucket delete fail
    ideas_container = mock_cosmos_manager.get_container("Ideas")
    ideas_container.delete_item.side_effect = RuntimeError("Cosmos timeout")

    transport = httpx.ASGITransport(app=inbox_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/api/inbox/inbox-100/recategorize",
            json={"new_bucket": "Projects"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    # Still succeeds -- old doc delete is non-fatal
    assert response.status_code == 200
    data = response.json()
    assert data["classificationMeta"]["bucket"] == "Projects"

    # New bucket doc was created
    projects_container = mock_cosmos_manager.get_container("Projects")
    projects_container.create_item.assert_called_once()

    # Inbox was updated
    inbox_container.upsert_item.assert_called_once()
