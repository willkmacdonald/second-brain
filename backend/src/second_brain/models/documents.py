"""Pydantic document schemas for all 5 Cosmos DB containers.

Shared base schema (id, userId, createdAt, updatedAt, rawText, classificationMeta)
with bucket-specific extensions per the locked CONTEXT.md decision.
"""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class BaseDocument(BaseModel):
    """Shared fields across all Cosmos DB containers."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rawText: str
    classificationMeta: dict | None = None


class InboxDocument(BaseDocument):
    """Inbox container document -- raw capture log.

    No additional fields beyond source for Phase 1.
    """

    source: str = "text"


class PeopleDocument(BaseDocument):
    """People container document with person-specific extensions."""

    name: str
    context: str | None = None
    birthday: str | None = None
    contacts: dict | None = None
    lastInteraction: datetime | None = None


class ProjectsDocument(BaseDocument):
    """Projects container document with project-specific extensions."""

    title: str
    status: str = "active"
    nextAction: str | None = None


class IdeasDocument(BaseDocument):
    """Ideas container document with idea-specific extensions."""

    title: str
    tags: list[str] = Field(default_factory=list)


class AdminDocument(BaseDocument):
    """Admin container document with admin-specific extensions."""

    title: str
    nextAction: str | None = None
    dueDate: str | None = None


CONTAINER_MODELS: dict[str, type[BaseDocument]] = {
    "Inbox": InboxDocument,
    "People": PeopleDocument,
    "Projects": ProjectsDocument,
    "Ideas": IdeasDocument,
    "Admin": AdminDocument,
}
