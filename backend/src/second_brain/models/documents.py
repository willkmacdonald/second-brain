"""Pydantic document schemas for all 5 Cosmos DB containers.

Shared base schema (id, userId, createdAt, updatedAt, rawText, classificationMeta)
with bucket-specific extensions per the locked CONTEXT.md decision.
"""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

VALID_BUCKETS: frozenset[str] = frozenset({"People", "Projects", "Ideas", "Admin"})


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
    adminProcessingStatus: str | None = None  # None, "pending", "processed", "failed"


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


class ErrandItem(BaseModel):
    """Individual errand item in the Errands Cosmos container.

    Partition key is /destination (not /userId like other containers).
    Items exist until deleted -- no status tracking, no timestamps.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    destination: str  # Partition key: dynamic slug from Destinations container
    name: str  # Full natural language: "2 lbs ground beef", "cat litter"
    needsRouting: bool = (
        False  # True when destination is "unrouted" (no affinity rule matched)
    )
    sourceName: str | None = None  # Recipe name for source attribution
    sourceUrl: str | None = None  # Recipe URL for source attribution


class TaskItem(BaseModel):
    """Individual task item in the Tasks Cosmos container.

    Partition key is /userId (like most containers).
    Tasks are actionable to-dos routed from Admin captures that aren't errands
    (e.g., "book eye appointment", "fill out expenses").
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    name: str  # Natural language: "book eye appointments", "fill out Peloton expenses"
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DestinationDocument(BaseModel):
    """User-defined errand destination (physical or online store/service).

    Stored in the Destinations Cosmos container with /userId partition key.
    The 'slug' field is the machine-readable identifier used as the
    partition key value in the Errands container.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    slug: str  # Lowercase, URL-safe: "agora", "nicks_fishmarket"
    displayName: str  # User-facing: "Agora", "Nick's Fishmarket"
    type: str = "physical"  # "physical" or "online"
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AffinityRuleDocument(BaseModel):
    """User-defined routing rule mapping items/categories to destinations.

    Stored in the AffinityRules Cosmos container with /userId partition key.
    Rules are natural language with structured metadata extracted by the LLM.
    Compound rules (with exceptions) stored as single document with exceptions list.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    naturalLanguage: str  # "meat goes to Agora, except fish goes to Nick's"
    itemPattern: str  # "meat" -- primary match pattern
    destinationSlug: str  # "agora" -- primary destination
    ruleType: str  # "item", "category", "entity"
    exceptions: list[dict] = Field(default_factory=list)
    autoSaved: bool = False  # True if created from HITL answer
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FeedbackDocument(BaseModel):
    """Quality signal document -- self-contained capture snapshot.

    Stores classification correction data.
    Partition key: /userId
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    signalType: str  # "recategorize", "hitl_bucket",
    # "errand_reroute", "thumbs_up", "thumbs_down"
    captureText: str  # Original raw text of the capture (self-contained snapshot)
    originalBucket: str  # What classifier assigned
    correctedBucket: str | None = None  # What user changed it to (None for thumbs_up)
    captureTraceId: str | None = None  # Links back to App Insights telemetry
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GoldenDatasetDocument(BaseModel):
    """Individual test case for classifier evaluation.

    One document per test case. Partition key: /userId
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    inputText: str  # The capture text to classify
    expectedBucket: str  # Known-correct bucket label
    source: str  # "manual", "promoted_feedback", "synthetic"
    tags: list[str] = Field(default_factory=list)  # "edge_case", "voice", "recipe"
    expectedDestination: str | None = (
        None  # For admin eval: known-correct destination slug
    )
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvalResultsDocument(BaseModel):
    """Single eval run with aggregate scores and individual case results.

    Partition key: /userId
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str = "will"
    evalType: str  # "classifier" or "admin_agent"
    runTimestamp: datetime  # When the eval started
    datasetSize: int  # How many test cases were evaluated
    aggregateScores: (
        dict  # e.g., {"accuracy": 0.92, "precision": {...}, "recall": {...}}
    )
    individualResults: list[
        dict
    ]  # e.g., [{"input": "...", "expected": "...", "actual": "...", "correct": True}]
    modelDeployment: str  # "gpt-4o" or similar
    notes: str | None = None  # Optional annotation
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


CONTAINER_MODELS: dict[str, type[BaseDocument]] = {
    "Inbox": InboxDocument,
    "People": PeopleDocument,
    "Projects": ProjectsDocument,
    "Ideas": IdeasDocument,
    "Admin": AdminDocument,
}
