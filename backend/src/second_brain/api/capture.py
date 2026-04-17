"""Capture API endpoint -- unified text and voice capture with SSE streaming.

POST /api/capture  -- text capture (JSON body)
POST /api/capture/voice -- voice capture (multipart file upload)
POST /api/capture/follow-up -- follow-up for misunderstood captures (SSE)
POST /api/capture/follow-up/voice -- voice follow-up for misunderstood captures (SSE)

Both capture endpoints stream Foundry agent classification results as
AG-UI-compatible SSE events. The mobile Expo app consumes these via
react-native-sse EventSource.
"""

import json
import logging
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from second_brain.spine.stream_wrapper import spine_stream_wrapper
from second_brain.streaming.adapter import (
    stream_follow_up_capture,
    stream_text_capture,
    stream_voice_capture,
)
from second_brain.tools.classification import follow_up_context

logger = logging.getLogger(__name__)


# Shared log extra factory for capture endpoints
def _capture_extra(trace_id: str) -> dict:
    return {"capture_trace_id": trace_id, "component": "capture"}


router = APIRouter(tags=["Capture"])

MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25 MB
ALLOWED_AUDIO_TYPES = frozenset(
    {
        "audio/m4a",
        "audio/mp4",
        "audio/mpeg",
        "audio/wav",
        "audio/vnd.wave",
        "audio/x-m4a",
        "audio/aac",
        "audio/ogg",
    }
)


async def _validate_and_read_audio(file: UploadFile) -> bytes:
    """Validate audio upload size and content type, then return bytes."""
    content_type = file.content_type or ""
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported audio format: {content_type}",
        )
    if file.size and file.size > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25 MB)")
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25 MB)")
    return audio_bytes


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class TextCaptureBody(BaseModel):
    """Request body for text capture."""

    text: str = Field(..., max_length=10000)
    thread_id: str | None = None
    run_id: str | None = None


class FollowUpBody(BaseModel):
    """Request body for follow-up capture (misunderstood re-classification)."""

    inbox_item_id: str
    follow_up_text: str = Field(..., max_length=10000)
    follow_up_round: int = 1


async def _stream_with_thread_id_persistence(
    inner_generator,
    cosmos_manager,
    capture_trace_id: str = "",
):
    """Wrap a capture stream generator to persist foundryThreadId on MISUNDERSTOOD.

    Yields all SSE events through to the client. When a MISUNDERSTOOD event is
    detected, immediately persists the foundryThreadId to Cosmos before
    yielding any further events -- this prevents a race condition where the
    client disconnects after COMPLETE and the Cosmos write never happens.
    """
    log_extra = _capture_extra(capture_trace_id)
    async for event in inner_generator:
        # Intercept MISUNDERSTOOD events to persist foundryThreadId immediately
        if event.startswith("data: "):
            try:
                payload = json.loads(event[6:].strip())
                if payload.get("type") == "MISUNDERSTOOD":
                    value = payload.get("value", {})
                    item_id = value.get("inboxItemId")
                    conversation_id = value.get("foundryConversationId")
                    if item_id and conversation_id:
                        try:
                            inbox_container = cosmos_manager.get_container("Inbox")
                            doc = await inbox_container.read_item(
                                item=item_id, partition_key="will"
                            )
                            doc["foundryThreadId"] = conversation_id
                            await inbox_container.upsert_item(body=doc)
                            logger.info(
                                "Persisted foundryThreadId=%s for inbox item %s",
                                conversation_id,
                                item_id,
                                extra=log_extra,
                            )
                        except Exception:
                            logger.warning(
                                "Failed to persist foundryThreadId for %s",
                                item_id,
                                extra=log_extra,
                            )
            except (json.JSONDecodeError, AttributeError):
                pass

        yield event


async def _stream_with_follow_up_context(
    inner_generator,
    inbox_item_id: str,
    cosmos_manager,
    capture_trace_id: str = "",
):
    """Set follow-up context so file_capture updates existing doc in-place.

    Wraps a follow-up stream generator. The follow_up_context context manager
    sets _follow_up_inbox_item_id so that file_capture (called by the Foundry
    agent during streaming) updates the existing misunderstood inbox doc
    instead of creating a new orphan.

    Also handles foundryThreadId persistence when the follow-up results in
    MISUNDERSTOOD again (needed for further follow-up rounds).
    """
    log_extra = _capture_extra(capture_trace_id)
    with follow_up_context(inbox_item_id):
        foundry_conversation_id = None
        async for event in inner_generator:
            if event.startswith("data: "):
                try:
                    payload = json.loads(event[6:].strip())
                    if payload.get("type") == "MISUNDERSTOOD":
                        value = payload.get("value", {})
                        foundry_conversation_id = value.get("foundryConversationId")
                except (json.JSONDecodeError, AttributeError):
                    pass
            yield event

        # After stream: if re-misunderstood, update foundryThreadId on original doc
        if foundry_conversation_id:
            try:
                inbox_container = cosmos_manager.get_container("Inbox")
                doc = await inbox_container.read_item(
                    item=inbox_item_id, partition_key="will"
                )
                doc["foundryThreadId"] = foundry_conversation_id
                await inbox_container.upsert_item(body=doc)
                logger.info(
                    "Updated foundryThreadId=%s for ongoing follow-up on %s",
                    foundry_conversation_id,
                    inbox_item_id,
                    extra=log_extra,
                )
            except Exception:
                logger.warning(
                    "Failed to update foundryThreadId on follow-up for %s",
                    inbox_item_id,
                    extra=log_extra,
                )


@router.post("/api/capture")
async def capture(request: Request, body: TextCaptureBody) -> StreamingResponse:
    """Stream text capture classification as AG-UI SSE events.

    Accepts a JSON body with the capture text, streams the Foundry agent
    classification result as SSE events (STEP_START, STEP_END, CLASSIFIED/
    MISUNDERSTOOD/UNRESOLVED, COMPLETE).

    When the outcome is MISUNDERSTOOD, the foundryThreadId is persisted to the
    inbox document for use in follow-up calls.
    """
    client = request.app.state.classifier_client
    tools = request.app.state.classifier_agent_tools
    cosmos_manager = request.app.state.cosmos_manager
    thread_id = body.thread_id or f"thread-{uuid4()}"
    run_id = body.run_id or f"run-{uuid4()}"
    capture_trace_id = request.headers.get("X-Trace-Id", str(uuid4()))
    request.state.capture_trace_id = capture_trace_id
    log_extra = _capture_extra(capture_trace_id)

    capture_source = request.headers.get("X-Capture-Source")
    if capture_source:
        logger.info(
            "Capture source: %s, thread_id=%s",
            capture_source,
            thread_id,
            extra=log_extra,
        )

    generator = stream_text_capture(
        client=client,
        user_text=body.text,
        tools=tools,
        thread_id=thread_id,
        run_id=run_id,
        cosmos_manager=cosmos_manager,
        capture_trace_id=capture_trace_id,
    )

    spine_repo = getattr(request.app.state, "spine_repo", None)
    stream = _stream_with_thread_id_persistence(
        generator, cosmos_manager, capture_trace_id
    )
    if spine_repo:
        stream = spine_stream_wrapper(
            stream,
            repo=spine_repo,
            segment_id="classifier",
            operation="classify_text",
            capture_trace_id=capture_trace_id,
            run_id=run_id,
        )

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/api/capture/voice")
async def capture_voice(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
) -> StreamingResponse:
    """Stream voice capture classification as AG-UI SSE events.

    Accepts a multipart audio file upload. The endpoint uploads the audio
    to Blob Storage, then streams the Foundry agent classification result.
    The blob is cleaned up after the stream completes. When the outcome is
    MISUNDERSTOOD, the foundryThreadId is persisted.
    """
    blob_manager = getattr(request.app.state, "blob_manager", None)
    if blob_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Blob storage not configured. Voice capture is unavailable.",
        )

    # Validate and read audio upload
    audio_bytes = await _validate_and_read_audio(file)
    blob_url = await blob_manager.upload_audio(audio_bytes=audio_bytes)

    client = request.app.state.classifier_client
    tools = request.app.state.classifier_agent_tools
    cosmos_manager = request.app.state.cosmos_manager
    thread_id = f"thread-{uuid4()}"
    run_id = f"run-{uuid4()}"
    capture_trace_id = request.headers.get("X-Trace-Id", str(uuid4()))
    request.state.capture_trace_id = capture_trace_id
    log_extra = _capture_extra(capture_trace_id)

    async def stream_with_cleanup_and_persistence():
        """Wrap voice capture with blob cleanup and foundryThreadId persistence."""
        inner = stream_voice_capture(
            client=client,
            blob_url=blob_url,
            tools=tools,
            thread_id=thread_id,
            run_id=run_id,
            cosmos_manager=cosmos_manager,
            capture_trace_id=capture_trace_id,
        )
        try:
            async for event in _stream_with_thread_id_persistence(
                inner, cosmos_manager, capture_trace_id
            ):
                yield event
        finally:
            try:
                await blob_manager.delete_audio(blob_url)
            except Exception:
                logger.warning(
                    "Failed to delete voice blob: %s",
                    blob_url,
                    extra=log_extra,
                )

    spine_repo = getattr(request.app.state, "spine_repo", None)
    stream = stream_with_cleanup_and_persistence()
    if spine_repo:
        stream = spine_stream_wrapper(
            stream,
            repo=spine_repo,
            segment_id="classifier",
            operation="classify_voice",
            capture_trace_id=capture_trace_id,
            run_id=run_id,
        )

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/api/capture/follow-up")
async def follow_up(request: Request, body: FollowUpBody) -> StreamingResponse:
    """Stream a follow-up classification attempt on the same Foundry thread.

    Used for misunderstood captures that need conversational follow-up.
    Reads the original inbox item to get the stored foundryThreadId, then
    streams the follow-up classification with thread reuse. Sets follow-up
    context so file_capture updates the existing misunderstood doc in-place.
    """
    cosmos_manager = request.app.state.cosmos_manager
    inbox_container = cosmos_manager.get_container("Inbox")
    capture_trace_id = request.headers.get("X-Trace-Id", str(uuid4()))
    request.state.capture_trace_id = capture_trace_id

    # Look up the original inbox item to get the Foundry thread ID
    try:
        item = await inbox_container.read_item(
            item=body.inbox_item_id, partition_key="will"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Inbox item {body.inbox_item_id} not found",
        ) from exc

    foundry_thread_id = item.get("foundryThreadId")
    if not foundry_thread_id:
        raise HTTPException(
            status_code=400,
            detail="No thread ID for follow-up. Item may not be misunderstood.",
        )

    client = request.app.state.classifier_client
    tools = request.app.state.classifier_agent_tools
    run_id = f"run-{uuid4()}"

    generator = stream_follow_up_capture(
        client=client,
        follow_up_text=body.follow_up_text,
        foundry_thread_id=foundry_thread_id,
        original_inbox_item_id=body.inbox_item_id,
        tools=tools,
        thread_id=foundry_thread_id,
        run_id=run_id,
        cosmos_manager=cosmos_manager,
        capture_trace_id=capture_trace_id,
    )

    spine_repo = getattr(request.app.state, "spine_repo", None)
    stream = _stream_with_follow_up_context(
        generator, body.inbox_item_id, cosmos_manager, capture_trace_id
    )
    if spine_repo:
        stream = spine_stream_wrapper(
            stream,
            repo=spine_repo,
            segment_id="classifier",
            operation="classify_follow_up",
            capture_trace_id=capture_trace_id,
            run_id=run_id,
            thread_id=foundry_thread_id,
        )

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/api/capture/follow-up/voice")
async def follow_up_voice(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    inbox_item_id: str = Form(...),  # noqa: B008
    follow_up_round: int = Form(1),  # noqa: B008
) -> StreamingResponse:
    """Stream a voice follow-up classification on the same Foundry thread.

    Accepts multipart audio upload with inbox_item_id. Uploads audio to Blob
    Storage for audit trail, transcribes via gpt-4o-transcribe from in-memory
    bytes, then streams the follow-up reclassification with follow-up context
    set so file_capture updates the existing misunderstood doc in-place.
    Blob is cleaned up after the stream completes.
    """
    # Validate blob storage
    blob_manager = getattr(request.app.state, "blob_manager", None)
    if blob_manager is None:
        raise HTTPException(status_code=503, detail="Blob storage not configured.")

    # Validate and read audio upload, then upload to blob for audit trail
    audio_bytes = await _validate_and_read_audio(file)
    blob_url = await blob_manager.upload_audio(audio_bytes=audio_bytes)
    capture_trace_id = request.headers.get("X-Trace-Id", str(uuid4()))
    request.state.capture_trace_id = capture_trace_id
    log_extra = _capture_extra(capture_trace_id)

    # Transcribe from in-memory bytes (no blob re-download)
    openai_client = request.app.state.openai_client
    if openai_client is None:
        raise HTTPException(status_code=503, detail="Transcription not configured.")

    transcript = await openai_client.audio.transcriptions.create(
        model="gpt-4o-transcribe",
        file=("recording.m4a", audio_bytes, "audio/m4a"),
    )
    follow_up_text = transcript.text

    logger.info(
        "Voice follow-up transcribed: round=%d, inbox=%s, text=%s",
        follow_up_round,
        inbox_item_id,
        follow_up_text[:80],
        extra=log_extra,
    )

    # Look up original inbox item for Foundry thread ID
    cosmos_manager = request.app.state.cosmos_manager
    inbox_container = cosmos_manager.get_container("Inbox")

    try:
        item = await inbox_container.read_item(item=inbox_item_id, partition_key="will")
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Inbox item {inbox_item_id} not found",
        ) from exc

    foundry_thread_id = item.get("foundryThreadId")
    if not foundry_thread_id:
        raise HTTPException(
            status_code=400,
            detail="No thread ID for follow-up. Item may not be misunderstood.",
        )

    client = request.app.state.classifier_client
    tools = request.app.state.classifier_agent_tools
    run_id = f"run-{uuid4()}"

    generator = stream_follow_up_capture(
        client=client,
        follow_up_text=follow_up_text,
        foundry_thread_id=foundry_thread_id,
        original_inbox_item_id=inbox_item_id,
        tools=tools,
        thread_id=foundry_thread_id,
        run_id=run_id,
        cosmos_manager=cosmos_manager,
        capture_trace_id=capture_trace_id,
    )

    async def stream_with_cleanup():
        """Wrap follow-up stream with blob cleanup and follow-up context."""
        try:
            async for event in _stream_with_follow_up_context(
                generator, inbox_item_id, cosmos_manager, capture_trace_id
            ):
                yield event
        finally:
            try:
                await blob_manager.delete_audio(blob_url)
            except Exception:
                logger.warning(
                    "Failed to delete voice follow-up blob: %s",
                    blob_url,
                    extra=log_extra,
                )

    spine_repo = getattr(request.app.state, "spine_repo", None)
    stream = stream_with_cleanup()
    if spine_repo:
        stream = spine_stream_wrapper(
            stream,
            repo=spine_repo,
            segment_id="classifier",
            operation="classify_follow_up_voice",
            capture_trace_id=capture_trace_id,
            run_id=run_id,
            thread_id=foundry_thread_id,
        )

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
