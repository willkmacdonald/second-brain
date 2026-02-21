"""FastAPI app with AG-UI endpoint, echo agent, and OpenTelemetry tracing."""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env BEFORE any other imports that read env vars (Pitfall 1 from research)
load_dotenv()

from agent_framework.observability import configure_otel_providers  # noqa: E402

# Configure OpenTelemetry immediately after load_dotenv (Pattern 4 from research)
configure_otel_providers()

from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint  # noqa: E402
from azure.identity.aio import DefaultAzureCredential  # noqa: E402
from azure.keyvault.secrets.aio import SecretClient as KeyVaultSecretClient  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from second_brain.agents.echo import create_echo_agent  # noqa: E402
from second_brain.api.health import router as health_router  # noqa: E402
from second_brain.config import get_settings  # noqa: E402
from second_brain.db.cosmos import CosmosManager  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources at startup, clean up at shutdown."""
    settings = get_settings()

    # Fetch API key from Azure Key Vault (per locked CONTEXT.md decision)
    credential = DefaultAzureCredential()
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
    cosmos_manager = CosmosManager(
        endpoint=settings.cosmos_endpoint,
        database_name=settings.database_name,
    )
    try:
        await cosmos_manager.initialize()
        app.state.cosmos_manager = cosmos_manager
        logger.info("Cosmos DB manager initialized")
    except Exception:
        logger.warning(
            "Could not initialize Cosmos DB. "
            "Database operations will not be available until Cosmos DB is configured."
        )
        app.state.cosmos_manager = None

    yield

    # Cleanup Cosmos DB
    if app.state.cosmos_manager is not None:
        await app.state.cosmos_manager.close()


# Create the echo agent at module level (sync credential, per research Pattern 1)
agent = create_echo_agent()

app = FastAPI(title="Second Brain AG-UI Server", lifespan=lifespan)

# Register the AG-UI endpoint (per locked decision: single POST /api/ag-ui)
add_agent_framework_fastapi_endpoint(app, agent, "/api/ag-ui")

# Include health check router
app.include_router(health_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
