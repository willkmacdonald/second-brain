"""Admin agent tools for errand item and destination management.

Uses the class-based tool pattern to bind CosmosManager references to @tool
functions. AdminTools provides 6 tools: add_errand_items, add_task_items,
get_routing_context, manage_destination, manage_affinity_rule, and query_rules.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from agent_framework import tool
from pydantic import Field

from second_brain.db.cosmos import CosmosManager
from second_brain.models.documents import (
    AffinityRuleDocument,
    DestinationDocument,
    ErrandItem,
    TaskItem,
)

logger = logging.getLogger(__name__)


async def build_routing_context(cosmos_manager: CosmosManager) -> str:
    """Build formatted routing context from destinations and affinity rules.

    Shared by the AdminTools.get_routing_context tool and admin_handoff.py.
    Returns a formatted string for the Admin Agent's routing decisions.
    """
    # Query destinations
    dest_container = cosmos_manager.get_container("Destinations")
    destinations: list[dict] = []
    async for item in dest_container.query_items(
        query="SELECT * FROM c WHERE c.userId = 'will'",
        partition_key="will",
    ):
        destinations.append(item)

    # Query affinity rules
    rules_container = cosmos_manager.get_container("AffinityRules")
    rules: list[dict] = []
    async for item in rules_container.query_items(
        query="SELECT * FROM c WHERE c.userId = 'will'",
        partition_key="will",
    ):
        rules.append(item)

    # Format context
    lines: list[str] = ["DESTINATIONS:"]
    if destinations:
        for dest in destinations:
            slug = dest.get("slug", "unknown")
            display = dest.get("displayName", slug)
            dtype = dest.get("type", "physical")
            lines.append(f"- {slug} ({display}, {dtype})")
    else:
        lines.append("- No destinations defined yet.")

    lines.append("")
    lines.append("ROUTING RULES:")
    if rules:
        for rule in rules:
            nl = rule.get("naturalLanguage", "")
            rtype = rule.get("ruleType", "item")
            pattern = rule.get("itemPattern", "")
            dest_slug = rule.get("destinationSlug", "")
            lines.append(f'- "{nl}" ({rtype}: {pattern} -> {dest_slug})')
        lines.append("")
        lines.append("If no rule matches an item, set destination to 'unrouted'.")
    else:
        lines.append(
            "No routing rules defined. Set all errand items to destination='unrouted'."
        )

    return "\n".join(lines)


class AdminTools:
    """Admin agent tools bound to a CosmosManager instance.

    Usage:
        tools = AdminTools(cosmos_manager=cosmos_mgr)
        agent_tools = [
            tools.add_errand_items, tools.add_task_items,
            tools.get_routing_context, tools.manage_destination,
            tools.manage_affinity_rule, tools.query_rules,
        ]
    """

    def __init__(self, cosmos_manager: CosmosManager) -> None:
        """Store the CosmosManager reference."""
        self._manager = cosmos_manager

    # ------------------------------------------------------------------
    # Helper: async query_items collection
    # ------------------------------------------------------------------

    async def _collect_query(
        self,
        container_name: str,
        query: str,
        partition_key: str = "will",
        parameters: list[dict] | None = None,
    ) -> list[dict]:
        """Run a Cosmos query and collect all results into a list."""
        container = self._manager.get_container(container_name)
        results: list[dict] = []
        kwargs: dict = {"query": query, "partition_key": partition_key}
        if parameters is not None:
            kwargs["parameters"] = parameters
        async for item in container.query_items(**kwargs):
            results.append(item)
        return results

    # ------------------------------------------------------------------
    # Tool 1: add_errand_items (modified -- dynamic destinations)
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def add_errand_items(
        self,
        items: Annotated[
            list[dict],
            Field(
                description=(
                    "List of errand items to add. Each dict must have "
                    "'name' (str, lowercase, natural language like '2 lbs ground beef') "
                    "and 'destination' (str, the destination slug from routing context). "
                    "Set destination to 'unrouted' if no affinity rule matches the item. "
                    "Optionally include 'sourceName' (str, recipe title) and "
                    "'sourceUrl' (str, recipe page URL) for items extracted from recipes."
                )
            ),
        ],
    ) -> str:
        """Add items to errands, grouped by destination.

        Each item is written as an individual document to the Errands
        container. Destinations are dynamic slugs from the Destinations
        container. Use 'unrouted' for items with no matching affinity rule.
        Returns a confirmation with total count and per-destination breakdown.
        """
        container = self._manager.get_container("Errands")
        destination_counts: dict[str, int] = {}

        for item_data in items:
            name = item_data.get("name", "").strip().lower()
            # Accept both "destination" (new) and "store" (legacy Agent instructions)
            destination = (
                item_data.get("destination") or item_data.get("store") or "unrouted"
            ).strip().lower()

            # Skip items with empty names
            if not name:
                logger.warning("Skipping item with empty name: %s", item_data)
                continue

            needs_routing = destination == "unrouted"
            source_name = item_data.get("sourceName")
            source_url = item_data.get("sourceUrl")
            doc = ErrandItem(
                destination=destination,
                name=name,
                needsRouting=needs_routing,
                sourceName=source_name,
                sourceUrl=source_url,
            )
            await container.create_item(body=doc.model_dump())
            destination_counts[destination] = destination_counts.get(destination, 0) + 1

        total = sum(destination_counts.values())
        if total == 0:
            return "No items added (all items had empty names)"

        breakdown = ", ".join(
            f"{count} to {dest}" for dest, count in destination_counts.items()
        )
        return f"Added {total} items: {breakdown}"

    # ------------------------------------------------------------------
    # Tool 2: add_task_items (unchanged)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Tool 3: get_routing_context
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def get_routing_context(self) -> str:
        """Load all destinations and affinity rules for routing decisions.

        Call this at the start of processing ANY Admin capture. Returns a
        formatted list of available destinations and routing rules so the
        agent can make informed routing decisions.
        """
        return await build_routing_context(self._manager)

    # ------------------------------------------------------------------
    # Tool 4: manage_destination
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def manage_destination(
        self,
        action: Annotated[
            str, Field(description="Action: 'create', 'rename', 'remove'")
        ],
        name: Annotated[
            str, Field(description="Destination name (e.g., 'Costco')")
        ],
        slug: Annotated[
            str, Field(description="URL-safe lowercase slug (e.g., 'costco')")
        ],
        destination_type: Annotated[
            str | None,
            Field(
                description="Type: 'physical' or 'online'. Infer from name if not sure."
            ),
        ] = None,
        new_name: Annotated[
            str | None, Field(description="New display name (rename only)")
        ] = None,
        new_slug: Annotated[
            str | None, Field(description="New slug (rename only)")
        ] = None,
    ) -> str:
        """Create, rename, or remove an errand destination."""
        action = action.strip().lower()

        if action == "create":
            return await self._destination_create(name, slug, destination_type)
        elif action == "rename":
            return await self._destination_rename(slug, new_name, new_slug)
        elif action == "remove":
            return await self._destination_remove(name, slug)
        else:
            return f"Unknown action '{action}'. Use 'create', 'rename', or 'remove'."

    async def _destination_create(
        self, name: str, slug: str, destination_type: str | None
    ) -> str:
        """Create a new destination if slug does not already exist."""
        query = "SELECT * FROM c WHERE c.slug = @slug AND c.userId = 'will'"
        parameters = [{"name": "@slug", "value": slug}]
        existing = await self._collect_query(
            "Destinations", query, parameters=parameters
        )
        if existing:
            return f"Destination '{name}' already exists."

        dtype = destination_type or "physical"
        doc = DestinationDocument(
            id=slug, slug=slug, displayName=name, type=dtype
        )
        container = self._manager.get_container("Destinations")
        await container.create_item(body=doc.model_dump(mode="json"))
        return f"Created destination '{name}' (slug: {slug}, type: {dtype})."

    async def _destination_rename(
        self, slug: str, new_name: str | None, new_slug: str | None
    ) -> str:
        """Rename a destination's display name and/or slug."""
        query = "SELECT * FROM c WHERE c.slug = @slug AND c.userId = 'will'"
        parameters = [{"name": "@slug", "value": slug}]
        existing = await self._collect_query(
            "Destinations", query, parameters=parameters
        )
        if not existing:
            return f"Destination with slug '{slug}' not found."

        dest = existing[0]
        if new_name:
            dest["displayName"] = new_name
        if new_slug:
            dest["slug"] = new_slug
        dest["updatedAt"] = datetime.now(UTC).isoformat()

        container = self._manager.get_container("Destinations")
        await container.upsert_item(body=dest)

        parts = []
        if new_name:
            parts.append(f"name to '{new_name}'")
        if new_slug:
            parts.append(f"slug to '{new_slug}'")
            parts.append(
                "Note: existing errand items still reference the old slug. "
                "Moving items is not yet supported."
            )
        changes = ", ".join(parts) if parts else "no changes"
        return f"Renamed destination '{slug}': {changes}."

    async def _destination_remove(self, name: str, slug: str) -> str:
        """Remove a destination, checking for existing errand items first."""
        # Check for existing errand items in this destination
        errands_container = self._manager.get_container("Errands")
        item_count = 0
        async for _item in errands_container.query_items(
            query="SELECT VALUE COUNT(1) FROM c",
            partition_key=slug,
        ):
            item_count = _item

        if item_count > 0:
            return (
                f"'{name}' has {item_count} items. Where should they go? "
                f"(provide a new destination slug)"
            )

        # Find and delete the destination document
        query = "SELECT * FROM c WHERE c.slug = @slug AND c.userId = 'will'"
        parameters = [{"name": "@slug", "value": slug}]
        existing = await self._collect_query(
            "Destinations", query, parameters=parameters
        )
        if not existing:
            return f"Destination with slug '{slug}' not found."

        container = self._manager.get_container("Destinations")
        await container.delete_item(item=existing[0]["id"], partition_key="will")
        return f"Removed destination '{name}' (slug: {slug})."

    # ------------------------------------------------------------------
    # Tool 5: manage_affinity_rule
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def manage_affinity_rule(
        self,
        action: Annotated[
            str, Field(description="Action: 'create', 'update', 'delete'")
        ],
        natural_language: Annotated[
            str,
            Field(
                description=(
                    "Rule in natural language "
                    "(e.g., 'chicken always goes to Agora')"
                )
            ),
        ],
        item_pattern: Annotated[
            str,
            Field(description="Primary item/category pattern (e.g., 'chicken')"),
        ],
        destination_slug: Annotated[
            str,
            Field(description="Target destination slug (e.g., 'agora')"),
        ],
        rule_type: Annotated[
            str,
            Field(description="Type: 'item', 'category', or 'entity'"),
        ],
        exceptions: Annotated[
            list[dict] | None,
            Field(
                description=(
                    "Exceptions: "
                    "[{'pattern': 'fish', 'destinationSlug': 'nicks_fishmarket'}]"
                )
            ),
        ] = None,
        auto_saved: Annotated[
            bool,
            Field(
                description="True if this rule was auto-saved from a HITL routing answer"
            ),
        ] = False,
    ) -> str:
        """Create, update, or delete an affinity routing rule.

        Returns confirmation on success, or conflict notification if an
        existing rule covers the same item pattern.
        """
        action = action.strip().lower()

        if action == "create":
            return await self._rule_create(
                natural_language, item_pattern, destination_slug,
                rule_type, exceptions, auto_saved,
            )
        elif action == "update":
            return await self._rule_update(
                natural_language, item_pattern, destination_slug,
                rule_type, exceptions, auto_saved,
            )
        elif action == "delete":
            return await self._rule_delete(item_pattern)
        else:
            return f"Unknown action '{action}'. Use 'create', 'update', or 'delete'."

    async def _rule_create(
        self,
        natural_language: str,
        item_pattern: str,
        destination_slug: str,
        rule_type: str,
        exceptions: list[dict] | None,
        auto_saved: bool,
    ) -> str:
        """Create a new affinity rule with conflict detection."""
        existing_rules = await self._collect_query(
            "AffinityRules", "SELECT * FROM c WHERE c.userId = 'will'"
        )
        # Check for conflict (case-insensitive itemPattern match)
        for rule in existing_rules:
            if rule.get("itemPattern", "").lower() == item_pattern.lower():
                existing_dest = rule.get("destinationSlug", "unknown")
                return (
                    f"'{item_pattern}' currently routes to '{existing_dest}'. "
                    f"Say 'yes change it' to update, or 'no keep it' to cancel."
                )

        doc = AffinityRuleDocument(
            naturalLanguage=natural_language,
            itemPattern=item_pattern.lower(),
            destinationSlug=destination_slug.lower(),
            ruleType=rule_type,
            exceptions=exceptions or [],
            autoSaved=auto_saved,
        )
        container = self._manager.get_container("AffinityRules")
        await container.create_item(body=doc.model_dump(mode="json"))
        return (
            f"Created rule: '{natural_language}' "
            f"({rule_type}: {item_pattern} -> {destination_slug})."
        )

    async def _rule_update(
        self,
        natural_language: str,
        item_pattern: str,
        destination_slug: str,
        rule_type: str,
        exceptions: list[dict] | None,
        auto_saved: bool,
    ) -> str:
        """Update an existing affinity rule by itemPattern."""
        existing_rules = await self._collect_query(
            "AffinityRules", "SELECT * FROM c WHERE c.userId = 'will'"
        )
        target = None
        for rule in existing_rules:
            if rule.get("itemPattern", "").lower() == item_pattern.lower():
                target = rule
                break

        if not target:
            return f"No rule found for '{item_pattern}'. Use 'create' to add one."

        target["naturalLanguage"] = natural_language
        target["destinationSlug"] = destination_slug.lower()
        target["ruleType"] = rule_type
        target["exceptions"] = exceptions or []
        target["autoSaved"] = auto_saved
        target["updatedAt"] = datetime.now(UTC).isoformat()

        container = self._manager.get_container("AffinityRules")
        await container.upsert_item(body=target)
        return (
            f"Updated rule: '{natural_language}' "
            f"({rule_type}: {item_pattern} -> {destination_slug})."
        )

    async def _rule_delete(self, item_pattern: str) -> str:
        """Delete an affinity rule by itemPattern."""
        existing_rules = await self._collect_query(
            "AffinityRules", "SELECT * FROM c WHERE c.userId = 'will'"
        )
        target = None
        for rule in existing_rules:
            if rule.get("itemPattern", "").lower() == item_pattern.lower():
                target = rule
                break

        if not target:
            return f"No rule found for '{item_pattern}'."

        container = self._manager.get_container("AffinityRules")
        await container.delete_item(item=target["id"], partition_key="will")
        return f"Deleted rule for '{item_pattern}'."

    # ------------------------------------------------------------------
    # Tool 6: query_rules
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def query_rules(
        self,
        query_text: Annotated[
            str,
            Field(
                description=(
                    "What the user asked, e.g., 'where does chicken go?' "
                    "or 'what are my rules?'"
                )
            ),
        ],
    ) -> str:
        """Answer questions about routing rules and destinations.

        Returns formatted information about rules matching the query.
        For 'what are my rules?' returns all rules. For 'where does X go?'
        returns the matching rule.
        """
        rules = await self._collect_query(
            "AffinityRules", "SELECT * FROM c WHERE c.userId = 'will'"
        )
        destinations = await self._collect_query(
            "Destinations", "SELECT * FROM c WHERE c.userId = 'will'"
        )

        # Build destination slug->displayName lookup
        dest_names: dict[str, str] = {
            d.get("slug", ""): d.get("displayName", d.get("slug", ""))
            for d in destinations
        }

        if not rules:
            return (
                "No routing rules defined yet. "
                "You can create one by saying something like "
                "'chicken goes to Jewel' or 'pet food goes to PetSmart'."
            )

        # Check if the query is asking about a specific item
        query_lower = query_text.lower().strip()

        # Try to find a specific item match
        for rule in rules:
            pattern = rule.get("itemPattern", "").lower()
            if pattern and pattern in query_lower:
                dest_slug = rule.get("destinationSlug", "unknown")
                dest_display = dest_names.get(dest_slug, dest_slug)
                nl = rule.get("naturalLanguage", "")
                result = f"Rule: {nl}\n{pattern} -> {dest_display} ({dest_slug})"
                exceptions = rule.get("exceptions", [])
                if exceptions:
                    for exc in exceptions:
                        exc_pattern = exc.get("pattern", "")
                        exc_dest = exc.get("destinationSlug", "")
                        exc_display = dest_names.get(exc_dest, exc_dest)
                        result += f"\n  Exception: {exc_pattern} -> {exc_display}"
                return result

        # No specific match -- return all rules grouped by destination
        by_dest: dict[str, list[dict]] = {}
        for rule in rules:
            dest_slug = rule.get("destinationSlug", "unknown")
            by_dest.setdefault(dest_slug, []).append(rule)

        lines: list[str] = ["All routing rules:"]
        for dest_slug, dest_rules in by_dest.items():
            dest_display = dest_names.get(dest_slug, dest_slug)
            lines.append(f"\n{dest_display} ({dest_slug}):")
            for rule in dest_rules:
                nl = rule.get("naturalLanguage", "")
                rtype = rule.get("ruleType", "item")
                lines.append(f"  - {nl} ({rtype})")

        return "\n".join(lines)
