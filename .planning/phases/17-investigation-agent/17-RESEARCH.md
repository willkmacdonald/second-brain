# Phase 17: Investigation Agent - Research

**Researched:** 2026-04-05
**Domain:** Azure AI Agent Service (Assistants API) + KQL tool functions + SSE streaming
**Confidence:** HIGH

## Summary

Phase 17 adds a third Azure AI Foundry assistant -- the Investigation Agent -- that answers natural language questions about captures and system health. The agent receives user questions, decides which KQL tools to call, the backend executes those KQL queries against App Insights via the existing `LogsQueryClient` (from Phase 16), returns results to the assistant, and the assistant formats human-readable answers that stream as SSE events to the client.

The existing codebase provides almost all infrastructure needed. Phase 16 established `LogsQueryClient`, `execute_kql()`, KQL templates (CAPTURE_TRACE, RECENT_FAILURES, SYSTEM_HEALTH, ADMIN_AUDIT_LOG), and Pydantic result models. The agent-framework SDK handles tool execution automatically -- when the assistant makes a `tool_calls` request, the SDK executes the `@tool`-decorated Python functions and submits results back to the assistant, which then generates text. The streaming adapter pattern from the Classifier can be adapted: instead of suppressing text output as reasoning, the Investigation Agent streams text tokens to the client as SSE `text` events.

Key differences from existing agents: (1) text output is the primary deliverable, not a side effect; (2) tools return data for the assistant to format, not perform side effects; (3) multi-turn conversation threads managed by client-provided `thread_id`; (4) SSE event types are different (`thinking`, `tool_call`, `tool_error`, `text`, `done`) rather than the capture-specific events.

**Primary recommendation:** Create four `@tool` functions in `tools/investigation.py` wrapping the existing observability queries with parameterized time windows, a new streaming adapter in `streaming/investigation_adapter.py` that yields SSE text events, a `POST /api/investigate` endpoint, agent registration in `agents/investigation.py`, and lifespan wiring in `main.py`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Answer Style & Depth**: Clinical tone, data-focused, no casual language. Default narrative summary; tables for error reports (Time, Component, Error, Trace ID). System health includes snapshot + trend comparison. Full trace IDs. Usage data as text with numbers. Confidence indicator when answer required interpretation. Suggest 1-2 follow-up questions at end of each response.
- **Query Boundaries**: Default 24h when unspecified. Out-of-scope queries explain scope. No results: suggest widening time range. Result cap: 10 items maximum, always mention total count.
- **Agent Architecture**: New Azure OpenAI Assistants API assistant (third). Named "Investigation Agent". System prompt managed in Foundry portal. Multi-turn conversation threads. Backend intercepts tool_calls, executes KQL via LogsQueryClient, returns results to assistant.
- **KQL Tool Design**: One tool per query type (not general-purpose):
  1. `trace_lifecycle` -- Given trace ID or "last capture", full pipeline with timing
  2. `recent_errors` -- Errors/exceptions with component attribution, trace IDs, timestamps
  3. `system_health` -- Error rates, capture volume, P95/P99 latency, success rates with trend comparison
  4. `usage_patterns` -- Capture counts by period, bucket distribution, destination usage
- **Strongly typed parameters**: enums for time ranges, component names, severity levels -- no freeform strings
- **Streaming & API**: SSE endpoint `POST /api/investigate`. Request body: `{question, thread_id?}`. SSE event types: `thinking`, `tool_call`, `tool_error`, `text`, `done`. Client-managed thread_id. Same auth pattern.
- **Error Handling & Resilience**: Partial results on partial tool failure. Failed tool calls visible as `tool_error` events. SSE break: send error event. App Insights unreachable: HTTP 503.
- **Rate Limiting & Cost**: Soft limit 10 queries/minute (warn but don't block). Log token usage and KQL count to App Insights.
- **Thread Lifecycle**: Threads persist indefinitely. Assistants API manages context window. Client stores thread_id locally. New thread by omitting thread_id.

### Claude's Discretion
- Exact KQL query templates and parameterization
- SSE implementation details (chunking, keepalive intervals)
- Assistant system prompt wording
- Error message exact phrasing
- Soft rate limit implementation approach

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INV-01 | User can ask NL questions about captures and get human-readable answers | Investigation Agent with `trace_lifecycle` tool + SSE streaming adapter + `POST /api/investigate` endpoint |
| INV-02 | User can trace a specific capture's full lifecycle by providing a trace ID | `trace_lifecycle` tool wrapping existing `CAPTURE_TRACE` KQL template with timing extraction |
| INV-03 | User can view recent failures and errors with trace IDs and component attribution | `recent_errors` tool wrapping existing `RECENT_FAILURES` KQL template (enhanced with component attribution) |
| INV-04 | User can query system health (error rates, capture volume, latency trends) | `system_health` tool wrapping existing `SYSTEM_HEALTH` KQL template (enhanced with P95/P99 and trend comparison) |
| INV-05 | User can query usage insights (capture counts by period, destination usage, bucket distribution) | `usage_patterns` tool with NEW KQL template (no existing template -- must be created) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `agent-framework-azure-ai` | (existing) | AzureAIAgentClient for Investigation Agent | Already used for Classifier and Admin agents. Handles thread management, tool execution, streaming. |
| `azure-monitor-query` | `>=2.0.0` (existing) | LogsQueryClient for KQL execution | Already installed and wired in Phase 16. Async variant in lifespan. |
| `azure.ai.agents` | (transitive) | Thread creation, agent runs, streaming events | Underlying Azure AI Agent SDK. Handles `conversation_id` -> thread mapping. |
| `fastapi` | (existing) | SSE streaming endpoint | StreamingResponse pattern already used for capture endpoints. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `opentelemetry` | (existing) | OTel spans for investigation queries | Tracing investigation requests in App Insights. |
| `pydantic` | (existing) | Request/response models, tool parameter types | Request body validation, KQL result models. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| agent-framework `@tool` decorator | Direct Azure AI Agents API | `@tool` is the established project pattern, handles serialization automatically. Direct API would mean manual JSON schema definition and tool output submission. |
| SSE for streaming | WebSocket | SSE is the established project pattern. Mobile app uses react-native-sse. No reason to introduce WebSocket complexity. |

**Installation:**
No new dependencies needed. All required packages are already installed.

## Architecture Patterns

### Recommended Project Structure
```
backend/src/second_brain/
├── agents/
│   ├── investigation.py      # NEW: ensure_investigation_agent()
│   └── ...
├── tools/
│   ├── investigation.py      # NEW: InvestigationTools class with 4 @tool functions
│   └── ...
├── streaming/
│   ├── investigation_adapter.py  # NEW: SSE streaming adapter for investigation
│   └── ...
├── api/
│   ├── investigate.py        # NEW: POST /api/investigate endpoint
│   └── ...
├── observability/
│   ├── kql_templates.py      # MODIFIED: add USAGE_PATTERNS template, enhance SYSTEM_HEALTH
│   ├── queries.py            # MODIFIED: add query_usage_patterns(), enhance existing queries
│   ├── models.py             # MODIFIED: add UsagePatternRecord model
│   └── ...
└── main.py                   # MODIFIED: wire investigation agent in lifespan
```

### Pattern 1: Tool Function as KQL Wrapper
**What:** Each `@tool` function wraps an `execute_kql()` call with parameterized time window and returns structured data for the assistant to format.
**When to use:** Every Investigation Agent tool.
**Why:** Tools return data (not formatted text). The assistant has the instructions and context to format data appropriately. This separates data retrieval from presentation.

```python
# Source: Existing project pattern (tools/classification.py, tools/admin.py)
from agent_framework import tool
from typing import Annotated
from pydantic import Field

class InvestigationTools:
    def __init__(self, logs_client, workspace_id: str) -> None:
        self._logs_client = logs_client
        self._workspace_id = workspace_id

    @tool(approval_mode="never_require")
    async def recent_errors(
        self,
        time_range: Annotated[
            str,
            Field(description="Time range: '1h', '6h', '24h', '3d', '7d'"),
        ] = "24h",
        component: Annotated[
            str | None,
            Field(description="Filter by component: 'classifier', 'admin_agent', 'capture', or null for all"),
        ] = None,
        severity: Annotated[
            str,
            Field(description="Minimum severity: 'warning' or 'error'"),
        ] = "error",
    ) -> str:
        """Query recent errors and exceptions from App Insights."""
        timespan = _parse_time_range(time_range)
        # Execute KQL with parameterized filters
        result = await execute_kql(self._logs_client, self._workspace_id, query, timespan)
        # Return as JSON string for the assistant to format
        return json.dumps(records, default=str)
```

### Pattern 2: SSE Streaming Adapter for Text Output
**What:** Unlike the Classifier adapter (which suppresses text), the Investigation adapter streams text tokens to the client.
**When to use:** The `POST /api/investigate` endpoint.
**Key difference from Classifier:** Text content from the assistant is the primary output, yielded as `text` SSE events.

```python
# Adapted from existing streaming/adapter.py pattern
async def stream_investigation(
    client: AzureAIAgentClient,
    question: str,
    tools: list,
    thread_id: str | None,
) -> AsyncGenerator[str, None]:
    messages = [Message(role="user", text=question)]
    options: ChatOptions = {
        "tools": tools,
        "conversation_id": thread_id,  # Reuse existing thread for follow-ups
    }

    yield encode_sse({"type": "thinking"})

    stream = client.get_response(messages=messages, stream=True, options=options)
    async for update in stream:
        for content in update.contents or []:
            if content.type == "text" and getattr(content, "text", None):
                yield encode_sse({"type": "text", "content": content.text})
            elif content.type == "function_call":
                name = getattr(content, "name", None)
                yield encode_sse({"type": "tool_call", "tool": name})
            elif content.type == "function_result":
                # Tool results go back to the assistant automatically
                pass

    yield encode_sse({"type": "done", "thread_id": final_thread_id})
```

### Pattern 3: Thread Management via conversation_id
**What:** The agent-framework SDK maps `conversation_id` in ChatOptions to an Azure AI Agent Service thread.
**When to use:** Multi-turn investigation conversations.
**Key behavior:** When `conversation_id` is provided, the SDK reuses the existing thread. When omitted, a new thread is created. The SDK returns the thread ID in `update.conversation_id`.

```python
options: ChatOptions = {
    "tools": tools,
}
if thread_id:
    options["conversation_id"] = thread_id
# SDK creates thread if not provided, returns thread_id in stream updates
```

### Pattern 4: Agent Registration (Non-Fatal)
**What:** Like the Admin Agent, the Investigation Agent registration is non-fatal.
**When to use:** `main.py` lifespan.
**Why:** Investigation is a diagnostic feature, not part of the core capture flow. If registration fails, the app should still start.

```python
# Same pattern as ensure_admin_agent()
async def ensure_investigation_agent(
    foundry_client: AzureAIAgentClient,
    stored_agent_id: str,
) -> str:
    """Ensure the Investigation agent exists in Foundry. Non-fatal."""
    ...
```

### Anti-Patterns to Avoid
- **Generating KQL in the assistant:** The CONTEXT.md locks tools as parameterized queries, not free-form KQL. The assistant should NEVER write raw KQL. Each tool has a fixed template with typed parameters.
- **Returning formatted text from tools:** Tools return structured data (JSON). The assistant formats for human consumption. This keeps tool logic testable and deterministic.
- **Blocking the event loop with KQL queries:** Always use the async LogsQueryClient already in place.
- **Creating threads server-side:** Thread IDs are client-managed. The backend does not persist thread IDs in Cosmos. The Assistants API manages thread lifecycle.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread management | Custom thread storage in Cosmos | Assistants API threads via `conversation_id` | The SDK handles thread creation, message history, context window limits. Client stores thread_id locally. |
| Tool execution loop | Manual tool_calls interception + submission | agent-framework `@tool` decorator + auto-execution | The SDK's `FunctionInvocationLayer` handles the requires_action -> execute -> submit cycle automatically. |
| SSE encoding | Custom SSE implementation | Existing `encode_sse()` from `streaming/sse.py` | Already battle-tested with the mobile app. |
| KQL execution | Custom HTTP calls to Log Analytics | Existing `execute_kql()` from `observability/queries.py` | Handles partial results, timeouts, table parsing. |
| Rate limiting | Complex distributed rate limiter | Simple in-memory sliding window counter | Single-user app. A `collections.deque` with timestamps is sufficient. Warn via SSE event, don't block. |
| Time range parsing | Complex datetime parsing | Simple dict mapping of enum values to `timedelta` | `{"1h": timedelta(hours=1), "6h": timedelta(hours=6), ...}` -- 5 lines of code. |

**Key insight:** Phase 16 built the observability query infrastructure. Phase 17 wraps it in agent tools and adds a streaming endpoint. Almost no new infrastructure is needed.

## Common Pitfalls

### Pitfall 1: Text vs Reasoning -- Wrong SSE Event Type
**What goes wrong:** The Classifier adapter suppresses all text content as reasoning. The Investigation Agent's text IS the answer.
**Why it happens:** Copy-pasting the Classifier adapter pattern.
**How to avoid:** The Investigation adapter must yield `text` SSE events for text content, not log-and-suppress. Be explicit in the adapter: text content = yield to client.
**Warning signs:** Test user asks a question, gets no visible response text.

### Pitfall 2: Thread ID Not Returned to Client
**What goes wrong:** Client can't continue a conversation because it never received the thread_id for the new thread.
**Why it happens:** The SDK creates threads lazily. The thread_id comes from `update.conversation_id` in the stream, which appears in early events. If the adapter doesn't capture and return it, the client has no way to continue.
**How to avoid:** Capture `conversation_id` from the first stream update that has it. Include it in the `done` SSE event.
**Warning signs:** First question works, follow-up fails with "thread not found".

### Pitfall 3: KQL Query Timeout Under Agent Timeout
**What goes wrong:** The agent's 60-second timeout fires before the KQL query completes, losing partial results.
**Why it happens:** `execute_kql()` has its own `server_timeout=60`, and the agent stream has a 60-second `asyncio.timeout`. They can race.
**How to avoid:** Set KQL `server_timeout` to 30 seconds (well under the 60-second agent timeout). This gives the agent time to receive results and format a response.
**Warning signs:** Intermittent "agent failed" errors on complex queries.

### Pitfall 4: Workspace Schema vs Portal Schema
**What goes wrong:** New KQL templates for usage_patterns accidentally use portal schema (AppTraces, AppRequests).
**Why it happens:** Copying from Azure portal query editor which uses portal schema.
**How to avoid:** All KQL templates MUST use workspace schema (traces, requests, dependencies, exceptions). This was established in Phase 16. The `kql_templates.py` header documents the field mapping.
**Warning signs:** KQL queries return empty results.

### Pitfall 5: Missing LogsQueryClient Guard
**What goes wrong:** Investigation endpoint crashes when LogsQueryClient is None (e.g., workspace ID not configured).
**Why it happens:** LogsQueryClient initialization is non-fatal in lifespan. If it fails, `app.state.logs_client` is None.
**How to avoid:** Check `logs_client` availability at the endpoint level. Return HTTP 503 ("App Insights is unreachable") per CONTEXT.md decision.
**Warning signs:** 500 errors in production when App Insights credential expires.

### Pitfall 6: tool_choice "required" on Investigation Agent
**What goes wrong:** Forcing the agent to always call a tool means it can't answer simple questions like "thanks" or "what can you help with?"
**Why it happens:** Copying the Classifier pattern which uses `tool_choice: {mode: "required"}`.
**How to avoid:** Investigation Agent should use `tool_choice: "auto"` (or omit it, which defaults to auto). The agent decides when to call tools.
**Warning signs:** Agent calls a random tool when the user says "thank you".

### Pitfall 7: App Insights Ingestion Delay
**What goes wrong:** User asks "what happened to my last capture?" and gets no results, even though they just captured something.
**Why it happens:** App Insights has a 2-5 minute ingestion delay. Recent events may not appear in KQL queries immediately.
**How to avoid:** Document this in the Investigation Agent's system prompt: "Note: there may be a 2-5 minute delay before the most recent events appear in telemetry data."
**Warning signs:** "Last capture" queries consistently fail for very recent captures.

## Code Examples

### InvestigationTools Class Structure
```python
# Source: Pattern from tools/classification.py and tools/admin.py
import json
import logging
from datetime import timedelta
from typing import Annotated

from agent_framework import tool
from azure.monitor.query.aio import LogsQueryClient
from pydantic import Field

from second_brain.observability.queries import execute_kql

logger = logging.getLogger(__name__)

TIME_RANGE_MAP: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "3d": timedelta(days=3),
    "7d": timedelta(days=7),
}


class InvestigationTools:
    """Investigation tools bound to LogsQueryClient for App Insights queries."""

    def __init__(
        self,
        logs_client: LogsQueryClient,
        workspace_id: str,
    ) -> None:
        self._logs_client = logs_client
        self._workspace_id = workspace_id

    @tool(approval_mode="never_require")
    async def trace_lifecycle(
        self,
        trace_id: Annotated[
            str | None,
            Field(description="Capture trace ID (UUID). Use null for 'last capture'."),
        ] = None,
    ) -> str:
        """Trace a capture's full lifecycle: classification, filing, admin processing."""
        # If trace_id is None, query for the most recent capture trace ID first
        ...

    @tool(approval_mode="never_require")
    async def recent_errors(
        self,
        time_range: Annotated[
            str,
            Field(description="Time range: '1h', '6h', '24h', '3d', '7d'"),
        ] = "24h",
        component: Annotated[
            str | None,
            Field(description="Component filter: 'classifier', 'admin_agent', 'capture', or null for all"),
        ] = None,
    ) -> str:
        """Query recent errors and exceptions with component attribution."""
        ...

    @tool(approval_mode="never_require")
    async def system_health(
        self,
        time_range: Annotated[
            str,
            Field(description="Time range: '1h', '6h', '24h', '3d', '7d'"),
        ] = "24h",
    ) -> str:
        """Query system health: error rates, capture volume, latency, success rates."""
        ...

    @tool(approval_mode="never_require")
    async def usage_patterns(
        self,
        time_range: Annotated[
            str,
            Field(description="Time range: '24h', '3d', '7d'"),
        ] = "7d",
        group_by: Annotated[
            str,
            Field(description="Group by: 'day', 'hour', 'bucket', 'destination'"),
        ] = "day",
    ) -> str:
        """Query usage patterns: capture counts, bucket distribution, destination usage."""
        ...
```

### SSE Event Types for Investigation
```python
# Source: Adapted from streaming/sse.py pattern
def thinking_event() -> dict:
    return {"type": "thinking"}

def tool_call_event(tool_name: str, description: str) -> dict:
    return {"type": "tool_call", "tool": tool_name, "description": description}

def tool_error_event(tool_name: str, error: str) -> dict:
    return {"type": "tool_error", "tool": tool_name, "error": error}

def text_event(content: str) -> dict:
    return {"type": "text", "content": content}

def done_event(thread_id: str) -> dict:
    return {"type": "done", "thread_id": thread_id}
```

### POST /api/investigate Endpoint
```python
# Source: Adapted from api/capture.py pattern
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

class InvestigateBody(BaseModel):
    question: str = Field(..., max_length=5000)
    thread_id: str | None = None

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

@router.post("/api/investigate")
async def investigate(request: Request, body: InvestigateBody) -> StreamingResponse:
    logs_client = request.app.state.logs_client
    if logs_client is None:
        raise HTTPException(503, "App Insights is unreachable. Investigation is unavailable.")

    investigation_client = request.app.state.investigation_client
    if investigation_client is None:
        raise HTTPException(503, "Investigation agent is unavailable.")

    generator = stream_investigation(
        client=investigation_client,
        question=body.question,
        tools=request.app.state.investigation_tools,
        thread_id=body.thread_id,
    )
    return StreamingResponse(generator, media_type="text/event-stream", headers=SSE_HEADERS)
```

### Soft Rate Limiter
```python
# Source: Standard sliding window pattern
import time
from collections import deque

class SoftRateLimiter:
    """Warn-only rate limiter using sliding window."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: deque[float] = deque()

    def check(self) -> bool:
        """Returns True if within limit, False if over (warn only)."""
        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] > self._window:
            self._timestamps.popleft()
        self._timestamps.append(now)
        return len(self._timestamps) <= self._max
```

### Enhanced SYSTEM_HEALTH KQL with P95/P99 and Trend
```sql
-- Source: Enhanced from existing kql_templates.py SYSTEM_HEALTH
let current_period = requests
| where name has "/api/capture"
| where timestamp > ago({time_range});
let previous_period = requests
| where name has "/api/capture"
| where timestamp between (ago(2 * {time_range}) .. ago({time_range}));
let current_stats = current_period
| summarize
    capture_count = count(),
    successful_count = countif(toint(resultCode) >= 200 and toint(resultCode) < 400),
    error_count = countif(toint(resultCode) >= 500),
    avg_duration_ms = avg(duration),
    p95_duration_ms = percentile(duration, 95),
    p99_duration_ms = percentile(duration, 99);
let previous_stats = previous_period
| summarize
    prev_capture_count = count(),
    prev_error_count = countif(toint(resultCode) >= 500);
-- Both periods joined for trend comparison
```

### New USAGE_PATTERNS KQL Template
```sql
-- Source: New template for INV-05
-- Captures by period
requests
| where name has "/api/capture"
| summarize capture_count = count() by bin(timestamp, {bin_size})
| order by timestamp asc

-- Bucket distribution
traces
| where customDimensions.component == "classifier"
| where message has "Filed to"
| extend bucket = extract("Filed to (\\w+)", 1, message)
| where isnotempty(bucket)
| summarize count() by bucket

-- Destination usage
traces
| where customDimensions.component == "admin_agent"
| where message has "Added"
| extend destination = extract("to (\\w+)", 1, message)
| summarize count() by destination
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Azure OpenAI Assistants API | Azure AI Agent Service (via agent-framework SDK) | Feb 2026 | Same underlying API, but SDK abstracts thread/run management. The project already uses the new SDK. |
| Manual tool_calls handling | `@tool` decorator with auto-execution | agent-framework RC (early 2026) | No need to manually intercept REQUIRES_ACTION and submit tool outputs. SDK handles it. |
| Portal KQL schema (AppTraces) | Workspace KQL schema (traces) | Phase 16 (Apr 2026) | All KQL templates already migrated. New templates must follow workspace schema. |

**Deprecated/outdated:**
- Assistants API: Deprecated, retiring Aug 2026. This project already uses Azure AI Agent Service via agent-framework SDK (compatible replacement).
- Portal KQL schema: Still works in Azure portal, but programmatic queries must use workspace schema.

## Open Questions

1. **"Last capture" resolution**
   - What we know: `trace_lifecycle` tool needs to support "last capture" (trace_id=null). This requires querying for the most recent capture trace ID first.
   - What's unclear: Best KQL query to find the most recent capture trace ID. Could use `requests | where name has "/api/capture" | top 1 by timestamp | project customDimensions.capture_trace_id`, but the trace ID might be in different fields.
   - Recommendation: Add a helper KQL template `LATEST_CAPTURE_TRACE_ID` that finds the most recent capture trace ID from requests. Test against actual data after deployment.

2. **P95/P99 latency in SYSTEM_HEALTH**
   - What we know: CONTEXT.md requires P95/P99 latency. The existing SYSTEM_HEALTH template only has `avg(duration)`.
   - What's unclear: Whether KQL `percentile()` function works correctly with the `print` statement pattern used in the existing template.
   - Recommendation: Restructure SYSTEM_HEALTH as a `summarize` query instead of `print` with `toscalar()` calls. The `summarize` approach supports `percentile()` directly.

3. **Trend comparison period**
   - What we know: CONTEXT.md requires system health with "trend comparison to previous period".
   - What's unclear: How to efficiently do two-period comparison in a single KQL query.
   - Recommendation: Use two `let` statements for current and previous periods, then join or union the results. The tool function can make two `execute_kql()` calls if a single-query approach is too complex.

## Sources

### Primary (HIGH confidence)
- **Existing codebase** (verified by reading): `agents/classifier.py`, `agents/admin.py`, `tools/classification.py`, `tools/admin.py`, `streaming/adapter.py`, `observability/queries.py`, `observability/kql_templates.py`, `api/capture.py`, `main.py`
- **agent-framework SDK** (verified by reading installed package): `agent_framework_azure_ai/_chat_client.py` -- thread management via `conversation_id` in ChatOptions, `_process_stream()` event handling, auto tool execution
- **Phase 16 RESEARCH.md** (verified): `azure-monitor-query>=2.0.0`, workspace schema, `LogsQueryClient` async patterns

### Secondary (MEDIUM confidence)
- [Azure AI Agents client library for Python](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-agents-readme?view=azure-python) -- Thread and conversation lifecycle
- [Azure Monitor Query client library for Python](https://learn.microsoft.com/en-us/python/api/overview/azure/monitor-query-readme?view=azure-python) -- `query_workspace()` timespan options
- [Microsoft Agent Framework RC announcement](https://devblogs.microsoft.com/foundry/microsoft-agent-framework-reaches-release-candidate/) -- SDK capabilities and agent types

### Tertiary (LOW confidence)
- None -- all findings verified against installed SDK code or official docs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and used in project
- Architecture: HIGH - patterns directly adapted from existing Classifier and Admin agent implementations
- Pitfalls: HIGH - derived from hands-on analysis of existing streaming adapter and SDK behavior
- KQL templates: MEDIUM - new templates (USAGE_PATTERNS, enhanced SYSTEM_HEALTH) need validation against actual App Insights data

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (30 days -- stable stack, no expected breaking changes)
