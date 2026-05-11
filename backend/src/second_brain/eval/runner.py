"""Core eval runner for Classifier and Admin Agent golden dataset evaluation.

Orchestrates sequential evaluation: reads golden dataset cases from Cosmos,
sends each through a real Foundry agent with dry-run tools, computes metrics,
persists results to Cosmos EvalResults container, and tracks run status
in-memory for status polling.

Each eval case runs in a fresh tool instance with no state leakage (Pitfall #2).
Agent calls have a 60-second timeout per case (Pitfall #5 / T-21-05).

Phase 24 task group 23.2 (plan 24-12, GA migration):
- Agent invocation is now indirected through ``EvalAgentInvoker`` so the
  runner stays agnostic of RC vs. GA call shapes during the migration
  window. See ``second_brain.eval.invoker`` for the Protocol + the two
  concrete implementations (RC for classifier until 24-13..24-17, GA for
  admin after 24-09..24-11).
- The caller (api/eval.py or tools/investigation.py) constructs a
  ``_MigrationHybridInvoker(rc_invoker=..., ga_invoker=...)`` and passes
  that single hybrid as the ``invoker`` argument. Plan 24-18 deletes the
  hybrid + RC class together once the classifier is GA.
- The runner does NOT import ``_MigrationHybridInvoker`` directly; it
  only types the parameter as the Protocol.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from second_brain.eval.dry_run_tools import DryRunAdminTools, EvalClassifierTools
from second_brain.eval.invoker import EvalAgentInvoker
from second_brain.eval.metrics import (
    compute_admin_metrics,
    compute_classifier_metrics,
    compute_confidence_calibration,
)
from second_brain.models.documents import EvalResultsDocument

if TYPE_CHECKING:
    from second_brain.db.cosmos import CosmosManager

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def _parse_retry_after(exc: Exception) -> int | None:
    """Extract retry-after seconds from a rate-limit error message."""
    match = re.search(r"retry after (\d+) seconds", str(exc), re.IGNORECASE)
    return int(match.group(1)) if match else None


async def _call_with_retry(
    coro_factory: Callable[[], object],
    *,
    max_retries: int = MAX_RETRIES,
    run_id: str,
    case_index: int,
    runs_dict: dict,
) -> None:
    """Call an async factory with retry on rate-limit errors."""
    for attempt in range(max_retries + 1):
        try:
            async with asyncio.timeout(60):
                await coro_factory()  # type: ignore[misc]
            return
        except Exception as exc:
            retry_after = _parse_retry_after(exc)
            if retry_after is not None and attempt < max_retries:
                logger.warning(
                    "Rate-limited on case %d (attempt %d/%d), retrying in %ds",
                    case_index,
                    attempt + 1,
                    max_retries + 1,
                    retry_after,
                    extra={
                        "component": "eval",
                        "eval_run_id": run_id,
                    },
                )
                progress = runs_dict[run_id].get("progress", "?")
                runs_dict[run_id]["progress"] = f"{progress} (waiting {retry_after}s)"
                await asyncio.sleep(retry_after)
                continue
            raise


async def run_classifier_eval(
    run_id: str,
    cosmos_manager: CosmosManager,
    invoker: EvalAgentInvoker,
    runs_dict: dict,
) -> None:
    """Run classifier evaluation against golden dataset.

    Reads classifier test cases from GoldenDataset container, sends each
    through the real Foundry Classifier agent (via ``invoker``) with
    dry-run tools, computes accuracy/precision/recall/calibration metrics,
    persists results, and updates run status.

    Args:
        run_id: Unique identifier for this eval run.
        cosmos_manager: Cosmos DB manager for reading/writing containers.
        invoker: ``EvalAgentInvoker`` implementation. During plan 24-12's
            migration window, callers construct a ``_MigrationHybridInvoker``
            that routes invoke_classifier -> RCEvalAgentInvoker. After plan
            24-18 this becomes a plain ``GAEvalAgentInvoker``.
        runs_dict: In-memory dict for tracking run status/progress.
    """
    try:
        runs_dict[run_id] = {"status": "running", "progress": "0/0"}

        # Step 1: Read golden dataset, filter to classifier-only cases
        golden_container = cosmos_manager.get_container("GoldenDataset")
        test_cases: list[dict] = []
        async for item in golden_container.query_items(
            query="SELECT * FROM c WHERE c.userId = @userId",
            parameters=[{"name": "@userId", "value": "will"}],
        ):
            # Skip admin eval cases (those with expectedDestination)
            if item.get("expectedDestination") is not None:
                continue
            test_cases.append(item)

        # Step 2: Empty check
        if not test_cases:
            runs_dict[run_id] = {
                "status": "failed",
                "error": "No classifier test cases found in golden dataset",
            }
            return

        runs_dict[run_id]["progress"] = f"0/{len(test_cases)}"
        individual_results: list[dict] = []

        # Step 3: Iterate sequentially (D-03)
        for i, case in enumerate(test_cases):
            try:
                # Fresh tool instance per case -- no state leakage (Pitfall #2)
                eval_tools = EvalClassifierTools()

                await _call_with_retry(
                    lambda et=eval_tools, txt=case["inputText"]: (
                        invoker.invoke_classifier(txt, et)
                    ),
                    run_id=run_id,
                    case_index=i,
                    runs_dict=runs_dict,
                )

                result = {
                    "input": case["inputText"][:100],
                    "expected": case["expectedBucket"],
                    "predicted": eval_tools.last_bucket or "NONE",
                    "confidence": eval_tools.last_confidence or 0.0,
                    "correct": eval_tools.last_bucket == case["expectedBucket"],
                    "case_id": case["id"],
                }
            except Exception as exc:
                result = {
                    "input": case["inputText"][:100],
                    "expected": case["expectedBucket"],
                    "predicted": "ERROR",
                    "confidence": 0.0,
                    "correct": False,
                    "case_id": case["id"],
                    "error": str(exc),
                }

            individual_results.append(result)
            runs_dict[run_id]["progress"] = f"{i + 1}/{len(test_cases)}"

        # Step 4: Compute metrics
        metrics = compute_classifier_metrics(individual_results)
        calibration = compute_confidence_calibration(individual_results)
        metrics["calibration"] = calibration

        # Step 5: Write EvalResultsDocument to Cosmos
        eval_doc = EvalResultsDocument(
            evalType="classifier",
            runTimestamp=datetime.now(UTC),
            datasetSize=len(test_cases),
            aggregateScores=metrics,
            individualResults=individual_results,
            modelDeployment="gpt-4o",
        )
        eval_container = cosmos_manager.get_container("EvalResults")
        await eval_container.create_item(body=eval_doc.model_dump(mode="json"))

        # Step 6: Log to App Insights
        logger.info(
            "Classifier eval complete: accuracy=%.2f, total=%d, correct=%d",
            metrics["accuracy"],
            metrics["total"],
            metrics["correct"],
            extra={
                "component": "eval",
                "eval_type": "classifier",
                "eval_run_id": run_id,
                "accuracy": metrics["accuracy"],
            },
        )

        # Step 7: Update run status
        runs_dict[run_id] = {
            "status": "completed",
            "result_id": eval_doc.id,
            "accuracy": metrics["accuracy"],
            "total": metrics["total"],
            "correct": metrics["correct"],
        }

    except Exception as exc:
        logger.error(
            "Classifier eval failed: %s",
            exc,
            extra={
                "component": "eval",
                "eval_type": "classifier",
                "eval_run_id": run_id,
            },
        )
        runs_dict[run_id] = {"status": "failed", "error": str(exc)}


async def run_admin_eval(
    run_id: str,
    cosmos_manager: CosmosManager,
    invoker: EvalAgentInvoker,
    routing_context: str,
    runs_dict: dict,
) -> None:
    """Run admin agent evaluation against golden dataset.

    Reads admin test cases from GoldenDataset container, sends each through
    the real Foundry Admin agent (via ``invoker``) with dry-run tools,
    computes routing accuracy metrics, persists results, and updates run
    status.

    Args:
        run_id: Unique identifier for this eval run.
        cosmos_manager: Cosmos DB manager for reading/writing containers.
        invoker: ``EvalAgentInvoker`` implementation. During plan 24-12's
            migration window, callers construct a ``_MigrationHybridInvoker``
            that routes invoke_admin -> GAEvalAgentInvoker. After plan
            24-18 this becomes a plain ``GAEvalAgentInvoker``.
        routing_context: Pre-built routing context string for
            ``DryRunAdminTools`` and passed into ``invoker.invoke_admin``.
        runs_dict: In-memory dict for tracking run status/progress.
    """
    try:
        runs_dict[run_id] = {"status": "running", "progress": "0/0"}

        # Step 1: Read golden dataset, filter to admin cases
        golden_container = cosmos_manager.get_container("GoldenDataset")
        test_cases: list[dict] = []
        async for item in golden_container.query_items(
            query="SELECT * FROM c WHERE c.userId = @userId",
            parameters=[{"name": "@userId", "value": "will"}],
        ):
            # Only admin cases (those with expectedDestination)
            if item.get("expectedDestination") is None:
                continue
            test_cases.append(item)

        # Step 2: Empty check
        if not test_cases:
            runs_dict[run_id] = {
                "status": "failed",
                "error": "No admin test cases found in golden dataset",
            }
            return

        runs_dict[run_id]["progress"] = f"0/{len(test_cases)}"
        individual_results: list[dict] = []

        # Step 3: Iterate sequentially
        for i, case in enumerate(test_cases):
            try:
                # Fresh tool instance per case -- no state leakage (Pitfall #2)
                dry_run_tools = DryRunAdminTools(routing_context=routing_context)
                input_text = case["inputText"]

                await _call_with_retry(
                    lambda dt=dry_run_tools, txt=input_text, rc=routing_context: (
                        invoker.invoke_admin(txt, dt, rc)
                    ),
                    run_id=run_id,
                    case_index=i,
                    runs_dict=runs_dict,
                )

                # Read prediction: primary destination
                predicted = (
                    dry_run_tools.captured_destinations[0]
                    if dry_run_tools.captured_destinations
                    else "unrouted"
                )

                result = {
                    "input": case["inputText"][:100],
                    "expected_destination": case["expectedDestination"],
                    "predicted_destination": predicted,
                    "correct": predicted == case["expectedDestination"],
                    "case_id": case["id"],
                    "all_destinations": dry_run_tools.captured_destinations,
                    "task_count": len(dry_run_tools.captured_tasks),
                }
            except Exception as exc:
                result = {
                    "input": case["inputText"][:100],
                    "expected_destination": case["expectedDestination"],
                    "predicted_destination": "ERROR",
                    "correct": False,
                    "case_id": case["id"],
                    "all_destinations": [],
                    "task_count": 0,
                    "error": str(exc),
                }

            individual_results.append(result)
            runs_dict[run_id]["progress"] = f"{i + 1}/{len(test_cases)}"

        # Step 4: Compute metrics
        metrics = compute_admin_metrics(individual_results)

        # Step 5: Write EvalResultsDocument to Cosmos
        eval_doc = EvalResultsDocument(
            evalType="admin_agent",
            runTimestamp=datetime.now(UTC),
            datasetSize=len(test_cases),
            aggregateScores=metrics,
            individualResults=individual_results,
            modelDeployment="gpt-4o",
        )
        eval_container = cosmos_manager.get_container("EvalResults")
        await eval_container.create_item(body=eval_doc.model_dump(mode="json"))

        # Step 6: Log to App Insights
        logger.info(
            "Admin eval complete: routing_accuracy=%.2f, total=%d, correct=%d",
            metrics["routing_accuracy"],
            metrics["total"],
            metrics["correct"],
            extra={
                "component": "eval",
                "eval_type": "admin_agent",
                "eval_run_id": run_id,
                "routing_accuracy": metrics["routing_accuracy"],
            },
        )

        # Step 7: Update run status
        runs_dict[run_id] = {
            "status": "completed",
            "result_id": eval_doc.id,
            "routing_accuracy": metrics["routing_accuracy"],
            "total": metrics["total"],
            "correct": metrics["correct"],
        }

    except Exception as exc:
        logger.error(
            "Admin eval failed: %s",
            exc,
            extra={
                "component": "eval",
                "eval_type": "admin_agent",
                "eval_run_id": run_id,
            },
        )
        runs_dict[run_id] = {"status": "failed", "error": str(exc)}
