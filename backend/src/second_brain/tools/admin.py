"""Admin agent tools for errand item management.

Uses the class-based tool pattern to bind CosmosManager references to @tool
functions. AdminTools provides the add_errand_items tool that writes
errand items to the Errands Cosmos container.
"""

import logging
from typing import Annotated

from agent_framework import tool
from pydantic import Field

from second_brain.db.cosmos import CosmosManager
from second_brain.models.documents import KNOWN_DESTINATIONS, ErrandItem, TaskItem

logger = logging.getLogger(__name__)


class AdminTools:
    """Admin agent tools bound to a CosmosManager instance.

    Usage:
        tools = AdminTools(cosmos_manager=cosmos_mgr)
        agent_tools = [tools.add_errand_items]
    """

    def __init__(self, cosmos_manager: CosmosManager) -> None:
        """Store the CosmosManager reference."""
        self._manager = cosmos_manager

    @tool(approval_mode="never_require")
    async def add_errand_items(
        self,
        items: Annotated[
            list[dict],
            Field(
                description=(
                    "List of errand items to add. Each dict must have "
                    "'name' (str, lowercase, natural language like '2 lbs ground beef') "
                    "and 'destination' (str: jewel=Jewel-Osco grocery, "
                    "cvs=CVS pharmacy, pet_store=pet supplies, or other)"
                )
            ),
        ],
    ) -> str:
        """Add items to errands, grouped by destination.

        Each item is written as an individual document to the Errands
        container. Unknown destination names silently fall back to 'other'.
        Returns a confirmation with total count and per-destination breakdown.
        """
        container = self._manager.get_container("Errands")
        destination_counts: dict[str, int] = {}

        for item_data in items:
            name = item_data.get("name", "").strip().lower()
            # Accept both "destination" (new) and "store" (legacy Agent instructions)
            destination = (
                item_data.get("destination") or item_data.get("store") or "other"
            ).strip().lower()

            # Skip items with empty names
            if not name:
                logger.warning("Skipping item with empty name: %s", item_data)
                continue

            # Validate destination -- fall back to "other" silently
            if destination not in KNOWN_DESTINATIONS:
                logger.info(
                    "Unknown destination '%s' for item '%s', falling back to 'other'",
                    destination,
                    name,
                )
                destination = "other"

            doc = ErrandItem(destination=destination, name=name)
            await container.create_item(body=doc.model_dump())
            destination_counts[destination] = destination_counts.get(destination, 0) + 1

        total = sum(destination_counts.values())
        if total == 0:
            return "No items added (all items had empty names)"

        breakdown = ", ".join(
            f"{count} to {destination}" for destination, count in destination_counts.items()
        )
        return f"Added {total} items: {breakdown}"

    @tool(approval_mode="never_require")
    async def add_task_items(
        self,
        tasks: Annotated[
            list[dict],
            Field(
                description=(
                    "List of task items to add. Each dict must have "
                    "'name' (str, natural language description of the task, "
                    "e.g. 'book eye appointments', 'fill out Peloton expenses'). "
                    "Use this for actionable to-dos that are NOT shopping/errands."
                )
            ),
        ],
    ) -> str:
        """Add actionable tasks (non-errand admin items) to the Tasks list.

        Use this for things like appointments, expenses, phone calls,
        emails, and other to-dos that aren't shopping errands.
        Each task is written as an individual document to the Tasks container.
        Returns a confirmation with total count.
        """
        container = self._manager.get_container("Tasks")
        added = 0

        for task_data in tasks:
            name = task_data.get("name", "").strip()
            if not name:
                logger.warning("Skipping task with empty name: %s", task_data)
                continue

            doc = TaskItem(name=name)
            await container.create_item(body=doc.model_dump(mode="json"))
            added += 1

        if added == 0:
            return "No tasks added (all tasks had empty names)"

        return f"Added {added} task{'s' if added != 1 else ''}"
