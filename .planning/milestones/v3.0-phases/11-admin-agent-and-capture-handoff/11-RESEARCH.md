# Phase 11: Admin Agent and Capture Handoff - Research

**Researched:** 2026-03-01
**Domain:** Async background processing, Azure AI Foundry Agent Service, fire-and-forget task patterns
**Confidence:** HIGH

## Summary

Phase 11 connects the already-registered Admin Agent (Phase 10) to the capture flow so that Admin-classified captures are silently processed in the background. The core technical challenge is implementing a fire-and-forget `asyncio.create_task` pattern within the existing SSE streaming adapter so that after the Classifier files a capture to Inbox as "Admin", the Admin Agent processes it without the user waiting or seeing any SSE events from it.

The codebase is well-structured for this work. All infrastructure exists: the Admin Agent is registered in Foundry (with `admin_client`, `admin_agent_tools` on `app.state`), the `AdminTools.add_shopping_list_items` tool writes to the `ShoppingLists` Cosmos container, and the `file_capture` tool returns `{"bucket": "Admin", "item_id": "..."}` which provides the exact data needed to trigger the handoff. The main implementation work involves: (1) adding an `adminProcessingStatus` field to `InboxDocument`, (2) creating a background processing function that runs the Admin Agent non-streaming and updates the inbox item's status, (3) wiring the fire-and-forget trigger into the streaming adapter or capture endpoint, and (4) writing the Admin Agent's system instructions in the Foundry portal.

**Primary recommendation:** Add a module-level `process_admin_capture` async function (not a class) that accepts the `admin_client`, `admin_agent_tools`, `cosmos_manager`, inbox item ID, and raw text. Call it via `asyncio.create_task` from within the streaming adapter when `bucket == "Admin"` is detected. The task reference should be stored in a set on `app.state` to prevent garbage collection.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Fire-and-forget via `asyncio.create_task` -- capture endpoint kicks off Admin Agent as a background coroutine after Classifier files to Inbox, then SSE closes immediately
- If Admin Agent fails (Azure AI timeout, tool error): log the error, leave inbox item in "failed" state. No retry mechanism. No user notification.
- No concurrency control needed -- single-user app, concurrent captures are rare
- If server restarts mid-processing, the background task is lost (acceptable for v2.1)
- Single Admin Agent call per capture -- agent receives the full capture text and splits items itself via its instructions
- Item names kept natural: whatever the user said stays as-is ("cat litter" stays "cat litter", "2% milk" stays "2% milk")
- Quantities stay inline as part of the item name ("3 cans of tuna" is the item text, no separate quantity field)
- Mixed-content captures (shopping + non-shopping): the Classifier is responsible for splitting these into separate inbox items before Admin Agent processes. Admin Agent only receives shopping-related captures.
- Store-to-category mapping lives in the Admin Agent's system instructions in the Azure AI Foundry portal (same pattern as Classifier instructions)
- Initial stores: **Jewel** (groceries, produce, dairy), **CVS** (pharmacy, toiletries), **Pet Store** (pet supplies), **Other** (catch-all for items that don't map to defined stores)
- Fixed store names only -- agent must use exactly "Jewel", "CVS", "Pet Store", or "Other". Cannot invent new store names.
- Three states: `pending` (default when filed), `processed` (Admin Agent completed successfully), `failed` (Admin Agent errored)
- Only Admin-classified inbox items get this field -- other categories (Journal, Followup, etc.) don't have it
- Not visible in mobile app this phase -- processing is silent, user just sees items appear on shopping lists
- Error details go to App Insights via Python logging, not stored on the inbox item document

### Claude's Discretion
- Exact structure of the Admin Agent's system instructions in Foundry portal
- How to wire the fire-and-forget task into the existing capture endpoint
- Error logging format and App Insights integration details

### Deferred Ideas (OUT OF SCOPE)
- Classifier multi-bucket splitting -- now Phase 11.1
- App Insights operational audit -- now Phase 14
- Retry mechanism for failed Admin Agent processing -- could add a scheduled sweep or manual retry in a future phase
- User-configurable store mapping -- letting users add/rename stores from the mobile app
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AGNT-01 | Admin Agent registered as persistent Foundry agent on startup (mirrors Classifier pattern) | Already implemented in Phase 10 (`ensure_admin_agent` in `agents/admin.py`, wired in `main.py` lifespan). Phase 11 validates it works end-to-end with instructions set in portal. |
| AGNT-03 | Admin Agent processes Inbox items classified as Admin, running silently after Classifier files to Inbox | Fire-and-forget pattern via `asyncio.create_task` after `file_capture` returns `bucket == "Admin"`. Non-streaming `get_response` call to Admin Agent with `add_shopping_list_items` tool. |
| AGNT-04 | Inbox items get a "processed" flag after Admin Agent handles them | New `adminProcessingStatus` field on `InboxDocument` with values `pending`, `processed`, `failed`. Updated via Cosmos `upsert_item` after Admin Agent completes. |
| SHOP-03 | User can capture ad hoc items ("need cat litter") that flow through Classifier -> Admin Agent -> correct store list | End-to-end flow: capture -> Classifier files to Inbox as Admin -> background task runs Admin Agent -> agent calls `add_shopping_list_items` -> items appear in ShoppingLists container. |
| SHOP-04 | Admin Agent splits multi-item captures across multiple stores from a single capture | Admin Agent receives full capture text, splits items via its instructions, calls `add_shopping_list_items` with items mapped to different stores in a single tool call. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| agent-framework-azure-ai | installed (RC) | `AzureAIAgentClient.get_response()` for non-streaming Admin Agent calls | Already used for Classifier streaming; same library for non-streaming |
| asyncio (stdlib) | Python 3.12 | `asyncio.create_task()` for fire-and-forget background processing | Standard library; no external dependency needed for simple background tasks |
| azure-cosmos | installed | Cosmos DB reads/writes for inbox status updates | Already used throughout the project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| opentelemetry | installed | OTel spans for Admin Agent background processing | Wrap background task in a span for App Insights tracing |
| logging (stdlib) | Python 3.12 | Error and info logging to App Insights | All Admin Agent processing outcomes logged |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.create_task` | FastAPI `BackgroundTasks` | BackgroundTasks runs AFTER response is sent; but we need to trigger from inside the SSE generator which doesn't have access to the BackgroundTasks dependency. `asyncio.create_task` is simpler and works from any async context. |
| `asyncio.create_task` | Celery / ARQ / dramatiq | Massive overkill for a single-user app with no retry needs. Would require Redis/broker setup. |

**No new installations needed.** All required libraries are already in `pyproject.toml`.

## Architecture Patterns

### Recommended Changes to Existing Structure
```
backend/src/second_brain/
├── agents/
│   ├── admin.py              # Already exists (ensure_admin_agent)
│   └── ...
├── api/
│   └── capture.py            # Modify: trigger background task after CLASSIFIED event
├── models/
│   └── documents.py          # Modify: add adminProcessingStatus to InboxDocument
├── processing/
│   └── admin_handoff.py      # NEW: background Admin Agent processing function
├── streaming/
│   └── adapter.py            # Modify: detect Admin bucket, pass app.state to capture
└── main.py                   # Modify: add background_tasks set, pass admin refs to adapter
```

### Pattern 1: Fire-and-Forget Background Task with Exception Handling
**What:** Run the Admin Agent asynchronously after SSE completes, with task reference tracking to prevent garbage collection.
**When to use:** When Admin-classified capture is detected in the SSE stream.

```python
# processing/admin_handoff.py
import asyncio
import logging
from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("second_brain.processing")

async def process_admin_capture(
    admin_client: AzureAIAgentClient,
    admin_tools: list,
    cosmos_manager,
    inbox_item_id: str,
    raw_text: str,
) -> None:
    """Process an Admin-classified capture in the background.

    Calls the Admin Agent (non-streaming) to parse items and route
    to shopping lists. Updates inbox item status to 'processed' or 'failed'.
    """
    with tracer.start_as_current_span("admin_agent_process") as span:
        span.set_attribute("admin.inbox_item_id", inbox_item_id)
        try:
            messages = [Message(role="user", text=raw_text)]
            options = ChatOptions(tools=admin_tools)

            response = await admin_client.get_response(
                messages=messages, options=options
            )

            # Update inbox item status to processed
            inbox_container = cosmos_manager.get_container("Inbox")
            doc = await inbox_container.read_item(
                item=inbox_item_id, partition_key="will"
            )
            doc["adminProcessingStatus"] = "processed"
            await inbox_container.upsert_item(body=doc)

            span.set_attribute("admin.outcome", "processed")
            logger.info(
                "Admin Agent processed inbox item %s: %s",
                inbox_item_id,
                response.text[:100] if response.text else "(no text)",
            )

        except Exception as exc:
            span.record_exception(exc)
            span.set_attribute("admin.outcome", "failed")
            logger.error(
                "Admin Agent failed for inbox item %s: %s",
                inbox_item_id,
                exc,
                exc_info=True,
            )

            # Update inbox item status to failed
            try:
                inbox_container = cosmos_manager.get_container("Inbox")
                doc = await inbox_container.read_item(
                    item=inbox_item_id, partition_key="will"
                )
                doc["adminProcessingStatus"] = "failed"
                await inbox_container.upsert_item(body=doc)
            except Exception as update_exc:
                logger.error(
                    "Failed to update inbox status to 'failed' for %s: %s",
                    inbox_item_id,
                    update_exc,
                )
```

### Pattern 2: Task Reference Tracking
**What:** Keep strong references to background tasks to prevent garbage collection and enable exception logging.
**When to use:** In `main.py` lifespan, initialize a set; in the trigger point, add tasks to it.

```python
# In main.py lifespan:
app.state.background_tasks = set()

# At the trigger point (adapter or capture endpoint):
task = asyncio.create_task(
    process_admin_capture(
        admin_client=admin_client,
        admin_tools=admin_tools,
        cosmos_manager=cosmos_manager,
        inbox_item_id=item_id,
        raw_text=raw_text,
    )
)
app.state.background_tasks.add(task)
task.add_done_callback(app.state.background_tasks.discard)
```

### Pattern 3: Where to Trigger the Background Task
**What:** The handoff trigger point -- where in the existing flow to detect Admin classification and spawn the background task.
**When to use:** After `file_capture` tool returns with `bucket == "Admin"`.

There are two viable trigger points:

**Option A: In `_stream_with_thread_id_persistence` wrapper (capture.py)**
The wrapper already inspects SSE event payloads. Add Admin detection here. The wrapper has access to `request.app.state` (indirectly via `cosmos_manager` parameter -- would need to pass additional references).

**Option B: In `stream_text_capture` / `stream_voice_capture` (adapter.py)**
The adapter already detects `file_capture` tool calls and knows the bucket. Emit the background task from here after detecting `bucket == "Admin"`.

**Recommendation: Option B (adapter.py)** is cleaner because:
- The adapter already parses `detected_tool_args` and knows the bucket and item_id
- It avoids double-parsing of SSE event JSON
- The adapter functions already receive `cosmos_manager`; they just need `admin_client` and `admin_agent_tools` added to their signatures
- The background task is triggered right after the `CLASSIFIED` event is emitted, before `COMPLETE`

**However**, `asyncio.create_task` needs the admin client references, which currently live on `app.state`. The adapter functions don't receive `app.state`. Two approaches:
1. **Pass admin refs as parameters** to `stream_text_capture` and `stream_voice_capture`
2. **Pass a callback function** that the adapter calls to trigger admin processing

Approach 1 is more explicit and testable.

### Anti-Patterns to Avoid
- **Blocking the SSE stream on Admin Agent work:** The Admin Agent call takes 3-10 seconds. Never `await` it in the streaming generator. Use `create_task` only.
- **Forgetting task references:** Without storing in a set, Python may garbage-collect the task before it completes, causing silent failures.
- **Catching Exception too broadly in the background task:** Always log with `exc_info=True` so the full traceback appears in App Insights.
- **Re-using the Classifier's Foundry thread:** The Admin Agent must use a fresh thread (no `conversation_id` in options). It has its own `AzureAIAgentClient` instance.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Background task tracking | Custom task manager with queues | `asyncio.create_task` + set + `add_done_callback` | Standard Python pattern; no need for a framework |
| Agent non-streaming call | Manual HTTP calls to Foundry API | `client.get_response(messages, options)` without `stream=True` | agent-framework handles tool execution loop internally |
| Shopping list item parsing | Custom NLP parser for items/stores | Admin Agent instructions in Foundry portal | The LLM does the parsing; instructions define store mappings |
| Inbox status updates | New API endpoint or event system | Direct Cosmos `upsert_item` in the background task | Simple field update; no need for event-driven architecture |

**Key insight:** The Admin Agent IS the item parser. Its instructions in the Foundry portal define how to split multi-item captures and route to stores. The code just calls `get_response` and lets the agent use `add_shopping_list_items`. No custom parsing code needed.

## Common Pitfalls

### Pitfall 1: Garbage-Collected Fire-and-Forget Tasks
**What goes wrong:** `asyncio.create_task(coro())` without storing the returned Task object. Python's GC may collect the task before completion.
**Why it happens:** Developers assume `create_task` keeps a strong reference internally. It doesn't always.
**How to avoid:** Store tasks in `app.state.background_tasks` set. Use `task.add_done_callback(tasks.discard)` for auto-cleanup.
**Warning signs:** Admin Agent processing silently never completes; inbox items stay in "pending" state indefinitely.

### Pitfall 2: Admin Agent Inheriting Classifier Thread Context
**What goes wrong:** Passing `conversation_id` from the Classifier's Foundry thread to the Admin Agent call. The Admin Agent would see the Classifier's conversation history and get confused.
**Why it happens:** Copy-pasting from the streaming adapter which uses `conversation_id` for follow-up flows.
**How to avoid:** Admin Agent `get_response` must NOT include `conversation_id` in options. Each Admin processing is a fresh, standalone call.
**Warning signs:** Admin Agent produces confused responses referencing classification logic.

### Pitfall 3: Race Condition on Inbox Status Update
**What goes wrong:** The background task reads the inbox doc to update `adminProcessingStatus`, but the doc was just created milliseconds ago. Cosmos eventual consistency could cause a 404.
**Why it happens:** Fire-and-forget task starts immediately after `file_capture` writes the inbox doc. With Cosmos strong consistency (the project default), this should not happen.
**How to avoid:** Use a brief retry on 404, or simply rely on Cosmos strong consistency (Session-level consistency is the default for the SDK). If it becomes a problem, add a 1-second delay before reading.
**Warning signs:** Sporadic 404 errors in App Insights when updating inbox status.

### Pitfall 4: Admin Agent Not Calling add_shopping_list_items
**What goes wrong:** The Admin Agent reasons about the capture but doesn't invoke the tool, similar to the Classifier's safety-net pattern.
**Why it happens:** LLM agents sometimes skip tool calls, especially with ambiguous input.
**How to avoid:** Write clear, directive instructions in the Foundry portal. Include examples. Consider a fallback: if `add_shopping_list_items` is never called, mark as "failed" and log a warning.
**Warning signs:** Inbox items marked "processed" but no shopping list items written.

### Pitfall 5: Store Name Mismatch Between Agent Instructions and KNOWN_STORES
**What goes wrong:** Admin Agent instructions say "Pet Store" but `KNOWN_STORES` in `documents.py` expects "pet_store". Items fall to "other" unexpectedly.
**Why it happens:** Case sensitivity and underscore/space differences between human-readable store names in agent instructions and the code-level store identifiers.
**How to avoid:** The `add_shopping_list_items` tool already lowercases and validates store names. Agent instructions should use the exact code-level identifiers: `jewel`, `cvs`, `pet_store`, `other`. Make this explicit in the instructions.
**Warning signs:** All items routing to "other" store despite clear category matches.

### Pitfall 6: asyncio.create_task Called Outside Event Loop
**What goes wrong:** `asyncio.create_task` can only be called from within an async context with a running event loop. If called from a synchronous callback, it fails.
**Why it happens:** Misunderstanding of where in the code the trigger fires.
**How to avoid:** The trigger point is inside an `async for` loop in the streaming adapter -- it is already in an async context. No issue here as long as the trigger stays in an async function.
**Warning signs:** `RuntimeError: no running event loop` in production logs.

## Code Examples

### Non-Streaming Agent Call (Admin Agent Pattern)
```python
# Verified from existing integration test: test_classifier_integration.py
# Same pattern works for Admin Agent
from agent_framework import ChatOptions, Message

messages = [Message(role="user", text="need cat litter and milk")]
options = ChatOptions(tools=[admin_tools.add_shopping_list_items])

# Non-streaming: awaits until agent completes all tool calls
response = await admin_client.get_response(messages=messages, options=options)

# response.text contains the agent's final text response
# Tool calls (add_shopping_list_items) execute during get_response
```

### Trigger Point in Streaming Adapter
```python
# In stream_text_capture, after detecting bucket == "Admin":
if detected_tool == "file_capture":
    result_src = tool_result or detected_tool_args
    bucket = result_src.get("bucket", "")
    item_id = result_src.get("item_id", "")

    # Trigger Admin Agent if classified as Admin
    if bucket == "Admin" and admin_client and item_id:
        task = asyncio.create_task(
            process_admin_capture(
                admin_client=admin_client,
                admin_tools=admin_tools,
                cosmos_manager=cosmos_manager,
                inbox_item_id=item_id,
                raw_text=user_text,
            )
        )
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

    # Continue with normal SSE event emission (CLASSIFIED/etc.)
    yield encode_sse(_emit_result_event(...))
```

### InboxDocument Model Extension
```python
# In models/documents.py -- add adminProcessingStatus field
class InboxDocument(BaseDocument):
    """Inbox container document -- raw capture log."""
    source: str = "text"
    filedRecordId: str | None = None
    status: str = "classified"
    title: str | None = None
    clarificationText: str | None = None
    foundryThreadId: str | None = None
    adminProcessingStatus: str | None = None  # "pending", "processed", "failed"
```

### Admin Agent System Instructions (Foundry Portal)
```text
You are the Admin Agent for a personal second brain system. Your job is to
process shopping-related captures and add items to the correct store shopping lists.

## Your Tool
You have one tool: add_shopping_list_items

## Store Mapping
Route items to the correct store using these rules:
- jewel: groceries, produce, dairy, meat, baking supplies, snacks, beverages
- cvs: pharmacy, medications, toiletries, first aid, personal care
- pet_store: pet food, pet supplies, pet medications, pet toys
- other: anything that doesn't clearly fit the above stores

## Instructions
1. Parse the user's capture text into individual shopping items
2. For each item, determine the correct store
3. Call add_shopping_list_items with ALL items in a single call
4. Keep item names natural -- exactly as the user said them
5. Quantities stay inline (e.g., "3 cans of tuna" is one item name)
6. Use lowercase store names: jewel, cvs, pet_store, other

## Examples

User: "need cat litter and milk"
-> add_shopping_list_items(items=[
     {"name": "cat litter", "store": "pet_store"},
     {"name": "milk", "store": "jewel"}
   ])

User: "pick up tylenol, dog treats, and bread"
-> add_shopping_list_items(items=[
     {"name": "tylenol", "store": "cvs"},
     {"name": "dog treats", "store": "pet_store"},
     {"name": "bread", "store": "jewel"}
   ])

User: "3 cans of tuna and shampoo"
-> add_shopping_list_items(items=[
     {"name": "3 cans of tuna", "store": "jewel"},
     {"name": "shampoo", "store": "cvs"}
   ])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom agent orchestration with manual tool execution | agent-framework SDK handles tool call loop in `get_response` | Phase 7 (2026-02-27) | Admin Agent uses same pattern -- just call `get_response`, SDK runs tools |
| BackgroundTasks in FastAPI | `asyncio.create_task` for fire-and-forget | Current | BackgroundTasks can't be used inside async generators (no DI access) |

**Deprecated/outdated:**
- The old v1.0 `AGUIWorkflowAdapter` was replaced in Phase 8. Admin Agent work extends the current `FoundrySSEAdapter` pattern but does not use streaming for the Admin call itself.

## Open Questions

1. **Should `adminProcessingStatus` be set to "pending" by `file_capture` or by the background task?**
   - What we know: `file_capture` creates the inbox doc. It could set `adminProcessingStatus = "pending"` when `bucket == "Admin"`.
   - What's unclear: This requires `file_capture` to know about the Admin workflow, coupling the Classifier tool to Admin concepts.
   - Recommendation: Set it in the background task's initial step (read doc, set to "pending", upsert, then process). This keeps `file_capture` agnostic. However, this means there's a brief window where the field is `None` (between filing and background task starting). Since the field is not visible in the mobile app this phase, this is acceptable. Alternatively, set it at creation time in `file_capture` for cleaner data -- the coupling is minimal (one field defaulting to "pending" when bucket is Admin).

2. **How to handle the Admin Agent calling add_shopping_list_items with incorrect store names?**
   - What we know: `add_shopping_list_items` already validates stores and falls back to "other" silently.
   - What's unclear: Whether the agent will consistently use lowercase identifiers vs. human-readable names.
   - Recommendation: The tool already handles this. Instructions should emphasize lowercase identifiers. No code changes needed.

3. **Should the background task have a timeout?**
   - What we know: The Classifier streaming has a 60-second `asyncio.timeout`. Admin Agent is non-streaming.
   - What's unclear: How long a non-streaming Foundry call typically takes.
   - Recommendation: Add a 60-second `asyncio.timeout` around the `get_response` call in `process_admin_capture`. Log timeout as a failure.

## Sources

### Primary (HIGH confidence)
- **Existing codebase analysis** -- full read of `main.py`, `capture.py`, `adapter.py`, `classification.py`, `admin.py`, `documents.py`, `cosmos.py`, all test files
- **agent-framework SDK source** -- verified `get_response` non-streaming signature and `ChatResponse` return type from installed package
- **Python 3.12 asyncio docs** -- `asyncio.create_task` behavior and task reference requirements

### Secondary (MEDIUM confidence)
- **FastAPI background tasks comparison** -- web search confirmed `asyncio.create_task` is appropriate when triggering from inside async generators where `BackgroundTasks` DI is unavailable
- **Python asyncio fire-and-forget best practices** -- web search confirmed task reference tracking via set + `add_done_callback` pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and used in the codebase
- Architecture: HIGH -- patterns directly extend existing working code; no new concepts needed
- Pitfalls: HIGH -- identified from codebase analysis and known asyncio patterns
- Admin Agent instructions: MEDIUM -- store routing quality depends on empirical testing with the LLM

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (stable domain, no fast-moving dependencies)
