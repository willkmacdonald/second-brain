"""Tests for GET /api/errands and DELETE /api/errands/{id}.

Validates grouped response, empty state, destination exclusion, successful delete,
not-found delete, invalid destination validation, and Admin Agent processing trigger.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import FastAPI

from second_brain.api.errands import router as errands_router
from second_brain.auth import APIKeyMiddleware

TEST_API_KEY = "test-api-key-12345"

# Sample items for different destinations
JEWEL_ITEMS = [
    {"id": "j1", "name": "2 lbs ground beef", "destination": "jewel"},
    {"id": "j2", "name": "whole milk", "destination": "jewel"},
    {"id": "j3", "name": "sourdough bread", "destination": "jewel"},
]

CVS_ITEMS = [
    {"id": "c1", "name": "toothpaste", "destination": "cvs"},
]


@pytest.fixture
def errands_app(mock_cosmos_manager: MagicMock) -> FastAPI:
    """Create a FastAPI app with the errands router and mock Cosmos."""
    app = FastAPI()
    app.include_router(errands_router)
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


def _setup_destination_items(
    mock_cosmos_manager: MagicMock,
    destination_items: dict[str, list[dict]],
) -> None:
    """Configure mock container to return items per destination partition key."""
    container = mock_cosmos_manager.get_container("Errands")

    def query_items_side_effect(*, query: str, partition_key: str):
        items = destination_items.get(partition_key, [])
        return _make_async_iterator(items)(query=query, partition_key=partition_key)

    container.query_items = MagicMock(side_effect=query_items_side_effect)


# ---------------------------------------------------------------------------
# GET /api/errands
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_errands_returns_grouped_items(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET returns items grouped by destination with display names, sorted by count desc."""
    _setup_destination_items(mock_cosmos_manager, {
        "jewel": JEWEL_ITEMS,
        "cvs": CVS_ITEMS,
    })

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/errands",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["totalCount"] == 4
    assert len(data["destinations"]) == 2

    # First destination should be jewel (3 items > 1 item)
    jewel_section = data["destinations"][0]
    assert jewel_section["destination"] == "jewel"
    assert jewel_section["displayName"] == "Jewel-Osco"
    assert jewel_section["count"] == 3
    assert len(jewel_section["items"]) == 3

    # Second destination should be cvs
    cvs_section = data["destinations"][1]
    assert cvs_section["destination"] == "cvs"
    assert cvs_section["displayName"] == "CVS"
    assert cvs_section["count"] == 1
    assert len(cvs_section["items"]) == 1


@pytest.mark.asyncio
async def test_get_errands_empty(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET returns empty destinations list and zero totalCount when no items exist."""
    _setup_destination_items(mock_cosmos_manager, {})

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/errands",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["totalCount"] == 0
    assert data["destinations"] == []


@pytest.mark.asyncio
async def test_get_errands_excludes_empty_destinations(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET only returns destination sections that have items."""
    _setup_destination_items(mock_cosmos_manager, {
        "jewel": JEWEL_ITEMS,
        # cvs, pet_store, other have no items
    })

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/errands",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()

    assert len(data["destinations"]) == 1
    assert data["destinations"][0]["destination"] == "jewel"
    # Verify other destinations are NOT present
    destination_names = [s["destination"] for s in data["destinations"]]
    assert "cvs" not in destination_names
    assert "pet_store" not in destination_names
    assert "other" not in destination_names


# ---------------------------------------------------------------------------
# DELETE /api/errands/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_errand_item_success(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """DELETE returns 204 and calls delete_item with correct partition key."""
    container = mock_cosmos_manager.get_container("Errands")
    container.delete_item = AsyncMock()

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/errands/j1?destination=jewel",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 204
    container.delete_item.assert_called_once_with(item="j1", partition_key="jewel")


@pytest.mark.asyncio
async def test_delete_errand_item_not_found(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """DELETE returns 404 when item does not exist."""
    container = mock_cosmos_manager.get_container("Errands")
    container.delete_item = AsyncMock(
        side_effect=CosmosResourceNotFoundError(
            status_code=404, message="Not found"
        )
    )

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/errands/nonexistent?destination=jewel",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_errand_item_unknown_destination(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """DELETE returns 400 for unknown destination name."""
    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/errands/x1?destination=unknown_destination",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 400
    assert "Unknown destination" in response.json()["detail"]


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
async def test_get_errands_triggers_processing(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET triggers background processing for unprocessed Admin items."""
    _setup_destination_items(mock_cosmos_manager, {"jewel": JEWEL_ITEMS})

    # Set up Inbox container to return 1 unprocessed Admin item
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.query_items = MagicMock(
        side_effect=lambda **kwargs: _make_inbox_async_iterator(
            [{"id": "inbox-1", "rawText": "need milk"}]
        )(**kwargs)
    )

    # Set up admin client on app state
    errands_app.state.admin_client = AsyncMock()
    errands_app.state.admin_agent_tools = [AsyncMock()]
    errands_app.state.background_tasks = set()

    # Patch asyncio.create_task to capture the coroutine
    with patch(
        "second_brain.api.errands.asyncio.create_task"
    ) as mock_create_task:
        mock_create_task.return_value = MagicMock()
        mock_create_task.return_value.add_done_callback = (
            MagicMock()
        )

        transport = httpx.ASGITransport(app=errands_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/errands",
                headers={
                    "Authorization": f"Bearer {TEST_API_KEY}"
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["processingCount"] == 1
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_get_errands_skips_pending_items(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET does NOT re-process items with adminProcessingStatus='pending'.

    Items already in 'pending' or 'failed' state should not be re-triggered
    automatically — this prevents infinite processing loops when the Agent
    writes items but fails to delete the inbox document.
    """
    _setup_destination_items(mock_cosmos_manager, {"jewel": JEWEL_ITEMS})

    # Set up Inbox container to return 0 items (pending items excluded by query)
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.query_items = MagicMock(
        side_effect=lambda **kwargs: _make_inbox_async_iterator(
            []
        )(**kwargs)
    )

    # Set up admin client on app state
    errands_app.state.admin_client = AsyncMock()
    errands_app.state.admin_agent_tools = [AsyncMock()]
    errands_app.state.background_tasks = set()

    # Patch asyncio.create_task to verify it is NOT called
    with patch(
        "second_brain.api.errands.asyncio.create_task"
    ) as mock_create_task:
        mock_create_task.return_value = MagicMock()
        mock_create_task.return_value.add_done_callback = (
            MagicMock()
        )

        transport = httpx.ASGITransport(app=errands_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/errands",
                headers={
                    "Authorization": f"Bearer {TEST_API_KEY}"
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["processingCount"] == 0
    mock_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_get_errands_no_trigger_when_no_admin_client(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET returns processingCount=0 when admin_client not configured."""
    _setup_destination_items(mock_cosmos_manager, {"jewel": JEWEL_ITEMS})

    # Set up Inbox with unprocessed items but NO admin_client
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.query_items = MagicMock(
        side_effect=lambda **kwargs: _make_inbox_async_iterator(
            [{"id": "inbox-1", "rawText": "need milk"}]
        )(**kwargs)
    )

    # Explicitly ensure admin_client is NOT set
    if hasattr(errands_app.state, "admin_client"):
        delattr(errands_app.state, "admin_client")

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/errands",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["processingCount"] == 0
