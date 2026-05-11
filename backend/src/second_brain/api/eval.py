"""Eval API endpoints for triggering and monitoring eval runs.

Phase 24 plan 24-18: the temporary _MigrationHybridInvoker / RCEvalAgentInvoker
seam introduced in 24-12 is gone. Both eval types now construct a plain
``GAEvalAgentInvoker(classifier_agent=..., admin_agent=...)`` using the GA
Agent singletons published on ``app.state``:

- ``app.state.classifier_agent`` -- GA Agent built by 24-14
- ``app.state.admin_agent``      -- GA Agent built by 24-09

Eval runs no longer touch the legacy ``app.state.classifier_client`` /
``app.state.admin_client`` attributes (those are W-03 dead-code references
slated for sweep in 24-19).
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from second_brain.eval.invoker import GAEvalAgentInvoker
from second_brain.eval.runner import run_admin_eval, run_classifier_eval

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory eval run tracking (single-user system; acceptable per RESEARCH.md)
_eval_runs: dict[str, dict] = {}


class EvalRunRequest(BaseModel):
    """Request body for triggering an eval run."""

    eval_type: str  # "classifier" or "admin_agent"
    routing_context: str | None = None  # Required for admin_agent eval per D-13


def _build_eval_invoker(
    classifier_agent: object | None,
    admin_agent: object | None,
) -> GAEvalAgentInvoker:
    """Construct the GA eval invoker.

    Both ``classifier_agent`` and ``admin_agent`` are ``agent_framework.Agent``
    instances published on ``app.state`` by main.py lifespan (24-14 and 24-09
    respectively). The caller has already validated that the side needed for
    the requested eval_type is non-None before calling here, so we pass through
    whatever the lifespan produced.
    """
    return GAEvalAgentInvoker(
        classifier_agent=classifier_agent,  # type: ignore[arg-type]
        admin_agent=admin_agent,  # type: ignore[arg-type]
    )


@router.post("/api/eval/run", status_code=202)
async def start_eval_run(request: Request, body: EvalRunRequest) -> dict:
    """Trigger an eval run as a background task.

    Returns immediately with a run ID for status polling.
    Single in-flight guard rejects concurrent runs of the same type (T-21-07).
    """
    # Validate eval_type
    if body.eval_type not in ("classifier", "admin_agent"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid eval_type '{body.eval_type}'."
                " Must be 'classifier' or 'admin_agent'."
            ),
        )

    # Single in-flight guard: reject if same type already running
    for rid, run in _eval_runs.items():
        if run.get("eval_type") == body.eval_type and run.get("status") == "running":
            raise HTTPException(
                status_code=409,
                detail="Eval already running",
                headers={"X-Existing-Run-Id": rid},
            )

    # Admin eval requires routing_context
    if body.eval_type == "admin_agent" and body.routing_context is None:
        raise HTTPException(
            status_code=400,
            detail="routing_context is required for admin_agent eval.",
        )

    # Get dependencies from app state
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(status_code=503, detail="Cosmos DB not configured.")

    run_id = str(uuid4())
    _eval_runs[run_id] = {
        "status": "running",
        "eval_type": body.eval_type,
        "started_at": datetime.now(UTC).isoformat(),
    }

    if body.eval_type == "classifier":
        classifier_agent = getattr(request.app.state, "classifier_agent", None)
        if classifier_agent is None:
            del _eval_runs[run_id]
            raise HTTPException(
                status_code=503, detail="Classifier agent not configured."
            )
        admin_agent = getattr(request.app.state, "admin_agent", None)
        invoker = _build_eval_invoker(
            classifier_agent=classifier_agent,
            admin_agent=admin_agent,
        )
        task = asyncio.create_task(
            run_classifier_eval(
                run_id=run_id,
                cosmos_manager=cosmos_manager,
                invoker=invoker,
                runs_dict=_eval_runs,
            )
        )
    else:
        admin_agent = getattr(request.app.state, "admin_agent", None)
        if admin_agent is None:
            del _eval_runs[run_id]
            raise HTTPException(status_code=503, detail="Admin agent not configured.")
        classifier_agent = getattr(request.app.state, "classifier_agent", None)
        invoker = _build_eval_invoker(
            classifier_agent=classifier_agent,
            admin_agent=admin_agent,
        )
        task = asyncio.create_task(
            run_admin_eval(
                run_id=run_id,
                cosmos_manager=cosmos_manager,
                invoker=invoker,
                routing_context=body.routing_context,
                runs_dict=_eval_runs,
            )
        )

    # GC prevention: strong reference until task completes
    bg_tasks: set = getattr(request.app.state, "background_tasks", set())
    bg_tasks.add(task)
    task.add_done_callback(bg_tasks.discard)

    logger.info(
        "Eval run started: run_id=%s eval_type=%s",
        run_id,
        body.eval_type,
        extra={"component": "eval", "eval_run_id": run_id},
    )

    return {"runId": run_id, "status": "running", "evalType": body.eval_type}


@router.get("/api/eval/status/{run_id}")
async def get_eval_status(run_id: str) -> dict:
    """Get the current status of an eval run."""
    run = _eval_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Eval run '{run_id}' not found.")
    return {"runId": run_id, **run}


@router.get("/api/eval/results")
async def get_eval_results(
    request: Request,
    eval_type: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=50),
) -> dict:
    """Get recent eval results from Cosmos DB.

    Returns aggregate scores only (individualResults stripped for T-21-08).
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(status_code=503, detail="Cosmos DB not configured.")

    try:
        container = cosmos_manager.get_container("EvalResults")

        query = "SELECT * FROM c WHERE c.userId = @userId"
        parameters: list[dict[str, str]] = [
            {"name": "@userId", "value": "will"},
        ]

        if eval_type is not None:
            query += " AND c.evalType = @evalType"
            parameters.append({"name": "@evalType", "value": eval_type})

        query += " ORDER BY c.runTimestamp DESC"

        results: list[dict] = []
        async for item in container.query_items(
            query=query,
            parameters=parameters,
        ):
            # Strip individualResults to keep response small (T-21-08)
            summary = {
                "id": item["id"],
                "evalType": item.get("evalType"),
                "runTimestamp": item.get("runTimestamp"),
                "datasetSize": item.get("datasetSize"),
                "aggregateScores": item.get("aggregateScores"),
                "modelDeployment": item.get("modelDeployment"),
            }
            results.append(summary)
            if len(results) >= limit:
                break

        return {"results": results, "count": len(results)}

    except Exception as exc:
        logger.error("Failed to query eval results: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503, detail="Failed to retrieve eval results."
        ) from None
