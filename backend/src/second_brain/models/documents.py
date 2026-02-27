"""Pydantic document schemas for all 5 Cosmos DB containers.

Shared base schema (id, userId, createdAt, updatedAt, rawText, classificationMeta)
with bucket-specific extensions per the locked CONTEXT.md decision.
"""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class ClassificationMeta(BaseModel):
    """Structured classification metadata attached to every filed document.

    All fields use camelCase per Phase 1 convention for Cosmos DB JSON.
    """

    bucket: str
    confidence: float
    allScores: dict[str, float]
    classifiedBy: str
    agentChain: list[str]
    classifiedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BaseDocument(BaseModel):
    """Shared fields across all Cosmos DB containers."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rawText: str
    classificationMeta: ClassificationMeta | None = None


class InboxDocument(BaseDocument):
    """Inbox container document -- raw capture log.

    Includes classification metadata, bi-directional link to bucket record,
    and status tracking.
    """

    source: str = "text"
    filedRecordId: str | None = None
    status: str = "classified"
    title: str | None = None
    clarificationText: str | None = None
    foundryThreadId: str | None = None


class PeopleDocument(BaseDocument):
    """People container document with person-specific extensions."""

    name: str
    context: str | None = None
    birthday: str | None = None
    contacts: dict | None = None
    lastInteraction: datetime | None = None
    inboxRecordId: str | None = None


class ProjectsDocument(BaseDocument):
    """Projects container document with project-specific extensions."""

    title: str
    status: str = "active"
    nextAction: str | None = None
    inboxRecordId: str | None = None


class IdeasDocument(BaseDocument):
    """Ideas container document with idea-specific extensions."""

    title: str
    tags: list[str] = Field(default_factory=list)
    inboxRecordId: str | None = None


class AdminDocument(BaseDocument):
    """Admin container document with admin-specific extensions."""

    title: str
    nextAction: str | None = None
    dueDate: str | None = None
    inboxRecordId: str | None = None


CONTAINER_MODELS: dict[str, type[BaseDocument]] = {
    "Inbox": InboxDocument,
    "People": PeopleDocument,
    "Projects": ProjectsDocument,
    "Ideas": IdeasDocument,
    "Admin": AdminDocument,
}
