"""Unit tests for AdminTools (add_shopping_list_items).

Tests use the mock_cosmos_manager fixture from conftest.py. No real Azure calls.
"""

from unittest.mock import AsyncMock

import pytest

from second_brain.tools.admin import AdminTools

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tools(mock_cosmos_manager: object) -> AdminTools:
    """Create an AdminTools instance with mock manager."""
    return AdminTools(cosmos_manager=mock_cosmos_manager)


def _echo_body(*, body: dict) -> dict:
    """Side-effect for create_item: return the body it was called with."""
    return body


def _setup_echo(mock_cosmos_manager: object, container_name: str) -> None:
    """Set up a container's create_item to echo back the body."""
    container = mock_cosmos_manager.get_container(container_name)
    container.create_item = AsyncMock(side_effect=_echo_body)


def _get_all_bodies(mock_cosmos_manager: object, container: str) -> list[dict]:
    """Extract all body dicts from a container's create_item calls."""
    c = mock_cosmos_manager.get_container(container)
    return [call[1]["body"] for call in c.create_item.call_args_list]


# ---------------------------------------------------------------------------
# Tests: add_shopping_list_items
# ---------------------------------------------------------------------------


async def test_add_items_happy_path(
    mock_cosmos_manager: object,
) -> None:
    """Two items to different stores: both written, confirmation returned."""
    _setup_echo(mock_cosmos_manager, "ShoppingLists")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_shopping_list_items(
        items=[
            {"name": "milk", "store": "jewel"},
            {"name": "bandages", "store": "cvs"},
        ]
    )

    assert "Added 2 items" in result
    assert "jewel" in result
    assert "cvs" in result

    # Verify create_item called twice
    container = mock_cosmos_manager.get_container("ShoppingLists")
    assert container.create_item.call_count == 2

    bodies = _get_all_bodies(mock_cosmos_manager, "ShoppingLists")
    names = {b["name"] for b in bodies}
    stores = {b["store"] for b in bodies}
    assert names == {"milk", "bandages"}
    assert stores == {"jewel", "cvs"}


async def test_add_items_unknown_store_falls_back_to_other(
    mock_cosmos_manager: object,
) -> None:
    """Unknown store 'walmart' falls back to 'other'."""
    _setup_echo(mock_cosmos_manager, "ShoppingLists")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_shopping_list_items(
        items=[{"name": "shampoo", "store": "walmart"}]
    )

    assert "Added 1 items" in result
    assert "other" in result

    bodies = _get_all_bodies(mock_cosmos_manager, "ShoppingLists")
    assert len(bodies) == 1
    assert bodies[0]["store"] == "other"
    assert bodies[0]["name"] == "shampoo"


async def test_add_items_empty_name_skipped(
    mock_cosmos_manager: object,
) -> None:
    """Item with empty name is skipped; only valid item is written."""
    _setup_echo(mock_cosmos_manager, "ShoppingLists")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_shopping_list_items(
        items=[
            {"name": "", "store": "jewel"},
            {"name": "eggs", "store": "jewel"},
        ]
    )

    assert "Added 1 items" in result

    container = mock_cosmos_manager.get_container("ShoppingLists")
    assert container.create_item.call_count == 1

    bodies = _get_all_bodies(mock_cosmos_manager, "ShoppingLists")
    assert bodies[0]["name"] == "eggs"


async def test_add_items_all_empty_names(
    mock_cosmos_manager: object,
) -> None:
    """All items have empty names: none written, appropriate message returned."""
    _setup_echo(mock_cosmos_manager, "ShoppingLists")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_shopping_list_items(
        items=[
            {"name": "", "store": "jewel"},
            {"name": "   ", "store": "cvs"},
        ]
    )

    assert result == "No items added (all items had empty names)"

    container = mock_cosmos_manager.get_container("ShoppingLists")
    container.create_item.assert_not_called()


async def test_add_items_normalizes_case(
    mock_cosmos_manager: object,
) -> None:
    """Name and store are lowercased in the written document."""
    _setup_echo(mock_cosmos_manager, "ShoppingLists")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_shopping_list_items(
        items=[{"name": "MILK", "store": "JEWEL"}]
    )

    assert "Added 1 items" in result

    bodies = _get_all_bodies(mock_cosmos_manager, "ShoppingLists")
    assert bodies[0]["name"] == "milk"
    assert bodies[0]["store"] == "jewel"


async def test_add_items_multiple_to_same_store(
    mock_cosmos_manager: object,
) -> None:
    """Three items to the same store: correct count in confirmation."""
    _setup_echo(mock_cosmos_manager, "ShoppingLists")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_shopping_list_items(
        items=[
            {"name": "apples", "store": "jewel"},
            {"name": "bread", "store": "jewel"},
            {"name": "cheese", "store": "jewel"},
        ]
    )

    assert "Added 3 items" in result
    assert "3 to jewel" in result

    container = mock_cosmos_manager.get_container("ShoppingLists")
    assert container.create_item.call_count == 3
