"""Dry-run tool handlers for Classifier and Admin Agent evaluation.

These classes mirror the production tool interfaces (ClassifierTools, AdminTools)
but capture predictions in memory instead of writing to Cosmos DB.  The Foundry
agent matches tools by JSON schema, so parameter signatures (Annotated types,
Field descriptions) MUST be byte-for-byte identical to the production versions.
"""

from __future__ import annotations

from typing import Annotated

from agent_framework import tool
from pydantic import Field


class EvalClassifierTools:
    """Dry-run replacement for ClassifierTools during eval.

    Captures bucket, confidence, and status predictions without any Cosmos
    writes.  Use ``last_bucket`` / ``last_confidence`` / ``last_status``
    after the agent run to read the prediction.
    """

    def __init__(self) -> None:
        self.last_bucket: str | None = None
        self.last_confidence: float | None = None
        self.last_status: str | None = None

    @tool(approval_mode="never_require")
    async def file_capture(
        self,
        text: Annotated[str, Field(description="The original captured text to file")],
        bucket: Annotated[
            str,
            Field(
                description="Classification bucket: People, Projects, Ideas, or Admin"
            ),
        ],
        confidence: Annotated[
            float,
            Field(description="Confidence score 0.0-1.0 for the chosen bucket"),
        ],
        status: Annotated[
            str,
            Field(
                description=(
                    "Status: 'classified' (confidence >= 0.6), "
                    "'pending' (confidence < 0.6), or 'misunderstood'"
                )
            ),
        ],
        title: Annotated[
            str | None,
            Field(description="Brief title (3-6 words) extracted from the text"),
        ] = None,
    ) -> dict:
        """Capture a classification prediction without writing to Cosmos DB.

        Parameter signature is identical to ClassifierTools.file_capture so
        the Foundry agent's JSON schema matches exactly.
        """
        self.last_bucket = bucket
        self.last_confidence = max(0.0, min(1.0, confidence))
        self.last_status = status
        return {"bucket": bucket, "confidence": confidence, "item_id": "eval-dry-run"}

    def reset(self) -> None:
        """Clear captured state between eval runs."""
        self.last_bucket = None
        self.last_confidence = None
        self.last_status = None


class DryRunAdminTools:
    """Dry-run replacement for AdminTools during eval.

    Captures destination routing decisions and task items in memory instead
    of writing to Cosmos DB.  Use ``captured_destinations``,
    ``captured_items``, and ``captured_tasks`` after the agent run to read
    the predictions.
    """

    def __init__(self, routing_context: str) -> None:
        self._routing_context = routing_context
        self.captured_destinations: list[str] = []
        self.captured_items: list[dict] = []
        self.captured_tasks: list[dict] = []

    @tool(approval_mode="never_require")
    async def add_errand_items(
        self,
        items: Annotated[
            list[dict],
            Field(
                description=(
                    "List of errand items to add. Each dict must have "
                    "'name' (str, lowercase, natural language "
                    "like '2 lbs ground beef') and 'destination' "
                    "(str, the destination slug from routing context). "
                    "Set destination to 'unrouted' if no affinity "
                    "rule matches the item. Optionally include "
                    "'sourceName' (str, recipe title) and "
                    "'sourceUrl' (str, recipe page URL) "
                    "for items extracted from recipes."
                )
            ),
        ],
    ) -> str:
        """Capture errand items and destinations without writing to Cosmos DB.

        Parameter signature is identical to AdminTools.add_errand_items so
        the Foundry agent's JSON schema matches exactly.
        """
        for item in items:
            self.captured_destinations.append(item.get("destination", "unrouted"))
            self.captured_items.append(item)
        return f"[DRY RUN] Would add {len(items)} errand items"

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
        """Capture task items without writing to Cosmos DB.

        Parameter signature is identical to AdminTools.add_task_items so
        the Foundry agent's JSON schema matches exactly.
        """
        self.captured_tasks.extend(tasks)
        return f"[DRY RUN] Would add {len(tasks)} task items"

    @tool(approval_mode="never_require")
    async def get_routing_context(self) -> str:
        """Load all destinations and affinity rules for routing decisions.

        Call this at the start of processing ANY Admin capture. Returns a
        formatted list of available destinations and routing rules so the
        agent can make informed routing decisions.
        """
        return self._routing_context
