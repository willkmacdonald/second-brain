"""Tests for feedback signal infrastructure.

Covers:
- POST /api/feedback explicit thumbs up/down endpoint (FEED-02)
- Inline feedback signal emission from recategorize, HITL, errand handlers (FEED-01)
"""

from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI

from second_brain.api.feedback import router as feedback_router
from second_brain.api.inbox import router as inbox_router
from second_brain.auth import APIKeyMiddleware

TEST_API_KEY = "test-api-key-12345"

SAMPLE_CLASSIFIED_ITEM = {
    "id": "inbox-100",
    "userId": "will",
    "rawText": "Build the new dashboard feature",
    "title": "Dashboard feature",
    "status": "classified",
    "createdAt": "2026-02-23T10:00:00Z",
    "updatedAt": "2026-02-23T10:00:00Z",
    "filedRecordId": "old-bucket-doc-id",
    "captureTraceId": "trace-abc-123",
    "classificationMeta": {
        "bucket": "Ideas",
        "confidence": 0.72,
        "allScores": {
            "People": 0.05,
            "Projects": 0.20,
            "Ideas": 0.72,
            "Admin": 0.03,
        },
        "classifiedBy": "Classifier",
        "agentChain": ["Orchestrator", "Classifier"],
        "classifiedAt": "2026-02-23T10:00:00Z",
    },
}


@pytest.fixture
def feedback_app(mock_cosmos_manager: MagicMock) -> FastAPI:
    """Create a FastAPI app with feedback and inbox routers plus mock Cosmos."""
    app = FastAPI()
    app.include_router(feedback_router)
    app.include_router(inbox_router)
    app.state.api_key = TEST_API_KEY
    app.state.cosmos_manager = mock_cosmos_manager
    app.add_middleware(APIKeyMiddleware)
    return app


# ---------------------------------------------------------------------------
# Explicit feedback endpoint tests (FEED-02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explicit_feedback_thumbs_up(
    feedback_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /api/feedback with thumbs_up writes FeedbackDocument and returns 201."""
    transport = httpx.ASGITransport(app=feedback_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/feedback",
            json={
                "inboxItemId": "inbox-100",
                "signalType": "thumbs_up",
                "captureText": "Buy milk",
                "originalBucket": "Admin",
            },
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "recorded"
    assert "id" in data

    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.create_item.assert_called_once()
    written = feedback_container.create_item.call_args[1]["body"]
    assert written["signalType"] == "thumbs_up"
    assert written["captureText"] == "Buy milk"
    assert written["originalBucket"] == "Admin"
    assert written["correctedBucket"] is None


@pytest.mark.asyncio
async def test_explicit_feedback_thumbs_down(
    feedback_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /api/feedback with thumbs_down writes FeedbackDocument and returns 201."""
    transport = httpx.ASGITransport(app=feedback_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/feedback",
            json={
                "inboxItemId": "inbox-100",
                "signalType": "thumbs_down",
                "captureText": "Buy milk",
                "originalBucket": "Admin",
                "captureTraceId": "trace-abc-123",
            },
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "recorded"

    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.create_item.assert_called_once()
    written = feedback_container.create_item.call_args[1]["body"]
    assert written["signalType"] == "thumbs_down"
    assert written["correctedBucket"] is None
    assert written["captureTraceId"] == "trace-abc-123"


@pytest.mark.asyncio
async def test_explicit_feedback_invalid_type(
    feedback_app: FastAPI,
) -> None:
    """POST /api/feedback with invalid signalType returns 400."""
    transport = httpx.ASGITransport(app=feedback_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/feedback",
            json={
                "inboxItemId": "inbox-100",
                "signalType": "invalid_type",
                "captureText": "Buy milk",
                "originalBucket": "Admin",
            },
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 400
    assert "Invalid signal type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_explicit_feedback_no_auth(
    feedback_app: FastAPI,
) -> None:
    """POST /api/feedback without auth header returns 401."""
    transport = httpx.ASGITransport(app=feedback_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/feedback",
            json={
                "inboxItemId": "inbox-100",
                "signalType": "thumbs_up",
                "captureText": "Buy milk",
                "originalBucket": "Admin",
            },
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_explicit_feedback_cosmos_unavailable(
    mock_cosmos_manager: MagicMock,
) -> None:
    """POST /api/feedback when Cosmos unavailable returns 503."""
    app = FastAPI()
    app.include_router(feedback_router)
    app.state.api_key = TEST_API_KEY
    # Deliberately NOT setting app.state.cosmos_manager
    app.add_middleware(APIKeyMiddleware)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/feedback",
            json={
                "inboxItemId": "inbox-100",
                "signalType": "thumbs_up",
                "captureText": "Buy milk",
                "originalBucket": "Admin",
            },
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 503
