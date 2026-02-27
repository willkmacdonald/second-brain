"""FoundrySSEAdapter -- async generator functions for streaming captures.

Iterates ChatResponseUpdate objects from the Foundry streaming API,
detects tool outcomes via Content inspection, and yields SSE-formatted
strings matching the AG-UI protocol the mobile app expects.

Chain-of-thought reasoning text is suppressed from the SSE stream and
logged to Application Insights for analysis and instruction tuning.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Mapping

from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient

from second_brain.streaming.sse import (
    classified_event,
    complete_event,
    encode_sse,
    error_event,
    misunderstood_event,
    step_end_event,
    step_start_event,
    unresolved_event,
)

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
    foundry_conversation_id: str | None = None,
) -> dict:
    """Determine and return the appropriate result event dict."""
    status = detected_tool_args.get("status")

    # Prefer tool_result values, fall back to detected_tool_args
    result_src = tool_result or detected_tool_args
    item_id = result_src.get("item_id", "")
    bucket = result_src.get("bucket", detected_tool_args.get("bucket", ""))
    confidence = result_src.get("confidence", detected_tool_args.get("confidence", 0.0))

    if status == "misunderstood":
        question_text = detected_tool_args.get("title", "Could you clarify?")
        return misunderstood_event(
            thread_id, item_id, question_text, foundry_conversation_id
        )

    if status in ("classified", "pending"):
        return classified_event(item_id, bucket, confidence)

    # No recognized status -- unresolved fallback
    return unresolved_event(item_id)


async def stream_text_capture(
    client: AzureAIAgentClient,
    user_text: str,
    tools: list,
    thread_id: str,
    run_id: str,
) -> AsyncGenerator[str, None]:
    """Stream a text capture through the Classifier agent as AG-UI SSE events.

    Iterates ChatResponseUpdate objects from the Foundry streaming API,
    detects tool outcomes, and yields SSE-formatted JSON events.
    Chain-of-thought reasoning text is suppressed and logged.
    """
    messages = [Message(role="user", text=user_text)]
    options: ChatOptions = {"tools": tools}

    yield encode_sse(step_start_event("Classifying"))

    # Outcome tracking
    detected_tool: str | None = None
    detected_tool_args: dict = {}
    tool_result: dict | None = None
    reasoning_buffer: str = ""
    chunk_idx: int = 0
    foundry_conversation_id: str | None = None

    try:
        async with asyncio.timeout(60):
            stream = client.get_response(
                messages=messages, stream=True, options=options
            )

            async for update in stream:
                # Capture the Foundry thread ID from the first update that has one
                if (
                    getattr(update, "conversation_id", None)
                    and not foundry_conversation_id
                ):
                    foundry_conversation_id = update.conversation_id

                for content in update.contents or []:
                    if content.type == "text" and getattr(content, "text", None):
                        reasoning_buffer += content.text
                        reasoning_logger.info(
                            "Reasoning chunk",
                            extra={
                                "reasoning_text": content.text,
                                "agent_run_id": run_id,
                                "chunk_index": chunk_idx,
                            },
                        )
                        chunk_idx += 1
                        # Do NOT yield -- suppress CoT from SSE

                    elif (
                        content.type == "function_call"
                        and getattr(content, "name", None) == "file_capture"
                    ):
                        detected_tool = "file_capture"
                        detected_tool_args = _parse_args(
                            getattr(content, "arguments", {})
                        )

                    elif content.type == "function_result":
                        tool_result = _parse_result(getattr(content, "result", None))

            yield encode_sse(step_end_event("Classifying"))

            # Emit result event
            if detected_tool == "file_capture":
                yield encode_sse(
                    _emit_result_event(
                        detected_tool_args,
                        tool_result,
                        thread_id,
                        foundry_conversation_id,
                    )
                )
            else:
                # No tool call detected -- unresolved fallback
                yield encode_sse(unresolved_event(""))

            yield encode_sse(complete_event(thread_id, run_id))

    except (TimeoutError, Exception) as exc:
        logger.error("Text capture stream error: %s", exc, exc_info=True)
        yield encode_sse(error_event(str(exc)))
        yield encode_sse(complete_event(thread_id, run_id))


async def stream_voice_capture(
    client: AzureAIAgentClient,
    blob_url: str,
    tools: list,
    thread_id: str,
    run_id: str,
) -> AsyncGenerator[str, None]:
    """Stream a voice capture through the Classifier agent as AG-UI SSE events.

    Voice captures use a single "Processing" step bracket for the entire run.
    The agent calls transcribe_audio then file_capture internally -- the adapter
    observes these as function_call content but does not emit separate step events.
    """
    messages = [
        Message(
            role="user",
            text=f"Transcribe and classify this voice recording: {blob_url}",
        )
    ]
    options: ChatOptions = {"tools": tools}

    yield encode_sse(step_start_event("Processing"))

    # Outcome tracking
    detected_tool: str | None = None
    detected_tool_args: dict = {}
    tool_result: dict | None = None
    reasoning_buffer: str = ""
    chunk_idx: int = 0
    foundry_conversation_id: str | None = None

    try:
        async with asyncio.timeout(60):
            stream = client.get_response(
                messages=messages, stream=True, options=options
            )

            async for update in stream:
                # Capture the Foundry thread ID from the first update that has one
                if (
                    getattr(update, "conversation_id", None)
                    and not foundry_conversation_id
                ):
                    foundry_conversation_id = update.conversation_id

                for content in update.contents or []:
                    if content.type == "text" and getattr(content, "text", None):
                        reasoning_buffer += content.text
                        reasoning_logger.info(
                            "Reasoning chunk",
                            extra={
                                "reasoning_text": content.text,
                                "agent_run_id": run_id,
                                "chunk_index": chunk_idx,
                            },
                        )
                        chunk_idx += 1

                    elif content.type == "function_call":
                        name = getattr(content, "name", None)
                        if name == "transcribe_audio":
                            # Log transcription tool call but do NOT emit
                            # a separate step event (single step for voice)
                            logger.info("Voice capture: transcribe_audio called")
                        elif name == "file_capture":
                            detected_tool = "file_capture"
                            detected_tool_args = _parse_args(
                                getattr(content, "arguments", {})
                            )

                    elif content.type == "function_result":
                        # Only capture the last function_result (file_capture)
                        parsed = _parse_result(getattr(content, "result", None))
                        if parsed is not None:
                            tool_result = parsed

            yield encode_sse(step_end_event("Processing"))

            # Emit result event
            if detected_tool == "file_capture":
                yield encode_sse(
                    _emit_result_event(
                        detected_tool_args,
                        tool_result,
                        thread_id,
                        foundry_conversation_id,
                    )
                )
            else:
                yield encode_sse(unresolved_event(""))

            yield encode_sse(complete_event(thread_id, run_id))

    except (TimeoutError, Exception) as exc:
        logger.error("Voice capture stream error: %s", exc, exc_info=True)
        yield encode_sse(error_event(str(exc)))
        yield encode_sse(complete_event(thread_id, run_id))


async def stream_follow_up_capture(
    client: AzureAIAgentClient,
    follow_up_text: str,
    foundry_thread_id: str,
    tools: list,
    thread_id: str,
    run_id: str,
) -> AsyncGenerator[str, None]:
    """Stream a follow-up classification attempt on the same Foundry thread.

    Reuses the existing Foundry thread via conversation_id in ChatOptions so
    the agent sees its prior classification attempt and the user's responses.
    Yields the same SSE event sequence as stream_text_capture.
    """
    messages = [Message(role="user", text=follow_up_text)]
    options: ChatOptions = {
        "tools": tools,
        "conversation_id": foundry_thread_id,
    }

    yield encode_sse(step_start_event("Classifying"))

    # Outcome tracking
    detected_tool: str | None = None
    detected_tool_args: dict = {}
    tool_result: dict | None = None
    reasoning_buffer: str = ""
    chunk_idx: int = 0
    foundry_conversation_id: str | None = None

    try:
        async with asyncio.timeout(60):
            stream = client.get_response(
                messages=messages, stream=True, options=options
            )

            async for update in stream:
                if (
                    getattr(update, "conversation_id", None)
                    and not foundry_conversation_id
                ):
                    foundry_conversation_id = update.conversation_id

                for content in update.contents or []:
                    if content.type == "text" and getattr(content, "text", None):
                        reasoning_buffer += content.text
                        reasoning_logger.info(
                            "Follow-up reasoning chunk",
                            extra={
                                "reasoning_text": content.text,
                                "agent_run_id": run_id,
                                "chunk_index": chunk_idx,
                            },
                        )
                        chunk_idx += 1

                    elif (
                        content.type == "function_call"
                        and getattr(content, "name", None) == "file_capture"
                    ):
                        detected_tool = "file_capture"
                        detected_tool_args = _parse_args(
                            getattr(content, "arguments", {})
                        )

                    elif content.type == "function_result":
                        tool_result = _parse_result(getattr(content, "result", None))

            yield encode_sse(step_end_event("Classifying"))

            # Emit result event
            if detected_tool == "file_capture":
                yield encode_sse(
                    _emit_result_event(
                        detected_tool_args,
                        tool_result,
                        thread_id,
                        foundry_conversation_id,
                    )
                )
            else:
                yield encode_sse(unresolved_event(""))

            yield encode_sse(complete_event(thread_id, run_id))

    except (TimeoutError, Exception) as exc:
        logger.error("Follow-up capture stream error: %s", exc, exc_info=True)
        yield encode_sse(error_event(str(exc)))
        yield encode_sse(complete_event(thread_id, run_id))
