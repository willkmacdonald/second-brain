"""Foundry-native evaluation for Classifier and Admin Agent quality.

Replaces custom eval runner/metrics/dry-run-tools with Azure AI Foundry's
native evaluation platform via AIProjectClient. Functions cover:

- Idempotent custom evaluator registration (code-based grade() functions)
- Canary-gated direct agent target evaluation
- App-mediated artifact generation fallback
- Content-hash-versioned dataset upload
- Eval run creation, polling, restart-safe discovery, result retrieval

All sync SDK calls are wrapped in asyncio.to_thread() to avoid blocking
the FastAPI event loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import tempfile
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from azure.ai.projects import AIProjectClient

    from second_brain.db.cosmos import CosmosManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom evaluator grade() functions (run in Foundry's sandboxed Python env)
# ---------------------------------------------------------------------------

CLASSIFIER_GRADE_FN = '''
import json

def grade(sample: dict, item: dict) -> float:
    """Exact-match scoring for classifier bucket accuracy.

    Supports two execution modes:
    - Direct target: parse item.sample.output_items for file_capture tool calls.
    - App-mediated fallback: parse item.tool_calls from precomputed JSONL.
    """
    expected = (item.get("expected_bucket") or "").strip().lower()
    if not expected:
        return 0.0

    predicted = ""

    # --- Mode 1: Direct target (output_items from Foundry agent run) ---
    try:
        output_items = item.get("sample", {}).get("output_items", [])
        if isinstance(output_items, str):
            output_items = json.loads(output_items)
        if isinstance(output_items, list):
            for msg in output_items:
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content", [])
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except (json.JSONDecodeError, TypeError):
                        content = []
                if isinstance(content, list):
                    for part in content:
                        if not isinstance(part, dict):
                            continue
                        is_file_capture = (
                            part.get("type") == "tool_call"
                            and part.get("name") == "file_capture"
                        )
                        if is_file_capture:
                            args = part.get("arguments", {})
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except (json.JSONDecodeError, TypeError):
                                    continue
                            predicted = (args.get("bucket") or "").strip().lower()
                            if predicted:
                                break
                if predicted:
                    break
    except Exception:
        pass

    # --- Mode 2: App-mediated fallback (tool_calls in JSONL row) ---
    if not predicted:
        try:
            tool_calls = item.get("tool_calls", [])
            if isinstance(tool_calls, str):
                tool_calls = json.loads(tool_calls)
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    if tc.get("name") == "file_capture":
                        args = tc.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except (json.JSONDecodeError, TypeError):
                                continue
                        predicted = (args.get("bucket") or "").strip().lower()
                        if predicted:
                            break
        except Exception:
            pass

    return 1.0 if predicted == expected else 0.0
'''

ADMIN_GRADE_FN = '''
import json

def grade(sample: dict, item: dict) -> float:
    """Exact-match scoring for admin routing accuracy.

    Supports two execution modes:
    - Direct target: parse item.sample.output_items for routing tool calls.
    - App-mediated fallback: parse item.tool_calls from precomputed JSONL.
    """
    expected = (item.get("expected_destination") or "").strip().lower()
    if not expected:
        return 0.0

    predicted = ""

    # --- Mode 1: Direct target (output_items from Foundry agent run) ---
    try:
        output_items = item.get("sample", {}).get("output_items", [])
        if isinstance(output_items, str):
            output_items = json.loads(output_items)
        if isinstance(output_items, list):
            for msg in output_items:
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content", [])
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except (json.JSONDecodeError, TypeError):
                        content = []
                if isinstance(content, list):
                    for part in content:
                        if not isinstance(part, dict):
                            continue
                        if part.get("type") != "tool_call":
                            continue
                        name = part.get("name", "")
                        args = part.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except (json.JSONDecodeError, TypeError):
                                continue
                        if name == "add_errand_items":
                            items_list = args.get("items", [])
                            if isinstance(items_list, list) and items_list:
                                dest = items_list[0].get("destination") or ""
                                predicted = dest.strip().lower()
                                if predicted:
                                    break
                        elif name == "add_task_items":
                            predicted = "tasks"
                            break
                if predicted:
                    break
    except Exception:
        pass

    # --- Mode 2: App-mediated fallback (tool_calls in JSONL row) ---
    if not predicted:
        try:
            tool_calls = item.get("tool_calls", [])
            if isinstance(tool_calls, str):
                tool_calls = json.loads(tool_calls)
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    name = tc.get("name", "")
                    args = tc.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, TypeError):
                            continue
                    if name == "add_errand_items":
                        items_list = args.get("items", [])
                        if isinstance(items_list, list) and items_list:
                            dest = items_list[0].get("destination") or ""
                            predicted = dest.strip().lower()
                            if predicted:
                                break
                    elif name == "add_task_items":
                        predicted = "tasks"
                        break
        except Exception:
            pass

    return 1.0 if predicted == expected else 0.0
'''

# ---------------------------------------------------------------------------
# Stable eval names and run prefixes (restart-safe discovery)
# ---------------------------------------------------------------------------

CLASSIFIER_EVAL_NAME = "second-brain-classifier-eval"
ADMIN_EVAL_NAME = "second-brain-admin-eval"


def _compute_code_hash(code: str) -> str:
    """Compute stable SHA-256 hash for evaluator code string."""
    return hashlib.sha256(code.strip().encode()).hexdigest()[:16]


def _compute_content_hash(rows: list[dict]) -> str:
    """Compute content hash from normalized JSONL rows."""
    normalized = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Evaluator registration
# ---------------------------------------------------------------------------


async def ensure_evaluators_registered(
    project_client: AIProjectClient,
) -> dict[str, str]:
    """Idempotently register custom code-based evaluators in Foundry catalog.

    Computes a stable code hash for each evaluator. Reuses the latest
    existing evaluator version if its description includes the same hash;
    creates a new version if the hash differs or the evaluator does not exist.

    Returns:
        dict mapping evaluator name to evaluator/version ID.
    """
    from azure.ai.projects.models import EvaluatorCategory, EvaluatorDefinitionType

    evaluators_config = [
        {
            "name": "classifier_bucket_accuracy",
            "display_name": "Classifier Bucket Accuracy",
            "description_prefix": (
                "Exact-match scoring for classifier bucket prediction"
            ),
            "code": CLASSIFIER_GRADE_FN,
            "data_schema_required": ["expected_bucket"],
        },
        {
            "name": "admin_routing_accuracy",
            "display_name": "Admin Routing Accuracy",
            "description_prefix": "Exact-match scoring for admin routing destination",
            "code": ADMIN_GRADE_FN,
            "data_schema_required": ["expected_destination"],
        },
    ]

    result: dict[str, str] = {}

    for cfg in evaluators_config:
        code_hash = _compute_code_hash(cfg["code"])
        description = f"{cfg['description_prefix']} [hash:{code_hash}]"

        try:
            # Check if evaluator already exists with matching hash
            existing = None
            with contextlib.suppress(Exception):
                existing = await asyncio.to_thread(
                    project_client.beta.evaluators.get_latest,
                    cfg["name"],
                )

            if (
                existing
                and hasattr(existing, "description")
                and code_hash in (existing.description or "")
            ):
                result[cfg["name"]] = getattr(existing, "id", cfg["name"])
                logger.info(
                    "Evaluator '%s' already registered (hash match: %s)",
                    cfg["name"],
                    code_hash,
                    extra={"component": "eval"},
                )
                continue

            # Create new evaluator version
            data_schema_props: dict[str, Any] = {}
            for field_name in cfg["data_schema_required"]:
                data_schema_props[field_name] = {"type": "string"}

            evaluator = await asyncio.to_thread(
                project_client.beta.evaluators.create_version,
                cfg["name"],
                {
                    "name": cfg["name"],
                    "categories": [EvaluatorCategory.QUALITY],
                    "display_name": cfg["display_name"],
                    "description": description,
                    "definition": {
                        "type": EvaluatorDefinitionType.CODE,
                        "code_text": cfg["code"],
                        "init_parameters": {
                            "type": "object",
                            "properties": {
                                "deployment_name": {"type": "string"},
                                "pass_threshold": {"type": "number"},
                            },
                            "required": ["deployment_name", "pass_threshold"],
                        },
                        "metrics": {
                            "result": {
                                "type": "continuous",
                                "desirable_direction": "increase",
                                "min_value": 0.0,
                                "max_value": 1.0,
                            }
                        },
                        "data_schema": {
                            "type": "object",
                            "required": ["item"],
                            "properties": {
                                "item": {
                                    "type": "object",
                                    "properties": data_schema_props,
                                },
                            },
                        },
                    },
                },
            )

            evaluator_id = getattr(evaluator, "id", cfg["name"])
            result[cfg["name"]] = evaluator_id
            logger.info(
                "Evaluator '%s' registered: id=%s hash=%s",
                cfg["name"],
                evaluator_id,
                code_hash,
                extra={"component": "eval"},
            )

        except Exception as exc:
            logger.error(
                "Failed to register evaluator '%s': %s",
                cfg["name"],
                exc,
                exc_info=True,
                extra={"component": "eval"},
            )
            result[cfg["name"]] = f"error:{exc}"

    return result


# ---------------------------------------------------------------------------
# Dataset export and upload
# ---------------------------------------------------------------------------


async def export_and_upload_dataset(
    project_client: AIProjectClient,
    cosmos_manager: CosmosManager,
    eval_type: str,
) -> dict:
    """Export golden dataset from Cosmos to JSONL and upload to Foundry.

    Args:
        project_client: Foundry project client.
        cosmos_manager: Cosmos DB manager for reading GoldenDataset.
        eval_type: "classifier" or "admin_agent".

    Returns:
        dict with file_id, dataset_hash, dataset_version, row_count.
    """
    golden_container = cosmos_manager.get_container("GoldenDataset")

    rows: list[dict] = []
    async for item in golden_container.query_items(
        query="SELECT * FROM c WHERE c.userId = @userId",
        parameters=[{"name": "@userId", "value": "will"}],
    ):
        if eval_type == "admin_agent":
            # Admin cases only: those with expectedDestination
            if item.get("expectedDestination") is None:
                continue
            rows.append(
                {
                    "query": item["inputText"],
                    "expected_destination": item["expectedDestination"],
                }
            )
        else:
            # Classifier cases: all entries (skip admin-only if desired,
            # but plan says "all entries" for classifier)
            rows.append(
                {
                    "query": item["inputText"],
                    "expected_bucket": item["expectedBucket"],
                }
            )

    if not rows:
        return {
            "file_id": None,
            "dataset_hash": "",
            "dataset_version": "",
            "row_count": 0,
            "error": f"No {eval_type} cases found in golden dataset",
        }

    # Compute content hash for unique versioning
    dataset_hash = _compute_content_hash(rows)
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    dataset_version = f"{timestamp}-{dataset_hash}"
    dataset_name = f"{eval_type}-golden-dataset"

    # Write JSONL to tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
        jsonl_path = f.name

    try:
        # Upload to Foundry (sync call wrapped in to_thread)
        dataset = await asyncio.to_thread(
            project_client.datasets.upload_file,
            name=dataset_name,
            version=dataset_version,
            file_path=jsonl_path,
        )
        file_id = getattr(dataset, "id", str(dataset))

        logger.info(
            "Dataset uploaded: name=%s version=%s rows=%d",
            dataset_name,
            dataset_version,
            len(rows),
            extra={
                "component": "eval",
                "eval_type": eval_type,
                "dataset_hash": dataset_hash,
            },
        )

        return {
            "file_id": file_id,
            "dataset_hash": dataset_hash,
            "dataset_version": dataset_version,
            "row_count": len(rows),
        }

    except Exception as exc:
        logger.error(
            "Dataset upload failed: %s",
            exc,
            exc_info=True,
            extra={"component": "eval", "eval_type": eval_type},
        )
        return {
            "file_id": None,
            "dataset_hash": dataset_hash,
            "dataset_version": dataset_version,
            "row_count": len(rows),
            "error": str(exc),
        }
    finally:
        import os

        with contextlib.suppress(OSError):
            os.unlink(jsonl_path)


# ---------------------------------------------------------------------------
# Canary: direct agent target evaluation gate
# ---------------------------------------------------------------------------


async def run_foundry_target_canary(
    project_client: AIProjectClient,
    cosmos_manager: CosmosManager,
) -> dict:
    """Run a minimal canary to test direct Foundry agent target evaluation.

    Sends one classifier and one admin row through azure_ai_target_completions
    and checks if output items contain the expected production tool calls.

    Returns:
        dict with direct_target_supported, classifier_tool_capture,
        admin_tool_capture, and details.
    """
    openai_client = await asyncio.to_thread(project_client.get_openai_client)

    classifier_capture = False
    admin_capture = False
    details: dict[str, Any] = {}

    # --- Classifier canary ---
    try:
        # Get a single classifier test case
        golden_container = cosmos_manager.get_container("GoldenDataset")
        classifier_case = None
        async for item in golden_container.query_items(
            query=(
                "SELECT TOP 1 * FROM c"
                " WHERE c.userId = @userId"
                " AND NOT IS_DEFINED(c.expectedDestination)"
            ),
            parameters=[{"name": "@userId", "value": "will"}],
        ):
            classifier_case = item
            break

        if classifier_case:
            from openai.types.eval_create_params import DataSourceConfigCustom

            # Create a minimal eval for the canary
            canary_eval = await asyncio.to_thread(
                openai_client.evals.create,
                name=f"canary-classifier-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
                data_source_config=DataSourceConfigCustom(
                    type="custom",
                    item_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "expected_bucket": {"type": "string"},
                        },
                        "required": ["query", "expected_bucket"],
                    },
                    include_sample_schema=True,
                ),
                testing_criteria=[],
            )

            # Upload single-row dataset
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".jsonl", delete=False
            ) as f:
                f.write(
                    json.dumps(
                        {
                            "query": classifier_case["inputText"],
                            "expected_bucket": classifier_case["expectedBucket"],
                        }
                    )
                    + "\n"
                )
                canary_path = f.name

            canary_dataset = await asyncio.to_thread(
                project_client.datasets.upload_file,
                name="canary-classifier-dataset",
                version=datetime.now(UTC).strftime("%Y%m%d%H%M%S"),
                file_path=canary_path,
            )

            canary_run = await asyncio.to_thread(
                openai_client.evals.runs.create,
                eval_id=canary_eval.id,
                name="canary-classifier-run",
                data_source={
                    "type": "azure_ai_target_completions",
                    "source": {
                        "type": "file_id",
                        "id": getattr(canary_dataset, "id", str(canary_dataset)),
                    },
                    "input_messages": {
                        "type": "template",
                        "template": [
                            {
                                "type": "message",
                                "role": "user",
                                "content": {
                                    "type": "input_text",
                                    "text": "{{item.query}}",
                                },
                            }
                        ],
                    },
                    "target": {
                        "type": "azure_ai_agent",
                        "name": "Classifier",
                    },
                },
            )

            # Poll canary run (short timeout for canary)
            for _ in range(30):  # 2.5 minutes max
                run_status = await asyncio.to_thread(
                    openai_client.evals.runs.retrieve,
                    run_id=canary_run.id,
                    eval_id=canary_eval.id,
                )
                if run_status.status in ("completed", "failed"):
                    break
                await asyncio.sleep(5)

            if run_status.status == "completed":
                output_items = list(
                    await asyncio.to_thread(
                        lambda: list(
                            openai_client.evals.runs.output_items.list(
                                run_id=canary_run.id,
                                eval_id=canary_eval.id,
                            )
                        )
                    )
                )

                for oi in output_items:
                    ds_item = getattr(oi, "datasource_item", {}) or {}
                    sample = ds_item.get("sample", {}) or {}
                    items_list = sample.get("output_items", [])
                    if isinstance(items_list, str):
                        try:
                            items_list = json.loads(items_list)
                        except (json.JSONDecodeError, TypeError):
                            items_list = []
                    if isinstance(items_list, list):
                        for msg in items_list:
                            if not isinstance(msg, dict):
                                continue
                            content = msg.get("content", [])
                            if isinstance(content, list):
                                for part in content:
                                    if (
                                        isinstance(part, dict)
                                        and part.get("name") == "file_capture"
                                    ):
                                        classifier_capture = True
                                        break

                details["classifier_canary_status"] = run_status.status
                details["classifier_output_items"] = len(output_items)
            else:
                details["classifier_canary_status"] = run_status.status
                details["classifier_canary_error"] = "Canary run did not complete"

            # Cleanup canary tempfile
            import os

            with contextlib.suppress(OSError):
                os.unlink(canary_path)
        else:
            details["classifier_canary_error"] = "No classifier test case found"

    except Exception as exc:
        details["classifier_canary_error"] = str(exc)
        logger.warning(
            "Classifier canary failed: %s",
            exc,
            extra={"component": "eval"},
        )

    # --- Admin canary ---
    try:
        admin_case = None
        async for item in golden_container.query_items(
            query=(
                "SELECT TOP 1 * FROM c"
                " WHERE c.userId = @userId"
                " AND IS_DEFINED(c.expectedDestination)"
            ),
            parameters=[{"name": "@userId", "value": "will"}],
        ):
            admin_case = item
            break

        if admin_case:
            canary_eval_admin = await asyncio.to_thread(
                openai_client.evals.create,
                name=f"canary-admin-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
                data_source_config=DataSourceConfigCustom(
                    type="custom",
                    item_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "expected_destination": {"type": "string"},
                        },
                        "required": ["query", "expected_destination"],
                    },
                    include_sample_schema=True,
                ),
                testing_criteria=[],
            )

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".jsonl", delete=False
            ) as f:
                f.write(
                    json.dumps(
                        {
                            "query": admin_case["inputText"],
                            "expected_destination": admin_case["expectedDestination"],
                        }
                    )
                    + "\n"
                )
                admin_canary_path = f.name

            admin_dataset = await asyncio.to_thread(
                project_client.datasets.upload_file,
                name="canary-admin-dataset",
                version=datetime.now(UTC).strftime("%Y%m%d%H%M%S"),
                file_path=admin_canary_path,
            )

            admin_run = await asyncio.to_thread(
                openai_client.evals.runs.create,
                eval_id=canary_eval_admin.id,
                name="canary-admin-run",
                data_source={
                    "type": "azure_ai_target_completions",
                    "source": {
                        "type": "file_id",
                        "id": getattr(admin_dataset, "id", str(admin_dataset)),
                    },
                    "input_messages": {
                        "type": "template",
                        "template": [
                            {
                                "type": "message",
                                "role": "user",
                                "content": {
                                    "type": "input_text",
                                    "text": "{{item.query}}",
                                },
                            }
                        ],
                    },
                    "target": {
                        "type": "azure_ai_agent",
                        "name": "AdminAgent",
                    },
                },
            )

            for _ in range(30):
                run_status_admin = await asyncio.to_thread(
                    openai_client.evals.runs.retrieve,
                    run_id=admin_run.id,
                    eval_id=canary_eval_admin.id,
                )
                if run_status_admin.status in ("completed", "failed"):
                    break
                await asyncio.sleep(5)

            if run_status_admin.status == "completed":
                admin_output_items = list(
                    await asyncio.to_thread(
                        lambda: list(
                            openai_client.evals.runs.output_items.list(
                                run_id=admin_run.id,
                                eval_id=canary_eval_admin.id,
                            )
                        )
                    )
                )

                for oi in admin_output_items:
                    ds_item = getattr(oi, "datasource_item", {}) or {}
                    sample = ds_item.get("sample", {}) or {}
                    items_list = sample.get("output_items", [])
                    if isinstance(items_list, str):
                        try:
                            items_list = json.loads(items_list)
                        except (json.JSONDecodeError, TypeError):
                            items_list = []
                    if isinstance(items_list, list):
                        for msg in items_list:
                            if not isinstance(msg, dict):
                                continue
                            content = msg.get("content", [])
                            if isinstance(content, list):
                                for part in content:
                                    if isinstance(part, dict) and part.get("name") in (
                                        "add_errand_items",
                                        "add_task_items",
                                    ):
                                        admin_capture = True
                                        break

                details["admin_canary_status"] = run_status_admin.status
                details["admin_output_items"] = len(admin_output_items)
            else:
                details["admin_canary_status"] = run_status_admin.status
                details["admin_canary_error"] = "Admin canary run did not complete"

            import os

            with contextlib.suppress(OSError):
                os.unlink(admin_canary_path)
        else:
            details["admin_canary_error"] = "No admin test case found"

    except Exception as exc:
        details["admin_canary_error"] = str(exc)
        logger.warning(
            "Admin canary failed: %s",
            exc,
            extra={"component": "eval"},
        )

    direct_target_supported = classifier_capture and admin_capture

    logger.info(
        "Canary result: direct_target_supported=%s classifier=%s admin=%s",
        direct_target_supported,
        classifier_capture,
        admin_capture,
        extra={"component": "eval"},
    )

    return {
        "direct_target_supported": direct_target_supported,
        "classifier_tool_capture": classifier_capture,
        "admin_tool_capture": admin_capture,
        "details": details,
    }


# ---------------------------------------------------------------------------
# App-mediated artifact generation (fallback)
# ---------------------------------------------------------------------------


async def generate_app_mediated_dataset(
    cosmos_manager: CosmosManager,
    eval_type: str,
    *,
    classifier_client: Any | None = None,
    classifier_tools: list | None = None,
    admin_client: Any | None = None,
    admin_tools: list | None = None,
    project_client: AIProjectClient | None = None,
) -> dict:
    """Generate app-mediated response/tool-call artifacts for Foundry scoring.

    Uses production clients/tools to invoke agents, captures response_text
    and tool_calls into JSONL rows, and uploads to Foundry.

    This is the fallback path when direct Foundry target evaluation cannot
    capture production-equivalent tool calls.
    """
    from agent_framework import ChatOptions, Message

    golden_container = cosmos_manager.get_container("GoldenDataset")

    rows: list[dict] = []
    async for item in golden_container.query_items(
        query="SELECT * FROM c WHERE c.userId = @userId",
        parameters=[{"name": "@userId", "value": "will"}],
    ):
        if eval_type == "classifier":
            if item.get("expectedDestination") is not None:
                continue
            row: dict[str, Any] = {
                "query": item["inputText"],
                "expected_bucket": item["expectedBucket"],
                "response_text": "",
                "tool_calls": [],
            }

            if classifier_client and classifier_tools:
                try:
                    messages = [Message(role="user", text=item["inputText"])]
                    options = ChatOptions(tools=classifier_tools)
                    async with asyncio.timeout(60):
                        response = await classifier_client.get_response(
                            messages=messages, options=options
                        )
                    # Extract tool calls from response
                    if hasattr(response, "messages"):
                        for msg in response.messages:
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    row["tool_calls"].append(
                                        {
                                            "name": getattr(tc, "name", ""),
                                            "arguments": getattr(tc, "arguments", {}),
                                        }
                                    )
                            if hasattr(msg, "text") and msg.text:
                                row["response_text"] = msg.text
                except Exception as exc:
                    row["error"] = str(exc)

            rows.append(row)

        elif eval_type == "admin_agent":
            if item.get("expectedDestination") is None:
                continue

            # Build routing context like production does
            from second_brain.tools.admin import build_routing_context

            routing_context = await build_routing_context(cosmos_manager)

            query_text = f"{routing_context}\n\n---\nUser capture: {item['inputText']}"
            row = {
                "query": query_text,
                "expected_destination": item["expectedDestination"],
                "response_text": "",
                "tool_calls": [],
            }

            if admin_client and admin_tools:
                try:
                    messages = [
                        Message(
                            role="user",
                            text=query_text,
                        )
                    ]
                    options = ChatOptions(tools=admin_tools)
                    async with asyncio.timeout(60):
                        response = await admin_client.get_response(
                            messages=messages, options=options
                        )
                    if hasattr(response, "messages"):
                        for msg in response.messages:
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    row["tool_calls"].append(
                                        {
                                            "name": getattr(tc, "name", ""),
                                            "arguments": getattr(tc, "arguments", {}),
                                        }
                                    )
                            if hasattr(msg, "text") and msg.text:
                                row["response_text"] = msg.text
                except Exception as exc:
                    row["error"] = str(exc)

            rows.append(row)

    if not rows:
        return {
            "file_id": None,
            "dataset_hash": "",
            "dataset_version": "",
            "row_count": 0,
            "error": f"No {eval_type} cases found",
        }

    # Compute content hash and upload
    dataset_hash = _compute_content_hash(rows)
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    dataset_version = f"{timestamp}-{dataset_hash}"
    dataset_name = f"{eval_type}-mediated-dataset"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
        jsonl_path = f.name

    try:
        if project_client:
            dataset = await asyncio.to_thread(
                project_client.datasets.upload_file,
                name=dataset_name,
                version=dataset_version,
                file_path=jsonl_path,
            )
            file_id = getattr(dataset, "id", str(dataset))
        else:
            file_id = None

        return {
            "file_id": file_id,
            "dataset_hash": dataset_hash,
            "dataset_version": dataset_version,
            "row_count": len(rows),
        }
    finally:
        import os

        with contextlib.suppress(OSError):
            os.unlink(jsonl_path)


# ---------------------------------------------------------------------------
# Eval run creation
# ---------------------------------------------------------------------------


async def run_classifier_eval(
    project_client: AIProjectClient,
    cosmos_manager: CosmosManager,
    *,
    classifier_client: Any | None = None,
    classifier_tools: list | None = None,
    execution_mode: str | None = None,
) -> dict:
    """Create and start a classifier evaluation run in Foundry.

    Args:
        project_client: Foundry project client.
        cosmos_manager: Cosmos DB manager.
        classifier_client: Optional production classifier client (for fallback).
        classifier_tools: Optional production tool list (for fallback).
        execution_mode: Force "direct_target" or "app_mediated". None = auto.

    Returns:
        dict with eval_id, run_id, status, execution_mode, dataset_hash,
        dataset_version.
    """
    from openai.types.eval_create_params import DataSourceConfigCustom

    openai_client = await asyncio.to_thread(project_client.get_openai_client)

    # Ensure custom evaluators exist
    await ensure_evaluators_registered(project_client)

    # Determine execution mode
    use_direct = execution_mode == "direct_target"

    # Upload dataset
    if use_direct:
        ds = await export_and_upload_dataset(
            project_client, cosmos_manager, "classifier"
        )
    else:
        # App-mediated fallback: generate artifacts
        ds = await generate_app_mediated_dataset(
            cosmos_manager,
            "classifier",
            classifier_client=classifier_client,
            classifier_tools=classifier_tools,
            project_client=project_client,
        )

    if ds.get("file_id") is None:
        return {
            "eval_id": None,
            "run_id": None,
            "status": "failed",
            "execution_mode": execution_mode or "app_mediated",
            "error": ds.get("error", "Dataset upload failed"),
            "dataset_hash": ds.get("dataset_hash", ""),
            "dataset_version": ds.get("dataset_version", ""),
        }

    # Create eval definition
    item_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "expected_bucket": {"type": "string"},
        },
        "required": ["query", "expected_bucket"],
    }
    if not use_direct:
        item_schema["properties"]["tool_calls"] = {"type": "array"}
        item_schema["properties"]["response_text"] = {"type": "string"}

    data_source_config = DataSourceConfigCustom(
        type="custom",
        item_schema=item_schema,
        include_sample_schema=True,
    )

    testing_criteria = [
        {
            "type": "azure_ai_evaluator",
            "name": "classifier_bucket_accuracy",
            "evaluator_name": "classifier_bucket_accuracy",
            "initialization_parameters": {
                "deployment_name": "gpt-4o",
                "pass_threshold": 0.5,
            },
        },
        {
            "type": "azure_ai_evaluator",
            "name": "intent_resolution",
            "evaluator_name": "builtin.intent_resolution",
            "initialization_parameters": {"deployment_name": "gpt-4o"},
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{sample.output_items}}"
                if use_direct
                else "{{item.response_text}}",
            },
        },
    ]

    eval_obj = await asyncio.to_thread(
        openai_client.evals.create,
        name=CLASSIFIER_EVAL_NAME,
        data_source_config=data_source_config,
        testing_criteria=testing_criteria,
    )

    # Create eval run
    run_name = (
        f"classifier-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{ds['dataset_hash']}"
    )

    if use_direct:
        data_source: dict[str, Any] = {
            "type": "azure_ai_target_completions",
            "source": {"type": "file_id", "id": ds["file_id"]},
            "input_messages": {
                "type": "template",
                "template": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": {
                            "type": "input_text",
                            "text": "{{item.query}}",
                        },
                    }
                ],
            },
            "target": {
                "type": "azure_ai_agent",
                "name": "Classifier",
            },
        }
    else:
        data_source = {
            "type": "jsonl",
            "source": {"type": "file_id", "id": ds["file_id"]},
        }

    eval_run = await asyncio.to_thread(
        openai_client.evals.runs.create,
        eval_id=eval_obj.id,
        name=run_name,
        data_source=data_source,
    )

    logger.info(
        "Classifier eval run created: eval_id=%s run_id=%s mode=%s",
        eval_obj.id,
        eval_run.id,
        execution_mode or "app_mediated",
        extra={
            "component": "eval",
            "eval_type": "classifier",
            "eval_run_id": eval_run.id,
        },
    )

    return {
        "eval_id": eval_obj.id,
        "run_id": eval_run.id,
        "status": eval_run.status,
        "execution_mode": execution_mode or "app_mediated",
        "dataset_hash": ds["dataset_hash"],
        "dataset_version": ds["dataset_version"],
    }


async def run_admin_eval(
    project_client: AIProjectClient,
    cosmos_manager: CosmosManager,
    *,
    admin_client: Any | None = None,
    admin_tools: list | None = None,
    execution_mode: str | None = None,
) -> dict:
    """Create and start an admin agent evaluation run in Foundry.

    Same pattern as classifier but with admin-specific evaluators and
    deterministic routing context preservation.
    """
    from openai.types.eval_create_params import DataSourceConfigCustom

    openai_client = await asyncio.to_thread(project_client.get_openai_client)

    # Ensure custom evaluators exist
    await ensure_evaluators_registered(project_client)

    # Determine execution mode
    use_direct = execution_mode == "direct_target"

    # Upload dataset
    if use_direct:
        ds = await export_and_upload_dataset(
            project_client, cosmos_manager, "admin_agent"
        )
    else:
        ds = await generate_app_mediated_dataset(
            cosmos_manager,
            "admin_agent",
            admin_client=admin_client,
            admin_tools=admin_tools,
            project_client=project_client,
        )

    if ds.get("file_id") is None:
        return {
            "eval_id": None,
            "run_id": None,
            "status": "failed",
            "execution_mode": execution_mode or "app_mediated",
            "error": ds.get("error", "Dataset upload failed"),
            "dataset_hash": ds.get("dataset_hash", ""),
            "dataset_version": ds.get("dataset_version", ""),
        }

    # Create eval definition
    item_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "expected_destination": {"type": "string"},
        },
        "required": ["query", "expected_destination"],
    }
    if not use_direct:
        item_schema["properties"]["tool_calls"] = {"type": "array"}
        item_schema["properties"]["response_text"] = {"type": "string"}

    data_source_config = DataSourceConfigCustom(
        type="custom",
        item_schema=item_schema,
        include_sample_schema=True,
    )

    testing_criteria = [
        {
            "type": "azure_ai_evaluator",
            "name": "admin_routing_accuracy",
            "evaluator_name": "admin_routing_accuracy",
            "initialization_parameters": {
                "deployment_name": "gpt-4o",
                "pass_threshold": 0.5,
            },
        },
        {
            "type": "azure_ai_evaluator",
            "name": "tool_call_accuracy",
            "evaluator_name": "builtin.tool_call_accuracy",
            "initialization_parameters": {"deployment_name": "gpt-4o"},
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{sample.output_items}}"
                if use_direct
                else "{{item.response_text}}",
            },
        },
        {
            "type": "azure_ai_evaluator",
            "name": "task_adherence",
            "evaluator_name": "builtin.task_adherence",
            "initialization_parameters": {"deployment_name": "gpt-4o"},
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{sample.output_items}}"
                if use_direct
                else "{{item.response_text}}",
            },
        },
    ]

    eval_obj = await asyncio.to_thread(
        openai_client.evals.create,
        name=ADMIN_EVAL_NAME,
        data_source_config=data_source_config,
        testing_criteria=testing_criteria,
    )

    run_name = (
        f"admin-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{ds['dataset_hash']}"
    )

    if use_direct:
        data_source = {
            "type": "azure_ai_target_completions",
            "source": {"type": "file_id", "id": ds["file_id"]},
            "input_messages": {
                "type": "template",
                "template": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": {
                            "type": "input_text",
                            "text": "{{item.query}}",
                        },
                    }
                ],
            },
            "target": {
                "type": "azure_ai_agent",
                "name": "AdminAgent",
            },
        }
    else:
        data_source = {
            "type": "jsonl",
            "source": {"type": "file_id", "id": ds["file_id"]},
        }

    eval_run = await asyncio.to_thread(
        openai_client.evals.runs.create,
        eval_id=eval_obj.id,
        name=run_name,
        data_source=data_source,
    )

    logger.info(
        "Admin eval run created: eval_id=%s run_id=%s mode=%s",
        eval_obj.id,
        eval_run.id,
        execution_mode or "app_mediated",
        extra={
            "component": "eval",
            "eval_type": "admin_agent",
            "eval_run_id": eval_run.id,
        },
    )

    return {
        "eval_id": eval_obj.id,
        "run_id": eval_run.id,
        "status": eval_run.status,
        "execution_mode": execution_mode or "app_mediated",
        "dataset_hash": ds["dataset_hash"],
        "dataset_version": ds["dataset_version"],
    }


# ---------------------------------------------------------------------------
# Polling and result retrieval
# ---------------------------------------------------------------------------


async def poll_eval_run(
    project_client: AIProjectClient,
    eval_id: str,
    run_id: str,
) -> dict:
    """Poll a Foundry eval run until completion or failure.

    Polls every 5 seconds. Returns the final run status dict.
    """
    openai_client = await asyncio.to_thread(project_client.get_openai_client)

    for _ in range(120):  # 10 minutes max
        run = await asyncio.to_thread(
            openai_client.evals.runs.retrieve,
            run_id=run_id,
            eval_id=eval_id,
        )
        if run.status in ("completed", "failed"):
            return {
                "status": run.status,
                "report_url": getattr(run, "report_url", None),
                "eval_id": eval_id,
                "run_id": run_id,
            }
        await asyncio.sleep(5)

    return {
        "status": "timeout",
        "eval_id": eval_id,
        "run_id": run_id,
    }


async def get_eval_results_from_foundry(
    project_client: AIProjectClient,
    eval_id: str,
    run_id: str,
) -> dict:
    """Retrieve and format eval results from Foundry.

    Parses per-item evaluator scores and formats output to match the
    existing investigation tool contract (D-11): accuracy, total, correct,
    per_bucket/per_destination breakdown, failures list.
    """
    openai_client = await asyncio.to_thread(project_client.get_openai_client)

    # Retrieve run
    run = await asyncio.to_thread(
        openai_client.evals.runs.retrieve,
        run_id=run_id,
        eval_id=eval_id,
    )

    # List output items
    output_items = await asyncio.to_thread(
        lambda: list(
            openai_client.evals.runs.output_items.list(
                run_id=run_id,
                eval_id=eval_id,
            )
        )
    )

    total = len(output_items)
    correct = 0
    failures: list[dict] = []
    per_category: dict[str, dict[str, int]] = {}

    for oi in output_items:
        ds_item = getattr(oi, "datasource_item", {}) or {}
        results_list = getattr(oi, "results", []) or []
        item_status = getattr(oi, "status", "unknown")

        # Extract expected label
        expected = ds_item.get("expected_bucket") or ds_item.get(
            "expected_destination", ""
        )
        query_text = ds_item.get("query", "")[:100]

        # Check custom evaluator result
        item_passed = False
        for res in results_list:
            res_dict = res if isinstance(res, dict) else getattr(res, "__dict__", {})
            score = res_dict.get("score") or res_dict.get("result")
            if score is not None:
                try:
                    if float(score) >= 0.5:
                        item_passed = True
                        break
                except (ValueError, TypeError):
                    pass

        if item_passed:
            correct += 1
        else:
            failures.append(
                {
                    "input": query_text,
                    "expected": expected,
                    "status": item_status,
                }
            )

        # Per-category breakdown
        if expected:
            if expected not in per_category:
                per_category[expected] = {"total": 0, "correct": 0}
            per_category[expected]["total"] += 1
            if item_passed:
                per_category[expected]["correct"] += 1

    accuracy = correct / total if total > 0 else 0.0

    return {
        "accuracy": accuracy,
        "total": total,
        "correct": correct,
        "per_bucket": {
            k: v["correct"] / v["total"] if v["total"] > 0 else 0.0
            for k, v in per_category.items()
        },
        "failures": failures[:10],  # Limit failures for readability
        "report_url": getattr(run, "report_url", None),
        "status": run.status,
        "eval_id": eval_id,
        "run_id": run_id,
    }


# ---------------------------------------------------------------------------
# Run discovery (restart-safe)
# ---------------------------------------------------------------------------


async def list_recent_eval_runs(
    project_client: AIProjectClient,
    eval_type: str | None = None,
    limit: int = 3,
) -> list[dict]:
    """List recent eval runs using stable eval names and run prefixes.

    Restart-safe: queries Foundry directly rather than relying on
    in-memory state. Uses stable eval names (second-brain-classifier-eval,
    second-brain-admin-eval) to discover evaluations.

    Returns:
        List of dicts with eval_id, run_id, name, status, created_at,
        report_url.
    """
    openai_client = await asyncio.to_thread(project_client.get_openai_client)

    # Determine which eval names to search
    target_names: list[str] = []
    if eval_type is None:
        target_names = [CLASSIFIER_EVAL_NAME, ADMIN_EVAL_NAME]
    elif eval_type == "classifier":
        target_names = [CLASSIFIER_EVAL_NAME]
    elif eval_type in ("admin_agent", "admin"):
        target_names = [ADMIN_EVAL_NAME]
    else:
        target_names = [CLASSIFIER_EVAL_NAME, ADMIN_EVAL_NAME]

    results: list[dict] = []

    for eval_name in target_names:
        try:
            # List evals and find by stable name
            evals_list = await asyncio.to_thread(
                lambda name=eval_name: list(openai_client.evals.list())
            )

            for eval_obj in evals_list:
                if getattr(eval_obj, "name", "") != eval_name:
                    continue

                # List runs for this eval
                try:
                    runs = await asyncio.to_thread(
                        lambda eid=eval_obj.id: list(
                            openai_client.evals.runs.list(eval_id=eid)
                        )
                    )

                    for run in runs[:limit]:
                        results.append(
                            {
                                "eval_id": eval_obj.id,
                                "run_id": run.id,
                                "name": getattr(run, "name", ""),
                                "status": run.status,
                                "created_at": str(getattr(run, "created_at", "")),
                                "report_url": getattr(run, "report_url", None),
                                "eval_name": eval_name,
                            }
                        )
                except Exception as exc:
                    logger.warning(
                        "Failed to list runs for eval %s: %s",
                        eval_obj.id,
                        exc,
                        extra={"component": "eval"},
                    )
        except Exception as exc:
            logger.warning(
                "Failed to list evals for name '%s': %s",
                eval_name,
                exc,
                extra={"component": "eval"},
            )

    # Sort by created_at descending and limit
    results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return results[:limit]


# Needed for tempfile cleanup
