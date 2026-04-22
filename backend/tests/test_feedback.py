"""Tests for feedback signal infrastructure.

Covers:
- POST /api/feedback explicit thumbs up/down endpoint (FEED-02)
- Inline feedback signal emission from recategorize, HITL, errand handlers (FEED-01)
"""

from unittest.mock import AsyncMock, MagicMock

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


# ---------------------------------------------------------------------------
# Implicit signal emission tests (FEED-01)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recategorize_emits_feedback(
    feedback_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """Recategorize to a different bucket emits signalType=recategorize."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.return_value = {**SAMPLE_CLASSIFIED_ITEM}

    transport = httpx.ASGITransport(app=feedback_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/api/inbox/inbox-100/recategorize",
            json={"new_bucket": "Projects"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200

    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.create_item.assert_called_once()
    written = feedback_container.create_item.call_args[1]["body"]
    assert written["signalType"] == "recategorize"
    assert written["originalBucket"] == "Ideas"
    assert written["correctedBucket"] == "Projects"
    assert written["captureText"] == "Build the new dashboard feature"
    assert written["captureTraceId"] == "trace-abc-123"


@pytest.mark.asyncio
async def test_hitl_bucket_emits_feedback(
    feedback_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """HITL same-bucket pick on pending item emits signalType=hitl_bucket."""
    pending_item = {
        **SAMPLE_CLASSIFIED_ITEM,
        "id": "inbox-300",
        "status": "pending",
        "classificationMeta": {
            **SAMPLE_CLASSIFIED_ITEM["classificationMeta"],
            "bucket": "Admin",
            "confidence": 0.45,
        },
    }
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.return_value = {**pending_item}

    transport = httpx.ASGITransport(app=feedback_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/api/inbox/inbox-300/recategorize",
            json={"new_bucket": "Admin"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200

    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.create_item.assert_called_once()
    written = feedback_container.create_item.call_args[1]["body"]
    assert written["signalType"] == "hitl_bucket"
    assert written["originalBucket"] == "Admin"
    assert written["correctedBucket"] is None


@pytest.mark.asyncio
async def test_errand_reroute_emits_feedback(
    mock_cosmos_manager: MagicMock,
) -> None:
    """Routing an unrouted errand emits signalType=errand_reroute."""
    from second_brain.api.errands import router as errands_router

    app = FastAPI()
    app.include_router(errands_router)
    app.state.api_key = TEST_API_KEY
    app.state.cosmos_manager = mock_cosmos_manager
    app.add_middleware(APIKeyMiddleware)

    # Set up errands container mock
    errands_container = mock_cosmos_manager.get_container("Errands")
    errands_container.read_item.return_value = {
        "id": "errand-1",
        "name": "Buy groceries",
        "destination": "unrouted",
    }

    # Set up destinations container mock with async generator
    dest_container = mock_cosmos_manager.get_container("Destinations")

    async def mock_dest_query(*args, **kwargs):
        yield {"slug": "costco"}

    dest_container.query_items.return_value = mock_dest_query()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/errands/errand-1/route",
            json={
                "destinationSlug": "costco",
                "saveRule": False,
            },
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200

    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.create_item.assert_called_once()
    written = feedback_container.create_item.call_args[1]["body"]
    assert written["signalType"] == "errand_reroute"
    assert written["originalBucket"] == "unrouted"
    assert written["correctedBucket"] == "costco"
    assert written["captureText"] == "Buy groceries"


@pytest.mark.asyncio
async def test_signal_failure_nonfatal(
    feedback_app: FastAPI,
    mock_cosmos_manager: MagicMock,
) -> None:
    """Feedback write failure does not block primary recategorize action."""
    inbox_container = mock_cosmos_manager.get_container("Inbox")
    inbox_container.read_item.return_value = {**SAMPLE_CLASSIFIED_ITEM}

    # Make feedback container fail
    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.create_item = AsyncMock(
        side_effect=RuntimeError("Cosmos timeout")
    )

    transport = httpx.ASGITransport(app=feedback_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/api/inbox/inbox-100/recategorize",
            json={"new_bucket": "Projects"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    # Primary action succeeds despite feedback write failure
    assert response.status_code == 200
    data = response.json()
    assert data["classificationMeta"]["bucket"] == "Projects"

    # New bucket doc was still created
    projects_container = mock_cosmos_manager.get_container("Projects")
    projects_container.create_item.assert_called_once()
