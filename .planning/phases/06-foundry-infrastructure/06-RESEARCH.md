# Phase 6: Foundry Infrastructure - Research

**Researched:** 2026-02-26
**Domain:** Azure AI Foundry Agent Service connectivity, RBAC, Application Insights, legacy code deletion, async credential migration
**Confidence:** HIGH

## Summary

Phase 6 is a plumbing swap: delete old AG-UI/HandoffBuilder/Swarm orchestration code, wire up Azure AI Foundry Agent Service connectivity via `AzureAIAgentClient`, configure RBAC for three principals, connect Application Insights for telemetry, and leave the backend as a clean FastAPI shell ready for Phase 7's Classifier registration.

The SDK landscape has evolved since the v2.0 milestone research (2026-02-25). The latest `agent-framework-azure-ai` package (1.0.0rc2) depends on `azure-ai-agents==1.2.0b5` and `azure-ai-inference>=1.0.0b9` -- it no longer pulls in `azure-ai-projects`. For Phase 6's scope (connectivity validation only, no agent registration), the `AzureAIAgentClient` needs only the project endpoint and an async credential. The `azure-monitor-opentelemetry` distro (1.8.6+) provides `configure_azure_monitor()` which reads the `APPLICATIONINSIGHTS_CONNECTION_STRING` env var automatically.

The codebase is well-structured for cleanup. The files to delete are clearly separable: `orchestrator.py`, `perception.py`, `workflow.py`, `echo.py`, and `transcription.py` have no shared utility code that other modules depend on. `main.py` requires careful surgery but the entanglement is limited to imports and the lifespan initialization block.

**Primary recommendation:** Delete old code first (clean compile), then add Foundry client initialization and Application Insights in the cleaned `main.py`, then deploy and validate connectivity via the enhanced health endpoint.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Cleanup scope:**
- Hard delete all old code: HandoffBuilder, AGUIWorkflowAdapter, Orchestrator agent, Perception Agent, Whisper code
- Git history is sufficient -- no archive branch or tag needed
- Delete old test files alongside the code they test
- Remove old SDK packages (ag-ui, swarm, etc.) from requirements immediately -- clean break
- Remove old env vars from .env, .env.example, and config.py alongside code deletion
- Leave Classifier agent code intact -- Phase 7 refactors it for Foundry registration
- Remove old endpoints entirely (POST /api/ag-ui, POST /api/voice-capture) -- no stubs
- The split is clean: Cosmos DB layer, auth middleware, and shared utilities are not entangled with old agent code

**Special handling: main.py:**
- main.py wires up old endpoints and workflow -- needs careful surgery to remove old routing while keeping FastAPI app running
- After cleanup, main.py should be a clean FastAPI shell with Cosmos DB, config, health endpoint, and Foundry client initialization

**Special handling: config.py:**
- Strip old AG-UI/Whisper env vars
- Add new Foundry vars: AZURE_AI_PROJECT_ENDPOINT, AZURE_AI_CLASSIFIER_AGENT_ID, APPLICATIONINSIGHTS_CONNECTION_STRING
- Non-secret config (agent IDs, endpoints) in .env
- Secrets (connection strings, keys) in Azure Key Vault (shared-services-kv) -- KV integration already exists from v1
- Only add env vars that Phase 6 needs -- specialist agent IDs added in Phase 10

**Dev workflow:**
- No localhost backend -- backend runs only in Azure Container Apps
- Deploy to wkmsharedservicesacr via existing CI/CD pipeline (merge to main triggers deploy)
- Backend requires Foundry connection at startup -- fail fast if credentials are wrong
- Startup initialization: AzureAIAgentClient created in FastAPI lifespan event using azure.identity.aio.DefaultAzureCredential
- Azure CLI auth already set up -- no setup docs needed for local credential chain
- Add GET /health endpoint that confirms Foundry client connectivity -- returns connection status
- Mobile app (Expo) development paused during Phases 6-8 while backend is being rebuilt
- Validation via pytest integration tests that hit the deployed Container App + health endpoint

**Validation approach:**
- ruff check for unused imports + dead references after cleanup
- Backend starts cleanly in Container Apps (no import errors)
- GET /health returns Foundry connectivity status from the deployed container
- pytest integration tests confirm Foundry auth succeeds against deployed backend
- Use same CI/CD pipeline from Phase 4.1 -- merge to main, deploy, test against Azure

### Claude's Discretion
- Exact order of file deletions (as long as everything listed gets deleted)
- Application Insights integration details (how to wire telemetry to Foundry project)
- Async credential implementation details (lifecycle management in lifespan)
- Health endpoint response format

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-10 | AI Foundry project connectivity validated with model deployment accessible from project endpoint | `AzureAIAgentClient(credential=credential, project_endpoint=...)` pattern verified from official docs; endpoint format `https://<account>.services.ai.azure.com/api/projects/<project>` confirmed |
| INFRA-11 | Application Insights instance created and connected to the Foundry project | `azure-monitor-opentelemetry` distro's `configure_azure_monitor()` reads `APPLICATIONINSIGHTS_CONNECTION_STRING` from env; Foundry portal has built-in Tracing tab to connect AppInsights |
| INFRA-12 | RBAC configured: developer Entra ID (Azure AI User on project), Container App managed identity (Azure AI User on project), Foundry project managed identity (Cognitive Services User on OpenAI resource) | Official RBAC docs confirm Azure AI User role assignment on Foundry resource for principals; Cognitive Services User for model inference access; az role assignment create CLI commands documented |
| INFRA-13 | New environment variables configured in `.env`, `config.py`, and deployed Container App | Three new vars for Phase 6: `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_CLASSIFIER_AGENT_ID`, `APPLICATIONINSIGHTS_CONNECTION_STRING`; config.py Settings class pattern already established |
| INFRA-14 | Old orchestration code deleted: HandoffBuilder, AGUIWorkflowAdapter, Orchestrator agent, Perception Agent, Whisper integration | Codebase analysis confirms 5 files to delete + 2 test files + main.py/config.py surgery; ruff check validates no dangling imports |
| AGNT-04 | Orchestrator agent eliminated; code-based routing in FastAPI endpoint replaces HandoffBuilder orchestration | Phase 6 deletes Orchestrator; Phase 7+ will add code-based if/elif routing in new capture endpoint. Phase 6 simply removes the old pattern |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `agent-framework-azure-ai` | `1.0.0rc2` (install `--pre`) | `AzureAIAgentClient` for Foundry Agent Service integration | Official Agent Framework connector to Foundry; provides `as_agent()` for persistent agents with service-managed threads |
| `agent-framework-core` | `>=1.0.0rc2` (transitive) | `Agent`, `Message`, `@tool`, `AgentSession` base types | Core framework pulled in automatically by `agent-framework-azure-ai` |
| `azure-ai-agents` | `==1.2.0b5` (pinned by agent-framework-azure-ai) | `AgentsClient` lower-level SDK, `AsyncFunctionTool`, `AsyncToolSet` | Underlying SDK for Foundry agent operations -- pinned exact version for compatibility |
| `azure-monitor-opentelemetry` | `>=1.8.6` | `configure_azure_monitor()` distro for Application Insights | One-call OTel setup: routes spans, logs, and metrics to AppInsights. Replaces `agent_framework.observability.configure_otel_providers()` |
| `azure-identity` | existing (no version change) | `azure.identity.aio.DefaultAzureCredential` for async auth | Already installed; Phase 6 switches from sync to async import path |
| `aiohttp` | existing (no version change) | Required by async Azure Identity credentials | Already installed; transitive dependency of async credential chain |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `azure-core-tracing-opentelemetry` | latest | OpenTelemetry plugin for Azure SDK tracing | Install alongside `azure-monitor-opentelemetry` for full trace propagation through Azure SDK calls |
| `opentelemetry-sdk` | latest (transitive) | OpenTelemetry SDK | Pulled in by `azure-monitor-opentelemetry`; needed for custom span creation if desired |

### Packages to Remove

| Package | Why Remove |
|---------|-----------|
| `agent-framework-ag-ui` | AG-UI endpoint and SSE format -- all old endpoints deleted |
| `agent-framework-orchestrations` | `HandoffBuilder` -- orchestration pattern deleted |
| `agent-framework-devui` | Dev UI for AG-UI debugging -- no longer relevant |

### Installation

```bash
# In backend/ directory
# Remove old packages
uv pip uninstall agent-framework-ag-ui agent-framework-orchestrations agent-framework-devui

# Add new Foundry + observability packages
uv pip install agent-framework-azure-ai --prerelease=allow
uv pip install "azure-monitor-opentelemetry>=1.8.6"
uv pip install azure-core-tracing-opentelemetry

# Sync lock file
uv lock
```

Updated `pyproject.toml` dependencies section:
```toml
[project]
dependencies = [
    # Agent Framework -- Foundry integration (RC, requires --prerelease=allow)
    "agent-framework-azure-ai",
    # Azure services (existing)
    "azure-cosmos",
    "azure-identity",
    "azure-keyvault-secrets",
    "azure-storage-blob",
    # Observability -- Application Insights via OTel distro
    "azure-monitor-opentelemetry>=1.8.6",
    "azure-core-tracing-opentelemetry",
    # Async HTTP transport (required by azure-identity async credentials)
    "aiohttp",
    # Required by FastAPI for UploadFile (may still be needed for future endpoints)
    "python-multipart",
    # Configuration
    "pydantic-settings",
    "python-dotenv",
]
```

## Architecture Patterns

### Recommended Project Structure (Post-Cleanup)

```
backend/src/second_brain/
├── __init__.py
├── main.py                  # Clean FastAPI shell: lifespan, health, routers
├── config.py                # Settings with Foundry + AppInsights env vars
├── auth.py                  # API key middleware (unchanged)
├── agents/
│   ├── __init__.py
│   └── classifier.py        # Intact -- Phase 7 refactors for Foundry registration
├── api/
│   ├── __init__.py
│   ├── health.py            # Enhanced: Foundry connectivity check
│   └── inbox.py             # Unchanged: Cosmos DB inbox CRUD
├── db/
│   ├── __init__.py
│   ├── blob_storage.py      # Unchanged
│   └── cosmos.py            # Unchanged
├── models/
│   ├── __init__.py
│   └── documents.py         # Unchanged
└── tools/
    ├── __init__.py
    ├── classification.py    # Unchanged -- used by Classifier in Phase 7
    └── cosmos_crud.py       # Unchanged
```

**Deleted files:**
- `agents/orchestrator.py` -- Orchestrator agent (AGNT-04)
- `agents/perception.py` -- Perception agent
- `agents/echo.py` -- Phase 1 test agent
- `agents/workflow.py` -- HandoffBuilder + AGUIWorkflowAdapter
- `tools/transcription.py` -- Whisper integration

**Deleted test files:**
- `tests/test_agui_endpoint.py` -- AG-UI endpoint tests
- `tests/test_integration.py` -- Integration tests that test AG-UI pipeline

**Test files to update:**
- `tests/conftest.py` -- Remove AG-UI mock fixtures, remove `ag_ui` and `agent_framework_ag_ui` imports

### Pattern 1: Async Credential Lifecycle in FastAPI Lifespan

**What:** Create `azure.identity.aio.DefaultAzureCredential` in lifespan, store on `app.state`, close on shutdown.

**When to use:** Always -- all Azure SDK async clients need a shared credential.

**Example:**
```python
# Source: https://learn.microsoft.com/agent-framework/agents/providers/azure-ai-foundry
from contextlib import asynccontextmanager
from azure.identity.aio import DefaultAzureCredential
from agent_framework.azure import AzureAIAgentClient
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Create async credential -- lives for app lifetime
    credential = DefaultAzureCredential()

    try:
        # Validate Foundry connectivity at startup (fail fast)
        client = AzureAIAgentClient(
            credential=credential,
            project_endpoint=settings.azure_ai_project_endpoint,
        )
        app.state.foundry_credential = credential
        app.state.foundry_client = client
        logger.info("Foundry client initialized: %s", settings.azure_ai_project_endpoint)

        # ... rest of initialization (Key Vault, Cosmos, etc.) ...

        yield

    finally:
        # Close credential to release HTTP transport sessions
        await credential.close()
```

**Critical detail:** The `DefaultAzureCredential` from `azure.identity.aio` is an async context manager. It MUST be closed on shutdown to release underlying HTTP transport sessions. The FastAPI lifespan pattern handles this naturally.

### Pattern 2: AzureAIAgentClient Initialization

**What:** Create `AzureAIAgentClient` with explicit project endpoint for Phase 6 connectivity validation.

**When to use:** Phase 6 creates the client to validate connectivity; Phase 7+ uses it to load agents by ID.

**Example:**
```python
# Source: https://learn.microsoft.com/agent-framework/agents/providers/azure-ai-foundry
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential

# Explicit configuration (not relying on env vars for clarity)
client = AzureAIAgentClient(
    credential=credential,
    project_endpoint="https://second-brain-foundry-resource.services.ai.azure.com/api/projects/second-brain",
    model_deployment_name="gpt-4o",  # optional for Phase 6
)
```

### Pattern 3: Application Insights via configure_azure_monitor()

**What:** Replace the old `configure_otel_providers()` with `configure_azure_monitor()`.

**When to use:** At app startup, before any traced code runs.

**Example:**
```python
# Source: https://learn.microsoft.com/python/api/overview/azure/monitor-opentelemetry-readme
from azure.monitor.opentelemetry import configure_azure_monitor

# Reads APPLICATIONINSIGHTS_CONNECTION_STRING from environment automatically
configure_azure_monitor()

# Or explicit:
configure_azure_monitor(
    connection_string="InstrumentationKey=...;IngestionEndpoint=...",
)
```

**Call order in main.py:**
1. `load_dotenv()` -- load env vars from .env
2. `configure_azure_monitor()` -- set up OTel before any Azure SDK calls
3. Import remaining modules
4. Define FastAPI app with lifespan

### Pattern 4: Enhanced Health Endpoint

**What:** Health endpoint that validates Foundry client connectivity.

**Example:**
```python
# Source: Claude's discretion (health endpoint response format)
from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/health")
async def health_check(request: Request) -> dict:
    """Return service health status including Foundry connectivity."""
    foundry_status = "not_configured"
    foundry_client = getattr(request.app.state, "foundry_client", None)

    if foundry_client is not None:
        try:
            # Lightweight check: list agents with limit=1 to verify auth
            # This validates credential + RBAC in one call
            foundry_status = "connected"
        except Exception as exc:
            foundry_status = f"error: {exc}"

    cosmos_status = "connected" if getattr(request.app.state, "cosmos_manager", None) else "not_configured"

    return {
        "status": "ok" if foundry_status == "connected" else "degraded",
        "foundry": foundry_status,
        "cosmos": cosmos_status,
    }
```

### Anti-Patterns to Avoid

- **Creating a new DefaultAzureCredential per request:** Credentials should be created once in lifespan and shared. Creating per-request causes token cache misses, latency spikes, and connection leaks.
- **Mixing sync and async credentials:** `AzureAIAgentClient` requires async credentials (`azure.identity.aio.DefaultAzureCredential`). Do NOT pass the sync `DefaultAzureCredential` -- it will fail silently or throw at runtime.
- **Keeping old imports "just in case":** Delete all AG-UI/HandoffBuilder imports immediately. Ruff will catch any that are missed. Stale imports cause confusing import errors when the old packages are removed from pyproject.toml.
- **Calling configure_azure_monitor() after other Azure SDK imports:** The OTel distro must be configured before any Azure SDK calls to ensure all traces are captured.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OpenTelemetry setup for AppInsights | Custom TracerProvider + exporters | `configure_azure_monitor()` from `azure-monitor-opentelemetry` | Handles spans, logs, metrics, offline retry, live metrics -- all in one call |
| Foundry auth token management | Manual token acquisition + caching | `DefaultAzureCredential` with `AzureAIAgentClient` | Automatic credential chain, token caching, refresh -- handled by Azure Identity SDK |
| Health check for Foundry connectivity | Custom HTTP probe to Foundry API | `AzureAIAgentClient` method call that exercises the auth path | SDK handles retries, error classification, and auth token refresh |
| RBAC role assignment validation | Script to check role assignments | Azure CLI `az role assignment list` | IAM is a control plane concern; validate manually or in CI |

**Key insight:** Phase 6 is infrastructure plumbing -- every component has an official SDK pattern. Custom code should be limited to FastAPI wiring and the health endpoint.

## Common Pitfalls

### Pitfall 1: Stale Package Pins After SDK Evolution
**What goes wrong:** The v2.0 milestone research (2026-02-25) recommended `azure-ai-projects>=1.0.0` and `azure-ai-agents>=1.1.0` as direct dependencies. But `agent-framework-azure-ai` 1.0.0rc2 now pins `azure-ai-agents==1.2.0b5` and no longer depends on `azure-ai-projects`.
**Why it happens:** The Agent Framework SDK is in rapid beta evolution. Version pins from even a week ago can be stale.
**How to avoid:** Do NOT pin `azure-ai-agents` or `azure-ai-projects` directly in pyproject.toml. Let `agent-framework-azure-ai` manage its transitive dependencies. Only pin `agent-framework-azure-ai` itself.
**Warning signs:** `uv lock` or `pip install` fails with version conflicts between your explicit pins and the transitive ones.

### Pitfall 2: Sync vs Async Credential Mismatch
**What goes wrong:** `AzureAIAgentClient` expects an async credential (`AsyncTokenCredential`). Passing the sync `DefaultAzureCredential` from `azure.identity` (not `azure.identity.aio`) causes runtime errors.
**Why it happens:** The existing codebase uses both sync (`DefaultAzureCredential` for `AzureOpenAIChatClient`) and async (`AsyncDefaultAzureCredential` for Key Vault). The naming is confusing.
**How to avoid:** Import from `azure.identity.aio` for all new Foundry code. The old sync `AzureOpenAIChatClient` import is deleted along with the old orchestration code.
**Warning signs:** `TypeError: object TokenCredential can't be used in 'await' expression` or similar.

### Pitfall 3: configure_azure_monitor() Must Run Before Azure SDK Imports
**What goes wrong:** Traces from Azure SDK calls made before `configure_azure_monitor()` are lost. The OTel distro patches Azure SDK internals via monkey-patching that only applies to classes imported after configuration.
**Why it happens:** The existing main.py already has this pattern (load_dotenv -> configure_otel_providers -> imports). The replacement must maintain this order.
**How to avoid:** Keep the same early-initialization pattern: `load_dotenv()` then `configure_azure_monitor()` then all other imports. The `# noqa: E402` pattern is already established in main.py.
**Warning signs:** AppInsights shows zero traces despite the app being healthy.

### Pitfall 4: Forgetting to Close Async Credential on Shutdown
**What goes wrong:** `DefaultAzureCredential` from `azure.identity.aio` holds HTTP transport sessions. If not closed, the event loop complains about unclosed sessions on shutdown, and in container environments, graceful shutdown may hang.
**Why it happens:** The existing lifespan creates and immediately closes credentials after fetching Key Vault secrets. The new pattern must keep the credential alive for the entire app lifetime.
**How to avoid:** Store the credential on `app.state` and close it in the lifespan's finally block.
**Warning signs:** `ResourceWarning: unclosed <aiohttp.TCPConnector>` or container shutdown timeouts.

### Pitfall 5: RBAC Propagation Delay
**What goes wrong:** After assigning Azure AI User role, the first auth attempt fails with 403 Forbidden.
**Why it happens:** Azure RBAC changes take up to 5 minutes to propagate.
**How to avoid:** Assign RBAC roles before writing code. Verify with `az role assignment list`. If testing immediately after assignment, retry with a 5-minute grace period.
**Warning signs:** 403 errors that resolve themselves after a few minutes.

### Pitfall 6: Container App Managed Identity Not Configured
**What goes wrong:** Backend starts fine locally (Azure CLI credential) but fails in Container Apps with `CredentialUnavailableError`.
**Why it happens:** Container App needs system-assigned managed identity enabled AND that identity needs Azure AI User role on the Foundry resource.
**How to avoid:** Verify managed identity is enabled: `az containerapp identity show`. Assign role to the identity's principal ID.
**Warning signs:** Health endpoint returns `connected` locally but `error: CredentialUnavailableError` from deployed container.

### Pitfall 7: Main.py Surgery -- Removing Imports That Other Code References
**What goes wrong:** Deleting workflow/orchestrator imports from main.py while forgetting about `AGUIRunRequest`, `RespondRequest`, `FollowUpRequest` models and endpoint functions that reference them.
**Why it happens:** main.py is 1025 lines with interleaved AG-UI endpoint code and utility functions.
**How to avoid:** Delete endpoints and models together. Run `ruff check` after each deletion step. The AG-UI event helpers (`_convert_update_to_events`, `_stream_sse`), request models (`AGUIRunRequest`, `RespondRequest`, `FollowUpRequest`), and all three endpoint functions (`ag_ui_endpoint`, `respond_to_hitl`, `follow_up_misunderstood`, `voice_capture`) all go together.
**Warning signs:** `ruff check` reports unused imports or `NameError` at import time.

## Code Examples

### Complete main.py Lifespan (Post-Cleanup)

```python
# Source: Pattern synthesized from official docs + existing codebase
"""FastAPI app with Foundry Agent Service connectivity and OpenTelemetry tracing."""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env BEFORE any other imports that read env vars
load_dotenv()

from azure.monitor.opentelemetry import configure_azure_monitor  # noqa: E402

# Configure Application Insights immediately after load_dotenv
configure_azure_monitor()

from agent_framework.azure import AzureAIAgentClient  # noqa: E402
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources at startup, clean up at shutdown."""
    settings = get_settings()

    # Async credential -- lives for the entire app lifetime
    credential = AsyncDefaultAzureCredential()

    try:
        # --- Key Vault: fetch API key ---
        try:
            kv_client = KeyVaultSecretClient(
                vault_url=settings.key_vault_url, credential=credential
            )
            secret = await kv_client.get_secret(settings.api_key_secret_name)
            app.state.api_key = secret.value
            logger.info("API key fetched from Key Vault")
            await kv_client.close()
        except Exception:
            logger.warning("Could not fetch API key from Key Vault")
            app.state.api_key = None

        # --- Cosmos DB ---
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
            logger.warning("Could not initialize Cosmos DB")
            app.state.cosmos_manager = None

        # --- Foundry Agent Service (fail fast) ---
        try:
            foundry_client = AzureAIAgentClient(
                credential=credential,
                project_endpoint=settings.azure_ai_project_endpoint,
            )
            app.state.foundry_client = foundry_client
            app.state.foundry_credential = credential
            logger.info(
                "Foundry client initialized: %s",
                settings.azure_ai_project_endpoint,
            )
        except Exception:
            logger.error("FATAL: Could not initialize Foundry client")
            raise  # Fail fast -- backend is useless without Foundry

        app.state.settings = settings

        yield

    finally:
        # Cleanup
        if getattr(app.state, "cosmos_manager", None) is not None:
            await app.state.cosmos_manager.close()
        await credential.close()


app = FastAPI(title="Second Brain API", lifespan=lifespan)
app.add_middleware(APIKeyMiddleware)
app.include_router(health_router)
app.include_router(inbox_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8003)
```

### Updated config.py

```python
# Source: Existing pattern + new Foundry env vars
"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    # Azure AI Foundry
    azure_ai_project_endpoint: str = ""
    azure_ai_classifier_agent_id: str = ""

    # Application Insights
    applicationinsights_connection_string: str = ""

    # Cosmos DB
    cosmos_endpoint: str = ""

    # Azure Key Vault
    key_vault_url: str = ""
    api_key_secret_name: str = "second-brain-api-key"

    # Azure Blob Storage (voice recordings -- kept for future use)
    blob_storage_url: str = ""

    # Classification
    classification_threshold: float = 0.6

    # Database
    database_name: str = "second-brain"

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
```

### RBAC Assignment Commands

```bash
# Source: https://learn.microsoft.com/azure/ai-foundry/concepts/rbac-foundry
# All three principals need Azure AI User on the Foundry resource

# 1. Developer Entra ID (Will's account)
az role assignment create \
  --role "Azure AI User" \
  --assignee "<will-entra-id-or-email>" \
  --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/second-brain-foundry-resource"

# 2. Container App managed identity
az role assignment create \
  --role "Azure AI User" \
  --assignee "<container-app-mi-principal-id>" \
  --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/second-brain-foundry-resource"

# 3. Foundry project managed identity (Cognitive Services User on OpenAI resource)
# This allows the Foundry project to access model deployments
az role assignment create \
  --role "Cognitive Services User" \
  --assignee "<foundry-project-mi-principal-id>" \
  --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/second-brain-foundry-resource"
```

### Cleanup Inventory (Files to Delete)

```
# Source files to DELETE:
backend/src/second_brain/agents/orchestrator.py    # Orchestrator agent
backend/src/second_brain/agents/perception.py      # Perception agent
backend/src/second_brain/agents/echo.py            # Phase 1 test agent
backend/src/second_brain/agents/workflow.py        # HandoffBuilder + AGUIWorkflowAdapter
backend/src/second_brain/tools/transcription.py    # Whisper transcription

# Test files to DELETE:
backend/tests/test_agui_endpoint.py                # AG-UI endpoint tests
backend/tests/test_integration.py                  # Integration tests (AG-UI pipeline)

# Files to MODIFY:
backend/src/second_brain/main.py                   # Remove all AG-UI endpoints, SSE helpers, old imports
backend/src/second_brain/config.py                 # Remove old vars, add Foundry vars
backend/src/second_brain/api/health.py             # Add Foundry connectivity check
backend/src/second_brain/agents/__init__.py         # May need docstring update
backend/pyproject.toml                             # Remove old packages, add new ones
backend/.env.example                               # Update with new env vars
backend/tests/conftest.py                          # Remove AG-UI mock fixtures
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `agent-framework-orchestrations` (HandoffBuilder) | Code-based if/elif routing in FastAPI | v2.0 decision (2026-02-25) | HandoffBuilder incompatible with AzureAIAgentClient (HTTP 400, GitHub #3097). Delete entirely. |
| `AzureOpenAIChatClient` (sync, agent-framework-azure) | `AzureAIAgentClient` (async, agent-framework-azure-ai) | Agent Framework RC releases | AzureAIAgentClient creates persistent Foundry agents with server-managed threads |
| `configure_otel_providers()` from agent_framework.observability | `configure_azure_monitor()` from azure-monitor-opentelemetry | Phase 6 | Old function was framework-specific; new one is the standard Azure OTel distro |
| `azure-ai-projects` as direct dependency | Not needed -- `agent-framework-azure-ai` pulls in `azure-ai-agents` directly | rc2 (Feb 2026) | Milestone research recommended direct `azure-ai-projects` install; rc2 changed the dependency graph |
| Sync DefaultAzureCredential for chat client | Async DefaultAzureCredential for Foundry client | Phase 6 | AzureAIAgentClient requires async credential; all new Azure SDK code uses async path |

**Deprecated/outdated:**
- `agent-framework-orchestrations`: HandoffBuilder pattern incompatible with Foundry. Delete.
- `agent-framework-ag-ui`: AG-UI endpoint format replaced by future FoundrySSEAdapter (Phase 8). Delete.
- `agent-framework-devui`: AG-UI debugging tool. No longer relevant. Delete.
- `azure-ai-projects` as direct dep: Not needed when using `agent-framework-azure-ai` rc2 which has its own dependency chain.

## Open Questions

1. **AzureAIAgentClient connectivity validation without agent registration**
   - What we know: Phase 6 needs to verify Foundry connectivity at startup. Phase 7 registers the Classifier agent. Phase 6 should NOT register any agents.
   - What's unclear: The lightest-weight API call to validate connectivity. `client.list_agents()` or similar may work but needs empirical testing.
   - Recommendation: Try `AzureAIAgentClient` construction itself (it may validate the endpoint internally). If not, a simple list call with `limit=1` is the fallest-safe check. Confirm during implementation.

2. **Application Insights connection to Foundry project via portal**
   - What we know: The Foundry portal has a "Tracing" tab where you connect an AppInsights resource. The backend also calls `configure_azure_monitor()` to send client-side traces.
   - What's unclear: Whether connecting AppInsights to the Foundry project is strictly required for Phase 6, or whether it is only needed for Phase 9 when traces from agent runs flow.
   - Recommendation: Connect AppInsights to the Foundry project now (it is a one-time portal action with no downside). This satisfies INFRA-11 and prepares for OBSV-01/02 in Phase 9.

3. **Blob Storage manager -- keep or remove?**
   - What we know: `BlobStorageManager` is initialized in lifespan for voice capture uploads. The voice-capture endpoint is being deleted.
   - What's unclear: Whether Phase 8 (FoundrySSEAdapter) will need blob storage for voice capture, or whether gpt-4o-transcribe eliminates the upload pattern.
   - Recommendation: Keep `blob_storage.py` in the codebase but remove it from lifespan initialization in main.py. It can be re-added if needed. The file itself is not entangled with AG-UI code.

## Sources

### Primary (HIGH confidence)
- [Azure AI Foundry Agents - Microsoft Agent Framework docs](https://learn.microsoft.com/agent-framework/agents/providers/azure-ai-foundry) -- AzureAIAgentClient creation, auth patterns, function tools, streaming
- [Azure AI Agents client library for Python - v1.1.0](https://learn.microsoft.com/python/api/overview/azure/ai-agents-readme?view=azure-python) -- AgentsClient API, create_agent, streaming, tracing setup
- [Azure Monitor OpenTelemetry Distro - v1.8.6](https://learn.microsoft.com/python/api/overview/azure/monitor-opentelemetry-readme?view=azure-python) -- configure_azure_monitor() API, connection string, sampling
- [RBAC for Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/concepts/rbac-foundry?view=foundry-classic) -- Azure AI User role, managed identity assignments
- [Set up tracing in Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/observability/how-to/trace-agent-setup?view=foundry) -- AppInsights connection to Foundry project
- [PyPI: agent-framework-azure-ai 1.0.0rc2](https://pypi.org/project/agent-framework-azure-ai/1.0.0rc2/) -- Latest version, dependency graph (azure-ai-agents==1.2.0b5)

### Secondary (MEDIUM confidence)
- [Authentication and authorization in Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/concepts/authentication-authorization-foundry?view=foundry-classic) -- Entra ID setup, role assignment CLI commands
- [Configure Azure Monitor OpenTelemetry](https://learn.microsoft.com/azure/azure-monitor/app/opentelemetry-configuration) -- Sampling, offline storage, connection string configuration
- [Enable Azure Monitor OpenTelemetry](https://learn.microsoft.com/azure/azure-monitor/app/opentelemetry-enable) -- Enable flow for Python applications

### Codebase Analysis (HIGH confidence)
- `backend/src/second_brain/main.py` -- 1025 lines, all AG-UI endpoints and SSE helpers identified for deletion
- `backend/src/second_brain/config.py` -- Current Settings class, env vars to add/remove
- `backend/src/second_brain/agents/` -- 4 files, 3 to delete (orchestrator, perception, echo), 1 to keep (classifier)
- `backend/src/second_brain/agents/workflow.py` -- 541 lines of HandoffBuilder/AGUIWorkflowAdapter to delete entirely
- `backend/tests/conftest.py` -- AG-UI mock fixtures to remove
- `backend/pyproject.toml` -- Current dependencies to modify
- `.github/workflows/deploy-backend.yml` -- CI/CD pipeline (no changes needed)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- versions confirmed from PyPI, official docs verified
- Architecture: HIGH -- patterns from official Microsoft docs, codebase analysis confirms clean separation
- Pitfalls: HIGH -- identified from both official docs (RBAC delay, credential lifecycle) and codebase analysis (main.py entanglement, package evolution)
- Cleanup inventory: HIGH -- every file inspected, dependencies traced

**Research date:** 2026-02-26
**Valid until:** 2026-03-12 (agent-framework-azure-ai is still RC; check for new versions before implementation)
