"""Investigation Agent SSE streaming adapter.

Streams Investigation Agent responses as SSE events. Unlike the Classifier
adapter (which suppresses text output as reasoning), the Investigation
Agent's text IS the primary deliverable -- yielded as "text" events.

SSE event types:
  - thinking: agent is processing the question
  - rate_warning: soft rate limit exceeded (warn only, do not block)
  - tool_call: agent is calling an investigation tool
  - tool_error: a tool returned an error result
  - text: agent's human-readable answer (primary output)
  - error: something went wrong
  - done: stream complete, includes thread_id for multi-turn
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from collections.abc import AsyncGenerator

from agent_framework import ChatOptions, Message
from agent_framework.azure import DurableAIAgentClient
from opentelemetry import trace

from second_brain.streaming.sse import encode_sse

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("second_brain.investigation")

# Human-friendly descriptions for tool calls
_TOOL_DESCRIPTIONS: dict[str, str] = {
    "trace_lifecycle": "Tracing capture lifecycle...",
    "recent_errors": "Querying recent errors...",
    "system_health": "Checking system health...",
    "usage_patterns": "Analyzing usage patterns...",
}


class SoftRateLimiter:
    """Warn-only rate limiter using sliding window.

    Does NOT block requests -- only indicates when the caller is
    sending queries faster than the configured threshold.
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: deque[float] = deque()

    def check(self) -> bool:
        """Return True if within limit, False if over (warn only)."""
        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] > self._window:
            self._timestamps.popleft()
        self._timestamps.append(now)
        return len(self._timestamps) <= self._max


async def stream_investigation(
    client: DurableAIAgentClient,
    question: str,
    tools: list,
    thread_id: str | None = None,
    rate_limiter: SoftRateLimiter | None = None,
) -> AsyncGenerator[str, None]:
    """Stream an Investigation Agent response as SSE events.

    The Investigation Agent's text output is the PRIMARY deliverable,
    yielded as "text" SSE events. This is the key difference from
    the Classifier adapter which suppresses text as reasoning.

    Args:
        client: DurableAIAgentClient configured for the Investigation
            Agent.
        question: The user's natural-language question.
        tools: List of @tool-decorated functions from
            InvestigationTools.
        thread_id: Optional thread ID for multi-turn conversation
            continuity.
        rate_limiter: Optional SoftRateLimiter instance. When over
            limit, yields a warning event but does NOT block.

    Yields:
        SSE-formatted strings (``data: {...}\\n\\n``).
    """
    with tracer.start_as_current_span("investigate") as span:
        span.set_attribute("investigate.question_length", len(question))
        span.set_attribute("investigate.thread_id", thread_id or "")
        span.set_attribute("investigate.has_tools", len(tools) > 0)

        # Soft rate limit check -- warn only
        if rate_limiter and not rate_limiter.check():
            yield encode_sse(
                {
                    "type": "rate_warning",
                    "message": (
                        "You're sending queries quickly. Results may be slower."
                    ),
                }
            )

        yield encode_sse({"type": "thinking"})

        messages = [Message(role="user", text=question)]
        options: ChatOptions = {"tools": tools}
        if thread_id:
            options["conversation_id"] = thread_id

        # NOTE: tool_choice is intentionally NOT set (defaults to auto).
        # The Investigation Agent can respond without calling tools
        # (e.g., "thanks", "what can you help with?").

        conversation_id: str | None = None
        last_tool_name: str | None = None

        try:
            async with asyncio.timeout(30):
                stream = client.get_response(
                    messages=messages,
                    stream=True,
                    options=options,
                )

                async for update in stream:
                    # Capture conversation_id for thread continuity
                    if getattr(update, "conversation_id", None) and not conversation_id:
                        conversation_id = update.conversation_id

                    for content in update.contents or []:
                        # Text output IS the answer
                        if content.type == "text" and getattr(content, "text", None):
                            yield encode_sse(
                                {
                                    "type": "text",
                                    "content": content.text,
                                }
                            )

                        # Tool call -- show which tool is being used
                        elif content.type == "function_call":
                            name = getattr(content, "name", None)
                            if name:
                                last_tool_name = name
                                description = _TOOL_DESCRIPTIONS.get(
                                    name, f"Calling {name}..."
                                )
                                yield encode_sse(
                                    {
                                        "type": "tool_call",
                                        "tool": name,
                                        "description": description,
                                    }
                                )

                        # Tool result -- check for errors
                        elif content.type == "function_result":
                            result_str = getattr(content, "result", None)
                            if result_str:
                                try:
                                    parsed = json.loads(str(result_str))
                                    if isinstance(parsed, dict) and "error" in parsed:
                                        yield encode_sse(
                                            {
                                                "type": "tool_error",
                                                "tool": last_tool_name or "unknown",
                                                "error": parsed["error"],
                                            }
                                        )
                                except (
                                    json.JSONDecodeError,
                                    TypeError,
                                ):
                                    pass

            # Stream completed successfully
            final_thread = conversation_id or thread_id or ""
            span.set_attribute("investigate.thread_id_out", final_thread)
            yield encode_sse({"type": "done", "thread_id": final_thread})

        except TimeoutError:
            logger.warning(
                "Investigation stream timed out after 30s",
                extra={"component": "investigation_agent"},
            )
            span.set_attribute("investigate.timed_out", True)
            yield encode_sse(
                {
                    "type": "error",
                    "message": (
                        "The investigation timed out after 30 seconds. "
                        "The agent may be processing a complex query -- "
                        "please try again or simplify your question."
                    ),
                }
            )
            yield encode_sse({"type": "done", "thread_id": thread_id or ""})

        except Exception as exc:
            logger.error(
                "Investigation stream error: %s",
                exc,
                exc_info=True,
                extra={"component": "investigation_agent"},
            )
            span.record_exception(exc)
            yield encode_sse(
                {
                    "type": "error",
                    "message": ("Investigation failed. Please try again."),
                }
            )
            yield encode_sse({"type": "done", "thread_id": thread_id or ""})
