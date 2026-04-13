"""Tests for errands API: GET, DELETE, POST route, and admin notifications.

Validates dynamic destination queries, HITL routing with auto-rule-save,
admin notification delivery, and Admin Agent processing trigger.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import FastAPI

from second_brain.api.errands import router as errands_router
from second_brain.auth import APIKeyMiddleware

TEST_API_KEY = "test-api-key-12345"

# Sample destination documents from the Destinations container
SAMPLE_DESTINATIONS = [
    {
        "id": "d1",
        "userId": "will",
        "slug": "jewel",
        "displayName": "Jewel-Osco",
        "type": "physical",
    },
    {
        "id": "d2",
        "userId": "will",
        "slug": "cvs",
        "displayName": "CVS",
        "type": "physical",
    },
    {
        "id": "d3",
        "userId": "will",
        "slug": "pet_store",
        "displayName": "PetSmart",
        "type": "physical",
    },
    {
        "id": "d4",
        "userId": "will",
        "slug": "other",
        "displayName": "Other",
        "type": "physical",
    },
]

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


def _setup_destinations(
    mock_cosmos_manager: MagicMock,
    destinations: list[dict] | None = None,
) -> None:
    """Configure Destinations container mock to return destination documents."""
    if destinations is None:
        destinations = SAMPLE_DESTINATIONS
    dest_container = mock_cosmos_manager.get_container("Destinations")
    dest_container.query_items = MagicMock(
        return_value=_make_async_iterator(destinations)()
    )


def _setup_destination_items(
    mock_cosmos_manager: MagicMock,
    destination_items: dict[str, list[dict]],
) -> None:
    """Configure Errands container mock to return items per destination."""
    container = mock_cosmos_manager.get_container("Errands")

    def query_items_side_effect(*, query: str, partition_key: str):
        items = destination_items.get(partition_key, [])
        return _make_async_iterator(items)(query=query, partition_key=partition_key)

    container.query_items = MagicMock(side_effect=query_items_side_effect)


def _setup_inbox_notifications(
    mock_cosmos_manager: MagicMock,
    notifications: list[dict] | None = None,
) -> None:
    """Configure Inbox container mock for notification queries.

    The Inbox container query_items is called for both admin processing
    queries and notification queries. This sets up a side_effect that
    returns the right data based on query content.
    """
    if notifications is None:
        notifications = []
    inbox_container = mock_cosmos_manager.get_container("Inbox")

    def inbox_query_side_effect(**kwargs):
        query = kwargs.get("query", "")
        if "adminProcessingStatus = 'completed'" in query:
            return _make_async_iterator(notifications)(**kwargs)
        # Default: no unprocessed items
        return _make_async_iterator([])(**kwargs)

    inbox_container.query_items = MagicMock(side_effect=inbox_query_side_effect)


# ---------------------------------------------------------------------------
# GET /api/errands
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_errands_returns_grouped_items(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET returns items grouped by destination with display names."""
    _setup_destinations(
        mock_cosmos_manager,
        [
            SAMPLE_DESTINATIONS[0],  # jewel
            SAMPLE_DESTINATIONS[1],  # cvs
        ],
    )
    _setup_destination_items(
        mock_cosmos_manager,
        {
            "jewel": JEWEL_ITEMS,
            "cvs": CVS_ITEMS,
        },
    )
    _setup_inbox_notifications(mock_cosmos_manager)

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
    _setup_destinations(
        mock_cosmos_manager,
        [
            SAMPLE_DESTINATIONS[0],
            SAMPLE_DESTINATIONS[1],
        ],
    )
    _setup_destination_items(mock_cosmos_manager, {})
    _setup_inbox_notifications(mock_cosmos_manager)

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
    _setup_destinations(mock_cosmos_manager)
    _setup_destination_items(
        mock_cosmos_manager,
        {
            "jewel": JEWEL_ITEMS,
            # cvs, pet_store, other have no items
        },
    )
    _setup_inbox_notifications(mock_cosmos_manager)

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


@pytest.mark.asyncio
async def test_get_errands_includes_destination_type(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET response includes type field on each DestinationSection."""
    online_dest = {
        "id": "d5",
        "userId": "will",
        "slug": "amazon",
        "displayName": "Amazon",
        "type": "online",
    }
    _setup_destinations(
        mock_cosmos_manager,
        [
            SAMPLE_DESTINATIONS[0],  # jewel (physical)
            online_dest,
        ],
    )
    _setup_destination_items(
        mock_cosmos_manager,
        {
            "jewel": JEWEL_ITEMS,
            "amazon": [{"id": "a1", "name": "USB cable", "destination": "amazon"}],
        },
    )
    _setup_inbox_notifications(mock_cosmos_manager)

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/errands",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()

    types_by_dest = {s["destination"]: s["type"] for s in data["destinations"]}
    assert types_by_dest["jewel"] == "physical"
    assert types_by_dest["amazon"] == "online"


@pytest.mark.asyncio
async def test_get_errands_includes_unrouted_section(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET returns unrouted items as a special 'Needs Routing' section."""
    _setup_destinations(mock_cosmos_manager, [SAMPLE_DESTINATIONS[0]])
    unrouted_items = [
        {
            "id": "u1",
            "name": "mystery item",
            "destination": "unrouted",
            "needsRouting": True,
        },
    ]
    _setup_destination_items(
        mock_cosmos_manager,
        {
            "jewel": JEWEL_ITEMS,
            "unrouted": unrouted_items,
        },
    )
    _setup_inbox_notifications(mock_cosmos_manager)

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/errands",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["totalCount"] == 4  # 3 jewel + 1 unrouted

    # Find the unrouted section
    unrouted_section = None
    for s in data["destinations"]:
        if s["destination"] == "unrouted":
            unrouted_section = s
            break

    assert unrouted_section is not None
    assert unrouted_section["displayName"] == "Needs Routing"
    assert unrouted_section["type"] == "unrouted"
    assert unrouted_section["count"] == 1
    assert unrouted_section["items"][0]["needsRouting"] is True


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
        side_effect=CosmosResourceNotFoundError(status_code=404, message="Not found")
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
async def test_delete_errand_item_any_destination(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """DELETE accepts any destination string (no hardcoded validation)."""
    container = mock_cosmos_manager.get_container("Errands")
    container.delete_item = AsyncMock()

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/errands/x1?destination=random_new_store",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 204
    container.delete_item.assert_called_once_with(
        item="x1", partition_key="random_new_store"
    )


# ---------------------------------------------------------------------------
# POST /api/errands/{item_id}/route
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_errand_item_success(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /route moves item from unrouted to destination and creates rule."""
    errands_container = mock_cosmos_manager.get_container("Errands")
    errands_container.read_item = AsyncMock(
        return_value={"id": "u1", "name": "chicken thighs", "destination": "unrouted"}
    )
    errands_container.create_item = AsyncMock()
    errands_container.delete_item = AsyncMock()

    # Set up Destinations to validate the slug
    dest_container = mock_cosmos_manager.get_container("Destinations")
    dest_container.query_items = MagicMock(
        return_value=_make_async_iterator([{"slug": "jewel"}])()
    )

    rules_container = mock_cosmos_manager.get_container("AffinityRules")
    rules_container.create_item = AsyncMock()

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/errands/u1/route",
            json={"destinationSlug": "jewel", "saveRule": True},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "chicken thighs" in data["message"]
    assert data["ruleSaved"] is True

    # Verify item was read from unrouted
    errands_container.read_item.assert_called_once_with(
        item="u1", partition_key="unrouted"
    )
    # Verify item was created in target destination
    errands_container.create_item.assert_called_once()
    created_body = errands_container.create_item.call_args.kwargs["body"]
    assert created_body["destination"] == "jewel"
    assert created_body["name"] == "chicken thighs"
    # Verify old unrouted item was deleted
    errands_container.delete_item.assert_called_once_with(
        item="u1", partition_key="unrouted"
    )
    # Verify affinity rule was created
    rules_container.create_item.assert_called_once()
    rule_body = rules_container.create_item.call_args.kwargs["body"]
    assert rule_body["itemPattern"] == "chicken thighs"
    assert rule_body["destinationSlug"] == "jewel"
    assert rule_body["autoSaved"] is True


@pytest.mark.asyncio
async def test_route_errand_item_not_found(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /route returns 404 for nonexistent unrouted item."""
    errands_container = mock_cosmos_manager.get_container("Errands")
    errands_container.read_item = AsyncMock(
        side_effect=CosmosResourceNotFoundError(status_code=404, message="Not found")
    )

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/errands/nonexistent/route",
            json={"destinationSlug": "jewel"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_route_errand_item_without_rule_save(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /route with saveRule=false moves item but does not create rule."""
    errands_container = mock_cosmos_manager.get_container("Errands")
    errands_container.read_item = AsyncMock(
        return_value={"id": "u2", "name": "specialty item", "destination": "unrouted"}
    )
    errands_container.create_item = AsyncMock()
    errands_container.delete_item = AsyncMock()

    # Set up Destinations to validate the slug
    dest_container = mock_cosmos_manager.get_container("Destinations")
    dest_container.query_items = MagicMock(
        return_value=_make_async_iterator([{"slug": "cvs"}])()
    )

    rules_container = mock_cosmos_manager.get_container("AffinityRules")
    rules_container.create_item = AsyncMock()

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/errands/u2/route",
            json={"destinationSlug": "cvs", "saveRule": False},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["ruleSaved"] is False

    # Verify item was moved
    errands_container.create_item.assert_called_once()
    errands_container.delete_item.assert_called_once()

    # Verify NO rule was created
    rules_container.create_item.assert_not_called()


@pytest.mark.asyncio
async def test_route_errand_item_invalid_destination(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /route returns 400 for unknown destination slug."""
    errands_container = mock_cosmos_manager.get_container("Errands")
    errands_container.read_item = AsyncMock(
        return_value={"id": "u3", "name": "some item", "destination": "unrouted"}
    )

    # No matching destination
    dest_container = mock_cosmos_manager.get_container("Destinations")
    dest_container.query_items = MagicMock(return_value=_make_async_iterator([])())

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/errands/u3/route",
            json={"destinationSlug": "nonexistent_store"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 400
    assert "Unknown destination" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Admin notifications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_errands_returns_admin_notifications(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET returns adminNotifications for completed agent responses."""
    _setup_destinations(mock_cosmos_manager, [SAMPLE_DESTINATIONS[0]])
    _setup_destination_items(mock_cosmos_manager, {"jewel": JEWEL_ITEMS})
    _setup_inbox_notifications(
        mock_cosmos_manager,
        [
            {
                "id": "notif-1",
                "adminAgentResponse": "I created a rule: chicken goes to jewel",
            },
        ],
    )

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/errands",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()

    assert len(data["adminNotifications"]) == 1
    notif = data["adminNotifications"][0]
    assert notif["inboxItemId"] == "notif-1"
    assert "chicken goes to jewel" in notif["message"]


@pytest.mark.asyncio
async def test_dismiss_admin_notification(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /dismiss deletes the inbox item for the notification."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.delete_item = AsyncMock()

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/errands/notifications/notif-1/dismiss",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 204
    inbox_container.delete_item.assert_called_once_with(
        item="notif-1", partition_key="will"
    )


@pytest.mark.asyncio
async def test_dismiss_admin_notification_not_found(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /dismiss returns 404 when notification inbox item is missing."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.delete_item = AsyncMock(
        side_effect=CosmosResourceNotFoundError(status_code=404, message="Not found")
    )

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/errands/notifications/nonexistent/dismiss",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Admin Agent processing trigger
# ---------------------------------------------------------------------------


def _close_coroutine(coro):
    """Close the coroutine to prevent RuntimeWarning."""
    coro.close()
    mock_task = MagicMock()
    mock_task.add_done_callback = MagicMock()
    return mock_task


def _make_inbox_async_iterator(items: list[dict]):
    """Async iterator for Inbox container query_items mock."""

    async def _iter(*args, **kwargs):
        for item in items:
            yield item

    return _iter


def _setup_trigger_mocks(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
    inbox_items: list[dict],
) -> None:
    """Set up all mocks needed for admin processing trigger tests."""
    _setup_destinations(mock_cosmos_manager, [SAMPLE_DESTINATIONS[0]])
    _setup_destination_items(mock_cosmos_manager, {"jewel": JEWEL_ITEMS})

    # Inbox query: return unprocessed items for trigger, empty for notifications
    inbox_container = mock_cosmos_manager.get_container("Inbox")

    def inbox_query_side_effect(**kwargs):
        query = kwargs.get("query", "")
        if "adminProcessingStatus = 'completed'" in query:
            return _make_inbox_async_iterator([])(**kwargs)
        # Admin trigger query
        return _make_inbox_async_iterator(inbox_items)(**kwargs)

    inbox_container.query_items = MagicMock(side_effect=inbox_query_side_effect)


@pytest.mark.asyncio
async def test_get_errands_triggers_processing(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET triggers background processing for unprocessed Admin items."""
    _setup_trigger_mocks(
        errands_app,
        mock_cosmos_manager,
        [{"id": "inbox-1", "rawText": "need milk"}],
    )

    # Set up admin client on app state
    errands_app.state.admin_client = AsyncMock()
    errands_app.state.admin_agent_tools = [AsyncMock()]
    errands_app.state.background_tasks = set()

    # Patch asyncio.create_task to close the coroutine (prevents RuntimeWarning)
    with patch(
        "second_brain.api.errands.asyncio.create_task",
        side_effect=_close_coroutine,
    ) as mock_create_task:
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
    assert data["processingCount"] == 1
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_get_errands_no_processing_when_query_returns_empty(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET does not trigger processing when no unprocessed items are found.

    When the inbox query returns an empty list, no background tasks should
    be created. The query now includes pending and failed items for retry,
    so this test verifies the "nothing to process" baseline.
    """
    _setup_trigger_mocks(errands_app, mock_cosmos_manager, [])

    # Set up admin client on app state
    errands_app.state.admin_client = AsyncMock()
    errands_app.state.admin_agent_tools = [AsyncMock()]
    errands_app.state.background_tasks = set()

    # Patch asyncio.create_task to verify it is NOT called
    with patch(
        "second_brain.api.errands.asyncio.create_task",
        side_effect=_close_coroutine,
    ) as mock_create_task:
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
    mock_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_get_errands_no_trigger_when_no_admin_client(
    errands_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """GET returns processingCount=0 when admin_client not configured."""
    _setup_trigger_mocks(
        errands_app,
        mock_cosmos_manager,
        [{"id": "inbox-1", "rawText": "need milk"}],
    )

    # Explicitly ensure admin_client is NOT set
    if hasattr(errands_app.state, "admin_client"):
        delattr(errands_app.state, "admin_client")

    transport = httpx.ASGITransport(app=errands_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/errands",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["processingCount"] == 0
