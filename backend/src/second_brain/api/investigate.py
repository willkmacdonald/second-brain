"""Investigation API endpoint -- natural language queries against App Insights.

POST /api/investigate -- accepts a question and streams SSE events with
the Investigation Agent's answer, tool calls, and thread ID for multi-turn
conversations.
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
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


class InvestigateBody(BaseModel):
    """Request body for investigation queries."""

    question: str = Field(..., max_length=5000)
    thread_id: str | None = None


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

    investigation_client = getattr(request.app.state, "investigation_client", None)
    if investigation_client is None:
        raise HTTPException(
            status_code=503,
            detail="Investigation agent is unavailable.",
        )

    tools = getattr(request.app.state, "investigation_tools", [])
    rate_limiter = getattr(request.app.state, "investigation_rate_limiter", None)

    logger.info(
        "Investigation query: question=%s thread_id=%s",
        body.question[:80],
        body.thread_id,
        extra={"component": "investigation_agent"},
    )

    generator = stream_investigation(
        client=investigation_client,
        question=body.question,
        tools=tools,
        thread_id=body.thread_id,
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
