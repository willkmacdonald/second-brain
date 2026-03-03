"""Background processing for Admin-classified captures.

Provides process_admin_capture() -- a fire-and-forget coroutine that
calls the Admin Agent non-streaming, routes shopping items to store lists,
and deletes the inbox item after successful processing.
"""

import asyncio
import logging

from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from opentelemetry import trace

from second_brain.db.cosmos import CosmosManager

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("second_brain.processing")


async def process_admin_capture(
    admin_client: AzureAIAgentClient,
    admin_tools: list,
    cosmos_manager: CosmosManager,
    inbox_item_id: str,
    raw_text: str,
) -> None:
    """Process an Admin-classified capture in the background.

    Calls the Admin Agent (non-streaming) to parse items and route
    to shopping lists via add_shopping_list_items. On success, deletes
    the inbox item (it is a transient routing artifact). On failure,
    sets adminProcessingStatus to 'failed' so the item remains visible.

    This function is designed to be called via asyncio.create_task() --
    it never raises (all exceptions are caught and logged).

    Args:
        admin_client: AzureAIAgentClient configured for the Admin Agent.
        admin_tools: List of tool functions (e.g., [admin_tools.add_shopping_list_items]).
        cosmos_manager: CosmosManager for inbox status updates.
        inbox_item_id: The Cosmos inbox document ID to update after processing.
        raw_text: The user's original capture text to send to the Admin Agent.
    """
    with tracer.start_as_current_span("admin_agent_process") as span:
        span.set_attribute("admin.inbox_item_id", inbox_item_id)
        span.set_attribute("admin.raw_text_length", len(raw_text))

        # Set status to pending immediately
        try:
            inbox_container = cosmos_manager.get_container("Inbox")
            doc = await inbox_container.read_item(
                item=inbox_item_id, partition_key="will"
            )
            doc["adminProcessingStatus"] = "pending"
            await inbox_container.upsert_item(body=doc)
        except Exception as exc:
            span.record_exception(exc)
            logger.error(
                "Failed to set pending status for inbox item %s: %s",
                inbox_item_id,
                exc,
                exc_info=True,
            )
            return  # Cannot proceed without the inbox item

        try:
            messages = [Message(role="user", text=raw_text)]
            options = ChatOptions(tools=admin_tools)

            async with asyncio.timeout(60):
                response = await admin_client.get_response(
                    messages=messages, options=options
                )

            # Delete the inbox item -- shopping list items are the durable output
            try:
                await inbox_container.delete_item(
                    item=inbox_item_id, partition_key="will"
                )
            except CosmosResourceNotFoundError:
                # User may have swipe-deleted the item while we were processing
                pass
            except Exception as del_exc:
                # Non-fatal: shopping list items already written successfully
                logger.warning(
                    "Failed to delete processed inbox item %s: %s",
                    inbox_item_id,
                    del_exc,
                )

            span.set_attribute("admin.outcome", "processed")
            logger.info(
                "Admin Agent processed inbox item %s (deleted): %s",
                inbox_item_id,
                response.text[:100] if response.text else "(no text)",
            )

        except Exception as exc:
            span.record_exception(exc)
            span.set_attribute("admin.outcome", "failed")
            logger.error(
                "Admin Agent failed for inbox item %s: %s",
                inbox_item_id,
                exc,
                exc_info=True,
            )

            # Update inbox item status to failed
            try:
                doc = await inbox_container.read_item(
                    item=inbox_item_id, partition_key="will"
                )
                doc["adminProcessingStatus"] = "failed"
                await inbox_container.upsert_item(body=doc)
            except Exception as update_exc:
                logger.error(
                    "Failed to update inbox status to 'failed' for %s: %s",
                    inbox_item_id,
                    update_exc,
                )


async def process_admin_captures_batch(
    admin_client: AzureAIAgentClient,
    admin_tools: list,
    cosmos_manager: CosmosManager,
    admin_items: list[dict],
) -> None:
    """Process multiple Admin-classified items from a multi-split capture.

    Calls process_admin_capture for each item sequentially within a single
    background task. Each item is independent -- one failure does not block others.

    This function is designed to be called via asyncio.create_task() --
    it never raises (all exceptions are caught internally by process_admin_capture).

    Args:
        admin_client: AzureAIAgentClient configured for the Admin Agent.
        admin_tools: List of tool functions for the Admin Agent.
        cosmos_manager: CosmosManager for inbox status updates.
        admin_items: List of dicts with "inbox_item_id" and "raw_text" keys.
    """
    with tracer.start_as_current_span("admin_agent_batch_process") as span:
        span.set_attribute("admin.batch_size", len(admin_items))
        for item in admin_items:
            await process_admin_capture(
                admin_client=admin_client,
                admin_tools=admin_tools,
                cosmos_manager=cosmos_manager,
                inbox_item_id=item["inbox_item_id"],
                raw_text=item["raw_text"],
            )
