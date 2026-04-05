# Architecture Patterns

**Domain:** Observability investigation agent + eval framework for existing capture-and-intelligence system
**Researched:** 2026-04-04
**Overall Confidence:** HIGH (existing architecture well-understood, target APIs verified with official docs)

---

## Existing Architecture Snapshot

Before describing new components, here is the current system as shipped in v3.0:

```
Mobile (Expo/RN)                    Backend (FastAPI on ACA)
+-----------------+                 +-----------------------------------+
| Capture Screen  |--POST /capture->| capture.py (SSE StreamingResponse)|
| (text/voice)    |<---SSE events---| adapter.py (AG-UI protocol)      |
+-----------------+                 |   |                               |
| Inbox Screen    |--GET/PATCH----->| inbox.py                         |
+-----------------+                 |   |                               |
| Status Screen   |--GET /errands-->| errands.py -> admin_handoff.py   |
+-----------------+                 |   (triggers Admin Agent)         |
                                    +---+------+--------+--------------+
                                        |      |        |
                              +---------+   +--+--+  +--+------+
                              | Foundry |   |Cosmos|  |App      |
                              | Agent   |   |DB    |  |Insights |
                              | Service |   |9 cont|  |(OTel)   |
                              +---------+   +------+  +---------+
```

**Key integration surfaces for new features:**
- `main.py` lifespan: all client initialization, app.state wiring
- `api/` routers: FastAPI endpoints, each gets clients from `request.app.state`
- `streaming/adapter.py`: SSE generator pattern for AG-UI protocol
- `streaming/sse.py`: SSE event helper functions (step_start, classified, complete, etc.)
- `db/cosmos.py`: CosmosManager with `get_container()` for 9 containers
- `processing/admin_handoff.py`: background processing pattern (fire-and-forget via asyncio.create_task)
- OTel already wired: `azure-monitor-opentelemetry` + `enable_instrumentation()`
- `agents/middleware.py`: AuditAgentMiddleware and ToolTimingMiddleware applied to all agent clients
- Existing KQL queries in `backend/queries/` (system-health, capture-trace, admin-agent-audit, recent-failures)

**Existing agents:**
1. **Classifier Agent** -- persistent, streaming, @tools: `file_capture`, `transcribe_audio`
2. **Admin Agent** -- persistent, non-streaming (called in background), @tools: `add_errand_items`, `add_task_items`, `get_routing_context`, `manage_destination`, `manage_affinity_rule`, `query_rules`, `fetch_recipe_url`

---

## Recommended Architecture: v3.1 Additions

### System Overview (new components in bold)

```
Mobile (Expo/RN)                         Backend (FastAPI on ACA)
+-------------------+                    +--------------------------------------+
| Capture Screen    |--POST /capture---->| capture.py (existing)                |
| + **Feedback UI** |--POST /feedback--->| **api/feedback.py** (NEW)            |
+-------------------+                    |                                      |
| Inbox Screen      |--GET /inbox------->| inbox.py (existing)                  |
| + **Feedback btn**|--POST /feedback--->| **api/feedback.py** (NEW)            |
+-------------------+                    |                                      |
| Status Screen     |--GET /errands----->| errands.py (existing)                |
+-------------------+                    |                                      |
| **Insights Tab**  |--POST /insights--->| **api/insights.py** (NEW)            |
| (chat + dashboard)|<---SSE events------| **streaming/insights_adapter.py**    |
|                   |--GET /insights/    |                                      |
|                   |   dashboard-------->| **api/insights.py** (dashboard data) |
+-------------------+                    +---+-------+--------+-------+--------+
                                             |       |        |       |
                                   +---------+  +----+--+  +--+--+ +--+------+
                                   | Foundry |  |Cosmos  |  |App  | |**Evals**|
                                   | Agent   |  |DB      |  |Ins. | |  (CLI)  |
                                   | Service |  |+Feedbk |  |Query| +---------+
                                   |+**Inv.**|  |+Evals  |  |API  |
                                   +---------+  |+Golden |  +-----+
                                                +--------+

Claude Code (local, via MCP)
+-------------------+
| **MCP Server**    |--stdio-->| **mcp/server.py** (NEW standalone)     |
| (query system     |          | Uses azure-monitor-query directly      |
|  health, traces)  |          | Auth: az login / DefaultAzureCredential|
+-------------------+          +----------------------------------------+
```

### Component Boundaries

| Component | Status | Responsibility | Communicates With |
|-----------|--------|---------------|-------------------|
| `api/feedback.py` | **NEW** | Collect explicit feedback (thumbs up/down, correct bucket) on captures | Cosmos DB (Feedback container), mobile app |
| `api/insights.py` | **NEW** | Chat endpoint for investigation agent + dashboard summary endpoint | App Insights (via azure-monitor-query), Foundry Agent Service, mobile |
| `streaming/insights_adapter.py` | **NEW** | SSE streaming for investigation agent responses (text deltas, not classification) | insights.py, AG-UI protocol to mobile |
| `agents/investigator.py` | **NEW** | Investigation Agent registration + prompt management | Foundry Agent Service |
| `tools/insights.py` | **NEW** | @tool functions: `query_captures`, `get_system_health`, `get_bucket_distribution`, `trace_capture` | App Insights Query API, Cosmos DB |
| `evals/` | **NEW** | Eval framework: golden datasets, custom evaluators, eval runner CLI | Azure AI Evaluation SDK, Cosmos DB, App Insights |
| `mcp/server.py` | **NEW (standalone)** | Claude Code MCP tool for querying App Insights | App Insights Query API (direct, not via backend) |
| `models/feedback.py` | **NEW** | Pydantic models for FeedbackDocument, EvalResultDocument, GoldenDatasetDocument | Cosmos DB |
| Mobile: Insights tab | **NEW** | Chat UI + dashboard cards for investigation agent | Backend /insights endpoints |
| Mobile: Feedback buttons | **MODIFY inbox** | Thumbs up/down on inbox detail card | Backend /feedback endpoint |

---

## Data Flow

### 1. Investigation Agent -- Mobile Chat

```
User types question in Insights tab: "How many captures failed today?"
    |
    v
POST /api/insights/chat { question, thread_id? }
    |
    v
insights.py creates Message, calls Investigation Agent (streaming)
    |
    v
Agent reasons, calls @tools as needed:
  - query_captures(bucket?, status?, timespan_hours, limit)
      -> Constructs KQL internally, runs via LogsQueryClient
  - get_system_health()
      -> Runs pre-built KQL: capture volume, success rate, error count, latency
  - trace_capture(trace_id)
      -> Runs capture-trace KQL + reads Cosmos inbox doc
  - get_bucket_distribution(timespan_hours)
      -> Returns classification distribution
    |
    v
insights_adapter.py streams AG-UI events:
  STEP_START("Investigating")
  TEXT_MESSAGE_CONTENT (delta streaming of agent's answer)
  STEP_END("Investigating")
  COMPLETE
    |
    v
Mobile Insights tab renders streaming text (ChatGPT-style)
```

**Key difference from capture flow:** The investigation agent streams natural language text responses, not classification outcomes. Uses `TEXT_MESSAGE_CONTENT` events with delta streaming. No CLASSIFIED/MISUNDERSTOOD/LOW_CONFIDENCE events.

**Thread persistence:** Investigation agent threads are short-lived. No need to persist foundryThreadId to Cosmos -- conversations are ephemeral Q&A, not follow-up flows.

### 2. Investigation Agent -- MCP Tool for Claude Code

```
Claude Code invokes MCP tool: query_second_brain("show me capture failures today")
    |
    v
mcp/server.py (stdio transport, local Python process)
    |
    v
Uses azure-monitor-query LogsQueryClient directly
    - DefaultAzureCredential (az login locally)
    - Runs KQL against Log Analytics workspace
    |
    v
Returns formatted text results to Claude Code
```

**Why standalone process, not backend API:** The MCP server runs as a local stdio child process spawned by Claude Code. Going through the deployed backend would require: (a) API key management for a dev tool, (b) unnecessary network round-trip local->ACA->App Insights, (c) exposing raw KQL as a backend endpoint. The MCP server queries App Insights directly, which is simpler and faster.

**MCP tools exposed:**
- `query_app_insights(kql, timespan_hours)` -- raw KQL (safe because single-user dev tool, guarded with timeout + row limit)
- `get_system_health()` -- pre-built dashboard summary
- `recent_captures(limit)` -- recent captures with outcomes
- `trace_capture(trace_id)` -- full lifecycle trace for a specific capture
- `recent_errors(hours)` -- error-level logs

### 3. Dashboard Summary

```
User opens Insights tab
    |
    v
GET /api/insights/dashboard
    |
    v
insights.py runs pre-built KQL queries via LogsQueryClient:
  - Capture volume (24h, by hour)
  - Success rate (2xx vs 4xx/5xx)
  - Bucket distribution (pie chart data)
  - Admin Agent stats (processed, failed, retry count)
  - Error count
  - P50/P90 latency
    |
    v
Returns JSON:
{
  "captureCount24h": 15,
  "successRate": 93.3,
  "bucketDistribution": {"Admin": 8, "Ideas": 3, "Projects": 2, "People": 2},
  "adminStats": {"processed": 7, "failed": 1, "retried": 1},
  "errorCount": 2,
  "latencyP50Ms": 1850,
  "latencyP90Ms": 3200
}
```

### 4. Feedback Collection

```
User views inbox item detail
    |
    v
Taps thumbs-up (correct) or thumbs-down (wrong bucket) + selects correct bucket
    |
    v
POST /api/feedback {
    inboxItemId: "abc-123",
    feedbackType: "correct" | "wrong_bucket",
    correctBucket?: "Ideas",    // only if wrong_bucket
    captureTraceId?: "trace-xyz"
}
    |
    v
feedback.py writes FeedbackDocument to Cosmos Feedback container
    |
    v
(Later) eval runner reads Feedback to compute explicit accuracy metrics
```

### 5. Eval Pipeline

```
Triggered: manually (uv run -m second_brain.evals.runner) or GitHub Actions cron

    |
    v
evals/runner.py loads data from three sources:
    |
    +-- 1. Golden dataset (Cosmos GoldenDataset container)
    |       Curated captures with expected bucket, expected confidence range
    |
    +-- 2. Implicit signals (App Insights via KQL)
    |       - Misunderstood rate, safety-net rate, low-confidence rate
    |       - Recategorize rate (from Inbox PATCH logs)
    |       - Admin Agent retry/failure rate
    |
    +-- 3. Explicit feedback (Cosmos Feedback container)
    |       - Thumbs up/down counts
    |       - Wrong bucket corrections with correct_bucket
    |
    v
Classifier evals:
  - BucketAccuracyEvaluator (custom code-based): correct bucket vs golden dataset
  - ConfidenceCalibrationEvaluator (custom code-based): confidence vs actual accuracy
  - F1ScoreEvaluator (built-in): bucket prediction as text match
  - ImplicitSignalEvaluator (custom code-based): misunderstood/safety-net rates as scores
    |
    v
Admin Agent evals:
  - TaskAdherenceEvaluator (built-in): did agent complete the processing task?
  - ToolCallAccuracyEvaluator (built-in): did agent call the right tools?
  - ErrandRoutingAccuracyEvaluator (custom code-based): items routed to correct destinations
    |
    v
Results written to:
  1. Cosmos EvalResults container (historical tracking)
  2. App Insights custom metrics (for Azure Monitor alert triggers)
    |
    v
If scores below threshold -> Azure Monitor scheduled query alert fires
```

---

## New Cosmos DB Containers

| Container | Partition Key | Purpose | Document Shape |
|-----------|--------------|---------|----------------|
| `Feedback` | `/userId` | Explicit user feedback on captures | `{id, userId, inboxItemId, feedbackType, correctBucket?, captureTraceId, createdAt}` |
| `EvalResults` | `/evalRunId` | Eval run results for historical tracking | `{id, evalRunId, timestamp, evaluatorName, score, details, metrics}` |
| `GoldenDataset` | `/userId` | Curated capture examples with expected outcomes | `{id, userId, rawText, expectedBucket, expectedConfidenceRange, tags, createdAt}` |

---

## New Azure Resources

| Resource | Purpose | Notes |
|----------|---------|-------|
| Investigation Agent (Foundry) | Third persistent agent | Same pattern as Classifier + Admin Agent. Managed via `ensure_investigator_agent()` |
| Log Analytics Reader RBAC | Allow KQL queries from backend + MCP tool | Already have workspace-based App Insights. Grant `Log Analytics Reader` to Container App managed identity (backend) and local dev credential (MCP tool) |

No new Azure resources beyond the Foundry agent and RBAC grant. The Log Analytics workspace already exists.

---

## Patterns to Follow

### Pattern 1: Third Persistent Agent (Investigation Agent)

**What:** Register a third persistent Foundry agent alongside Classifier and Admin Agent, using the identical `ensure_*_agent()` + `AzureAIAgentClient` pattern.

**When:** The investigation agent answers questions about system health, capture history, and agent behavior.

**Why this pattern:** The existing codebase has two agents registered in `main.py` lifespan with `ensure_*_agent()`, separate `AzureAIAgentClient` instances with middleware, and local @tool execution. Following the same pattern minimizes new patterns to learn and maintains consistency.

```python
# agents/investigator.py -- mirrors agents/classifier.py and agents/admin.py
INVESTIGATOR_INSTRUCTIONS = """You are the Investigation Agent for the Second Brain system.
You answer questions about system health, capture history, classification accuracy,
and agent behavior by querying Application Insights and Cosmos DB.

When asked about system health, call get_system_health().
When asked about specific captures, call query_captures() or trace_capture().
When asked about bucket distribution, call get_bucket_distribution().

Always present data clearly with counts, percentages, and time ranges.
If a query returns no results, say so explicitly.
"""

async def ensure_investigator_agent(
    foundry_client: AzureAIAgentClient,
    stored_agent_id: str = "",
) -> str:
    """Register or verify the Investigation Agent in Foundry."""
    # Same pattern as ensure_classifier_agent / ensure_admin_agent
    ...
```

```python
# main.py lifespan additions:
# --- LogsQueryClient for App Insights queries ---
from azure.monitor.query.aio import LogsQueryClient as AsyncLogsQueryClient

logs_client = AsyncLogsQueryClient(credential=credential)
app.state.logs_client = logs_client

# --- Investigation Agent ---
investigator_agent_id = await ensure_investigator_agent(
    foundry_client=foundry_client,
    stored_agent_id=settings.azure_ai_investigator_agent_id,
)
insights_tools = InsightsTools(
    logs_client=logs_client,
    workspace_id=settings.log_analytics_workspace_id,
    cosmos_manager=cosmos_mgr,
)
investigator_client = AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    agent_id=investigator_agent_id,
    should_cleanup_agent=False,
    middleware=[AuditAgentMiddleware(), ToolTimingMiddleware()],
)
app.state.investigator_client = investigator_client
app.state.insights_tools = insights_tools
app.state.investigator_agent_tools = [
    insights_tools.query_captures,
    insights_tools.get_system_health,
    insights_tools.get_bucket_distribution,
    insights_tools.trace_capture,
]
```

### Pattern 2: SSE Streaming for Investigation (Reuse AG-UI Protocol)

**What:** Stream investigation agent responses to the mobile app using the same SSE + AG-UI event protocol the capture flow uses.

**When:** Mobile Insights tab sends a chat message to the investigation agent.

**Why:** The mobile app already has `ag-ui-client.ts` with `attachCallbacks()` that handles STEP_START, TEXT_MESSAGE_CONTENT, STEP_END, COMPLETE, ERROR. Reusing this protocol means minimal new client-side parsing.

**Key difference from capture flow:** Investigation streams natural language text, not classification events. Use `TEXT_MESSAGE_CONTENT` with delta streaming. The existing `onTextDelta` callback in `attachCallbacks()` already handles this event type.

```python
# streaming/insights_adapter.py
async def stream_investigation(
    client: AzureAIAgentClient,
    question: str,
    tools: list,
    thread_id: str,
    run_id: str,
) -> AsyncGenerator[str, None]:
    """Stream investigation agent response as AG-UI SSE events."""
    yield encode_sse(step_start_event("Investigating"))

    messages = [Message(role="user", text=question)]
    options = ChatOptions(tools=tools)

    try:
        async with asyncio.timeout(120):  # Longer timeout for KQL queries
            stream = client.get_response(
                messages=messages, stream=True, options=options
            )
            async for update in stream:
                for content in update.contents or []:
                    if content.type == "text" and getattr(content, "text", None):
                        yield encode_sse(text_delta_event(content.text))
                    elif content.type == "function_call":
                        # Log tool calls but don't emit to client
                        ...
                    elif content.type == "function_result":
                        # Tool results consumed by agent, not streamed
                        ...

        yield encode_sse(step_end_event("Investigating"))
        yield encode_sse(complete_event(thread_id, run_id))
    except Exception as exc:
        yield encode_sse(error_event(str(exc)))
        yield encode_sse(complete_event(thread_id, run_id))
```

### Pattern 3: MCP Server as Standalone Process

**What:** A separate Python project under `mcp/` that runs as a stdio-transport MCP server for Claude Code.

**When:** Will uses Claude Code and wants to investigate system health, query captures, or debug issues without opening the mobile app or Azure portal.

**Implementation:**
```python
# mcp/server.py
from mcp.server.fastmcp import FastMCP
from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient
from datetime import timedelta

mcp = FastMCP("second-brain-insights")

# Initialize on first use (lazy)
_client = None
_workspace_id = None

def _get_client():
    global _client, _workspace_id
    if _client is None:
        import os
        _workspace_id = os.environ["LOG_ANALYTICS_WORKSPACE_ID"]
        _client = LogsQueryClient(DefaultAzureCredential())
    return _client, _workspace_id

@mcp.tool()
def query_app_insights(kql: str, timespan_hours: int = 24) -> str:
    """Run a KQL query against the Second Brain App Insights workspace.
    Use for custom investigation queries. Results limited to 100 rows."""
    client, workspace_id = _get_client()
    response = client.query_workspace(
        workspace_id=workspace_id,
        query=kql,
        timespan=timedelta(hours=timespan_hours),
        server_timeout=30,
    )
    # Format as readable table
    ...

@mcp.tool()
def get_system_health() -> str:
    """Get a dashboard summary of Second Brain health for the last 24 hours."""
    ...

@mcp.tool()
def recent_captures(limit: int = 20) -> str:
    """Show recent captures with classification outcomes."""
    ...

@mcp.tool()
def trace_capture(trace_id: str) -> str:
    """Trace a specific capture through its full lifecycle."""
    ...

@mcp.tool()
def recent_errors(hours: int = 24) -> str:
    """Show recent error-level logs and exceptions."""
    ...
```

**Claude Code configuration (project-level `.mcp.json`):**
```json
{
  "mcpServers": {
    "second-brain-insights": {
      "command": "uv",
      "args": ["--directory", "/path/to/second-brain/mcp", "run", "server.py"],
      "env": {
        "LOG_ANALYTICS_WORKSPACE_ID": "your-workspace-id"
      }
    }
  }
}
```

**Why sync not async for MCP:** The MCP SDK's stdio transport manages the event loop. The `azure-monitor-query` sync client is simpler here and avoids async complexity in a synchronous stdio context. FastMCP handles the protocol layer.

### Pattern 4: Eval as CLI + CI, Not Backend Endpoint

**What:** Run evals from a CLI command or GitHub Actions, not as a backend API.

**When:** Manually after shipping changes, or automatically on a weekly schedule.

**Why:** Evals are batch operations that take minutes. They should not run inside the FastAPI request-response cycle because:
- They use LLM judges (GPT-4o) which are slow and expensive
- They should run against the deployed system, not inside it
- GitHub Actions cron provides scheduling without infrastructure
- CLI entry point keeps eval code testable in isolation

```python
# evals/runner.py (CLI entry point)
import asyncio
import json
from azure.ai.evaluation import evaluate, F1ScoreEvaluator
from second_brain.evals.evaluators import (
    BucketAccuracyEvaluator,
    ConfidenceCalibrationEvaluator,
    ImplicitSignalEvaluator,
)

async def run_classifier_evals(golden_dataset_path: str) -> dict:
    """Run Classifier accuracy evals against a golden dataset."""
    result = evaluate(
        data=golden_dataset_path,
        evaluators={
            "bucket_accuracy": BucketAccuracyEvaluator(),
            "confidence_calibration": ConfidenceCalibrationEvaluator(),
            "f1_score": F1ScoreEvaluator(),
        },
        azure_ai_project=os.environ.get("AZURE_AI_PROJECT"),
    )
    return result

if __name__ == "__main__":
    # Usage: uv run -m second_brain.evals.runner --classifier --golden golden.jsonl
    ...
```

### Pattern 5: Implicit Signal Collection (Zero-Effort Feedback)

**What:** Derive quality signals from actions Will already takes, without requiring explicit feedback for every capture.

**When:** Always, automatically, as part of normal operation.

**Why:** Single user, limited patience for rating every capture. The system already logs rich signals:

| Implicit Signal | Source | What It Means | Already Logged? |
|----------------|--------|---------------|-----------------|
| Recategorize | Inbox PATCH /recategorize | Classifier got bucket wrong | YES (App Insights) |
| Safety-net fire | adapter.py `_safety_net_file_as_misunderstood` | Classifier failed to call file_capture | YES (logger.warning) |
| Low-confidence | adapter.py `low_confidence_event` | Classifier uncertain | YES (OTel span attribute) |
| Misunderstood | adapter.py `misunderstood_event` | Classifier confused | YES (OTel span attribute) |
| Admin retry | admin_handoff.py retry logic | Admin Agent needed second attempt | YES (logger.warning + span) |
| Admin failed | admin_handoff.py `_mark_inbox_failed` | Admin Agent couldn't process | YES (logger.error + span) |
| Swipe-to-delete inbox | inbox.py DELETE | Capture was junk | YES (App Insights request log) |

The eval pipeline reads these with KQL queries from App Insights. No new write paths needed -- all signals are already in the telemetry.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Investigation Agent Generates Raw KQL

**What:** Letting the LLM write arbitrary KQL and executing it against App Insights.

**Why bad:** KQL injection risk, unpredictable query cost (timeouts, massive result sets), and LLMs frequently get KQL syntax wrong (table names, operators, date functions).

**Instead:** The Investigation Agent calls @tool functions that accept structured parameters (bucket, status, timespan, limit) and construct KQL internally. The tools use parameterized query templates with validated inputs.

```python
# GOOD: Parameterized tool for the Investigation Agent
@tool
async def query_captures(
    bucket: str | None = None,
    status: str | None = None,
    timespan_hours: int = 24,
    limit: int = 20,
) -> str:
    """Query recent captures with optional filters."""
    filters = []
    if bucket:
        filters.append(f'| where customDimensions.bucket == "{bucket}"')
    if status:
        filters.append(f'| where customDimensions.status == "{status}"')
    kql = f"""
    traces
    | where timestamp > ago({timespan_hours}h)
    | where customDimensions.component == "classifier"
    {chr(10).join(filters)}
    | project timestamp, message, customDimensions
    | order by timestamp desc
    | take {min(limit, 50)}
    """
    # Execute via LogsQueryClient
    ...
```

**Exception for MCP tool:** The Claude Code MCP tool CAN expose a raw KQL tool because: (a) Will is the only user and Claude Code is a developer tool, (b) it is guarded with `server_timeout=30` and `| take 100` appended.

### Anti-Pattern 2: Eval Framework as Backend Background Service

**What:** Running evals continuously inside the FastAPI backend as a recurring background task.

**Why bad:** Evals use LLM judges (GPT-4o) which are slow (~5-10 seconds per eval item) and consume the same deployment used for captures. Running them as a background service creates unpredictable load spikes, makes failures invisible, and conflates the eval concern with the serving concern.

**Instead:** Evals run as a separate CLI process or GitHub Actions job. They execute against the deployed system from outside, not inside.

### Anti-Pattern 3: Storing Eval Scores on Inbox Documents

**What:** Adding eval score fields to existing InboxDocument.

**Why bad:** Conflates capture data with eval metadata. Inbox documents are the system of record for captures; eval results are a separate analytical concern. Mixing them pollutes the capture schema and makes both harder to query.

**Instead:** Store eval results in a dedicated `EvalResults` container. Link to captures by `captureTraceId` when needed.

### Anti-Pattern 4: Backend API as Proxy for MCP Server

**What:** Having the MCP server call the deployed backend API for App Insights data.

**Why bad:** Adds unnecessary complexity: MCP server (local) -> HTTPS to ACA -> backend proxies to App Insights. The backend doesn't expose raw KQL and shouldn't. API key auth adds friction for a dev tool.

**Instead:** MCP server queries App Insights directly using `azure-monitor-query` with `DefaultAzureCredential` (`az login` locally). One hop, no auth management.

### Anti-Pattern 5: Single "Observability Agent" for Both Mobile and MCP

**What:** Using the same agent/code path for both the mobile investigation chat and the Claude Code MCP tool.

**Why bad:** Different users, different needs. The mobile chat is conversational (natural language in, natural language out, streaming SSE). The MCP tool is programmatic (Claude Code formulates queries, needs structured data back). Forcing both through the same agent creates prompt conflicts and response format issues.

**Instead:** Two separate implementations:
- **Investigation Agent (Foundry)** for mobile chat: persistent agent, streaming, @tools with parameterized queries, natural language responses
- **MCP server** for Claude Code: standalone process, raw KQL capability, structured text output, no agent framework overhead

---

## Integration Points Summary

### New Components -> Existing (what new code touches)

| New Component | Existing Component | Integration Type |
|---------------|-------------------|------------------|
| `api/insights.py` | `main.py` lifespan | Router registration + investigator client/tools init |
| `api/insights.py` | `streaming/sse.py` | Reuse existing SSE event helpers (step_start, step_end, complete, error) + new text_delta |
| `api/insights.py` | `auth.py` | Same API key middleware (existing) |
| `api/feedback.py` | `main.py` lifespan | Router registration |
| `api/feedback.py` | `db/cosmos.py` | New container: Feedback |
| `agents/investigator.py` | `agents/classifier.py` pattern | Same ensure_agent pattern |
| `agents/investigator.py` | `agents/middleware.py` | Same AuditAgentMiddleware + ToolTimingMiddleware |
| `tools/insights.py` | `db/cosmos.py` | Read from Inbox + bucket containers for capture queries |
| `evals/runner.py` | `config.py` | Read settings for Azure endpoints |
| `evals/evaluators.py` | `models/documents.py` | Uses InboxDocument schema for golden dataset structure |
| Mobile Insights tab | `ag-ui-client.ts` | Reuse attachCallbacks + SSE pattern (TEXT_MESSAGE_CONTENT events) |
| Mobile feedback buttons | New POST handler (not SSE) | Simple fetch() call to /api/feedback |

### Modifications to Existing Code

| Existing File | Modification | Reason |
|---------------|-------------|--------|
| `main.py` | Add: LogsQueryClient init, investigator agent init, insights/feedback routers | Lifespan wiring for investigation agent + feedback collection |
| `config.py` | Add: `azure_ai_investigator_agent_id`, `log_analytics_workspace_id` | Investigation agent needs agent ID + workspace ID |
| `db/cosmos.py` | Add: `Feedback`, `EvalResults`, `GoldenDataset` to CONTAINER_NAMES | New containers (same init pattern) |
| `models/documents.py` | Add: FeedbackDocument, EvalResultDocument, GoldenDatasetDocument | New Pydantic models for new containers |
| `streaming/sse.py` | Add: `text_delta_event()` helper function | Investigation agent streams text, not classification events |
| `pyproject.toml` | Add: `azure-monitor-query`, `azure-ai-evaluation` (optional dep) | New SDK dependencies |
| Mobile `(tabs)/_layout.tsx` | Add: Insights tab | New tab in tab navigator |
| Mobile inbox detail component | Add: thumbs-up/down buttons | Feedback collection surface |

### Unchanged Components

| Component | Why Unchanged |
|-----------|---------------|
| `api/capture.py` | Capture flow unaffected |
| `streaming/adapter.py` | Capture streaming unaffected |
| `agents/classifier.py` | Classifier agent unchanged |
| `agents/admin.py` | Admin agent unchanged |
| `tools/classification.py` | Classification tools unchanged |
| `tools/admin.py` | Admin tools unchanged |
| `processing/admin_handoff.py` | Admin processing unchanged |
| `api/errands.py` | Errands API unchanged |
| `api/inbox.py` | Inbox API unchanged |

---

## Scalability Considerations

| Concern | Current (1 user) | Notes |
|---------|-------------------|-------|
| App Insights query rate | ~10-20 queries/day (chat + dashboard) | Log Analytics API allows 200 requests/30s per user. No concern. |
| Foundry Agent concurrent requests | 3 agents, 1 user | No concurrent pressure. Warm-up loop already handles cold starts. Add investigator to warm-up list. |
| Cosmos RU for new containers | Feedback + EvalResults + GoldenDataset | ~5 additional RU/s max. Free tier (1000 RU/s shared) has headroom. |
| Eval pipeline cost | Weekly runs, ~50-100 golden items | ~$0.50-1.50/run with GPT-4o judge. Acceptable for hobby project. |
| MCP server resource usage | Local process, on-demand | Zero cost when not in use. Spawned/killed by Claude Code. |
| Dashboard KQL queries | 6 queries per dashboard load | ~2-3 seconds total. Cache on mobile side (stale-while-revalidate pattern). |

---

## Suggested Build Order

Based on dependency analysis:

### Phase A: Foundation (enables everything else)
1. **App Insights Query API integration** -- Add `azure-monitor-query` dependency, `LogsQueryClient` init in lifespan, `tools/insights.py` with parameterized query functions, `log_analytics_workspace_id` in config.
2. **New Cosmos containers** -- Add Feedback, EvalResults, GoldenDataset to CosmosManager + Pydantic models.

### Phase B: Investigation Agent (highest user value)
3. **Investigation Agent registration** -- `agents/investigator.py`, config setting, third persistent agent in Foundry, lifespan wiring.
4. **Investigation Agent streaming** -- `api/insights.py` chat endpoint + `streaming/insights_adapter.py` + `text_delta_event()` in sse.py.
5. **Mobile Insights tab -- chat** -- Chat UI that reuses AG-UI SSE client with TEXT_MESSAGE_CONTENT handling.

### Phase C: Dashboard (complements investigation)
6. **Dashboard endpoint** -- `GET /api/insights/dashboard` with pre-built KQL queries returning summary JSON.
7. **Mobile Insights tab -- dashboard** -- Dashboard cards above the chat interface.

### Phase D: MCP Tool (developer experience, parallel-safe)
8. **MCP server for Claude Code** -- Standalone `mcp/server.py` with raw KQL, system health, capture tracing, recent errors. Independent of all other phases.

### Phase E: Feedback Collection
9. **Feedback API** -- `api/feedback.py` endpoint, FeedbackDocument model, Cosmos writes.
10. **Mobile feedback UI** -- Thumbs up/down on inbox detail card, POST to feedback endpoint.

### Phase F: Eval Framework
11. **Golden dataset seeding** -- CLI tool to curate captures from Inbox into GoldenDataset container.
12. **Custom evaluators** -- BucketAccuracyEvaluator, ConfidenceCalibrationEvaluator, ImplicitSignalEvaluator, ErrandRoutingAccuracyEvaluator.
13. **Eval runner CLI** -- `uv run -m second_brain.evals.runner` entry point using azure-ai-evaluation.
14. **Admin Agent evals** -- TaskAdherenceEvaluator + ToolCallAccuracyEvaluator with AIAgentConverter.

### Phase G: Self-Monitoring Loop
15. **Eval CI integration** -- GitHub Actions workflow for weekly scheduled eval runs.
16. **Alert on regression** -- Azure Monitor scheduled query alert when eval scores drop below threshold.
17. **Eval trends in dashboard** -- Add eval score history to Insights dashboard.

**Phase ordering rationale:**
- Phase A must come first: LogsQueryClient and Cosmos containers are prerequisites for everything.
- Phase B is the highest-value user-facing feature: asking the system "what happened?" in natural language.
- Phase C builds on Phase A's query infrastructure and complements Phase B's chat with at-a-glance metrics.
- Phase D is fully independent (standalone process) and can run in parallel with B/C, but is lower priority (developer convenience vs user feature).
- Phase E needs containers from Phase A but is otherwise independent. It collects data that Phase F consumes.
- Phase F depends on Phase E (explicit feedback) + Phase A (implicit signals from App Insights) + golden dataset curation.
- Phase G closes the loop: automated eval runs + alerts when quality degrades + trend visibility.

---

## Sources

- [Azure Monitor Query client library for Python](https://learn.microsoft.com/en-us/python/api/overview/azure/monitor-query-readme?view=azure-python) -- LogsQueryClient, async client, KQL query execution, workspace querying (HIGH confidence, official docs, updated 2025-07-30)
- [Azure AI Evaluation SDK -- Local Evaluation](https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk) -- evaluate() function, built-in evaluators, custom evaluators, data formats (HIGH confidence, official docs, updated 2026-02-25)
- [Azure AI Evaluation SDK -- Agent Evaluation](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/agent-evaluate-sdk?view=foundry-classic) -- IntentResolutionEvaluator, ToolCallAccuracyEvaluator, TaskAdherenceEvaluator, AIAgentConverter for Foundry agents (HIGH confidence, official docs, updated 2026-03-19)
- [Custom Evaluators](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/evaluation-evaluators/custom-evaluators?view=foundry-classic) -- Code-based and prompt-based custom evaluator patterns (HIGH confidence, official docs, updated 2026-03-19)
- [MCP Server Build Guide](https://modelcontextprotocol.io/docs/develop/build-server) -- FastMCP Python SDK, stdio transport, @mcp.tool() decorator (HIGH confidence, official docs)
- [Claude Code MCP Documentation](https://code.claude.com/docs/en/mcp) -- Connecting MCP servers to Claude Code (HIGH confidence, official docs)
- [azure-ai-evaluation on PyPI](https://pypi.org/project/azure-ai-evaluation/) -- Package version and installation (HIGH confidence)
- [azure-monitor-query on PyPI](https://pypi.org/project/azure-monitor-query/) -- Package version, async support via azure-monitor-query[aio] (HIGH confidence)
- Existing codebase: `backend/src/second_brain/` -- All current patterns verified by reading source (HIGH confidence)
- Existing KQL queries: `backend/queries/*.kql` -- system-health, capture-trace, admin-agent-audit, recent-failures (HIGH confidence, used as templates for new query tools)
