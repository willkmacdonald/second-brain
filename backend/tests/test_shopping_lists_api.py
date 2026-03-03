"""Tests for GET /api/shopping-lists and DELETE /api/shopping-lists/items/{id}.

Validates grouped response, empty state, store exclusion, successful delete,
not-found delete, invalid store validation, and Admin Agent processing trigger.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import FastAPI

from second_brain.api.shopping_lists import router as shopping_lists_router
from second_brain.auth import APIKeyMiddleware

TEST_API_KEY = "test-api-key-12345"

# Sample items for different stores
JEWEL_ITEMS = [
    {"id": "j1", "name": "2 lbs ground beef", "store": "jewel"},
    {"id": "j2", "name": "whole milk", "store": "jewel"},
    {"id": "j3", "name": "sourdough bread", "store": "jewel"},
]

CVS_ITEMS = [
    {"id": "c1", "name": "toothpaste", "store": "cvs"},
]


@pytest.fixture
def shopping_app(mock_cosmos_manager: MagicMock) -> FastAPI:
    """Create a FastAPI app with the shopping lists router and mock Cosmos."""
    app = FastAPI()
    app.include_router(shopping_lists_router)
    app.state.api_key = TEST_API_KEY
    app.state.cosmos_manager = mock_cosmos_manager
    app.add_middleware(APIKeyMiddleware)
    return app


def _make_async_iterator(items: list[dict]):
    """Create an async iterator from a list of dicts (mimics Cosmos query_items)."""

    async def _iter(*args, **kwargs):
        for item in items:
            yield item

    return _iter


def _setup_store_items(
    mock_cosmos_manager: MagicMock,
    store_items: dict[str, list[dict]],
) -> None:
    """Configure mock container to return items per store partition key."""
    container = mock_cosmos_manager.get_container("ShoppingLists")

    def query_items_side_effect(*, query: str, partition_key: str):
        items = store_items.get(partition_key, [])
        return _make_async_iterator(items)(query=query, partition_key=partition_key)

    container.query_items = MagicMock(side_effect=query_items_side_effect)


# ---------------------------------------------------------------------------
# GET /api/shopping-lists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_shopping_lists_returns_grouped_items(
    shopping_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET returns items grouped by store with display names, sorted by count desc."""
    _setup_store_items(mock_cosmos_manager, {
        "jewel": JEWEL_ITEMS,
        "cvs": CVS_ITEMS,
    })

    transport = httpx.ASGITransport(app=shopping_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/shopping-lists",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["totalCount"] == 4
    assert len(data["stores"]) == 2

    # First store should be jewel (3 items > 1 item)
    jewel_section = data["stores"][0]
    assert jewel_section["store"] == "jewel"
    assert jewel_section["displayName"] == "Jewel-Osco"
    assert jewel_section["count"] == 3
    assert len(jewel_section["items"]) == 3

    # Second store should be cvs
    cvs_section = data["stores"][1]
    assert cvs_section["store"] == "cvs"
    assert cvs_section["displayName"] == "CVS"
    assert cvs_section["count"] == 1
    assert len(cvs_section["items"]) == 1


@pytest.mark.asyncio
async def test_get_shopping_lists_empty(
    shopping_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET returns empty stores list and zero totalCount when no items exist."""
    _setup_store_items(mock_cosmos_manager, {})

    transport = httpx.ASGITransport(app=shopping_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/shopping-lists",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["totalCount"] == 0
    assert data["stores"] == []


@pytest.mark.asyncio
async def test_get_shopping_lists_excludes_empty_stores(
    shopping_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET only returns store sections that have items."""
    _setup_store_items(mock_cosmos_manager, {
        "jewel": JEWEL_ITEMS,
        # cvs, pet_store, other have no items
    })

    transport = httpx.ASGITransport(app=shopping_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/shopping-lists",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()

    assert len(data["stores"]) == 1
    assert data["stores"][0]["store"] == "jewel"
    # Verify other stores are NOT present
    store_names = [s["store"] for s in data["stores"]]
    assert "cvs" not in store_names
    assert "pet_store" not in store_names
    assert "other" not in store_names


# ---------------------------------------------------------------------------
# DELETE /api/shopping-lists/items/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_shopping_item_success(
    shopping_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """DELETE returns 204 and calls delete_item with correct partition key."""
    container = mock_cosmos_manager.get_container("ShoppingLists")
    container.delete_item = AsyncMock()

    transport = httpx.ASGITransport(app=shopping_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/shopping-lists/items/j1?store=jewel",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 204
    container.delete_item.assert_called_once_with(item="j1", partition_key="jewel")


@pytest.mark.asyncio
async def test_delete_shopping_item_not_found(
    shopping_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """DELETE returns 404 when item does not exist."""
    container = mock_cosmos_manager.get_container("ShoppingLists")
    container.delete_item = AsyncMock(
        side_effect=CosmosResourceNotFoundError(
            status_code=404, message="Not found"
        )
    )

    transport = httpx.ASGITransport(app=shopping_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/shopping-lists/items/nonexistent?store=jewel",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_shopping_item_unknown_store(
    shopping_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """DELETE returns 400 for unknown store name."""
    transport = httpx.ASGITransport(app=shopping_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/shopping-lists/items/x1?store=unknown_store",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 400
    assert "Unknown store" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Admin Agent processing trigger
# ---------------------------------------------------------------------------


def _make_inbox_async_iterator(items: list[dict]):
    """Async iterator for Inbox container query_items mock."""

    async def _iter(*args, **kwargs):
        for item in items:
            yield item

    return _iter


@pytest.mark.asyncio
async def test_get_shopping_lists_triggers_processing(
    shopping_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET triggers background processing for unprocessed Admin items."""
    _setup_store_items(mock_cosmos_manager, {"jewel": JEWEL_ITEMS})

    # Set up Inbox container to return 1 unprocessed Admin item
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.query_items = MagicMock(
        side_effect=lambda **kwargs: _make_inbox_async_iterator(
            [{"id": "inbox-1", "rawText": "need milk"}]
        )(**kwargs)
    )

    # Set up admin client on app state
    shopping_app.state.admin_client = AsyncMock()
    shopping_app.state.admin_agent_tools = [AsyncMock()]
    shopping_app.state.background_tasks = set()

    # Patch asyncio.create_task to capture the coroutine
    with patch(
        "second_brain.api.shopping_lists.asyncio.create_task"
    ) as mock_create_task:
        mock_create_task.return_value = MagicMock()
        mock_create_task.return_value.add_done_callback = (
            MagicMock()
        )

        transport = httpx.ASGITransport(app=shopping_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/shopping-lists",
                headers={
                    "Authorization": f"Bearer {TEST_API_KEY}"
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["processingCount"] == 1
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_get_shopping_lists_triggers_for_pending_items(
    shopping_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET triggers processing for items stuck with adminProcessingStatus='pending'.

    When delete_item fails after successful Admin Agent processing, the inbox
    item remains with adminProcessingStatus='pending'. The retry query must
    include these stuck items so they are recovered on next Status screen open.
    """
    _setup_store_items(mock_cosmos_manager, {"jewel": JEWEL_ITEMS})

    # Set up Inbox container to return 1 item stuck in 'pending' state
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.query_items = MagicMock(
        side_effect=lambda **kwargs: _make_inbox_async_iterator(
            [
                {
                    "id": "inbox-stuck",
                    "rawText": "milk and eggs",
                    "adminProcessingStatus": "pending",
                }
            ]
        )(**kwargs)
    )

    # Set up admin client on app state
    shopping_app.state.admin_client = AsyncMock()
    shopping_app.state.admin_agent_tools = [AsyncMock()]
    shopping_app.state.background_tasks = set()

    # Patch asyncio.create_task to capture the coroutine
    with patch(
        "second_brain.api.shopping_lists.asyncio.create_task"
    ) as mock_create_task:
        mock_create_task.return_value = MagicMock()
        mock_create_task.return_value.add_done_callback = (
            MagicMock()
        )

        transport = httpx.ASGITransport(app=shopping_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/shopping-lists",
                headers={
                    "Authorization": f"Bearer {TEST_API_KEY}"
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["processingCount"] == 1
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_get_shopping_lists_no_trigger_when_no_admin_client(
    shopping_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET returns processingCount=0 when admin_client not configured."""
    _setup_store_items(mock_cosmos_manager, {"jewel": JEWEL_ITEMS})

    # Set up Inbox with unprocessed items but NO admin_client
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.query_items = MagicMock(
        side_effect=lambda **kwargs: _make_inbox_async_iterator(
            [{"id": "inbox-1", "rawText": "need milk"}]
        )(**kwargs)
    )

    # Explicitly ensure admin_client is NOT set
    if hasattr(shopping_app.state, "admin_client"):
        delattr(shopping_app.state, "admin_client")

    transport = httpx.ASGITransport(app=shopping_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/shopping-lists",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["processingCount"] == 0
