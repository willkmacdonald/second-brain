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
        status = "classified" if confidence >= self._threshold else "pending"

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
        if status == "pending":
            return f"Filed (needs review) \u2192 {bucket} ({confidence:.2f})"
        return f"Filed \u2192 {bucket} ({confidence:.2f})"

    @tool
    async def request_misunderstood(
        self,
        raw_text: Annotated[str, "The original captured text"],
        question_text: Annotated[
            str,
            "A friendly, open-ended question asking the user what they meant. "
            "Example: \"I'm not quite sure what you meant by 'Aardvark'. "
            "Could you tell me more?\"",
        ],
        follow_up_round: Annotated[
            int,
            "Which follow-up round this is (1 = first question, 2 = second attempt)",
        ] = 1,
    ) -> str:
        """Flag input as misunderstood and ask the user a conversational question.

        Creates a misunderstood Inbox document with no bucket filing and no
        classification metadata. Returns the question text for streaming to
        the user on the capture screen.
        """
        # Generate inbox doc ID
        inbox_doc_id = str(uuid4())

        # Create misunderstood Inbox document -- NO bucket container write
        inbox_doc = InboxDocument(
            id=inbox_doc_id,
            rawText=raw_text,
            source="text",
            title=None,
            filedRecordId=None,
            classificationMeta=None,
            status="misunderstood",
            clarificationText=question_text,
        )

        # Write ONLY to Inbox container
        inbox_container = self._manager.get_container("Inbox")
        await inbox_container.create_item(body=inbox_doc.model_dump(mode="json"))

        logger.info(
            "Misunderstood: '%s' (round %d)", raw_text[:80], follow_up_round
        )
        return f"Misunderstood \u2192 {inbox_doc_id} | {question_text}"

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
