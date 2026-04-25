"""Eval API endpoints for triggering and monitoring eval runs."""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from second_brain.eval.runner import run_admin_eval, run_classifier_eval

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory eval run tracking (single-user system; acceptable per RESEARCH.md)
_eval_runs: dict[str, dict] = {}


class EvalRunRequest(BaseModel):
    """Request body for triggering an eval run."""

    eval_type: str  # "classifier" or "admin_agent"
    routing_context: str | None = None  # Required for admin_agent eval per D-13


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
        classifier_client = getattr(request.app.state, "classifier_client", None)
        if classifier_client is None:
            del _eval_runs[run_id]
            raise HTTPException(
                status_code=503, detail="Classifier agent not configured."
            )
        task = asyncio.create_task(
            run_classifier_eval(
                run_id=run_id,
                cosmos_manager=cosmos_manager,
                classifier_client=classifier_client,
                runs_dict=_eval_runs,
            )
        )
    else:
        admin_client = getattr(request.app.state, "admin_client", None)
        if admin_client is None:
            del _eval_runs[run_id]
            raise HTTPException(status_code=503, detail="Admin agent not configured.")
        task = asyncio.create_task(
            run_admin_eval(
                run_id=run_id,
                cosmos_manager=cosmos_manager,
                admin_client=admin_client,
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
