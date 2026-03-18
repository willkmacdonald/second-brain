"""Unit tests for AdminTools (all 6 tools).

Tests use the mock_cosmos_manager fixture from conftest.py. No real Azure calls.
"""

from unittest.mock import AsyncMock, MagicMock

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


async def _async_iter(items: list):
    """Create an async iterator from a list."""
    for item in items:
        yield item


def _setup_query(
    mock_cosmos_manager: object,
    container_name: str,
    results: list[dict],
) -> None:
    """Set up a container's query_items to return a fixed list as async iterator."""
    container = mock_cosmos_manager.get_container(container_name)
    container.query_items = MagicMock(return_value=_async_iter(results))


def _setup_query_multi(
    mock_cosmos_manager: object,
    container_name: str,
    results_sequence: list[list[dict]],
) -> None:
    """Set up query_items to return different results on successive calls."""
    container = mock_cosmos_manager.get_container(container_name)
    call_count = 0

    def _side_effect(**kwargs):
        nonlocal call_count
        idx = min(call_count, len(results_sequence) - 1)
        call_count += 1
        return _async_iter(results_sequence[idx])

    container.query_items = MagicMock(side_effect=_side_effect)


# ---------------------------------------------------------------------------
# Tests: add_errand_items
# ---------------------------------------------------------------------------


async def test_add_items_happy_path(
    mock_cosmos_manager: object,
) -> None:
    """Two items to different destinations: both written, confirmation returned."""
    _setup_echo(mock_cosmos_manager, "Errands")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_errand_items(
        items=[
            {"name": "milk", "destination": "jewel"},
            {"name": "bandages", "destination": "cvs"},
        ]
    )

    assert "Added 2 items" in result
    assert "jewel" in result
    assert "cvs" in result

    # Verify create_item called twice
    container = mock_cosmos_manager.get_container("Errands")
    assert container.create_item.call_count == 2

    bodies = _get_all_bodies(mock_cosmos_manager, "Errands")
    names = {b["name"] for b in bodies}
    destinations = {b["destination"] for b in bodies}
    assert names == {"milk", "bandages"}
    assert destinations == {"jewel", "cvs"}


async def test_add_items_dynamic_destination_accepted(
    mock_cosmos_manager: object,
) -> None:
    """Any destination slug is accepted as-is (no hardcoded validation)."""
    _setup_echo(mock_cosmos_manager, "Errands")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_errand_items(
        items=[{"name": "shampoo", "destination": "walmart"}]
    )

    assert "Added 1 items" in result
    assert "walmart" in result

    bodies = _get_all_bodies(mock_cosmos_manager, "Errands")
    assert len(bodies) == 1
    assert bodies[0]["destination"] == "walmart"
    assert bodies[0]["name"] == "shampoo"
    assert bodies[0]["needsRouting"] is False


async def test_add_items_unrouted_sets_needs_routing(
    mock_cosmos_manager: object,
) -> None:
    """Items with destination='unrouted' have needsRouting=True."""
    _setup_echo(mock_cosmos_manager, "Errands")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_errand_items(
        items=[{"name": "mystery item", "destination": "unrouted"}]
    )

    assert "Added 1 items" in result
    assert "unrouted" in result

    bodies = _get_all_bodies(mock_cosmos_manager, "Errands")
    assert bodies[0]["destination"] == "unrouted"
    assert bodies[0]["needsRouting"] is True


async def test_add_items_empty_name_skipped(
    mock_cosmos_manager: object,
) -> None:
    """Item with empty name is skipped; only valid item is written."""
    _setup_echo(mock_cosmos_manager, "Errands")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_errand_items(
        items=[
            {"name": "", "destination": "jewel"},
            {"name": "eggs", "destination": "jewel"},
        ]
    )

    assert "Added 1 items" in result

    container = mock_cosmos_manager.get_container("Errands")
    assert container.create_item.call_count == 1

    bodies = _get_all_bodies(mock_cosmos_manager, "Errands")
    assert bodies[0]["name"] == "eggs"


async def test_add_items_all_empty_names(
    mock_cosmos_manager: object,
) -> None:
    """All items have empty names: none written, appropriate message returned."""
    _setup_echo(mock_cosmos_manager, "Errands")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_errand_items(
        items=[
            {"name": "", "destination": "jewel"},
            {"name": "   ", "destination": "cvs"},
        ]
    )

    assert result == "No items added (all items had empty names)"

    container = mock_cosmos_manager.get_container("Errands")
    container.create_item.assert_not_called()


async def test_add_items_normalizes_case(
    mock_cosmos_manager: object,
) -> None:
    """Name and destination are lowercased in the written document."""
    _setup_echo(mock_cosmos_manager, "Errands")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_errand_items(
        items=[{"name": "MILK", "destination": "JEWEL"}]
    )

    assert "Added 1 items" in result

    bodies = _get_all_bodies(mock_cosmos_manager, "Errands")
    assert bodies[0]["name"] == "milk"
    assert bodies[0]["destination"] == "jewel"


async def test_add_items_multiple_to_same_destination(
    mock_cosmos_manager: object,
) -> None:
    """Three items to the same destination: correct count in confirmation."""
    _setup_echo(mock_cosmos_manager, "Errands")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_errand_items(
        items=[
            {"name": "apples", "destination": "jewel"},
            {"name": "bread", "destination": "jewel"},
            {"name": "cheese", "destination": "jewel"},
        ]
    )

    assert "Added 3 items" in result
    assert "3 to jewel" in result

    container = mock_cosmos_manager.get_container("Errands")
    assert container.create_item.call_count == 3


async def test_add_items_no_destination_defaults_to_unrouted(
    mock_cosmos_manager: object,
) -> None:
    """Missing destination defaults to 'unrouted' with needsRouting=True."""
    _setup_echo(mock_cosmos_manager, "Errands")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.add_errand_items(
        items=[{"name": "something"}]
    )

    assert "Added 1 items" in result

    bodies = _get_all_bodies(mock_cosmos_manager, "Errands")
    assert bodies[0]["destination"] == "unrouted"
    assert bodies[0]["needsRouting"] is True


# ---------------------------------------------------------------------------
# Tests: get_routing_context
# ---------------------------------------------------------------------------


async def test_get_routing_context_with_rules_and_destinations(
    mock_cosmos_manager: object,
) -> None:
    """Routing context includes destinations and rules when both exist."""
    sample_destinations = [
        {"slug": "jewel", "displayName": "Jewel-Osco", "type": "physical"},
        {"slug": "chewy", "displayName": "Chewy", "type": "online"},
    ]
    sample_rules = [
        {
            "naturalLanguage": "meat goes to Agora",
            "ruleType": "category",
            "itemPattern": "meat",
            "destinationSlug": "agora",
        },
        {
            "naturalLanguage": "Luna's food goes to PetSmart",
            "ruleType": "entity",
            "itemPattern": "luna's food",
            "destinationSlug": "petsmart",
        },
    ]

    _setup_query(mock_cosmos_manager, "Destinations", sample_destinations)
    _setup_query(mock_cosmos_manager, "AffinityRules", sample_rules)

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.get_routing_context()

    assert "DESTINATIONS:" in result
    assert "jewel (Jewel-Osco, physical)" in result
    assert "chewy (Chewy, online)" in result
    assert "ROUTING RULES:" in result
    assert "meat goes to Agora" in result
    assert "Luna's food goes to PetSmart" in result
    assert "unrouted" in result


async def test_get_routing_context_no_rules(
    mock_cosmos_manager: object,
) -> None:
    """When no rules exist, the 'no rules defined' message appears."""
    sample_destinations = [
        {"slug": "jewel", "displayName": "Jewel-Osco", "type": "physical"},
    ]

    _setup_query(mock_cosmos_manager, "Destinations", sample_destinations)
    _setup_query(mock_cosmos_manager, "AffinityRules", [])

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.get_routing_context()

    assert "DESTINATIONS:" in result
    assert "jewel (Jewel-Osco, physical)" in result
    assert "No routing rules defined" in result
    assert "destination='unrouted'" in result


async def test_get_routing_context_no_destinations_or_rules(
    mock_cosmos_manager: object,
) -> None:
    """When nothing exists, show no-destinations and no-rules messages."""
    _setup_query(mock_cosmos_manager, "Destinations", [])
    _setup_query(mock_cosmos_manager, "AffinityRules", [])

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.get_routing_context()

    assert "No destinations defined yet" in result
    assert "No routing rules defined" in result


# ---------------------------------------------------------------------------
# Tests: manage_destination
# ---------------------------------------------------------------------------


async def test_manage_destination_create(
    mock_cosmos_manager: object,
) -> None:
    """Create a new destination successfully."""
    _setup_query(mock_cosmos_manager, "Destinations", [])
    _setup_echo(mock_cosmos_manager, "Destinations")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_destination(
        action="create",
        name="Costco",
        slug="costco",
        destination_type="physical",
    )

    assert "Created destination 'Costco'" in result
    assert "costco" in result
    assert "physical" in result

    container = mock_cosmos_manager.get_container("Destinations")
    assert container.create_item.call_count == 1

    body = container.create_item.call_args[1]["body"]
    assert body["slug"] == "costco"
    assert body["displayName"] == "Costco"
    assert body["type"] == "physical"


async def test_manage_destination_create_default_type(
    mock_cosmos_manager: object,
) -> None:
    """Create a destination without specifying type defaults to 'physical'."""
    _setup_query(mock_cosmos_manager, "Destinations", [])
    _setup_echo(mock_cosmos_manager, "Destinations")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_destination(
        action="create",
        name="Target",
        slug="target",
    )

    assert "physical" in result

    body = mock_cosmos_manager.get_container("Destinations").create_item.call_args[1]["body"]
    assert body["type"] == "physical"


async def test_manage_destination_create_duplicate(
    mock_cosmos_manager: object,
) -> None:
    """Attempting to create a destination with an existing slug returns 'already exists'."""
    _setup_query(
        mock_cosmos_manager,
        "Destinations",
        [{"id": "costco", "slug": "costco", "displayName": "Costco"}],
    )

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_destination(
        action="create",
        name="Costco",
        slug="costco",
    )

    assert "already exists" in result

    container = mock_cosmos_manager.get_container("Destinations")
    container.create_item.assert_not_called()


async def test_manage_destination_remove_empty(
    mock_cosmos_manager: object,
) -> None:
    """Remove a destination with no errand items deletes it."""
    # Errands query returns count 0
    _setup_query(mock_cosmos_manager, "Errands", [0])
    # Destinations query returns the destination doc
    _setup_query(
        mock_cosmos_manager,
        "Destinations",
        [{"id": "old_store", "slug": "old_store", "displayName": "Old Store"}],
    )

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_destination(
        action="remove",
        name="Old Store",
        slug="old_store",
    )

    assert "Removed destination 'Old Store'" in result

    container = mock_cosmos_manager.get_container("Destinations")
    container.delete_item.assert_called_once_with(
        item="old_store", partition_key="will"
    )


async def test_manage_destination_remove_with_items(
    mock_cosmos_manager: object,
) -> None:
    """Remove a destination that has items returns a warning, no delete."""
    # Errands query returns count 5
    _setup_query(mock_cosmos_manager, "Errands", [5])

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_destination(
        action="remove",
        name="Jewel",
        slug="jewel",
    )

    assert "has 5 items" in result
    assert "Where should they go?" in result

    container = mock_cosmos_manager.get_container("Destinations")
    container.delete_item.assert_not_called()


async def test_manage_destination_rename(
    mock_cosmos_manager: object,
) -> None:
    """Rename a destination's display name."""
    _setup_query(
        mock_cosmos_manager,
        "Destinations",
        [{"id": "jewel", "slug": "jewel", "displayName": "Jewel-Osco", "userId": "will"}],
    )

    container = mock_cosmos_manager.get_container("Destinations")
    container.upsert_item = AsyncMock()

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_destination(
        action="rename",
        name="Jewel-Osco",
        slug="jewel",
        new_name="Jewel Grocery",
    )

    assert "Renamed destination 'jewel'" in result
    assert "Jewel Grocery" in result

    container.upsert_item.assert_called_once()
    body = container.upsert_item.call_args[1]["body"]
    assert body["displayName"] == "Jewel Grocery"


# ---------------------------------------------------------------------------
# Tests: manage_affinity_rule
# ---------------------------------------------------------------------------


async def test_manage_affinity_rule_create(
    mock_cosmos_manager: object,
) -> None:
    """Create a new affinity rule when no conflict exists."""
    _setup_query(mock_cosmos_manager, "AffinityRules", [])
    _setup_echo(mock_cosmos_manager, "AffinityRules")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_affinity_rule(
        action="create",
        natural_language="chicken always goes to Agora",
        item_pattern="chicken",
        destination_slug="agora",
        rule_type="item",
    )

    assert "Created rule" in result
    assert "chicken" in result
    assert "agora" in result

    container = mock_cosmos_manager.get_container("AffinityRules")
    assert container.create_item.call_count == 1

    body = container.create_item.call_args[1]["body"]
    assert body["itemPattern"] == "chicken"
    assert body["destinationSlug"] == "agora"
    assert body["ruleType"] == "item"
    assert body["autoSaved"] is False


async def test_manage_affinity_rule_create_conflict(
    mock_cosmos_manager: object,
) -> None:
    """Creating a rule for an existing pattern returns a conflict message."""
    existing_rules = [
        {
            "id": "rule-1",
            "itemPattern": "chicken",
            "destinationSlug": "jewel",
            "naturalLanguage": "chicken goes to Jewel",
        }
    ]
    _setup_query(mock_cosmos_manager, "AffinityRules", existing_rules)

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_affinity_rule(
        action="create",
        natural_language="chicken goes to Agora",
        item_pattern="chicken",
        destination_slug="agora",
        rule_type="item",
    )

    assert "currently routes to 'jewel'" in result
    assert "yes change it" in result

    container = mock_cosmos_manager.get_container("AffinityRules")
    container.create_item.assert_not_called()


async def test_manage_affinity_rule_create_conflict_case_insensitive(
    mock_cosmos_manager: object,
) -> None:
    """Conflict detection is case-insensitive."""
    existing_rules = [
        {
            "id": "rule-1",
            "itemPattern": "Chicken",
            "destinationSlug": "jewel",
        }
    ]
    _setup_query(mock_cosmos_manager, "AffinityRules", existing_rules)

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_affinity_rule(
        action="create",
        natural_language="chicken goes to Agora",
        item_pattern="CHICKEN",
        destination_slug="agora",
        rule_type="item",
    )

    assert "currently routes to" in result

    container = mock_cosmos_manager.get_container("AffinityRules")
    container.create_item.assert_not_called()


async def test_manage_affinity_rule_update(
    mock_cosmos_manager: object,
) -> None:
    """Update an existing rule changes destination and other fields."""
    existing_rules = [
        {
            "id": "rule-1",
            "itemPattern": "chicken",
            "destinationSlug": "jewel",
            "naturalLanguage": "chicken goes to Jewel",
            "ruleType": "item",
            "exceptions": [],
            "autoSaved": False,
            "userId": "will",
        }
    ]
    _setup_query(mock_cosmos_manager, "AffinityRules", existing_rules)

    container = mock_cosmos_manager.get_container("AffinityRules")
    container.upsert_item = AsyncMock()

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_affinity_rule(
        action="update",
        natural_language="chicken now goes to Agora",
        item_pattern="chicken",
        destination_slug="agora",
        rule_type="item",
    )

    assert "Updated rule" in result
    assert "agora" in result

    container.upsert_item.assert_called_once()
    body = container.upsert_item.call_args[1]["body"]
    assert body["destinationSlug"] == "agora"
    assert body["naturalLanguage"] == "chicken now goes to Agora"


async def test_manage_affinity_rule_delete(
    mock_cosmos_manager: object,
) -> None:
    """Delete a rule by item_pattern removes it from Cosmos."""
    existing_rules = [
        {
            "id": "rule-1",
            "itemPattern": "chicken",
            "destinationSlug": "jewel",
            "userId": "will",
        }
    ]
    _setup_query(mock_cosmos_manager, "AffinityRules", existing_rules)

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_affinity_rule(
        action="delete",
        natural_language="",
        item_pattern="chicken",
        destination_slug="",
        rule_type="item",
    )

    assert "Deleted rule for 'chicken'" in result

    container = mock_cosmos_manager.get_container("AffinityRules")
    container.delete_item.assert_called_once_with(
        item="rule-1", partition_key="will"
    )


async def test_manage_affinity_rule_delete_not_found(
    mock_cosmos_manager: object,
) -> None:
    """Deleting a non-existent rule returns 'not found' message."""
    _setup_query(mock_cosmos_manager, "AffinityRules", [])

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_affinity_rule(
        action="delete",
        natural_language="",
        item_pattern="nonexistent",
        destination_slug="",
        rule_type="item",
    )

    assert "No rule found for 'nonexistent'" in result


async def test_manage_affinity_rule_create_with_exceptions(
    mock_cosmos_manager: object,
) -> None:
    """Create a rule with exceptions stores them correctly."""
    _setup_query(mock_cosmos_manager, "AffinityRules", [])
    _setup_echo(mock_cosmos_manager, "AffinityRules")

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.manage_affinity_rule(
        action="create",
        natural_language="meat goes to Agora except fish goes to Nick's",
        item_pattern="meat",
        destination_slug="agora",
        rule_type="category",
        exceptions=[{"pattern": "fish", "destinationSlug": "nicks_fishmarket"}],
    )

    assert "Created rule" in result

    body = mock_cosmos_manager.get_container("AffinityRules").create_item.call_args[1]["body"]
    assert body["exceptions"] == [{"pattern": "fish", "destinationSlug": "nicks_fishmarket"}]
    assert body["ruleType"] == "category"


# ---------------------------------------------------------------------------
# Tests: query_rules
# ---------------------------------------------------------------------------


async def test_query_rules_all(
    mock_cosmos_manager: object,
) -> None:
    """Asking 'what are my rules?' returns all rules grouped by destination."""
    sample_rules = [
        {
            "naturalLanguage": "chicken goes to Agora",
            "ruleType": "item",
            "itemPattern": "chicken",
            "destinationSlug": "agora",
        },
        {
            "naturalLanguage": "pet food goes to PetSmart",
            "ruleType": "category",
            "itemPattern": "pet food",
            "destinationSlug": "petsmart",
        },
    ]
    sample_destinations = [
        {"slug": "agora", "displayName": "Agora"},
        {"slug": "petsmart", "displayName": "PetSmart"},
    ]

    _setup_query(mock_cosmos_manager, "AffinityRules", sample_rules)
    _setup_query(mock_cosmos_manager, "Destinations", sample_destinations)

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.query_rules(query_text="what are my rules?")

    assert "All routing rules:" in result
    assert "chicken goes to Agora" in result
    assert "pet food goes to PetSmart" in result
    assert "Agora" in result
    assert "PetSmart" in result


async def test_query_rules_specific_item(
    mock_cosmos_manager: object,
) -> None:
    """Asking 'where does chicken go?' returns the matching rule."""
    sample_rules = [
        {
            "naturalLanguage": "chicken goes to Agora",
            "ruleType": "item",
            "itemPattern": "chicken",
            "destinationSlug": "agora",
        },
    ]
    sample_destinations = [
        {"slug": "agora", "displayName": "Agora"},
    ]

    _setup_query(mock_cosmos_manager, "AffinityRules", sample_rules)
    _setup_query(mock_cosmos_manager, "Destinations", sample_destinations)

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.query_rules(query_text="where does chicken go?")

    assert "chicken goes to Agora" in result
    assert "Agora (agora)" in result


async def test_query_rules_no_match(
    mock_cosmos_manager: object,
) -> None:
    """Asking about an item with no rule returns 'No routing rules' message."""
    _setup_query(mock_cosmos_manager, "AffinityRules", [])
    _setup_query(mock_cosmos_manager, "Destinations", [])

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.query_rules(query_text="where does salmon go?")

    assert "No routing rules defined yet" in result
    assert "create one" in result


async def test_query_rules_specific_item_with_exceptions(
    mock_cosmos_manager: object,
) -> None:
    """Querying a rule with exceptions includes exception details."""
    sample_rules = [
        {
            "naturalLanguage": "meat goes to Agora except fish",
            "ruleType": "category",
            "itemPattern": "meat",
            "destinationSlug": "agora",
            "exceptions": [{"pattern": "fish", "destinationSlug": "nicks"}],
        },
    ]
    sample_destinations = [
        {"slug": "agora", "displayName": "Agora"},
        {"slug": "nicks", "displayName": "Nick's Fishmarket"},
    ]

    _setup_query(mock_cosmos_manager, "AffinityRules", sample_rules)
    _setup_query(mock_cosmos_manager, "Destinations", sample_destinations)

    tools = _make_tools(mock_cosmos_manager)
    result = await tools.query_rules(query_text="where does meat go?")

    assert "meat goes to Agora except fish" in result
    assert "Exception: fish" in result
    assert "Nick's Fishmarket" in result
