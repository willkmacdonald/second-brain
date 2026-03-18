"""Unit tests for the Tasks API (GET /api/tasks, DELETE /api/tasks/{id}).

Uses the same fixture patterns as test_errands_api.py.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from second_brain.api.tasks import router as tasks_router
from second_brain.auth import APIKeyMiddleware
from second_brain.db.cosmos import CONTAINER_NAMES

TEST_API_KEY = "test-api-key-12345"


@pytest.fixture
def app_with_tasks() -> FastAPI:
    """Create a FastAPI app with Tasks router and mocked Cosmos."""
    app = FastAPI()
    app.state.api_key = TEST_API_KEY
    app.add_middleware(APIKeyMiddleware)
    app.include_router(tasks_router)

    # Mock CosmosManager
    manager = MagicMock()
    containers: dict = {}
    for name in CONTAINER_NAMES:
        container = MagicMock()
        container.create_item = AsyncMock()
        container.read_item = AsyncMock()
        container.delete_item = AsyncMock()
        container.query_items = MagicMock()
        containers[name] = container
    manager.containers = containers
    manager.get_container = MagicMock(side_effect=lambda n: containers[n])
    app.state.cosmos_manager = manager

    return app


@pytest.fixture
def tasks_client(app_with_tasks: FastAPI) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient bound to the tasks app."""
    transport = httpx.ASGITransport(app=app_with_tasks)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _mock_query_items(items: list[dict]):
    """Create an async iterator mock for query_items."""
    async def _aiter(*args, **kwargs):
        for item in items:
            yield item
    return _aiter


async def test_get_tasks_empty(
    app_with_tasks: FastAPI,
    tasks_client: httpx.AsyncClient,
) -> None:
    """GET /api/tasks with no items returns empty list."""
    container = app_with_tasks.state.cosmos_manager.get_container("Tasks")
    container.query_items = MagicMock(return_value=_mock_query_items([])())

    res = await tasks_client.get(
        "/api/tasks",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["tasks"] == []
    assert data["totalCount"] == 0


async def test_get_tasks_with_items(
    app_with_tasks: FastAPI,
    tasks_client: httpx.AsyncClient,
) -> None:
    """GET /api/tasks returns items with correct structure."""
    container = app_with_tasks.state.cosmos_manager.get_container("Tasks")
    container.query_items = MagicMock(
        return_value=_mock_query_items([
            {"id": "t1", "name": "Book eye appointments", "createdAt": "2026-03-17T10:00:00Z"},
            {"id": "t2", "name": "Fill out expenses", "createdAt": "2026-03-17T09:00:00Z"},
        ])()
    )

    res = await tasks_client.get(
        "/api/tasks",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["totalCount"] == 2
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["name"] == "Book eye appointments"
    assert data["tasks"][1]["name"] == "Fill out expenses"


async def test_delete_task_success(
    app_with_tasks: FastAPI,
    tasks_client: httpx.AsyncClient,
) -> None:
    """DELETE /api/tasks/{id} returns 204 on success."""
    res = await tasks_client.delete(
        "/api/tasks/t1",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )
    assert res.status_code == 204

    container = app_with_tasks.state.cosmos_manager.get_container("Tasks")
    container.delete_item.assert_called_once_with(
        item="t1", partition_key="will"
    )


async def test_delete_task_not_found(
    app_with_tasks: FastAPI,
    tasks_client: httpx.AsyncClient,
) -> None:
    """DELETE /api/tasks/{id} returns 404 when item doesn't exist."""
    from azure.cosmos.exceptions import CosmosResourceNotFoundError

    container = app_with_tasks.state.cosmos_manager.get_container("Tasks")
    container.delete_item = AsyncMock(
        side_effect=CosmosResourceNotFoundError(message="Not found", status_code=404)
    )

    res = await tasks_client.delete(
        "/api/tasks/nonexistent",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )
    assert res.status_code == 404


async def test_get_tasks_no_cosmos(tasks_client: httpx.AsyncClient) -> None:
    """GET /api/tasks returns 503 when Cosmos is not configured."""
    # Remove cosmos_manager from app state
    app = tasks_client._transport.app  # type: ignore[attr-defined]
    app.state.cosmos_manager = None

    res = await tasks_client.get(
        "/api/tasks",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )
    assert res.status_code == 503
