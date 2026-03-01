"""Inbox API endpoints for listing, retrieving, deleting, and recategorizing items.

Queries Cosmos DB Inbox container for recent captures ordered by createdAt DESC.
Follows the same pattern as health.py (APIRouter, include_router in main.py).
"""

import logging
from datetime import UTC, datetime
from uuid import uuid4

from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import APIRouter, HTTPException, Request, Response
from opentelemetry import trace
from pydantic import BaseModel

from second_brain.models.documents import CONTAINER_MODELS, ClassificationMeta

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("second_brain.api")

router = APIRouter()

VALID_BUCKETS = {"People", "Projects", "Ideas", "Admin"}


class RecategorizeRequest(BaseModel):
    """Request body for recategorizing an inbox item to a different bucket."""

    new_bucket: str  # "People", "Projects", "Ideas", or "Admin"  # noqa: N815


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


@router.patch("/api/inbox/{item_id}/recategorize")
async def recategorize_inbox_item(
    request: Request, item_id: str, body: RecategorizeRequest
) -> dict:
    """Move a classified inbox item to a different bucket container.

    Three-step cross-container move: create new bucket doc, update inbox
    metadata, delete old bucket doc (non-fatal). Returns the updated inbox doc.
    Wrapped in an OTel span for per-recategorize tracing in Application Insights.
    """
    with tracer.start_as_current_span("recategorize") as span:
        span.set_attribute("recategorize.item_id", item_id)
        span.set_attribute("recategorize.new_bucket", body.new_bucket)

        try:
            cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
            if cosmos_manager is None:
                raise HTTPException(
                    status_code=503,
                    detail="Cosmos DB not configured. Inbox is unavailable.",
                )

            # Validate bucket name
            if body.new_bucket not in VALID_BUCKETS:
                valid = ", ".join(sorted(VALID_BUCKETS))
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid bucket '{body.new_bucket}'. Valid buckets: {valid}"
                    ),
                )

            # Read the inbox item
            inbox_container = cosmos_manager.get_container("Inbox")
            try:
                item = await inbox_container.read_item(
                    item=item_id, partition_key="will"
                )
            except CosmosResourceNotFoundError as exc:
                raise HTTPException(
                    status_code=404, detail=f"Inbox item {item_id} not found"
                ) from exc

            # Extract old bucket info
            old_meta = item.get("classificationMeta") or {}
            old_bucket = old_meta.get("bucket")
            old_filed_id = item.get("filedRecordId")
            span.set_attribute("recategorize.old_bucket", old_bucket or "")

            # Same-bucket: skip cross-container move, but still promote
            # pending -> classified when user confirms the best-guess bucket.
            if old_bucket == body.new_bucket:
                if item.get("status") == "pending":
                    item["status"] = "classified"
                    item["updatedAt"] = datetime.now(UTC).isoformat()
                    # Tag agent chain with User confirmation
                    old_chain = list(old_meta.get("agentChain", []))
                    if "User" not in old_chain:
                        old_chain.append("User")
                        old_meta["agentChain"] = old_chain
                        old_meta["classifiedBy"] = "User"
                        item["classificationMeta"] = old_meta
                    await inbox_container.upsert_item(body=item)
                span.set_attribute("recategorize.success", True)
                return dict(item)

            # Step 1: Create new bucket document
            new_bucket_doc_id = str(uuid4())

            # Build fresh ClassificationMeta preserving original confidence/allScores
            new_agent_chain = list(old_meta.get("agentChain", []))
            if "User" not in new_agent_chain:
                new_agent_chain.append("User")

            classification_meta = ClassificationMeta(
                bucket=body.new_bucket,
                confidence=old_meta.get("confidence", 0.0),
                allScores=old_meta.get("allScores", {}),
                classifiedBy="User",
                agentChain=new_agent_chain,
                classifiedAt=datetime.now(UTC),
            )

            model_class = CONTAINER_MODELS[body.new_bucket]
            kwargs: dict = {
                "id": new_bucket_doc_id,
                "rawText": item.get("rawText", ""),
                "classificationMeta": classification_meta,
                "inboxRecordId": item_id,
            }
            if body.new_bucket == "People":
                kwargs["name"] = item.get("title") or "Unnamed"
            else:
                kwargs["title"] = item.get("title") or "Untitled"

            bucket_doc = model_class(**kwargs)
            target_container = cosmos_manager.get_container(body.new_bucket)
            await target_container.create_item(
                body=bucket_doc.model_dump(mode="json")
            )

            # Step 2: Update inbox document
            item["classificationMeta"] = classification_meta.model_dump(mode="json")
            item["filedRecordId"] = new_bucket_doc_id
            item["status"] = "classified"
            item["updatedAt"] = datetime.now(UTC).isoformat()
            await inbox_container.upsert_item(body=item)

            # Step 3: Delete old bucket document (non-fatal)
            if old_filed_id and old_bucket:
                try:
                    old_container = cosmos_manager.get_container(old_bucket)
                    await old_container.delete_item(
                        item=old_filed_id, partition_key="will"
                    )
                except Exception:
                    logger.warning(
                        "Could not delete old bucket doc %s/%s during recategorize",
                        old_bucket,
                        old_filed_id,
                    )

            span.set_attribute("recategorize.success", True)
            logger.info(
                "Recategorized inbox %s: %s -> %s",
                item_id,
                old_bucket,
                body.new_bucket,
            )
            return dict(item)

        except HTTPException:
            span.set_attribute("recategorize.success", False)
            raise
        except Exception as e:
            span.set_attribute("recategorize.success", False)
            span.record_exception(e)
            raise
