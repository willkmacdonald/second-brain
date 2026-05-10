"""Investigation API endpoint -- natural language queries against App Insights.

POST /api/investigate -- accepts a question + visible chat history and
streams SSE events with the Investigation Agent's answer and tool calls.

P0-1 OUTCOME (2026-05-10): the wire field ``thread_id`` no longer carries
server-side meaning. The mobile app holds the visible chat history and
passes it with each follow-up via the ``history`` field; the backend
constructs an explicit message list and invokes ``agent.run(..., stream=True)``
stateless. The ``thread_id`` echoed back on the ``done`` SSE event is a
fresh per-turn UUID for mobile backward compat (mobile does not introspect
the value).
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from pydantic import BaseModel, Field

from second_brain.spine.stream_wrapper import spine_stream_wrapper
from second_brain.streaming.investigation_adapter import (
    stream_investigation,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Investigation"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class ConversationTurn(BaseModel):
    """A single prior conversation turn (mobile-supplied visible history).

    Mobile holds the visible chat history client-side (chat bubbles on
    screen) and passes it with each follow-up so the backend can pass an
    explicit message list into ``agent.run(...)`` -- see P0-1 OUTCOME.
    """

    role: Literal["user", "assistant"]
    content: str


class InvestigateBody(BaseModel):
    """Request body for investigation queries."""

    question: str = Field(..., max_length=5000)
    # ``thread_id`` is accepted for backward compat (older mobile builds
    # supply it) but is no longer used server-side under P0-1 OUTCOME.
    # It is logged onto the AppRequests span for observability
    # cross-referencing only.
    thread_id: str | None = None
    # Visible chat history from the mobile client, in chronological order.
    # ``None`` (or empty) means a fresh conversation. The adapter builds
    # an explicit ``Message`` list from this + the new user turn.
    history: list[ConversationTurn] | None = None


@router.post("/api/investigate")
async def investigate(
    request: Request,
    body: InvestigateBody,
) -> StreamingResponse:
    """Stream investigation results as SSE events.

    Accepts a natural-language question about captures and system
    health. Returns streaming SSE events: thinking, tool_call,
    tool_error, text (the answer), and done (with thread_id for
    multi-turn).

    Returns 503 if App Insights or the Investigation Agent is
    unavailable.
    """
    logs_client = getattr(request.app.state, "logs_client", None)
    if logs_client is None:
        raise HTTPException(
            status_code=503,
            detail=("App Insights is unreachable. Investigation is unavailable."),
        )

    investigation_agent = getattr(request.app.state, "investigation_agent", None)
    if investigation_agent is None:
        raise HTTPException(
            status_code=503,
            detail="Investigation agent is unavailable.",
        )

    rate_limiter = getattr(request.app.state, "investigation_rate_limiter", None)

    # Convert Pydantic ConversationTurn list to list[dict] for the adapter
    # (the adapter's history param is typed list[dict] -- it stays plain
    # dicts so the helper can be unit-tested without Pydantic imports).
    history_dicts: list[dict] | None = (
        [{"role": turn.role, "content": turn.content} for turn in body.history]
        if body.history
        else None
    )

    logger.info(
        "Investigation query: question=%s thread_id=%s history_length=%d",
        body.question[:80],
        body.thread_id,
        len(history_dicts) if history_dicts else 0,
        extra={"component": "investigation_agent"},
    )

    # P0-1 OUTCOME: investigate.* attributes that previously lived on the
    # deleted custom 'investigate' span (F-15) now ride on the AppRequests
    # span via the same pattern as api/capture.py:228. Set them BEFORE the
    # StreamingResponse is returned so they land on the request span that
    # ASGI auto-instrumentation created at request entry.
    _current = trace.get_current_span()
    if _current.is_recording():
        _current.set_attribute("investigate.question_length", len(body.question))
        _current.set_attribute("investigate.thread_id", body.thread_id or "")
        _current.set_attribute(
            "investigate.history_length",
            len(history_dicts) if history_dicts else 0,
        )

    generator = stream_investigation(
        agent=investigation_agent,
        question=body.question,
        history=history_dicts,
        rate_limiter=rate_limiter,
    )

    spine_repo = getattr(request.app.state, "spine_repo", None)
    stream = generator
    if spine_repo:
        stream = spine_stream_wrapper(
            stream,
            repo=spine_repo,
            segment_id="investigation",
            operation="answer_question",
            thread_id=body.thread_id,
        )

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
