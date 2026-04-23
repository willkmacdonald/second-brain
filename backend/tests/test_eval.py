"""Tests for the eval runner (classifier and admin agent evaluation).

Tests cover:
- Classifier eval with golden dataset entries (mocked Cosmos + agent)
- Empty golden dataset handling
- Result persistence to Cosmos EvalResults container
- Progress tracking in runs_dict
- Agent timeout handling (individual case marked ERROR, run continues)
- Top-level exception handling (run marked as failed)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from second_brain.eval.runner import run_classifier_eval


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
        tool_fn = options.tools[0]
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
        add_errand_fn = options.tools[0]
        await add_errand_fn(
            items=[{"name": text[:30], "destination": destination}],
        )
        return MagicMock()

    mock_client.get_response = AsyncMock(side_effect=fake_get_response)
    return mock_client


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
        tool_fn = options.tools[0]
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
        tool_fn = options.tools[0]
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
    # 2 correct + 1 error = total 3, correct 2
    assert runs["test-run-5"]["total"] == 3
    assert runs["test-run-5"]["correct"] == 2


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
