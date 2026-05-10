"""Investigation Agent SSE streaming adapter (GA, STATELESS Option A).

Streams Investigation Agent responses as SSE events. Unlike the Classifier
adapter (which suppresses text output as reasoning), the Investigation
Agent's text IS the primary deliverable -- yielded as "text" events.

P0-1 OUTCOME (2026-05-10, fixture
``backend/tests/fixtures/foundry-probe/session_rehydration_fresh_process.json``):
cross-process session-handle rehydration via ``session_id`` alone FAILS on
GA Foundry SDK 1.3.0. The client UUID is a local correlator only; the server
creates a new response thread on every ``agent.run()`` call. Operator locked
**Option A**: stateless agent invocation with explicit conversation context.

For Investigation specifically, the mobile app already holds the visible
chat history (chat bubbles on screen). Mobile passes that history with each
new turn; the backend is a thin pass-through. Each chat turn is therefore
a fresh agent invocation with the explicit message list. NO Inbox-doc
persistence -- Investigation is a transient session, not a captured artifact.

The wire field ``thread_id`` on the ``done`` SSE event stays for mobile
backward compat, but is now a fresh ``uuid.uuid4()`` per turn with no
server-side meaning. Mobile does not introspect the value.

SSE event types:
  - thinking: agent is processing the question
  - rate_warning: soft rate limit exceeded (warn only, do not block)
  - tool_call: agent is calling an investigation tool
  - tool_error: a tool returned an error result
  - text: agent's human-readable answer (primary output)
  - error: something went wrong
  - done: stream complete, includes a fresh ``thread_id`` UUID (backward compat only)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from collections.abc import AsyncGenerator

from agent_framework import Agent, Message

from second_brain.streaming.sse import encode_sse

logger = logging.getLogger(__name__)

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
    agent: Agent,
    question: str,
    history: list[dict] | None = None,
    rate_limiter: SoftRateLimiter | None = None,
) -> AsyncGenerator[str, None]:
    """Stream an Investigation Agent response as SSE events (Option A).

    Stateless wrapper around ``agent.run(messages=..., stream=True)``. The
    caller (api/investigate.py) supplies the visible chat history from the
    mobile request body; this function builds an explicit ``Message`` list
    and passes it through. There is NO server-side session handle and NO
    server-side thread continuity (P0-1 OUTCOME).

    The Investigation Agent's text output is the PRIMARY deliverable,
    yielded as "text" SSE events. This is the key difference from the
    Classifier adapter which suppresses text as reasoning.

    Args:
        agent: GA ``Agent`` instance (pre-registered with the Investigation
            tools at lifespan construction -- see 24-04).
        question: The user's natural-language question.
        history: Optional list of prior conversation turns, each a dict
            ``{"role": "user"|"assistant", "content": str}``. Mobile holds
            the visible chat history and passes it with each follow-up.
            ``None`` (or empty) means a fresh conversation.
        rate_limiter: Optional SoftRateLimiter instance. When over limit,
            yields a warning event but does NOT block.

    Yields:
        SSE-formatted strings (``data: {...}\\n\\n``).
    """
    # Soft rate limit check -- warn only
    if rate_limiter and not rate_limiter.check():
        yield encode_sse(
            {
                "type": "rate_warning",
                "message": ("You're sending queries quickly. Results may be slower."),
            }
        )

    yield encode_sse({"type": "thinking"})

    # P0-1 OUTCOME (Option A): explicit message list from mobile-supplied history.
    # Cross-process session-handle rehydration fails on GA SDK 1.3.0 -- we hold
    # the history client-side and pass it explicitly on every turn.
    msg_list: list[Message] = [
        Message(role=t["role"], contents=[t["content"]]) for t in (history or [])
    ]
    msg_list.append(Message(role="user", contents=[question]))

    last_tool_name: str | None = None

    try:
        async with asyncio.timeout(30):
            # GA: agent.run returns a ResponseStream directly when stream=True.
            # Tools are pre-registered on the agent at lifespan construction
            # (24-04); the adapter no longer threads them in per call.
            stream = agent.run(msg_list, stream=True)

            async for update in stream:
                # Primary text emission via update.text (per probe 1
                # streaming_shape.json -- AgentResponseUpdate.text accumulates
                # final user-visible text; empty during tool-call phase).
                text_delta = getattr(update, "text", None)
                if text_delta:
                    yield encode_sse(
                        {
                            "type": "text",
                            "content": text_delta,
                        }
                    )

                # Tool events still come through contents[] during the
                # tool-call phase; keep the existing content.type matching.
                for content in getattr(update, "contents", None) or []:
                    content_type = getattr(content, "type", None)

                    # Tool call -- show which tool is being used
                    if content_type == "function_call":
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
                    elif content_type == "function_result":
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

        # Stream completed successfully.
        # P0-1 OUTCOME: thread_id is a fresh UUID with no server meaning.
        # Mobile expects the field but does not introspect the value.
        yield encode_sse(
            {
                "type": "done",
                "thread_id": str(uuid.uuid4()),
            }
        )

    except TimeoutError:
        logger.warning(
            "Investigation stream timed out after 30s",
            extra={"component": "investigation_agent"},
        )
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
        yield encode_sse(
            {
                "type": "done",
                "thread_id": str(uuid.uuid4()),
            }
        )

    except Exception as exc:
        logger.error(
            "Investigation stream error: %s",
            exc,
            exc_info=True,
            extra={"component": "investigation_agent"},
        )
        yield encode_sse(
            {
                "type": "error",
                "message": ("Investigation failed. Please try again."),
            }
        )
        yield encode_sse(
            {
                "type": "done",
                "thread_id": str(uuid.uuid4()),
            }
        )
