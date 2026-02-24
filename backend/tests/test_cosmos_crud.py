"""Tests for Cosmos DB CRUD tool operations.

All tests use a mocked CosmosManager -- no real Azure calls are made.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from second_brain.db.cosmos import CosmosManager
from second_brain.tools.cosmos_crud import CosmosCrudTools


@pytest.fixture
def crud_tools(mock_cosmos_manager: CosmosManager) -> CosmosCrudTools:
    """Create CosmosCrudTools with a mocked CosmosManager."""
    return CosmosCrudTools(mock_cosmos_manager)


@pytest.mark.asyncio
async def test_create_document_inbox(
    crud_tools: CosmosCrudTools,
    mock_cosmos_manager: CosmosManager,
) -> None:
    """create_document should create a document with correct schema fields."""
    container = mock_cosmos_manager.containers["Inbox"]
    container.create_item = AsyncMock(
        return_value={"id": "test-id-123", "userId": "will"}
    )

    result = await crud_tools.create_document(
        container_name="Inbox",
        raw_text="Buy groceries",
    )

    assert "test-id-123" in result
    assert "Inbox" in result
    container.create_item.assert_awaited_once()

    # Verify the document body has the expected base fields
    call_kwargs = container.create_item.call_args
    body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
    assert body["userId"] == "will"
    assert body["rawText"] == "Buy groceries"
    assert "id" in body
    assert "createdAt" in body
    assert "updatedAt" in body
    assert "source" in body  # InboxDocument-specific field


@pytest.mark.asyncio
async def test_create_document_uses_correct_model_per_container(
    crud_tools: CosmosCrudTools,
    mock_cosmos_manager: CosmosManager,
) -> None:
    """create_document should use the right Pydantic model for each container."""
    # Test People container (requires 'name' field)
    container = mock_cosmos_manager.containers["People"]
    container.create_item = AsyncMock(
        return_value={"id": "people-id", "userId": "will"}
    )

    result = await crud_tools.create_document(
        container_name="People",
        raw_text="Met John at conference",
        title="John Smith",
    )

    assert "people-id" in result
    body = container.create_item.call_args.kwargs.get(
        "body"
    ) or container.create_item.call_args[1].get("body")
    assert body["name"] == "John Smith"
    assert "birthday" in body  # PeopleDocument field exists (None)

    # Test Projects container (requires 'title' field)
    container = mock_cosmos_manager.containers["Projects"]
    container.create_item = AsyncMock(return_value={"id": "proj-id", "userId": "will"})

    result = await crud_tools.create_document(
        container_name="Projects",
        raw_text="Build second brain app",
        title="Second Brain",
    )

    body = container.create_item.call_args.kwargs.get(
        "body"
    ) or container.create_item.call_args[1].get("body")
    assert body["title"] == "Second Brain"
    assert body["status"] == "active"  # ProjectsDocument default


@pytest.mark.asyncio
async def test_read_document_uses_correct_partition_key(
    crud_tools: CosmosCrudTools,
    mock_cosmos_manager: CosmosManager,
) -> None:
    """read_document should read from the correct container with partition key."""
    container = mock_cosmos_manager.containers["Ideas"]
    container.read_item = AsyncMock(
        return_value={
            "id": "idea-123",
            "userId": "will",
            "rawText": "AI-powered garden",
            "title": "Smart Garden",
        }
    )

    result = await crud_tools.read_document(
        container_name="Ideas",
        document_id="idea-123",
    )

    container.read_item.assert_awaited_once_with(item="idea-123", partition_key="will")
    parsed = json.loads(result)
    assert parsed["id"] == "idea-123"
    assert parsed["title"] == "Smart Garden"


@pytest.mark.asyncio
async def test_list_documents_returns_json_string(
    crud_tools: CosmosCrudTools,
    mock_cosmos_manager: CosmosManager,
) -> None:
    """list_documents should return a serialized JSON string."""
    items = [
        {"id": "doc-1", "userId": "will", "rawText": "Item 1"},
        {"id": "doc-2", "userId": "will", "rawText": "Item 2"},
    ]

    # Create an async iterator from the items list
    async def mock_query_items(**kwargs):
        for item in items:
            yield item

    container = mock_cosmos_manager.containers["Admin"]
    container.query_items = MagicMock(
        return_value=mock_query_items(query="", parameters=[], partition_key="will")
    )

    result = await crud_tools.list_documents(
        container_name="Admin",
        max_items=10,
    )

    parsed = json.loads(result)
    assert len(parsed) == 2
    assert parsed[0]["id"] == "doc-1"
    assert parsed[1]["id"] == "doc-2"


@pytest.mark.asyncio
async def test_create_document_invalid_container(
    crud_tools: CosmosCrudTools,
) -> None:
    """create_document with invalid container returns error message, not exception."""
    result = await crud_tools.create_document(
        container_name="InvalidBucket",
        raw_text="Some text",
    )

    assert "Error" in result
    assert "InvalidBucket" in result


@pytest.mark.asyncio
async def test_read_document_invalid_container(
    crud_tools: CosmosCrudTools,
) -> None:
    """read_document with invalid container returns error message."""
    result = await crud_tools.read_document(
        container_name="NonExistent",
        document_id="some-id",
    )

    assert "Error" in result
    assert "NonExistent" in result


@pytest.mark.asyncio
async def test_list_documents_invalid_container(
    crud_tools: CosmosCrudTools,
) -> None:
    """list_documents with invalid container returns error message."""
    result = await crud_tools.list_documents(
        container_name="BadContainer",
    )

    assert "Error" in result
    assert "BadContainer" in result
