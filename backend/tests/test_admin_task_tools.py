"""Unit tests for AdminTools.add_task_items.

Tests use the mock_cosmos_manager fixture from conftest.py. No real Azure calls.
"""

from unittest.mock import AsyncMock

import pytest

from second_brain.tools.admin import AdminTools


def _make_tools(mock_cosmos_manager: object) -> AdminTools:
    """Create an AdminTools instance with mock manager."""
    return AdminTools(cosmos_manager=mock_cosmos_manager)


def _setup_echo(mock_cosmos_manager: object, container_name: str) -> None:
    """Set up a container's create_item to echo back the body."""
    container = mock_cosmos_manager.get_container(container_name)
    container.create_item = AsyncMock(side_effect=lambda *, body: body)


def _get_all_bodies(mock_cosmos_manager: object, container: str) -> list[dict]:
    """Extract all body dicts from a container's create_item calls."""
    c = mock_cosmos_manager.get_container(container)
    return [call[1]["body"] for call in c.create_item.call_args_list]


async def test_add_task_items_happy_path(mock_cosmos_manager: object) -> None:
    """Two tasks added: both written, confirmation returned."""
    _setup_echo(mock_cosmos_manager, "Tasks")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_task_items(
        tasks=[
            {"name": "Book eye appointments"},
            {"name": "Fill out Peloton expenses"},
        ]
    )

    assert "Added 2 tasks" in result

    container = mock_cosmos_manager.get_container("Tasks")
    assert container.create_item.call_count == 2

    bodies = _get_all_bodies(mock_cosmos_manager, "Tasks")
    names = {b["name"] for b in bodies}
    assert names == {"Book eye appointments", "Fill out Peloton expenses"}


async def test_add_task_items_single(mock_cosmos_manager: object) -> None:
    """Single task: correct singular form in confirmation."""
    _setup_echo(mock_cosmos_manager, "Tasks")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_task_items(
        tasks=[{"name": "Call dentist"}]
    )

    assert "Added 1 task" in result
    assert "tasks" not in result  # Singular, not plural


async def test_add_task_items_empty_name_skipped(mock_cosmos_manager: object) -> None:
    """Task with empty name is skipped."""
    _setup_echo(mock_cosmos_manager, "Tasks")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_task_items(
        tasks=[
            {"name": ""},
            {"name": "Return package"},
        ]
    )

    assert "Added 1 task" in result

    container = mock_cosmos_manager.get_container("Tasks")
    assert container.create_item.call_count == 1


async def test_add_task_items_all_empty(mock_cosmos_manager: object) -> None:
    """All tasks have empty names: none written."""
    _setup_echo(mock_cosmos_manager, "Tasks")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_task_items(
        tasks=[{"name": ""}, {"name": "   "}]
    )

    assert result == "No tasks added (all tasks had empty names)"

    container = mock_cosmos_manager.get_container("Tasks")
    container.create_item.assert_not_called()


async def test_add_task_items_preserves_case(mock_cosmos_manager: object) -> None:
    """Task names preserve original case (unlike errand items)."""
    _setup_echo(mock_cosmos_manager, "Tasks")

    tools = _make_tools(mock_cosmos_manager)
    await tools.add_task_items(
        tasks=[{"name": "Book Eye Appointments"}]
    )

    bodies = _get_all_bodies(mock_cosmos_manager, "Tasks")
    assert bodies[0]["name"] == "Book Eye Appointments"


async def test_add_task_items_has_userid(mock_cosmos_manager: object) -> None:
    """Task items include userId field for partition key."""
    _setup_echo(mock_cosmos_manager, "Tasks")

    tools = _make_tools(mock_cosmos_manager)
    await tools.add_task_items(
        tasks=[{"name": "Test task"}]
    )

    bodies = _get_all_bodies(mock_cosmos_manager, "Tasks")
    assert bodies[0]["userId"] == "will"
