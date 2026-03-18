"""Tasks API endpoints for reading and deleting task items.

Queries the Cosmos DB Tasks container which uses /userId as partition key.
Tasks are actionable to-dos routed from Admin captures that aren't errands
(e.g., appointments, expenses, phone calls).

GET /api/tasks returns all tasks for the user.
DELETE /api/tasks/{item_id} removes a completed task.
"""

import logging

from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class TaskItemResponse(BaseModel):
    """Single task item."""

    id: str
    name: str
    createdAt: str | None = None  # noqa: N815


class TasksResponse(BaseModel):
    """Full tasks response."""

    tasks: list[TaskItemResponse]
    totalCount: int  # noqa: N815


@router.get("/api/tasks", response_model=TasksResponse)
async def get_tasks(request: Request) -> TasksResponse:
    """List all task items for the user.

    Returns tasks sorted by creation date (newest first).
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured. Tasks unavailable.",
        )

    container = cosmos_manager.get_container("Tasks")

    items: list[TaskItemResponse] = []
    async for item in container.query_items(
        query="SELECT * FROM c ORDER BY c.createdAt DESC",
        partition_key="will",
    ):
        items.append(
            TaskItemResponse(
                id=item["id"],
                name=item["name"],
                createdAt=item.get("createdAt"),
            )
        )

    logger.info("Tasks: %d items", len(items))
    return TasksResponse(tasks=items, totalCount=len(items))


@router.delete("/api/tasks/{item_id}", status_code=204)
async def delete_task_item(
    request: Request,
    item_id: str,
) -> Response:
    """Delete a task item by ID.

    Returns 204 No Content on success, 404 if item not found.
    """
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Cosmos DB not configured. Tasks unavailable.",
        )

    container = cosmos_manager.get_container("Tasks")

    try:
        await container.delete_item(item=item_id, partition_key="will")
    except CosmosResourceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Task item {item_id} not found",
        ) from exc

    logger.info("Deleted task item %s", item_id)
    return Response(status_code=204)
