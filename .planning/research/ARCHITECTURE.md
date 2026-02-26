# Architecture Patterns: Foundry Agent Service Migration

**Domain:** AzureAIAgentClient + Connected Agents integration with existing FastAPI architecture
**Researched:** 2026-02-25
**Confidence:** MEDIUM-HIGH — AzureAIAgentClient is documented in official Microsoft Learn; Connected Agents pattern is documented but has a critical limitation that changes the approach. New Foundry Workflows API (2025-11-15-preview) exists but is complex for this use case. Some integration details confirmed by reading installed SDK source.

---

## Critical Finding: Connected Agents Cannot Call Local Functions

Connected Agents in the classic Foundry portal are deprecated in the new Foundry experience (replaced by Workflows). More importantly, the classic Connected Agents pattern has a hard limitation: **connected agents cannot call local @tool functions using the function calling mechanism.** Microsoft recommends Azure Functions or OpenAPI tools instead.

This breaks the naive migration plan. The Classifier agent uses three local async @tool functions (classify_and_file, request_misunderstood, mark_as_junk) that perform Cosmos DB writes. These cannot be registered as connected-agent tools.

**Resolution:** Use two independent AzureAIAgentClient agents without server-side Connected Agents routing. The Orchestrator is a thin pass-through (may be eliminated). The Classifier runs as a persistent Foundry agent with local @tool functions via agent-framework-azure-ai's AsyncFunctionTool pattern. The AGUIWorkflowAdapter is replaced with a simpler streaming adapter that runs the Classifier directly.

---

## New Architecture: Foundry Single-Agent with Lifespan-Managed Persistence

### What Changes vs. the Current System

| Component | Current | After Migration | Change Type |
|-----------|---------|-----------------|-------------|
| `main.py` client creation | `AzureOpenAIChatClient(credential, endpoint, deployment)` | `AzureAIAgentClient(credential=async_credential, project_endpoint=..., model_deployment_name=...)` | MODIFIED |
| `main.py` credential type | `DefaultAzureCredential()` (sync) | `DefaultAzureCredential()` from `azure.identity.aio` (async) | MODIFIED |
| `orchestrator.py` | `chat_client.as_agent(name, instructions)` | Eliminated (Orchestrator is redundant without HandoffBuilder; Classifier runs directly) OR kept as thin wrapper | MODIFIED/DELETED |
| `classifier.py` | `chat_client.as_agent(name, instructions, tools=[...])` | `ai_client.as_agent(name, instructions, tools=[...])` — tools registered server-side via Foundry | MODIFIED |
| `workflow.py` | HandoffBuilder + AGUIWorkflowAdapter (340 lines) | REPLACED ENTIRELY — new FoundrySSEAdapter (~80-100 lines) wrapping single agent run | REPLACED |
| `config.py` | `azure_openai_endpoint`, `azure_openai_chat_deployment_name` | Add `azure_ai_project_endpoint`, `azure_ai_model_deployment_name` | MODIFIED |
| Agent lifecycle | Ephemeral per-process | Persistent server-registered with ID; `should_cleanup_agent=False` | MODIFIED |
| Conversation threads | In-memory, per-request | Server-managed via Foundry; thread ID stored per capture flow | MODIFIED |

| Component | Change Type |
|-----------|-------------|
| `tools/classification.py` (@tool functions) | UNCHANGED |
| `db/cosmos.py` (CosmosManager) | UNCHANGED |
| `db/blob_storage.py` (BlobStorageManager) | UNCHANGED |
| `api/inbox.py`, `api/health.py` | UNCHANGED |
| `auth.py` (APIKeyMiddleware) | UNCHANGED |
| `models/documents.py` | UNCHANGED |
| `tools/transcription.py` | UNCHANGED |
| Mobile Expo app | UNCHANGED |
| AG-UI SSE protocol (events, format) | UNCHANGED |
| Cosmos DB data model | UNCHANGED |
| `/api/ag-ui/respond` endpoint | UNCHANGED (no agent call, direct Cosmos write) |
| `/api/voice-capture` Perception step | UNCHANGED (Blob upload + Whisper) |

---

## New Package Dependency

```toml
# pyproject.toml — add to dependencies
"agent-framework-azure-ai",   # Provides AzureAIAgentClient
```

The `agent-framework-azure-ai` package installs alongside `agent-framework-core`. The current `agent-framework-orchestrations` (HandoffBuilder) can be removed once workflow.py is replaced.

```bash
uv add agent-framework-azure-ai --prerelease=allow
uv remove agent-framework-orchestrations  # after workflow.py replacement
```

---

## Component Diagram: After Migration

```
┌────────────────────────────────────────────────────────────────────┐
│                     Mobile App (Expo)                              │
│               (AG-UI SSE Client — unchanged)                       │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ HTTP POST + SSE (AG-UI protocol)
                              │ API key header
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                   FastAPI (Azure Container Apps)                    │
│                                                                    │
│  ┌─── Lifespan ─────────────────────────────────────────────────┐  │
│  │  async DefaultAzureCredential                                │  │
│  │  AzureAIAgentClient (project_endpoint, model, credential)    │  │
│  │  ClassificationTools (bound to CosmosManager)                │  │
│  │  classifier_agent = ai_client.as_agent(name, instructions,   │  │
│  │                        tools=[classification_tools.*])        │  │
│  │  app.state.classifier_agent = classifier_agent               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  POST /api/ag-ui                                                   │
│  ┌─── FoundrySSEAdapter ────────────────────────────────────────┐  │
│  │  classifier_agent.run(messages, stream=True)                 │  │
│  │  AgentResponseUpdate → AG-UI events                          │  │
│  │  MISUNDERSTOOD / CLASSIFIED / UNRESOLVED custom events       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  POST /api/voice-capture  (Perception step unchanged)              │
│  POST /api/ag-ui/respond  (Direct Cosmos write, no agent)         │
│  POST /api/ag-ui/follow-up (Uses classifier_agent)                │
│                                                                    │
└──────────────────┬────────────────────────────────────────────────┘
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
┌─────────────────┐     ┌──────────────────────────────────────────┐
│  Cosmos DB      │     │  Azure AI Foundry                        │
│  (unchanged)    │     │  ┌─────────────────────────────────────┐  │
│  - Inbox        │     │  │  Classifier Agent (persistent)      │  │
│  - People       │     │  │  ID: saved at startup / stable      │  │
│  - Projects     │     │  │  Tools: local @tool functions        │  │
│  - Ideas        │     │  │  Threads: server-managed            │  │
│  - Admin        │     │  └─────────────────────────────────────┘  │
└─────────────────┘     │  Application Insights tracing            │
                        └──────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With | Status |
|-----------|---------------|-------------------|--------|
| `main.py` | FastAPI app, lifespan, SSE endpoints, request routing | All below | MODIFIED |
| `config.py` | Settings via pydantic-settings | Environment variables | MODIFIED |
| `agents/classifier.py` | Create Classifier Agent with Foundry client | AzureAIAgentClient, ClassificationTools | MODIFIED |
| `agents/workflow.py` | REPLACED: new FoundrySSEAdapter wraps classifier run | classifier_agent, AG-UI encoder | REPLACED |
| `agents/orchestrator.py` | ELIMINATED (Classifier runs directly) | N/A | DELETED |
| `tools/classification.py` | @tool functions: classify_and_file, request_misunderstood, mark_as_junk | CosmosManager | UNCHANGED |
| `tools/cosmos_crud.py` | Cosmos CRUD helpers | CosmosManager | UNCHANGED |
| `tools/transcription.py` | Whisper transcription | Azure OpenAI Whisper | UNCHANGED |
| `db/cosmos.py` | CosmosManager singleton | Azure Cosmos DB | UNCHANGED |
| `db/blob_storage.py` | BlobStorageManager singleton | Azure Blob Storage | UNCHANGED |
| `auth.py` | APIKeyMiddleware | app.state.api_key | UNCHANGED |
| `api/inbox.py` | Inbox CRUD REST endpoints | CosmosManager | UNCHANGED |
| `api/health.py` | Health check | N/A | UNCHANGED |

---

## Data Flow: Text Capture (New Architecture)

```
1. Mobile app sends POST /api/ag-ui
   Body: { messages: [{role: "user", content: "Buy milk eggs bread"}], thread_id, run_id }

2. FastAPI ag_ui_endpoint handler:
   - Reads app.state.classifier_agent (AzureAIAgentClient-backed Agent)
   - Converts messages to agent-framework Message objects
   - Calls: stream = classifier_agent.run(messages, stream=True, thread_id=thread_id)

3. Foundry Agent Service (server-side):
   - Receives the run request with Classifier agent ID
   - LLM call: Classifier model + instructions + tools
   - LLM decides to call classify_and_file(bucket="Admin", confidence=0.95, ...)
   - Foundry service sends tool call back to client (requires_action or stream tool call event)

4. agent-framework-azure-ai handles tool dispatch:
   - AsyncFunctionTool intercepts the classify_and_file tool call
   - Executes locally in FastAPI process (Cosmos DB write via CosmosManager)
   - Returns result string "Filed → Admin (0.95) | <uuid>" to Foundry service
   - Foundry continues the run with tool result

5. FoundrySSEAdapter (new workflow.py):
   - Consumes AgentResponseUpdate stream from classifier_agent.run()
   - Detects classification outcome by inspecting function_call.name (same as before)
   - Suppresses Classifier chain-of-thought text (same buffer logic)
   - Emits StepStartedEvent / StepFinishedEvent for "Classifier" step
   - Emits CLASSIFIED / MISUNDERSTOOD / UNRESOLVED custom events
   - Converts AgentResponseUpdate → AG-UI events via _convert_update_to_events()

6. FastAPI _stream_sse():
   - Wraps FoundrySSEAdapter output in RunStarted / RunFinished
   - Yields SSE text chunks to mobile app

7. Mobile app receives:
   - RUN_STARTED
   - STEP_STARTED (Classifier)
   - TEXT_MESSAGE_CONTENT delta (clean result string)
   - STEP_FINISHED (Classifier)
   - CUSTOM: CLASSIFIED { inboxItemId, bucket, confidence }
   - RUN_FINISHED
```

---

## Data Flow: Voice Capture (New Architecture)

Voice capture data flow is nearly identical. The Perception step (Blob upload + Whisper transcription) is unchanged. After transcription produces text, the flow merges with text capture:

```
1. Mobile app sends POST /api/voice-capture (multipart audio)

2. FastAPI voice_capture handler:
   - Reads audio bytes
   - Validates size (1KB - 25MB)
   - Emits StepStartedEvent("Perception") to SSE stream
   - Uploads audio to Blob Storage (BlobStorageManager.upload_audio)
   - Transcribes via Whisper (asyncio.to_thread(transcribe_audio, ...))
   - Deletes blob after transcription
   - Emits StepFinishedEvent("Perception")

3. SAME AS TEXT CAPTURE from step 2 onward:
   - Uses app.state.classifier_agent (same persistent agent)
   - Transcription text is the user message
   - Same FoundrySSEAdapter stream processing
   - Same CLASSIFIED / MISUNDERSTOOD / UNRESOLVED events

4. KEY DIFFERENCE vs current: No HandoffBuilder wrapping
   - Current: voice_capture calls workflow_agent.run() which creates a fresh Workflow
   - After: voice_capture calls classifier_agent.run() directly
   - The Perception "step" is still manually emitted (unchanged from current)
```

---

## Agent Lifecycle: How Persistent Agents Work

### The Problem with Ephemeral Agents

`AzureAIAgentClient` with `should_cleanup_agent=True` (default) creates and deletes agents on every context manager exit. For a FastAPI app, this means every request (or every startup) creates a new server-registered agent. This:
- Accumulates stale agents in the Foundry portal
- Adds latency on first use
- Is incorrect for learning goals (defeats the "persistent agents" value proposition)

### Recommended Pattern: Create Once, Reuse by ID

```python
# In lifespan: create agent if not exists, store ID in persistent config
# Option A: Store agent ID in environment variable (simplest)
# Option B: Store agent ID in Key Vault secret (more production-appropriate)
# Option C: Query Foundry for existing agents by name (requires admin API call)

# Implementation approach for lifespan:
async with AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    model_deployment_name=settings.azure_ai_model_deployment_name,
    agent_name="Classifier",
    should_cleanup_agent=False,  # CRITICAL: don't delete on close
) as ai_client:
    classifier = ai_client.as_agent(
        name="Classifier",
        instructions="...",
        tools=[classification_tools.classify_and_file, ...]
    )
    app.state.classifier_agent = classifier
    app.state.ai_client = ai_client  # keep alive for duration
```

### Agent ID Persistence Strategy

**Recommended for this project:** Environment variable `AZURE_AI_CLASSIFIER_AGENT_ID`. On first deploy, set to empty string. Lifespan checks: if empty, create new agent, log its ID for manual env var update. If set, use `AzureAIAgentClient(agent_id=settings.azure_ai_classifier_agent_id, ...)` to attach to existing.

This avoids portal accumulation and matches the learning goal of visible persistent agents.

---

## Key Code Pattern: AzureAIAgentClient Initialization

```python
# config.py additions
class Settings(BaseSettings):
    # NEW: Foundry project endpoint
    azure_ai_project_endpoint: str = ""
    # NEW: Model deployment name (replaces azure_openai_chat_deployment_name for agents)
    azure_ai_model_deployment_name: str = "gpt-4o"
    # NEW: Optional pre-registered Classifier agent ID
    azure_ai_classifier_agent_id: str = ""
    # Application Insights (for Foundry tracing)
    applicationinsights_connection_string: str = ""

    # KEEP: Whisper still uses Azure OpenAI directly
    azure_openai_endpoint: str = ""
    azure_openai_whisper_deployment_name: str = "whisper"
```

```python
# main.py lifespan (key changes only)
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from agent_framework.azure import AzureAIAgentClient  # NEW import

@asynccontextmanager
async def lifespan(app: FastAPI):
    # CHANGED: Use async credential for AzureAIAgentClient
    credential = AsyncDefaultAzureCredential()

    # EXISTING: Cosmos DB, Blob Storage, Key Vault unchanged

    # CHANGED: Replace AzureOpenAIChatClient with AzureAIAgentClient
    try:
        ai_client = AzureAIAgentClient(
            credential=credential,
            project_endpoint=settings.azure_ai_project_endpoint,
            model_deployment_name=settings.azure_ai_model_deployment_name,
            should_cleanup_agent=False,
        )

        classification_tools = ClassificationTools(
            cosmos_manager=cosmos_manager,
            classification_threshold=settings.classification_threshold,
        )

        # NEW: Pass agent_id if pre-registered, else create fresh
        agent_kwargs = {}
        if settings.azure_ai_classifier_agent_id:
            agent_kwargs["agent_id"] = settings.azure_ai_classifier_agent_id

        classifier_agent = ai_client.as_agent(
            name="Classifier",
            instructions="...",  # same as current classifier.py
            tools=[
                classification_tools.classify_and_file,
                classification_tools.request_misunderstood,
                classification_tools.mark_as_junk,
            ],
            **agent_kwargs,
        )

        # REMOVED: orchestrator (no HandoffBuilder needed)
        # REMOVED: create_capture_workflow()

        # CHANGED: Store classifier_agent directly (not workflow_agent)
        app.state.classifier_agent = classifier_agent
        app.state.ai_client = ai_client
        app.state.classification_tools = classification_tools
        app.state.settings = settings

    except Exception:
        logger.warning("Could not initialize AI client or Classifier agent.")
        app.state.classifier_agent = None
        app.state.ai_client = None

    yield

    # Cleanup: close ai_client (does NOT delete agent since should_cleanup_agent=False)
    if getattr(app.state, "ai_client", None) is not None:
        await app.state.ai_client.close()
    # ... existing Cosmos, Blob cleanup
```

---

## New workflow.py: FoundrySSEAdapter

The 340-line AGUIWorkflowAdapter is replaced with a ~150-line adapter that wraps a single agent run. The key behavior is preserved:

- Outcome detection via function_call.name (UNCHANGED logic)
- Classifier text buffering / suppression (UNCHANGED logic)
- StepStarted / StepFinished event emission for "Classifier" step
- MISUNDERSTOOD / CLASSIFIED / UNRESOLVED custom events

What changes:
- No HandoffBuilder, no Workflow, no WorkflowEvent handling
- No executor_invoked / executor_completed event types
- No Orchestrator echo filtering (Orchestrator is gone)
- `workflow.run()` → `classifier_agent.run()`
- `get_new_thread()` → thread management via `thread_id` parameter

```python
# New workflow.py skeleton
class FoundrySSEAdapter:
    """Thin adapter wrapping classifier_agent.run() for AG-UI compatibility.

    Preserves outcome detection, text buffering, and step events
    from the old AGUIWorkflowAdapter without HandoffBuilder dependencies.
    """

    def __init__(
        self,
        classifier: Agent,
        classification_threshold: float = 0.6,
    ) -> None:
        self._classifier = classifier
        self._classification_threshold = classification_threshold

    async def _stream_updates(
        self,
        messages,
        thread_id: str,
        **kwargs,
    ) -> AsyncIterable[StreamItem]:
        # SAME outcome detection logic as AGUIWorkflowAdapter
        # SAME text buffering logic
        # SAME custom event emission
        # But source is: self._classifier.run(messages, stream=True)
        # Not: workflow.run(message=messages, stream=True)

        yield StepStartedEvent(step_name="Classifier")
        async for update in self._classifier.run(messages, stream=True):
            # ... same processing as before but no WorkflowEvent handling
            yield update
        yield StepFinishedEvent(step_name="Classifier")
        # ... emit CLASSIFIED / MISUNDERSTOOD based on detected_tool

    def run(self, messages, *, stream=False, thread=None, **kwargs):
        if stream:
            return ResponseStream(self._stream_updates(messages, **kwargs))
        # sync path (tests)
        raise NotImplementedError("Sync run not needed in new architecture")
```

---

## Thread Management: Server-Side vs Cosmos DB

Foundry Agent Service manages conversation threads server-side. Each `classifier_agent.run()` call that includes a `thread_id` continues the existing thread (conversation history is server-maintained).

**Implication for HITL flow:**

The current flow uses Cosmos DB `inbox_item_id` as the anchor for follow-up re-classification. The Foundry `thread_id` is a separate concept.

**Recommended approach:**
- Text capture: create a new `thread_id` per capture (same as current behavior — fresh context each time)
- Follow-up endpoint (`/api/ag-ui/follow-up`): use the same `thread_id` from the original capture to continue the server-managed thread, OR create a new thread with combined text (same as current approach)
- The Cosmos DB `inbox_item_id` remains the authoritative cross-system anchor

The current code already generates a new `thread_id` per request (`f"thread-{uuid.uuid4()}"`), so server-side thread accumulation is acceptable. Each capture has its own Foundry thread.

---

## /api/ag-ui Endpoint Changes

The endpoint handler needs a small update to call `classifier_agent.run()` directly:

```python
# BEFORE (current main.py)
workflow_agent: AGUIWorkflowAdapter = request.app.state.workflow_agent
thread = workflow_agent.get_new_thread()
stream = workflow_agent.run(messages, stream=True, thread=thread, thread_id=thread_id)

# AFTER
from second_brain.agents.workflow import FoundrySSEAdapter

sse_adapter: FoundrySSEAdapter = request.app.state.sse_adapter
stream = sse_adapter.run(messages, stream=True, thread_id=thread_id)
```

The `_stream_sse()` helper and `_convert_update_to_events()` helper in `main.py` are **unchanged** — they consume `AsyncGenerator[StreamItem, None]` regardless of source.

The `/api/ag-ui/respond` endpoint is unchanged (no agent call — direct Cosmos DB operation).

The `/api/ag-ui/follow-up` endpoint changes only in how it calls the agent:

```python
# BEFORE
stream = workflow_agent.run(messages, stream=True, thread=thread, thread_id=thread_id)

# AFTER
stream = sse_adapter.run(messages, stream=True, thread_id=thread_id)
```

---

## Build Order

Dependencies must be resolved in this sequence:

1. **Infrastructure** (Phase 1) — Azure AI Foundry project, Application Insights, RBAC (Azure AI User role on project), model deployment in Foundry project. Nothing in code works until this exists.

2. **config.py + .env** (Phase 2a) — Add `azure_ai_project_endpoint`, `azure_ai_model_deployment_name`, `azure_ai_classifier_agent_id`. Update `.env` with new values. No other code changes yet.

3. **Package install** (Phase 2b) — `uv add agent-framework-azure-ai --prerelease=allow`. Validate import works.

4. **Single agent smoke test** (Phase 2c) — Verify `AzureAIAgentClient` can authenticate and the Classifier agent appears in portal. Use a standalone test script (not FastAPI). Do NOT modify `main.py` yet.

5. **classifier.py migration** (Phase 3a) — Change import from `AzureOpenAIChatClient` to `AzureAIAgentClient`. Verify @tool functions still work. Test that `classify_and_file` executes locally when agent calls it via Foundry.

6. **workflow.py replacement** (Phase 3b) — Replace `AGUIWorkflowAdapter` + HandoffBuilder with `FoundrySSEAdapter`. The stream processing logic (outcome detection, buffering, custom events) is largely copy-pasted from the old class.

7. **main.py lifespan migration** (Phase 3c) — Replace `AzureOpenAIChatClient` construction and `create_capture_workflow()` with `AzureAIAgentClient` + `FoundrySSEAdapter`. Remove `orchestrator.py` usage. Update app.state names.

8. **End-to-end test** (Phase 3d) — Full text capture → SSE stream → Cosmos DB write. Verify CLASSIFIED event reaches mobile app.

9. **Voice capture test** (Phase 3e) — Verify Perception step still works, transcription feeds correctly into FoundrySSEAdapter.

10. **HITL test** (Phase 3f) — request_misunderstood path, follow-up endpoint.

11. **Observability wiring** (Phase 4) — Application Insights connection string, Foundry portal tracing, remove old HandoffBuilder package.

**Key dependency:** Steps 2-4 can be done independently of `main.py` — keep FastAPI running on the old stack while validating Foundry connectivity. Switch `main.py` only in step 7.

---

## Patterns to Follow

### Pattern 1: Async Credential for AzureAIAgentClient

AzureAIAgentClient requires `AsyncTokenCredential` (from `azure.identity.aio`), not the sync `TokenCredential` that `AzureOpenAIChatClient` used. The lifespan already uses async credentials for Key Vault — extend this to the AI client.

```python
# Correct
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
credential = AsyncDefaultAzureCredential()
ai_client = AzureAIAgentClient(credential=credential, ...)

# Wrong (sync credential fails with AzureAIAgentClient)
from azure.identity import DefaultAzureCredential
credential = DefaultAzureCredential()  # DO NOT use with AzureAIAgentClient
```

### Pattern 2: should_cleanup_agent=False for Persistent Agents

```python
ai_client = AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    model_deployment_name=settings.azure_ai_model_deployment_name,
    should_cleanup_agent=False,  # Required to preserve agent across restarts
)
```

### Pattern 3: Keep ai_client Alive in lifespan

`AzureAIAgentClient` must remain open as long as agents created from it are in use. Store it on `app.state` alongside the agent:

```python
app.state.classifier_agent = classifier_agent
app.state.ai_client = ai_client  # Prevents premature GC / connection closure
```

Close it explicitly in the lifespan cleanup:
```python
if getattr(app.state, "ai_client", None) is not None:
    await app.state.ai_client.close()
```

### Pattern 4: Tool Execution in Foundry

With `AzureAIAgentClient`, local @tool functions are executed by the `agent-framework-azure-ai` runtime during the `run()` call. The service sends a `requires_action` event; the client intercepts it, executes the tool locally, returns the result to the service, and the stream continues. This is automatic — no changes needed to the @tool function implementations.

The key requirement: tools must be registered at agent creation time (via `as_agent(tools=[...])`) and must be accessible during `run()`. Since `ClassificationTools` is initialized in lifespan and bound to the agent, this is already correct.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Using Connected Agents for Classifier Tools

Connected Agents cannot invoke local function tools. Do not attempt to register classify_and_file as a connected agent tool or OpenAPI endpoint — the existing @tool decorator pattern works correctly with AzureAIAgentClient via the local function execution model.

### Anti-Pattern 2: should_cleanup_agent=True in Production

The default `should_cleanup_agent=True` deletes the Foundry agent on context exit. For a FastAPI lifespan, "context exit" means shutdown. The agent gets recreated on next startup with a new ID — accumulating deleted agents in the portal and losing persistent thread history.

### Anti-Pattern 3: Keeping HandoffBuilder with AzureAIAgentClient

HandoffBuilder creates synthetic transfer tools that route control between local agent objects. With `AzureAIAgentClient`, the actual tool call loop is managed by the Foundry service, not locally. HandoffBuilder's synthetic tools would either never be called or cause conflicts with the service-managed tool routing. Remove it entirely.

### Anti-Pattern 4: Sync Credential with AzureAIAgentClient

`AzureAIAgentClient` requires async credentials. Passing a sync `DefaultAzureCredential` will cause runtime failures on token refresh. Use `azure.identity.aio.DefaultAzureCredential`.

### Anti-Pattern 5: Creating a New ai_client Per Request

`AzureAIAgentClient` should be created once in lifespan and reused across all requests. Creating per-request creates new HTTP sessions and potentially new agent registrations.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| AzureAIAgentClient constructor params | HIGH | Official Microsoft Learn docs + SDK installed in venv |
| AzureAIAgentClient requires async credential | HIGH | Confirmed from AzureAIAgentClient constructor source |
| agent-framework-azure-ai package name | HIGH | Confirmed in azure/__init__.py lazy imports in installed SDK |
| agent-framework-azure-ai NOT installed in current venv | HIGH | Confirmed by searching .venv |
| Local @tool functions work with AzureAIAgentClient | HIGH | Official docs show function tool registration; agent-framework handles tool dispatch |
| Connected Agents limitation (no local functions) | HIGH | Official Microsoft Learn docs, multiple sources |
| Connected Agents deprecated in new Foundry portal | MEDIUM | Q&A forum response + release notes referencing Workflows as replacement |
| FoundrySSEAdapter replaces AGUIWorkflowAdapter | HIGH | Same AgentResponseUpdate event type emitted by both clients; confirmed in AG-UI integration docs |
| should_cleanup_agent=False semantics | HIGH | Documented in AzureAIAgentClient constructor params |
| Thread management approach | MEDIUM | Official docs describe thread creation; per-capture thread approach inferred from existing pattern |
| Whisper still requires azure_openai_endpoint | HIGH | Whisper is not a Foundry Agent Service feature; stays on Azure OpenAI directly |

---

## Open Questions for Phase-Specific Research

1. **Foundry project endpoint format**: The endpoint format changed in May 2025 from connection string (hub-based) to `https://<resource>.services.ai.azure.com/api/projects/<project-id>` (Foundry-based). The existing Azure OpenAI resource at `https://<resource>.openai.azure.com/` is a different resource. Confirm whether a new Foundry project resource is required or whether an existing Azure OpenAI resource can be wrapped in a Foundry project.

2. **Model deployment in Foundry vs Azure OpenAI**: The existing gpt-4o deployment lives in the Azure OpenAI resource. Foundry Agent Service uses model deployments from within the Foundry project. Confirm whether existing Azure OpenAI deployments are automatically available in a new Foundry project, or whether a separate deployment is needed.

3. **RBAC for Foundry Agent Service**: The current Container App uses Managed Identity with Cognitive Services User role. Foundry Agent Service requires Azure AI User role on the Foundry project. Confirm exact role assignments needed for the Container App to call Foundry endpoints.

4. **Streaming event types from AzureAIAgentClient**: The existing AGUIWorkflowAdapter handles both `WorkflowEvent` (from HandoffBuilder) and `AgentResponseUpdate`. The new FoundrySSEAdapter only handles `AgentResponseUpdate`. Confirm that `classifier_agent.run(stream=True)` emits only `AgentResponseUpdate` (not WorkflowEvent types) when using AzureAIAgentClient.

5. **Application Insights integration**: The existing `configure_otel_providers()` call in `main.py` sets up OpenTelemetry. Foundry Agent Service additionally supports native Application Insights export. Confirm whether the existing OTel setup forwards to Application Insights automatically, or whether `APPLICATIONINSIGHTS_CONNECTION_STRING` must be set separately.

---

## Sources

- [AzureAIAgentClient API Reference](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.azure.azureaiagentclient?view=agent-framework-python-latest) — HIGH confidence (official docs, updated 2026-01-08)
- [Azure AI Foundry Agents: agent-framework integration](https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-types/azure-ai-foundry-agent) — HIGH confidence (official docs, updated 2026-02-17)
- [Connected Agents documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) — HIGH confidence; local function tools limitation explicitly stated
- [azure-ai-agents Python client library README](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-agents-readme?view=azure-python) — HIGH confidence; streaming and AsyncFunctionTool patterns
- [AG-UI Integration with Agent Framework](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/) — HIGH confidence; AgentResponseUpdate → AG-UI event mapping unchanged
- [Connected Agents removed in new Foundry](https://learn.microsoft.com/en-us/answers/questions/5631003/new-ai-foundry-experience-no-more-connected-agents) — MEDIUM confidence (community Q&A)
- [Foundry Multi-Agent Workflows announcement](https://devblogs.microsoft.com/foundry/introducing-multi-agent-workflows-in-foundry-agent-service/) — MEDIUM confidence; confirms new orchestration model
- Local SDK inspection: `/Users/willmacdonald/Documents/Code/claude/second-brain/backend/.venv/lib/python3.12/site-packages/agent_framework/azure/__init__.py` — HIGH confidence; confirms AzureAIAgentClient lazy import from `agent_framework_azure_ai`

---

*Architecture research for: The Active Second Brain — Foundry Agent Service Migration*
*Researched: 2026-02-25*
