"""Shopping Lists API endpoints for reading and deleting shopping list items.

Queries the Cosmos DB ShoppingLists container which uses /store as partition key.
Items are grouped by store with display names for the mobile Status screen.

GET /api/shopping-lists also triggers Admin Agent processing as a side effect
when there are unprocessed Admin inbox items.
"""

import asyncio
import logging

from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from second_brain.models.documents import KNOWN_STORES
from second_brain.processing.admin_handoff import (
    process_admin_capture,
    process_admin_captures_batch,
)

logger = logging.getLogger(__name__)

router = APIRouter()

STORE_DISPLAY_NAMES: dict[str, str] = {
    "jewel": "Jewel-Osco",
    "cvs": "CVS",
    "pet_store": "Pet Store",
    "other": "Other",
}


class ShoppingItemResponse(BaseModel):
    """Single shopping list item."""

    id: str
    name: str
    store: str


class StoreSection(BaseModel):
    """A group of shopping items for a single store."""

    store: str
    displayName: str  # noqa: N815
    items: list[ShoppingItemResponse]
    count: int


class ShoppingListResponse(BaseModel):
    """Full shopping list response with items grouped by store."""

    stores: list[StoreSection]
    totalCount: int  # noqa: N815
    processingCount: int = 0  # noqa: N815


@router.get("/api/shopping-lists", response_model=ShoppingListResponse)
async def get_shopping_lists(request: Request) -> ShoppingListResponse:
    """List all shopping list items grouped by store.

    Queries each known store partition individually and returns sections
    sorted by item count descending (most items first). Empty stores
    are excluded from the response.
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured. Shopping lists unavailable.",
        )

    container = cosmos_manager.get_container("ShoppingLists")

    sections: list[StoreSection] = []
    total_count = 0

    for store in KNOWN_STORES:
        items: list[ShoppingItemResponse] = []
        async for item in container.query_items(
            query="SELECT * FROM c",
            partition_key=store,
        ):
            items.append(
                ShoppingItemResponse(
                    id=item["id"],
                    name=item["name"],
                    store=item.get("store", store),
                )
            )

        if items:
            display_name = STORE_DISPLAY_NAMES.get(
                store, store.replace("_", " ").title()
            )
            sections.append(
                StoreSection(
                    store=store,
                    displayName=display_name,
                    items=items,
                    count=len(items),
                )
            )
            total_count += len(items)

    # Sort by item count descending (most items first)
    sections.sort(key=lambda s: s.count, reverse=True)

    # Side effect: trigger Admin Agent processing for unprocessed items
    processing_count = 0
    try:
        admin_client = getattr(
            request.app.state, "admin_client", None
        )
        if admin_client is not None:
            inbox_container = cosmos_manager.get_container("Inbox")
            query = (
                "SELECT c.id, c.rawText FROM c "
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
            in_flight: set = getattr(
                request.app.state, "admin_processing_ids", set()
            )
            new_items = [
                i for i in unprocessed if i["id"] not in in_flight
            ]

            if new_items:
                processing_count = len(new_items)
                admin_tools = getattr(
                    request.app.state, "admin_agent_tools", []
                )
                bg_tasks: set = getattr(
                    request.app.state, "background_tasks", set()
                )

                # Mark items as in-flight before creating tasks
                new_ids = {i["id"] for i in new_items}
                in_flight.update(new_ids)

                def _cleanup_in_flight(
                    _task, ids=new_ids, inflight=in_flight,
                ):
                    inflight.difference_update(ids)

                if len(new_items) == 1:
                    task = asyncio.create_task(
                        process_admin_capture(
                            admin_client=admin_client,
                            admin_tools=admin_tools,
                            cosmos_manager=cosmos_manager,
                            inbox_item_id=new_items[0]["id"],
                            raw_text=new_items[0].get(
                                "rawText", ""
                            ),
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
                                    "raw_text": i.get(
                                        "rawText", ""
                                    ),
                                }
                                for i in new_items
                            ],
                        )
                    )
                bg_tasks.add(task)
                task.add_done_callback(bg_tasks.discard)
                task.add_done_callback(_cleanup_in_flight)
                logger.info(
                    "Triggered Admin Agent processing for "
                    "%d item(s)",
                    processing_count,
                )
            elif unprocessed:
                # Items exist but already in-flight — report as processing
                processing_count = len(unprocessed)
    except Exception:
        logger.warning(
            "Failed to trigger Admin Agent processing",
            exc_info=True,
        )

    logger.info(
        "Shopping lists: %d stores, %d total items",
        len(sections),
        total_count,
    )
    return ShoppingListResponse(
        stores=sections,
        totalCount=total_count,
        processingCount=processing_count,
    )


@router.delete("/api/shopping-lists/items/{item_id}", status_code=204)
async def delete_shopping_item(
    request: Request,
    item_id: str,
    store: str = Query(..., description="Store name (partition key)"),
) -> Response:
    """Delete a shopping list item by ID and store partition key.

    Returns 204 No Content on success, 400 for unknown store,
    404 if item not found.
    """
    if store not in KNOWN_STORES:
        valid = ", ".join(KNOWN_STORES)
        raise HTTPException(
            status_code=400,
            detail=f"Unknown store '{store}'. Valid stores: {valid}",
        )

    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured. Shopping lists unavailable.",
        )

    container = cosmos_manager.get_container("ShoppingLists")

    try:
        await container.delete_item(item=item_id, partition_key=store)
    except CosmosResourceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Shopping list item {item_id} not found in store '{store}'",
        ) from exc

    logger.info("Deleted shopping list item %s from store '%s'", item_id, store)
    return Response(status_code=204)
