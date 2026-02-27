# Phase 9: HITL Parity and Observability - Research

**Researched:** 2026-02-27
**Domain:** HITL classification flows (low-confidence pending, misunderstood conversational follow-up, recategorize from inbox), Azure Application Insights observability via OpenTelemetry, agent-framework SDK conversation/threading
**Confidence:** HIGH

## Summary

Phase 9 requires two parallel work streams: (1) implementing three backend endpoints that the mobile app already calls but which do not exist on the v2 backend (`/api/ag-ui/respond`, `/api/ag-ui/follow-up`, and updating the existing recategorize endpoint to match v1 behavior), and (2) upgrading the middleware skeleton in `agents/middleware.py` to emit structured OpenTelemetry traces/metrics that flow to Application Insights.

The mobile client code is already fully wired for all three HITL flows. `sendClarification()` POSTs to `/api/ag-ui/respond` and `sendFollowUp()` POSTs to `/api/ag-ui/follow-up` -- both functions are implemented and called from `text.tsx` (capture screen) and `inbox.tsx`. The recategorize flow already works end-to-end via `PATCH /api/inbox/{item_id}/recategorize`. The primary gap is backend: the `/api/ag-ui/respond` and `/api/ag-ui/follow-up` SSE endpoints do not exist in v2.

For the misunderstood flow, the CONTEXT.md decision is to reuse the same Foundry thread (not create a new one). The `agent-framework` SDK supports this via `conversation_id` in `ChatOptions` -- passing the same `conversation_id` to subsequent `get_response()` calls appends to the existing Foundry thread. The `ChatResponseUpdate.conversation_id` field on streaming responses carries the Foundry thread ID, which the adapter captures from the initial classification stream and stores in the inbox document for use in follow-up calls.

For observability, the agent-framework SDK provides `enable_instrumentation()` from `agent_framework.observability` which, when called after `configure_azure_monitor()`, enables built-in OpenTelemetry spans and metrics for all `get_response()` calls. This automatically tracks `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, and `gen_ai.operation.duration` -- covering the OBSV-02 requirement. The existing middleware skeleton (`AuditAgentMiddleware`, `ToolTimingMiddleware`) should be upgraded to emit custom spans with classification-specific dimensions (bucket, confidence, status, item_id) for per-capture trace granularity (OBSV-01).

**Primary recommendation:** Build two new SSE streaming endpoints (`/api/capture/respond` and `/api/capture/follow-up`) that reuse the existing `stream_text_capture` async generator pattern. Enable `agent_framework.observability.enable_instrumentation()` in `main.py` after `configure_azure_monitor()`. Upgrade middleware to use `opentelemetry.trace` spans with custom attributes for classification metadata. Keep recategorize as-is (PATCH endpoint, already works).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Misunderstood flow threading: Reuse the same Foundry thread for follow-up conversation (not a new thread). Agent sees its own classification attempt and the user's responses in thread history. Auto re-classify after each user reply -- agent attempts classification on every message and files as soon as confident. No limit on follow-up exchanges -- conversation continues until classified or user navigates away (same as v1).
- Low-confidence filing behavior: Pending items wait forever until user acts -- no auto-timeout (same as v1). Bucket buttons in inbox highlight the Classifier's top guess, other buckets shown as secondary (same as v1). Tapping a bucket button is instant confirm -- no SSE streaming steps, just immediate success toast + item update. After confirmation, item stays in inbox with classified status (not removed).
- Recategorize mechanics: Label change only -- update bucket field in Cosmos DB. No specialist agent re-processing (that's Phase 10). Available for ALL inbox item statuses: classified, pending, misunderstood (same as v1).
- Observability: Token usage + latency per classification (no cost calculation). Per-capture trace granularity -- one trace covers full lifecycle from capture received to filing. Manual App Insights queries only -- no automated alerting. Instrument both: middleware traces (AgentMiddleware, FunctionMiddleware) AND endpoint-level traces (capture, respond, recategorize).

### Claude's Discretion
- Recategorize endpoint contract design (keep v1 PATCH shape or redesign for v2)
- Data model for recategorize audit trail (preserve original classification vs overwrite)

### Deferred Ideas (OUT OF SCOPE)
- Natural language agent for querying App Insights (ask questions in English, agent executes KQL queries) -- future phase beyond v2.0
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HITL-01 | Low-confidence captures filed as pending with bucket buttons for recategorization (direct Cosmos write, unchanged) | The `file_capture` tool already files with `status="pending"` when confidence is low. Pending items appear in inbox with orange status dot. The CONTEXT.md decision is "instant confirm" -- tapping a bucket button should call the existing recategorize PATCH endpoint (no SSE streaming). The mobile `handlePendingResolve()` currently calls `sendClarification()` which POSTs to `/api/ag-ui/respond` -- this needs to be changed to a simple PATCH call to the existing recategorize endpoint for instant filing. |
| HITL-02 | Misunderstood captures trigger conversational follow-up using fresh Foundry thread (no conversation history contamination) | **UPDATED by CONTEXT.md**: Decision changed to "reuse same thread" (not fresh thread). The `agent-framework` SDK supports this via `conversation_id` in `ChatOptions`. The initial classification stream returns a `conversation_id` in `ChatResponseUpdate` which is the Foundry thread ID. Storing this in the inbox document and passing it to the follow-up endpoint's `get_response(options={"conversation_id": stored_thread_id})` appends to the same Foundry thread. The agent sees its prior classification attempt and the user's responses. |
| HITL-03 | Recategorize from inbox detail card works end-to-end (direct Cosmos write, unchanged) | Already implemented and working in v2 at `PATCH /api/inbox/{item_id}/recategorize`. The three-step cross-container move (create new bucket doc, update inbox metadata, delete old bucket doc) handles all cases. Recommendation: keep the current PATCH contract unchanged -- it already matches v1 behavior. |
| OBSV-01 | Application Insights receives traces from Foundry agent runs with per-classification visibility | The `agent-framework` SDK provides `enable_instrumentation()` which emits OTel spans for every `get_response()` call. Combined with the existing `configure_azure_monitor()`, these traces flow to App Insights automatically. The middleware skeleton (`AuditAgentMiddleware`, `ToolTimingMiddleware`) should be upgraded to create custom OTel spans with classification-specific attributes (bucket, confidence, status, item_id) for per-capture querying. |
| OBSV-02 | Token usage and cost metrics visible in Foundry portal or Application Insights | The `agent-framework` SDK's `enable_instrumentation()` automatically tracks `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens` as OTel metrics. The `ChatResponseUpdate` stream also includes `Content.type == "usage"` items with `usage_details` containing `input_token_count`, `output_token_count`, `total_token_count`. These flow to App Insights via the Azure Monitor OTel distro without additional code. Cost calculation is explicitly out of scope per CONTEXT.md. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `agent-framework-azure-ai` | `1.0.0rc2` | `AzureAIAgentClient.get_response()` with `conversation_id` for thread reuse | Already installed; provides thread continuation via ChatOptions |
| `agent-framework` (core) | `1.0.0rc2` | `enable_instrumentation()`, `AgentMiddleware`, `FunctionMiddleware`, `Content` | Already installed; built-in OTel observability layer |
| `azure-monitor-opentelemetry` | `>=1.8.6` | `configure_azure_monitor()` -- OTel distro for App Insights | Already installed and called in main.py |
| `opentelemetry-api` | (transitive) | `trace.get_tracer()`, custom spans with attributes | Transitive dep of azure-monitor-opentelemetry |
| `fastapi` | existing | SSE streaming endpoints, PATCH endpoint | Already installed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `azure-core-tracing-opentelemetry` | existing | Automatic tracing for Azure SDK calls (Cosmos, Blob) | Already installed; auto-instruments Azure SDK HTTP calls |

### NOT Needed
| Library | Reason |
|---------|--------|
| `opentelemetry-sdk` | Already configured by `azure-monitor-opentelemetry`; no manual SDK setup needed |
| `azure-monitor-opentelemetry-exporter` | Included in `azure-monitor-opentelemetry` distro |
| Any new packages | All dependencies for Phase 9 are already installed |

**Installation:**
No new packages needed.

## Architecture Patterns

### Recommended Changes to Project Structure
```
backend/src/second_brain/
  api/
    capture.py         # ADD: /api/capture/respond endpoint, /api/capture/follow-up endpoint
  streaming/
    adapter.py         # ADD: stream_follow_up_capture() async generator
  agents/
    middleware.py      # UPDATE: OTel spans + custom attributes replacing console logging
  models/
    documents.py       # UPDATE: Add foundryThreadId field to InboxDocument
  main.py             # UPDATE: Add enable_instrumentation() call after configure_azure_monitor()
```

### Pattern 1: Misunderstood Follow-Up with Thread Reuse

**What:** The follow-up endpoint receives the inbox item ID and follow-up text. It looks up the stored Foundry thread ID from the inbox document, then calls `get_response()` with `conversation_id` in `ChatOptions` to append to the same Foundry thread.

**When to use:** For the `/api/capture/follow-up` endpoint.

**How `conversation_id` works in agent-framework:**
- Source: Verified from `agent_framework_azure_ai._client.py` lines 586-589
- `_get_current_conversation_id()` resolves: `options.get("conversation_id")` or `kwargs.get("conversation_id")` or `self.conversation_id`
- The resolved conversation_id is passed as `previous_response_id` to the Azure AI Responses API, which appends to the existing thread
- `ChatResponseUpdate.conversation_id` on streaming responses carries the Foundry thread ID back

**Example:**
```python
# Source: Verified from agent-framework-azure-ai 1.0.0rc2 source code

async def stream_follow_up_capture(
    client: AzureAIAgentClient,
    follow_up_text: str,
    foundry_thread_id: str,
    tools: list,
    thread_id: str,
    run_id: str,
) -> AsyncGenerator[str, None]:
    """Stream a follow-up classification attempt on the same Foundry thread.

    Reuses the existing Foundry thread so the agent sees prior conversation
    history (its classification attempt + user's responses).
    """
    messages = [Message(role="user", text=follow_up_text)]
    options: ChatOptions = {
        "tools": tools,
        "conversation_id": foundry_thread_id,  # Reuse same thread
    }

    yield encode_sse(step_start_event("Classifying"))

    # ... same outcome tracking pattern as stream_text_capture ...

    async with asyncio.timeout(60):
        stream = client.get_response(
            messages=messages, stream=True, options=options
        )
        # ... iterate and detect outcomes ...
```

### Pattern 2: Capturing Foundry Thread ID from Stream

**What:** During the initial text capture stream, capture the `conversation_id` from `ChatResponseUpdate` objects. This is the Foundry thread ID needed for follow-up calls. Store it in the inbox document's new `foundryThreadId` field.

**When to use:** Every text/voice capture stream that produces a MISUNDERSTOOD outcome.

**Example:**
```python
# Inside stream_text_capture / stream_voice_capture:
foundry_conversation_id: str | None = None

async for update in stream:
    # Capture the Foundry thread ID from the first update that has one
    if update.conversation_id and not foundry_conversation_id:
        foundry_conversation_id = update.conversation_id

    for content in update.contents or []:
        # ... existing content processing ...
        pass

# After stream completes, if MISUNDERSTOOD, include foundry_conversation_id
# in the misunderstood event so the endpoint can store it
if status == "misunderstood":
    yield encode_sse(misunderstood_event(
        thread_id=foundry_conversation_id or thread_id,
        item_id=item_id,
        question_text=question_text,
    ))
```

### Pattern 3: Low-Confidence Pending - Instant Confirm via PATCH

**What:** The CONTEXT.md decision is "instant confirm" -- tapping a bucket button should not stream SSE. Instead, the mobile app calls the existing `PATCH /api/inbox/{item_id}/recategorize` endpoint directly. This is a REST call, not SSE.

**When to use:** For resolving pending items in the inbox.

**Mobile change required:** `handlePendingResolve()` in `inbox.tsx` currently calls `sendClarification()` which POSTs to `/api/ag-ui/respond` via SSE. This should be changed to call `handleRecategorize()` which already does the PATCH call correctly. The conversation screen (`[threadId].tsx`) also needs updating for the same reason.

**Example (mobile):**
```typescript
// inbox.tsx: handlePendingResolve should use the same PATCH as recategorize
const handlePendingResolve = useCallback(
  async (itemId: string, bucket: string) => {
    // Same PATCH call as handleRecategorize -- instant, no SSE
    await handleRecategorize(itemId, bucket);
  },
  [handleRecategorize],
);
```

### Pattern 4: OpenTelemetry Custom Spans in Middleware

**What:** Upgrade the middleware skeleton to create OTel spans with classification-specific attributes. The `opentelemetry.trace` API creates spans that flow to App Insights via the already-configured Azure Monitor distro.

**When to use:** In `AuditAgentMiddleware` and `ToolTimingMiddleware`.

**Example:**
```python
from opentelemetry import trace

tracer = trace.get_tracer("second_brain.agents")

class AuditAgentMiddleware(AgentMiddleware):
    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        with tracer.start_as_current_span("classifier_agent_run") as span:
            span.set_attribute("agent.name", "Classifier")
            start = time.monotonic()

            await call_next()

            elapsed = time.monotonic() - start
            span.set_attribute("agent.duration_ms", int(elapsed * 1000))


class ToolTimingMiddleware(FunctionMiddleware):
    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        func_name = context.function.name
        with tracer.start_as_current_span(f"tool_{func_name}") as span:
            span.set_attribute("tool.name", func_name)
            start = time.monotonic()

            await call_next()

            elapsed = time.monotonic() - start
            span.set_attribute("tool.duration_ms", int(elapsed * 1000))

            # Extract classification metadata from tool result
            if func_name == "file_capture" and context.result:
                result = context.result
                if isinstance(result, dict):
                    span.set_attribute("classification.bucket", result.get("bucket", ""))
                    span.set_attribute("classification.confidence", result.get("confidence", 0.0))
                    span.set_attribute("classification.item_id", result.get("item_id", ""))
```

### Pattern 5: Endpoint-Level Trace Spans

**What:** Create a trace span at the endpoint level that covers the full capture lifecycle. Middleware spans become child spans within this parent. This gives the per-capture trace granularity the CONTEXT.md requires.

**Example:**
```python
tracer = trace.get_tracer("second_brain.api")

@router.post("/api/capture")
async def capture(request: Request, body: TextCaptureBody) -> StreamingResponse:
    with tracer.start_as_current_span("capture_text") as span:
        span.set_attribute("capture.type", "text")
        span.set_attribute("capture.thread_id", body.thread_id or "")

        # ... existing capture logic ...
```

### Pattern 6: enable_instrumentation() Integration

**What:** Call `enable_instrumentation()` from `agent_framework.observability` in `main.py` right after `configure_azure_monitor()`. This enables the SDK's built-in OTel layer which automatically traces all `get_response()` calls and records token usage metrics.

**Example:**
```python
# main.py -- after configure_azure_monitor()
from azure.monitor.opentelemetry import configure_azure_monitor
configure_azure_monitor()

from agent_framework.observability import enable_instrumentation
enable_instrumentation()
```

### Anti-Patterns to Avoid

- **DO NOT create a separate SSE endpoint for pending item confirmation:** CONTEXT.md decision is "instant confirm" -- use the existing PATCH recategorize endpoint. No SSE streaming for bucket button taps.
- **DO NOT create a new Foundry thread for follow-up:** CONTEXT.md decision is to reuse the same thread. Pass `conversation_id` in ChatOptions.
- **DO NOT build custom token counting:** The SDK's `enable_instrumentation()` handles this automatically via OTel metrics. `Content.type == "usage"` items in the stream also carry token counts.
- **DO NOT build cost calculation:** Explicitly out of scope per CONTEXT.md.
- **DO NOT build automated alerting:** Manual App Insights queries only per CONTEXT.md.
- **DO NOT store Foundry thread IDs server-side for pending items:** Pending items use instant PATCH confirm, no thread needed. Only misunderstood items need the Foundry thread ID for follow-up conversation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token usage tracking | Manual counting of input/output tokens | `enable_instrumentation()` from agent-framework | Automatically emits `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens` OTel metrics |
| Foundry thread continuation | Manual thread creation + message history management | `ChatOptions(conversation_id=foundry_thread_id)` | SDK handles appending to existing thread transparently |
| OpenTelemetry exporter setup | Manual `TracerProvider`, `SpanExporter`, etc. | `configure_azure_monitor()` (already called) | Azure Monitor distro configures everything automatically |
| Classification trace correlation | Custom correlation ID passing | OpenTelemetry parent-child span hierarchy | Endpoint span -> middleware span -> tool span automatically correlated |

**Key insight:** The heaviest lift in this phase is NOT observability -- it's the follow-up endpoint with thread reuse. Observability is mostly "turn on SDK features that are already installed but not enabled." The follow-up endpoint requires understanding how `conversation_id` flows through the agent-framework SDK and how to store/retrieve the Foundry thread ID from the inbox document.

## Common Pitfalls

### Pitfall 1: conversation_id vs thread_id Confusion

**What goes wrong:** The app's `thread_id` (a client-generated string like `thread-1709234567`) is confused with the Foundry's `conversation_id` (the actual Azure AI thread identifier returned by the service).
**Why it happens:** The `capture.py` endpoint generates `thread_id = f"thread-{uuid4()}"` which is a local identifier used in SSE events. The Foundry service generates its own thread ID, returned as `conversation_id` on `ChatResponseUpdate`.
**How to avoid:** Use the app's `thread_id` only for SSE event correlation. Use the Foundry's `conversation_id` (from `ChatResponseUpdate.conversation_id`) for follow-up thread reuse. Store the latter as `foundryThreadId` in the inbox document.
**Warning signs:** Follow-up calls create new Foundry threads instead of continuing the conversation.

### Pitfall 2: Orphaned Inbox Documents on Follow-Up Reclassification

**What goes wrong:** When the follow-up classification succeeds, `file_capture` creates a new inbox document. Now there are two inbox entries for the same capture: the original (status=misunderstood) and the new one (status=classified).
**Why it happens:** `file_capture` always creates a new inbox document. The follow-up endpoint needs post-stream reconciliation: copy classification metadata from the new doc to the original, delete the orphan, and update the bucket doc's `inboxRecordId`.
**How to avoid:** After the follow-up stream completes with a CLASSIFIED result, perform the same reconciliation logic that v1 did: (1) read the new inbox doc by its `item_id`, (2) copy its `classificationMeta` and `filedRecordId` to the original inbox doc, (3) update the original's status to "classified", (4) delete the new orphan inbox doc, (5) update the bucket doc's `inboxRecordId` to point to the original.
**Warning signs:** Duplicate inbox entries after follow-up. Original item still showing "misunderstood" status.

### Pitfall 3: Missing enable_instrumentation() Call

**What goes wrong:** Token usage and agent traces don't appear in Application Insights even though `configure_azure_monitor()` is called.
**Why it happens:** `configure_azure_monitor()` sets up the OTel exporters (traces/metrics/logs -> App Insights), but the agent-framework SDK only emits spans/metrics when `enable_instrumentation()` is called to activate the `ChatTelemetryLayer` and `AgentTelemetryLayer`.
**How to avoid:** Call `enable_instrumentation()` after `configure_azure_monitor()` in `main.py`. Order matters: Azure Monitor must configure exporters first, then agent-framework can enable instrumentation on top.
**Warning signs:** HTTP-level traces appear in App Insights (from FastAPI/uvicorn) but no `gen_ai.*` spans or metrics.

### Pitfall 4: OTel Span Context Loss in Async Generators

**What goes wrong:** Endpoint-level spans don't properly parent the middleware spans because the OTel context is lost when crossing async generator boundaries.
**Why it happens:** `StreamingResponse` runs the async generator in a separate task/coroutine. The OTel context propagation depends on `contextvars` which may not carry across task boundaries.
**How to avoid:** Create the trace span inside the async generator function (not in the endpoint handler). The generator runs within the same task as the streaming response, so context propagates correctly to middleware spans invoked during `get_response()`.
**Warning signs:** Middleware spans appear as root spans rather than children of the capture endpoint span.

### Pitfall 5: Pending Item Resolution via Wrong Endpoint

**What goes wrong:** The mobile app calls the SSE endpoint (`/api/ag-ui/respond`) for pending items, but the CONTEXT.md decision is "instant confirm" (no SSE).
**Why it happens:** The mobile code currently has `handlePendingResolve()` using `sendClarification()` which opens an SSE connection. But CONTEXT.md says tapping a bucket button should be instant.
**How to avoid:** Change `handlePendingResolve()` to use a simple `fetch` PATCH to the recategorize endpoint. Remove the SSE connection for pending resolution. The conversation screen (`[threadId].tsx`) should be repurposed or simplified.
**Warning signs:** Pending item resolution shows SSE streaming steps instead of instant success.

### Pitfall 6: InboxDocument Status Not Updated After Follow-Up

**What goes wrong:** After a successful follow-up reclassification, the original inbox item still shows `status: "misunderstood"` in the inbox list.
**Why it happens:** The reconciliation step that copies the new classification metadata to the original inbox document must also update the `status` field to "classified".
**How to avoid:** Include `item["status"] = "classified"` in the reconciliation logic, same as the recategorize endpoint does.
**Warning signs:** Items showing orange "Needs Clarification" dot forever, even after successful follow-up.

## Code Examples

### Example 1: Follow-Up Endpoint with Thread Reuse

```python
# Source: Pattern derived from capture.py + conversation_id research

class FollowUpBody(BaseModel):
    inbox_item_id: str
    follow_up_text: str
    follow_up_round: int = 1

@router.post("/api/capture/follow-up")
async def follow_up(request: Request, body: FollowUpBody) -> StreamingResponse:
    """Stream a follow-up classification attempt on the same Foundry thread."""
    cosmos_manager = request.app.state.cosmos_manager
    inbox_container = cosmos_manager.get_container("Inbox")

    # Look up the original inbox item to get the Foundry thread ID
    item = await inbox_container.read_item(
        item=body.inbox_item_id, partition_key="will"
    )
    foundry_thread_id = item.get("foundryThreadId")
    if not foundry_thread_id:
        raise HTTPException(400, "No thread ID for follow-up")

    client = request.app.state.classifier_client
    tools = request.app.state.classifier_agent_tools
    run_id = f"run-{uuid4()}"

    generator = stream_follow_up_capture(
        client=client,
        follow_up_text=body.follow_up_text,
        foundry_thread_id=foundry_thread_id,
        tools=tools,
        thread_id=foundry_thread_id,
        run_id=run_id,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
```

### Example 2: Reconciliation After Follow-Up Success

```python
# Source: Pattern derived from inbox.py recategorize + v1 follow-up logic

async def reconcile_follow_up(
    cosmos_manager: CosmosManager,
    original_inbox_id: str,
    new_inbox_id: str,
) -> None:
    """Copy classification from new doc to original, delete orphan."""
    inbox_container = cosmos_manager.get_container("Inbox")

    # Read the new doc created by file_capture
    new_doc = await inbox_container.read_item(
        item=new_inbox_id, partition_key="will"
    )

    # Read the original misunderstood doc
    original_doc = await inbox_container.read_item(
        item=original_inbox_id, partition_key="will"
    )

    # Copy classification to original
    original_doc["classificationMeta"] = new_doc.get("classificationMeta")
    original_doc["filedRecordId"] = new_doc.get("filedRecordId")
    original_doc["status"] = "classified"
    original_doc["updatedAt"] = datetime.now(UTC).isoformat()
    await inbox_container.upsert_item(body=original_doc)

    # Update bucket doc's inboxRecordId to point to original
    bucket = (new_doc.get("classificationMeta") or {}).get("bucket")
    filed_id = new_doc.get("filedRecordId")
    if bucket and filed_id:
        bucket_container = cosmos_manager.get_container(bucket)
        bucket_doc = await bucket_container.read_item(
            item=filed_id, partition_key="will"
        )
        bucket_doc["inboxRecordId"] = original_inbox_id
        await bucket_container.upsert_item(body=bucket_doc)

    # Delete orphan inbox doc
    await inbox_container.delete_item(item=new_inbox_id, partition_key="will")
```

### Example 3: Enabling Agent Framework Instrumentation

```python
# Source: agent_framework.observability (verified from installed source)
# main.py -- add after configure_azure_monitor()

from azure.monitor.opentelemetry import configure_azure_monitor
configure_azure_monitor()

from agent_framework.observability import enable_instrumentation
enable_instrumentation()  # Activates OTel spans + metrics for all get_response() calls
```

### Example 4: KQL Query for Per-Classification Traces in App Insights

```kusto
// Source: Standard App Insights KQL patterns

// Find all classification traces with token usage
traces
| where customDimensions.["gen_ai.operation.name"] == "chat"
| project
    timestamp,
    operation_Id,
    input_tokens = toint(customDimensions.["gen_ai.usage.input_tokens"]),
    output_tokens = toint(customDimensions.["gen_ai.usage.output_tokens"]),
    duration_ms = duration,
    bucket = customDimensions.["classification.bucket"],
    confidence = todouble(customDimensions.["classification.confidence"]),
    status = customDimensions.["classification.status"]
| order by timestamp desc
```

## State of the Art

| Old Approach (v1) | Current Approach (v2) | When Changed | Impact |
|---|---|---|---|
| `sendClarification` POST to `/api/ag-ui/respond` for ALL HITL | Pending: PATCH recategorize (instant), Misunderstood: POST `/api/capture/follow-up` (SSE) | Phase 9 | Cleaner separation: pending=instant, misunderstood=conversational |
| Fresh Foundry thread for follow-up | Reuse same thread via `conversation_id` | Phase 9 (CONTEXT.md decision) | Agent sees full conversation history, better classification |
| Console logging in middleware | OTel spans + metrics flowing to App Insights | Phase 9 | Structured querying of classification metrics |
| No token tracking | `enable_instrumentation()` auto-tracks tokens | Phase 9 | Per-classification token usage visible in App Insights |

## Open Questions

1. **Reconciliation complexity for the follow-up endpoint**
   - What we know: The follow-up flow must reconcile two inbox documents (original misunderstood + new classified). This is a multi-step Cosmos operation that can partially fail.
   - What's unclear: Should we use a simpler approach? e.g., instead of letting `file_capture` create a new inbox doc and then reconciling, could the follow-up endpoint pass the original inbox_item_id to `file_capture` so it updates in place?
   - Recommendation: Use the `file_capture` tool as-is (it always creates new docs) and reconcile afterward. Modifying `file_capture` would change its behavior for all flows and add complexity. The reconciliation pattern from v1 is proven. Confidence: HIGH.

2. **Where to store the Foundry thread ID**
   - What we know: The inbox document needs a `foundryThreadId` field to store the Foundry conversation ID for follow-up calls. Currently `InboxDocument` has no such field.
   - What's unclear: Should the adapter store it (by calling Cosmos after stream completes) or should the endpoint store it (by extracting it from the stream)?
   - Recommendation: The adapter should return the `foundry_conversation_id` as part of the MISUNDERSTOOD event payload (already has `threadId` field). The endpoint extracts it and writes to the inbox doc. This keeps the adapter pure (yields SSE strings) and the endpoint handles persistence. Confidence: HIGH.

3. **Recategorize audit trail**
   - What we know: CONTEXT.md gives Claude's discretion on whether to preserve original classification or overwrite. The current implementation overwrites `classificationMeta` completely.
   - Recommendation: **Overwrite** (current behavior is correct). Preserving a history would require a new field (e.g., `classificationHistory: list[ClassificationMeta]`) and adds complexity for minimal value. The Cosmos change feed already provides an audit trail if needed. The `agentChain` field in `ClassificationMeta` tracks who classified it (adding "User" when recategorized). Keep current behavior. Confidence: HIGH.

4. **Thread ID storage for initial MISUNDERSTOOD items**
   - What we know: When `file_capture` creates a misunderstood inbox item, the Foundry thread ID hasn't been stored yet. The adapter only has it after the stream completes.
   - What's unclear: The timing: `file_capture` runs mid-stream, creates the inbox doc, then the adapter sees the MISUNDERSTOOD result after stream completes.
   - Recommendation: After the stream completes and a MISUNDERSTOOD outcome is detected, the endpoint should write the `foundryThreadId` to the already-created inbox document via a separate Cosmos upsert. This is a two-step process: (1) `file_capture` creates inbox doc during stream, (2) endpoint updates it with `foundryThreadId` after stream. Confidence: HIGH.

## Sources

### Primary (HIGH confidence)
- `agent-framework-azure-ai==1.0.0rc2` source: `_client.py` -- `_get_current_conversation_id()` (line 587-589), `conversation_id` in constructor and ChatOptions
- `agent-framework==1.0.0rc2` source: `_agents.py` -- `_prepare_run_context()` (line 1050-1052) showing conversation_id flow from options to run_opts
- `agent-framework==1.0.0rc2` source: `_types.py` -- `ChatResponseUpdate.conversation_id`, `Content.type == "usage"`, `UsageDetails`
- `agent-framework==1.0.0rc2` source: `observability.py` -- `enable_instrumentation()`, `ChatTelemetryLayer`, `OtelAttr` enum with `gen_ai.*` attributes
- `agent-framework==1.0.0rc2` source: `_middleware.py` -- `AgentContext`, `FunctionInvocationContext` with result access
- `agent-framework==1.0.0rc2` source: `_sessions.py` -- `AgentSession.service_session_id` for thread ID propagation
- Backend source: `streaming/adapter.py`, `api/capture.py`, `api/inbox.py`, `agents/middleware.py`, `tools/classification.py`, `models/documents.py`
- Mobile source: `lib/ag-ui-client.ts` (sendClarification, sendFollowUp), `app/capture/text.tsx`, `app/(tabs)/inbox.tsx`, `app/conversation/[threadId].tsx`

### Secondary (MEDIUM confidence)
- OpenTelemetry Python API docs -- `trace.get_tracer()`, `span.set_attribute()` patterns
- Azure Monitor OpenTelemetry distro -- `configure_azure_monitor()` auto-configuration

### Tertiary (LOW confidence)
- Exact format of `conversation_id` returned by Foundry in streaming mode -- based on source code analysis, not empirically tested in this v2 context

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All packages already installed, source code inspected in detail
- Architecture (HITL flows): HIGH -- Mobile client code verified, backend patterns from Phase 8 research, SDK threading mechanism traced through source code
- Architecture (observability): HIGH -- `enable_instrumentation()` source code verified, OTel integration patterns from SDK docs
- Pitfalls: HIGH -- Based on v1 experience, source code analysis, and known orphan reconciliation issue
- conversation_id thread reuse: HIGH -- Traced through `_get_current_conversation_id()` to `_prepare_run_context()` to `run_opts["conversation_id"]`

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable -- agent-framework SDK is RC, patterns unlikely to change significantly)
