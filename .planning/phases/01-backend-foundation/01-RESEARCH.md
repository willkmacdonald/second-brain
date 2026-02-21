# Phase 1: Backend Foundation - Research

**Researched:** 2026-02-21
**Domain:** Agent Framework + AG-UI + FastAPI backend with Cosmos DB, OpenTelemetry, API key auth
**Confidence:** HIGH (official Microsoft docs verified for all critical claims)

## Summary

Phase 1 establishes the backend foundation: a FastAPI server exposing a Microsoft Agent Framework agent via the AG-UI protocol, with Cosmos DB persistence, OpenTelemetry tracing, and API key authentication. The key finding is that the `agent-framework-ag-ui` package handles nearly all protocol complexity with a single function call (`add_agent_framework_fastapi_endpoint`), making the server setup straightforward. OpenTelemetry is built into Agent Framework with `configure_otel_providers()` requiring only environment variable configuration. DevUI (`agent-framework-devui`) provides a local web UI for trace visualization and agent testing without external infrastructure.

The critical implementation pattern is: create `AzureOpenAIChatClient` (reads env vars automatically), create an `Agent` or use `chat_client.create_agent()`, register it with `add_agent_framework_fastapi_endpoint(app, agent, "/")`. For Phase 1, a single echo/test agent proves the stack works before building the full 7-agent handoff mesh (which is a Phase 3 concern). Cosmos DB async client should be initialized in FastAPI's lifespan context manager as a singleton. API key auth should use FastAPI middleware wrapping the entire ASGI app, since `add_agent_framework_fastapi_endpoint` does not provide built-in auth.

**Primary recommendation:** Build the simplest possible AG-UI server with one test agent, add Cosmos DB CRUD tools, add API key middleware, enable OpenTelemetry via environment variables -- in that order.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Agent Framework server runs on Azure Container Apps with AG-UI endpoint accepting HTTP POST and streaming SSE responses | `add_agent_framework_fastapi_endpoint()` from `agent-framework-ag-ui` handles HTTP POST + SSE streaming. Verified in official Microsoft Learn docs. Server runs via uvicorn. |
| INFRA-02 | Cosmos DB provisioned with 5 containers (Inbox, People, Projects, Ideas, Admin) partitioned by `/userId` | `azure.cosmos.aio.CosmosClient` with `DefaultAzureCredential` for async operations. Container creation via `database.create_container_if_not_exists()`. Singleton client in FastAPI lifespan. |
| INFRA-04 | OpenTelemetry tracing enabled across all agent handoffs with traces viewable in Agent Framework DevUI | Agent Framework includes `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-semantic-conventions-ai` by default. Call `configure_otel_providers()` + set `ENABLE_INSTRUMENTATION=true`. DevUI shows traces with `--tracing` flag or `tracing_enabled=True`. |
| INFRA-05 | API key authentication protects the AG-UI endpoint (key stored in Expo Secure Store) | FastAPI middleware checking `X-API-Key` header. `add_agent_framework_fastapi_endpoint` does NOT provide built-in auth -- must wrap the app with custom middleware or use Starlette middleware. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `agent-framework-ag-ui` | `--pre` (RC 1.0.0b260210) | AG-UI FastAPI endpoint, SSE streaming, protocol translation | Installs `agent-framework-core`, `fastapi`, `uvicorn` as dependencies. Single `add_agent_framework_fastapi_endpoint()` call wires everything. Official Microsoft package. |
| `agent-framework-core` | `--pre` (auto-installed) | Agent, ChatAgent, tool decorator, AzureOpenAIChatClient | Core agent abstractions. Provides `Agent`, `tool`, `AzureOpenAIChatClient`, observability. Auto-installed by `agent-framework-ag-ui`. |
| `azure-cosmos` | `>=4.14.0` | Async Cosmos DB NoSQL client | Provides `azure.cosmos.aio.CosmosClient` for async operations. Requires `aiohttp`. Singleton pattern recommended. |
| `azure-identity` | `>=1.16.1` | Azure AD authentication | `DefaultAzureCredential` for local dev (`AzureCliCredential`) and production (`ManagedIdentityCredential`). Use async version from `azure.identity.aio`. |
| `pydantic` | `>=2.11.2` | Data validation, Cosmos DB document schemas | Required by `ag-ui-protocol`. Agent Framework depends on it. Use for all data models. |
| `pydantic-settings` | `>=2.13.1` | Environment variable configuration | Load settings from `.env` file and environment variables with type validation. |
| `python-dotenv` | `>=1.0.0` | .env file loading | Agent Framework does NOT auto-load .env files. Must call `load_dotenv()` explicitly. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `agent-framework-devui` | `--pre` | Local testing UI + trace viewer | During development to test agents interactively and view OpenTelemetry traces. NOT for production. |
| `uvicorn` | `>=0.30.0` (auto-installed) | ASGI server | Running FastAPI locally. Auto-installed by `agent-framework-ag-ui`. |
| `opentelemetry-exporter-otlp-proto-grpc` | `>=1.27.0` | OTLP trace exporter (gRPC) | When exporting traces to external collectors (Aspire Dashboard, Jaeger). Not needed if only using DevUI's built-in trace viewer. |
| `ruff` | `>=0.8.0` | Linting + formatting | Always. Per global CLAUDE.md preferences. Dev dependency only. |
| `pytest` | `>=8.0.0` | Testing | Always. Dev dependency. |
| `pytest-asyncio` | `>=0.23.0` | Async test support | For testing async FastAPI and Cosmos DB operations. Dev dependency. |
| `httpx` | `>=0.27.0` | Async HTTP test client | For testing AG-UI SSE endpoints. FastAPI test client uses httpx. Dev dependency. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `AzureOpenAIChatClient` | `AzureOpenAIResponsesClient` | ResponsesClient supports hosted tools (code interpreter, file search). ChatClient uses Chat Completions API -- simpler, sufficient for Phase 1. Use ChatClient now, switch to ResponsesClient if hosted tools needed later. |
| `agent-framework-devui` for traces | Aspire Dashboard (Docker) | Aspire provides richer trace visualization but requires Docker. DevUI is zero-dependency for basic trace viewing. Use DevUI for Phase 1, add Aspire later if needed. |
| FastAPI middleware for auth | `fastapi-key-auth` package | Third-party package adds dependency for ~10 lines of code. Hand-roll the middleware -- it's trivial. |
| `azure-cosmos` with key auth | `azure-cosmos` with `DefaultAzureCredential` | Key auth is simpler but less secure. Use `DefaultAzureCredential` from the start -- works with `az login` locally and managed identity in production. Zero code change between environments. |

### Installation

```bash
# Create virtual environment
uv venv .venv
source .venv/bin/activate

# Core Agent Framework + AG-UI (installs agent-framework-core, fastapi, uvicorn)
uv pip install agent-framework-ag-ui --prerelease=allow

# Azure services (async Cosmos DB + authentication)
uv pip install azure-cosmos azure-identity

# Configuration
uv pip install pydantic-settings python-dotenv

# Development tools
uv pip install agent-framework-devui --prerelease=allow

# Observability (only needed if exporting to external collector)
uv pip install opentelemetry-exporter-otlp-proto-grpc

# Dev dependencies
uv pip install ruff pytest pytest-asyncio httpx
```

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── pyproject.toml              # uv project definition
├── .env                        # Local environment variables (gitignored)
├── .env.example                # Template with placeholder values
├── src/
│   └── second_brain/
│       ├── __init__.py
│       ├── main.py             # FastAPI app + AG-UI endpoint + lifespan
│       ├── config.py           # pydantic-settings configuration
│       ├── auth.py             # API key middleware
│       ├── cosmos.py           # Cosmos DB singleton client + container helpers
│       ├── agents/
│       │   ├── __init__.py
│       │   └── echo.py         # Phase 1: Simple test agent (replaced in Phase 3)
│       ├── tools/
│       │   ├── __init__.py
│       │   └── cosmos_crud.py  # @tool functions for Cosmos DB CRUD
│       └── models/
│           ├── __init__.py
│           └── documents.py    # Pydantic models for Cosmos DB documents
├── tests/
│   ├── conftest.py
│   ├── test_agui_endpoint.py   # SSE streaming tests
│   ├── test_cosmos_crud.py     # Cosmos DB CRUD tests
│   └── test_auth.py            # API key rejection tests
└── Dockerfile
```

### Pattern 1: AG-UI Server Setup (FastAPI + Agent Framework)

**What:** Register an Agent Framework agent as an AG-UI endpoint on a FastAPI app using `add_agent_framework_fastapi_endpoint()`. This single function call handles HTTP POST request parsing, agent invocation, AG-UI event translation, and SSE response streaming.

**When to use:** Always -- this is the standard way to expose agents via AG-UI.

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/getting-started
"""AG-UI server with Agent Framework."""

import os
from contextlib import asynccontextmanager

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint
from azure.identity import AzureCliCredential
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

chat_client = AzureOpenAIChatClient(
    credential=AzureCliCredential(),
    endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    deployment_name=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
)

agent = Agent(
    name="SecondBrainAgent",
    instructions="You are a helpful assistant for a personal knowledge management system.",
    chat_client=chat_client,
)

app = FastAPI(title="Second Brain AG-UI Server")
add_agent_framework_fastapi_endpoint(app, agent, "/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```
**Confidence:** HIGH -- verified from official Microsoft Learn AG-UI Getting Started tutorial (updated 2026-02-13).

### Pattern 2: FastAPI Lifespan for Cosmos DB Singleton

**What:** Use FastAPI's `lifespan` async context manager to initialize the Cosmos DB client at startup and close it at shutdown. Store the client reference on `app.state` for access in route handlers and tools.

**When to use:** Always for Cosmos DB. The async CosmosClient manages a connection pool that should be reused across all requests. Creating per-request clients causes connection churn.

**Example:**
```python
# Source: https://devblogs.microsoft.com/cosmosdb/azure-cosmos-db-python-and-fastapi/
# Updated to use lifespan (on_event("startup") is deprecated)
from contextlib import asynccontextmanager
from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey, exceptions
from azure.identity.aio import DefaultAzureCredential
from fastapi import FastAPI

DATABASE_NAME = "second-brain"
CONTAINERS = {
    "Inbox": "/userId",
    "People": "/userId",
    "Projects": "/userId",
    "Ideas": "/userId",
    "Admin": "/userId",
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup Cosmos DB client."""
    credential = DefaultAzureCredential()
    app.state.cosmos_client = CosmosClient(
        url=os.environ["COSMOS_ENDPOINT"],
        credential=credential,
    )
    # Ensure database and containers exist
    database = app.state.cosmos_client.get_database_client(DATABASE_NAME)
    app.state.cosmos_db = database
    app.state.cosmos_containers = {}
    for name, pk_path in CONTAINERS.items():
        container = database.get_container_client(name)
        app.state.cosmos_containers[name] = container

    yield  # App runs here

    # Cleanup
    await app.state.cosmos_client.close()
    await credential.close()

app = FastAPI(title="Second Brain", lifespan=lifespan)
```
**Confidence:** HIGH -- lifespan pattern from official FastAPI docs + Cosmos DB async pattern from Microsoft blog.

### Pattern 3: API Key Middleware for AG-UI Endpoint Protection

**What:** A Starlette middleware that checks for a valid `X-API-Key` header on all requests. Returns 401 for missing/invalid keys. Since `add_agent_framework_fastapi_endpoint` does not provide built-in auth, this wraps the entire FastAPI app.

**When to use:** Phase 1 and beyond. The mobile app sends the API key in every request header.

**Example:**
```python
# API key auth middleware
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate X-API-Key header on all requests."""

    async def dispatch(self, request: Request, call_next):
        # Allow health check without auth
        if request.url.path == "/health":
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        expected_key = os.environ.get("API_KEY")

        if not api_key or api_key != expected_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)

# Register BEFORE add_agent_framework_fastapi_endpoint
app.add_middleware(APIKeyMiddleware)
```
**Confidence:** HIGH -- standard FastAPI/Starlette middleware pattern. Verified that AG-UI endpoint is a regular FastAPI route that middleware can wrap.

**Important note from CLAUDE.md:** When using middleware with frameworks that register their own auth (like FastMCP), outer middleware can block valid tokens. This does NOT apply to `add_agent_framework_fastapi_endpoint` because it does NOT register its own auth middleware -- it only adds the AG-UI route handler. Custom middleware is safe here.

### Pattern 4: OpenTelemetry with Agent Framework

**What:** Agent Framework has built-in OpenTelemetry support. Call `configure_otel_providers()` once at startup to enable tracing. All agent invocations, LLM calls, and tool executions emit spans automatically.

**When to use:** From the start in Phase 1. Tracing is essential for debugging agent behavior.

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/enable-observability
from agent_framework.observability import configure_otel_providers

# Option A: Environment variable configuration (recommended)
# Set ENABLE_INSTRUMENTATION=true in .env
# Set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 (for Aspire/Jaeger)
configure_otel_providers()

# Option B: Console output for development
# Set ENABLE_CONSOLE_EXPORTERS=true in .env
configure_otel_providers()

# Automatic spans created by Agent Framework:
# - invoke_agent <agent_name>  (top-level agent invocation)
# - chat <model_name>          (LLM call with prompt/response)
# - execute_tool <tool_name>   (tool execution with args/result)
```

**For DevUI trace viewing (no external infrastructure needed):**
```python
from agent_framework.devui import serve

serve(entities=[agent], tracing_enabled=True)
# Opens browser to http://localhost:8080 with trace viewer in debug panel
```

**Or via CLI:**
```bash
devui ./agents --tracing --port 8080
```
**Confidence:** HIGH -- verified from official Agent Framework observability docs (updated 2026-02-20).

### Pattern 5: Agent Tool Definition

**What:** Agent Framework uses the `@tool` decorator (from `agent_framework`) to define functions that agents can call. Tools use `Annotated` type hints for parameter descriptions. Return strings that the LLM can parse.

**When to use:** For all Cosmos DB CRUD operations that agents need to perform.

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff
from typing import Annotated
from agent_framework import tool

@tool
async def create_record(
    container_name: Annotated[str, "Target container: Inbox, People, Projects, Ideas, or Admin"],
    title: Annotated[str, "Title or name for the record"],
    content: Annotated[str, "Main content or description"],
) -> str:
    """Create a new record in the specified Cosmos DB container."""
    import uuid
    record = {
        "id": str(uuid.uuid4()),
        "userId": "will",
        "title": title,
        "content": content,
    }
    # Access cosmos container via app.state (injected or module-level)
    container = cosmos_containers[container_name]
    result = await container.create_item(body=record)
    return f"Created record {result['id']} in {container_name}"

@tool
async def read_records(
    container_name: Annotated[str, "Container to read from: Inbox, People, Projects, Ideas, or Admin"],
) -> str:
    """Read all records from the specified Cosmos DB container."""
    container = cosmos_containers[container_name]
    items = [item async for item in container.read_all_items()]
    return str(items)
```
**Confidence:** HIGH -- `@tool` decorator syntax verified from handoff orchestration docs.

### Anti-Patterns to Avoid

- **Creating Cosmos DB client per request:** Each `CosmosClient` manages TCP connections and connection pooling. Creating per-request wastes resources. Use singleton via FastAPI lifespan.
- **Using sync Cosmos DB client in FastAPI:** The synchronous `CosmosClient` (from `azure.cosmos`) blocks the event loop. Always use `azure.cosmos.aio.CosmosClient`.
- **Storing Azure service keys in the mobile app:** The Expo app should only store the backend API key (in Expo Secure Store). Azure OpenAI keys, Cosmos DB credentials -- all stay on the backend.
- **Building all 7 agents in Phase 1:** Phase 1 should have ONE agent (an echo/test agent) to prove the AG-UI + FastAPI + Cosmos DB stack works. The Orchestrator/Classifier handoff mesh is a Phase 3 concern.
- **Skipping `load_dotenv()`:** Agent Framework does NOT automatically load `.env` files. You MUST call `load_dotenv()` at the start of your application. This is explicitly documented.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AG-UI protocol handling | Custom SSE event emission, HTTP POST parsing, event type serialization | `add_agent_framework_fastapi_endpoint()` | Handles all 17+ AG-UI event types (RUN_STARTED, TEXT_MESSAGE_CONTENT, TOOL_CALL_START, etc.), thread ID management, and streaming automatically. |
| OpenTelemetry span creation for agents | Custom tracing decorators on agent functions | `configure_otel_providers()` + `ENABLE_INSTRUMENTATION=true` | Agent Framework auto-creates `invoke_agent`, `chat`, `execute_tool` spans with GenAI semantic conventions. |
| Agent-to-Azure-OpenAI connection management | Direct `openai.AsyncAzureOpenAI` client | `AzureOpenAIChatClient` from `agent_framework.azure` | Handles credential setup (env vars, .env files, Azure credential objects), API version management, and connection pooling. |
| Trace visualization during development | Jaeger/Zipkin Docker containers | `agent-framework-devui` with `--tracing` | Zero-config local trace viewer. No Docker required. Shows span hierarchy, timing, and agent events in a web UI. |
| AG-UI client for testing | Custom HTTP client with SSE parsing | `curl -N` with proper headers, or DevUI web interface | DevUI provides interactive testing. `curl` validates raw SSE protocol. Build custom mobile client in Phase 2. |

**Key insight:** The `agent-framework-ag-ui` package abstracts the entire AG-UI protocol. Your code only touches agent definitions, tools, and business logic. The SSE streaming, event translation, thread management, and protocol compliance are all handled by the framework.

## Common Pitfalls

### Pitfall 1: Not Calling load_dotenv()

**What goes wrong:** Environment variables are not loaded. `AzureOpenAIChatClient()` fails silently or raises `ValueError` because `AZURE_OPENAI_ENDPOINT` is empty.
**Why it happens:** Agent Framework explicitly does NOT auto-load `.env` files. This is different from many Python frameworks that do.
**How to avoid:** Call `load_dotenv()` at the very top of `main.py` before any Agent Framework or Azure SDK code.
**Warning signs:** `ValueError: AZURE_OPENAI_ENDPOINT environment variable is required` even though it is in your `.env` file.

### Pitfall 2: Using Sync Cosmos DB Client in Async FastAPI

**What goes wrong:** The synchronous `CosmosClient` blocks the FastAPI event loop, causing all concurrent requests to stall.
**Why it happens:** `from azure.cosmos import CosmosClient` (sync) looks nearly identical to `from azure.cosmos.aio import CosmosClient` (async). Easy to import the wrong one.
**How to avoid:** Always import from `azure.cosmos.aio`. Always `await` all Cosmos operations. The async client requires `aiohttp` (installed automatically with `azure-cosmos`).
**Warning signs:** Requests are slow under any concurrency. Uvicorn logs show `Waited for 5 seconds` warnings.

### Pitfall 3: Middleware Order with AG-UI Endpoint

**What goes wrong:** API key middleware is added AFTER `add_agent_framework_fastapi_endpoint()`. Depending on middleware stacking order, requests may bypass auth.
**Why it happens:** FastAPI/Starlette middleware is applied in reverse order of registration. The last middleware added is the outermost (first to execute).
**How to avoid:** Add the API key middleware AFTER calling `add_agent_framework_fastapi_endpoint()` so it wraps the AG-UI endpoint. Alternatively, use `app.add_middleware(...)` which always adds to the outermost layer.
**Warning signs:** Unauthenticated requests succeed when they should fail.

### Pitfall 4: Cosmos DB Container Creation in Production

**What goes wrong:** Using `create_container_if_not_exists()` in the FastAPI lifespan works for development but creates containers with default settings (no indexing policy, default throughput).
**Why it happens:** The convenience method uses defaults that may not match your production needs.
**How to avoid:** For Phase 1, `create_container_if_not_exists()` is acceptable since this is a hobby project using serverless Cosmos DB. For production, use Bicep/ARM templates or Azure CLI to provision containers with specific settings. The lifespan should only get existing container references, not create them.
**Warning signs:** Unexpected RU charges due to unoptimized indexing policies.

### Pitfall 5: AzureOpenAIChatClient Environment Variable Names

**What goes wrong:** You set `AZURE_OPENAI_DEPLOYMENT_NAME` but `AzureOpenAIChatClient` expects `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`. The client fails to find the deployment.
**Why it happens:** The AG-UI Getting Started tutorial uses `AZURE_OPENAI_DEPLOYMENT_NAME` but the `AzureOpenAIChatClient` API reference shows `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`. The quickstart uses `AzureOpenAIResponsesClient` with `AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME`.
**How to avoid:** Check the specific client class you are using. `AzureOpenAIChatClient` uses `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`. Or pass `deployment_name=` explicitly to avoid any env var confusion.
**Warning signs:** `openai.NotFoundError: Resource not found` even though the deployment exists in Azure.

### Pitfall 6: Forgetting to Close Async Cosmos Client

**What goes wrong:** The async `CosmosClient` is not closed on shutdown, causing resource leaks and unclosed connection warnings.
**Why it happens:** Using `async with` in a context manager is the recommended pattern, but the lifespan pattern requires manual close.
**How to avoid:** Always close in the lifespan's cleanup phase (after `yield`). Close both the client and the credential object.
**Warning signs:** `ResourceWarning: unclosed` messages in logs on shutdown.

## Code Examples

Verified patterns from official sources:

### Complete main.py for Phase 1

```python
# Source: Synthesized from official Microsoft Learn docs
"""Second Brain Backend - Phase 1: Backend Foundation."""

import os
from contextlib import asynccontextmanager

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework.observability import configure_otel_providers
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint
from azure.cosmos import PartitionKey
from azure.cosmos.aio import CosmosClient as AsyncCosmosClient
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

load_dotenv()

# Enable OpenTelemetry (reads ENABLE_INSTRUMENTATION from env)
configure_otel_providers()

# --- Cosmos DB Setup ---
DATABASE_NAME = "second-brain"
CONTAINERS = ["Inbox", "People", "Projects", "Ideas", "Admin"]
PARTITION_KEY_PATH = "/userId"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Cosmos DB client and container references."""
    credential = DefaultAzureCredential()
    cosmos_client = AsyncCosmosClient(
        url=os.environ["COSMOS_ENDPOINT"],
        credential=credential,
    )
    database = cosmos_client.get_database_client(DATABASE_NAME)
    containers = {}
    for name in CONTAINERS:
        containers[name] = database.get_container_client(name)

    # Store references on app.state
    app.state.cosmos_client = cosmos_client
    app.state.cosmos_db = database
    app.state.cosmos_containers = containers

    yield

    await cosmos_client.close()
    await credential.close()

# --- FastAPI App ---
app = FastAPI(title="Second Brain AG-UI Server", lifespan=lifespan)

# --- API Key Auth Middleware ---
class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != os.environ.get("API_KEY"):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
        return await call_next(request)

app.add_middleware(APIKeyMiddleware)

# --- Health Check ---
@app.get("/health")
async def health():
    return {"status": "ok"}

# --- Agent Setup ---
chat_client = AzureOpenAIChatClient(
    credential=DefaultAzureCredential(),
    endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    deployment_name=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
)

agent = Agent(
    name="SecondBrainEcho",
    instructions="You are a test agent for the Second Brain system. Echo back what the user says and confirm the system is working.",
    chat_client=chat_client,
)

# --- AG-UI Endpoint ---
add_agent_framework_fastapi_endpoint(app, agent, "/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

### Testing the AG-UI Endpoint with curl

```bash
# Source: https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/getting-started
curl -N http://127.0.0.1:8000/ \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello, is the system working?"}
    ]
  }'

# Expected SSE output:
# data: {"type":"RUN_STARTED","threadId":"...","runId":"..."}
# data: {"type":"TEXT_MESSAGE_START","messageId":"...","role":"assistant"}
# data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"...","delta":"Yes"}
# data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"...","delta":", the system"}
# ...
# data: {"type":"TEXT_MESSAGE_END","messageId":"..."}
# data: {"type":"RUN_FINISHED","threadId":"...","runId":"..."}
```

### Cosmos DB Tool for Agents

```python
# Source: Derived from handoff orchestration docs + Cosmos DB async SDK
from typing import Annotated
from agent_framework import tool

# Module-level reference, set during app startup
cosmos_containers: dict = {}

@tool
async def create_document(
    container_name: Annotated[str, "Container name: Inbox, People, Projects, Ideas, or Admin"],
    title: Annotated[str, "Document title"],
    content: Annotated[str, "Document content"],
) -> str:
    """Create a document in the specified Cosmos DB container."""
    import uuid
    document = {
        "id": str(uuid.uuid4()),
        "userId": "will",
        "title": title,
        "content": content,
    }
    container = cosmos_containers[container_name]
    result = await container.create_item(body=document)
    return f"Created: {result['id']} in {container_name}"

@tool
async def read_document(
    container_name: Annotated[str, "Container name"],
    document_id: Annotated[str, "Document ID to read"],
) -> str:
    """Read a document by ID from the specified container."""
    container = cosmos_containers[container_name]
    item = await container.read_item(item=document_id, partition_key="will")
    return str(item)
```

### .env.example

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o

# Cosmos DB
COSMOS_ENDPOINT=https://your-cosmos-account.documents.azure.com:443/

# API Key (for mobile app authentication)
API_KEY=your-secure-api-key-here

# OpenTelemetry
ENABLE_INSTRUMENTATION=true
ENABLE_SENSITIVE_DATA=false
# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317  # Uncomment for Aspire Dashboard
# ENABLE_CONSOLE_EXPORTERS=true  # Uncomment for console trace output
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| AutoGen / Semantic Kernel (separate) | Microsoft Agent Framework (unified) | Feb 2026 (RC) | Single framework for all agent patterns. AutoGen deprecated. |
| Custom SSE event handling for agents | `add_agent_framework_fastapi_endpoint()` | Dec 2025 | One function call replaces hundreds of lines of custom SSE code. |
| `@app.on_event("startup")` | `@asynccontextmanager` lifespan | FastAPI 0.109+ | `on_event` is deprecated. Lifespan is the only supported pattern. |
| Manual OpenTelemetry setup | `configure_otel_providers()` | Agent Framework RC | One function call configures traces, metrics, and logs from env vars. |
| `opentelemetry-semantic-conventions` | `opentelemetry-semantic-conventions-ai` | 2025 | GenAI-specific semantic conventions for agent/LLM spans. Included in Agent Framework by default. |
| Pydantic settings in Agent Framework | `load_dotenv()` + env vars | Agent Framework RC | Agent Framework removed auto-loading of .env files. Must call `load_dotenv()` explicitly. |

**Deprecated/outdated:**
- **AutoGen (standalone):** Merged into Agent Framework. Import paths changed. Migration guide available at Microsoft Learn.
- **Semantic Kernel (standalone):** Merged into Agent Framework. The `semantic-kernel` package still exists but is deprecated.
- **`app.on_event("startup")`:** Deprecated in FastAPI. Use `lifespan` async context manager instead.
- **`AzureOpenAIChatClient` with `api_key=` only:** Use `credential=DefaultAzureCredential()` for Azure AD auth. API keys are fallback only.

## Open Questions

1. **Cosmos DB Container Provisioning Strategy**
   - What we know: `create_container_if_not_exists()` works for dev. Bicep templates are standard for production.
   - What's unclear: Should Phase 1 provision containers in the lifespan (simple) or use a separate provisioning script/Bicep (correct)?
   - Recommendation: Use lifespan for Phase 1 (hobby project). Add Bicep in the deployment phase. Containers are cheap to recreate on serverless tier.

2. **AzureOpenAIChatClient vs AzureOpenAIResponsesClient for Phase 1**
   - What we know: ChatClient uses Chat Completions API (simpler). ResponsesClient uses Responses API (supports hosted tools like code interpreter).
   - What's unclear: The quickstart tutorial uses `AzureOpenAIResponsesClient` but the AG-UI Getting Started uses `AzureOpenAIChatClient`. Both work with `add_agent_framework_fastapi_endpoint()`.
   - Recommendation: Use `AzureOpenAIChatClient` for Phase 1. It is simpler and sufficient. The second brain agents only need local function tools, not hosted tools.

3. **Tool Injection Pattern for Cosmos DB References**
   - What we know: Tools need access to Cosmos DB container references. Module-level globals work but are not clean.
   - What's unclear: Agent Framework supports middleware and dependency injection, but the exact pattern for injecting app-level state into `@tool` functions is not clearly documented.
   - Recommendation: Start with module-level references set during lifespan. This is the pattern shown in the official Cosmos DB + FastAPI blog. Refactor to middleware/DI if it becomes unwieldy.

4. **DevUI vs Aspire Dashboard for Trace Viewing**
   - What we know: DevUI has built-in trace viewing with `--tracing`. Aspire Dashboard requires Docker but has richer visualization.
   - What's unclear: Does DevUI's trace viewer show enough detail for debugging agent handoffs (which are a Phase 3 concern)?
   - Recommendation: Use DevUI for Phase 1 (zero additional setup). Add Aspire Dashboard if trace visualization is insufficient.

## Sources

### Primary (HIGH confidence)
- [AG-UI Getting Started (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/getting-started) -- Complete Python server + client code, AG-UI event types, curl test example. Updated 2026-02-13.
- [Agent Framework Quickstart (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/get-started/your-first-agent) -- Basic agent creation, `AzureOpenAIResponsesClient.as_agent()` pattern. Updated 2026-02-20.
- [agent_framework.ag_ui API Reference (Microsoft Learn)](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.ag_ui) -- `add_agent_framework_fastapi_endpoint()` full signature with all parameters.
- [AzureOpenAIChatClient API Reference (Microsoft Learn)](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.azure.azureopenaichatclient) -- Constructor parameters, env var names (`AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`), `create_agent()` method.
- [Agent Framework Observability (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/enable-observability) -- `configure_otel_providers()`, env vars (`ENABLE_INSTRUMENTATION`, `ENABLE_SENSITIVE_DATA`), custom spans, Aspire Dashboard setup. Updated 2026-02-20.
- [DevUI Overview (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/devui/) -- Installation, CLI options, `serve()` API, tracing flag. Updated 2026-02-13.
- [DevUI Tracing (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/user-guide/devui/tracing) -- `--tracing` flag, trace structure, OTLP endpoint export.
- [Handoff Orchestration (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff) -- `HandoffBuilder` Python examples, `@tool` decorator, agent creation via `chat_client.as_agent()`. Updated 2026-02-13.
- [Azure Cosmos DB Python + FastAPI (Microsoft Blog)](https://devblogs.microsoft.com/cosmosdb/azure-cosmos-db-python-and-fastapi/) -- Async client pattern, CRUD operations, FastAPI integration.
- [azure.cosmos.aio.CosmosClient (Microsoft Learn)](https://learn.microsoft.com/en-us/python/api/azure-cosmos/azure.cosmos.aio.cosmosclient) -- Async client API, `DefaultAzureCredential` usage.

### Secondary (MEDIUM confidence)
- [Building an AI Agent Server with AG-UI (baeke.info)](https://baeke.info/2025/12/07/building-an-ai-agent-server-with-ag-ui-and-microsoft-agent-framework/) -- Practical implementation patterns, tool return types (must be JSON strings), `.as_tool()` for sub-agents.
- [Building Interactive Agent UIs (MS Tech Community)](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/building-interactive-agent-uis-with-ag-ui-and-microsoft-agent-framework/4488249) -- AG-UI patterns and community guidance.
- [FastAPI Lifespan Events (fastapi.tiangolo.com)](https://fastapi.tiangolo.com/advanced/events/) -- Official FastAPI lifespan documentation.
- [FastAPI Security Tools (fastapi.tiangolo.com)](https://fastapi.tiangolo.com/reference/security/) -- APIKeyHeader dependency for authentication.

### Tertiary (LOW confidence)
- Cosmos DB container provisioning in FastAPI lifespan: While the pattern is well-established for existing containers, using `create_container_if_not_exists()` in production is not explicitly endorsed or discouraged in the docs. Flag for validation.
- Tool injection pattern: No official documentation shows how to inject `app.state` into `@tool` functions. Module-level globals are used in examples but may have issues in testing.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages verified on PyPI and Microsoft Learn docs. Version compatibility confirmed.
- Architecture: HIGH -- AG-UI endpoint setup, FastAPI lifespan, and Cosmos DB async patterns all verified from official docs.
- Pitfalls: HIGH -- environment variable naming verified from API reference. Async client import paths verified. Middleware order validated against Starlette docs.
- OpenTelemetry: HIGH -- `configure_otel_providers()` and DevUI tracing verified from docs updated 2026-02-20.
- API key auth: MEDIUM -- standard pattern, but exact interaction with AG-UI endpoint middleware stack not explicitly documented. Verified that AG-UI does NOT register its own auth middleware.

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (Agent Framework may reach GA before then, potentially changing package names or APIs)

---

## Agent Framework Deep Dive

**Added:** 2026-02-21
**Purpose:** Detailed reference for agent definitions, handoff patterns, tool registration, and dependency injection -- the patterns needed to build Phase 1's stub agent and Phase 3's multi-agent handoff mesh.

### 1. Agent Definitions

#### The Agent Type Hierarchy

Agent Framework has a clear class hierarchy. Understanding it avoids confusion between old names (like "ChatCompletionAgent" from AutoGen/Semantic Kernel) and the current API:

| Class | Import | Purpose | Phase 1 Use |
|-------|--------|---------|-------------|
| `BaseAgent` | `from agent_framework import BaseAgent` | Abstract base class. Cannot be instantiated directly. | Do not use directly. |
| `ChatAgent` | `from agent_framework import ChatAgent` | Primary concrete agent -- wraps a chat client + tools + instructions. This is what `as_agent()` returns. | This is the agent type you get when calling `chat_client.as_agent()`. |
| `WorkflowAgent` | `from agent_framework import WorkflowAgent` | Wraps a workflow (handoff, sequential, concurrent) and exposes it as a single agent. | Phase 3 -- wrap the handoff workflow as an agent for the AG-UI endpoint. |

**Confidence:** HIGH -- verified from official API reference page (learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework), updated 2026-02-13.

**IMPORTANT terminology note:** There is NO class called `ChatCompletionAgent` in the current Agent Framework RC. That name is from the old AutoGen/Semantic Kernel era. The current equivalent is `ChatAgent`. If you see `ChatCompletionAgent` in any example, it is outdated.

#### Creating an Agent: Three Patterns

**Pattern A: `chat_client.as_agent()` (Recommended)**

This is the most common pattern. The chat client creates and returns a `ChatAgent` instance.

```python
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential

chat_client = AzureOpenAIChatClient(credential=AzureCliCredential())

agent = chat_client.as_agent(
    name="SecondBrainEcho",
    instructions="You are a test agent for the Second Brain system.",
    tools=[my_tool_1, my_tool_2],           # Optional: list of @tool functions
    description="Echo agent for testing",    # Optional: used by handoff for routing
    temperature=0.7,                         # Optional: LLM parameters
    max_tokens=1000,                         # Optional: limit response length
    middleware=[my_middleware],               # Optional: agent/function/chat middleware
)
```

**Source:** https://learn.microsoft.com/en-us/agent-framework/agents/providers/azure-openai (Updated 2026-02-13)

**Pattern B: `ChatAgent(...)` direct construction**

Use when you need more control or are working with a generic `ChatClientProtocol`.

```python
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential

chat_client = AzureOpenAIChatClient(credential=AzureCliCredential())

agent = ChatAgent(
    chat_client=chat_client,
    name="SecondBrainEcho",
    instructions="You are a test agent.",
    tools=[my_tool_1, my_tool_2],
    context_providers=None,        # Optional: dynamic context injection
    middleware=None,                # Optional: middleware chain
    frequency_penalty=None,
    presence_penalty=None,
    temperature=0.7,
    top_p=None,
    max_tokens=1000,
    seed=None,
    request_kwargs=None,           # Optional: extra kwargs passed to LLM
)
```

**Source:** https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework (API reference)

**Pattern C: `AzureOpenAIResponsesClient` (for hosted tools)**

Use when you need code interpreter, file search, web search, or hosted MCP tools. NOT needed for Phase 1.

```python
from agent_framework.azure import AzureOpenAIResponsesClient
from azure.identity import AzureCliCredential

client = AzureOpenAIResponsesClient(credential=AzureCliCredential())
agent = client.as_agent(
    name="FullFeaturedAgent",
    instructions="You have access to hosted tools.",
    tools=[client.get_code_interpreter_tool(), client.get_web_search_tool()],
)
```

**Source:** https://learn.microsoft.com/en-us/agent-framework/agents/providers/azure-openai

#### Which Client for Phase 1?

Use `AzureOpenAIChatClient` (Chat Completions API). Reasons:

1. **Simplest API surface** -- Chat Completions is the most widely supported API.
2. **Function tools are fully supported** -- our Cosmos DB CRUD tools work with ChatClient.
3. **No hosted tools needed** -- Second Brain agents only need local function tools.
4. **Less setup** -- no Azure AI Foundry project endpoint needed, just an Azure OpenAI resource.

Switch to `AzureOpenAIResponsesClient` only if you need code interpreter, file search, web search, or hosted MCP. That is not in scope for any phase.

**Confidence:** HIGH -- provider comparison table verified from official docs.

#### Running an Agent

```python
# Non-streaming (complete response)
result = await agent.run("What is in my inbox?")
print(result.text)

# Streaming (token-by-token)
async for chunk in agent.run("What is in my inbox?", stream=True):
    if chunk.text:
        print(chunk.text, end="", flush=True)

# Multi-turn with session (conversation memory)
session = agent.create_session()
r1 = await agent.run("My name is Will", session=session)
r2 = await agent.run("What is my name?", session=session)  # Remembers "Will"
```

**Source:** https://learn.microsoft.com/en-us/agent-framework/get-started/your-first-agent (Updated 2026-02-20)

### 2. Tool Registration

#### Defining Tools with `@tool`

The `@tool` decorator (aliased as `@ai_function`) converts a Python function into something the LLM can call. Two key mechanisms for parameter descriptions: `Annotated` type hints and Pydantic `Field`.

**Minimal tool:**
```python
from agent_framework import tool

@tool
def echo(message: str) -> str:
    """Echo the message back."""
    return message
```

**Tool with full descriptions:**
```python
from typing import Annotated
from pydantic import Field
from agent_framework import tool

@tool
async def create_inbox_item(
    title: Annotated[str, Field(description="Title for the inbox item")],
    content: Annotated[str, Field(description="Content or body of the item")],
    priority: Annotated[int, Field(description="Priority 1-5, where 1 is highest")] = 3,
) -> str:
    """Create a new item in the user's inbox."""
    # implementation...
    return f"Created inbox item: {title}"
```

**Tool with explicit name and description override:**
```python
@tool(name="search_people", description="Search the People container by name")
async def search_people(
    query: Annotated[str, Field(description="Name or partial name to search for")],
) -> str:
    """Search for people by name."""
    # implementation...
    return "results..."
```

**Tool with approval mode (human-in-the-loop):**
```python
@tool(approval_mode="always_require")
async def delete_document(
    container_name: Annotated[str, Field(description="Container name")],
    document_id: Annotated[str, Field(description="Document ID to delete")],
) -> str:
    """Delete a document permanently. Requires human approval."""
    # implementation...
    return f"Deleted {document_id}"
```

**Source:** https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools (Updated 2026-02-20)

**Confidence:** HIGH -- all patterns verified from official function tools tutorial.

#### `@tool` Decorator Parameters

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `name` | `str \| None` | Function `__name__` | Custom tool name exposed to the LLM |
| `description` | `str \| None` | Function docstring | Custom description for the LLM |
| `approval_mode` | `"always_require" \| "never_require" \| None` | `None` | Require human approval before execution |
| `max_invocations` | `int \| None` | `None` | Max times the tool can be called per agent run |
| `max_invocation_exceptions` | `int \| None` | `None` | Max exceptions before the tool is disabled |
| `schema` | `BaseModel \| dict \| None` | `None` | Explicit Pydantic model or JSON schema for parameters |

#### Assigning Tools to Agents

Tools are passed as a list (or single function) to `as_agent()` or `ChatAgent()`:

```python
# Single tool (no list needed)
agent = chat_client.as_agent(
    instructions="You help manage inbox items.",
    tools=create_inbox_item,
)

# Multiple tools as a list
agent = chat_client.as_agent(
    instructions="You help manage the second brain.",
    tools=[create_inbox_item, search_people, read_records, delete_document],
)
```

**Important:** Each agent gets its own tool set. In Phase 3, the Classifier agent gets classification tools, the InboxManager gets inbox CRUD tools, etc. Tools are NOT shared across agents in a handoff workflow -- each specialist owns its tools.

#### Sync vs Async Tools

Both synchronous and asynchronous functions work with `@tool`:

```python
# Sync tool -- runs in a thread pool automatically
@tool
def get_current_time() -> str:
    """Get the current server time."""
    from datetime import datetime
    return datetime.now().isoformat()

# Async tool -- runs on the event loop (preferred for I/O)
@tool
async def read_from_cosmos(container_name: str) -> str:
    """Read items from Cosmos DB."""
    # await cosmos operations here
    pass
```

**Rule for Second Brain:** Always use async tools when they perform I/O (Cosmos DB reads/writes). Sync tools are fine for pure computation (formatting, timestamp generation).

#### Tool Type Constraints

- **Parameter types:** Must be JSON-serializable types that the LLM can produce: `str`, `int`, `float`, `bool`, `list`, `dict`, `Optional[T]`, and Pydantic models.
- **Return type:** Must be `str`. Tools return strings that the LLM interprets. For complex data, serialize to JSON string.
- **Annotated descriptions:** Use `Annotated[type, Field(description="...")]` for each parameter. Without descriptions, the LLM has to guess from parameter names alone.
- **No positional-only args:** All parameters must be keyword arguments (the LLM calls tools by name).

#### Dependency Injection into Tools: The `**kwargs` Pattern

**This is the critical pattern for passing Cosmos DB references to tools.**

Agent Framework supports injecting runtime context into tools via `**kwargs`. When you call `agent.run(...)`, any extra keyword arguments are passed through to all tool invocations. The tool receives them in `**kwargs` -- the LLM never sees them.

```python
from typing import Annotated, Any
from pydantic import Field
from agent_framework import tool

@tool
async def create_inbox_item(
    title: Annotated[str, Field(description="Title for the inbox item")],
    content: Annotated[str, Field(description="Content or body of the item")],
    **kwargs: Any,  # <-- Receives injected runtime context
) -> str:
    """Create a new item in the user's inbox."""
    # Extract injected dependencies
    cosmos_containers = kwargs.get("cosmos_containers", {})
    user_id = kwargs.get("user_id", "will")

    container = cosmos_containers.get("Inbox")
    if not container:
        return "Error: Inbox container not available"

    import uuid
    document = {
        "id": str(uuid.uuid4()),
        "userId": user_id,
        "title": title,
        "content": content,
    }
    result = await container.create_item(body=document)
    return f"Created inbox item: {result['id']}"


# When running the agent, pass the dependencies as kwargs:
result = await agent.run(
    "Add 'Buy groceries' to my inbox",
    cosmos_containers=app.state.cosmos_containers,  # Injected into **kwargs
    user_id="will",                                  # Injected into **kwargs
)
```

**Source:** https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools -- complete example titled "AI Function with kwargs Example" (Updated 2026-02-20)

**Confidence:** HIGH -- this pattern is explicitly documented in the official function tools tutorial with a complete runnable example.

**How this works with AG-UI:** The `add_agent_framework_fastapi_endpoint()` function handles the HTTP layer. When the AG-UI client sends a message, the endpoint calls `agent.run()` internally. The question is: can we pass kwargs through the AG-UI endpoint? This needs validation during Phase 1 implementation. If not, the fallback is module-level references or a class-based tool pattern (documented below).

#### Alternative: Class-Based Tools for Shared State

When `**kwargs` injection is not available (e.g., through the AG-UI endpoint which may not pass extra kwargs), use a class with instance methods as tools:

```python
class CosmosTools:
    """Tools that share Cosmos DB container references."""

    def __init__(self, containers: dict):
        self.containers = containers

    @tool
    async def create_inbox_item(
        self,
        title: Annotated[str, Field(description="Title for the inbox item")],
        content: Annotated[str, Field(description="Content or body of the item")],
    ) -> str:
        """Create a new item in the user's inbox."""
        import uuid
        container = self.containers["Inbox"]
        document = {
            "id": str(uuid.uuid4()),
            "userId": "will",
            "title": title,
            "content": content,
        }
        result = await container.create_item(body=document)
        return f"Created inbox item: {result['id']}"

    @tool
    async def read_inbox(self) -> str:
        """Read all items from the inbox."""
        container = self.containers["Inbox"]
        items = [item async for item in container.read_all_items()]
        return str(items)


# In the FastAPI lifespan, after initializing Cosmos containers:
cosmos_tools = CosmosTools(containers=app.state.cosmos_containers)

# Pass instance methods as tools to the agent:
agent = chat_client.as_agent(
    instructions="You manage the second brain inbox.",
    tools=[cosmos_tools.create_inbox_item, cosmos_tools.read_inbox],
)
```

**Source:** https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools -- "Create a class with multiple function tools" section.

**Confidence:** HIGH -- class-based tool pattern explicitly documented with official examples.

**Recommendation for Phase 1:** Use the class-based tool pattern. It works regardless of whether the AG-UI endpoint passes kwargs, and it cleanly binds Cosmos DB references without module-level globals. The class is justified here per CLAUDE.md guidelines (manages stateful client references -- Cosmos containers).

#### Alternative: Module-Level References (Simplest, Less Testable)

```python
# cosmos_crud.py
from typing import Annotated
from pydantic import Field
from agent_framework import tool

# Set during FastAPI lifespan initialization
_containers: dict = {}

def init_tools(containers: dict) -> None:
    """Called from lifespan to inject Cosmos container references."""
    global _containers
    _containers = containers

@tool
async def create_inbox_item(
    title: Annotated[str, Field(description="Title for the inbox item")],
    content: Annotated[str, Field(description="Content or body of the item")],
) -> str:
    """Create a new item in the user's inbox."""
    container = _containers["Inbox"]
    # ... create document ...
    return "Created"
```

This works but makes testing harder (must mock globals). Use class-based pattern instead.

### 3. Handoff Pattern

#### Overview

The handoff pattern creates a **mesh topology** where agents can transfer control to one another. There is no central orchestrator routing messages -- each agent decides when to hand off based on the conversation context. The `HandoffBuilder` automatically injects "handoff tools" into each agent so the LLM can call a function like `transfer_to_refund_agent()` to hand off.

**Key insight:** Handoff is fundamentally different from "agent-as-tools" (where a primary agent delegates sub-tasks). In handoff, the receiving agent takes **full ownership** of the conversation. In agent-as-tools, the primary agent retains control.

**Source:** https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff (Updated 2026-02-13)

#### HandoffBuilder API

```python
from agent_framework.orchestrations import HandoffBuilder

workflow = (
    HandoffBuilder(
        name="second_brain_handoff",                    # Workflow name
        participants=[triage, inbox_mgr, people_mgr],   # All agents in the mesh
        termination_condition=lambda conv: False,        # When to end (return True to stop)
    )
    .with_start_agent(triage)           # Which agent receives the first user message
    .build()                            # Returns a Workflow object
)
```

**Full HandoffBuilder method chain:**

| Method | Purpose |
|--------|---------|
| `HandoffBuilder(name, participants, termination_condition)` | Constructor. `participants` is the list of all agents. `termination_condition` is a callable that takes the conversation list and returns bool. |
| `.with_start_agent(agent)` | Sets which agent gets the initial user message. |
| `.add_handoff(from_agent, [to_agents])` | Restricts which agents `from_agent` can hand off to. By default, ALL agents can hand off to ALL others. |
| `.with_autonomous_mode()` | Enables autonomous mode (no human input needed between turns). Can target specific agents. |
| `.with_autonomous_mode(agents=[...], prompts={...}, turn_limits={...})` | Fine-grained autonomous control per agent. |
| `.build()` | Returns a `Workflow` object. |

**Confidence:** HIGH -- all methods verified from official handoff orchestration docs.

#### How Handoff Control Flow Works

1. **User sends message** to the workflow.
2. **Start agent** receives the message and generates a response.
3. If the start agent decides to hand off, it calls a **handoff tool** (auto-injected by HandoffBuilder) -- e.g., `transfer_to_inbox_manager()`.
4. The **HandoffBuilder** intercepts this tool call and transfers conversation ownership to the target agent.
5. The target agent receives the **full conversation history** (all messages broadcast to all participants).
6. If the target agent does NOT hand off, the workflow emits a `request_info` event requesting user input.
7. The cycle repeats until the `termination_condition` returns `True`.

**What "handing back" looks like:** The specialist agent calls a handoff tool to transfer back to the triage agent (or any other agent in its allowed handoff list). There is no automatic "return to caller" -- the agent must explicitly hand off.

#### Configuring Handoff Routes

**Default: all-to-all mesh (every agent can hand off to every other agent)**

```python
workflow = (
    HandoffBuilder(
        name="second_brain",
        participants=[triage, inbox_mgr, people_mgr, project_mgr, idea_mgr],
    )
    .with_start_agent(triage)
    .build()
)
```

**Custom routes: restrict who can hand off to whom**

```python
workflow = (
    HandoffBuilder(
        name="second_brain",
        participants=[triage, inbox_mgr, people_mgr, project_mgr, idea_mgr],
    )
    .with_start_agent(triage)
    # Triage can route to any specialist
    .add_handoff(triage, [inbox_mgr, people_mgr, project_mgr, idea_mgr])
    # Each specialist can only hand back to triage
    .add_handoff(inbox_mgr, [triage])
    .add_handoff(people_mgr, [triage])
    .add_handoff(project_mgr, [triage])
    .add_handoff(idea_mgr, [triage])
    .build()
)
```

#### Context Synchronization in Handoffs

All participants in a handoff workflow share conversation context through **broadcasting**:
- When any agent generates a response, it is broadcast to all other participants.
- When user input is received, it is broadcast to all participants.
- **Tool calls and handoff tool calls are NOT broadcast** -- only user and agent messages.
- Each agent maintains its own `AgentSession` -- they do NOT share session instances (because different agent types may have different session implementations).

**Source:** Handoff docs, "Context Synchronization" section.

#### Complete Handoff Example (Phase 3 Preview)

This shows what the full Second Brain handoff will look like in Phase 3. Phase 1 only needs a single agent -- this is included for architectural understanding.

```python
"""Second Brain Agent Handoff Workflow -- Phase 3 target architecture."""

from typing import Annotated
from pydantic import Field
from agent_framework import tool
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework.orchestrations import HandoffBuilder
from azure.identity import AzureCliCredential

# --- Chat Client ---
chat_client = AzureOpenAIChatClient(credential=AzureCliCredential())

# --- Tools (simplified for illustration) ---
@tool
async def add_to_inbox(
    title: Annotated[str, Field(description="Item title")],
    content: Annotated[str, Field(description="Item content")],
) -> str:
    """Add an item to the inbox."""
    return f"Added '{title}' to inbox"

@tool
async def search_people(
    query: Annotated[str, Field(description="Name to search")],
) -> str:
    """Search the People container."""
    return f"Found people matching '{query}'"

# --- Agents ---
triage_agent = chat_client.as_agent(
    name="triage",
    instructions=(
        "You are the Second Brain triage agent. Determine what the user needs and "
        "hand off to the appropriate specialist:\n"
        "- inbox_manager: for adding/reading/managing inbox items\n"
        "- people_manager: for managing contacts and people\n"
        "ALWAYS hand off to a specialist. Do not answer domain questions yourself."
    ),
    description="Routes user requests to the appropriate specialist agent.",
)

inbox_manager = chat_client.as_agent(
    name="inbox_manager",
    instructions=(
        "You manage the user's inbox. You can add items, read items, and "
        "update items. When done, hand off back to triage."
    ),
    description="Manages inbox items -- add, read, update, delete.",
    tools=[add_to_inbox],
)

people_manager = chat_client.as_agent(
    name="people_manager",
    instructions=(
        "You manage the user's contacts. You can search, add, and update "
        "people records. When done, hand off back to triage."
    ),
    description="Manages people/contacts -- search, add, update.",
    tools=[search_people],
)

# --- Handoff Workflow ---
workflow = (
    HandoffBuilder(
        name="second_brain_handoff",
        participants=[triage_agent, inbox_manager, people_manager],
    )
    .with_start_agent(triage_agent)
    .add_handoff(triage_agent, [inbox_manager, people_manager])
    .add_handoff(inbox_manager, [triage_agent])
    .add_handoff(people_manager, [triage_agent])
    .with_autonomous_mode(agents=[triage_agent])  # Triage auto-routes without user input
    .build()
)
```

**Confidence:** HIGH -- assembled from verified HandoffBuilder API + official handoff examples.

#### Exposing a Handoff Workflow via AG-UI

To expose a handoff workflow through the AG-UI endpoint, wrap it in a `WorkflowAgent`:

```python
from agent_framework import WorkflowAgent
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint

# Wrap the workflow as a single agent
workflow_agent = WorkflowAgent(workflow=workflow, name="SecondBrainWorkflow")

# Register with AG-UI endpoint
add_agent_framework_fastapi_endpoint(app, workflow_agent, "/")
```

**Confidence:** MEDIUM -- `WorkflowAgent` is documented in the API reference with the constructor `WorkflowAgent(workflow, name)`. Its use with `add_agent_framework_fastapi_endpoint` is logical (the function accepts any agent protocol) but not explicitly shown in the handoff docs. Needs validation during implementation.

### 4. Agent-as-Tool Pattern (Alternative to Handoff)

For simpler delegation without full handoff semantics, you can use an agent as a tool for another agent. The inner agent runs as a sub-task and returns control to the outer agent.

```python
# Inner agent
weather_agent = chat_client.as_agent(
    name="WeatherAgent",
    description="Answers weather questions",  # LLM sees this to decide when to call
    instructions="You answer questions about the weather.",
    tools=[get_weather],
)

# Outer agent uses inner agent as a tool
main_agent = chat_client.as_agent(
    instructions="You are a helpful assistant.",
    tools=[weather_agent.as_tool()],  # .as_tool() converts agent to callable tool
)

# Custom tool name/description
weather_tool = weather_agent.as_tool(
    name="WeatherLookup",
    description="Look up weather information for any location",
    arg_name="query",
    arg_description="The weather query or location",
)
```

**When to use agent-as-tool vs handoff:**
- **Agent-as-tool:** Primary agent retains control. Sub-agent handles ONE sub-task and returns. Good for utility agents (weather, time, calculations).
- **Handoff:** Receiving agent takes FULL ownership. Good for domain specialists that need multi-turn conversation (inbox management, people management).

**For Second Brain:** Use handoff for the specialist agents (Phase 3). Agent-as-tool is not the right pattern here because specialists need multi-turn conversation ownership.

**Source:** https://learn.microsoft.com/en-us/agent-framework/agents/tools/ -- "Using an Agent as a Function Tool" section.

### 5. Middleware for Cross-Cutting Concerns

Agent Framework supports three middleware types that form a pipeline around agent execution. Middleware is relevant for Phase 1 (logging, security) and essential for Phase 3 (observability across handoffs).

#### Middleware Types

| Type | Context Object | What It Intercepts | Use Case |
|------|---------------|-------------------|----------|
| Agent middleware | `AgentContext` | Agent run (input messages, output result) | Logging, security validation, input filtering |
| Function middleware | `FunctionInvocationContext` | Tool invocations (function name, args, result) | Tool execution logging, timing, error handling |
| Chat middleware | `ChatContext` | LLM requests/responses (raw messages, options) | Token counting, prompt injection detection |

#### Registration Patterns

```python
from agent_framework import AgentMiddleware, FunctionMiddleware, AgentContext, FunctionInvocationContext

# Class-based function middleware (for Cosmos DB tool logging)
class ToolLoggingMiddleware(FunctionMiddleware):
    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        import logging
        logger = logging.getLogger("second_brain.tools")
        logger.info(f"Tool called: {context.function.name}")
        await call_next()
        logger.info(f"Tool completed: {context.function.name}")

# Register middleware when creating an agent
agent = chat_client.as_agent(
    name="SecondBrainEcho",
    instructions="You are a test agent.",
    tools=[create_inbox_item],
    middleware=[ToolLoggingMiddleware()],  # Applied to ALL runs of this agent
)

# Or register per-run
result = await agent.run(
    "Add something to my inbox",
    middleware=[ToolLoggingMiddleware()],  # Applied to THIS run only
)
```

**Middleware execution order:** Agent-level middleware (outermost) wraps run-level middleware (innermost). For agent middleware `[A1, A2]` and run middleware `[R1, R2]`, execution is: `A1 -> A2 -> R1 -> R2 -> Agent -> R2 -> R1 -> A2 -> A1`.

**Source:** https://learn.microsoft.com/en-us/agent-framework/agents/middleware/ (Updated 2026-02-20)

**Confidence:** HIGH -- complete middleware examples with imports verified from official docs.

### 6. Orchestration Builders (Beyond Handoff)

For reference, Agent Framework provides four workflow orchestration patterns. Only handoff is needed for Second Brain, but knowing the alternatives helps understand the design space:

| Builder | Import | Pattern | When to Use |
|---------|--------|---------|-------------|
| `HandoffBuilder` | `from agent_framework.orchestrations import HandoffBuilder` | Mesh -- agents hand off to each other | Multi-domain specialists needing multi-turn conversation |
| `SequentialBuilder` | `from agent_framework import SequentialBuilder` | Pipeline -- agents process in fixed order | Review chains, content pipelines |
| `ConcurrentBuilder` | `from agent_framework import ConcurrentBuilder` | Fan-out/fan-in -- agents process in parallel | Multiple perspectives, ensemble responses |
| `MagenticBuilder` | `from agent_framework import MagenticBuilder` | LLM-managed -- a manager agent plans and delegates | Complex multi-step tasks needing dynamic planning |

**Confidence:** HIGH -- all builders verified in API reference.

### 7. Phase 1 vs Phase 3 Architecture Bridge

#### Phase 1: Single Agent (prove the stack works)

```python
# main.py -- Phase 1 architecture
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint

chat_client = AzureOpenAIChatClient(credential=AzureCliCredential())

# One agent, simple tools
agent = chat_client.as_agent(
    name="SecondBrainEcho",
    instructions="You are a test agent. You can create and read inbox items.",
    tools=[cosmos_tools.create_inbox_item, cosmos_tools.read_inbox],
)

add_agent_framework_fastapi_endpoint(app, agent, "/")
```

#### Phase 3: Multi-Agent Handoff (full system)

```python
# main.py -- Phase 3 architecture (builds on Phase 1)
from agent_framework import WorkflowAgent
from agent_framework.orchestrations import HandoffBuilder
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint

# Multiple specialized agents (each with own tools)
triage = chat_client.as_agent(name="triage", instructions="...", description="...")
inbox_mgr = chat_client.as_agent(name="inbox_manager", instructions="...", tools=[...])
people_mgr = chat_client.as_agent(name="people_manager", instructions="...", tools=[...])
# ... more specialists ...

# Wire them into a handoff workflow
workflow = (
    HandoffBuilder(name="second_brain", participants=[triage, inbox_mgr, people_mgr])
    .with_start_agent(triage)
    .add_handoff(triage, [inbox_mgr, people_mgr])
    .add_handoff(inbox_mgr, [triage])
    .add_handoff(people_mgr, [triage])
    .with_autonomous_mode(agents=[triage])
    .build()
)

# Wrap workflow as agent, expose via AG-UI
workflow_agent = WorkflowAgent(workflow=workflow, name="SecondBrain")
add_agent_framework_fastapi_endpoint(app, workflow_agent, "/")
```

**The transition from Phase 1 to Phase 3:**
1. Replace the single `agent` with a `WorkflowAgent` wrapping a `HandoffBuilder` workflow.
2. Move the single agent's tools into specialist agents.
3. Add a triage agent with routing instructions.
4. The AG-UI endpoint call stays exactly the same -- `add_agent_framework_fastapi_endpoint(app, workflow_agent, "/")`.
5. The FastAPI lifespan, Cosmos DB setup, middleware, and API key auth remain unchanged.

This is why Phase 1 builds the foundation correctly: the AG-UI endpoint, Cosmos DB singleton, API key auth, and tool patterns all carry forward without modification.

### 8. Deep Dive Open Questions

1. **AG-UI endpoint `**kwargs` passthrough**
   - What we know: `agent.run()` supports `**kwargs` that flow to tools. The AG-UI endpoint calls `agent.run()` internally.
   - What's unclear: Does `add_agent_framework_fastapi_endpoint()` support passing extra kwargs that flow through to tools? The API reference shows optional `request_kwargs` but it is unclear if these reach tool invocations.
   - Recommendation: Validate during Phase 1. If kwargs don't flow through, use class-based tools (which are cleaner anyway).

2. **WorkflowAgent with AG-UI endpoint**
   - What we know: `WorkflowAgent(workflow, name)` wraps a workflow as an agent. `add_agent_framework_fastapi_endpoint` accepts any `AgentProtocol`.
   - What's unclear: Whether the AG-UI endpoint correctly streams events from a handoff workflow (which has multi-agent turns, handoff events, user input requests).
   - Recommendation: Phase 3 concern. Validate when building the handoff mesh. Phase 1 uses a simple `ChatAgent` which is known to work.

3. **Handoff + autonomous mode with AG-UI**
   - What we know: Handoff workflows can request user input (`request_info` events). Autonomous mode auto-responds for specified agents.
   - What's unclear: How AG-UI client handles `request_info` events. The mobile app would need to render these as prompts and send responses.
   - Recommendation: Phase 3 concern. For Phase 1, not relevant since there is only one agent.

### Deep Dive Sources

#### Primary (HIGH confidence)
- [Handoff Orchestration (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff) -- Complete HandoffBuilder API, Python code, context sync, autonomous mode, tool approval in handoffs. Updated 2026-02-13.
- [Function Tools (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools) -- `@tool` decorator, Annotated types, `**kwargs` injection, class-based tools, explicit schemas, declaration-only tools. Updated 2026-02-20.
- [Azure OpenAI Provider (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/agents/providers/azure-openai) -- Three client types (Chat/Responses/Assistants), `as_agent()` pattern, hosted tools, env var names. Updated 2026-02-13.
- [Agent Middleware (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/agents/middleware/) -- Three middleware types, registration patterns, class/function/decorator syntax, execution order, termination. Updated 2026-02-20.
- [Tools Overview (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/agents/tools/) -- Tool type matrix, provider support, agent-as-tool pattern. Updated 2026-02-13.
- [Providers Overview (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/agents/providers/) -- Agent type hierarchy, provider comparison table. Updated 2026-02-13.
- [AgentSession (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/agents/conversations/session) -- Session fields, multi-turn pattern, serialization. Updated 2026-02-20.
- [Agent Framework API Reference (Microsoft Learn)](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework) -- Full API: BaseAgent, ChatAgent, WorkflowAgent, HandoffBuilder, ai_function, middleware types, builders.
- [Your First Agent (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/get-started/your-first-agent) -- Basic agent creation, run/stream patterns. Updated 2026-02-20.

#### Observations (needs Phase 1 validation)
- AG-UI endpoint kwargs passthrough: Not documented. Needs empirical testing.
- WorkflowAgent + AG-UI: Logical but not explicitly shown. Needs Phase 3 validation.
- Handoff `request_info` events through AG-UI: Not documented. Phase 3 concern.

### Deep Dive Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Agent definitions (ChatAgent, as_agent) | HIGH | API reference + provider docs + quickstart all consistent |
| Tool registration (@tool, Annotated, **kwargs) | HIGH | Complete official tutorial with runnable examples |
| Handoff pattern (HandoffBuilder, routes, context sync) | HIGH | Comprehensive official docs with Python code |
| Dependency injection (class tools, **kwargs) | HIGH | Official tutorial explicitly demonstrates both patterns |
| Agent-as-tool pattern | HIGH | Official tools overview with code examples |
| Middleware (agent, function, chat) | HIGH | Official docs with class/function/decorator examples |
| WorkflowAgent + AG-UI integration | MEDIUM | API reference confirms WorkflowAgent exists, AG-UI endpoint accepts AgentProtocol, but integration not explicitly documented |
| Handoff + AG-UI streaming | LOW | Not documented. Needs Phase 3 validation. |

---

## AG-UI Protocol Deep Dive

**Added:** 2026-02-21
**Purpose:** Comprehensive reference for the AG-UI protocol as consumed by Agent Framework's `add_agent_framework_fastapi_endpoint()`. Critical for Phase 2 (mobile SSE client) and Phase 4 (HITL patterns). The Expo app has no CopilotKit equivalent -- a custom SSE consumer must be built.

### 1. Protocol Overview

AG-UI (Agent-User Interaction Protocol) is an open, lightweight, event-based protocol that standardizes how AI agents connect to user-facing applications. It is transport-agnostic (supports SSE, WebSockets, webhooks) but the standard HTTP transport uses **HTTP POST + Server-Sent Events (SSE)** for streaming responses.

**Key design principles:**
- **Event-driven:** All communication is broken into typed events with JSON payloads
- **Transport-agnostic:** Protocol defines events, not how they travel (SSE is the standard HTTP transport)
- **Bidirectional:** Agents accept input from users and emit event streams back
- **Minimal opinion:** Does not mandate UI rendering, state shape, or framework choice

**Current version:** `@ag-ui/core` v0.0.45 (npm). Protocol version 0.1.x. Pre-1.0 -- breaking changes possible.

**Confidence:** HIGH -- sourced from official AG-UI docs (docs.ag-ui.com) and `@ag-ui/core` npm package.

### 2. The HTTP Contract

#### Request: HTTP POST

The client sends an HTTP POST to the agent endpoint. The body is a JSON `RunAgentInput`:

```
POST / HTTP/1.1
Content-Type: application/json
Accept: text/event-stream
X-API-Key: <your-api-key>       (custom, from our auth middleware)

{
  "threadId": "thread-abc123",
  "runId": "run-xyz789",
  "messages": [
    {"id": "msg-1", "role": "user", "content": "What is in my inbox?"}
  ],
  "tools": [],
  "context": [],
  "state": {},
  "forwardedProps": {}
}
```

**RunAgentInput fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `threadId` | `string` | Yes | Conversation thread ID. Client provides this. Same thread across multiple requests = continuity. |
| `runId` | `string` | Yes | Unique ID for this specific run. Client generates a new one per request. |
| `parentRunId` | `string` | No | For branching/time-travel. References a prior run in the same thread. |
| `messages` | `Message[]` | Yes | Conversation history. Client maintains this and sends the full history each time. |
| `tools` | `Tool[]` | No | Frontend-defined tools the agent can call (for HITL patterns). Empty array for backend-only tools. |
| `context` | `Context[]` | No | Extra context objects (description + value pairs). |
| `state` | `any` | No | Current client-side state. Used for shared state / predictive state updates. |
| `forwardedProps` | `any` | No | Arbitrary properties forwarded to the agent. |
| `resume` | `object` | No | **DRAFT** -- For interrupt/resume pattern. Contains `interruptId` and `payload`. |

**IMPORTANT for Agent Framework:** When using `add_agent_framework_fastapi_endpoint()`, the endpoint accepts a simplified body. The framework handles the full `RunAgentInput` internally. The minimal curl body is:

```json
{
  "messages": [
    {"role": "user", "content": "Hello"}
  ]
}
```

The framework generates `threadId` and `runId` if not provided by the client. For conversation continuity, the client SHOULD provide `threadId`.

**Confidence:** HIGH -- verified from both AG-UI official docs (docs.ag-ui.com/sdk/js/core/types) and Agent Framework Getting Started curl example.

#### Response: Server-Sent Events (SSE)

The server responds with `Content-Type: text/event-stream`. Each event is a `data:` line containing a JSON object, followed by a blank line:

```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

data: {"type":"RUN_STARTED","threadId":"thread-abc123","runId":"run-xyz789"}

data: {"type":"TEXT_MESSAGE_START","messageId":"msg-asst-001","role":"assistant"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-asst-001","delta":"Hello"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-asst-001","delta":", how"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-asst-001","delta":" can I help?"}

data: {"type":"TEXT_MESSAGE_END","messageId":"msg-asst-001"}

data: {"type":"RUN_FINISHED","threadId":"thread-abc123","runId":"run-xyz789"}

```

**SSE format rules:**
- Each event is `data: {json}\n\n` (data line + blank line separator)
- No SSE `event:` field is used -- the event type is inside the JSON `type` field
- No SSE `id:` field is used -- message correlation uses `messageId`, `toolCallId`, `threadId`, `runId`
- Field names in JSON are **camelCase** (e.g., `threadId`, `runId`, `messageId`)
- Event type names are **UPPER_SNAKE_CASE** (e.g., `RUN_STARTED`, `TEXT_MESSAGE_CONTENT`)
- Connection closes after `RUN_FINISHED` or `RUN_ERROR` event
- Stream is one-directional: server to client. Client cannot send data mid-stream.

**Confidence:** HIGH -- verified from Agent Framework Getting Started tutorial (curl example showing exact SSE format) and AG-UI architecture docs.

#### Connection Lifecycle

```
1. Client opens HTTP POST connection
2. Server responds with 200 OK + Content-Type: text/event-stream
3. Server emits RUN_STARTED event
4. Server streams events (text messages, tool calls, state updates)
5. Server emits RUN_FINISHED or RUN_ERROR
6. Server closes the connection
7. Client processes final event and closes its end
```

**For multi-turn conversations:**
- Client opens a NEW HTTP POST for each user message
- Client includes the FULL conversation history in `messages[]`
- Server does NOT maintain conversation state between connections
- Thread continuity is achieved by the client sending the same `threadId` and full message history

This is fundamentally **stateless on the server side**. Each POST is independent. The client is the source of truth for conversation history.

### 3. Complete Event Type Reference

The AG-UI protocol defines 26 event types across 7 categories. Here is the complete list with payload shapes:

#### 3.1 Lifecycle Events (REQUIRED)

Every run MUST emit `RUN_STARTED` and either `RUN_FINISHED` or `RUN_ERROR`.

| Event Type | Key Fields | Description |
|------------|-----------|-------------|
| `RUN_STARTED` | `threadId`, `runId`, `parentRunId?`, `input?` | First event in every run. Establishes execution context. |
| `RUN_FINISHED` | `threadId`, `runId`, `result?`, `outcome?`, `interrupt?` | Successful completion (or interrupt, see HITL section). |
| `RUN_ERROR` | `message`, `code?` | Fatal error. Run terminates. No further events. |
| `STEP_STARTED` | `stepName` | Optional. Signals start of a named sub-task within a run. |
| `STEP_FINISHED` | `stepName` | Optional. Signals end of a named sub-task. |

**Payload shapes:**
```typescript
// RUN_STARTED
{
  type: "RUN_STARTED",
  threadId: string,       // conversation thread
  runId: string,          // this execution
  parentRunId?: string,   // for branching/time-travel
  input?: RunAgentInput,  // the request that started this run
  timestamp?: number
}

// RUN_FINISHED
{
  type: "RUN_FINISHED",
  threadId: string,
  runId: string,
  result?: any,           // final output data
  outcome?: "success" | "interrupt",  // DRAFT: for HITL
  interrupt?: {           // DRAFT: present when outcome === "interrupt"
    id?: string,
    reason?: string,
    payload?: any
  },
  timestamp?: number
}

// RUN_ERROR
{
  type: "RUN_ERROR",
  message: string,        // human-readable error
  code?: string,          // machine-readable error code
  timestamp?: number
}
```

#### 3.2 Text Message Events

Streamed token-by-token. Follow the Start -> Content* -> End pattern.

| Event Type | Key Fields | Description |
|------------|-----------|-------------|
| `TEXT_MESSAGE_START` | `messageId`, `role` | Start of assistant response. `role` is always `"assistant"`. |
| `TEXT_MESSAGE_CONTENT` | `messageId`, `delta` | One chunk of text. `delta` is a non-empty string. Concatenate in order. |
| `TEXT_MESSAGE_END` | `messageId` | Message complete. No more content for this `messageId`. |
| `TEXT_MESSAGE_CHUNK` | `messageId?`, `role?`, `delta?` | Convenience event. Auto-expands to Start/Content/End triad. |

**Payload shapes:**
```typescript
// TEXT_MESSAGE_START
{ type: "TEXT_MESSAGE_START", messageId: string, role: "assistant", timestamp?: number }

// TEXT_MESSAGE_CONTENT
{ type: "TEXT_MESSAGE_CONTENT", messageId: string, delta: string, timestamp?: number }

// TEXT_MESSAGE_END
{ type: "TEXT_MESSAGE_END", messageId: string, timestamp?: number }
```

#### 3.3 Tool Call Events

Streamed when the agent invokes a tool. Arguments are sent as JSON fragments.

| Event Type | Key Fields | Description |
|------------|-----------|-------------|
| `TOOL_CALL_START` | `toolCallId`, `toolCallName`, `parentMessageId?` | Agent begins calling a tool. |
| `TOOL_CALL_ARGS` | `toolCallId`, `delta` | JSON fragment of tool arguments. Concatenate all deltas to get complete JSON. |
| `TOOL_CALL_END` | `toolCallId` | All arguments sent. Tool execution begins (or has completed). |
| `TOOL_CALL_RESULT` | `messageId`, `toolCallId`, `content`, `role?` | Result of tool execution. `content` is a string. |
| `TOOL_CALL_CHUNK` | `toolCallId?`, `toolCallName?`, `parentMessageId?`, `delta?` | Convenience event. Auto-expands to Start/Args/End triad. |

**Payload shapes:**
```typescript
// TOOL_CALL_START
{
  type: "TOOL_CALL_START",
  toolCallId: string,      // unique ID for this tool invocation
  toolCallName: string,    // name of the tool being called
  parentMessageId?: string // links to the assistant message that triggered it
}

// TOOL_CALL_ARGS
{
  type: "TOOL_CALL_ARGS",
  toolCallId: string,
  delta: string            // JSON fragment, e.g. '{"locat' ... 'ion":"Paris"}'
}

// TOOL_CALL_END
{ type: "TOOL_CALL_END", toolCallId: string }

// TOOL_CALL_RESULT
{
  type: "TOOL_CALL_RESULT",
  messageId: string,       // message ID for this result in the conversation
  toolCallId: string,      // links back to the TOOL_CALL_START
  content: string,         // the tool's return value as a string
  role?: "tool"
}
```

**Complete tool call flow example:**
```
data: {"type":"TOOL_CALL_START","toolCallId":"call_abc","toolCallName":"get_weather"}
data: {"type":"TOOL_CALL_ARGS","toolCallId":"call_abc","delta":"{\"location\":\"Paris\"}"}
data: {"type":"TOOL_CALL_END","toolCallId":"call_abc"}
data: {"type":"TOOL_CALL_RESULT","messageId":"msg-tool-1","toolCallId":"call_abc","content":"Sunny, 22C"}
```

#### 3.4 State Management Events

For synchronizing shared state between agent and client. Uses JSON Patch (RFC 6902) for deltas.

| Event Type | Key Fields | Description |
|------------|-----------|-------------|
| `STATE_SNAPSHOT` | `snapshot` | Complete state replacement. Client should overwrite its state. |
| `STATE_DELTA` | `delta` | Array of JSON Patch operations (RFC 6902). Apply incrementally. |
| `MESSAGES_SNAPSHOT` | `messages` | Complete conversation history snapshot. |

**Payload shapes:**
```typescript
// STATE_SNAPSHOT
{ type: "STATE_SNAPSHOT", snapshot: any }

// STATE_DELTA -- uses RFC 6902 JSON Patch
{ type: "STATE_DELTA", delta: [{ op: "add", path: "/foo", value: 1 }, ...] }

// MESSAGES_SNAPSHOT
{ type: "MESSAGES_SNAPSHOT", messages: Message[] }
```

#### 3.5 Activity Events

For structured progress updates (e.g., "searching...", "planning...").

| Event Type | Key Fields | Description |
|------------|-----------|-------------|
| `ACTIVITY_SNAPSHOT` | `messageId`, `activityType`, `content`, `replace?` | Complete activity state. `activityType` is a discriminator like `"PLAN"` or `"SEARCH"`. |
| `ACTIVITY_DELTA` | `messageId`, `activityType`, `patch` | JSON Patch operations on the activity content. |

#### 3.6 Reasoning Events

For exposing agent chain-of-thought. Replaces deprecated `THINKING_*` events.

| Event Type | Key Fields | Description |
|------------|-----------|-------------|
| `REASONING_START` | `messageId` | Start of reasoning phase. Pass-through signal. |
| `REASONING_MESSAGE_START` | `messageId`, `role` | Start of a reasoning message. Creates `ReasoningMessage` in history. |
| `REASONING_MESSAGE_CONTENT` | `messageId`, `delta` | Reasoning text chunk. |
| `REASONING_MESSAGE_END` | `messageId` | End of reasoning message. |
| `REASONING_MESSAGE_CHUNK` | `messageId?`, `delta?` | Convenience event, auto-expands to Start/Content/End. |
| `REASONING_END` | `messageId` | End of reasoning phase. |
| `REASONING_ENCRYPTED_VALUE` | `subtype`, `entityId`, `encryptedValue` | Encrypted chain-of-thought for state carry-over across turns. |

#### 3.7 Special Events

| Event Type | Key Fields | Description |
|------------|-----------|-------------|
| `RAW` | `event`, `source?` | Passthrough for external system events. |
| `CUSTOM` | `name`, `value` | Application-specific custom events. |

#### 3.8 Deprecated Events (do NOT implement)

| Deprecated | Replacement |
|------------|-------------|
| `THINKING_START` | `REASONING_START` |
| `THINKING_END` | `REASONING_END` |
| `THINKING_TEXT_MESSAGE_START` | `REASONING_MESSAGE_START` |
| `THINKING_TEXT_MESSAGE_CONTENT` | `REASONING_MESSAGE_CONTENT` |
| `THINKING_TEXT_MESSAGE_END` | `REASONING_MESSAGE_END` |

**Confidence:** HIGH -- all event types and payload shapes sourced from official AG-UI docs (docs.ag-ui.com/sdk/js/core/events and docs.ag-ui.com/concepts/events).

### 4. Which Events Does Agent Framework Actually Emit?

Agent Framework's `add_agent_framework_fastapi_endpoint()` uses an internal `AgentFrameworkEventBridge` to translate Agent Framework internal events to AG-UI events. Based on the official documentation and Getting Started tutorial, here is what the bridge emits:

#### Events Agent Framework Definitely Emits

| AG-UI Event | Agent Framework Source | When |
|-------------|----------------------|------|
| `RUN_STARTED` | Run begins | Always first. Bridge generates `threadId` and `runId`. |
| `TEXT_MESSAGE_START` | Agent begins generating text response | Start of each assistant message. |
| `TEXT_MESSAGE_CONTENT` | Streaming tokens from LLM | Each token/chunk from Azure OpenAI. `delta` contains the token text. |
| `TEXT_MESSAGE_END` | Agent finishes text response | After all tokens for a message. |
| `TOOL_CALL_START` | Agent decides to call a `@tool` function | Includes `toolCallName` matching the Python function name. |
| `TOOL_CALL_ARGS` | LLM streams function arguments | JSON fragments of the tool arguments. |
| `TOOL_CALL_END` | Arguments complete | Tool is about to execute (or just executed). |
| `TOOL_CALL_RESULT` | Tool function returns a value | `content` is the string return value from the `@tool` function. |
| `RUN_FINISHED` | Run completes successfully | Always last on success. |
| `RUN_ERROR` | Unhandled exception during run | Replaces `RUN_FINISHED` on failure. |

#### Events Agent Framework May Emit (Situational)

| AG-UI Event | When | Notes |
|-------------|------|-------|
| `STEP_STARTED` / `STEP_FINISHED` | During handoff workflow steps | When using `WorkflowAgent` with `HandoffBuilder`. Each agent transition may emit step events. Needs Phase 3 validation. |
| `STATE_SNAPSHOT` | When using shared state orchestrator | The AG-UI overview mentions "Shared State" as a supported feature. Requires explicit state configuration. |

#### Events Agent Framework Does NOT Emit (Client-Side / Future)

| AG-UI Event | Why Not |
|-------------|---------|
| `STATE_DELTA` | No incremental state updates from Agent Framework. State snapshots only if configured. |
| `MESSAGES_SNAPSHOT` | Agent Framework does not send message history snapshots -- client maintains history. |
| `ACTIVITY_SNAPSHOT` / `ACTIVITY_DELTA` | Activity events are for custom progress UIs. Not part of standard Agent Framework flow. |
| `REASONING_*` events | Would require extended thinking / chain-of-thought model support. Not emitted by standard Azure OpenAI Chat Completions. |
| `RAW` / `CUSTOM` | For application-specific extensions. Not emitted by default. |
| `TEXT_MESSAGE_CHUNK` / `TOOL_CALL_CHUNK` | Convenience events -- Agent Framework emits the explicit Start/Content/End triad instead. |

**Confidence:** HIGH for the "Definitely Emits" list (verified from Getting Started curl output and backend tool rendering tutorial). MEDIUM for "May Emit" (documented as supported features but not shown in basic examples). HIGH for "Does NOT Emit" (these are client-side or extension features not relevant to the bridge).

### 5. Thread Management

#### How Thread IDs Work

Thread IDs provide conversation continuity. The key insight: **AG-UI is stateless on the server side.** The client is the source of truth.

**Who provides the thread ID?**
- The **client** provides `threadId` in the POST body
- If the client omits `threadId`, Agent Framework generates one and returns it in `RUN_STARTED`
- For conversation continuity, the client MUST capture `threadId` from `RUN_STARTED` and send it in subsequent requests

**Thread lifecycle:**

```
Request 1 (new conversation):
  Client sends: { "messages": [{"role": "user", "content": "Hello"}] }
  Server responds: RUN_STARTED { threadId: "thread-abc", runId: "run-1" }
  Client captures threadId = "thread-abc"

Request 2 (continuation):
  Client sends: {
    "threadId": "thread-abc",
    "messages": [
      {"role": "user", "content": "Hello"},
      {"role": "assistant", "content": "Hi! How can I help?"},
      {"role": "user", "content": "What is in my inbox?"}
    ]
  }
  Server responds: RUN_STARTED { threadId: "thread-abc", runId: "run-2" }
```

**Critical detail:** The client sends the ENTIRE conversation history in `messages[]` on every request. The server does not store conversation state between requests. This means:

1. **Mobile app must maintain the message array** -- accumulate user messages + assistant responses
2. **Thread ID is just a correlation ID** -- it does not cause the server to look up stored history
3. **Agent Framework `AgentSession`** provides in-process session state, but the AG-UI bridge reconstructs context from the incoming messages array

**Relationship between AG-UI threads and Agent Framework sessions:**
- AG-UI `threadId` maps to Agent Framework's `ConversationId` concept
- Each HTTP POST creates a new Agent Framework session internally
- The session is populated with the messages from the POST body
- After the response streams, the session is discarded
- There is no persistent server-side session store in the AG-UI pattern

**Confidence:** HIGH -- verified from Getting Started tutorial (client manages message history, sends full array each time) and AG-UI architecture overview (stateless server pattern).

### 6. HITL / Interrupt Pattern

#### Current Status: DRAFT Proposal

The interrupt-aware run lifecycle is a **draft proposal** in the AG-UI protocol (docs.ag-ui.com/drafts/interrupts). It is NOT yet part of the stable specification. However, Agent Framework lists "Human in the Loop" as a supported AG-UI feature, and the `@tool(approval_mode="always_require")` decorator exists.

#### How It Works (Draft Spec)

The interrupt pattern uses `RUN_FINISHED` with a special `outcome` field:

**Step 1: Agent encounters an action requiring approval**

The agent calls a tool marked with `approval_mode="always_require"`. Instead of executing immediately, the framework emits a `RUN_FINISHED` event with `outcome: "interrupt"`:

```json
{
  "type": "RUN_FINISHED",
  "threadId": "thread-abc",
  "runId": "run-1",
  "outcome": "interrupt",
  "interrupt": {
    "id": "int-xyz",
    "reason": "human_approval",
    "payload": {
      "proposal": {
        "tool": "delete_document",
        "args": {"container_name": "Inbox", "document_id": "doc-123"}
      }
    }
  }
}
```

**Step 2: Client presents approval UI to user**

The mobile app receives the `RUN_FINISHED` event, checks for `outcome === "interrupt"`, and renders an approval dialog showing the proposed action.

**Step 3: User approves or rejects**

The client sends a new POST request with a `resume` field:

```json
{
  "threadId": "thread-abc",
  "runId": "run-2",
  "messages": [...],
  "resume": {
    "interruptId": "int-xyz",
    "payload": {"approved": true}
  }
}
```

**Step 4: Agent continues or aborts**

If approved, the agent executes the tool and continues. If rejected, the agent acknowledges and moves on.

#### Agent Framework's HITL Implementation

Agent Framework supports HITL through two mechanisms:

1. **`@tool(approval_mode="always_require")`** -- marks a tool for approval before execution
2. **AG-UI orchestrator middleware** -- the `AgentFrameworkAgent` wrapper handles the approval protocol

The AG-UI integration page lists these as supported:
- "Human-in-the-Loop: Function approval requests for user confirmation"
- "ApprovalRequiredAIFunction: Middleware converts to approval protocol"

**How this maps to AG-UI events for the mobile client:**

| Step | Server Emits | Client Action |
|------|-------------|---------------|
| Agent wants to call approved tool | `TOOL_CALL_START` + `TOOL_CALL_ARGS` + `TOOL_CALL_END` (showing what will be called) | Display "Agent wants to call X with args Y" |
| Framework pauses for approval | `RUN_FINISHED` with `outcome: "interrupt"` | Show approval dialog |
| User approves | -- | Send new POST with `resume: { approved: true }` |
| Agent executes tool | `TOOL_CALL_RESULT` in new run | Display result |

**Important caveat:** The exact wire format for Agent Framework's HITL through AG-UI is not fully documented for the Python SDK. The draft interrupt proposal is the latest specification. The implementation may use frontend-defined tools (where the client implements the approval tool) rather than the interrupt pattern. Both approaches achieve the same goal.

**Alternative HITL approach (frontend tools):** AG-UI also supports defining tools on the frontend that the agent can call. For approval workflows:

1. Client defines a `confirmAction` tool in the `tools[]` array of the POST body
2. Agent calls this frontend tool when it needs approval
3. Client receives `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END` events
4. Client executes the tool (shows dialog, gets user input)
5. Client sends a new POST with the tool result in messages

This is the CopilotKit pattern (`useCopilotAction`) adapted for a custom client.

**Confidence:** MEDIUM -- interrupt draft is well-specified but explicitly marked as "Draft" and "subject to change." Agent Framework claims HITL support but the exact Python AG-UI wire format is not documented. The mobile client should be designed to handle BOTH the interrupt pattern and the frontend-tool pattern.

### 7. Serialization and Event Compaction

AG-UI supports serializing event streams for persistence and replay. Key concepts for the mobile app:

- **Event compaction** -- `compactEvents()` merges verbose streams into snapshots (e.g., merge `TEXT_MESSAGE_START` + `TEXT_MESSAGE_CONTENT*` + `TEXT_MESSAGE_END` into a single `MESSAGES_SNAPSHOT`)
- **Run lineage** -- `parentRunId` creates git-like branching for conversation time-travel
- **Stream persistence** -- Store events as JSON arrays, restore later

**Relevance to mobile app:** The Expo app should store compacted conversation history locally (AsyncStorage or SQLite) to avoid re-fetching. On reconnect, send the compacted messages array in the next POST.

### 8. What the Mobile SSE Client Must Handle

Given no CopilotKit for React Native, the Expo app needs a custom SSE consumer. Here is the minimum viable specification:

#### 8.1 SSE Parsing Requirements

The client must:

1. **Open an HTTP POST connection** with `Content-Type: application/json` and `Accept: text/event-stream`
2. **Read the response as a stream** of `data: {json}\n\n` lines
3. **Parse each `data:` line** as JSON
4. **Dispatch on the `type` field** to handle different event types
5. **Handle connection close** after `RUN_FINISHED` or `RUN_ERROR`
6. **Handle network errors** (timeout, disconnect) gracefully

#### 8.2 Minimum Event Set to Handle

For Phase 2, the mobile client MUST handle these events:

| Event | Client Action |
|-------|---------------|
| `RUN_STARTED` | Capture `threadId` and `runId`. Show loading indicator. |
| `TEXT_MESSAGE_START` | Create a new assistant message bubble. Begin rendering. |
| `TEXT_MESSAGE_CONTENT` | Append `delta` text to the current message. Real-time token display. |
| `TEXT_MESSAGE_END` | Finalize message. Remove loading indicator for this message. |
| `TOOL_CALL_START` | Optionally show "Agent is calling [toolCallName]..." indicator. |
| `TOOL_CALL_ARGS` | Optionally accumulate tool arguments for display. |
| `TOOL_CALL_END` | Optionally show "Tool call complete, waiting for result..." |
| `TOOL_CALL_RESULT` | Optionally display tool result in UI. |
| `RUN_FINISHED` | Mark run complete. Enable user input. |
| `RUN_ERROR` | Display error message. Enable user input. Allow retry. |

**Events to ignore initially (Phase 2 can skip):**
- `STEP_STARTED` / `STEP_FINISHED` -- nice-to-have progress indicators
- `STATE_SNAPSHOT` / `STATE_DELTA` -- no shared state needed initially
- `MESSAGES_SNAPSHOT` -- client manages messages locally
- `ACTIVITY_SNAPSHOT` / `ACTIVITY_DELTA` -- no activity UI in Phase 2
- `REASONING_*` -- no reasoning display in Phase 2
- `RAW` / `CUSTOM` -- no custom events in Phase 2

**Events for Phase 4 (HITL):**
- `RUN_FINISHED` with `outcome: "interrupt"` -- trigger approval dialog
- Frontend tool calls via `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END`

#### 8.3 React Native SSE Implementation Approaches

**Option A: `EventSource` polyfill (simplest)**

React Native does not natively support `EventSource` for POST requests. Use a library:

```typescript
// react-native-sse or expo-server-sent-events
// These handle the SSE parsing layer

import EventSource from 'react-native-sse';

const es = new EventSource('http://backend:8000/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey,
  },
  body: JSON.stringify({
    threadId: threadId,
    messages: messageHistory,
  }),
});

es.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case 'TEXT_MESSAGE_CONTENT':
      appendToCurrentMessage(data.delta);
      break;
    case 'RUN_FINISHED':
      completeRun();
      es.close();
      break;
    // ... handle other event types
  }
});
```

**Option B: `fetch()` with streaming reader (more control)**

```typescript
const response = await fetch('http://backend:8000/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
    'X-API-Key': apiKey,
  },
  body: JSON.stringify({ threadId, messages: messageHistory }),
});

const reader = response.body?.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (reader) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });

  // Parse SSE data lines
  const lines = buffer.split('\n');
  buffer = lines.pop() || ''; // Keep incomplete line in buffer

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const json = line.slice(6); // Remove 'data: ' prefix
      if (json.trim()) {
        const event = JSON.parse(json);
        handleAgUiEvent(event);
      }
    }
  }
}
```

**Recommendation for Phase 2:** Use Option B (`fetch` with streaming reader). It gives full control over the connection, does not require an EventSource polyfill that may not support POST bodies, and works well with React Native's `fetch` implementation. The parsing logic is ~20 lines of code.

**Confidence:** MEDIUM -- React Native SSE support varies by version and platform. The `fetch` streaming approach is more reliable. Both approaches need validation on actual device. The `react-native-sse` library supports POST but has fewer downloads. Need to test with Expo SDK during Phase 2.

#### 8.4 Client-Side State Management

The mobile client must maintain:

1. **Message history array** -- `Message[]` accumulating user + assistant + tool messages
2. **Current thread ID** -- captured from first `RUN_STARTED`, reused across requests
3. **Current run state** -- `idle | running | error` for UI state
4. **Streaming message buffer** -- accumulate `TEXT_MESSAGE_CONTENT` deltas for the current message
5. **Tool call tracking** -- map of `toolCallId -> { name, args, result }` for display

**Suggested Zustand store shape (Phase 2):**
```typescript
interface ChatState {
  threadId: string | null;
  messages: Message[];
  isRunning: boolean;
  error: string | null;
  currentStreamingMessage: string;
  pendingToolCalls: Map<string, ToolCallState>;

  // Actions
  sendMessage: (content: string) => Promise<void>;
  handleEvent: (event: AgUiEvent) => void;
  reset: () => void;
}
```

### 9. Complete SSE Stream Examples

#### Example 1: Simple Text Response

```
POST / HTTP/1.1
Content-Type: application/json

{"messages":[{"role":"user","content":"Hello"}]}

---

data: {"type":"RUN_STARTED","threadId":"t1","runId":"r1"}

data: {"type":"TEXT_MESSAGE_START","messageId":"m1","role":"assistant"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m1","delta":"Hello"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m1","delta":"! How"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m1","delta":" can I help you?"}

data: {"type":"TEXT_MESSAGE_END","messageId":"m1"}

data: {"type":"RUN_FINISHED","threadId":"t1","runId":"r1"}

```

#### Example 2: Tool Call + Text Response

```
data: {"type":"RUN_STARTED","threadId":"t1","runId":"r2"}

data: {"type":"TOOL_CALL_START","toolCallId":"tc1","toolCallName":"read_inbox"}

data: {"type":"TOOL_CALL_ARGS","toolCallId":"tc1","delta":"{}"}

data: {"type":"TOOL_CALL_END","toolCallId":"tc1"}

data: {"type":"TOOL_CALL_RESULT","messageId":"tr1","toolCallId":"tc1","content":"[{\"title\":\"Buy groceries\"}]"}

data: {"type":"TEXT_MESSAGE_START","messageId":"m2","role":"assistant"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m2","delta":"You have 1 item"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m2","delta":" in your inbox: Buy groceries."}

data: {"type":"TEXT_MESSAGE_END","messageId":"m2"}

data: {"type":"RUN_FINISHED","threadId":"t1","runId":"r2"}

```

#### Example 3: Interrupt (HITL Approval) -- DRAFT

```
data: {"type":"RUN_STARTED","threadId":"t1","runId":"r3"}

data: {"type":"TOOL_CALL_START","toolCallId":"tc2","toolCallName":"delete_document"}

data: {"type":"TOOL_CALL_ARGS","toolCallId":"tc2","delta":"{\"container\":\"Inbox\",\"id\":\"doc-123\"}"}

data: {"type":"TOOL_CALL_END","toolCallId":"tc2"}

data: {"type":"RUN_FINISHED","threadId":"t1","runId":"r3","outcome":"interrupt","interrupt":{"id":"int-1","reason":"human_approval","payload":{"tool":"delete_document","args":{"container":"Inbox","id":"doc-123"}}}}

```

Client then sends a resume POST:

```
POST / HTTP/1.1
Content-Type: application/json

{"threadId":"t1","runId":"r4","messages":[...],"resume":{"interruptId":"int-1","payload":{"approved":true}}}
```

### 10. Deep Dive Open Questions

1. **Agent Framework's exact HITL wire format**
   - What we know: AG-UI interrupt draft is specified. Agent Framework claims HITL support. `@tool(approval_mode="always_require")` exists.
   - What's unclear: Does Agent Framework's Python AG-UI bridge emit `RUN_FINISHED` with `outcome: "interrupt"`, or does it use the frontend-tool pattern? The Getting Started and Backend Tool Rendering tutorials don't show HITL.
   - Recommendation: Design the mobile client to handle BOTH patterns. Test during Phase 4 implementation.

2. **React Native SSE support for POST requests**
   - What we know: Standard `EventSource` API does not support POST. React Native's `fetch` supports streaming.
   - What's unclear: Exact behavior of `response.body.getReader()` in Expo/React Native on iOS and Android. Some older Expo versions may not support ReadableStream.
   - Recommendation: Validate during Phase 2 with a simple POC. Fallback is `XMLHttpRequest` with `onprogress` handler.

3. **Message history size limits**
   - What we know: Each POST includes full message history. Azure OpenAI has token limits.
   - What's unclear: Does Agent Framework truncate messages, or does the client need to manage context window?
   - Recommendation: Implement client-side message truncation (keep last N messages + system prompt). Agent Framework likely passes messages through to Azure OpenAI which will error on token limit exceeded.

4. **Thread ID persistence across app restarts**
   - What we know: Thread ID is just a string correlation ID. No server-side state.
   - What's unclear: Should the mobile app persist `threadId` + message history to AsyncStorage for session continuity across app restarts?
   - Recommendation: Yes. Store `{ threadId, messages }` in Expo SecureStore or AsyncStorage. Restore on app launch.

5. **Concurrent requests on same thread**
   - What we know: Each POST is independent. Server does not lock threads.
   - What's unclear: What happens if the user sends a new message while a previous run is still streaming? Does the server handle concurrent runs on the same thread?
   - Recommendation: Disable the send button while a run is in progress (`isRunning` state). Queue messages if needed.

### Deep Dive Sources

#### Primary (HIGH confidence)
- [AG-UI Events Reference (docs.ag-ui.com)](https://docs.ag-ui.com/concepts/events) -- Complete event type documentation with mermaid sequence diagrams, all 26 event types, payload descriptions.
- [AG-UI SDK Events (docs.ag-ui.com)](https://docs.ag-ui.com/sdk/js/core/events) -- TypeScript type definitions for all events with exact field types and validation schemas (Zod).
- [AG-UI Core Types (docs.ag-ui.com)](https://docs.ag-ui.com/sdk/js/core/types) -- `RunAgentInput`, `Message`, `Tool`, `Context`, `State` type definitions.
- [AG-UI Core Architecture (docs.ag-ui.com)](https://docs.ag-ui.com/concepts/architecture) -- Design principles, transport options, architectural overview, HttpAgent client.
- [AG-UI Serialization (docs.ag-ui.com)](https://docs.ag-ui.com/concepts/serialization) -- Event compaction, branching with `parentRunId`, stream persistence patterns.
- [AG-UI Tools (docs.ag-ui.com)](https://docs.ag-ui.com/concepts/tools) -- Frontend-defined tools, tool call lifecycle, HITL via tools, CopilotKit integration.
- [Agent Framework AG-UI Integration (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/) -- Feature list, architecture diagram, event mapping table, supported features (7 AG-UI features). Updated 2026-02-13.
- [Agent Framework AG-UI Getting Started (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/getting-started) -- Server setup, client setup, curl testing, SSE format, thread management, protocol details. Updated 2026-02-13.
- [Agent Framework AG-UI Backend Tool Rendering (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/backend-tool-rendering) -- Tool event sequences (`TOOL_CALL_START` through `TOOL_CALL_RESULT`), Python examples. Updated 2026-02-13.

#### Secondary (MEDIUM confidence)
- [AG-UI Interrupt Draft Proposal (docs.ag-ui.com)](https://docs.ag-ui.com/drafts/interrupts) -- `RUN_FINISHED` with `outcome: "interrupt"`, `RunAgentInput.resume` field, contract rules, implementation examples. Status: Draft.
- [CopilotKit AG-UI Blog (copilotkit.ai)](https://www.copilotkit.ai/blog/master-the-17-ag-ui-event-types-for-building-agents-the-right-way) -- Practical walkthrough of all event types with diagrams. Counts 17 events (pre-Reasoning events addition).
- [@ag-ui/core npm package](https://npmjs.com/package/@ag-ui/core) -- v0.0.45, 323K weekly downloads, confirms 16 core event kinds in current release.

#### Tertiary (LOW confidence)
- React Native SSE support: No official AG-UI documentation for React Native. SSE POST support depends on Expo version and platform. Needs Phase 2 validation.
- Agent Framework HITL wire format via AG-UI: Claimed as supported but no Python example showing the interrupt flow end-to-end. Needs Phase 4 validation.

### Deep Dive Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Event type list and payload shapes | HIGH | Official AG-UI TypeScript types + Zod schemas verified |
| HTTP contract (POST body, SSE format) | HIGH | Official docs + Agent Framework curl example match |
| Thread management lifecycle | HIGH | Stateless server pattern verified from multiple sources |
| Agent Framework event mapping | HIGH | Getting Started tutorial + backend tool rendering show exact events |
| HITL / Interrupt pattern | MEDIUM | Draft proposal well-specified but not yet stable. Agent Framework claims support but wire format undocumented for Python. |
| Mobile SSE client requirements | MEDIUM | Event parsing is well-defined. React Native SSE transport needs device validation. |
| State management events | MEDIUM | Well-specified in protocol but Agent Framework does not emit them in basic scenarios. |

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (AG-UI protocol is pre-1.0, may change. Interrupt proposal is Draft status.)
