"""Background processing for Admin-classified captures.

Provides process_admin_capture() -- a fire-and-forget coroutine that
calls the Admin Agent non-streaming, routes errand items to destination lists,
and handles the inbox item after processing. Responses that need user attention
are kept on the inbox item for delivery; simple confirmations trigger deletion.
Failed items remain with adminProcessingStatus = 'failed' for retry.

Phase 24 task group 23.2 (GA migration):
- Uses GA Agent.run() in place of the legacy RC client's get_response().
- Tool detection is post-hoc: walks response.messages for role='tool'
  entries per FOUNDRY-PROBE-FINDINGS.md probe 2 (tool_call_extraction).
- Custom admin_agent_process / admin_agent_batch_process spans removed
  (F-16). Capture-trace correlation rides on the framework's
  invoke_agent span via CaptureTraceAgentMiddleware (24-03).
- admin.* observability attributes ride structured log extras instead
  of a custom span.
"""

import asyncio
import logging
import time

from agent_framework import Agent, ChatOptions
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from second_brain.config import get_settings
from second_brain.db.cosmos import CosmosManager
from second_brain.spine.agent_emitter import emit_agent_workload
from second_brain.spine.cosmos_request_id import trace_headers
from second_brain.spine.storage import SpineRepository
from second_brain.tools.admin import admin_inbox_item_id_var, build_routing_context

logger = logging.getLogger(__name__)


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


def _output_tool_called(response) -> tuple[bool, set[str]]:
    """Inspect response.messages for tool calls.

    Returns (output_tool_fired, all_tools_called).

    Phase 24 UAT bug fix (2026-05-17): Plan 24-11's original implementation
    walked role='tool' messages looking for `content.name`, but on the GA
    framework the `name` field is populated on the `function_call` content
    (in role='assistant' messages), NOT on the `function_result` content
    (in role='tool' messages). The probe fixture didn't reveal this, so
    detection silently returned empty for every successful capture →
    admin_handoff marked the inbox as failed → next /api/errands poll
    re-fired the agent → tool fired again → duplicate Errand/Task rows
    accumulated.

    Correct shape per local probe (2026-05-17):
      message[i] role='assistant' contents=[function_call(name='X', call_id='c1', arguments=...)]
      message[i+1] role='tool' contents=[function_result(name=None, call_id='c1', result=...)]

    We look at the `function_call` blocks (any role) for tool detection.
    If the function_result for the matching call_id carries an `exception`,
    the call failed at validation — don't count it as fired.
    """
    tools_called: set[str] = set()
    # First pass: collect function_call (name, call_id) pairs
    call_id_to_name: dict[str, str] = {}
    for msg in getattr(response, "messages", None) or []:
        for content in getattr(msg, "contents", None) or []:
            if getattr(content, "type", None) != "function_call":
                continue
            name = getattr(content, "name", None) or getattr(
                content, "function_name", None
            )
            call_id = getattr(content, "call_id", None)
            if name and call_id:
                call_id_to_name[call_id] = str(name)
    # Second pass: only count calls whose result didn't raise. A
    # validation-error result (e.g., bad args) sets `exception` on the
    # function_result content. Those count as attempted but not actually
    # executed — admin_handoff's retry path should still fire.
    failed_call_ids: set[str] = set()
    for msg in getattr(response, "messages", None) or []:
        if getattr(msg, "role", None) != "tool":
            continue
        for content in getattr(msg, "contents", None) or []:
            if getattr(content, "type", None) != "function_result":
                continue
            call_id = getattr(content, "call_id", None)
            if call_id and getattr(content, "exception", None):
                failed_call_ids.add(call_id)
    for cid, name in call_id_to_name.items():
        if cid not in failed_call_ids:
            tools_called.add(name)
    return bool(tools_called & _OUTPUT_TOOL_NAMES), tools_called


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
    if all(any(skip in line for skip in skip_patterns) for line in lines):
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
    capture_trace_id: str = "",
) -> None:
    """Set adminProcessingStatus='failed' on an inbox item (best-effort).

    The `span` parameter is accepted for back-compat with the pre-Phase-24
    call shape but is now always None — the custom admin_agent_process
    span was deleted (F-16). The framework's invoke_agent span (auto-
    emitted by GA SDK + tagged by CaptureTraceAgentMiddleware) is the
    canonical correlation surface.
    """
    th = trace_headers(capture_trace_id or None)
    try:
        doc = await inbox_container.read_item(
            item=inbox_item_id, partition_key="will", **th
        )
        doc["adminProcessingStatus"] = "failed"
        await inbox_container.upsert_item(body=doc, **th)
    except Exception as update_exc:
        if span:
            span.record_exception(update_exc)
        logger.error(
            "Failed to update inbox status to 'failed' for %s: %s",
            inbox_item_id,
            update_exc,
        )


async def process_admin_capture(
    admin_agent: Agent,
    cosmos_manager: CosmosManager,
    inbox_item_id: str,
    raw_text: str,
    capture_trace_id: str = "",
    spine_repo: SpineRepository | None = None,
) -> None:
    """Process an Admin-classified capture in the background.

    Calls the Admin Agent (non-streaming) with routing context (destinations
    and affinity rules) prepended to the user's capture text. Routes errand
    items to destinations via tools that are pre-registered on the Agent
    at lifespan construction time (D-05). After processing:

    - If the response needs user attention (rule queries, conflicts, etc.),
      the inbox item is kept with status "completed" and the response stored.
    - If the response is a simple confirmation, the inbox item is deleted.
    - If the agent didn't call any tools, the item is marked as "failed".

    This function is designed to be called via asyncio.create_task() --
    it never raises (all exceptions are caught and logged).

    Args:
        admin_agent: GA Agent configured for the Admin Agent (tools and
            middleware pre-registered at lifespan construction).
        cosmos_manager: CosmosManager for inbox status updates.
        inbox_item_id: The Cosmos inbox document ID to update after processing.
        raw_text: The user's original capture text to send to the Admin Agent.
        capture_trace_id: Trace ID from the originating capture.
        spine_repo: Optional SpineRepository for workload emission at boundary.
    """
    from second_brain.tools.classification import capture_trace_id_var

    if capture_trace_id:
        capture_trace_id_var.set(capture_trace_id)
    # Phase 25: set inbox_item_id ContextVar so add_errand_items / add_task_items
    # (Plan 04 read sites) can stamp sourceInboxItemId backlinks on every
    # Errand/Task doc created during this admin processing context.
    admin_inbox_item_id_var.set(inbox_item_id)

    # Spine workload tracking
    _spine_start = time.perf_counter()
    _spine_outcome = "success"
    _spine_error_class: str | None = None

    # Defensive initialization: ensure variables are bound even if the
    # first try block raises before assignment.
    inbox_container = None
    log_extra: dict = {
        "component": "admin_agent",
        "inbox_item_id": inbox_item_id,
        "raw_text_length": len(raw_text),
    }

    # Set status to pending immediately
    th = trace_headers(capture_trace_id or None)
    try:
        inbox_container = cosmos_manager.get_container("Inbox")
        doc = await inbox_container.read_item(
            item=inbox_item_id, partition_key="will", **th
        )
        # Resolve trace ID: prefer inbox doc field, fall back to parameter
        trace_id = doc.get("captureTraceId", capture_trace_id or "unknown")
        log_extra = {
            "capture_trace_id": trace_id,
            "component": "admin_agent",
            "inbox_item_id": inbox_item_id,
            "raw_text_length": len(raw_text),
        }
        doc["adminProcessingStatus"] = "pending"
        await inbox_container.upsert_item(body=doc, **th)
    except Exception as exc:
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
            enriched_text = f"{routing_context}\n\n---\nUser capture: {raw_text}"
        except Exception as ctx_exc:
            logger.warning(
                "Failed to build routing context for %s: %s. Falling back to raw text.",
                inbox_item_id,
                ctx_exc,
                extra=log_extra,
            )
            enriched_text = raw_text

        # D-07 EXPLICIT JUSTIFICATION (CONTEXT D-11):
        # 1. Framework primitive considered: tool_choice='required' (forces
        #    SOME tool call).
        # 2. What custom code provides: pin which SUBSET of tools
        #    (add_errand_items OR add_task_items) the model must call.
        #    Framework primitive cannot pin a subset.
        # 3. Why not middleware/context provider/tool/configuration:
        #    provider-dict {"mode":"required",...} schema is undocumented
        #    (probe 3 confirmed); spiking rejected as time-risky in
        #    CONTEXT D-10.
        # 4. Permanent or temporary: temporary bridge. Deletion trigger:
        #    when 'mode' dict schema is documented OR Foundry adds
        #    tool_choice subset pinning.
        async with asyncio.timeout(60):
            response = await admin_agent.run(
                enriched_text,
                options=ChatOptions(tool_choice="required"),
            )

        # Post-hoc tool detection per FOUNDRY-PROBE-FINDINGS.md probe 2:
        # walk response.messages for role='tool' entries instead of
        # FunctionTool invocation_count snapshots (GA removes those).
        output_fired, tools_called = _output_tool_called(response)
        any_tool_fired = bool(tools_called)

        if not any_tool_fired:
            # Agent responded without calling any tools at all.
            logger.warning(
                "Admin Agent did not call any tool for inbox item %s "
                "(text: %.80s). Marking as failed. outcome=no_tool_call",
                inbox_item_id,
                raw_text,
                extra=log_extra,
            )
            await _mark_inbox_failed(
                inbox_container, inbox_item_id, None, capture_trace_id
            )
            return

        if not output_fired:
            # Agent called intermediate tools (e.g. fetch_recipe_url)
            # but never followed up with add_errand_items/add_task_items.
            # Retry once with the agent's text response as context.
            response_text = response.text if response.text else ""
            logger.warning(
                "Admin Agent called intermediate tools but not "
                "add_errand_items/add_task_items for inbox item %s. "
                "Retrying with nudge. tools_called=%s",
                inbox_item_id,
                tools_called,
                extra=log_extra,
            )

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

            # D-09 bounded retry: exactly one retry, no loop. Same D-07
            # justification as the initial call above — tool_choice="required"
            # forces SOME tool but cannot pin to the output-tool subset.
            async with asyncio.timeout(60):
                response = await admin_agent.run(
                    retry_prompt,
                    options=ChatOptions(tool_choice="required"),
                )

            retry_output_fired, retry_tools_called = _output_tool_called(response)

            if not retry_output_fired:
                logger.error(
                    "Admin Agent retry also failed to call output "
                    "tools for inbox item %s. Marking as failed. "
                    "outcome=no_output_tool retry_tools_called=%s",
                    inbox_item_id,
                    retry_tools_called,
                    extra=log_extra,
                )
                await _mark_inbox_failed(
                    inbox_container, inbox_item_id, None, capture_trace_id
                )
                return

            logger.info(
                "Admin Agent retry succeeded for inbox item %s. "
                "outcome=retry_succeeded retry_tools_called=%s",
                inbox_item_id,
                retry_tools_called,
                extra=log_extra,
            )

        # Tool was called -- decide whether to keep or delete inbox item
        response_text = response.text if response.text else None

        if _response_needs_delivery(response_text):
            # Response contains info the user needs to see --
            # keep the inbox item with response attached
            try:
                doc = await inbox_container.read_item(
                    item=inbox_item_id, partition_key="will", **th
                )
                doc["adminProcessingStatus"] = "completed"
                doc["adminAgentResponse"] = response_text
                await inbox_container.upsert_item(body=doc, **th)
                logger.info(
                    "Stored admin response for delivery on inbox item %s. "
                    "outcome=response_stored",
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
        else:
            # Simple confirmation -- soft-delete by filing the inbox item.
            # Setting status="filed" + adminProcessingStatus="completed" + ttl
            # in ONE upsert is critical: the api/errands.py:174 unprocessed
            # query gates on adminProcessingStatus, so partial writes would
            # re-fire the agent on a filed doc (Landmine #4). Container TTL
            # must already be enabled (defaultTtl=-1) for the per-doc ttl to
            # take effect (Plan 02 one-time infra step).
            try:
                settings = get_settings()
                ttl_seconds = settings.inbox_filed_retention_days * 86400
                doc = await inbox_container.read_item(
                    item=inbox_item_id, partition_key="will", **th
                )
                doc["status"] = "filed"
                doc["adminProcessingStatus"] = "completed"
                doc["ttl"] = ttl_seconds
                await inbox_container.upsert_item(body=doc, **th)
                logger.info(
                    "Filed processed inbox item %s. outcome=filed",
                    inbox_item_id,
                    extra=log_extra,
                )
            except CosmosResourceNotFoundError:
                # User may have swipe-deleted while processing
                logger.info(
                    "Inbox item %s already deleted (user may have removed it)",
                    inbox_item_id,
                    extra=log_extra,
                )
            except Exception as file_exc:
                # Non-fatal: errand items are the durable output
                logger.warning(
                    "Failed to file processed inbox item %s: %s",
                    inbox_item_id,
                    file_exc,
                    extra=log_extra,
                )

        logger.info(
            "Admin Agent processed inbox item %s: %s",
            inbox_item_id,
            response.text[:100] if response.text else "(no text)",
            extra=log_extra,
        )

    except Exception as exc:
        _spine_outcome = "failure"
        _spine_error_class = type(exc).__name__
        logger.error(
            "Admin Agent failed for inbox item %s: %s. outcome=failed",
            inbox_item_id,
            exc,
            exc_info=True,
            extra=log_extra,
        )

        # Update inbox item status to failed (only if container was resolved)
        if inbox_container is not None:
            await _mark_inbox_failed(
                inbox_container, inbox_item_id, None, capture_trace_id
            )
    finally:
        if spine_repo:
            _duration = int((time.perf_counter() - _spine_start) * 1000)
            await emit_agent_workload(
                repo=spine_repo,
                segment_id="admin",
                operation="process_capture",
                outcome=_spine_outcome,
                duration_ms=_duration,
                capture_trace_id=capture_trace_id or None,
                run_id=None,
                thread_id=None,
                error_class=_spine_error_class,
            )


async def process_admin_captures_batch(
    admin_agent: Agent,
    cosmos_manager: CosmosManager,
    admin_items: list[dict],
    capture_trace_id: str = "",
    spine_repo: SpineRepository | None = None,
) -> None:
    """Process multiple Admin-classified items from a multi-split capture.

    Calls process_admin_capture for each item sequentially within a single
    background task. Each item is independent -- one failure does not block others.

    This function is designed to be called via asyncio.create_task() --
    it never raises (all exceptions are caught internally by process_admin_capture).

    Args:
        admin_agent: GA Agent configured for the Admin Agent (tools pre-registered).
        cosmos_manager: CosmosManager for inbox status updates.
        admin_items: List of dicts with "inbox_item_id" and "raw_text" keys.
        capture_trace_id: Trace ID from the originating capture.
        spine_repo: Optional SpineRepository for workload emission.
    """
    logger.info(
        "Admin Agent batch processing %d item(s) capture_trace_id=%s",
        len(admin_items),
        capture_trace_id or "(none)",
        extra={
            "component": "admin_agent",
            "batch_size": len(admin_items),
            "capture_trace_id": capture_trace_id or "",
        },
    )
    for item in admin_items:
        item_trace_id = item.get("capture_trace_id", "") or capture_trace_id
        await process_admin_capture(
            admin_agent=admin_agent,
            cosmos_manager=cosmos_manager,
            inbox_item_id=item["inbox_item_id"],
            raw_text=item["raw_text"],
            capture_trace_id=item_trace_id,
            spine_repo=spine_repo,
        )
