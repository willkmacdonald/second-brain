"""Capture API endpoint -- unified text and voice capture with SSE streaming.

POST /api/capture  -- text capture (JSON body)
POST /api/capture/voice -- voice capture (multipart file upload)

Both endpoints stream Foundry agent classification results as AG-UI-compatible
SSE events. The mobile Expo app consumes these via react-native-sse EventSource.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from second_brain.streaming.adapter import stream_text_capture, stream_voice_capture

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


@router.post("/api/capture")
async def capture(request: Request, body: TextCaptureBody) -> StreamingResponse:
    """Stream text capture classification as AG-UI SSE events.

    Accepts a JSON body with the capture text, streams the Foundry agent
    classification result as SSE events (STEP_START, STEP_END, CLASSIFIED/
    MISUNDERSTOOD/UNRESOLVED, COMPLETE).
    """
    client = request.app.state.classifier_client
    tools = request.app.state.classifier_agent_tools
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
        generator,
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
    The blob is cleaned up after the stream completes.
    """
    blob_manager = getattr(request.app.state, "blob_manager", None)
    if blob_manager is None:
        from fastapi import HTTPException

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
    thread_id = f"thread-{uuid4()}"
    run_id = f"run-{uuid4()}"

    async def stream_with_cleanup():
        """Wrap the voice capture stream with blob cleanup on completion."""
        try:
            async for event in stream_voice_capture(
                client=client,
                blob_url=blob_url,
                tools=tools,
                thread_id=thread_id,
                run_id=run_id,
            ):
                yield event
        finally:
            try:
                await blob_manager.delete_audio(blob_url)
            except Exception:
                logger.warning("Failed to delete voice blob: %s", blob_url)

    return StreamingResponse(
        stream_with_cleanup(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
