"""Admin agent tools for shopping list management.

Uses the class-based tool pattern to bind CosmosManager references to @tool
functions. AdminTools provides the add_shopping_list_items tool that writes
shopping items to the ShoppingLists Cosmos container.
"""

import logging
from typing import Annotated

from agent_framework import tool
from pydantic import Field

from second_brain.db.cosmos import CosmosManager
from second_brain.models.documents import KNOWN_STORES, ShoppingListItem

logger = logging.getLogger(__name__)


class AdminTools:
    """Admin agent tools bound to a CosmosManager instance.

    Usage:
        tools = AdminTools(cosmos_manager=cosmos_mgr)
        agent_tools = [tools.add_shopping_list_items]
    """

    def __init__(self, cosmos_manager: CosmosManager) -> None:
        """Store the CosmosManager reference."""
        self._manager = cosmos_manager
        self.last_items_written: int = 0

    @tool(approval_mode="never_require")
    async def add_shopping_list_items(
        self,
        items: Annotated[
            list[dict],
            Field(
                description=(
                    "List of shopping items to add. Each dict must have "
                    "'name' (str, lowercase, natural language like '2 lbs ground beef') "
                    "and 'store' (str: jewel, cvs, pet_store, or other)"
                )
            ),
        ],
    ) -> str:
        """Add items to shopping lists, grouped by store.

        Each item is written as an individual document to the ShoppingLists
        container. Unknown store names silently fall back to 'other'.
        Returns a confirmation with total count and per-store breakdown.
        """
        container = self._manager.get_container("ShoppingLists")
        store_counts: dict[str, int] = {}

        for item_data in items:
            name = item_data.get("name", "").strip().lower()
            store = item_data.get("store", "other").strip().lower()

            # Skip items with empty names
            if not name:
                logger.warning("Skipping item with empty name: %s", item_data)
                continue

            # Validate store -- fall back to "other" silently
            if store not in KNOWN_STORES:
                logger.info(
                    "Unknown store '%s' for item '%s', falling back to 'other'",
                    store,
                    name,
                )
                store = "other"

            doc = ShoppingListItem(store=store, name=name)
            await container.create_item(body=doc.model_dump())
            store_counts[store] = store_counts.get(store, 0) + 1

        total = sum(store_counts.values())
        self.last_items_written = total
        if total == 0:
            return "No items added (all items had empty names)"

        breakdown = ", ".join(
            f"{count} to {store}" for store, count in store_counts.items()
        )
        return f"Added {total} items: {breakdown}"
