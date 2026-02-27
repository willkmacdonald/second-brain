"""Classification tools for the Classifier agent.

Uses the class-based tool pattern to bind CosmosManager references to @tool
functions. ClassifierTools manages stateful references to CosmosManager and
the file_capture tool that writes classification results to Cosmos DB.
"""

import logging
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
            str,
            Field(description="Brief title (3-6 words) extracted from the text"),
        ] = "Untitled",
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
        """
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

            inbox_container = self._manager.get_container("Inbox")
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

        inbox_container = self._manager.get_container("Inbox")
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
