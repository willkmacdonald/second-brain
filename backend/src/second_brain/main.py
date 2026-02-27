"""FastAPI app with inbox API, health check, and Cosmos DB persistence."""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env BEFORE any other imports that read env vars
load_dotenv()

from azure.monitor.opentelemetry import configure_azure_monitor  # noqa: E402

# Configure Application Insights immediately after load_dotenv --
# must run before Azure SDK imports to capture all traces
configure_azure_monitor()

from agent_framework.azure import AzureAIAgentClient  # noqa: E402
from azure.identity.aio import (  # noqa: E402
    DefaultAzureCredential as AsyncDefaultAzureCredential,
    get_bearer_token_provider,
)
from azure.keyvault.secrets.aio import SecretClient as KeyVaultSecretClient  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from openai import AsyncAzureOpenAI  # noqa: E402

from second_brain.agents.classifier import ensure_classifier_agent  # noqa: E402
from second_brain.agents.middleware import (  # noqa: E402
    AuditAgentMiddleware,
    ToolTimingMiddleware,
)
from second_brain.api.health import router as health_router  # noqa: E402
from second_brain.api.inbox import router as inbox_router  # noqa: E402
from second_brain.auth import APIKeyMiddleware  # noqa: E402
from second_brain.config import get_settings  # noqa: E402
from second_brain.db.blob_storage import BlobStorageManager  # noqa: E402
from second_brain.db.cosmos import CosmosManager  # noqa: E402
from second_brain.tools.classification import ClassifierTools  # noqa: E402
from second_brain.tools.transcription import TranscriptionTools  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources at startup, clean up at shutdown."""
    settings = get_settings()

    # Async credential -- persists for the entire lifespan (used by Key Vault,
    # Foundry agent client, and OpenAI transcription client)
    credential = AsyncDefaultAzureCredential()
    app.state.credential = credential

    try:
        # Fetch API key from Azure Key Vault
        kv_client = KeyVaultSecretClient(
            vault_url=settings.key_vault_url, credential=credential
        )
        try:
            secret = await kv_client.get_secret(settings.api_key_secret_name)
            app.state.api_key = secret.value
            logger.info("API key fetched from Key Vault")
        except Exception:
            logger.warning(
                "Could not fetch API key from Key Vault. "
                "API key auth will not be available until Key Vault is configured."
            )
            app.state.api_key = None
        finally:
            await kv_client.close()

        # Initialize Cosmos DB client singleton
        cosmos_mgr = CosmosManager(
            endpoint=settings.cosmos_endpoint,
            database_name=settings.database_name,
        )
        try:
            await cosmos_mgr.initialize()
            app.state.cosmos_manager = cosmos_mgr
            logger.info("Cosmos DB manager initialized")
        except Exception:
            logger.warning(
                "Could not initialize Cosmos DB. "
                "Database operations will not be available "
                "until Cosmos DB is configured."
            )
            app.state.cosmos_manager = None
            cosmos_mgr = None

        # --- Foundry Agent Service (fail fast) ---
        try:
            foundry_client = AzureAIAgentClient(
                credential=credential,
                project_endpoint=settings.azure_ai_project_endpoint,
                # model_deployment_name needed for constructor validation
                # when no agent_id is provided (Phase 7 sets agent_id)
                model_deployment_name="gpt-4o",
            )
            # AzureAIAgentClient is a lazy client -- construction alone does
            # NOT make a network call, so wrong credentials would pass
            # silently. Force an auth round-trip to genuinely validate
            # connectivity + RBAC.
            async for _ in foundry_client.agents_client.list_agents(
                limit=1
            ):
                break
            app.state.foundry_client = foundry_client
            app.state.foundry_credential = credential
            logger.info(
                "Foundry client initialized and connectivity validated: %s",
                settings.azure_ai_project_endpoint,
            )
        except Exception:
            logger.error(
                "FATAL: Could not initialize Foundry client",
                exc_info=True,
            )
            raise  # Fail fast -- backend is useless without Foundry

        # --- Classifier Agent Registration (fail fast) ---
        classifier_agent_id = await ensure_classifier_agent(
            foundry_client=foundry_client,
            stored_agent_id=settings.azure_ai_classifier_agent_id,
        )
        app.state.classifier_agent_id = classifier_agent_id

        # --- ClassifierTools (uses Cosmos for filing) ---
        classifier_tools = ClassifierTools(
            cosmos_manager=cosmos_mgr,
            classification_threshold=settings.classification_threshold,
        )
        app.state.classifier_tools = classifier_tools

        # --- OpenAI transcription client (optional) ---
        openai_client: AsyncAzureOpenAI | None = None
        if settings.azure_openai_endpoint:
            # cognitiveservices scope (NOT ai.azure.com) per RESEARCH pitfall #4
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            openai_client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2025-04-01-preview",
            )
            app.state.openai_client = openai_client
        else:
            app.state.openai_client = None
            logger.warning(
                "AZURE_OPENAI_ENDPOINT not set -- transcription unavailable"
            )

        # --- TranscriptionTools + BlobStorage (optional) ---
        blob_manager: BlobStorageManager | None = None
        if openai_client and settings.blob_storage_url:
            blob_manager = BlobStorageManager(
                account_url=settings.blob_storage_url,
            )
            await blob_manager.initialize()
            app.state.blob_manager = blob_manager

            transcription_tools = TranscriptionTools(
                openai_client=openai_client,
                blob_manager=blob_manager,
                credential=credential,
                deployment_name=settings.azure_openai_transcription_deployment,
            )
            app.state.transcription_tools = transcription_tools
        else:
            app.state.blob_manager = None
            app.state.transcription_tools = None

        # --- Classifier AzureAIAgentClient (with middleware) ---
        # Separate client from the probe client -- this one has agent_id set
        # and should_cleanup_agent=False to persist the agent across restarts
        classifier_client = AzureAIAgentClient(
            credential=credential,
            project_endpoint=settings.azure_ai_project_endpoint,
            agent_id=classifier_agent_id,
            should_cleanup_agent=False,
            middleware=[AuditAgentMiddleware(), ToolTimingMiddleware()],
        )
        app.state.classifier_client = classifier_client

        # Build tool list for request-time use (file_capture always,
        # transcribe_audio only if configured)
        agent_tools = [classifier_tools.file_capture]
        if app.state.transcription_tools:
            agent_tools.append(app.state.transcription_tools.transcribe_audio)
        app.state.classifier_agent_tools = agent_tools

        logger.info(
            "Classifier agent ready: id=%s tools=%d middleware=2",
            classifier_agent_id,
            len(agent_tools),
        )

        app.state.settings = settings

        yield

        # Cleanup in reverse order
        if getattr(app.state, "blob_manager", None) is not None:
            await app.state.blob_manager.close()

        if getattr(app.state, "openai_client", None) is not None:
            await app.state.openai_client.close()

        if getattr(app.state, "cosmos_manager", None) is not None:
            await app.state.cosmos_manager.close()

    finally:
        await credential.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Second Brain API", lifespan=lifespan)

# API key auth middleware -- reads app.state.api_key lazily (set by lifespan)
app.add_middleware(APIKeyMiddleware)

# Include health check router and inbox router
app.include_router(health_router)
app.include_router(inbox_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8003)
