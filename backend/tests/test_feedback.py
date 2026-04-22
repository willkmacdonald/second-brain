"""Tests for feedback signal infrastructure.

Covers:
- POST /api/feedback explicit thumbs up/down endpoint (FEED-02)
- Inline feedback signal emission from recategorize, HITL, errand handlers (FEED-01)
- Investigation tool tests for query_feedback_signals
  and promote_to_golden_dataset (FEED-03, FEED-04)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from second_brain.api.feedback import router as feedback_router
from second_brain.api.inbox import router as inbox_router
from second_brain.auth import APIKeyMiddleware
from second_brain.tools.investigation import InvestigationTools

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


# ---------------------------------------------------------------------------
# Investigation tool tests for feedback signals (FEED-03, FEED-04)
# ---------------------------------------------------------------------------

SAMPLE_FEEDBACK_SIGNALS = [
    {
        "id": "sig-1",
        "userId": "will",
        "signalType": "recategorize",
        "captureText": "Buy milk at store",
        "originalBucket": "Ideas",
        "correctedBucket": "Admin",
        "captureTraceId": "trace-abc",
        "createdAt": "2026-04-20T10:00:00Z",
    },
    {
        "id": "sig-2",
        "userId": "will",
        "signalType": "thumbs_up",
        "captureText": "Call dentist tomorrow",
        "originalBucket": "Admin",
        "correctedBucket": None,
        "captureTraceId": "trace-def",
        "createdAt": "2026-04-20T11:00:00Z",
    },
    {
        "id": "sig-3",
        "userId": "will",
        "signalType": "recategorize",
        "captureText": "Pick up dry cleaning",
        "originalBucket": "Ideas",
        "correctedBucket": "Admin",
        "captureTraceId": "trace-ghi",
        "createdAt": "2026-04-20T12:00:00Z",
    },
]


@pytest.fixture
def investigation_tools(mock_cosmos_manager: MagicMock) -> InvestigationTools:
    """InvestigationTools with mock LogsQueryClient and mock cosmos_manager."""
    logs_client = MagicMock()
    return InvestigationTools(
        logs_client=logs_client,
        workspace_id="test-workspace-id",
        cosmos_manager=mock_cosmos_manager,
    )


@pytest.fixture
def investigation_tools_no_cosmos() -> InvestigationTools:
    """InvestigationTools without cosmos_manager."""
    logs_client = MagicMock()
    return InvestigationTools(
        logs_client=logs_client,
        workspace_id="test-workspace-id",
    )


def _mock_feedback_query(signals: list[dict]):
    """Create an async generator returning the given signals."""

    async def _gen(*args, **kwargs):
        for item in signals:
            yield item

    return _gen


@pytest.mark.asyncio
async def test_query_feedback_signals_no_filters(
    investigation_tools: InvestigationTools,
    mock_cosmos_manager: MagicMock,
) -> None:
    """query_feedback_signals with no filters returns recent signals as JSON."""
    import json

    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.query_items.return_value = _mock_feedback_query(
        SAMPLE_FEEDBACK_SIGNALS
    )()

    result = await investigation_tools.query_feedback_signals()
    data = json.loads(result)

    assert "signals" in data
    assert len(data["signals"]) == 3
    assert data["total"] == 3
    # Each signal should have expected fields
    sig = data["signals"][0]
    assert "signalType" in sig
    assert "captureText" in sig
    assert "originalBucket" in sig


@pytest.mark.asyncio
async def test_query_feedback_signals_filter_recategorize(
    investigation_tools: InvestigationTools,
    mock_cosmos_manager: MagicMock,
) -> None:
    """query_feedback_signals with signal_type='recategorize' filters correctly."""
    import json

    recategorize_only = [
        s for s in SAMPLE_FEEDBACK_SIGNALS if s["signalType"] == "recategorize"
    ]
    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.query_items.return_value = _mock_feedback_query(
        recategorize_only
    )()

    result = await investigation_tools.query_feedback_signals(
        signal_type="recategorize"
    )
    data = json.loads(result)

    assert len(data["signals"]) == 2
    # Check the query included signalType filter
    call_args = feedback_container.query_items.call_args
    query_str = call_args[1].get("query", "") or call_args[0][0] if call_args[0] else ""
    assert "signalType" in query_str


@pytest.mark.asyncio
async def test_query_feedback_signals_misclassification_summary(
    investigation_tools: InvestigationTools,
    mock_cosmos_manager: MagicMock,
) -> None:
    """query_feedback_signals includes misclassification_summary
    for recategorize signals."""
    import json

    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.query_items.return_value = _mock_feedback_query(
        SAMPLE_FEEDBACK_SIGNALS
    )()

    result = await investigation_tools.query_feedback_signals()
    data = json.loads(result)

    assert "misclassification_summary" in data
    summary = data["misclassification_summary"]
    # Two recategorize signals: Ideas -> Admin (x2)
    assert "Ideas -> Admin" in summary
    assert summary["Ideas -> Admin"] == 2


@pytest.mark.asyncio
async def test_query_feedback_signals_no_cosmos(
    investigation_tools_no_cosmos: InvestigationTools,
) -> None:
    """query_feedback_signals with cosmos_manager=None returns JSON error."""
    import json

    result = await investigation_tools_no_cosmos.query_feedback_signals()
    data = json.loads(result)
    assert "error" in data
    assert (
        "unavailable" in data["error"].lower()
        or "not configured" in data["error"].lower()
    )


@pytest.mark.asyncio
async def test_promote_to_golden_dataset_preview(
    investigation_tools: InvestigationTools,
    mock_cosmos_manager: MagicMock,
) -> None:
    """promote_to_golden_dataset with confirm=False returns preview."""
    import json

    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.read_item = AsyncMock(return_value=SAMPLE_FEEDBACK_SIGNALS[0])

    result = await investigation_tools.promote_to_golden_dataset(
        signal_id="sig-1", confirm=False
    )
    data = json.loads(result)

    assert "preview" in data or "captureText" in data
    # Should NOT write to GoldenDataset
    golden_container = mock_cosmos_manager.get_container("GoldenDataset")
    golden_container.create_item.assert_not_called()


@pytest.mark.asyncio
async def test_promote_to_golden_dataset_confirm(
    investigation_tools: InvestigationTools,
    mock_cosmos_manager: MagicMock,
) -> None:
    """promote_to_golden_dataset with confirm=True writes GoldenDatasetDocument."""
    import json

    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.read_item = AsyncMock(return_value=SAMPLE_FEEDBACK_SIGNALS[0])

    result = await investigation_tools.promote_to_golden_dataset(
        signal_id="sig-1", confirm=True
    )
    data = json.loads(result)

    assert "success" in data or "id" in data

    golden_container = mock_cosmos_manager.get_container("GoldenDataset")
    golden_container.create_item.assert_called_once()
    written = golden_container.create_item.call_args[1]["body"]
    assert written["source"] == "promoted_feedback"
    assert written["inputText"] == "Buy milk at store"
    assert written["expectedBucket"] == "Admin"  # correctedBucket from signal


@pytest.mark.asyncio
async def test_promote_to_golden_dataset_not_found(
    investigation_tools: InvestigationTools,
    mock_cosmos_manager: MagicMock,
) -> None:
    """promote_to_golden_dataset with nonexistent signal returns JSON error."""
    import json

    from azure.cosmos.exceptions import CosmosResourceNotFoundError

    feedback_container = mock_cosmos_manager.get_container("Feedback")
    feedback_container.read_item = AsyncMock(
        side_effect=CosmosResourceNotFoundError(status_code=404, message="Not found")
    )

    result = await investigation_tools.promote_to_golden_dataset(
        signal_id="nonexistent", confirm=False
    )
    data = json.loads(result)
    assert "error" in data
    assert "not found" in data["error"].lower()


# ---------------------------------------------------------------------------
# Non-fatal signal emission test (FEED-01 continued)
# ---------------------------------------------------------------------------


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
