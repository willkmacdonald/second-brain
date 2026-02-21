"""Agent Framework @tool functions for Cosmos DB CRUD operations.

Uses the class-based tool pattern to bind Cosmos container references
without module-level globals. CosmosCrudTools manages stateful references
to the CosmosManager (justified per CLAUDE.md -- not a single-method class
or namespace).
"""

import json
import logging
from typing import Annotated

from agent_framework import tool

from second_brain.db.cosmos import CONTAINER_NAMES, CosmosManager
from second_brain.models.documents import CONTAINER_MODELS

logger = logging.getLogger(__name__)


class CosmosCrudTools:
    """CRUD tool functions bound to a CosmosManager instance.

    Usage:
        crud = CosmosCrudTools(cosmos_manager)
        agent = chat_client.as_agent(
            tools=[crud.create_document, crud.read_document, crud.list_documents],
        )
    """

    def __init__(self, cosmos_manager: CosmosManager) -> None:
        """Store the CosmosManager reference for container access."""
        self._manager = cosmos_manager

    @tool
    async def create_document(
        self,
        container_name: Annotated[
            str, "Target container: Inbox, People, Projects, Ideas, or Admin"
        ],
        raw_text: Annotated[str, "The raw captured text"],
        title: Annotated[str, "Title or name for the record"] = "",
    ) -> str:
        """Create a document in the specified Cosmos DB container."""
        if container_name not in CONTAINER_NAMES:
            valid = ", ".join(CONTAINER_NAMES)
            return f"Error: Unknown container '{container_name}'. Valid: {valid}"

        try:
            model_class = CONTAINER_MODELS[container_name]

            # Build kwargs based on which model we are creating
            kwargs: dict = {"rawText": raw_text}

            # Add title/name fields for models that require them
            if container_name == "People":
                kwargs["name"] = title or "Unnamed"
            elif container_name in ("Projects", "Ideas", "Admin"):
                kwargs["title"] = title or "Untitled"

            doc = model_class(**kwargs)
            doc_dict = doc.model_dump(mode="json")

            container = self._manager.get_container(container_name)
            result = await container.create_item(body=doc_dict)

            logger.info("Created document %s in %s", result["id"], container_name)
            return (
                f"Created document {result['id']} in {container_name}: {raw_text[:80]}"
            )

        except Exception as exc:
            logger.error("Failed to create document in %s: %s", container_name, exc)
            return f"Error creating document in {container_name}: {exc}"

    @tool
    async def read_document(
        self,
        container_name: Annotated[str, "Container name"],
        document_id: Annotated[str, "Document ID to read"],
    ) -> str:
        """Read a single document by ID from the specified container."""
        if container_name not in CONTAINER_NAMES:
            valid = ", ".join(CONTAINER_NAMES)
            return f"Error: Unknown container '{container_name}'. Valid: {valid}"

        try:
            container = self._manager.get_container(container_name)
            item = await container.read_item(item=document_id, partition_key="will")
            return json.dumps(item, default=str)

        except Exception as exc:
            logger.error(
                "Failed to read document %s from %s: %s",
                document_id,
                container_name,
                exc,
            )
            return f"Error reading document {document_id} from {container_name}: {exc}"

    @tool
    async def list_documents(
        self,
        container_name: Annotated[str, "Container name"],
        max_items: Annotated[int, "Maximum items to return"] = 10,
    ) -> str:
        """List documents from the specified container."""
        if container_name not in CONTAINER_NAMES:
            valid = ", ".join(CONTAINER_NAMES)
            return f"Error: Unknown container '{container_name}'. Valid: {valid}"

        try:
            container = self._manager.get_container(container_name)
            query = "SELECT TOP @max_items * FROM c WHERE c.userId = @userId"
            parameters: list[dict[str, str | int]] = [
                {"name": "@max_items", "value": max_items},
                {"name": "@userId", "value": "will"},
            ]

            items: list[dict] = []
            async for item in container.query_items(
                query=query,
                parameters=parameters,
                partition_key="will",
            ):
                items.append(item)

            return json.dumps(items, default=str)

        except Exception as exc:
            logger.error("Failed to list documents from %s: %s", container_name, exc)
            return f"Error listing documents from {container_name}: {exc}"
