"""Capture API endpoint -- unified text and voice capture with SSE streaming.

POST /api/capture  -- text capture (JSON body)
POST /api/capture/voice -- voice capture (multipart file upload)
POST /api/capture/follow-up -- follow-up for misunderstood captures (SSE)

Both capture endpoints stream Foundry agent classification results as
AG-UI-compatible SSE events. The mobile Expo app consumes these via
react-native-sse EventSource.
"""

import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from second_brain.streaming.adapter import (
    stream_follow_up_capture,
    stream_text_capture,
    stream_voice_capture,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Capture"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class TextCaptureBody(BaseModel):
    """Request body for text capture."""

    text: str
    thread_id: str | None = None
    run_id: str | None = None


class FollowUpBody(BaseModel):
    """Request body for follow-up capture (misunderstood re-classification)."""

    inbox_item_id: str
    follow_up_text: str
    follow_up_round: int = 1


async def _stream_with_thread_id_persistence(
    inner_generator,
    cosmos_manager,
):
    """Wrap a capture stream generator to persist foundryThreadId on MISUNDERSTOOD.

    Yields all SSE events through to the client. After the inner generator
    completes, if a MISUNDERSTOOD event was detected, upserts the
    foundryThreadId to the inbox document in Cosmos.
    """
    misunderstood_item_id: str | None = None
    foundry_conversation_id: str | None = None

    async for event in inner_generator:
        yield event

        # Intercept MISUNDERSTOOD events to extract IDs for persistence
        if event.startswith("data: "):
            try:
                payload = json.loads(event[6:].strip())
                if payload.get("type") == "MISUNDERSTOOD":
                    value = payload.get("value", {})
                    misunderstood_item_id = value.get("inboxItemId")
                    foundry_conversation_id = value.get("foundryConversationId")
            except (json.JSONDecodeError, AttributeError):
                pass

    # After stream completes, persist foundryThreadId if MISUNDERSTOOD was detected
    if misunderstood_item_id and foundry_conversation_id:
        try:
            inbox_container = cosmos_manager.get_container("Inbox")
            doc = await inbox_container.read_item(
                item=misunderstood_item_id, partition_key="will"
            )
            doc["foundryThreadId"] = foundry_conversation_id
            await inbox_container.upsert_item(body=doc)
            logger.info(
                "Persisted foundryThreadId=%s for inbox item %s",
                foundry_conversation_id,
                misunderstood_item_id,
            )
        except Exception:
            logger.warning(
                "Failed to persist foundryThreadId for %s",
                misunderstood_item_id,
            )


async def _stream_with_reconciliation(
    inner_generator,
    cosmos_manager,
    original_inbox_id: str,
):
    """Wrap follow-up stream to reconcile orphan inbox documents on CLASSIFIED.

    Yields all SSE events through to the client. After the inner generator
    completes, if a CLASSIFIED result was detected:
    1. Read the new inbox doc by its item_id
    2. Copy classificationMeta and filedRecordId to the original inbox doc
    3. Update original's status to "classified", set updatedAt
    4. Upsert the original
    5. Update the bucket doc's inboxRecordId to point to the original inbox ID
    6. Delete the orphan new inbox doc

    If MISUNDERSTOOD again, update the foundryThreadId on the original doc.
    """
    new_item_id: str | None = None
    is_classified = False
    foundry_conversation_id: str | None = None
    is_misunderstood = False

    async for event in inner_generator:
        yield event

        # Parse SSE events to detect outcome
        if event.startswith("data: "):
            try:
                payload = json.loads(event[6:].strip())
                event_type = payload.get("type")

                if event_type == "CLASSIFIED":
                    value = payload.get("value", {})
                    new_item_id = value.get("inboxItemId")
                    is_classified = True

                elif event_type == "MISUNDERSTOOD":
                    value = payload.get("value", {})
                    foundry_conversation_id = value.get("foundryConversationId")
                    is_misunderstood = True

            except (json.JSONDecodeError, AttributeError):
                pass

    # Reconciliation after stream completes
    if is_classified and new_item_id:
        try:
            inbox_container = cosmos_manager.get_container("Inbox")

            # Read the new doc created by file_capture
            new_doc = await inbox_container.read_item(
                item=new_item_id, partition_key="will"
            )

            # Read the original misunderstood doc
            original_doc = await inbox_container.read_item(
                item=original_inbox_id, partition_key="will"
            )

            # Copy classification to original
            original_doc["classificationMeta"] = new_doc.get("classificationMeta")
            original_doc["filedRecordId"] = new_doc.get("filedRecordId")
            original_doc["status"] = "classified"
            original_doc["updatedAt"] = datetime.now(UTC).isoformat()
            await inbox_container.upsert_item(body=original_doc)

            # Update bucket doc's inboxRecordId to point to original
            bucket = (new_doc.get("classificationMeta") or {}).get("bucket")
            filed_id = new_doc.get("filedRecordId")
            if bucket and filed_id:
                try:
                    bucket_container = cosmos_manager.get_container(bucket)
                    bucket_doc = await bucket_container.read_item(
                        item=filed_id, partition_key="will"
                    )
                    bucket_doc["inboxRecordId"] = original_inbox_id
                    await bucket_container.upsert_item(body=bucket_doc)
                except Exception:
                    logger.warning(
                        "Failed to update bucket doc %s inboxRecordId", filed_id
                    )

            # Delete orphan inbox doc
            try:
                await inbox_container.delete_item(
                    item=new_item_id, partition_key="will"
                )
            except Exception:
                logger.warning("Failed to delete orphan inbox doc %s", new_item_id)

            logger.info(
                "Reconciled follow-up: original=%s, orphan=%s deleted",
                original_inbox_id,
                new_item_id,
            )
        except Exception:
            logger.warning(
                "Follow-up reconciliation failed for original=%s, new=%s",
                original_inbox_id,
                new_item_id,
                exc_info=True,
            )

    elif is_misunderstood and foundry_conversation_id:
        # Follow-up resulted in MISUNDERSTOOD again -- update foundryThreadId
        try:
            inbox_container = cosmos_manager.get_container("Inbox")
            doc = await inbox_container.read_item(
                item=original_inbox_id, partition_key="will"
            )
            doc["foundryThreadId"] = foundry_conversation_id
            await inbox_container.upsert_item(body=doc)
            logger.info(
                "Updated foundryThreadId=%s for ongoing follow-up on %s",
                foundry_conversation_id,
                original_inbox_id,
            )
        except Exception:
            logger.warning(
                "Failed to update foundryThreadId on follow-up for %s",
                original_inbox_id,
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

    generator = stream_text_capture(
        client=client,
        user_text=body.text,
        tools=tools,
        thread_id=thread_id,
        run_id=run_id,
    )

    return StreamingResponse(
        _stream_with_thread_id_persistence(generator, cosmos_manager),
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

    # Upload audio to blob storage
    audio_bytes = await file.read()
    blob_url = await blob_manager.upload_audio(
        audio_bytes=audio_bytes,
        filename=file.filename or "voice-capture.m4a",
    )

    client = request.app.state.classifier_client
    tools = request.app.state.classifier_agent_tools
    cosmos_manager = request.app.state.cosmos_manager
    thread_id = f"thread-{uuid4()}"
    run_id = f"run-{uuid4()}"

    async def stream_with_cleanup_and_persistence():
        """Wrap voice capture with blob cleanup and foundryThreadId persistence."""
        inner = stream_voice_capture(
            client=client,
            blob_url=blob_url,
            tools=tools,
            thread_id=thread_id,
            run_id=run_id,
        )
        try:
            async for event in _stream_with_thread_id_persistence(
                inner, cosmos_manager
            ):
                yield event
        finally:
            try:
                await blob_manager.delete_audio(blob_url)
            except Exception:
                logger.warning("Failed to delete voice blob: %s", blob_url)

    return StreamingResponse(
        stream_with_cleanup_and_persistence(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/api/capture/follow-up")
async def follow_up(request: Request, body: FollowUpBody) -> StreamingResponse:
    """Stream a follow-up classification attempt on the same Foundry thread.

    Used for misunderstood captures that need conversational follow-up.
    Reads the original inbox item to get the stored foundryThreadId, then
    streams the follow-up classification with thread reuse. If the follow-up
    results in CLASSIFIED, reconciles the orphan inbox document.
    """
    cosmos_manager = request.app.state.cosmos_manager
    inbox_container = cosmos_manager.get_container("Inbox")

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
    )

    return StreamingResponse(
        _stream_with_reconciliation(
            generator, cosmos_manager, body.inbox_item_id
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
