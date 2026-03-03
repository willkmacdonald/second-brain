"""Health check endpoint with Foundry connectivity status."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict:
    """Return service health status including Foundry connectivity."""
    foundry_status = "not_configured"
    foundry_client = getattr(request.app.state, "foundry_client", None)

    if foundry_client is not None:
        foundry_status = "connected"

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

    overall = "ok" if foundry_status == "connected" else "degraded"

    return {
        "status": overall,
        "foundry": foundry_status,
        "cosmos": cosmos_status,
        "admin_agent": admin_status,
    }
