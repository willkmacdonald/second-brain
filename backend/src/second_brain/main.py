"""FastAPI app with AG-UI endpoint, capture pipeline, and OpenTelemetry tracing."""

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from dotenv import load_dotenv

# Load .env BEFORE any other imports that read env vars (Pitfall 1 from research)
load_dotenv()

from agent_framework.observability import configure_otel_providers  # noqa: E402

# Configure OpenTelemetry immediately after load_dotenv (Pattern 4 from research)
configure_otel_providers()

from ag_ui.core.events import (  # noqa: E402
    BaseEvent,
    CustomEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)
from ag_ui.encoder import EventEncoder  # noqa: E402
from agent_framework import AgentResponseUpdate  # noqa: E402
from agent_framework.azure import AzureOpenAIChatClient  # noqa: E402
from azure.identity import DefaultAzureCredential  # noqa: E402
from azure.identity.aio import (  # noqa: E402, I001
    DefaultAzureCredential as AsyncDefaultAzureCredential,
)
from azure.keyvault.secrets.aio import SecretClient as KeyVaultSecretClient  # noqa: E402
from fastapi import FastAPI, File, Request, UploadFile  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from second_brain.agents.classifier import create_classifier_agent  # noqa: E402
from second_brain.agents.orchestrator import create_orchestrator_agent  # noqa: E402
from second_brain.agents.workflow import (  # noqa: E402
    AGUIWorkflowAdapter,
    StreamItem,
    create_capture_workflow,
)
from second_brain.api.health import router as health_router  # noqa: E402
from second_brain.api.inbox import router as inbox_router  # noqa: E402
from second_brain.auth import APIKeyMiddleware  # noqa: E402
from second_brain.config import get_settings  # noqa: E402
from second_brain.db.blob_storage import BlobStorageManager  # noqa: E402
from second_brain.db.cosmos import CosmosManager  # noqa: E402
from second_brain.tools.transcription import transcribe_audio  # noqa: E402
from second_brain.models.documents import (  # noqa: E402
    CONTAINER_MODELS,
    ClassificationMeta,
)
from second_brain.tools.classification import ClassificationTools  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AG-UI SSE helpers
# ---------------------------------------------------------------------------


def _convert_update_to_events(
    update: AgentResponseUpdate,
    message_id_state: dict[str, str | None],
) -> list[BaseEvent]:
    """Convert an AgentResponseUpdate to AG-UI BaseEvent objects.

    Simplified version of the framework's _emit_content that handles
    text and function_call content types (the two types our workflow produces).
    """
    events: list[BaseEvent] = []
    for content in update.contents or []:
        content_type = getattr(content, "type", None)

        if content_type == "text" and content.text:
            if not message_id_state.get("current"):
                msg_id = str(uuid.uuid4())
                message_id_state["current"] = msg_id
                events.append(
                    TextMessageStartEvent(message_id=msg_id, role="assistant")
                )
            events.append(
                TextMessageContentEvent(
                    message_id=message_id_state["current"],
                    delta=content.text,
                )
            )

        elif content_type == "function_call":
            call_id = getattr(content, "call_id", None) or str(uuid.uuid4())
            name = getattr(content, "name", None) or ""
            args = getattr(content, "arguments", None) or ""

            events.append(
                ToolCallStartEvent(
                    tool_call_id=call_id,
                    tool_call_name=name,
                    parent_message_id=message_id_state.get("current"),
                )
            )
            if args:
                events.append(ToolCallArgsEvent(tool_call_id=call_id, delta=args))
            events.append(ToolCallEndEvent(tool_call_id=call_id))

    return events


async def _stream_sse(
    items: AsyncGenerator[StreamItem, None],
    thread_id: str,
    run_id: str,
) -> AsyncGenerator[str, None]:
    """Convert a mixed stream of AgentResponseUpdate and BaseEvent to SSE text.

    Wraps the stream in RUN_STARTED / RUN_FINISHED lifecycle events and
    ensures a TextMessageEndEvent is emitted if a text message was open.
    """
    encoder = EventEncoder()
    message_id_state: dict[str, str | None] = {"current": None}

    yield encoder.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))

    async for item in items:
        if isinstance(item, BaseEvent):
            yield encoder.encode(item)
        elif isinstance(item, AgentResponseUpdate):
            for event in _convert_update_to_events(item, message_id_state):
                yield encoder.encode(event)

    # Close any open text message
    if message_id_state.get("current"):
        yield encoder.encode(
            TextMessageEndEvent(message_id=message_id_state["current"])
        )

    yield encoder.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))


# ---------------------------------------------------------------------------
# Request model for AG-UI
# ---------------------------------------------------------------------------


class AGUIRunRequest(BaseModel):
    """AG-UI run request with messages, thread_id, and run_id."""

    messages: list[dict] = []
    thread_id: str | None = None  # noqa: N815
    run_id: str | None = None  # noqa: N815
    state: dict | None = None


class RespondRequest(BaseModel):
    """Request body for the HITL respond endpoint.

    The client sends the thread_id (for SSE lifecycle) and the user's
    chosen bucket. The inbox_item_id identifies the low-confidence inbox
    document to re-classify.
    """

    thread_id: str  # noqa: N815
    response: str
    inbox_item_id: str | None = None  # noqa: N815


class FollowUpRequest(BaseModel):
    """Request body for misunderstood follow-up re-classification."""

    inbox_item_id: str  # noqa: N815
    follow_up_text: str  # noqa: N815
    follow_up_round: int = 1  # noqa: N815


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources at startup, clean up at shutdown."""
    settings = get_settings()

    # Fetch API key from Azure Key Vault (per locked CONTEXT.md decision)
    credential = AsyncDefaultAzureCredential()
    try:
        kv_client = KeyVaultSecretClient(
            vault_url=settings.key_vault_url, credential=credential
        )
        secret = await kv_client.get_secret(settings.api_key_secret_name)
        app.state.api_key = secret.value
        logger.info("API key fetched from Key Vault")
        await kv_client.close()
    except Exception:
        logger.warning(
            "Could not fetch API key from Key Vault. "
            "API key auth will not be available until Key Vault is configured."
        )
        app.state.api_key = None
    finally:
        await credential.close()

    # Initialize Cosmos DB client singleton
    cosmos_manager: CosmosManager | None = None
    cosmos_mgr = CosmosManager(
        endpoint=settings.cosmos_endpoint,
        database_name=settings.database_name,
    )
    try:
        await cosmos_mgr.initialize()
        cosmos_manager = cosmos_mgr
        app.state.cosmos_manager = cosmos_manager
        logger.info("Cosmos DB manager initialized")
    except Exception:
        logger.warning(
            "Could not initialize Cosmos DB. "
            "Database operations will not be available until Cosmos DB is configured."
        )
        app.state.cosmos_manager = None

    # Initialize Blob Storage manager (for voice capture)
    blob_manager: BlobStorageManager | None = None
    if settings.blob_storage_url:
        blob_mgr = BlobStorageManager(account_url=settings.blob_storage_url)
        try:
            await blob_mgr.initialize()
            blob_manager = blob_mgr
            app.state.blob_manager = blob_manager
            logger.info("Blob Storage manager initialized")
        except Exception:
            logger.warning(
                "Could not initialize Blob Storage. "
                "Voice capture will not be available."
            )
            app.state.blob_manager = None
    else:
        app.state.blob_manager = None

    # Create shared chat client (sync credential -- AzureOpenAIChatClient expects
    # TokenCredential, not AsyncTokenCredential, per Phase 1 decision)
    try:
        chat_client = AzureOpenAIChatClient(
            credential=DefaultAzureCredential(),
            endpoint=settings.azure_openai_endpoint,
            deployment_name=settings.azure_openai_chat_deployment_name,
        )

        # Create classification tools (None-safe: tools will error at runtime
        # if called without Cosmos, but server still starts)
        classification_tools = ClassificationTools(
            cosmos_manager=cosmos_manager,
            classification_threshold=settings.classification_threshold,
        )

        # Create agents
        orchestrator = create_orchestrator_agent(chat_client)
        classifier = create_classifier_agent(chat_client, classification_tools)

        # Build workflow adapter and store on app.state for respond endpoint
        workflow_agent = create_capture_workflow(
            orchestrator,
            classifier,
            classification_threshold=settings.classification_threshold,
        )
        app.state.workflow_agent = workflow_agent
        app.state.classification_tools = classification_tools
        app.state.settings = settings
        logger.info("Capture pipeline created and stored on app.state")
    except Exception:
        logger.warning(
            "Could not create chat client or capture pipeline. "
            "Azure OpenAI credentials are not available. "
            "AG-UI endpoints will not work until credentials are configured."
        )
        app.state.workflow_agent = None
        app.state.classification_tools = None

    yield

    # Cleanup Blob Storage
    if getattr(app.state, "blob_manager", None) is not None:
        await app.state.blob_manager.close()

    # Cleanup Cosmos DB
    if app.state.cosmos_manager is not None:
        await app.state.cosmos_manager.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Second Brain AG-UI Server", lifespan=lifespan)

# API key auth middleware -- reads app.state.api_key lazily (set by lifespan)
app.add_middleware(APIKeyMiddleware)

# Include health check router and inbox router
app.include_router(health_router)
app.include_router(inbox_router)


# ---------------------------------------------------------------------------
# AG-UI endpoint (custom, replaces add_agent_framework_fastapi_endpoint)
# ---------------------------------------------------------------------------


@app.post("/api/ag-ui", tags=["AG-UI"])
async def ag_ui_endpoint(request: Request, body: AGUIRunRequest) -> StreamingResponse:
    """Handle AG-UI capture requests with step events and HITL support.

    Custom endpoint that replaces add_agent_framework_fastapi_endpoint to
    support the mixed stream of AgentResponseUpdate and BaseEvent objects
    yielded by AGUIWorkflowAdapter._stream_updates.
    """
    workflow_agent: AGUIWorkflowAdapter = request.app.state.workflow_agent
    thread_id = body.thread_id or f"thread-{uuid.uuid4()}"
    run_id = body.run_id or f"run-{uuid.uuid4()}"

    # Convert AG-UI messages to plain strings for the workflow
    from agent_framework import Message as AFMessage  # noqa: E402

    messages: list[AFMessage] = []
    for msg in body.messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        messages.append(AFMessage(role=role, text=content))

    # Create thread and run the workflow
    thread = workflow_agent.get_new_thread()
    stream = workflow_agent.run(
        messages, stream=True, thread=thread, thread_id=thread_id
    )

    async def generate() -> AsyncGenerator[str, None]:
        async for chunk in _stream_sse(stream, thread_id, run_id):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# HITL respond endpoint
# ---------------------------------------------------------------------------


@app.post("/api/ag-ui/respond", tags=["AG-UI"])
async def respond_to_hitl(request: Request, body: RespondRequest) -> StreamingResponse:
    """Re-classify a low-confidence capture with the user's chosen bucket.

    The client sends the bucket name the user selected. This endpoint
    looks up the original inbox item, re-classifies it with the chosen
    bucket at high confidence, and streams back the result as SSE events.
    """
    cosmos_manager: CosmosManager | None = request.app.state.cosmos_manager

    run_id = f"run-{uuid.uuid4()}"
    encoder = EventEncoder()

    async def generate() -> AsyncGenerator[str, None]:
        yield encoder.encode(RunStartedEvent(thread_id=body.thread_id, run_id=run_id))

        msg_id = str(uuid.uuid4())
        bucket = body.response

        # Guard: inbox_item_id is required for filing
        if not body.inbox_item_id:
            yield encoder.encode(
                TextMessageStartEvent(message_id=msg_id, role="assistant")
            )
            yield encoder.encode(
                TextMessageContentEvent(
                    message_id=msg_id,
                    delta="Error: No inbox item ID provided",
                )
            )
            yield encoder.encode(TextMessageEndEvent(message_id=msg_id))
            yield encoder.encode(
                RunFinishedEvent(thread_id=body.thread_id, run_id=run_id)
            )
            return

        try:
            result = f"Filed \u2192 {bucket} (0.85)"

            if body.inbox_item_id and cosmos_manager:
                inbox_container = cosmos_manager.get_container("Inbox")
                try:
                    # Read existing pending inbox item
                    existing = await inbox_container.read_item(
                        item=body.inbox_item_id, partition_key="will"
                    )
                    raw_text = existing.get("rawText", "")
                    title = existing.get("title", "Untitled")

                    if raw_text:
                        # Create bucket document
                        bucket_doc_id = str(uuid.uuid4())

                        classification_meta = ClassificationMeta(
                            bucket=bucket,
                            confidence=0.85,
                            allScores={
                                "People": 0.85 if bucket == "People" else 0.05,
                                "Projects": 0.85 if bucket == "Projects" else 0.05,
                                "Ideas": 0.85 if bucket == "Ideas" else 0.05,
                                "Admin": 0.85 if bucket == "Admin" else 0.05,
                            },
                            classifiedBy="User",
                            agentChain=[
                                "Orchestrator",
                                "Classifier",
                                "User",
                            ],
                            classifiedAt=datetime.now(UTC),
                        )

                        model_class = CONTAINER_MODELS[bucket]
                        kwargs: dict = {
                            "id": bucket_doc_id,
                            "rawText": raw_text,
                            "classificationMeta": classification_meta,
                            "inboxRecordId": body.inbox_item_id,
                        }
                        if bucket == "People":
                            kwargs["name"] = title
                        else:
                            kwargs["title"] = title

                        bucket_doc = model_class(**kwargs)
                        target_container = cosmos_manager.get_container(bucket)
                        await target_container.create_item(
                            body=bucket_doc.model_dump(mode="json")
                        )

                        # Update existing inbox document in place
                        existing["status"] = "classified"
                        existing["filedRecordId"] = bucket_doc_id
                        existing["classificationMeta"] = classification_meta.model_dump(
                            mode="json"
                        )
                        existing["updatedAt"] = datetime.now(UTC).isoformat()
                        await inbox_container.upsert_item(body=existing)

                        result = f"Filed \u2192 {bucket} (0.85)"

                except Exception:
                    logger.exception(
                        "Failed to process inbox item %s",
                        body.inbox_item_id,
                    )
                    result = "Error: Could not file capture. Please try again."

            # Stream the result as text events
            yield encoder.encode(
                TextMessageStartEvent(message_id=msg_id, role="assistant")
            )
            yield encoder.encode(
                TextMessageContentEvent(message_id=msg_id, delta=result)
            )
            yield encoder.encode(TextMessageEndEvent(message_id=msg_id))

        except Exception as exc:
            logger.exception("Respond error: %s", exc)
            yield encoder.encode(
                TextMessageStartEvent(message_id=msg_id, role="assistant")
            )
            yield encoder.encode(
                TextMessageContentEvent(
                    message_id=msg_id,
                    delta="Error: Could not file capture. Please try again.",
                )
            )
            yield encoder.encode(TextMessageEndEvent(message_id=msg_id))

        yield encoder.encode(RunFinishedEvent(thread_id=body.thread_id, run_id=run_id))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Follow-up endpoint for misunderstood re-classification
# ---------------------------------------------------------------------------


@app.post("/api/ag-ui/follow-up", tags=["AG-UI"])
async def follow_up_misunderstood(
    request: Request, body: FollowUpRequest
) -> StreamingResponse:
    """Re-classify a misunderstood capture with additional user context.

    Combines the original captured text with the user's follow-up
    clarification and re-runs the classification workflow. If still
    misunderstood after max rounds (>= 2), marks the inbox item as
    "unresolved" and emits an UNRESOLVED event instead of MISUNDERSTOOD.
    """
    workflow_agent: AGUIWorkflowAdapter = request.app.state.workflow_agent
    cosmos_manager: CosmosManager | None = request.app.state.cosmos_manager
    thread_id = f"thread-{uuid.uuid4()}"
    run_id = f"run-{uuid.uuid4()}"

    # Read the original inbox item to get the raw text
    original_text = ""
    if cosmos_manager:
        try:
            inbox_container = cosmos_manager.get_container("Inbox")
            existing = await inbox_container.read_item(
                item=body.inbox_item_id, partition_key="will"
            )
            original_text = existing.get("rawText", "")
        except Exception:
            logger.warning(
                "Could not read inbox item %s for follow-up", body.inbox_item_id
            )

    # Combine original text with user's clarification
    combined_text = (
        f"{original_text}\n\n---\nUser clarification: {body.follow_up_text}"
        if original_text
        else body.follow_up_text
    )

    # Run the workflow with combined text
    from agent_framework import Message as AFMessage  # noqa: E402

    messages: list[AFMessage] = [AFMessage(role="user", text=combined_text)]
    thread = workflow_agent.get_new_thread()
    stream = workflow_agent.run(
        messages, stream=True, thread=thread, thread_id=thread_id
    )

    async def generate() -> AsyncGenerator[str, None]:
        encoder = EventEncoder()
        yield encoder.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))

        message_id_state: dict[str, str | None] = {"current": None}

        # Track outcomes from custom events
        classified_event_data: dict | None = None  # From CLASSIFIED event
        misunderstood_detected = False
        orphaned_inbox_item_id: str | None = None  # From MISUNDERSTOOD event

        async for item in stream:
            if isinstance(item, BaseEvent):
                if isinstance(item, CustomEvent):
                    if item.name == "CLASSIFIED":
                        # Workflow successfully classified the combined text.
                        # Don't yield to client -- handle reconciliation after stream.
                        classified_event_data = (
                            item.value if isinstance(item.value, dict) else {}
                        )
                        continue

                    if item.name == "MISUNDERSTOOD":
                        if body.follow_up_round >= 2:
                            # Max rounds reached -- mark as unresolved
                            misunderstood_detected = True
                            orphaned_inbox_item_id = (
                                item.value.get("inboxItemId")
                                if isinstance(item.value, dict)
                                else None
                            )
                            continue
                        else:
                            # Round 1: still misunderstood. Intercept to update
                            # original item's clarificationText, then pass event
                            # to client for next follow-up round.
                            orphaned_inbox_item_id = (
                                item.value.get("inboxItemId")
                                if isinstance(item.value, dict)
                                else None
                            )
                            # Update original item's clarificationText
                            if cosmos_manager and orphaned_inbox_item_id:
                                try:
                                    inbox_container = cosmos_manager.get_container(
                                        "Inbox"
                                    )
                                    existing = await inbox_container.read_item(
                                        item=body.inbox_item_id,
                                        partition_key="will",
                                    )
                                    question_text = (
                                        item.value.get("questionText", "")
                                        if isinstance(item.value, dict)
                                        else ""
                                    )
                                    existing["clarificationText"] = question_text
                                    existing["updatedAt"] = datetime.now(
                                        UTC
                                    ).isoformat()
                                    await inbox_container.upsert_item(body=existing)
                                    logger.info(
                                        "Updated original %s clarificationText",
                                        body.inbox_item_id,
                                    )
                                    # Delete the orphaned new inbox doc
                                    if orphaned_inbox_item_id != body.inbox_item_id:
                                        await inbox_container.delete_item(
                                            item=orphaned_inbox_item_id,
                                            partition_key="will",
                                        )
                                        logger.info(
                                            "Deleted orphan misunderstood inbox %s",
                                            orphaned_inbox_item_id,
                                        )
                                except Exception:
                                    logger.warning(
                                        "Could not reconcile misunderstood round 1"
                                        " for %s",
                                        body.inbox_item_id,
                                    )
                            # Emit MISUNDERSTOOD event to client with ORIGINAL item ID
                            yield encoder.encode(
                                CustomEvent(
                                    name="MISUNDERSTOOD",
                                    value={
                                        "threadId": thread_id,
                                        "inboxItemId": body.inbox_item_id,
                                        "questionText": (
                                            item.value.get("questionText", "")
                                            if isinstance(item.value, dict)
                                            else ""
                                        ),
                                    },
                                )
                            )
                            continue

                yield encoder.encode(item)
            elif isinstance(item, AgentResponseUpdate):
                for event in _convert_update_to_events(item, message_id_state):
                    yield encoder.encode(event)

        # Close open text message
        if message_id_state.get("current"):
            yield encoder.encode(
                TextMessageEndEvent(message_id=message_id_state["current"])
            )

        # --- Post-stream orphan reconciliation ---

        if classified_event_data and cosmos_manager:
            # Workflow created a new inbox doc + bucket doc via classify_and_file.
            # Copy classification metadata to original, delete orphaned inbox doc,
            # update bucket doc's inboxRecordId.
            orphan_inbox_id = classified_event_data.get("inboxItemId", "")
            bucket = classified_event_data.get("bucket", "")
            try:
                inbox_container = cosmos_manager.get_container("Inbox")

                # Read the orphaned inbox doc to get its classification metadata
                orphan_doc = await inbox_container.read_item(
                    item=orphan_inbox_id, partition_key="will"
                )
                classification_meta = orphan_doc.get("classificationMeta")
                filed_record_id = orphan_doc.get("filedRecordId")
                title = orphan_doc.get("title")

                # Read the original inbox doc
                existing = await inbox_container.read_item(
                    item=body.inbox_item_id, partition_key="will"
                )

                # Copy classification to original
                existing["classificationMeta"] = classification_meta
                existing["filedRecordId"] = filed_record_id
                existing["title"] = title
                existing["status"] = orphan_doc.get("status", "classified")
                existing["updatedAt"] = datetime.now(UTC).isoformat()
                await inbox_container.upsert_item(body=existing)
                logger.info(
                    "Copied classification to original %s from orphan %s",
                    body.inbox_item_id,
                    orphan_inbox_id,
                )

                # Delete the orphaned inbox doc
                if orphan_inbox_id and orphan_inbox_id != body.inbox_item_id:
                    await inbox_container.delete_item(
                        item=orphan_inbox_id, partition_key="will"
                    )
                    logger.info("Deleted orphan inbox doc %s", orphan_inbox_id)

                # Update the bucket doc's inboxRecordId to point to original
                if filed_record_id and bucket:
                    try:
                        bucket_container = cosmos_manager.get_container(bucket)
                        bucket_doc = await bucket_container.read_item(
                            item=filed_record_id, partition_key="will"
                        )
                        bucket_doc["inboxRecordId"] = body.inbox_item_id
                        await bucket_container.upsert_item(body=bucket_doc)
                        logger.info(
                            "Updated bucket doc %s inboxRecordId to %s",
                            filed_record_id,
                            body.inbox_item_id,
                        )
                    except Exception:
                        logger.warning(
                            "Could not update bucket doc %s inboxRecordId",
                            filed_record_id,
                        )

            except Exception:
                logger.exception(
                    "Failed post-stream reconciliation for inbox %s",
                    body.inbox_item_id,
                )

        elif misunderstood_detected:
            # Max rounds reached -- update original to unresolved + clean up orphan
            if cosmos_manager:
                try:
                    inbox_container = cosmos_manager.get_container("Inbox")
                    existing = await inbox_container.read_item(
                        item=body.inbox_item_id, partition_key="will"
                    )
                    existing["status"] = "unresolved"
                    existing["updatedAt"] = datetime.now(UTC).isoformat()
                    await inbox_container.upsert_item(body=existing)
                except Exception:
                    logger.warning(
                        "Could not update inbox item %s to unresolved",
                        body.inbox_item_id,
                    )

                if (
                    orphaned_inbox_item_id
                    and orphaned_inbox_item_id != body.inbox_item_id
                ):
                    try:
                        await inbox_container.delete_item(
                            item=orphaned_inbox_item_id,
                            partition_key="will",
                        )
                        logger.info(
                            "Deleted orphaned misunderstood inbox item %s",
                            orphaned_inbox_item_id,
                        )
                    except Exception:
                        logger.warning(
                            "Could not delete orphaned inbox item %s",
                            orphaned_inbox_item_id,
                        )

            yield encoder.encode(
                CustomEvent(
                    name="UNRESOLVED",
                    value={"inboxItemId": body.inbox_item_id},
                )
            )

        yield encoder.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Voice capture endpoint
# ---------------------------------------------------------------------------

_MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25 MB (Whisper limit)
_MIN_AUDIO_SIZE = 1024  # 1 KB — anything smaller is likely an accidental tap


@app.post("/api/voice-capture", tags=["Capture"])
async def voice_capture(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
) -> StreamingResponse:
    """Accept multipart audio upload, transcribe via Whisper, classify via pipeline.

    SSE stream includes a synthetic Perception step (upload + transcribe + delete)
    followed by the existing Orchestrator -> Classifier workflow steps.
    """
    thread_id = f"thread-{uuid.uuid4()}"
    run_id = f"run-{uuid.uuid4()}"

    audio_bytes = await file.read()

    # Validate audio size
    if len(audio_bytes) < _MIN_AUDIO_SIZE:
        encoder = EventEncoder()

        async def _error_short() -> AsyncGenerator[str, None]:
            yield encoder.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))
            msg_id = str(uuid.uuid4())
            yield encoder.encode(
                TextMessageStartEvent(message_id=msg_id, role="assistant")
            )
            yield encoder.encode(
                TextMessageContentEvent(message_id=msg_id, delta="Recording too short")
            )
            yield encoder.encode(TextMessageEndEvent(message_id=msg_id))
            yield encoder.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        return StreamingResponse(
            _error_short(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    if len(audio_bytes) > _MAX_AUDIO_SIZE:
        encoder = EventEncoder()

        async def _error_large() -> AsyncGenerator[str, None]:
            yield encoder.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))
            msg_id = str(uuid.uuid4())
            yield encoder.encode(
                TextMessageStartEvent(message_id=msg_id, role="assistant")
            )
            yield encoder.encode(
                TextMessageContentEvent(
                    message_id=msg_id,
                    delta="Recording too large (max 25 MB)",
                )
            )
            yield encoder.encode(TextMessageEndEvent(message_id=msg_id))
            yield encoder.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        return StreamingResponse(
            _error_large(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    blob_manager: BlobStorageManager | None = getattr(
        request.app.state, "blob_manager", None
    )
    workflow_agent: AGUIWorkflowAdapter | None = getattr(
        request.app.state, "workflow_agent", None
    )
    settings = getattr(request.app.state, "settings", None)
    filename = file.filename or "voice-capture.m4a"

    async def generate() -> AsyncGenerator[str, None]:
        encoder = EventEncoder()
        yield encoder.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))

        # Guard: blob manager required
        if blob_manager is None:
            msg_id = str(uuid.uuid4())
            yield encoder.encode(
                TextMessageStartEvent(message_id=msg_id, role="assistant")
            )
            yield encoder.encode(
                TextMessageContentEvent(
                    message_id=msg_id,
                    delta="Voice capture not available (Blob Storage not configured)",
                )
            )
            yield encoder.encode(TextMessageEndEvent(message_id=msg_id))
            yield encoder.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))
            return

        # Guard: workflow agent required
        if workflow_agent is None or settings is None:
            msg_id = str(uuid.uuid4())
            yield encoder.encode(
                TextMessageStartEvent(message_id=msg_id, role="assistant")
            )
            yield encoder.encode(
                TextMessageContentEvent(
                    message_id=msg_id,
                    delta="Voice capture not available (pipeline not configured)",
                )
            )
            yield encoder.encode(TextMessageEndEvent(message_id=msg_id))
            yield encoder.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))
            return

        # --- Perception step (synthetic) ---
        perception_started = False
        blob_url: str | None = None
        transcription: str | None = None
        try:
            yield encoder.encode(StepStartedEvent(step_name="Perception"))
            perception_started = True

            # Upload audio to Blob Storage
            blob_url = await blob_manager.upload_audio(audio_bytes, filename)

            # Transcribe via Whisper (sync function -> run in thread)
            transcription = await asyncio.to_thread(
                transcribe_audio,
                audio_bytes,
                filename,
                settings.azure_openai_whisper_deployment_name,
                settings.azure_openai_endpoint,
            )

            # Delete blob after transcription (per CONTEXT.md)
            await blob_manager.delete_audio(blob_url)
            blob_url = None  # Mark as deleted

            yield encoder.encode(StepFinishedEvent(step_name="Perception"))
            perception_started = False

        except Exception:
            logger.exception("Perception step failed")
            # Clean up blob if uploaded but transcription failed
            if blob_url is not None:
                await blob_manager.delete_audio(blob_url)
            if perception_started:
                yield encoder.encode(StepFinishedEvent(step_name="Perception"))

            msg_id = str(uuid.uuid4())
            yield encoder.encode(
                TextMessageStartEvent(message_id=msg_id, role="assistant")
            )
            yield encoder.encode(
                TextMessageContentEvent(
                    message_id=msg_id,
                    delta="Transcription failed. Please try again.",
                )
            )
            yield encoder.encode(TextMessageEndEvent(message_id=msg_id))
            yield encoder.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))
            return

        # Guard: empty transcription
        if not transcription or not transcription.strip():
            msg_id = str(uuid.uuid4())
            yield encoder.encode(
                TextMessageStartEvent(message_id=msg_id, role="assistant")
            )
            yield encoder.encode(
                TextMessageContentEvent(
                    message_id=msg_id,
                    delta="Could not transcribe audio. Please try again.",
                )
            )
            yield encoder.encode(TextMessageEndEvent(message_id=msg_id))
            yield encoder.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))
            return

        # --- Classification pipeline ---
        from agent_framework import Message as AFMessage  # noqa: E402

        messages: list[AFMessage] = [AFMessage(role="user", text=transcription)]
        thread = workflow_agent.get_new_thread()
        stream = workflow_agent.run(
            messages, stream=True, thread=thread, thread_id=thread_id
        )

        message_id_state: dict[str, str | None] = {"current": None}
        async for item in stream:
            if isinstance(item, BaseEvent):
                yield encoder.encode(item)
            elif isinstance(item, AgentResponseUpdate):
                for event in _convert_update_to_events(item, message_id_state):
                    yield encoder.encode(event)

        # Close any open text message
        if message_id_state.get("current"):
            yield encoder.encode(
                TextMessageEndEvent(message_id=message_id_state["current"])
            )

        yield encoder.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8003)
