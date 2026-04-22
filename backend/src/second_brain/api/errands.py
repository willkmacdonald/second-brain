"""Errands API endpoints for reading, deleting, and routing errand items.

Queries the Cosmos DB Errands container which uses /destination as partition key.
Items are grouped by destination with display names for the mobile Status screen.
Destinations are loaded dynamically from the Destinations container.

GET /api/errands also triggers Admin Agent processing as a side effect
when there are unprocessed Admin inbox items, and returns admin notifications
for completed agent responses that need user attention.
"""

import asyncio
import logging

from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from second_brain.models.documents import (
    AffinityRuleDocument,
    FeedbackDocument,
)
from second_brain.processing.admin_handoff import (
    process_admin_capture,
    process_admin_captures_batch,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ErrandItemResponse(BaseModel):
    """Single errand item."""

    id: str
    name: str
    destination: str
    needsRouting: bool = False  # noqa: N815
    sourceName: str | None = None  # noqa: N815
    sourceUrl: str | None = None  # noqa: N815


class DestinationSection(BaseModel):
    """A group of errand items for a single destination."""

    destination: str
    displayName: str  # noqa: N815
    type: str = "physical"  # "physical", "online", or "unrouted"
    items: list[ErrandItemResponse]
    count: int


class AdminNotification(BaseModel):
    """A message from the Admin Agent that needs user attention."""

    inboxItemId: str  # noqa: N815
    message: str


class ErrandsResponse(BaseModel):
    """Full errands response with items grouped by destination."""

    destinations: list[DestinationSection]
    totalCount: int  # noqa: N815
    processingCount: int = 0  # noqa: N815
    adminNotifications: list[AdminNotification] = []  # noqa: N815


class RouteItemBody(BaseModel):
    """Request body for routing an unrouted errand item."""

    destinationSlug: str = Field(..., max_length=100)  # noqa: N815
    saveRule: bool = True  # noqa: N815


@router.get("/api/errands", response_model=ErrandsResponse)
async def get_errands(request: Request) -> ErrandsResponse:
    """List all errand items grouped by destination.

    Queries destinations dynamically from the Destinations container, then
    fetches errand items per destination partition. Returns sections sorted
    by item count descending (most items first). Empty destinations are
    excluded from the response. Unrouted items appear as a special section.
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured. Errands unavailable.",
        )

    container = cosmos_manager.get_container("Errands")

    # Load destinations dynamically from Cosmos
    dest_container = cosmos_manager.get_container("Destinations")
    destinations: list[dict] = []
    async for doc in dest_container.query_items(
        query="SELECT * FROM c",
        partition_key="will",
    ):
        destinations.append(doc)

    sections: list[DestinationSection] = []
    total_count = 0

    for dest in destinations:
        slug = dest["slug"]
        items: list[ErrandItemResponse] = []
        async for item in container.query_items(
            query="SELECT * FROM c",
            partition_key=slug,
        ):
            items.append(
                ErrandItemResponse(
                    id=item["id"],
                    name=item["name"],
                    destination=item.get("destination", slug),
                    needsRouting=item.get("needsRouting", False),
                    sourceName=item.get("sourceName"),
                    sourceUrl=item.get("sourceUrl"),
                )
            )

        if items:
            sections.append(
                DestinationSection(
                    destination=slug,
                    displayName=dest["displayName"],
                    type=dest.get("type", "physical"),
                    items=items,
                    count=len(items),
                )
            )
            total_count += len(items)

    # Check for unrouted items
    unrouted_items: list[ErrandItemResponse] = []
    async for item in container.query_items(
        query="SELECT * FROM c",
        partition_key="unrouted",
    ):
        unrouted_items.append(
            ErrandItemResponse(
                id=item["id"],
                name=item["name"],
                destination="unrouted",
                needsRouting=True,
                sourceName=item.get("sourceName"),
                sourceUrl=item.get("sourceUrl"),
            )
        )

    if unrouted_items:
        sections.append(
            DestinationSection(
                destination="unrouted",
                displayName="Needs Routing",
                type="unrouted",
                items=unrouted_items,
                count=len(unrouted_items),
            )
        )
        total_count += len(unrouted_items)

    # Sort by item count descending (most items first)
    sections.sort(key=lambda s: s.count, reverse=True)

    # Side effect: trigger Admin Agent processing for unprocessed items
    processing_count = 0
    try:
        admin_client = getattr(request.app.state, "admin_client", None)
        if admin_client is not None:
            inbox_container = cosmos_manager.get_container("Inbox")
            query = (
                "SELECT c.id, c.rawText, c.captureTraceId FROM c "
                "WHERE c.userId = @userId "
                "AND c.classificationMeta.bucket = 'Admin' "
                "AND (NOT IS_DEFINED(c.adminProcessingStatus) "
                "     OR IS_NULL(c.adminProcessingStatus) "
                "     OR c.adminProcessingStatus = 'failed' "
                "     OR c.adminProcessingStatus = 'pending')"
            )
            parameters: list[dict[str, object]] = [
                {"name": "@userId", "value": "will"},
            ]

            unprocessed: list[dict] = []
            async for item in inbox_container.query_items(
                query=query,
                parameters=parameters,
                partition_key="will",
            ):
                unprocessed.append(item)

            # Filter out items already being processed in-flight
            in_flight: set = getattr(request.app.state, "admin_processing_ids", set())
            new_items = [i for i in unprocessed if i["id"] not in in_flight]

            if new_items:
                processing_count = len(new_items)
                admin_tools = getattr(request.app.state, "admin_agent_tools", [])
                bg_tasks: set = getattr(request.app.state, "background_tasks", set())

                # Mark items as in-flight before creating tasks
                new_ids = {i["id"] for i in new_items}
                in_flight.update(new_ids)

                def _cleanup_in_flight(
                    _task,
                    ids=new_ids,
                    inflight=in_flight,
                ):
                    inflight.difference_update(ids)

                spine_repo = getattr(request.app.state, "spine_repo", None)
                if len(new_items) == 1:
                    task = asyncio.create_task(
                        process_admin_capture(
                            admin_client=admin_client,
                            admin_tools=admin_tools,
                            cosmos_manager=cosmos_manager,
                            inbox_item_id=new_items[0]["id"],
                            raw_text=new_items[0].get("rawText", ""),
                            capture_trace_id=new_items[0].get("captureTraceId", ""),
                            spine_repo=spine_repo,
                        )
                    )
                else:
                    task = asyncio.create_task(
                        process_admin_captures_batch(
                            admin_client=admin_client,
                            admin_tools=admin_tools,
                            cosmos_manager=cosmos_manager,
                            admin_items=[
                                {
                                    "inbox_item_id": i["id"],
                                    "raw_text": i.get("rawText", ""),
                                    "capture_trace_id": i.get("captureTraceId", ""),
                                }
                                for i in new_items
                            ],
                            spine_repo=spine_repo,
                        )
                    )
                bg_tasks.add(task)
                task.add_done_callback(bg_tasks.discard)
                task.add_done_callback(_cleanup_in_flight)
                logger.info(
                    "Triggered Admin Agent processing for %d item(s)",
                    processing_count,
                )
            elif unprocessed:
                # Items exist but already in-flight -- report as processing
                processing_count = len(unprocessed)
    except Exception:
        logger.warning(
            "Failed to trigger Admin Agent processing",
            exc_info=True,
        )

    # Query for completed admin items with responses to deliver
    notifications: list[AdminNotification] = []
    try:
        inbox_container = cosmos_manager.get_container("Inbox")
        notify_query = (
            "SELECT c.id, c.adminAgentResponse FROM c "
            "WHERE c.userId = @userId "
            "AND c.adminProcessingStatus = 'completed' "
            "AND IS_DEFINED(c.adminAgentResponse) "
            "AND NOT IS_NULL(c.adminAgentResponse)"
        )
        notify_params: list[dict[str, object]] = [
            {"name": "@userId", "value": "will"},
        ]
        async for item in inbox_container.query_items(
            query=notify_query,
            parameters=notify_params,
            partition_key="will",
        ):
            notifications.append(
                AdminNotification(
                    inboxItemId=item["id"],
                    message=item["adminAgentResponse"],
                )
            )
    except Exception:
        logger.warning(
            "Failed to query admin notifications",
            exc_info=True,
        )

    logger.debug(
        "Errands: %d destinations, %d total items, %d notifications",
        len(sections),
        total_count,
        len(notifications),
    )
    return ErrandsResponse(
        destinations=sections,
        totalCount=total_count,
        processingCount=processing_count,
        adminNotifications=notifications,
    )


@router.delete("/api/errands/{item_id}", status_code=204)
async def delete_errand_item(
    request: Request,
    item_id: str,
    destination: str = Query(..., description="Destination name (partition key)"),
) -> Response:
    """Delete an errand item by ID and destination partition key.

    Returns 204 No Content on success, 404 if item not found.
    Accepts any destination string -- no hardcoded validation.
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured. Errands unavailable.",
        )

    container = cosmos_manager.get_container("Errands")

    try:
        await container.delete_item(item=item_id, partition_key=destination)
    except CosmosResourceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Errand item {item_id} not found in destination '{destination}'",
        ) from exc

    logger.info("Deleted errand item %s from destination '%s'", item_id, destination)
    return Response(status_code=204)


@router.post("/api/errands/{item_id}/route")
async def route_errand_item(
    request: Request,
    item_id: str,
    body: RouteItemBody,
) -> dict:
    """Move an unrouted errand item to a destination and optionally save a rule.

    1. Read the unrouted item from Errands container (partition_key="unrouted")
    2. Validate that destinationSlug matches a known destination
    3. Create a new ErrandItem in the target destination partition
    4. Delete the old unrouted item
    5. If saveRule=True, create an AffinityRuleDocument with autoSaved=True
    6. Return confirmation
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured. Errands unavailable.",
        )

    container = cosmos_manager.get_container("Errands")

    # Read the unrouted item
    try:
        item = await container.read_item(item=item_id, partition_key="unrouted")
    except CosmosResourceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Unrouted errand item {item_id} not found",
        ) from exc

    # Validate destination exists
    dest_container = cosmos_manager.get_container("Destinations")
    dest_exists = False
    async for _doc in dest_container.query_items(
        query="SELECT c.slug FROM c WHERE c.slug = @slug",
        parameters=[{"name": "@slug", "value": body.destinationSlug}],
        partition_key="will",
    ):
        dest_exists = True
        break

    if not dest_exists:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown destination '{body.destinationSlug}'",
        )

    # Create item in target destination
    item_name = item["name"]
    await container.create_item(
        body={
            "id": item_id,
            "destination": body.destinationSlug,
            "name": item_name,
        }
    )

    # Delete from unrouted
    await container.delete_item(item=item_id, partition_key="unrouted")

    # --- Feedback signal (fire-and-forget) ---
    try:
        feedback_doc = FeedbackDocument(
            signalType="errand_reroute",
            captureText=item_name,
            originalBucket="unrouted",
            correctedBucket=body.destinationSlug,
            captureTraceId=None,
        )
        fb_container = cosmos_manager.get_container("Feedback")
        await fb_container.create_item(body=feedback_doc.model_dump(mode="json"))
    except Exception:
        logger.warning(
            "Failed to write feedback signal for errand re-route %s",
            item_id,
            exc_info=True,
        )

    # Optionally save an affinity rule
    if body.saveRule:
        rules_container = cosmos_manager.get_container("AffinityRules")
        rule = AffinityRuleDocument(
            naturalLanguage=f"{item_name} goes to {body.destinationSlug}",
            itemPattern=item_name,
            destinationSlug=body.destinationSlug,
            ruleType="item",
            autoSaved=True,
        )
        await rules_container.create_item(body=rule.model_dump(mode="json"))

    logger.info(
        "Routed errand item %s ('%s') to %s (rule saved: %s)",
        item_id,
        item_name,
        body.destinationSlug,
        body.saveRule,
    )
    return {
        "message": f"Routed '{item_name}' to {body.destinationSlug}",
        "ruleSaved": body.saveRule,
    }


@router.post(
    "/api/errands/notifications/{inbox_item_id}/dismiss",
    status_code=204,
)
async def dismiss_admin_notification(
    request: Request,
    inbox_item_id: str,
) -> Response:
    """Dismiss an admin notification by deleting the completed inbox item.

    The mobile app calls this after the user has seen the notification.
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured.",
        )

    inbox_container = cosmos_manager.get_container("Inbox")

    try:
        await inbox_container.delete_item(item=inbox_item_id, partition_key="will")
    except CosmosResourceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Notification {inbox_item_id} not found",
        ) from exc

    logger.info("Dismissed admin notification %s", inbox_item_id)
    return Response(status_code=204)
