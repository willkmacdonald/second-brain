"""Shopping Lists API endpoints for reading and deleting shopping list items.

Queries the Cosmos DB ShoppingLists container which uses /store as partition key.
Items are grouped by store with display names for the mobile Status screen.
"""

import logging

from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from second_brain.models.documents import KNOWN_STORES

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

    logger.info(
        "Shopping lists: %d stores, %d total items",
        len(sections),
        total_count,
    )
    return ShoppingListResponse(stores=sections, totalCount=total_count)


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
