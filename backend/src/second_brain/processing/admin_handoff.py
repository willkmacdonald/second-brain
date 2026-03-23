"""Background processing for Admin-classified captures.

Provides process_admin_capture() -- a fire-and-forget coroutine that
calls the Admin Agent non-streaming, routes errand items to destination lists,
and handles the inbox item after processing. Responses that need user attention
are kept on the inbox item for delivery; simple confirmations trigger deletion.
Failed items remain with adminProcessingStatus = 'failed' for retry.
"""

import asyncio
import logging

from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from opentelemetry import trace

from second_brain.db.cosmos import CosmosManager
from second_brain.tools.admin import build_routing_context

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("second_brain.processing")


def _count_tool_invocations(tools: list) -> int:
    """Sum invocation_count across all FunctionTool instances in a tool list.

    Uses duck typing (hasattr) rather than isinstance so that test mocks
    with an invocation_count attribute also work correctly.
    """
    total = 0
    for t in tools:
        count = getattr(t, "invocation_count", None)
        if count is not None:
            total += count
    return total


# Tools that produce user-visible output. Intermediate tools like
# fetch_recipe_url and get_routing_context gather data but don't complete
# the agent's job — calling them alone means the agent stalled.
_OUTPUT_TOOL_NAMES = {
    "add_errand_items",
    "add_task_items",
    "manage_destination",
    "manage_affinity_rule",
    "query_rules",
}


def _count_output_tool_invocations(tools: list) -> int:
    """Count invocations of output-producing tools only.

    fetch_recipe_url and get_routing_context are intermediate tools — calling
    them without following up with add_errand_items or add_task_items means
    the agent didn't complete its work.
    """
    total = 0
    for t in tools:
        name = getattr(t, "name", None)
        count = getattr(t, "invocation_count", None)
        if name in _OUTPUT_TOOL_NAMES and count is not None:
            total += count
    return total


def _response_needs_delivery(response_text: str | None) -> bool:
    """Check if the Admin Agent response contains information the user needs to see.

    Returns True for rule management feedback, conflict confirmations,
    and query answers. Returns False for simple errand/task-add confirmations
    and generic chatty responses like "Is there anything else?".
    """
    if not response_text:
        return False
    text_lower = response_text.lower()

    # Skip generic chatty responses that don't contain actionable info
    skip_patterns = [
        "anything else",
        "let me know if",
        "is there anything",
        "can i help",
    ]
    # If the response is ONLY chatty filler (no real content), skip it
    lines = [ln.strip() for ln in text_lower.split("\n") if ln.strip()]
    if all(
        any(skip in line for skip in skip_patterns)
        for line in lines
    ):
        return False

    # Only deliver responses about rule/destination management or questions
    # that require user action
    delivery_indicators = [
        "conflict",
        "currently goes to",
        "currently routes to",
        "where should",
        "which destination",
        "affinity rule",
        "routing rule",
        "goes to",
        "routed to",
        "renamed",
        "removed destination",
        "no matching rule",
        "items added",
        "no recipe found",
        "error fetching",
    ]
    return any(indicator in text_lower for indicator in delivery_indicators)


async def _mark_inbox_failed(
    inbox_container,
    inbox_item_id: str,
    span,
) -> None:
    """Set adminProcessingStatus='failed' on an inbox item (best-effort)."""
    try:
        doc = await inbox_container.read_item(item=inbox_item_id, partition_key="will")
        doc["adminProcessingStatus"] = "failed"
        await inbox_container.upsert_item(body=doc)
    except Exception as update_exc:
        if span:
            span.record_exception(update_exc)
        logger.error(
            "Failed to update inbox status to 'failed' for %s: %s",
            inbox_item_id,
            update_exc,
        )


async def process_admin_capture(
    admin_client: AzureAIAgentClient,
    admin_tools: list,
    cosmos_manager: CosmosManager,
    inbox_item_id: str,
    raw_text: str,
    capture_trace_id: str = "",
) -> None:
    """Process an Admin-classified capture in the background.

    Calls the Admin Agent (non-streaming) with routing context (destinations
    and affinity rules) prepended to the user's capture text. Routes errand
    items to destinations via tools. After processing:

    - If the response needs user attention (rule queries, conflicts, etc.),
      the inbox item is kept with status "completed" and the response stored.
    - If the response is a simple confirmation, the inbox item is deleted.
    - If the agent didn't call any tools, the item is marked as "failed".

    This function is designed to be called via asyncio.create_task() --
    it never raises (all exceptions are caught and logged).

    Args:
        admin_client: AzureAIAgentClient configured for the Admin Agent.
        admin_tools: List of tool functions
            (e.g., [admin_tools.add_errand_items]).
        cosmos_manager: CosmosManager for inbox status updates.
        inbox_item_id: The Cosmos inbox document ID to update after processing.
        raw_text: The user's original capture text to send to the Admin Agent.
        capture_trace_id: Trace ID from the originating capture for end-to-end filtering.
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
            # Resolve trace ID: prefer inbox doc field, fall back to parameter
            trace_id = doc.get("captureTraceId", capture_trace_id or "unknown")
            span.set_attribute("capture.trace_id", trace_id)
            log_extra: dict = {
                "capture_trace_id": trace_id,
                "component": "admin_agent",
            }
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
            # Build routing context (destinations + rules)
            try:
                routing_context = await build_routing_context(cosmos_manager)
                enriched_text = (
                    f"{routing_context}\n\n---\nUser capture: {raw_text}"
                )
            except Exception as ctx_exc:
                logger.warning(
                    "Failed to build routing context for %s: %s. "
                    "Falling back to raw text.",
                    inbox_item_id,
                    ctx_exc,
                    extra=log_extra,
                )
                enriched_text = raw_text

            messages = [Message(role="user", text=enriched_text)]
            options = ChatOptions(tools=admin_tools)

            # Snapshot tool invocation counts before calling the agent
            pre_count = _count_tool_invocations(admin_tools)
            pre_output_count = _count_output_tool_invocations(admin_tools)

            async with asyncio.timeout(60):
                response = await admin_client.get_response(
                    messages=messages, options=options
                )

            # Check whether the agent produced output (errands or tasks)
            post_count = _count_tool_invocations(admin_tools)
            post_output_count = _count_output_tool_invocations(admin_tools)
            any_tool_called = post_count > pre_count
            output_tool_called = post_output_count > pre_output_count

            span.set_attribute("admin.tool_invoked", any_tool_called)
            span.set_attribute("admin.output_tool_invoked", output_tool_called)

            if not any_tool_called:
                # Agent responded without calling any tools at all.
                logger.warning(
                    "Admin Agent did not call any tool for inbox item %s "
                    "(text: %.80s). Marking as failed.",
                    inbox_item_id,
                    raw_text,
                    extra=log_extra,
                )
                span.set_attribute("admin.outcome", "no_tool_call")
                await _mark_inbox_failed(inbox_container, inbox_item_id, span)
                return

            if not output_tool_called:
                # Agent called intermediate tools (e.g. fetch_recipe_url)
                # but never followed up with add_errand_items/add_task_items.
                # Retry once with the agent's text response as context.
                response_text = response.text if response.text else ""
                logger.warning(
                    "Admin Agent called intermediate tools but not "
                    "add_errand_items/add_task_items for inbox item %s. "
                    "Retrying with nudge.",
                    inbox_item_id,
                    extra=log_extra,
                )
                span.set_attribute("admin.retry", True)

                retry_prompt = (
                    f"{enriched_text}\n\n"
                    f"---\n"
                    f"IMPORTANT: You already gathered data above but "
                    f"did not complete the user's request. You MUST "
                    f"call the appropriate tool (add_errand_items, "
                    f"add_task_items, manage_destination, etc.) to "
                    f"finish. Do NOT respond with text -- call the "
                    f"tool.\n\n"
                    f"Your previous response was:\n{response_text}"
                )
                retry_messages = [Message(role="user", text=retry_prompt)]

                pre_output_count_2 = _count_output_tool_invocations(
                    admin_tools
                )

                async with asyncio.timeout(60):
                    response = await admin_client.get_response(
                        messages=retry_messages, options=options
                    )

                post_output_count_2 = _count_output_tool_invocations(
                    admin_tools
                )
                output_tool_called = post_output_count_2 > pre_output_count_2

                if not output_tool_called:
                    logger.error(
                        "Admin Agent retry also failed to call output "
                        "tools for inbox item %s. Marking as failed.",
                        inbox_item_id,
                        extra=log_extra,
                    )
                    span.set_attribute("admin.outcome", "no_output_tool")
                    await _mark_inbox_failed(
                        inbox_container, inbox_item_id, span
                    )
                    return

                span.set_attribute("admin.outcome", "retry_succeeded")

            # Tool was called -- decide whether to keep or delete inbox item
            response_text = response.text if response.text else None

            if _response_needs_delivery(response_text):
                # Response contains info the user needs to see --
                # keep the inbox item with response attached
                try:
                    doc = await inbox_container.read_item(
                        item=inbox_item_id, partition_key="will"
                    )
                    doc["adminProcessingStatus"] = "completed"
                    doc["adminAgentResponse"] = response_text
                    await inbox_container.upsert_item(body=doc)
                    logger.info(
                        "Stored admin response for delivery on inbox "
                        "item %s",
                        inbox_item_id,
                        extra=log_extra,
                    )
                except Exception as store_exc:
                    logger.warning(
                        "Failed to store admin response for %s: %s",
                        inbox_item_id,
                        store_exc,
                        extra=log_extra,
                    )
                span.set_attribute("admin.outcome", "response_stored")
            else:
                # Simple confirmation -- delete the inbox item
                try:
                    await inbox_container.delete_item(
                        item=inbox_item_id, partition_key="will"
                    )
                    logger.info(
                        "Deleted processed inbox item %s",
                        inbox_item_id,
                        extra=log_extra,
                    )
                except CosmosResourceNotFoundError:
                    # User may have swipe-deleted while processing
                    logger.info(
                        "Inbox item %s already deleted "
                        "(user may have removed it)",
                        inbox_item_id,
                        extra=log_extra,
                    )
                except Exception as del_exc:
                    # Non-fatal: errand items are the durable output
                    logger.warning(
                        "Failed to delete processed inbox item %s: %s",
                        inbox_item_id,
                        del_exc,
                        extra=log_extra,
                    )
                span.set_attribute("admin.outcome", "processed")

            logger.info(
                "Admin Agent processed inbox item %s: %s",
                inbox_item_id,
                response.text[:100] if response.text else "(no text)",
                extra=log_extra,
            )

        except Exception as exc:
            span.record_exception(exc)
            span.set_attribute("admin.outcome", "failed")
            logger.error(
                "Admin Agent failed for inbox item %s: %s",
                inbox_item_id,
                exc,
                exc_info=True,
                extra=log_extra,
            )

            # Update inbox item status to failed
            await _mark_inbox_failed(inbox_container, inbox_item_id, span)


async def process_admin_captures_batch(
    admin_client: AzureAIAgentClient,
    admin_tools: list,
    cosmos_manager: CosmosManager,
    admin_items: list[dict],
    capture_trace_id: str = "",
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
        capture_trace_id: Trace ID from the originating capture.
    """
    with tracer.start_as_current_span("admin_agent_batch_process") as span:
        span.set_attribute("admin.batch_size", len(admin_items))
        span.set_attribute("capture.trace_id", capture_trace_id)
        for item in admin_items:
            await process_admin_capture(
                admin_client=admin_client,
                admin_tools=admin_tools,
                cosmos_manager=cosmos_manager,
                inbox_item_id=item["inbox_item_id"],
                raw_text=item["raw_text"],
                capture_trace_id=capture_trace_id,
            )
