"""FastAPI app with inbox API, health check, and Cosmos DB persistence."""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env BEFORE any other imports that read env vars
load_dotenv()

from azure.identity.aio import (  # noqa: E402
    DefaultAzureCredential as AsyncDefaultAzureCredential,
)
from azure.keyvault.secrets.aio import SecretClient as KeyVaultSecretClient  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from second_brain.api.health import router as health_router  # noqa: E402
from second_brain.api.inbox import router as inbox_router  # noqa: E402
from second_brain.auth import APIKeyMiddleware  # noqa: E402
from second_brain.config import get_settings  # noqa: E402
from second_brain.db.cosmos import CosmosManager  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources at startup, clean up at shutdown."""
    settings = get_settings()

    # Async credential -- persists for the entire lifespan (used by Key Vault
    # now and by Foundry agent client in Plan 02)
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

        app.state.settings = settings

        yield

        # Cleanup Cosmos DB
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
