"""Classification tools for the Classifier agent.

Uses the class-based tool pattern (same as CosmosCrudTools) to bind
CosmosManager references to @tool functions. ClassificationTools manages
stateful references to CosmosManager and classification threshold.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from agent_framework import tool

from second_brain.db.cosmos import CosmosManager
from second_brain.models.documents import (
    CONTAINER_MODELS,
    ClassificationMeta,
    InboxDocument,
)

logger = logging.getLogger(__name__)

VALID_BUCKETS = {"People", "Projects", "Ideas", "Admin"}


class ClassificationTools:
    """Classification tools bound to a CosmosManager instance.

    Usage:
        tools = ClassificationTools(cosmos_manager, classification_threshold=0.6)
        agent = chat_client.as_agent(
            tools=[tools.classify_and_file, tools.mark_as_junk],
        )
    """

    def __init__(
        self,
        cosmos_manager: CosmosManager | None,
        classification_threshold: float = 0.6,
    ) -> None:
        """Store the CosmosManager reference and threshold."""
        self._manager = cosmos_manager
        self._threshold = classification_threshold

    @tool
    async def classify_and_file(
        self,
        bucket: Annotated[
            str, "Classification bucket: People, Projects, Ideas, or Admin"
        ],
        confidence: Annotated[float, "Confidence score 0.0-1.0 for the primary bucket"],
        people_score: Annotated[float, "Score 0.0-1.0 for People bucket"],
        projects_score: Annotated[float, "Score 0.0-1.0 for Projects bucket"],
        ideas_score: Annotated[float, "Score 0.0-1.0 for Ideas bucket"],
        admin_score: Annotated[float, "Score 0.0-1.0 for Admin bucket"],
        raw_text: Annotated[str, "The original captured text"],
        title: Annotated[str, "Brief title extracted from the text (3-6 words)"],
    ) -> str:
        """Classify captured text and file to Cosmos DB.

        Always call this after analyzing the text. Assigns the text to
        exactly one bucket with a confidence score. Files to both Inbox
        (with full metadata) and the target bucket container.
        """
        # Validate bucket
        if bucket not in VALID_BUCKETS:
            valid = ", ".join(sorted(VALID_BUCKETS))
            return f"Error: Invalid bucket '{bucket}'. Valid buckets: {valid}"

        # Clamp confidence
        confidence = max(0.0, min(1.0, confidence))

        # Build allScores from individual score parameters
        all_scores = {
            "People": people_score,
            "Projects": projects_score,
            "Ideas": ideas_score,
            "Admin": admin_score,
        }

        # Build ClassificationMeta
        classification_meta = ClassificationMeta(
            bucket=bucket,
            confidence=confidence,
            allScores=all_scores,
            classifiedBy="Classifier",
            agentChain=["Orchestrator", "Classifier"],
            classifiedAt=datetime.now(UTC),
        )

        # Generate IDs upfront for bi-directional linking
        inbox_doc_id = str(uuid4())
        bucket_doc_id = str(uuid4())

        # Determine status based on threshold
        status = "classified" if confidence >= self._threshold else "low_confidence"

        # Create Inbox document
        inbox_doc = InboxDocument(
            id=inbox_doc_id,
            rawText=raw_text,
            classificationMeta=classification_meta,
            source="text",
            title=title,
            filedRecordId=bucket_doc_id,
            status=status,
        )

        # Write Inbox document to Cosmos DB
        inbox_container = self._manager.get_container("Inbox")
        await inbox_container.create_item(body=inbox_doc.model_dump(mode="json"))

        # Create bucket document
        model_class = CONTAINER_MODELS[bucket]
        kwargs: dict = {
            "id": bucket_doc_id,
            "rawText": raw_text,
            "classificationMeta": classification_meta,
            "inboxRecordId": inbox_doc_id,
        }
        if bucket == "People":
            kwargs["name"] = title or "Unnamed"
        elif bucket in ("Projects", "Ideas", "Admin"):
            kwargs["title"] = title or "Untitled"

        bucket_doc = model_class(**kwargs)

        # Write bucket document to Cosmos DB
        target_container = self._manager.get_container(bucket)
        await target_container.create_item(body=bucket_doc.model_dump(mode="json"))

        logger.info(
            "Filed to %s (%.2f, status=%s): %s",
            bucket,
            confidence,
            status,
            raw_text[:80],
        )
        return f"Filed \u2192 {bucket} ({confidence:.2f})"

    @tool
    async def request_clarification(
        self,
        raw_text: Annotated[str, "The original captured text"],
        title: Annotated[str, "Brief title extracted from the text (3-6 words)"],
        top_bucket: Annotated[str, "Most likely bucket"],
        top_confidence: Annotated[float, "Confidence for top bucket (must be < 0.6)"],
        second_bucket: Annotated[str, "Second most likely bucket"],
        second_confidence: Annotated[float, "Confidence for second bucket"],
        clarification_text: Annotated[
            str,
            "A specific question explaining your top 2 buckets and why you're unsure. "
            "Example: 'I'm torn between People (0.55) and Projects (0.42) -- this "
            "mentions Mike but also a potential relocation project. "
            "Which fits better?'",
        ],
        people_score: Annotated[float, "Score 0.0-1.0 for People bucket"],
        projects_score: Annotated[float, "Score 0.0-1.0 for Projects bucket"],
        ideas_score: Annotated[float, "Score 0.0-1.0 for Ideas bucket"],
        admin_score: Annotated[float, "Score 0.0-1.0 for Admin bucket"],
    ) -> str:
        """Request human clarification when classification confidence is below 0.6.

        Creates a pending Inbox document (NO bucket container record) and returns
        the clarification text for streaming to the user. The capture will be
        filed to the correct bucket only after the user responds.
        """
        # Validate buckets
        if top_bucket not in VALID_BUCKETS:
            valid = ", ".join(sorted(VALID_BUCKETS))
            return f"Error: Invalid bucket '{top_bucket}'. Valid buckets: {valid}"
        if second_bucket not in VALID_BUCKETS:
            valid = ", ".join(sorted(VALID_BUCKETS))
            return f"Error: Invalid bucket '{second_bucket}'. Valid buckets: {valid}"

        # Build allScores from individual score parameters
        all_scores = {
            "People": people_score,
            "Projects": projects_score,
            "Ideas": ideas_score,
            "Admin": admin_score,
        }

        # Build ClassificationMeta with top bucket
        classification_meta = ClassificationMeta(
            bucket=top_bucket,
            confidence=top_confidence,
            allScores=all_scores,
            classifiedBy="Classifier",
            agentChain=["Orchestrator", "Classifier"],
            classifiedAt=datetime.now(UTC),
        )

        # Generate inbox doc ID
        inbox_doc_id = str(uuid4())

        # Create pending Inbox document -- NO bucket container write
        inbox_doc = InboxDocument(
            id=inbox_doc_id,
            rawText=raw_text,
            classificationMeta=classification_meta,
            source="text",
            title=title,
            filedRecordId=None,
            status="pending",
            clarificationText=clarification_text,
        )

        # Write ONLY to Inbox container
        inbox_container = self._manager.get_container("Inbox")
        await inbox_container.create_item(body=inbox_doc.model_dump(mode="json"))

        logger.info(
            "Clarification requested for '%s' (top=%s %.2f, second=%s %.2f)",
            raw_text[:80],
            top_bucket,
            top_confidence,
            second_bucket,
            second_confidence,
        )
        return f"Clarification \u2192 {inbox_doc_id} | {clarification_text}"

    @tool
    async def mark_as_junk(
        self,
        raw_text: Annotated[str, "The original captured text"],
    ) -> str:
        """Log junk or nonsensical input to Inbox without classification.

        Call this when the input is gibberish, accidental, or nonsensical.
        Creates a minimal Inbox record with status 'unclassified'.
        """
        inbox_doc = InboxDocument(
            rawText=raw_text,
            source="text",
            status="unclassified",
            classificationMeta=None,
        )

        inbox_container = self._manager.get_container("Inbox")
        await inbox_container.create_item(body=inbox_doc.model_dump(mode="json"))

        logger.info("Marked as junk: %s", raw_text[:80])
        return "Capture logged as unclassified"
