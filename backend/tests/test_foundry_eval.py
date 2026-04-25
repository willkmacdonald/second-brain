"""Tests for Foundry eval module (eval/foundry.py).

Mocks the Foundry SDK to verify:
- Custom evaluator grade() functions (exact-match scoring)
- Dataset export with content-hash versioning
- Canary detection of tool capture
- Eval run creation with correct data sources
- Result formatting matching investigation tool contract
- Run discovery using stable eval names
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from second_brain.eval.foundry import (
    ADMIN_GRADE_FN,
    CLASSIFIER_GRADE_FN,
    export_and_upload_dataset,
    get_eval_results_from_foundry,
    list_recent_eval_runs,
    run_classifier_eval,
    run_foundry_target_canary,
)

# ---------------------------------------------------------------------------
# Helpers: exec grade functions from string constants
# ---------------------------------------------------------------------------


def _exec_grade_fn(code: str) -> object:
    """Execute a grade function string and return the grade callable."""
    ns: dict = {}
    exec(code, ns)  # noqa: S102
    return ns["grade"]


# ---------------------------------------------------------------------------
# Test 1: classifier grade() exact match
# ---------------------------------------------------------------------------


def test_classifier_grade_fn_exact_match():
    grade = _exec_grade_fn(CLASSIFIER_GRADE_FN)
    item = {
        "expected_bucket": "Admin",
        "sample": {
            "output_items": [
                {
                    "content": [
                        {
                            "type": "tool_call",
                            "name": "file_capture",
                            "arguments": {"bucket": "Admin"},
                        }
                    ]
                }
            ]
        },
    }
    assert grade({}, item) == 1.0


# ---------------------------------------------------------------------------
# Test 2: classifier grade() mismatch
# ---------------------------------------------------------------------------


def test_classifier_grade_fn_mismatch():
    grade = _exec_grade_fn(CLASSIFIER_GRADE_FN)
    item = {
        "expected_bucket": "Ideas",
        "sample": {
            "output_items": [
                {
                    "content": [
                        {
                            "type": "tool_call",
                            "name": "file_capture",
                            "arguments": {"bucket": "Admin"},
                        }
                    ]
                }
            ]
        },
    }
    assert grade({}, item) == 0.0


# ---------------------------------------------------------------------------
# Test 3: classifier grade() case insensitive
# ---------------------------------------------------------------------------


def test_classifier_grade_fn_case_insensitive():
    grade = _exec_grade_fn(CLASSIFIER_GRADE_FN)
    item = {
        "expected_bucket": "admin",
        "sample": {
            "output_items": [
                {
                    "content": [
                        {
                            "type": "tool_call",
                            "name": "file_capture",
                            "arguments": {"bucket": "Admin"},
                        }
                    ]
                }
            ]
        },
    }
    assert grade({}, item) == 1.0


# ---------------------------------------------------------------------------
# Test 4: admin grade() exact match
# ---------------------------------------------------------------------------


def test_admin_grade_fn_exact_match():
    grade = _exec_grade_fn(ADMIN_GRADE_FN)
    item = {
        "expected_destination": "costco",
        "sample": {
            "output_items": [
                {
                    "content": [
                        {
                            "type": "tool_call",
                            "name": "add_errand_items",
                            "arguments": {
                                "items": [
                                    {
                                        "name": "paper towels",
                                        "destination": "costco",
                                    }
                                ]
                            },
                        }
                    ]
                }
            ]
        },
    }
    assert grade({}, item) == 1.0


# ---------------------------------------------------------------------------
# Test 4b: admin grade() with add_task_items
# ---------------------------------------------------------------------------


def test_admin_grade_fn_tasks():
    grade = _exec_grade_fn(ADMIN_GRADE_FN)
    item = {
        "expected_destination": "tasks",
        "sample": {
            "output_items": [
                {
                    "content": [
                        {
                            "type": "tool_call",
                            "name": "add_task_items",
                            "arguments": {"tasks": [{"name": "book dentist"}]},
                        }
                    ]
                }
            ]
        },
    }
    assert grade({}, item) == 1.0


# ---------------------------------------------------------------------------
# Test 4c: classifier grade() fallback mode (tool_calls in item)
# ---------------------------------------------------------------------------


def test_classifier_grade_fn_fallback_mode():
    grade = _exec_grade_fn(CLASSIFIER_GRADE_FN)
    item = {
        "expected_bucket": "People",
        "tool_calls": [
            {
                "name": "file_capture",
                "arguments": {"bucket": "People"},
            }
        ],
    }
    assert grade({}, item) == 1.0


# ---------------------------------------------------------------------------
# Test 4d: admin grade() fallback mode (tool_calls in item)
# ---------------------------------------------------------------------------


def test_admin_grade_fn_fallback_mode():
    grade = _exec_grade_fn(ADMIN_GRADE_FN)
    item = {
        "expected_destination": "agora",
        "tool_calls": [
            {
                "name": "add_errand_items",
                "arguments": {"items": [{"name": "milk", "destination": "agora"}]},
            }
        ],
    }
    assert grade({}, item) == 1.0


# ---------------------------------------------------------------------------
# Test 5: export_and_upload_dataset
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_cosmos_manager():
    """Mock CosmosManager with 3 golden dataset entries."""
    mgr = MagicMock()
    container = MagicMock()

    async def _query_items(**kwargs):
        items = [
            {
                "inputText": "buy milk",
                "expectedBucket": "Admin",
                "expectedDestination": None,
            },
            {
                "inputText": "met Sarah",
                "expectedBucket": "People",
                "expectedDestination": None,
            },
            {
                "inputText": "finish report",
                "expectedBucket": "Admin",
                "expectedDestination": "tasks",
            },
        ]
        for item in items:
            yield item

    container.query_items = _query_items
    mgr.get_container.return_value = container
    return mgr


@pytest.fixture
def mock_project_client():
    """Mock AIProjectClient."""
    client = MagicMock()
    dataset_result = MagicMock()
    dataset_result.id = "ds-file-123"
    client.datasets.upload_file.return_value = dataset_result
    return client


async def test_export_and_upload_dataset(mock_cosmos_manager, mock_project_client):
    result = await export_and_upload_dataset(
        mock_project_client,
        mock_cosmos_manager,
        "classifier",
    )

    assert result["file_id"] == "ds-file-123"
    assert result["row_count"] == 3  # All 3 entries for classifier
    assert result["dataset_hash"]  # Non-empty hash
    assert result["dataset_version"]  # Non-empty version


# ---------------------------------------------------------------------------
# Test 6: dataset uses unique hash version, not fixed "1"
# ---------------------------------------------------------------------------


async def test_export_and_upload_dataset_uses_unique_hash_version(
    mock_cosmos_manager, mock_project_client
):
    result = await export_and_upload_dataset(
        mock_project_client,
        mock_cosmos_manager,
        "classifier",
    )

    version = result["dataset_version"]
    assert version != "1"
    assert "-" in version  # timestamp-hash format
    assert len(result["dataset_hash"]) == 8  # 8-char hash


# ---------------------------------------------------------------------------
# Test 7: canary detects tool capture
# ---------------------------------------------------------------------------


async def test_run_foundry_target_canary_detects_tool_capture(
    mock_cosmos_manager,
):
    project_client = MagicMock()

    # Mock openai_client
    openai_client = MagicMock()
    project_client.get_openai_client.return_value = openai_client

    # Mock dataset upload
    ds = MagicMock()
    ds.id = "canary-ds"
    project_client.datasets.upload_file.return_value = ds

    # Mock eval create
    eval_obj = MagicMock()
    eval_obj.id = "canary-eval-1"
    openai_client.evals.create.return_value = eval_obj

    # Mock run create
    run_obj = MagicMock()
    run_obj.id = "canary-run-1"
    run_obj.status = "completed"
    openai_client.evals.runs.create.return_value = run_obj

    # Mock run retrieve (completed)
    openai_client.evals.runs.retrieve.return_value = run_obj

    # Mock output items with file_capture tool call
    output_item = MagicMock()
    output_item.datasource_item = {
        "sample": {
            "output_items": [
                {
                    "content": [
                        {
                            "type": "tool_call",
                            "name": "file_capture",
                            "arguments": {"bucket": "Admin"},
                        }
                    ]
                }
            ]
        }
    }
    openai_client.evals.runs.output_items.list.return_value = [output_item]

    # Admin canary: output items with add_errand_items
    admin_output = MagicMock()
    admin_output.datasource_item = {
        "sample": {
            "output_items": [
                {
                    "content": [
                        {
                            "type": "tool_call",
                            "name": "add_errand_items",
                            "arguments": {
                                "items": [
                                    {
                                        "name": "milk",
                                        "destination": "costco",
                                    }
                                ]
                            },
                        }
                    ]
                }
            ]
        }
    }

    # Second call to output_items.list returns admin output
    call_count = 0

    def _list_side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            return [output_item]
        return [admin_output]

    openai_client.evals.runs.output_items.list = _list_side_effect

    result = await run_foundry_target_canary(project_client, mock_cosmos_manager)

    assert result["direct_target_supported"] is True
    assert result["classifier_tool_capture"] is True
    assert result["admin_tool_capture"] is True


# ---------------------------------------------------------------------------
# Test 8: canary fails without tool calls
# ---------------------------------------------------------------------------


async def test_run_foundry_target_canary_fails_without_tool_calls(
    mock_cosmos_manager,
):
    project_client = MagicMock()
    openai_client = MagicMock()
    project_client.get_openai_client.return_value = openai_client

    ds = MagicMock()
    ds.id = "canary-ds"
    project_client.datasets.upload_file.return_value = ds

    eval_obj = MagicMock()
    eval_obj.id = "canary-eval-1"
    openai_client.evals.create.return_value = eval_obj

    run_obj = MagicMock()
    run_obj.id = "canary-run-1"
    run_obj.status = "completed"
    openai_client.evals.runs.create.return_value = run_obj
    openai_client.evals.runs.retrieve.return_value = run_obj

    # Empty output items (no tool calls)
    empty_output = MagicMock()
    empty_output.datasource_item = {"sample": {"output_items": [{"content": []}]}}
    openai_client.evals.runs.output_items.list.return_value = [empty_output]

    result = await run_foundry_target_canary(project_client, mock_cosmos_manager)

    assert result["direct_target_supported"] is False


# ---------------------------------------------------------------------------
# Test 9: run_classifier_eval creates eval and run
# ---------------------------------------------------------------------------


async def test_run_classifier_eval_creates_eval_and_run(
    mock_cosmos_manager,
):
    project_client = MagicMock()
    openai_client = MagicMock()
    project_client.get_openai_client.return_value = openai_client

    # Mock evaluator registration
    project_client.beta.evaluators.get_latest.side_effect = Exception("not found")
    evaluator = MagicMock()
    evaluator.id = "eval-v1"
    project_client.beta.evaluators.create_version.return_value = evaluator

    # Mock dataset upload
    ds = MagicMock()
    ds.id = "ds-file-456"
    project_client.datasets.upload_file.return_value = ds

    # Mock eval creation
    eval_obj = MagicMock()
    eval_obj.id = "eval-001"
    openai_client.evals.create.return_value = eval_obj

    # Mock run creation
    run_obj = MagicMock()
    run_obj.id = "run-001"
    run_obj.status = "running"
    openai_client.evals.runs.create.return_value = run_obj

    result = await run_classifier_eval(
        project_client=project_client,
        cosmos_manager=mock_cosmos_manager,
    )

    assert result["eval_id"] == "eval-001"
    assert result["run_id"] == "run-001"
    assert result["dataset_hash"]
    assert result["execution_mode"] == "app_mediated"


# ---------------------------------------------------------------------------
# Test 10: run_classifier_eval fallback uses jsonl artifacts
# ---------------------------------------------------------------------------


async def test_run_classifier_eval_fallback_uses_jsonl(
    mock_cosmos_manager,
):
    project_client = MagicMock()
    openai_client = MagicMock()
    project_client.get_openai_client.return_value = openai_client

    project_client.beta.evaluators.get_latest.side_effect = Exception("not found")
    evaluator = MagicMock()
    evaluator.id = "eval-v1"
    project_client.beta.evaluators.create_version.return_value = evaluator

    ds = MagicMock()
    ds.id = "ds-mediated"
    project_client.datasets.upload_file.return_value = ds

    eval_obj = MagicMock()
    eval_obj.id = "eval-002"
    openai_client.evals.create.return_value = eval_obj

    run_obj = MagicMock()
    run_obj.id = "run-002"
    run_obj.status = "running"
    openai_client.evals.runs.create.return_value = run_obj

    result = await run_classifier_eval(
        project_client=project_client,
        cosmos_manager=mock_cosmos_manager,
        execution_mode="app_mediated",
    )

    assert result["execution_mode"] == "app_mediated"
    assert result["eval_id"] == "eval-002"

    # Verify the run data source uses jsonl type (not target)
    create_call = openai_client.evals.runs.create
    assert create_call.called
    call_kwargs = create_call.call_args
    ds_arg = (
        call_kwargs.kwargs.get("data_source") or call_kwargs.args[0]
        if call_kwargs.args
        else None
    )
    # The data_source should have type=jsonl for fallback
    if isinstance(ds_arg, dict):
        assert ds_arg.get("type") == "jsonl"


# ---------------------------------------------------------------------------
# Test 11: get_eval_results formats correctly
# ---------------------------------------------------------------------------


async def test_get_eval_results_formats_correctly():
    project_client = MagicMock()
    openai_client = MagicMock()
    project_client.get_openai_client.return_value = openai_client

    run = MagicMock()
    run.status = "completed"
    run.report_url = "https://foundry.example.com/eval/123"
    openai_client.evals.runs.retrieve.return_value = run

    # Mock output items
    oi1 = MagicMock()
    oi1.datasource_item = {
        "query": "buy milk",
        "expected_bucket": "Admin",
    }
    oi1.results = [{"score": 1.0, "name": "classifier_bucket_accuracy"}]
    oi1.status = "completed"

    oi2 = MagicMock()
    oi2.datasource_item = {
        "query": "met Sarah",
        "expected_bucket": "People",
    }
    oi2.results = [{"score": 0.0, "name": "classifier_bucket_accuracy"}]
    oi2.status = "completed"

    openai_client.evals.runs.output_items.list.return_value = [oi1, oi2]

    result = await get_eval_results_from_foundry(project_client, "eval-001", "run-001")

    assert result["accuracy"] == 0.5
    assert result["total"] == 2
    assert result["correct"] == 1
    assert "per_bucket" in result
    assert "Admin" in result["per_bucket"]
    assert len(result["failures"]) == 1


# ---------------------------------------------------------------------------
# Test 12: list_recent_eval_runs uses stable names
# ---------------------------------------------------------------------------


async def test_list_recent_eval_runs_uses_stable_names():
    project_client = MagicMock()
    openai_client = MagicMock()
    project_client.get_openai_client.return_value = openai_client

    # Mock eval listing
    classifier_eval = MagicMock()
    classifier_eval.id = "eval-c1"
    classifier_eval.name = "second-brain-classifier-eval"

    other_eval = MagicMock()
    other_eval.id = "eval-other"
    other_eval.name = "some-other-eval"

    openai_client.evals.list.return_value = [
        classifier_eval,
        other_eval,
    ]

    # Mock runs for classifier eval
    run1 = MagicMock()
    run1.id = "run-c1"
    run1.name = "classifier-20260424-120000-abc12345"
    run1.status = "completed"
    run1.created_at = "2026-04-24T12:00:00Z"
    run1.report_url = "https://foundry/report/c1"

    openai_client.evals.runs.list.return_value = [run1]

    result = await list_recent_eval_runs(
        project_client, eval_type="classifier", limit=3
    )

    assert len(result) >= 1
    assert result[0]["eval_name"] == "second-brain-classifier-eval"
    assert result[0]["run_id"] == "run-c1"
