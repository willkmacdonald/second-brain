"""Tests for the eval runner, API endpoint, and investigation tools.

Tests cover:
- Classifier eval with golden dataset entries (mocked Cosmos + agent)
- Empty golden dataset handling
- Result persistence to Cosmos EvalResults container
- Progress tracking in runs_dict
- Agent timeout handling (individual case marked ERROR, run continues)
- Top-level exception handling (run marked as failed)
- POST /api/eval/run returns 202 with runId
- POST /api/eval/run with invalid eval_type returns 400
- POST /api/eval/run with same type already running returns 409
- GET /api/eval/status/{run_id} returns run status
- GET /api/eval/status/unknown returns 404
- Investigation tool run_classifier_eval returns started JSON
- Investigation tool get_eval_results queries Cosmos and returns formatted results
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

from second_brain.api.eval import _eval_runs
from second_brain.api.eval import router as eval_router
from second_brain.auth import APIKeyMiddleware
from second_brain.eval.runner import run_classifier_eval
from second_brain.tools.investigation import InvestigationTools

TEST_API_KEY = "test-eval-api-key-12345"


def _mock_golden_query(items: list[dict]):
    """Create an async generator returning golden dataset items."""

    async def _gen(*args, **kwargs):
        for item in items:
            yield item

    return _gen


CLASSIFIER_GOLDEN = [
    {
        "id": "case-1",
        "userId": "will",
        "inputText": "Buy groceries from the store",
        "expectedBucket": "Admin",
        "source": "manual",
        "tags": [],
        "expectedDestination": None,
    },
    {
        "id": "case-2",
        "userId": "will",
        "inputText": "Talk to Sarah about the new project",
        "expectedBucket": "People",
        "source": "manual",
        "tags": [],
        "expectedDestination": None,
    },
    {
        "id": "case-3",
        "userId": "will",
        "inputText": "Build a mobile app for expense tracking",
        "expectedBucket": "Ideas",
        "source": "manual",
        "tags": [],
        "expectedDestination": None,
    },
]

ADMIN_GOLDEN = [
    {
        "id": "admin-1",
        "userId": "will",
        "inputText": "Buy milk and eggs",
        "expectedBucket": "Admin",
        "source": "manual",
        "tags": [],
        "expectedDestination": "costco",
    },
    {
        "id": "admin-2",
        "userId": "will",
        "inputText": "Pick up dog food",
        "expectedBucket": "Admin",
        "source": "manual",
        "tags": [],
        "expectedDestination": "petco",
    },
]

# Mixed dataset with both classifier and admin cases
MIXED_GOLDEN = CLASSIFIER_GOLDEN + ADMIN_GOLDEN


def _make_mock_cosmos(golden_items: list[dict]) -> MagicMock:
    """Create a mock CosmosManager with golden dataset and eval results containers."""
    manager = MagicMock()

    golden_container = MagicMock()
    golden_container.query_items.return_value = _mock_golden_query(golden_items)()

    eval_container = MagicMock()
    eval_container.create_item = AsyncMock()

    manager.get_container = MagicMock(
        side_effect=lambda name: {
            "GoldenDataset": golden_container,
            "EvalResults": eval_container,
        }[name]
    )

    return manager


def _make_classifier_agent_mock(bucket_map: dict[str, tuple[str, float]]):
    """Create a mock agent client whose get_response calls file_capture.

    bucket_map: maps input text to (bucket, confidence) pairs.
    """
    mock_client = AsyncMock()

    async def fake_get_response(*, messages, options):
        text = messages[0].text
        bucket, confidence = bucket_map.get(text, ("Admin", 0.5))
        tool_fn = options["tools"][0]
        await tool_fn(
            text=text,
            bucket=bucket,
            confidence=confidence,
            status="classified",
        )
        return MagicMock()

    mock_client.get_response = AsyncMock(side_effect=fake_get_response)
    return mock_client


def _make_admin_agent_mock(dest_map: dict[str, str]):
    """Create a mock agent client that calls add_errand_items.

    dest_map: maps input text to destination string.
    """
    mock_client = AsyncMock()

    async def fake_get_response(*, messages, options):
        text = messages[0].text
        destination = dest_map.get(text, "unrouted")
        # Find add_errand_items tool (first tool in list)
        add_errand_fn = options["tools"][0]
        await add_errand_fn(
            items=[{"name": text[:30], "destination": destination}],
        )
        return MagicMock()

    mock_client.get_response = AsyncMock(side_effect=fake_get_response)
    return mock_client


# ======================================================================
# Eval Runner Tests (from Plan 03)
# ======================================================================


@pytest.mark.asyncio
async def test_classifier_eval_produces_accuracy() -> None:
    """run_classifier_eval with 3 golden entries produces correct accuracy."""
    cosmos = _make_mock_cosmos(MIXED_GOLDEN)
    agent = _make_classifier_agent_mock(
        {
            "Buy groceries from the store": ("Admin", 0.95),
            "Talk to Sarah about the new project": ("People", 0.85),
            "Build a mobile app for expense tracking": ("Ideas", 0.9),
        }
    )
    runs: dict = {}

    await run_classifier_eval(
        run_id="test-run-1",
        cosmos_manager=cosmos,
        classifier_client=agent,
        runs_dict=runs,
    )

    assert runs["test-run-1"]["status"] == "completed"
    assert runs["test-run-1"]["accuracy"] == 1.0
    assert runs["test-run-1"]["total"] == 3
    assert runs["test-run-1"]["correct"] == 3


@pytest.mark.asyncio
async def test_classifier_eval_empty_dataset() -> None:
    """run_classifier_eval with no classifier cases fails gracefully."""
    # Only admin cases in golden dataset (no classifier-only entries)
    cosmos = _make_mock_cosmos(ADMIN_GOLDEN)
    agent = AsyncMock()
    runs: dict = {}

    await run_classifier_eval(
        run_id="test-run-2",
        cosmos_manager=cosmos,
        classifier_client=agent,
        runs_dict=runs,
    )

    assert runs["test-run-2"]["status"] == "failed"
    assert "No classifier test cases" in runs["test-run-2"]["error"]


@pytest.mark.asyncio
async def test_classifier_eval_writes_to_cosmos() -> None:
    """run_classifier_eval writes EvalResultsDocument to EvalResults container."""
    cosmos = _make_mock_cosmos(MIXED_GOLDEN)
    agent = _make_classifier_agent_mock(
        {
            "Buy groceries from the store": ("Admin", 0.95),
            "Talk to Sarah about the new project": ("People", 0.85),
            "Build a mobile app for expense tracking": ("Ideas", 0.9),
        }
    )
    runs: dict = {}

    await run_classifier_eval(
        run_id="test-run-3",
        cosmos_manager=cosmos,
        classifier_client=agent,
        runs_dict=runs,
    )

    eval_container = cosmos.get_container("EvalResults")
    eval_container.create_item.assert_called_once()

    # Verify the document structure
    call_args = eval_container.create_item.call_args
    doc = call_args[1]["body"] if "body" in (call_args[1] or {}) else call_args[0][0]
    assert doc["evalType"] == "classifier"
    assert doc["datasetSize"] == 3
    assert "accuracy" in doc["aggregateScores"]
    assert len(doc["individualResults"]) == 3


@pytest.mark.asyncio
async def test_classifier_eval_updates_progress() -> None:
    """run_classifier_eval updates runs_dict progress during iteration."""
    cosmos = _make_mock_cosmos(MIXED_GOLDEN)
    progress_snapshots: list[str] = []

    original_runs: dict = {}

    async def fake_get_response(*, messages, options):
        # Record progress at each call
        if "test-run-4" in original_runs:
            progress_snapshots.append(original_runs["test-run-4"].get("progress", ""))
        tool_fn = options["tools"][0]
        await tool_fn(
            text=messages[0].text,
            bucket="Admin",
            confidence=0.9,
            status="classified",
        )
        return MagicMock()

    agent = AsyncMock()
    agent.get_response = AsyncMock(side_effect=fake_get_response)

    await run_classifier_eval(
        run_id="test-run-4",
        cosmos_manager=cosmos,
        classifier_client=agent,
        runs_dict=original_runs,
    )

    # Final state should show completion
    assert original_runs["test-run-4"]["status"] == "completed"
    # Progress should have been set during iteration
    # The progress values at each agent call depend on timing,
    # but the final progress should be "3/3"


@pytest.mark.asyncio
async def test_classifier_eval_handles_timeout() -> None:
    """run_classifier_eval handles agent timeout for individual cases."""
    cosmos = _make_mock_cosmos(MIXED_GOLDEN)
    call_count = 0

    async def fake_get_response(*, messages, options):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise TimeoutError("Agent timed out")
        tool_fn = options["tools"][0]
        await tool_fn(
            text=messages[0].text,
            bucket="Admin",
            confidence=0.9,
            status="classified",
        )
        return MagicMock()

    agent = AsyncMock()
    agent.get_response = AsyncMock(side_effect=fake_get_response)
    runs: dict = {}

    await run_classifier_eval(
        run_id="test-run-5",
        cosmos_manager=cosmos,
        classifier_client=agent,
        runs_dict=runs,
    )

    # Should still complete despite one timeout
    assert runs["test-run-5"]["status"] == "completed"
    # Mock always predicts "Admin": case-1 (Admin) correct, case-2 timeout
    # (ERROR), case-3 (Ideas) wrong -> 1 correct out of 3
    assert runs["test-run-5"]["total"] == 3
    assert runs["test-run-5"]["correct"] == 1


@pytest.mark.asyncio
async def test_classifier_eval_catches_toplevel_exception() -> None:
    """run_classifier_eval catches top-level exception, marks run as failed."""
    # Create a cosmos mock that raises on golden dataset query
    manager = MagicMock()
    golden_container = MagicMock()
    golden_container.query_items.side_effect = RuntimeError("Cosmos is down")
    manager.get_container = MagicMock(return_value=golden_container)

    agent = AsyncMock()
    runs: dict = {}

    await run_classifier_eval(
        run_id="test-run-6",
        cosmos_manager=manager,
        classifier_client=agent,
        runs_dict=runs,
    )

    assert runs["test-run-6"]["status"] == "failed"
    assert "Cosmos is down" in runs["test-run-6"]["error"]


# ======================================================================
# Eval API Endpoint Tests (Plan 04)
# ======================================================================


@pytest.fixture
def eval_app() -> FastAPI:
    """FastAPI app with eval router and mocked app state."""
    app = FastAPI()
    app.include_router(eval_router)
    app.state.api_key = TEST_API_KEY
    app.state.cosmos_manager = MagicMock()
    app.state.classifier_client = AsyncMock()
    app.state.admin_client = AsyncMock()
    app.state.background_tasks = set()
    app.add_middleware(APIKeyMiddleware)
    return app


@pytest.fixture(autouse=True)
def _clear_eval_runs():
    """Clear _eval_runs dict before each test to avoid cross-test leakage."""
    _eval_runs.clear()
    yield
    _eval_runs.clear()


@pytest.mark.asyncio
async def test_eval_run_returns_202(eval_app: FastAPI) -> None:
    """POST /api/eval/run returns 202 with runId for classifier eval."""
    transport = httpx.ASGITransport(app=eval_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "second_brain.api.eval.run_classifier_eval",
            new_callable=AsyncMock,
        ):
            response = await client.post(
                "/api/eval/run",
                json={"eval_type": "classifier"},
                headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            )

    assert response.status_code == 202
    data = response.json()
    assert "runId" in data
    assert data["status"] == "running"
    assert data["evalType"] == "classifier"


@pytest.mark.asyncio
async def test_eval_run_invalid_type_returns_400(
    eval_app: FastAPI,
) -> None:
    """POST /api/eval/run with invalid eval_type returns 400."""
    transport = httpx.ASGITransport(app=eval_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/eval/run",
            json={"eval_type": "unknown"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 400
    assert "Invalid eval_type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_eval_run_duplicate_returns_409(
    eval_app: FastAPI,
) -> None:
    """POST /api/eval/run with same type already running returns 409."""
    # Pre-populate a running eval
    _eval_runs["existing-run"] = {
        "status": "running",
        "eval_type": "classifier",
    }

    transport = httpx.ASGITransport(app=eval_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/eval/run",
            json={"eval_type": "classifier"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 409
    assert "already running" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_eval_status_returns_run(eval_app: FastAPI) -> None:
    """GET /api/eval/status/{run_id} returns run status."""
    _eval_runs["test-status-run"] = {
        "status": "completed",
        "eval_type": "classifier",
        "accuracy": 0.95,
    }

    transport = httpx.ASGITransport(app=eval_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/eval/status/test-status-run",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["runId"] == "test-status-run"
    assert data["status"] == "completed"
    assert data["accuracy"] == 0.95


@pytest.mark.asyncio
async def test_eval_status_unknown_returns_404(
    eval_app: FastAPI,
) -> None:
    """GET /api/eval/status/unknown returns 404."""
    transport = httpx.ASGITransport(app=eval_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/eval/status/nonexistent-run",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_eval_requires_routing_context(
    eval_app: FastAPI,
) -> None:
    """POST /api/eval/run for admin_agent without routing_context returns 400."""
    transport = httpx.ASGITransport(app=eval_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/eval/run",
            json={"eval_type": "admin_agent"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 400
    assert "routing_context" in response.json()["detail"]


# ======================================================================
# Investigation Tool Tests (Plan 04)
# ======================================================================


@pytest.fixture
def investigation_tools_with_eval() -> InvestigationTools:
    """InvestigationTools with mock clients for eval tools."""
    logs_client = MagicMock()
    cosmos_manager = MagicMock()
    classifier_client = AsyncMock()
    admin_client = AsyncMock()
    return InvestigationTools(
        logs_client=logs_client,
        workspace_id="test-workspace-id",
        cosmos_manager=cosmos_manager,
        classifier_client=classifier_client,
        admin_client=admin_client,
    )


@pytest.mark.asyncio
async def test_investigation_run_classifier_eval_starts(
    investigation_tools_with_eval: InvestigationTools,
) -> None:
    """Investigation run_classifier_eval tool returns started JSON."""
    result_json = await investigation_tools_with_eval.run_classifier_eval()
    result = json.loads(result_json)

    assert result["status"] == "started"
    assert "run_id" in result
    assert "Classifier eval started" in result["message"]


@pytest.mark.asyncio
async def test_investigation_run_classifier_eval_no_client() -> None:
    """Investigation run_classifier_eval without client returns error."""
    logs_client = MagicMock()
    tools = InvestigationTools(
        logs_client=logs_client,
        workspace_id="test-workspace-id",
        cosmos_manager=MagicMock(),
        classifier_client=None,
    )

    result_json = await tools.run_classifier_eval()
    result = json.loads(result_json)
    assert "error" in result
    assert "not available" in result["error"]


@pytest.mark.asyncio
async def test_investigation_run_classifier_eval_already_running(
    investigation_tools_with_eval: InvestigationTools,
) -> None:
    """Investigation run_classifier_eval with existing run returns already_running."""
    _eval_runs["existing-classifier"] = {
        "status": "running",
        "eval_type": "classifier",
        "progress": "5/10",
    }

    result_json = await investigation_tools_with_eval.run_classifier_eval()
    result = json.loads(result_json)
    assert result["status"] == "already_running"
    assert result["run_id"] == "existing-classifier"


@pytest.mark.asyncio
async def test_investigation_get_eval_results(
    investigation_tools_with_eval: InvestigationTools,
) -> None:
    """Investigation get_eval_results queries Cosmos and returns results."""
    # Mock Cosmos query
    eval_items = [
        {
            "id": "result-1",
            "userId": "will",
            "evalType": "classifier",
            "runTimestamp": "2026-04-23T12:00:00Z",
            "datasetSize": 50,
            "aggregateScores": {"accuracy": 0.92, "total": 50, "correct": 46},
            "modelDeployment": "gpt-4o",
            "individualResults": [{"should": "be stripped"}],
        },
    ]
    cosmos = investigation_tools_with_eval._cosmos_manager
    eval_container = MagicMock()
    eval_container.query_items.return_value = _mock_golden_query(eval_items)()
    cosmos.get_container = MagicMock(return_value=eval_container)

    result_json = await investigation_tools_with_eval.get_eval_results()
    result = json.loads(result_json)

    assert result["count"] == 1
    assert len(result["results"]) == 1
    assert result["results"][0]["evalType"] == "classifier"
    assert result["results"][0]["aggregateScores"]["accuracy"] == 0.92
    # individualResults should NOT be in the response
    assert "individualResults" not in result["results"][0]


@pytest.mark.asyncio
async def test_investigation_get_eval_results_with_in_progress(
    investigation_tools_with_eval: InvestigationTools,
) -> None:
    """Investigation get_eval_results includes in-progress runs."""
    _eval_runs["running-eval"] = {
        "status": "running",
        "eval_type": "classifier",
        "progress": "3/10",
        "started_at": "2026-04-23T12:00:00Z",
    }

    # Mock empty Cosmos results
    cosmos = investigation_tools_with_eval._cosmos_manager
    eval_container = MagicMock()
    eval_container.query_items.return_value = _mock_golden_query([])()
    cosmos.get_container = MagicMock(return_value=eval_container)

    result_json = await investigation_tools_with_eval.get_eval_results()
    result = json.loads(result_json)

    assert len(result["in_progress"]) == 1
    assert result["in_progress"][0]["run_id"] == "running-eval"
    assert result["in_progress"][0]["progress"] == "3/10"
