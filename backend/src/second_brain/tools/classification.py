"""Classification tools for the Classifier agent.

Uses the class-based tool pattern to bind CosmosManager references to @tool
functions. ClassifierTools manages stateful references to CosmosManager and
the file_capture tool that writes classification results to Cosmos DB.
"""

import contextvars
import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from agent_framework import tool
from pydantic import Field

from second_brain.db.cosmos import CosmosManager
from second_brain.models.documents import (
    CONTAINER_MODELS,
    ClassificationMeta,
    InboxDocument,
)

logger = logging.getLogger(__name__)

VALID_BUCKETS = {"People", "Projects", "Ideas", "Admin"}

# Context var for follow-up mode: when set, file_capture updates the existing
# inbox doc in-place instead of creating a new one.
_follow_up_inbox_item_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_follow_up_inbox_item_id", default=None
)


@contextmanager
def follow_up_context(inbox_item_id: str):
    """Set the follow-up inbox item ID for file_capture to update in-place."""
    token = _follow_up_inbox_item_id.set(inbox_item_id)
    try:
        yield
    finally:
        _follow_up_inbox_item_id.reset(token)


class ClassifierTools:
    """Classification tools bound to a CosmosManager instance.

    The Classifier agent does the reasoning; these tools are filing helpers
    that write the agent's classification decision to Cosmos DB.

    Usage:
        tools = ClassifierTools(cosmos_manager, classification_threshold=0.6)
        agent = client.create_agent(
            tools=[tools.file_capture],
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

    @tool(approval_mode="never_require")
    async def file_capture(
        self,
        text: Annotated[str, Field(description="The original captured text to file")],
        bucket: Annotated[
            str,
            Field(
                description="Classification bucket: People, Projects, Ideas, or Admin"
            ),
        ],
        confidence: Annotated[
            float,
            Field(description="Confidence score 0.0-1.0 for the chosen bucket"),
        ],
        status: Annotated[
            str,
            Field(
                description=(
                    "Status: 'classified' (confidence >= 0.6), "
                    "'pending' (confidence < 0.6), or 'misunderstood'"
                )
            ),
        ],
        title: Annotated[
            str | None,
            Field(description="Brief title (3-6 words) extracted from the text"),
        ] = None,
    ) -> dict:
        """File a classified capture to Cosmos DB.

        The Classifier agent calls this after determining the bucket,
        confidence, and status. For misunderstood items, set
        status='misunderstood' -- only an Inbox record is created (no bucket
        container write).
        """
        # Validate bucket
        if bucket not in VALID_BUCKETS:
            valid = ", ".join(sorted(VALID_BUCKETS))
            return {
                "error": "invalid_bucket",
                "detail": f"Unknown bucket: {bucket}. Valid: {valid}",
            }

        # Clamp confidence
        confidence = max(0.0, min(1.0, confidence))

        # If confidence is 0.0 but a valid bucket was chosen, apply a default
        if confidence == 0.0 and bucket in VALID_BUCKETS:
            confidence = 0.75
            logger.warning(
                "confidence was 0.0 with valid bucket '%s' -- defaulting to 0.75",
                bucket,
            )

        try:
            return await self._write_to_cosmos(text, bucket, confidence, status, title)
        except Exception as exc:
            logger.warning("file_capture Cosmos write failed: %s", exc)
            return {"error": "cosmos_write_failed", "detail": str(exc)}

    async def _write_to_cosmos(
        self,
        text: str,
        bucket: str,
        confidence: float,
        status: str,
        title: str,
    ) -> dict:
        """Write the classification result to Cosmos DB.

        For misunderstood: writes only to Inbox with no classificationMeta.
        For classified/pending: writes to both Inbox and the bucket container.

        When the _follow_up_inbox_item_id context var is set (follow-up mode),
        updates the existing inbox doc in-place instead of creating a new one.
        """
        existing_inbox_id = _follow_up_inbox_item_id.get()
        inbox_container = self._manager.get_container("Inbox")

        # --- Follow-up mode: update existing inbox doc in-place ---
        if existing_inbox_id is not None:
            return await self._write_follow_up_to_cosmos(
                existing_inbox_id,
                inbox_container,
                text,
                bucket,
                confidence,
                status,
                title,
            )

        # --- Normal mode: create new docs ---
        inbox_doc_id = str(uuid4())

        if status == "misunderstood":
            # Misunderstood: Inbox only, no classification metadata, no bucket write
            inbox_doc = InboxDocument(
                id=inbox_doc_id,
                rawText=text,
                source="text",
                title=title,
                filedRecordId=None,
                classificationMeta=None,
                status="misunderstood",
            )

            await inbox_container.create_item(body=inbox_doc.model_dump(mode="json"))

            logger.info(
                "Filed as misunderstood: %s",
                text[:80],
            )
            return {"bucket": bucket, "confidence": confidence, "item_id": inbox_doc_id}

        # Classified or pending: write to both Inbox and bucket container
        bucket_doc_id = str(uuid4())

        classification_meta = ClassificationMeta(
            bucket=bucket,
            confidence=confidence,
            allScores={},
            classifiedBy="Classifier",
            agentChain=["Classifier"],
            classifiedAt=datetime.now(UTC),
        )

        inbox_doc = InboxDocument(
            id=inbox_doc_id,
            rawText=text,
            classificationMeta=classification_meta,
            source="text",
            title=title,
            filedRecordId=bucket_doc_id,
            status=status,
        )

        await inbox_container.create_item(body=inbox_doc.model_dump(mode="json"))

        # Create bucket document
        model_class = CONTAINER_MODELS[bucket]
        kwargs: dict = {
            "id": bucket_doc_id,
            "rawText": text,
            "classificationMeta": classification_meta,
            "inboxRecordId": inbox_doc_id,
        }
        if bucket == "People":
            kwargs["name"] = title or "Unnamed"
        elif bucket in ("Projects", "Ideas", "Admin"):
            kwargs["title"] = title or "Untitled"

        bucket_doc = model_class(**kwargs)

        target_container = self._manager.get_container(bucket)
        await target_container.create_item(body=bucket_doc.model_dump(mode="json"))

        logger.info(
            "Filed to %s (%.2f, status=%s): %s",
            bucket,
            confidence,
            status,
            text[:80],
        )
        return {"bucket": bucket, "confidence": confidence, "item_id": inbox_doc_id}

    async def _write_follow_up_to_cosmos(
        self,
        existing_inbox_id: str,
        inbox_container,
        text: str,
        bucket: str,
        confidence: float,
        status: str,
        title: str,
    ) -> dict:
        """Update the existing inbox doc in-place during follow-up reclassification.

        For misunderstood: updates rawText, title, updatedAt on the existing doc.
        For classified/pending: reads existing doc, preserves original rawText,
        stores follow-up text as clarificationText, updates classification fields,
        creates a new bucket doc pointing to the original inbox ID.
        """
        now = datetime.now(UTC).isoformat()

        if status == "misunderstood":
            # Still misunderstood after follow-up: update existing doc in-place
            existing_doc = await inbox_container.read_item(
                item=existing_inbox_id, partition_key="will"
            )
            existing_doc["title"] = title
            existing_doc["clarificationText"] = text
            existing_doc["updatedAt"] = now
            await inbox_container.upsert_item(body=existing_doc)

            logger.info(
                "Follow-up still misunderstood, updated in-place: %s",
                existing_inbox_id,
            )
            return {
                "bucket": bucket,
                "confidence": confidence,
                "item_id": existing_inbox_id,
            }

        # Classified or pending: update existing inbox doc with classification,
        # preserve original rawText, store follow-up as clarificationText
        existing_doc = await inbox_container.read_item(
            item=existing_inbox_id, partition_key="will"
        )

        bucket_doc_id = str(uuid4())

        classification_meta = ClassificationMeta(
            bucket=bucket,
            confidence=confidence,
            allScores={},
            classifiedBy="Classifier",
            agentChain=["Classifier"],
            classifiedAt=datetime.now(UTC),
        )

        # Update existing inbox doc in-place
        existing_doc["classificationMeta"] = classification_meta.model_dump(mode="json")
        existing_doc["filedRecordId"] = bucket_doc_id
        existing_doc["status"] = status
        existing_doc["clarificationText"] = text
        existing_doc["title"] = title
        existing_doc["updatedAt"] = now
        await inbox_container.upsert_item(body=existing_doc)

        # Create NEW bucket doc pointing to the original inbox ID
        original_raw_text = existing_doc.get("rawText", text)
        model_class = CONTAINER_MODELS[bucket]
        kwargs: dict = {
            "id": bucket_doc_id,
            "rawText": original_raw_text,
            "classificationMeta": classification_meta,
            "inboxRecordId": existing_inbox_id,
        }
        if bucket == "People":
            kwargs["name"] = title or "Unnamed"
        elif bucket in ("Projects", "Ideas", "Admin"):
            kwargs["title"] = title or "Untitled"

        bucket_doc = model_class(**kwargs)

        target_container = self._manager.get_container(bucket)
        await target_container.create_item(body=bucket_doc.model_dump(mode="json"))

        logger.info(
            "Follow-up filed to %s (%.2f, status=%s) in-place on %s: %s",
            bucket,
            confidence,
            status,
            existing_inbox_id,
            text[:80],
        )
        return {
            "bucket": bucket,
            "confidence": confidence,
            "item_id": existing_inbox_id,
        }
