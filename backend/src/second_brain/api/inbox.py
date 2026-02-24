"""Inbox API endpoints for listing, retrieving, and deleting captured items.

Queries Cosmos DB Inbox container for recent captures ordered by createdAt DESC.
Follows the same pattern as health.py (APIRouter, include_router in main.py).
"""

import logging

from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# Response models use camelCase field names per project convention (Ruff N815 ignore)
class InboxItemResponse(BaseModel):  # noqa: N815
    """Single inbox item returned by the list endpoint."""

    id: str
    rawText: str  # noqa: N815
    title: str | None = None
    status: str
    createdAt: str  # noqa: N815
    classificationMeta: dict | None = None  # noqa: N815
    clarificationText: str | None = None  # noqa: N815


class InboxListResponse(BaseModel):
    """Paginated list of inbox items."""

    items: list[InboxItemResponse]
    count: int


@router.get("/api/inbox", response_model=InboxListResponse)
async def list_inbox(
    request: Request, limit: int = 20, offset: int = 0
) -> InboxListResponse:
    """List recent Inbox captures ordered by creation time (newest first).

    Queries the Cosmos DB Inbox container for the authenticated user,
    returning classification metadata with each item.
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured. Inbox is unavailable.",
        )

    container = cosmos_manager.get_container("Inbox")

    query = (
        "SELECT * FROM c WHERE c.userId = @userId "
        "ORDER BY c.createdAt DESC "
        "OFFSET @offset LIMIT @limit"
    )
    parameters: list[dict[str, object]] = [
        {"name": "@userId", "value": "will"},
        {"name": "@offset", "value": offset},
        {"name": "@limit", "value": limit},
    ]

    items: list[InboxItemResponse] = []
    async for item in container.query_items(
        query=query,
        parameters=parameters,
        partition_key="will",
    ):
        items.append(
            InboxItemResponse(
                id=item["id"],
                rawText=item.get("rawText", ""),
                title=item.get("title"),
                status=item.get("status", "unknown"),
                createdAt=item.get("createdAt", ""),
                classificationMeta=item.get("classificationMeta"),
                clarificationText=item.get("clarificationText"),
            )
        )

    logger.info(
        "Inbox list: returned %d items (offset=%d, limit=%d)",
        len(items),
        offset,
        limit,
    )
    return InboxListResponse(items=items, count=len(items))


@router.get("/api/inbox/{item_id}")
async def get_inbox_item(request: Request, item_id: str) -> dict:
    """Retrieve a single Inbox item by ID.

    Returns the full Cosmos DB document for the item detail view.
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured. Inbox is unavailable.",
        )

    container = cosmos_manager.get_container("Inbox")

    try:
        item = await container.read_item(item=item_id, partition_key="will")
    except CosmosResourceNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Inbox item {item_id} not found"
        ) from exc

    return dict(item)


@router.delete("/api/inbox/{item_id}", status_code=204)
async def delete_inbox_item(request: Request, item_id: str) -> Response:
    """Delete an Inbox item and its associated bucket document (cascade).

    If the item has a filedRecordId and a known bucket, the corresponding
    bucket document is also deleted to maintain referential integrity.
    Returns 204 No Content on success, 404 if item not found.
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured. Inbox is unavailable.",
        )

    inbox_container = cosmos_manager.get_container("Inbox")

    # Read item first to get cascade info
    try:
        item = await inbox_container.read_item(item=item_id, partition_key="will")
    except CosmosResourceNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Inbox item {item_id} not found"
        ) from exc

    # Cascade delete: remove the filed bucket document if it exists
    filed_record_id = item.get("filedRecordId")
    bucket_name = (item.get("classificationMeta") or {}).get("bucket")
    if filed_record_id and bucket_name:
        try:
            bucket_container = cosmos_manager.get_container(bucket_name)
            await bucket_container.delete_item(
                item=filed_record_id, partition_key="will"
            )
            logger.info(
                "Cascade deleted %s/%s for inbox item %s",
                bucket_name,
                filed_record_id,
                item_id,
            )
        except CosmosResourceNotFoundError:
            logger.warning(
                "Bucket document %s/%s already missing during cascade delete",
                bucket_name,
                filed_record_id,
            )
        except ValueError:
            logger.warning(
                "Unknown bucket '%s' during cascade delete for inbox item %s",
                bucket_name,
                item_id,
            )

    # Delete the inbox document
    await inbox_container.delete_item(item=item_id, partition_key="will")
    logger.info("Deleted inbox item %s", item_id)

    return Response(status_code=204)
