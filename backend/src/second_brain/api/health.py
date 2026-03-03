"""Health check endpoint with Foundry connectivity status."""

import traceback

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


@router.get("/health/debug-admin")
async def debug_admin_query(request: Request) -> dict:
    """Temporary diagnostic: run the admin retry query and return results."""
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    admin_client = getattr(request.app.state, "admin_client", None)
    admin_tools = getattr(request.app.state, "admin_agent_tools", [])

    result: dict = {
        "admin_client_set": admin_client is not None,
        "admin_tools_count": len(admin_tools),
        "cosmos_available": cosmos_manager is not None,
    }

    if cosmos_manager is None:
        result["error"] = "No cosmos_manager"
        return result

    try:
        inbox_container = cosmos_manager.get_container("Inbox")
        query = (
            "SELECT c.id, c.rawText, c.adminProcessingStatus, "
            "c.classificationMeta.bucket AS bucket, c.userId FROM c "
            "WHERE c.userId = @userId "
            "AND c.classificationMeta.bucket = 'Admin' "
            "AND (NOT IS_DEFINED(c.adminProcessingStatus) "
            "     OR c.adminProcessingStatus = 'failed' "
            "     OR c.adminProcessingStatus = 'pending')"
        )
        parameters: list[dict[str, object]] = [
            {"name": "@userId", "value": "will"},
        ]

        items: list[dict] = []
        async for item in inbox_container.query_items(
            query=query,
            parameters=parameters,
            partition_key="will",
        ):
            items.append(item)

        result["unprocessed_count"] = len(items)
        result["unprocessed_items"] = items
    except Exception:
        result["error"] = traceback.format_exc()

    return result
