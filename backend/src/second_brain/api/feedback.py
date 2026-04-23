"""Feedback API endpoint for explicit thumbs up/down signals."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from second_brain.models.documents import FeedbackDocument

logger = logging.getLogger(__name__)

router = APIRouter()


class FeedbackRequest(BaseModel):
    """Request body for explicit feedback (thumbs up/down)."""

    inboxItemId: str  # noqa: N815
    signalType: str  # "thumbs_up" or "thumbs_down"  # noqa: N815
    captureText: str  # noqa: N815
    originalBucket: str  # noqa: N815
    captureTraceId: str | None = None  # noqa: N815


@router.post("/api/feedback", status_code=201)
async def submit_feedback(request: Request, body: FeedbackRequest) -> dict:
    """Record explicit user feedback on a classification."""
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(status_code=503, detail="Cosmos DB not configured.")

    if body.signalType not in ("thumbs_up", "thumbs_down"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid signal type '{body.signalType}'."
                " Must be 'thumbs_up' or 'thumbs_down'."
            ),
        )

    feedback_doc = FeedbackDocument(
        signalType=body.signalType,
        captureText=body.captureText,
        originalBucket=body.originalBucket,
        correctedBucket=None,  # thumbs don't have corrected bucket
        captureTraceId=body.captureTraceId,
    )

    try:
        container = cosmos_manager.get_container("Feedback")
        await container.create_item(body=feedback_doc.model_dump(mode="json"))
    except Exception:
        logger.warning("Failed to write feedback document", exc_info=True)
        raise HTTPException(
            status_code=503, detail="Failed to record feedback."
        ) from None

    return {"status": "recorded", "id": feedback_doc.id}
