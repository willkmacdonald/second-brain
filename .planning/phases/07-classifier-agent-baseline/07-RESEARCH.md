# Phase 7: Classifier Agent Baseline - Research

**Researched:** 2026-02-26
**Domain:** Azure AI Foundry Agent Service -- persistent agent registration, @tool function execution, middleware, gpt-4o-transcribe, integration testing
**Confidence:** HIGH

## Summary

Phase 7 migrates the Classifier from the old `AzureOpenAIChatClient.as_agent()` pattern to a persistent Foundry-registered agent using `AzureAIAgentClient`. The agent is registered once at startup (or loaded by stored ID), persists across restarts, and executes local Python `@tool` functions (`file_capture`, `transcribe_audio`) in-process. The Foundry service handles thread management, message routing, and model inference; tool execution happens locally via the SDK callback mechanism.

The `agent-framework-azure-ai` SDK (1.0.0rc2+) provides the exact pattern needed: `AzureAIAgentClient(credential=..., agent_id=<id>).as_agent(tools=[...], middleware=[...])` loads an existing Foundry agent by ID and attaches local tools and middleware. The `should_cleanup_agent=False` flag prevents the SDK from deleting the agent when the client closes. Middleware is registered via the `middleware=[]` parameter on `as_agent()` / `create_agent()`, supporting both class-based (`AgentMiddleware`, `FunctionMiddleware`) and function-based patterns.

For `transcribe_audio`, the `gpt-4o-transcribe` model uses the standard OpenAI Audio Transcriptions API (`client.audio.transcriptions.create(model="gpt-4o-transcribe", file=...)`) -- the same endpoint shape as Whisper but with a different model name. The tool downloads audio from Blob Storage, calls the transcription API via `AsyncAzureOpenAI`, and returns the transcript text. This is a separate API call from the Foundry agent pipeline, made directly by the tool function.

**Primary recommendation:** Use `AzureAIAgentClient` with `agent_id` and `should_cleanup_agent=False` for persistent agent lifecycle. Register the agent via the underlying `agents_client` at startup if the stored ID is missing. Wire `file_capture` and `transcribe_audio` as `@tool` functions with `approval_mode="never_require"`. Use class-based `AgentMiddleware` and `FunctionMiddleware` for audit logging and tool timing.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Tool behavior:**
- Rename `classify_and_file` to `file_capture` -- the agent does classification reasoning, the tool is a Cosmos DB write helper
- Agent calls `file_capture(text, bucket, confidence, status)` with the classification result it determined
- `file_capture` returns a structured dict: `{"bucket": "Ideas", "confidence": 0.85, "item_id": "..."}` on success
- On failure (Cosmos write error, transcription failure), tools return an error dict `{"error": "...", "detail": "..."}` -- no exceptions raised
- `transcribe_audio` returns just the transcript text string -- no metadata
- Voice captures use two separate tool calls: `transcribe_audio` first, agent reads transcript and reasons, then `file_capture`
- Confidence threshold: 0.6 -- same as v1 (>= 0.6 auto-files, < 0.6 goes pending)

**Agent instructions:**
- Three outcomes: classified (high confidence), pending (low confidence), misunderstood (can't parse OR junk -- unified, no separate junk status)
- Detailed bucket definitions with boundaries, edge cases, and overlap rules for each of the four buckets (Admin, Ideas, People, Projects)
- Multi-bucket edge cases: agent picks strongest match -- no priority hierarchy
- Port refined v1 decision logic for misunderstood detection (from 04.3-10) -- junk and can't-parse are the same outcome
- Misunderstood items are filed via `file_capture` with `status=misunderstood` -- conversational follow-up wired in Phase 9
- Light persona framing ("You are Will's second brain classifier") followed by functional classification rules
- Foundry portal is the source of truth for instructions -- no local reference copy in repo
- Instructions editable in AI Foundry portal without redeployment

**Middleware & logging:**
- Standard detail: agent run start/end, tool calls with timing, tool retry counts
- Token usage tracking deferred to Phase 9 (Observability)
- Logs go to both Python logging (console/stdout) AND Application Insights from the start
- Tool failures logged at WARNING level -- ERROR reserved for app-level issues
- Use Foundry's built-in thread/run IDs for correlation -- no custom run_id
- Log classification result as structured fields (bucket, confidence, status) -- queryable in AppInsights

**Registration & lifecycle:**
- Agent registered at app startup -- self-healing (creates if missing)
- Check stored `AZURE_AI_CLASSIFIER_AGENT_ID` first; if valid in Foundry, use it. Only create if missing -- idempotent
- If agent registration fails at startup, app fails to start (hard dependency)
- Validation via pytest integration test: creates thread, sends message, asserts Cosmos result

### Claude's Discretion

- Tool parameter design (separate params vs grouped object for file_capture)
- Whether to store original voice transcript alongside classified text in Cosmos
- Exact middleware implementation (decorator vs class vs hook pattern)
- Compression/format of structured AppInsights custom dimensions
- Agent instruction wording and prompt engineering for classification accuracy

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AGNT-01 | Classifier agent registered as a persistent Foundry agent with stable ID visible in AI Foundry portal | `AzureAIAgentClient` with `agent_id` loads existing agent; underlying `agents_client.create_agent()` registers new agents. `should_cleanup_agent=False` prevents deletion on shutdown. Agent is visible in Foundry portal by name and ID. |
| AGNT-02 | Classifier agent executes in-process Python `@tool` functions (`file_capture`, `transcribe_audio`) through Foundry callback mechanism with results written to Cosmos DB | Tools passed via `tools=[file_capture, transcribe_audio]` to `as_agent()` / `create_agent()`. SDK auto-invokes local tools when the Foundry service requests them during `agent.run()`. The `@tool(approval_mode="never_require")` decorator prevents approval prompts. |
| AGNT-03 | `AzureAIAgentClient` with `should_cleanup_agent=False` manages agent lifecycle -- agent persists across Container App restarts | `should_cleanup_agent` defaults to `True`; set to `False` to prevent cleanup on `close()`. Agent ID stored in `AZURE_AI_CLASSIFIER_AGENT_ID` env var. Existing agents passed via `agent_id` are never deleted regardless of this flag. |
| AGNT-05 | `transcribe_audio` is a `@tool` callable by the Classifier agent, using `gpt-4o-transcribe` via `AsyncAzureOpenAI` (replaces Whisper) | `gpt-4o-transcribe` uses the standard Audio Transcriptions API: `client.audio.transcriptions.create(model="gpt-4o-transcribe", file=audio_file)`. Endpoint: `POST /openai/deployments/{deployment-id}/audio/transcriptions`. API version: `2025-04-01-preview`. The tool makes a direct `AsyncAzureOpenAI` call, separate from the Foundry agent pipeline. |
| AGNT-06 | Agent middleware wired: `AgentMiddleware` for audit logging, `FunctionMiddleware` for tool validation/timing | Middleware registered via `middleware=[AuditMiddleware(), ToolTimingMiddleware()]` on `as_agent()` / `create_agent()`. `AgentMiddleware` subclass gets `AgentContext` with `agent`, `messages`, `metadata`. `FunctionMiddleware` subclass gets `FunctionInvocationContext` with `function.name`, `arguments`, `result`. |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `agent-framework-azure-ai` | `1.0.0rc2+` (install `--pre`) | `AzureAIAgentClient` for persistent Foundry agent creation and loading | Already installed in Phase 6; provides `as_agent()`, `create_agent()`, `should_cleanup_agent`, middleware support |
| `agent-framework` (core) | `>=1.0.0rc2` (transitive) | `@tool`, `AgentMiddleware`, `FunctionMiddleware`, `AgentContext`, `FunctionInvocationContext` | Core framework types; middleware and tool decorators |
| `azure-ai-agents` | `==1.2.0b5` (pinned by agent-framework-azure-ai) | Lower-level `AgentsClient` for `create_agent()`, `list_agents()`, thread management | Used at startup for agent registration when the SDK's higher-level API doesn't cover "create-if-missing" |
| `openai` | existing (transitive via azure-ai-agents) | `AsyncAzureOpenAI` for `audio.transcriptions.create()` with `gpt-4o-transcribe` | Standard client for Azure OpenAI API calls; async version for FastAPI context |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `azure-storage-blob` | existing | Download voice recordings from Blob Storage before transcription | Used by `transcribe_audio` tool to fetch audio bytes from blob URL |
| `azure-monitor-opentelemetry` | `>=1.8.6` (existing) | `configure_azure_monitor()` for Application Insights traces | Already configured in Phase 6; middleware logs flow to AppInsights via Python logging integration |
| `pydantic` | existing (via pydantic-settings) | `Field` for tool parameter descriptions with `Annotated` | Tool parameters use `Annotated[str, Field(description="...")]` pattern |

### No New Dependencies

Phase 7 requires NO new pip installs. All needed packages are already installed from Phase 6. The `openai` package is a transitive dependency of `azure-ai-agents`.

## Architecture Patterns

### Recommended Project Structure (Phase 7 Additions)

```
backend/src/second_brain/
├── __init__.py
├── main.py                  # Lifespan: add agent registration + agent on app.state
├── config.py                # No changes needed (AZURE_AI_CLASSIFIER_AGENT_ID already present)
├── auth.py                  # Unchanged
├── agents/
│   ├── __init__.py
│   ├── classifier.py        # REWRITE: Foundry agent creation/loading, instructions
│   └── middleware.py         # NEW: AuditAgentMiddleware + ToolTimingMiddleware
├── api/
│   ├── __init__.py
│   ├── health.py            # Unchanged
│   └── inbox.py             # Unchanged
├── db/
│   ├── __init__.py
│   ├── blob_storage.py      # Unchanged (used by transcribe_audio)
│   └── cosmos.py            # Unchanged
├── models/
│   ├── __init__.py
│   └── documents.py         # Minor: remove mark_as_junk status, add transcript field if storing
└── tools/
    ├── __init__.py
    ├── classification.py    # REWRITE: file_capture replaces classify_and_file, remove mark_as_junk
    ├── transcription.py     # NEW: transcribe_audio tool using gpt-4o-transcribe
    └── cosmos_crud.py       # Unchanged
```

### Pattern 1: Persistent Agent Registration at Startup (Self-Healing)

**What:** Check if the stored agent ID exists in Foundry. If valid, load it. If missing or invalid, create a new agent and log the new ID.

**When to use:** App startup in FastAPI lifespan, after Foundry client initialization.

**Example:**
```python
# Source: Official docs + CONTEXT.md decisions
from agent_framework.azure import AzureAIAgentClient

async def ensure_classifier_agent(
    foundry_client: AzureAIAgentClient,
    settings: Settings,
) -> str:
    """Ensure Classifier agent exists in Foundry. Returns agent_id.

    Self-healing: if stored ID is invalid/missing, creates a new agent.
    """
    agent_id = settings.azure_ai_classifier_agent_id

    if agent_id:
        # Check if stored agent still exists in Foundry
        try:
            agent_info = await foundry_client.agents_client.get_agent(agent_id)
            logger.info(
                "Classifier agent loaded: id=%s name=%s",
                agent_info.id,
                agent_info.name,
            )
            return agent_id
        except Exception:
            logger.warning(
                "Stored agent ID %s not found in Foundry, creating new agent",
                agent_id,
            )

    # Create new agent -- instructions set here but editable in portal
    new_agent = await foundry_client.agents_client.create_agent(
        model="gpt-4o",
        name="Classifier",
        instructions=CLASSIFIER_INSTRUCTIONS,
    )
    logger.info(
        "Created new Classifier agent: id=%s. "
        "Update AZURE_AI_CLASSIFIER_AGENT_ID=%s in .env",
        new_agent.id,
        new_agent.id,
    )
    return new_agent.id
```

**Critical detail:** After creating a new agent, the ID should be logged prominently so Will can update `.env`. The agent registration itself is the persistent store -- the ID in `.env` is just a cache to avoid re-creation.

### Pattern 2: Agent with Local @tool Functions

**What:** Create a ChatAgent from `AzureAIAgentClient` with tools and middleware attached.

**When to use:** After agent registration, to get a runnable agent instance.

**Example:**
```python
# Source: Official docs -- https://learn.microsoft.com/agent-framework/agents/providers/azure-ai-foundry
from agent_framework.azure import AzureAIAgentClient
from agent_framework import tool

# Tools can be module-level functions or class methods
@tool(approval_mode="never_require")
async def file_capture(
    text: Annotated[str, Field(description="The text to classify and file")],
    bucket: Annotated[str, Field(description="Classification bucket: People, Projects, Ideas, or Admin")],
    confidence: Annotated[float, Field(description="Confidence score 0.0-1.0")],
    status: Annotated[str, Field(description="Status: classified, pending, or misunderstood")],
) -> dict:
    """File a classified capture to Cosmos DB."""
    # ... Cosmos write logic ...
    return {"bucket": bucket, "confidence": confidence, "item_id": doc_id}

# Create agent with tools
classifier_client = AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    agent_id=classifier_agent_id,
    should_cleanup_agent=False,
)

agent = classifier_client.create_agent(
    instructions=None,  # Use instructions from Foundry portal
    tools=[file_capture, transcribe_audio],
    middleware=[AuditAgentMiddleware(), ToolTimingMiddleware()],
)

# Run the agent
result = await agent.run("Pick up prescription at Walgreens")
print(result.text)  # "Filed -> Admin (0.92)"
```

### Pattern 3: file_capture Tool with Structured Dict Returns

**What:** The `file_capture` tool replaces `classify_and_file`. It receives the agent's classification decision and writes to Cosmos DB. Returns a dict, not a string.

**When to use:** Every classification -- the agent calls this after reasoning about the text.

**Recommended parameter design (Claude's Discretion):** Use separate parameters rather than a grouped object. The Foundry service serializes tool calls as JSON with named parameters -- separate params give the LLM clearer structure.

**Example:**
```python
@tool(approval_mode="never_require")
async def file_capture(
    text: Annotated[str, Field(description="The original captured text to file")],
    bucket: Annotated[str, Field(description="Classification bucket: People, Projects, Ideas, or Admin")],
    confidence: Annotated[float, Field(description="Confidence score 0.0-1.0 for the chosen bucket")],
    status: Annotated[str, Field(description="Status: 'classified' (confidence >= 0.6), 'pending' (confidence < 0.6), or 'misunderstood'")],
    title: Annotated[str, Field(description="Brief title (3-6 words) extracted from the text")] = "Untitled",
) -> dict:
    """File a classified capture to Cosmos DB.

    The Classifier agent calls this after determining the bucket and confidence.
    For misunderstood items, set status='misunderstood' with bucket='Admin' and
    confidence=0.0.
    """
    # Validate
    if bucket not in VALID_BUCKETS:
        return {"error": "invalid_bucket", "detail": f"Unknown bucket: {bucket}"}

    confidence = max(0.0, min(1.0, confidence))

    try:
        # ... Cosmos DB write (Inbox + bucket container) ...
        return {"bucket": bucket, "confidence": confidence, "item_id": inbox_doc_id}
    except Exception as exc:
        logger.warning("file_capture Cosmos write failed: %s", exc)
        return {"error": "cosmos_write_failed", "detail": str(exc)}
```

### Pattern 4: transcribe_audio Tool

**What:** Downloads audio from Blob Storage URL, calls `gpt-4o-transcribe` via `AsyncAzureOpenAI`, returns transcript text.

**When to use:** Voice captures -- agent calls `transcribe_audio` first, reads the transcript, then calls `file_capture`.

**Example:**
```python
@tool(approval_mode="never_require")
async def transcribe_audio(
    blob_url: Annotated[str, Field(description="Azure Blob Storage URL of the audio recording")],
) -> str:
    """Transcribe a voice recording to text using gpt-4o-transcribe.

    Downloads audio from Blob Storage, sends to Azure OpenAI Audio API,
    returns the transcript text.
    """
    try:
        # Download audio bytes from Blob Storage
        audio_bytes = await _download_blob(blob_url)

        # Call gpt-4o-transcribe via AsyncAzureOpenAI
        result = await openai_client.audio.transcriptions.create(
            model="gpt-4o-transcribe",  # deployment name in Azure
            file=("recording.m4a", audio_bytes, "audio/m4a"),
        )
        return result.text
    except Exception as exc:
        logger.warning("transcribe_audio failed: %s", exc)
        return f"Transcription failed: {exc}"
```

**Key detail:** The `gpt-4o-transcribe` model uses the same `audio.transcriptions.create()` API as Whisper. The only change from v1 is the model name. The Azure OpenAI API version should be `2025-04-01-preview` or later. The model must be deployed in the Azure OpenAI resource as `gpt-4o-transcribe`.

### Pattern 5: Class-Based Middleware

**What:** `AgentMiddleware` for audit logging of agent runs, `FunctionMiddleware` for tool timing.

**When to use:** Registered at agent creation via `middleware=[]` parameter.

**Recommendation (Claude's Discretion):** Use class-based middleware. It is more aligned with the project's existing class patterns for stateful resources (CosmosManager, BlobStorageManager, ClassificationTools), and the official docs show class-based as the primary pattern.

**Example:**
```python
# Source: https://learn.microsoft.com/agent-framework/agents/middleware/
import logging
import time
from collections.abc import Awaitable, Callable

from agent_framework import AgentMiddleware, AgentContext
from agent_framework import FunctionMiddleware, FunctionInvocationContext

logger = logging.getLogger(__name__)


class AuditAgentMiddleware(AgentMiddleware):
    """Logs agent run start/end with timing."""

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        start = time.monotonic()
        logger.info("[Agent] Run started")
        await call_next()
        elapsed = time.monotonic() - start
        logger.info("[Agent] Run completed in %.3fs", elapsed)


class ToolTimingMiddleware(FunctionMiddleware):
    """Logs tool call name, timing, and result summary."""

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        func_name = context.function.name
        logger.info("[Tool] Calling %s", func_name)
        start = time.monotonic()
        await call_next()
        elapsed = time.monotonic() - start

        # Log structured classification result for AppInsights queryability
        result = context.result
        if isinstance(result, dict) and "bucket" in result:
            logger.info(
                "[Tool] %s completed in %.3fs: bucket=%s confidence=%.2f status=%s item_id=%s",
                func_name,
                elapsed,
                result.get("bucket"),
                result.get("confidence"),
                result.get("status", "classified"),
                result.get("item_id"),
            )
        else:
            logger.info("[Tool] %s completed in %.3fs", func_name, elapsed)
```

### Pattern 6: Tool Closure Pattern for Dependency Injection

**What:** Tools need access to CosmosManager, BlobStorageManager, and AsyncAzureOpenAI clients. Since tools are passed as callables to `as_agent()`, they need these dependencies injected.

**Two options:**

**Option A: Class-based tools (current v1 pattern)**
```python
class ClassifierTools:
    def __init__(self, cosmos_manager, openai_client, blob_manager):
        self._cosmos = cosmos_manager
        self._openai = openai_client
        self._blob = blob_manager

    @tool(approval_mode="never_require")
    async def file_capture(self, text, bucket, confidence, status, title="Untitled"):
        # self._cosmos available here
        ...

    @tool(approval_mode="never_require")
    async def transcribe_audio(self, blob_url):
        # self._openai and self._blob available here
        ...

# Usage:
tools = ClassifierTools(cosmos_manager, openai_client, blob_manager)
agent = client.create_agent(tools=[tools.file_capture, tools.transcribe_audio])
```

**Option B: Module-level functions with closure**
```python
def create_file_capture_tool(cosmos_manager, threshold):
    @tool(approval_mode="never_require")
    async def file_capture(text, bucket, confidence, status, title="Untitled"):
        # cosmos_manager captured in closure
        ...
    return file_capture
```

**Recommendation (Claude's Discretion):** Use **Option A (class-based)** -- consistent with the existing `ClassificationTools` pattern and justified per CLAUDE.md because the class manages stateful references to clients. The existing `ClassificationTools` class can be refactored in place.

### Anti-Patterns to Avoid

- **Creating the agent on every request:** The agent is persistent and should be created once at startup. Each request creates a new thread and runs the agent on it, not a new agent.
- **Storing instructions in a local Python file AND the portal:** Locked decision: Foundry portal is the source of truth. The initial instructions are passed at agent creation but are editable in the portal without redeployment. Do NOT maintain a local reference copy.
- **Raising exceptions from tools:** Locked decision: tools return error dicts, not exceptions. The agent can read the error and respond appropriately (retry, report to user, etc.).
- **Using `should_cleanup_agent=True` for persistent agents:** This would delete the agent when the app shuts down, losing the stable ID.
- **Mixing sync and async in tool functions:** All tools must be async since they call async Azure SDK clients (Cosmos, Blob, OpenAI).
- **Passing `approval_mode="always_require"` for automated tools:** This would halt execution waiting for human approval on every tool call. Use `"never_require"` for backend-automated tools.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tool parameter schema generation | Manual JSON schema for Foundry | `@tool` decorator with `Annotated[type, Field(...)]` | SDK auto-generates the function schema from type annotations and Pydantic Fields |
| Agent thread management | Custom conversation/thread tracking | Foundry service-managed threads | Each `agent.run()` creates a thread; Foundry handles history, token limits, cleanup |
| Tool execution callback loop | Manual polling for tool calls + submitting results | `agent.run()` with `approval_mode="never_require"` | SDK auto-invokes local tools when the Foundry service requests them |
| Agent-level audit logging | Custom decorators on each tool | `AgentMiddleware` + `FunctionMiddleware` | Framework middleware intercepts all runs and tool calls centrally |
| Audio transcription pipeline | Custom audio processing chain | `AsyncAzureOpenAI.audio.transcriptions.create()` | Standard OpenAI API with gpt-4o-transcribe model -- same API shape as Whisper |

**Key insight:** The Agent Framework SDK handles the entire tool execution loop internally. When the Foundry service decides to call a tool, the SDK deserializes the arguments, calls the local Python function, serializes the result, and submits it back to the service. All the developer provides is a decorated Python function.

## Common Pitfalls

### Pitfall 1: Agent ID Not Persisted After First Creation
**What goes wrong:** App creates a new Classifier agent on every restart, leaving orphan agents in the Foundry portal.
**Why it happens:** `AZURE_AI_CLASSIFIER_AGENT_ID` is empty in `.env` and nobody updates it after the first startup.
**How to avoid:** The `ensure_classifier_agent()` function should log the new ID prominently. On first run, Will updates `.env` manually with the new ID. On subsequent restarts, the existing ID is used.
**Warning signs:** Multiple agents named "Classifier" appearing in the Foundry portal.

### Pitfall 2: Tool Functions Not Getting CosmosManager Reference
**What goes wrong:** `file_capture` tries to write to Cosmos but has no reference to the initialized `CosmosManager`.
**Why it happens:** Module-level `@tool` functions don't have access to app.state. The dependency must be injected.
**How to avoid:** Use the class-based tool pattern (ClassifierTools) where `CosmosManager` is passed to `__init__`. The tool methods are bound methods with `self._cosmos` available.
**Warning signs:** `AttributeError: 'NoneType' object has no attribute 'get_container'` at runtime.

### Pitfall 3: gpt-4o-transcribe Model Not Deployed
**What goes wrong:** `transcribe_audio` fails with a 404 or model-not-found error.
**Why it happens:** `gpt-4o-transcribe` must be deployed as a model in the Azure OpenAI resource. It is NOT automatically available just because gpt-4o is deployed.
**How to avoid:** Before coding, verify the model is deployed: check Azure AI Foundry portal > Models > Deployments. The deployment name is what goes in the `model=` parameter.
**Warning signs:** HTTP 404 from `audio.transcriptions.create()`.

### Pitfall 4: AsyncAzureOpenAI Credential vs Foundry Credential
**What goes wrong:** `transcribe_audio` uses a separate `AsyncAzureOpenAI` client for the Audio API, and it needs its own credential setup. Using the Foundry client's credential directly may not work because the Audio API has a different token scope.
**Why it happens:** The Foundry Agent Service uses `https://ai.azure.com/.default` scope; the Azure OpenAI API may need `https://cognitiveservices.azure.com/.default` scope.
**How to avoid:** Create a dedicated `AsyncAzureOpenAI` client with `azure_ad_token_provider` using `get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")`. Store it on app.state alongside the Foundry client.
**Warning signs:** 401 Unauthorized from the Audio API despite valid Foundry credentials.

### Pitfall 5: Middleware `call_next` Signature Mismatch
**What goes wrong:** Middleware fails with a TypeError because the `call_next` signature differs between class-based and function-based patterns.
**Why it happens:** In the official docs, the class-based middleware's `process` method takes `call_next: Callable[[], Awaitable[None]]` (no args), while the function-based pattern takes `next: Callable[[Context], Awaitable[None]]` (with context arg). The current documentation shows **both** patterns, and there may be SDK version differences.
**How to avoid:** Use the class-based pattern consistently. In the official class-based examples, `call_next()` is called with no arguments. Test middleware with a simple agent.run() call before integrating into the full pipeline.
**Warning signs:** `TypeError: call_next() takes 0 positional arguments but 1 was given` or vice versa.

### Pitfall 6: Instructions Passed to Both create_agent() AND Foundry Portal
**What goes wrong:** Instructions are set at agent creation time, then Will edits them in the portal. On the next restart, if the code calls `create_agent()` again (because the agent was deleted from the portal), it overwrites the portal edits with the code version.
**Why it happens:** The initial `create_agent()` call requires instructions. If the agent is recreated, the code version replaces whatever was in the portal.
**How to avoid:** The `ensure_classifier_agent()` function only creates an agent when none exists. Once created, instructions are managed exclusively in the portal. Keep the code-side instructions as a reasonable starting point but accept that the portal version may diverge.
**Warning signs:** Classification accuracy changes after a restart without code changes (the code re-created the agent with stale instructions).

### Pitfall 7: v1 Tool Return Format vs v2 Dict Format
**What goes wrong:** Tests or downstream code expect the old string return format (`"Filed -> Projects (0.85) | {uuid}"`), but the new `file_capture` returns a dict.
**Why it happens:** The CONTEXT.md decision changes the return format from string to structured dict.
**How to avoid:** Update all tests to expect dict returns. The agent's text response (visible to the user in Phase 8+) is separate from the tool return value.
**Warning signs:** Tests asserting `"Filed" in result` fail because `result` is now a dict.

## Code Examples

### Complete Agent Registration and Loading

```python
# Source: Official docs + CONTEXT.md decisions
# backend/src/second_brain/agents/classifier.py

import logging
from typing import TYPE_CHECKING

from agent_framework.azure import AzureAIAgentClient

if TYPE_CHECKING:
    from second_brain.config import Settings

logger = logging.getLogger(__name__)

# Initial instructions -- used only when creating a NEW agent.
# Portal is the source of truth after creation.
CLASSIFIER_INSTRUCTIONS = """You are Will's second brain classifier. Your job is to classify
captured text into exactly one of four buckets and file it.

## Buckets
- **People**: Relationships, interactions, social context...
- **Projects**: Multi-step endeavors with a goal...
- **Ideas**: Thoughts to revisit later, reflections...
- **Admin**: One-off tasks, errands, logistics...

## Decision Flow
1. High confidence (>= 0.6): Call file_capture with status='classified'
2. Low confidence (0.3-0.59): Call file_capture with status='pending'
3. Misunderstood (< 0.3 OR can't determine intent): Call file_capture with status='misunderstood'

## Rules
- ALWAYS call file_capture -- never respond without filing
- For voice captures: call transcribe_audio first, read the transcript, then file_capture
"""


async def ensure_classifier_agent(
    foundry_client: AzureAIAgentClient,
    stored_agent_id: str,
) -> str:
    """Ensure Classifier agent exists in Foundry. Returns valid agent_id."""
    if stored_agent_id:
        try:
            agent_info = await foundry_client.agents_client.get_agent(stored_agent_id)
            logger.info("Classifier agent verified: id=%s", agent_info.id)
            return stored_agent_id
        except Exception:
            logger.warning("Stored agent ID %s invalid, creating new", stored_agent_id)

    new_agent = await foundry_client.agents_client.create_agent(
        model="gpt-4o",
        name="Classifier",
        instructions=CLASSIFIER_INSTRUCTIONS,
    )
    logger.info(
        "NEW Classifier agent created: id=%s -- update AZURE_AI_CLASSIFIER_AGENT_ID",
        new_agent.id,
    )
    return new_agent.id
```

### Complete file_capture Tool

```python
# Source: v1 ClassificationTools refactored per CONTEXT.md decisions
# backend/src/second_brain/tools/classification.py

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
    """Tool functions for the Classifier agent, bound to Cosmos and OpenAI clients."""

    def __init__(
        self,
        cosmos_manager: CosmosManager,
        classification_threshold: float = 0.6,
    ) -> None:
        self._cosmos = cosmos_manager
        self._threshold = classification_threshold

    @tool(approval_mode="never_require")
    async def file_capture(
        self,
        text: Annotated[str, Field(description="The original captured text to file")],
        bucket: Annotated[str, Field(description="Classification bucket: People, Projects, Ideas, or Admin")],
        confidence: Annotated[float, Field(description="Confidence score 0.0-1.0")],
        status: Annotated[str, Field(description="Status: classified, pending, or misunderstood")],
        title: Annotated[str, Field(description="Brief title (3-6 words)")] = "Untitled",
    ) -> dict:
        """File a classified capture to Cosmos DB."""
        if bucket not in VALID_BUCKETS:
            return {"error": "invalid_bucket", "detail": f"Unknown: {bucket}"}

        confidence = max(0.0, min(1.0, confidence))

        try:
            inbox_doc_id = str(uuid4())
            bucket_doc_id = str(uuid4())

            classification_meta = ClassificationMeta(
                bucket=bucket,
                confidence=confidence,
                allScores={},  # Agent-determined; not tracking per-bucket scores in v2
                classifiedBy="Classifier",
                agentChain=["Classifier"],
                classifiedAt=datetime.now(UTC),
            )

            inbox_doc = InboxDocument(
                id=inbox_doc_id,
                rawText=text,
                classificationMeta=classification_meta if status != "misunderstood" else None,
                source="text",
                title=title,
                filedRecordId=bucket_doc_id if status != "misunderstood" else None,
                status=status,
            )

            inbox_container = self._cosmos.get_container("Inbox")
            await inbox_container.create_item(body=inbox_doc.model_dump(mode="json"))

            # Only write to bucket container for classified/pending (not misunderstood)
            if status != "misunderstood":
                model_class = CONTAINER_MODELS[bucket]
                kwargs = {
                    "id": bucket_doc_id,
                    "rawText": text,
                    "classificationMeta": classification_meta,
                    "inboxRecordId": inbox_doc_id,
                }
                if bucket == "People":
                    kwargs["name"] = title or "Unnamed"
                else:
                    kwargs["title"] = title or "Untitled"

                bucket_doc = model_class(**kwargs)
                target = self._cosmos.get_container(bucket)
                await target.create_item(body=bucket_doc.model_dump(mode="json"))

            logger.info("Filed: bucket=%s confidence=%.2f status=%s", bucket, confidence, status)
            return {"bucket": bucket, "confidence": confidence, "item_id": inbox_doc_id}

        except Exception as exc:
            logger.warning("file_capture failed: %s", exc)
            return {"error": "cosmos_write_failed", "detail": str(exc)}
```

### Complete transcribe_audio Tool

```python
# Source: Azure OpenAI Audio API + CONTEXT.md decisions
# backend/src/second_brain/tools/transcription.py

import logging
from typing import Annotated

from agent_framework import tool
from openai import AsyncAzureOpenAI
from pydantic import Field

from second_brain.db.blob_storage import BlobStorageManager

logger = logging.getLogger(__name__)


class TranscriptionTools:
    """Audio transcription tool using gpt-4o-transcribe."""

    def __init__(
        self,
        openai_client: AsyncAzureOpenAI,
        blob_manager: BlobStorageManager,
    ) -> None:
        self._openai = openai_client
        self._blob = blob_manager

    @tool(approval_mode="never_require")
    async def transcribe_audio(
        self,
        blob_url: Annotated[str, Field(description="Azure Blob Storage URL of the voice recording")],
    ) -> str:
        """Transcribe a voice recording to text using gpt-4o-transcribe.

        Downloads audio from Blob Storage, sends to Azure OpenAI Audio API.
        Returns the transcript text string on success, or an error message on failure.
        """
        try:
            # Download audio bytes from blob
            audio_bytes = await self._download_blob(blob_url)

            # Call gpt-4o-transcribe
            result = await self._openai.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=("recording.m4a", audio_bytes, "audio/m4a"),
            )
            logger.info("Transcribed %d bytes -> %d chars", len(audio_bytes), len(result.text))
            return result.text

        except Exception as exc:
            logger.warning("transcribe_audio failed: %s", exc)
            return f"Transcription error: {exc}"

    async def _download_blob(self, blob_url: str) -> bytes:
        """Download blob bytes from Azure Blob Storage."""
        from azure.storage.blob.aio import BlobClient
        from azure.identity.aio import DefaultAzureCredential

        async with DefaultAzureCredential() as cred:
            blob_client = BlobClient.from_blob_url(blob_url, credential=cred)
            stream = await blob_client.download_blob()
            return await stream.readall()
```

### Integration Test Pattern

```python
# Source: CONTEXT.md -- "Validation via pytest integration test"
# backend/tests/test_classifier_integration.py

import pytest
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential

from second_brain.config import get_settings


@pytest.mark.integration
async def test_classifier_agent_classifies_text():
    """Integration test: send text to Classifier, assert Cosmos result."""
    settings = get_settings()

    async with DefaultAzureCredential() as cred:
        client = AzureAIAgentClient(
            credential=cred,
            project_endpoint=settings.azure_ai_project_endpoint,
            agent_id=settings.azure_ai_classifier_agent_id,
            should_cleanup_agent=False,
        )

        # Create agent with tools
        from second_brain.tools.classification import ClassifierTools
        # ... set up mock or real Cosmos ...

        agent = client.create_agent(
            tools=[tools.file_capture],
            middleware=[],
        )

        result = await agent.run("Pick up prescription at Walgreens")

        # Agent should have called file_capture and returned confirmation
        assert result.text is not None
        # Verify Cosmos DB write occurred (query Inbox container)
```

## State of the Art

| Old Approach (v1) | Current Approach (v2 Phase 7) | When Changed | Impact |
|---|---|---|---|
| `AzureOpenAIChatClient.as_agent()` | `AzureAIAgentClient(agent_id=...).create_agent()` | Phase 7 | Agent persists in Foundry portal; threads managed server-side |
| `classify_and_file` returns string | `file_capture` returns dict | Phase 7 (CONTEXT.md) | Structured return enables downstream parsing; error dicts replace exceptions |
| `mark_as_junk` + `request_misunderstood` separate tools | `file_capture(status="misunderstood")` unified | Phase 7 (CONTEXT.md) | Junk and misunderstood unified into one status |
| Whisper `whisper-1` via old transcription tool | `gpt-4o-transcribe` via `AsyncAzureOpenAI.audio.transcriptions.create()` | Phase 7 | Same API shape, better accuracy, model deployed as `gpt-4o-transcribe` |
| No middleware | `AgentMiddleware` + `FunctionMiddleware` | Phase 7 | Audit logging and tool timing built into the agent framework |
| Tools use `agent_framework.tool` | Tools use `agent_framework.tool(approval_mode="never_require")` | Phase 7 | Explicit approval mode prevents unintended human-in-the-loop halts |

**Deprecated/outdated:**
- `AzureOpenAIChatClient`: Replaced by `AzureAIAgentClient` for Foundry-backed agents
- `classify_and_file` tool: Replaced by `file_capture` with dict returns
- `mark_as_junk` tool: Eliminated -- misunderstood status in `file_capture` covers this
- `request_misunderstood` tool: Eliminated from Phase 7 -- misunderstood is a `file_capture` status; conversational follow-up is Phase 9
- `agentChain: ["Orchestrator", "Classifier"]`: No orchestrator in v2 -- `agentChain: ["Classifier"]`

## Open Questions

1. **Middleware `call_next` signature -- zero args vs context arg**
   - What we know: The official docs show two patterns. Class-based uses `call_next: Callable[[], Awaitable[None]]` (no args). Function-based uses `next: Callable[[Context], Awaitable[None]]` (context arg). Some doc examples show `call_next()` and others show `await next(context)`.
   - What's unclear: Whether the SDK validates the signature at runtime or if both work. The docs may have inconsistencies between rc versions.
   - Recommendation: Use the class-based pattern consistently. Test with a simple agent call before integrating. If `call_next()` fails, try `call_next(context)`. Flag for empirical validation during implementation.
   - Confidence: MEDIUM -- docs are recent but SDK is RC

2. **gpt-4o-transcribe deployment name in Azure**
   - What we know: The REST API uses `/openai/deployments/{deployment-id}/audio/transcriptions`. The `model=` parameter in the Python SDK maps to the deployment name.
   - What's unclear: Whether the deployment name is literally `"gpt-4o-transcribe"` or a custom name assigned during model deployment in the portal.
   - Recommendation: Verify the deployment name in the Azure AI Foundry portal. Store it as an env var (e.g., `AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT`) rather than hardcoding.
   - Confidence: MEDIUM -- need empirical verification

3. **Voice transcript storage in Cosmos alongside classified text**
   - What we know (Claude's Discretion): The current InboxDocument has `rawText` and `source` fields. For voice captures, `rawText` could hold the transcript and `source` would be `"voice"`. The question is whether to also store the original audio blob URL.
   - Recommendation: Store both -- add a `transcriptSource` field to InboxDocument: `"voice"` when transcribed, `None` when typed. Keep the blob URL in `audioUrl` field. This enables Phase 9 follow-up conversations to reference the original recording.
   - Confidence: HIGH -- minimal schema change, high future value

4. **Whether `as_agent()` vs `create_agent()` should be used**
   - What we know: `as_agent()` returns a context manager (used with `async with`). `create_agent()` returns a `ChatAgent` directly (not a context manager). Both accept `tools=` and `middleware=`.
   - What's unclear: Whether `as_agent()` context manager exit triggers agent cleanup even with `should_cleanup_agent=False`. The `create_agent()` method is simpler for long-lived agents in a FastAPI lifespan.
   - Recommendation: Use `create_agent()` for the persistent Classifier. The agent lives for the entire app lifetime and is stored on `app.state`. No context manager needed.
   - Confidence: HIGH -- `create_agent()` is the non-context-manager alternative

## Sources

### Primary (HIGH confidence)
- [Azure AI Foundry Agents -- Microsoft Agent Framework docs](https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-types/azure-ai-foundry-agent) -- `AzureAIAgentClient` creation, `as_agent()`, function tools, streaming, agent reuse by ID
- [Agent Middleware -- Microsoft Agent Framework docs](https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-middleware) -- `AgentMiddleware`, `FunctionMiddleware`, class-based and function-based patterns, middleware registration, termination, result override
- [AzureAIAgentClient API Reference](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.azure.azureaiagentclient?view=agent-framework-python-latest) -- Constructor params (`agent_id`, `should_cleanup_agent`, `credential`), `create_agent()` method signature, `close()` behavior
- [Using function tools with an agent](https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools) -- `@tool` decorator, `approval_mode`, `Annotated` + `Field` parameter descriptions, class-based tool methods, complete examples
- [Azure OpenAI REST API -- Transcriptions Create](https://learn.microsoft.com/azure/ai-foundry/openai/reference-preview?view=foundry-classic#transcriptions---create) -- `gpt-4o-transcribe` model name, file parameter, response format, API version `2025-04-01-preview`

### Secondary (MEDIUM confidence)
- [Azure OpenAI Whisper quickstart (Python)](https://learn.microsoft.com/azure/ai-foundry/openai/whisper-quickstart?pivots=programming-language-python) -- `client.audio.transcriptions.create()` API pattern (same for gpt-4o-transcribe, just different model name)
- [OpenAI Speech-to-Text docs](https://platform.openai.com/docs/guides/speech-to-text) -- `gpt-4o-transcribe` as drop-in replacement for `whisper-1` in transcriptions API
- [Azure OpenAI Audio Models blog](https://devblogs.microsoft.com/foundry/get-started-azure-openai-advanced-audio-models/) -- gpt-4o-transcribe availability in Azure, API version reference

### Codebase Analysis (HIGH confidence)
- `backend/src/second_brain/agents/classifier.py` -- Current v1 classifier agent (to be rewritten)
- `backend/src/second_brain/tools/classification.py` -- Current `ClassificationTools` class (to be refactored to `file_capture`)
- `backend/src/second_brain/main.py` -- Current lifespan with Foundry client init (add agent registration)
- `backend/src/second_brain/config.py` -- `azure_ai_classifier_agent_id` already present
- `backend/src/second_brain/db/blob_storage.py` -- Existing blob download logic for voice recordings
- `backend/tests/test_classification.py` -- Current test patterns (need updating for dict returns)
- `backend/tests/conftest.py` -- Mock fixtures pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages already installed, SDK APIs verified from official docs
- Architecture: HIGH -- agent registration, tool execution, and middleware patterns all documented with Python examples
- Tool design (file_capture): HIGH -- refactoring existing ClassificationTools, CONTEXT.md provides clear spec
- Transcription (gpt-4o-transcribe): MEDIUM -- API shape confirmed (same as Whisper) but deployment name and Azure-specific API version need empirical validation
- Middleware: MEDIUM -- class-based pattern well-documented but `call_next` signature has inconsistencies between doc examples; needs empirical testing
- Pitfalls: HIGH -- identified from both official docs and codebase analysis

**Research date:** 2026-02-26
**Valid until:** 2026-03-12 (agent-framework-azure-ai is still RC; check for new versions before implementation)
