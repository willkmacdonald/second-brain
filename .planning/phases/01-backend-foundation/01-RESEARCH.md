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
