"""FoundrySSEAdapter -- GA streaming adapter for Classifier captures.

Iterates ``AgentResponseUpdate`` objects from ``agent.run(messages, stream=True)``,
detects tool outcomes via ``Content`` inspection, and yields SSE-formatted
strings matching the AG-UI protocol the mobile app expects.

Chain-of-thought reasoning text is suppressed from the SSE stream and
logged to Application Insights for analysis and instruction tuning.

P0-1 OUTCOME (2026-05-10, fixture
``backend/tests/fixtures/foundry-probe/session_rehydration_fresh_process.json``):
cross-process session-handle rehydration via ``session_id`` alone FAILS on
GA Foundry SDK 1.3.0. Operator locked **Option A**: stateless agent invocation
with explicit conversation context. The caller passes the inbox doc; the
adapter resolves the persisted conversation history via
``resolve_inbox_conversation_history()``, constructs an explicit
``Message`` list (history + new user turn), calls ``agent.run(...)``, then
persists the updated history back to the inbox doc after the stream
completes.

D-04 forced-tool failure mode: when ``tool_choice='required'`` cannot be
satisfied (the framework raises before ``file_capture`` runs), the adapter
yields an ``ERROR`` SSE event with ``sub_code='forced_tool_failure'`` so
monitoring/dashboards can distinguish this from generic errors.

F-14 custom-span deletion: the previous ``capture_text`` / ``capture_voice``
/ ``capture_follow_up`` custom OTel spans are gone. The capture.*
attributes that lived on them now ride on structured ``logger.info(...,
extra=log_extra)`` dicts. The framework ``invoke_agent`` span (auto-emitted
by the SDK + tagged at source by ``CaptureTraceAgentMiddleware`` from
24-03) remains the canonical span for correlation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator, Mapping

from agent_framework import Agent, ChatOptions, Message

from second_brain.cosmos.inbox_conversation_history import (
    ConversationTurn,
    resolve_inbox_conversation_history,
)
from second_brain.spine.cosmos_request_id import trace_headers
from second_brain.streaming.sse import (
    classified_event,
    complete_event,
    encode_sse,
    error_event,
    low_confidence_event,
    misunderstood_event,
    step_end_event,
    step_start_event,
    unresolved_event,
)
from second_brain.tools.classification import capture_trace_id_var

logger = logging.getLogger(__name__)
reasoning_logger = logging.getLogger("second_brain.streaming.reasoning")


def _parse_args(raw: object) -> dict:
    """Parse function call arguments defensively (str or dict/Mapping)."""
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _parse_result(raw: object) -> dict | None:
    """Parse function result defensively (str or dict/Mapping)."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
    if isinstance(raw, Mapping):
        return dict(raw)
    return None


def _emit_result_event(
    detected_tool_args: dict,
    tool_result: dict | None,
    thread_id: str,
) -> dict:
    """Determine and return the appropriate result event dict.

    P0-1 OUTCOME: no foundry conversation id parameter; conversation
    continuity now rides on the Inbox doc's ``conversationHistory`` field
    rather than on a server-side session handle.
    """
    status = detected_tool_args.get("status")

    # Prefer tool_result values, fall back to detected_tool_args
    result_src = tool_result or detected_tool_args
    item_id = result_src.get("item_id", "")
    bucket = result_src.get("bucket", detected_tool_args.get("bucket", ""))
    confidence = result_src.get("confidence", detected_tool_args.get("confidence", 0.0))

    if status == "misunderstood":
        question_text = detected_tool_args.get("title", "Could you clarify?")
        return misunderstood_event(thread_id, item_id, question_text)

    if status == "classified":
        return classified_event(item_id, bucket, confidence)

    if status == "pending":
        return low_confidence_event(item_id, bucket, confidence)

    # No recognized status -- unresolved fallback
    return unresolved_event(item_id)


def _forced_tool_failure_event() -> dict:
    """Construct an ERROR SSE event with the ``forced_tool_failure`` sub_code.

    D-04: emitted when the agent run fails (e.g. ``tool_choice='required'``
    cannot be satisfied, the framework raises before ``file_capture`` runs,
    or the tool raises during execution). Distinct from a generic ``ERROR``
    so monitoring/dashboards can break out forced-tool failures separately.
    """
    return {
        "type": "ERROR",
        "message": "Classifier could not file this capture.",
        "sub_code": "forced_tool_failure",
    }


def _persist_conversation_history_inplace(
    inbox_doc, history: list[ConversationTurn]
) -> dict:
    """Write the updated ``conversationHistory`` back onto the inbox doc.

    Accepts either a dict (raw Cosmos body) or a Pydantic model. Returns the
    mutated dict body ready for ``container.upsert_item(...)``.
    """
    serialized = [t.model_dump() for t in history]
    if isinstance(inbox_doc, dict):
        inbox_doc["conversationHistory"] = serialized
        return inbox_doc
    # Pydantic-style attribute access; coerce to dict for Cosmos upsert.
    inbox_doc.conversationHistory = serialized
    if hasattr(inbox_doc, "model_dump"):
        body = inbox_doc.model_dump(mode="json")
    else:
        body = dict(getattr(inbox_doc, "__dict__", {}))
    body["conversationHistory"] = serialized
    return body


async def _upsert_inbox_with_history(
    cosmos_manager,
    inbox_doc,
    history: list[ConversationTurn],
    capture_trace_id: str,
) -> None:
    """Persist the updated ``conversationHistory`` to Cosmos (best-effort).

    Failures are logged but do NOT raise -- the SSE stream has already
    delivered the classification result to the client. Losing the history
    write means a follow-up will treat the conversation as fresh
    (P0-1 OUTCOME Option A graceful-loss path).
    """
    if cosmos_manager is None or inbox_doc is None:
        return
    log_extra = {"capture_trace_id": capture_trace_id, "component": "classifier"}
    try:
        body = _persist_conversation_history_inplace(inbox_doc, history)
        inbox_container = cosmos_manager.get_container("Inbox")
        await inbox_container.upsert_item(
            body=body, **trace_headers(capture_trace_id or None)
        )
    except Exception:
        logger.warning(
            "Failed to persist conversationHistory back to inbox doc",
            exc_info=True,
            extra=log_extra,
        )


def _build_message_list(
    history: list[ConversationTurn], new_user_text: str
) -> list[Message]:
    """Build the explicit Message list passed to ``agent.run(...)``.

    P0-1 OUTCOME Option A: stateless agent invocation. The history is the
    full prior conversation as persisted on the Inbox doc; the new user
    turn is appended.
    """
    msg_list: list[Message] = [
        Message(role=t.role, contents=[t.content]) for t in history
    ]
    msg_list.append(Message(role="user", contents=[new_user_text]))
    return msg_list


async def stream_text_capture(
    agent: Agent,
    user_text: str,
    inbox_doc,
    thread_id: str,
    run_id: str,
    cosmos_manager=None,
    capture_trace_id: str = "",
) -> AsyncGenerator[str, None]:
    """Stream a text capture through the Classifier agent as AG-UI SSE events.

    GA agent.run(messages, stream=True) under P0-1 OUTCOME Option A:

    * Caller passes the inbox doc (either a freshly-constructed empty body
      for a new capture, or the existing body for a follow-up).
    * Adapter resolves the persisted conversation history from the doc
      via ``resolve_inbox_conversation_history`` (24-15 helper).
    * Adapter builds an explicit ``Message`` list (history + new user turn)
      and calls ``agent.run(...)``.
    * Adapter accumulates the assistant's emitted text deltas, then
      appends the new user turn and the assistant turn to the history,
      and persists the updated history back to the inbox doc.

    Custom OTel span deleted (F-14). capture.* attributes ride on
    structured logger.info(..., extra=log_extra) instead.

    Args:
        agent: GA ``Agent`` instance (Classifier; pre-registered with
            ``[file_capture]`` per F-11 voice path split).
        user_text: The user's text capture body.
        inbox_doc: The inbox doc body to load history from and write the
            updated history back to. dict (raw Cosmos body) or Pydantic
            model accepted.
        thread_id: App-level thread id for SSE event correlation
            (echoed back on MISUNDERSTOOD + COMPLETE for mobile).
        run_id: App-level run id for SSE event correlation.
        cosmos_manager: ``CosmosManager`` for persisting the updated
            conversationHistory back to the inbox doc.
        capture_trace_id: Per-capture trace ID propagated end-to-end.
    """
    log_extra: dict = {
        "capture_trace_id": capture_trace_id,
        "component": "classifier",
        "capture.type": "text",
        "capture.thread_id": thread_id,
        "capture.run_id": run_id,
    }
    # Set ContextVar so file_capture can read the trace ID during agent execution
    trace_token = capture_trace_id_var.set(capture_trace_id)

    # P0-1 OUTCOME Option A: explicit conversation history threading
    history = resolve_inbox_conversation_history(inbox_doc) if inbox_doc else []
    msg_list = _build_message_list(history, user_text)
    options = ChatOptions(tool_choice="required")

    yield encode_sse(step_start_event("Classifying"))

    # Multi-result tracking (Phase 11.1)
    file_capture_results: list[dict] = []
    pending_calls: dict[str, dict] = {}  # call_id -> {name, args}
    accumulated_assistant_text = ""

    chunk_idx: int = 0

    try:
        async with asyncio.timeout(60):
            # GA: agent.run returns a streaming response directly when stream=True.
            # Tools (file_capture) are pre-registered on the agent at lifespan
            # construction (24-14); adapter no longer threads them in per call.
            stream = agent.run(msg_list, options=options, stream=True)

            async for update in stream:
                # Per probe 1 (streaming_shape.json) update.text accumulates
                # final user-visible text; empty during tool-call phase.
                text_delta = getattr(update, "text", "")
                if text_delta:
                    accumulated_assistant_text += text_delta
                    # Classifier suppresses text deltas from the SSE stream
                    # (chain-of-thought is not the user-facing deliverable for
                    # the classifier surface; cf. the Investigation adapter,
                    # which DOES emit text). Log to reasoning channel for
                    # offline analysis / instruction tuning.
                    reasoning_logger.info(
                        "Reasoning chunk",
                        extra={
                            "reasoning_text": text_delta,
                            "agent_run_id": run_id,
                            "chunk_index": chunk_idx,
                            "capture_trace_id": capture_trace_id,
                            "component": "classifier",
                        },
                    )
                    chunk_idx += 1

                for content in getattr(update, "contents", None) or []:
                    content_type = getattr(content, "type", None)

                    if content_type == "function_call":
                        call_id = getattr(content, "call_id", None)
                        name = getattr(content, "name", None)
                        if call_id and name:
                            pending_calls[call_id] = {
                                "name": name,
                                "args": _parse_args(getattr(content, "arguments", {}))
                                if name == "file_capture"
                                else {},
                            }

                    elif content_type == "function_result":
                        call_id = getattr(content, "call_id", None)
                        if call_id and call_id in pending_calls:
                            call_info = pending_calls.pop(call_id)
                            if call_info["name"] == "file_capture":
                                parsed = _parse_result(getattr(content, "result", None))
                                if parsed is not None:
                                    merged = {**call_info["args"], **parsed}
                                    file_capture_results.append(merged)

            yield encode_sse(step_end_event("Classifying"))

            # Emit result event and log outcome
            if file_capture_results:
                # Use first result as primary (backward-compatible)
                primary = file_capture_results[0]
                all_buckets = [r.get("bucket", "?") for r in file_capture_results]
                all_item_ids = [r.get("item_id", "") for r in file_capture_results]
                statuses = [r.get("status", "classified") for r in file_capture_results]

                outcome_extra = {
                    **log_extra,
                    "capture.outcome": "classified",
                    "capture.split_count": len(file_capture_results),
                    "capture.buckets": ",".join(all_buckets),
                    "capture.bucket": primary.get("bucket", ""),
                    "capture.confidence": primary.get("confidence", 0.0),
                }
                logger.info(
                    "Text capture classified: bucket=%s confidence=%.2f splits=%d",
                    primary.get("bucket", ""),
                    primary.get("confidence", 0.0),
                    len(file_capture_results),
                    extra=outcome_extra,
                )

                if "misunderstood" in statuses:
                    yield encode_sse(
                        misunderstood_event(
                            thread_id,
                            primary.get("item_id", ""),
                            "I didn’t quite catch that. Could you clarify?",
                        )
                    )
                elif "pending" in statuses:
                    pending_item = next(
                        r for r in file_capture_results if r.get("status") == "pending"
                    )
                    yield encode_sse(
                        low_confidence_event(
                            pending_item.get("item_id", ""),
                            pending_item.get("bucket", "?"),
                            pending_item.get("confidence", 0.0),
                        )
                    )
                else:
                    if len(file_capture_results) > 1:
                        yield encode_sse(
                            classified_event(
                                primary.get("item_id", ""),
                                primary.get("bucket", "?"),
                                primary.get("confidence", 0.0),
                                buckets=all_buckets,
                                item_ids=all_item_ids,
                            )
                        )
                    else:
                        yield encode_sse(
                            classified_event(
                                primary.get("item_id", ""),
                                primary.get("bucket", "?"),
                                primary.get("confidence", 0.0),
                            )
                        )
            else:
                # tool_choice='required' should force file_capture to fire.
                # Reaching here means the framework allowed the model to
                # produce only natural-language output, OR a tool result
                # was malformed. With the Python safety net gone (F-09),
                # surface this as a forced_tool_failure so monitoring can
                # see the gap.
                logger.warning(
                    "Text capture: tool_choice=required produced no file_capture "
                    "result (forced_tool_failure)",
                    extra={**log_extra, "capture.outcome": "forced_tool_failure"},
                )
                yield encode_sse(_forced_tool_failure_event())

            # P0-1 OUTCOME Option A: append the turns and persist history.
            history.append(ConversationTurn(role="user", content=user_text))
            if accumulated_assistant_text:
                history.append(
                    ConversationTurn(
                        role="assistant", content=accumulated_assistant_text
                    )
                )
            await _upsert_inbox_with_history(
                cosmos_manager, inbox_doc, history, capture_trace_id
            )

            # COMPLETE event: thread_id is a fresh UUID per turn for mobile
            # backward compat; no server-side meaning under P0-1 OUTCOME.
            yield encode_sse(
                complete_event(str(uuid.uuid4()), run_id),
            )

    except Exception as exc:
        # D-04 forced_tool_failure: any exception from agent.run (including
        # tool_choice='required' could-not-satisfy errors and tool exceptions)
        # surfaces as the forced_tool_failure SSE sub_code.
        logger.error(
            "Text capture stream error (forced_tool_failure): %s",
            exc,
            exc_info=True,
            extra={**log_extra, "capture.outcome": "forced_tool_failure"},
        )
        yield encode_sse(_forced_tool_failure_event())
        yield encode_sse(complete_event(str(uuid.uuid4()), run_id))
    finally:
        capture_trace_id_var.reset(trace_token)


async def stream_follow_up_capture(
    agent: Agent,
    follow_up_text: str,
    inbox_doc,
    original_inbox_item_id: str,
    thread_id: str,
    run_id: str,
    cosmos_manager=None,
    capture_trace_id: str = "",
) -> AsyncGenerator[str, None]:
    """Stream a follow-up classification under P0-1 OUTCOME Option A.

    Loads the persisted conversationHistory from the inbox doc via the
    24-15 helper, builds an explicit Message list (history + new user
    turn), calls ``agent.run(...)``, accumulates the assistant text,
    appends both turns, and persists the updated history back to the doc.

    The original RC ``conversation_id`` round-trip is GONE (F-13). The
    legacy ``foundryThreadId`` field is also unused here -- the helper
    returns ``[]`` for docs that only carry the legacy field, and the
    follow-up proceeds as a fresh conversation (Option A graceful-loss
    trade-off).

    Args:
        agent: GA ``Agent`` instance (Classifier; pre-registered with
            ``[file_capture]``).
        follow_up_text: The user's follow-up clarification text.
        inbox_doc: The existing inbox doc loaded by the caller.
        original_inbox_item_id: The Cosmos inbox item ID for the original
            misunderstood capture, used for structured logging.
        thread_id: App-level thread id for SSE event correlation.
        run_id: App-level run id for SSE event correlation.
        cosmos_manager: ``CosmosManager`` for persisting the updated
            conversationHistory back to the inbox doc.
        capture_trace_id: Per-capture trace ID propagated end-to-end.
    """
    log_extra: dict = {
        "capture_trace_id": capture_trace_id,
        "component": "classifier",
        "capture.type": "follow_up",
        "capture.thread_id": thread_id,
        "capture.run_id": run_id,
        "capture.original_inbox_item_id": original_inbox_item_id,
    }
    trace_token = capture_trace_id_var.set(capture_trace_id)

    history = resolve_inbox_conversation_history(inbox_doc) if inbox_doc else []
    msg_list = _build_message_list(history, follow_up_text)
    options = ChatOptions(tool_choice="required")

    yield encode_sse(step_start_event("Classifying"))

    # Outcome tracking
    detected_tool: str | None = None
    detected_tool_args: dict = {}
    tool_result: dict | None = None
    accumulated_assistant_text = ""

    chunk_idx: int = 0

    try:
        async with asyncio.timeout(60):
            stream = agent.run(msg_list, options=options, stream=True)

            async for update in stream:
                text_delta = getattr(update, "text", "")
                if text_delta:
                    accumulated_assistant_text += text_delta
                    reasoning_logger.info(
                        "Follow-up reasoning chunk",
                        extra={
                            "reasoning_text": text_delta,
                            "agent_run_id": run_id,
                            "chunk_index": chunk_idx,
                            "capture_trace_id": capture_trace_id,
                            "component": "classifier",
                        },
                    )
                    chunk_idx += 1

                for content in getattr(update, "contents", None) or []:
                    content_type = getattr(content, "type", None)
                    if (
                        content_type == "function_call"
                        and getattr(content, "name", None) == "file_capture"
                    ):
                        detected_tool = "file_capture"
                        detected_tool_args = _parse_args(
                            getattr(content, "arguments", {})
                        )

                    elif content_type == "function_result":
                        tool_result = _parse_result(getattr(content, "result", None))

            yield encode_sse(step_end_event("Classifying"))

            if detected_tool == "file_capture":
                result_src = tool_result or detected_tool_args
                status = detected_tool_args.get("status", "")
                outcome_extra = {
                    **log_extra,
                    "capture.outcome": status if status else "unresolved",
                    "capture.bucket": result_src.get("bucket", ""),
                    "capture.confidence": result_src.get("confidence", 0.0),
                }
                logger.info(
                    "Follow-up classified: status=%s bucket=%s confidence=%.2f",
                    status or "unresolved",
                    result_src.get("bucket", ""),
                    result_src.get("confidence", 0.0),
                    extra=outcome_extra,
                )
                yield encode_sse(
                    _emit_result_event(detected_tool_args, tool_result, thread_id)
                )
            else:
                logger.warning(
                    "Follow-up: tool_choice=required produced no file_capture "
                    "result (forced_tool_failure)",
                    extra={**log_extra, "capture.outcome": "forced_tool_failure"},
                )
                yield encode_sse(_forced_tool_failure_event())

            # P0-1 OUTCOME Option A: append turns and persist history.
            history.append(ConversationTurn(role="user", content=follow_up_text))
            if accumulated_assistant_text:
                history.append(
                    ConversationTurn(
                        role="assistant", content=accumulated_assistant_text
                    )
                )
            await _upsert_inbox_with_history(
                cosmos_manager, inbox_doc, history, capture_trace_id
            )

            yield encode_sse(
                complete_event(str(uuid.uuid4()), run_id),
            )

    except Exception as exc:
        logger.error(
            "Follow-up capture stream error (forced_tool_failure): %s",
            exc,
            exc_info=True,
            extra={**log_extra, "capture.outcome": "forced_tool_failure"},
        )
        yield encode_sse(_forced_tool_failure_event())
        yield encode_sse(complete_event(str(uuid.uuid4()), run_id))
    finally:
        capture_trace_id_var.reset(trace_token)


# The previous voice-capture streaming function has been deleted in plan
# 24-16 (D-04 voice path split). Voice path routes through
# stream_text_capture after the api/capture.py voice handler direct-calls
# TranscriptionTools.transcribe_audio (24-15). Any remaining importer of
# the deleted function will raise ImportError -- this is intentional and
# documented in 24-15 SUMMARY's Decision #4 (left to ruff for stripping).

# The legacy ``error_event`` helper from streaming/sse.py is retained for
# the unresolved-event path and any future generic-error use; the new
# forced_tool_failure path uses ``_forced_tool_failure_event()`` above.
_ = error_event  # noqa: F401 -- preserved for callers; not used directly here.
_ = unresolved_event  # noqa: F401 -- preserved for callers.
