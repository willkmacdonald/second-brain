"""Health check and dashboard summary endpoints."""

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException, Request

from second_brain.observability.queries import query_system_health

logger = logging.getLogger("second_brain")

router = APIRouter()

# Cache TTL for Foundry health check (seconds). Mutable state lives on
# app.state to avoid cross-process leakage in tests.
_FOUNDRY_CACHE_TTL = 60.0


@router.get("/health")
async def health_check(request: Request) -> dict:
    """Return service health status including Foundry connectivity."""
    foundry_status = "not_configured"
    foundry_client = getattr(request.app.state, "foundry_client", None)

    if foundry_client is not None:
        # Active Foundry connectivity check with TTL cache on app.state
        now = time.monotonic()
        cache = getattr(request.app.state, "_foundry_health_cache", None)
        if cache is not None and (now - cache["checked_at"]) < _FOUNDRY_CACHE_TTL:
            foundry_status = cache["status"]
        else:
            try:
                async with asyncio.timeout(5):
                    async for _ in foundry_client.agents_client.list_agents(limit=1):
                        break
                foundry_status = "connected"
            except Exception:
                foundry_status = "degraded"
            request.app.state._foundry_health_cache = {
                "status": foundry_status,
                "checked_at": now,
            }

    cosmos_status = (
        "connected"
        if getattr(request.app.state, "cosmos_manager", None) is not None
        else "not_configured"
    )

    admin_status = (
        "ready"
        if getattr(request.app.state, "admin_client", None) is not None
        else "not_initialized"
    )

    investigation_status = (
        "ready"
        if getattr(request.app.state, "investigation_client", None) is not None
        else "not_initialized"
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
    }
