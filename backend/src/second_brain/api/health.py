"""Health check and dashboard summary endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request

from second_brain.observability.queries import query_system_health

logger = logging.getLogger("second_brain")

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict:
    """Return service health status including Foundry connectivity.

    Foundry connectivity is inferred from per-agent readiness on app.state.
    The legacy ``foundry_client`` (RC AzureAIAgentClient) was retired in
    Phase 24; agents are now constructed individually via FoundryChatClient
    factories, so connectivity is asserted indirectly via agent readiness.
    """
    classifier_agent = getattr(request.app.state, "classifier_agent", None)
    admin_agent = getattr(request.app.state, "admin_agent", None)
    investigation_agent = getattr(request.app.state, "investigation_agent", None)

    foundry_status = (
        "connected"
        if classifier_agent is not None
        and admin_agent is not None
        and investigation_agent is not None
        else "degraded"
        if any(
            a is not None for a in (classifier_agent, admin_agent, investigation_agent)
        )
        else "not_configured"
    )

    cosmos_status = (
        "connected"
        if getattr(request.app.state, "cosmos_manager", None) is not None
        else "not_configured"
    )

    admin_status = "ready" if admin_agent is not None else "not_initialized"
    investigation_status = (
        "ready" if investigation_agent is not None else "not_initialized"
    )

    overall = "ok" if foundry_status == "connected" else "degraded"

    return {
        "status": overall,
        "foundry": foundry_status,
        "cosmos": cosmos_status,
        "admin_agent": admin_status,
        "investigation_agent": investigation_status,
    }


@router.get("/api/health-summary")
async def health_summary(request: Request) -> dict:
    """Return dashboard metrics directly from App Insights (no LLM)."""
    logs_client = getattr(request.app.state, "logs_client", None)
    workspace_id = getattr(request.app.state, "log_analytics_workspace_id", "")

    if logs_client is None or not workspace_id:
        raise HTTPException(
            status_code=503,
            detail="App Insights is unavailable.",
        )

    try:
        health = await query_system_health(logs_client, workspace_id)
    except Exception as exc:
        logger.exception("Failed to query system health from App Insights")
        raise HTTPException(
            status_code=502,
            detail="App Insights query failed.",
        ) from exc

    return {
        "captureCount": health.capture_count,
        "successRate": health.success_rate,
        "errorCount": health.error_count + health.failed_capture_count,
        "lastErrorTime": health.last_error_time,
    }
