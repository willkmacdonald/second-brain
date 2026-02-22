# Phase 4: HITL Clarification and AG-UI Streaming - Research

**Researched:** 2026-02-22
**Domain:** Real-time AG-UI streaming, Human-in-the-Loop (HITL) clarification, mobile conversation UI, inbox view
**Confidence:** HIGH (backend patterns verified via official Microsoft docs; mobile UI patterns well-established)

## Summary

Phase 4 transforms the fire-and-forget capture flow into a real-time interactive experience with three major additions: (1) AG-UI event streaming so Will sees the agent chain processing in real time, (2) a HITL clarification loop for low-confidence classifications, and (3) two new mobile screens (Inbox view and Conversation view).

The critical architectural finding is that HandoffBuilder's interactive mode is the native mechanism for HITL. When the Classifier doesn't hand off (which happens for low-confidence classifications), the workflow emits a `WorkflowEvent` with `type="request_info"` and a `HandoffAgentUserRequest` payload. The current `AGUIWorkflowAdapter` already handles `request_info` events but skips them (`continue`). Phase 4 must convert these into AG-UI text messages that reach the mobile client, accept the user's clarifying response via a new HTTP POST, and resume the workflow with `workflow.run(responses=...)`. This is the standard HandoffBuilder pattern documented by Microsoft.

For real-time agent chain visibility, AG-UI's `StepStarted`/`StepFinished` events are the standard mechanism. However, the Agent Framework's WorkflowAgent event bridge does not currently emit step events for handoff transitions. The pragmatic approach is to emit step events from the `AGUIWorkflowAdapter` when we detect agent transitions in `WorkflowEvent` data (agent name changes in `executor_id`). Combined with `ToolCallStart`/`ToolCallEnd` events already emitted by the framework for tool calls like `classify_and_file`, this provides sufficient real-time visibility.

For the mobile side, the conversation view should NOT use `react-native-gifted-chat` -- it adds 5+ dependencies (reanimated, gesture-handler, keyboard-controller) for features we don't need (swipe-to-reply, message bubbles, typing indicators). The clarification flow is a focused 2-3 message exchange, not a full chat. A simple custom view with FlatList + TextInput is sufficient and avoids dependency bloat.

**Primary recommendation:** Make the Classifier interactive (remove from autonomous mode), handle `request_info` events in the adapter by converting them to text messages streamed to the client, add a `/api/ag-ui/respond` endpoint for the user's clarification reply, build a simple Inbox FlatList screen backed by a new REST endpoint, and build a minimal Conversation view for the clarification exchange.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CAPT-02 | User receives real-time visual feedback showing the agent chain processing their capture (Orchestrator -> Classifier -> Action) | AG-UI StepStarted/StepFinished events emitted from AGUIWorkflowAdapter on agent transitions; ToolCallStart/ToolCallEnd events for classify_and_file; TEXT_MESSAGE_CONTENT for streaming responses. Mobile SSE client already handles these event types. |
| CLAS-04 | When confidence < 0.6, Classifier asks the user a focused clarifying question before filing | HandoffBuilder interactive mode: Classifier removed from autonomous mode, emits request_info with HandoffAgentUserRequest. Adapter converts to TEXT_MESSAGE_CONTENT. classify_and_file returns guidance text instead of filing when confidence < 0.6 (already implemented). Classifier generates clarifying question. User responds via /api/ag-ui/respond. Workflow resumes with responses parameter. |
| APPX-02 | Inbox view shows recent captures with the agent chain that processed each one | New REST endpoint `GET /api/inbox` queries Cosmos DB Inbox container ordered by createdAt DESC. Returns list with rawText, title, classificationMeta (bucket, confidence, agentChain), status. FlatList on mobile with pull-to-refresh. |
| APPX-04 | Conversation view opens when a specialist needs clarification, showing a focused chat | New mobile screen `app/conversation/[threadId].tsx` with dynamic route. Displays agent messages + user input. Uses SSE to stream the clarification exchange. Minimal UI: FlatList of messages + TextInput. No gifted-chat dependency. |
</phase_requirements>

## Standard Stack

### Core (already installed, no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `agent-framework-orchestrations` | 1.0.0b260210 | HandoffBuilder with interactive mode for HITL | Already installed. Provides `HandoffAgentUserRequest`, `request_info` events, autonomous mode control per-agent. |
| `agent-framework-core` | 1.0.0b260210 | WorkflowEvent, AgentResponseUpdate, Message | Already installed. Core event types for streaming. |
| `agent-framework-ag-ui` | 1.0.0b260210 | AG-UI endpoint | Already installed. SSE event streaming. |
| `react-native-sse` | ^1.2.1 | SSE client for mobile | Already installed. EventSource with POST support, generic type parameter. |
| `azure-cosmos` | >=4.14.0 | Cosmos DB queries for Inbox | Already installed. Async queries for inbox listing. |

### Supporting (already installed, no changes)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@ag-ui/core` | ^0.0.45 | AG-UI type definitions (TypeScript) | Already in package.json. Use for type-safe event parsing on mobile. |
| `pydantic` | >=2.11.2 | Response models for Inbox API | Pydantic models for REST endpoint response schemas. |
| `expo-router` | ~6.0.23 | File-based routing for new screens | Dynamic routes for conversation view `[threadId].tsx`. |
| `expo-haptics` | ~15.0.8 | Tactile feedback on clarification received | Already used for capture confirmation. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom FlatList conversation UI | `react-native-gifted-chat` | Gifted-chat adds 5+ peer dependencies (reanimated, gesture-handler, keyboard-controller) for a 2-3 message exchange. Overkill. Custom FlatList is ~80 lines of code. |
| StepStarted/StepFinished from adapter | Custom AG-UI event type (`Custom` event) | Step events are the AG-UI standard for sub-task visibility. Custom events would work but miss the semantic meaning the protocol provides. |
| New `/api/ag-ui/respond` endpoint | Reuse existing `/api/ag-ui` POST endpoint | Separate endpoint is cleaner: the main endpoint creates new runs, the respond endpoint continues existing runs. Prevents confusion about thread_id semantics. |
| REST endpoint for Inbox | Cosmos DB Change Feed via SSE | Change Feed is overengineered for a single-user hobby project. Simple REST with pull-to-refresh is sufficient. |

### No new npm/pip packages needed

All dependencies are already in `package.json` and `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure Changes

```
backend/src/second_brain/
  agents/
    workflow.py          # UPDATE: HITL handling, step events, thread management
    classifier.py        # UPDATE: remove from autonomous mode, add clarification instructions
  api/
    inbox.py             # NEW: GET /api/inbox REST endpoint
  main.py                # UPDATE: register inbox router, add /api/ag-ui/respond

mobile/
  app/
    _layout.tsx           # UPDATE: add tab navigation for Inbox
    index.tsx             # UPDATE: add Inbox tab
    inbox.tsx             # NEW: Inbox list view
    conversation/
      [threadId].tsx      # NEW: Conversation view for HITL clarification
  lib/
    ag-ui-client.ts       # UPDATE: add streaming callbacks, step events, respond function
    types.ts              # UPDATE: add new AG-UI event types and callback interfaces
  components/
    AgentSteps.tsx         # NEW: Visual step indicator component
    InboxItem.tsx          # NEW: Inbox list item component
    ChatMessage.tsx        # NEW: Chat bubble for conversation view
```

### Pattern 1: HandoffBuilder Interactive Mode for HITL

**What:** Remove the Classifier from autonomous mode so that when it generates a response without handing off (low-confidence classification), the workflow pauses and emits a `request_info` event. The user responds, and the workflow resumes.

**When to use:** When an agent needs to ask the human a question before proceeding. HandoffBuilder's interactive mode is purpose-built for this.

**Example (workflow.py changes):**
```python
# Source: https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/handoff

# Phase 3 (both autonomous):
.with_autonomous_mode(
    agents=[orchestrator, classifier],
    prompts={...},
)

# Phase 4 (only Orchestrator is autonomous; Classifier is interactive):
.with_autonomous_mode(
    agents=[orchestrator],
    prompts={orchestrator.name: "Route this input to the Classifier."},
)
# Classifier is NOT in autonomous mode -- when it responds without
# handing off, the workflow emits request_info and waits for user input.
```

**The HITL flow:**
1. User submits text via POST to `/api/ag-ui`
2. Orchestrator hands off to Classifier (autonomous)
3. Classifier calls `classify_and_file` with confidence < 0.6
4. Tool returns guidance: "Low confidence (0.45) for 'People'. Ask for clarification."
5. Classifier generates a clarifying question (e.g., "Is this about a person or a project?")
6. Classifier does NOT call a handoff tool -- it responds to the user
7. HandoffBuilder detects no handoff, emits `request_info` with `HandoffAgentUserRequest`
8. `AGUIWorkflowAdapter` converts this to TEXT_MESSAGE_CONTENT events + a signal that HITL is needed
9. Mobile app receives the question, opens conversation view
10. User responds via POST to `/api/ag-ui/respond` with `{thread_id, response}`
11. Adapter calls `workflow.run(responses={request_id: HandoffAgentUserRequest.create_response(user_input)})`
12. Classifier receives the clarification, re-classifies with higher confidence, files the record
13. RUN_FINISHED event sent to mobile

**Confidence:** HIGH -- HandoffBuilder interactive mode and `request_info` are documented in official Microsoft Learn docs (updated 2026-02-13).

### Pattern 2: Thread-Based Conversation State

**What:** Use `thread_id` from the AG-UI request to maintain conversation state across the initial capture and the clarification response. The workflow must be persisted between requests.

**When to use:** Whenever HITL requires a multi-turn exchange where the second message continues the same workflow run.

**Critical design decision:** The current `AGUIWorkflowAdapter` creates a fresh `WorkflowAgent` per request. For HITL, the workflow must survive between the initial request and the clarification response. Two options:

1. **Store pending workflow in memory** (recommended for Phase 4): Hold the workflow instance and pending `request_id` in a dict keyed by `thread_id`. When the respond endpoint is called, retrieve the workflow and resume it. Simple, no new dependencies, but workflows are lost on server restart.

2. **Use checkpoint storage** (future): HandoffBuilder supports `checkpoint_storage` for durable workflows that survive process restarts. Not needed for Phase 4 (single-user, hobby project, server restarts are rare).

**Example:**
```python
# In AGUIWorkflowAdapter:

# Store pending HITL sessions: thread_id -> (workflow, request_id)
_pending_sessions: dict[str, tuple[Workflow, str]] = {}

async def _stream_updates(self, messages, thread, **kwargs):
    workflow = self._create_workflow()  # Not WorkflowAgent -- we need the raw workflow
    thread_id = str(thread.id) if thread else str(uuid4())

    async for event in workflow.run_stream(messages):
        if event.type == "request_info" and isinstance(event.data, HandoffAgentUserRequest):
            # Store the workflow and request_id for later resumption
            self._pending_sessions[thread_id] = (workflow, event.request_id)
            # Convert agent messages to AG-UI text events
            for msg in event.data.agent_response.messages:
                yield _make_text_message_update(msg)
            # Yield a custom event indicating HITL is needed
            yield _make_hitl_needed_update(thread_id)
            return  # End this stream; client will call /respond
        # ... handle other events as before

async def resume_with_response(self, thread_id: str, user_response: str):
    """Resume a paused workflow with the user's clarification response."""
    workflow, request_id = self._pending_sessions.pop(thread_id)
    responses = {request_id: HandoffAgentUserRequest.create_response(user_response)}
    async for event in workflow.run(responses=responses):
        yield event  # Convert to AG-UI events as before
```

**Confidence:** HIGH -- `workflow.run(responses=...)` is the documented pattern for resuming workflows after `request_info`.

### Pattern 3: AG-UI Step Events for Agent Chain Visibility

**What:** Emit `StepStarted` and `StepFinished` AG-UI events when agents change during the workflow. This gives the mobile client real-time visibility into which agent is processing the capture.

**When to use:** When the user should see "Orchestrator routing..." then "Classifier analyzing..." as the agent chain progresses.

**Implementation approach:** The `AGUIWorkflowAdapter._stream_updates` method already processes `WorkflowEvent` objects. When `event.executor_id` changes between events, emit a StepFinished for the previous agent and StepStarted for the new one.

**Example (AG-UI events emitted during a capture):**
```
1. RUN_STARTED {threadId, runId}
2. STEP_STARTED {stepName: "Orchestrator"}
3. STEP_FINISHED {stepName: "Orchestrator"}
4. STEP_STARTED {stepName: "Classifier"}
5. TOOL_CALL_START {toolCallName: "classify_and_file"}
6. TOOL_CALL_ARGS {delta: '{"bucket":"Projects","confidence":0.85...}'}
7. TOOL_CALL_END {}
8. TEXT_MESSAGE_START {messageId, role: "assistant"}
9. TEXT_MESSAGE_CONTENT {delta: "Filed -> Projects (0.85)"}
10. TEXT_MESSAGE_END {}
11. STEP_FINISHED {stepName: "Classifier"}
12. RUN_FINISHED {}
```

**For low-confidence (HITL) flow:**
```
1. RUN_STARTED {threadId, runId}
2. STEP_STARTED {stepName: "Orchestrator"}
3. STEP_FINISHED {stepName: "Orchestrator"}
4. STEP_STARTED {stepName: "Classifier"}
5. TOOL_CALL_START {toolCallName: "classify_and_file"}
6. TOOL_CALL_END {}
7. TEXT_MESSAGE_START {messageId, role: "assistant"}
8. TEXT_MESSAGE_CONTENT {delta: "I'm not sure about this one. Is this about..."}
9. TEXT_MESSAGE_END {}
10. CUSTOM {name: "HITL_REQUIRED", value: {threadId, questionText}}
   -- stream pauses, waiting for user response --
```

**Confidence:** MEDIUM -- StepStarted/StepFinished are standard AG-UI events. The agent framework does not emit them automatically for handoff transitions, so we emit them from the adapter. This is a pragmatic approach that may need adjustment if the framework adds native step event support.

### Pattern 4: REST Endpoint for Inbox Listing

**What:** A simple GET endpoint that queries Cosmos DB Inbox container, returning recent captures with their classification metadata.

**When to use:** For the Inbox view that shows a list of recent captures with agent chain details.

**Example:**
```python
# backend/src/second_brain/api/inbox.py
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()

class InboxItem(BaseModel):
    id: str
    rawText: str
    title: str | None
    status: str
    createdAt: str
    classificationMeta: dict | None

class InboxResponse(BaseModel):
    items: list[InboxItem]
    count: int

@router.get("/api/inbox", response_model=InboxResponse)
async def list_inbox(request: Request, limit: int = 20):
    """List recent Inbox captures ordered by creation time."""
    cosmos = request.app.state.cosmos_manager
    container = cosmos.get_container("Inbox")

    query = (
        "SELECT * FROM c WHERE c.userId = @userId "
        "ORDER BY c.createdAt DESC "
        "OFFSET 0 LIMIT @limit"
    )
    params = [
        {"name": "@userId", "value": "will"},
        {"name": "@limit", "value": limit},
    ]

    items = []
    async for item in container.query_items(
        query=query, parameters=params, partition_key="will"
    ):
        items.append(InboxItem(**item))

    return InboxResponse(items=items, count=len(items))
```

**Confidence:** HIGH -- standard Cosmos DB query pattern, already used in `cosmos_crud.py`.

### Pattern 5: Echo Bug Filter (Phase 3 Deferred Item)

**What:** Filter the echo bug from Phase 3 where `workflow.as_agent()` prepends the user's input to the assistant response in TEXT_MESSAGE_CONTENT events.

**When to use:** Now that Phase 4 displays streamed text to the user, the echo must be filtered.

**Implementation approach:** The echo bug occurs because HandoffBuilder's internal executor echoes user input as part of the assistant response. The filter should be applied in the `AGUIWorkflowAdapter` by detecting and stripping the user's original message from the beginning of TEXT_MESSAGE_CONTENT streams.

**Example (client-side filter in ag-ui-client.ts):**
```typescript
// Track the original user message to filter echo
const userMessage = message.trim();
let isFirstTextChunk = true;
let accumulatedText = "";

es.addEventListener("message", (event) => {
    const parsed = JSON.parse(event.data);
    if (parsed.type === "TEXT_MESSAGE_CONTENT" && parsed.delta) {
        accumulatedText += parsed.delta;
        // Skip chunks that are building up the echo of user input
        if (isFirstTextChunk && accumulatedText.length <= userMessage.length) {
            return; // Still accumulating echo prefix
        }
        if (isFirstTextChunk) {
            isFirstTextChunk = false;
            // Remove the echo prefix from accumulated text
            const cleanText = accumulatedText.startsWith(userMessage)
                ? accumulatedText.slice(userMessage.length).trimStart()
                : accumulatedText;
            onDelta(cleanText);
        } else {
            onDelta(parsed.delta);
        }
    }
});
```

**Better approach (server-side in adapter):** Filter in the `AGUIWorkflowAdapter` before events reach the SSE stream. Track the user's input message and skip `AgentResponseUpdate` objects whose text matches the input prefix.

**Confidence:** MEDIUM -- the echo bug (issue #3206) is still open. Server-side filtering is cleaner but depends on how the framework emits the echo. May need both client and server-side handling.

### Anti-Patterns to Avoid

- **Making both Orchestrator and Classifier autonomous for HITL:** Classifier MUST be interactive (not in autonomous mode) for the `request_info` to be emitted. If Classifier is autonomous, it auto-responds and never pauses for user input.
- **Creating a WebSocket for HITL:** AG-UI uses SSE (unidirectional). The response goes back via a separate HTTP POST. Do not introduce WebSockets -- they add complexity with no benefit over the SSE + POST pattern.
- **Building a full chat framework for clarification:** The clarification exchange is 2-3 messages max (question, answer, confirmation). A full chat UI with typing indicators, read receipts, and message history is massive overkill.
- **Polling for Inbox updates:** Use pull-to-refresh, not polling. Single-user system -- the user knows when they submitted a capture.
- **Storing conversation history in Cosmos DB for HITL:** The workflow holds conversation state in memory. No need to persist the clarification exchange separately -- it's part of the agent workflow. The final classification result is stored in Cosmos DB as before.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HITL workflow pause/resume | Custom state machine for pausing agent execution | HandoffBuilder interactive mode + `request_info` events + `workflow.run(responses=...)` | Framework handles all the complexity of pausing workflow execution, buffering context, and resuming with the response |
| Agent chain step events | Custom event emission logic in each agent | `AGUIWorkflowAdapter` detecting `executor_id` changes and emitting AG-UI StepStarted/StepFinished | Centralized in the adapter, not scattered across agents |
| Real-time SSE event streaming | Custom HTTP streaming with chunked transfer | `react-native-sse` EventSource with POST support | Already working in Phase 2/3; handles reconnection, error events, cleanup |
| Clarification conversation state | Custom session store with Redis/Cosmos | In-memory dict of pending workflows keyed by thread_id | Single-user hobby project -- in-memory is fine. If server restarts, user can resubmit the capture. |
| Pull-to-refresh inbox | Custom scroll-based refresh logic | FlatList `onRefresh` + `refreshing` props | React Native's built-in pull-to-refresh mechanism |
| Chat message layout | `react-native-gifted-chat` with 5+ peer deps | Custom FlatList with simple message bubbles | 2-3 message exchange doesn't warrant a chat library |

**Key insight:** The HITL mechanism is built into HandoffBuilder. The work is in wiring the existing `request_info` events through the `AGUIWorkflowAdapter` to the mobile client, not in building a custom HITL system.

## Common Pitfalls

### Pitfall 1: Classifier Still in Autonomous Mode

**What goes wrong:** The Classifier is listed in `with_autonomous_mode(agents=[orchestrator, classifier])` from Phase 3. When confidence is low, the Classifier generates a clarifying question, but the autonomous mode auto-responds with "Classify this text and file it." The workflow never pauses for the user.
**Why it happens:** Phase 3 put both agents in autonomous mode for fire-and-forget. Phase 4 must change this.
**How to avoid:** Remove `classifier` from the `agents` list in `with_autonomous_mode()`. Only `orchestrator` should be autonomous.
**Warning signs:** Low-confidence captures get filed without any clarification question reaching the user. Logs show autonomous auto-response messages.

### Pitfall 2: Workflow Lost Between Requests

**What goes wrong:** User receives a clarification question, responds via `/api/ag-ui/respond`, but the workflow no longer exists because `AGUIWorkflowAdapter` creates a fresh workflow per request.
**Why it happens:** The current adapter is stateless -- each `run()` call creates a new `WorkflowAgent`. For HITL, the workflow must survive between the initial request and the clarification response.
**How to avoid:** Store pending workflows in a dict keyed by `thread_id`. When `request_info` is emitted, save the workflow and request_id. When the respond endpoint is called, retrieve and resume.
**Warning signs:** `/api/ag-ui/respond` returns an error or creates a new workflow instead of resuming the paused one.

### Pitfall 3: Echo Bug Now Visible to Users

**What goes wrong:** Phase 3 accepted the echo bug because only `RUN_FINISHED` events were consumed. Phase 4 streams `TEXT_MESSAGE_CONTENT` events to the UI, making the echo visible: "Had coffee with Jake Filed -> People (0.90)".
**Why it happens:** `WorkflowAgent.as_agent()` echoes user input in the streamed response (issue #3206).
**How to avoid:** Filter the echo either server-side in the adapter (preferred) or client-side in the SSE handler. The server-side approach tracks the original user message and strips matching prefixes from response updates.
**Warning signs:** Agent responses in the UI start with the user's input text.

### Pitfall 4: Thread ID Not Persisted for HITL Continuation

**What goes wrong:** The initial capture creates a `thread_id` but the mobile client doesn't store it. When the user taps the clarification notification/prompt, the client can't reference the correct workflow.
**Why it happens:** Phase 2/3 generate a throw-away `thread_id` (`thread-${Date.now()}`). For HITL, the thread_id must be stored and used to call the respond endpoint.
**How to avoid:** When the SSE stream includes a HITL signal (custom event or specific text pattern), store the `thread_id` and navigate to the conversation view with it as a parameter.
**Warning signs:** User taps to respond to clarification but the app doesn't know which thread to continue.

### Pitfall 5: Inbox Query Without ORDER BY Hits RU Cost

**What goes wrong:** Cosmos DB query without `ORDER BY` on a composite index returns items in arbitrary order, requiring client-side sorting. Worse, a query with `ORDER BY c.createdAt DESC` without a matching composite index consumes high RUs.
**Why it happens:** Cosmos DB serverless charges per RU consumed. `ORDER BY` on a non-indexed field requires a full scan.
**How to avoid:** Add a composite index on `(userId ASC, createdAt DESC)` to the Inbox container. This allows efficient ordered queries within the user's partition.
**Warning signs:** Inbox list shows items in random order, or the query is slow/expensive.

### Pitfall 6: Clarification Flow Blocks Future Captures

**What goes wrong:** While a capture is awaiting clarification, the user can't submit new captures because the workflow is "busy."
**Why it happens:** If the system only supports one active workflow at a time.
**How to avoid:** Each capture creates an independent workflow. The pending sessions dict supports multiple concurrent HITL sessions keyed by thread_id. New captures go through a fresh workflow while old ones wait for clarification.
**Warning signs:** Tapping "Text" while a clarification is pending results in an error or blocks.

## Code Examples

### Updated AGUIWorkflowAdapter with HITL Support

```python
# Source: Adapted from official HandoffBuilder HITL docs
# File: backend/src/second_brain/agents/workflow.py

from agent_framework.orchestrations import HandoffAgentUserRequest

class AGUIWorkflowAdapter:
    """Adapter with HITL support for Phase 4."""

    # Store pending HITL sessions: thread_id -> (workflow, request_id)
    _pending_sessions: dict[str, tuple] = {}

    def _create_workflow(self):
        """Create a fresh Workflow (not WorkflowAgent) for HITL support."""
        return (
            HandoffBuilder(
                name="capture_pipeline",
                participants=[self._orchestrator, self._classifier],
            )
            .with_start_agent(self._orchestrator)
            .add_handoff(self._orchestrator, [self._classifier])
            .with_autonomous_mode(
                agents=[self._orchestrator],  # Only Orchestrator is autonomous
                prompts={self._orchestrator.name: "Route this input to the Classifier."},
            )
            .build()
        )

    async def _stream_updates(self, messages, thread, **kwargs):
        workflow = self._create_workflow()
        thread_id = kwargs.get("thread_id", str(uuid4()))
        current_agent = None
        user_input_text = ""  # Track for echo filtering

        # Extract user input for echo filtering
        if isinstance(messages, list):
            for msg in messages:
                if hasattr(msg, "text") and msg.text:
                    user_input_text = msg.text
                    break

        async for event in workflow.run_stream(messages):
            if event.type == "request_info" and isinstance(
                event.data, HandoffAgentUserRequest
            ):
                # HITL: Classifier wants user input
                self._pending_sessions[thread_id] = (workflow, event.request_id)

                # Emit the agent's clarifying question as text events
                for msg in event.data.agent_response.messages:
                    if msg.text:
                        yield _make_text_update(msg.text, msg.author_name)

                # Signal HITL needed
                yield _make_custom_event("HITL_REQUIRED", {"threadId": thread_id})
                return  # End stream; client will call /respond

            elif isinstance(event, WorkflowEvent):
                # Track agent changes for step events
                if event.executor_id and event.executor_id != current_agent:
                    if current_agent:
                        yield _make_step_finished(current_agent)
                    current_agent = event.executor_id
                    yield _make_step_started(current_agent)

                # Convert workflow events to AG-UI updates
                # ... (existing conversion logic)

            elif isinstance(event, AgentResponseUpdate):
                # Filter echo bug
                if user_input_text and event.text:
                    if event.text.strip().startswith(user_input_text):
                        event = _strip_echo(event, user_input_text)
                yield event

        # Final step finished
        if current_agent:
            yield _make_step_finished(current_agent)

    async def resume_with_response(self, thread_id: str, user_response: str):
        """Resume a paused workflow with the user's clarification."""
        if thread_id not in self._pending_sessions:
            raise ValueError(f"No pending session for thread {thread_id}")

        workflow, request_id = self._pending_sessions.pop(thread_id)
        responses = {
            request_id: HandoffAgentUserRequest.create_response(user_response)
        }

        async for event in workflow.run(responses=responses):
            # Process and yield events same as _stream_updates
            yield event
```

### Updated Classifier Instructions for Clarification

```python
# File: backend/src/second_brain/agents/classifier.py (additions)

# Add to existing instructions:
CLARIFICATION_INSTRUCTIONS = """
## Low Confidence Handling

When the classify_and_file tool returns a low-confidence message:
1. Ask the user ONE focused clarifying question
2. The question should help distinguish between the 2-3 most likely buckets
3. Keep the question concise (one sentence)
4. Do NOT file the capture yet -- wait for the user's response
5. After receiving the user's answer, call classify_and_file again with
   updated confidence based on their clarification

Example low-confidence interaction:
- User: "Interesting conversation with Mike about moving to Austin"
- Tool returns: "Low confidence (0.45) for 'People'. Ask for clarification."
- You ask: "Is this more about your relationship with Mike, or about the idea of moving to Austin?"
- User: "It's about Mike -- he's thinking of moving and I want to stay in touch"
- You call classify_and_file with bucket="People", confidence=0.85
"""
```

### Updated Mobile SSE Client with Streaming Callbacks

```typescript
// File: mobile/lib/types.ts (additions)

export type AGUIEventType =
  | "message"
  | "RUN_STARTED"
  | "TEXT_MESSAGE_START"
  | "TEXT_MESSAGE_CONTENT"
  | "TEXT_MESSAGE_END"
  | "STEP_STARTED"
  | "STEP_FINISHED"
  | "TOOL_CALL_START"
  | "TOOL_CALL_END"
  | "CUSTOM"
  | "RUN_FINISHED"
  | "RUN_ERROR";

export interface StreamingCallbacks {
  onStepStart?: (stepName: string) => void;
  onStepFinish?: (stepName: string) => void;
  onTextDelta?: (delta: string) => void;
  onToolCallStart?: (toolName: string) => void;
  onToolCallEnd?: (toolName: string) => void;
  onHITLRequired?: (threadId: string, questionText: string) => void;
  onComplete: (result: string) => void;
  onError: (error: string) => void;
}

export interface SendCaptureOptions {
  message: string;
  apiKey: string;
  callbacks: StreamingCallbacks;
}
```

```typescript
// File: mobile/lib/ag-ui-client.ts (updated sendCapture)

export function sendCapture({
  message,
  apiKey,
  callbacks,
}: SendCaptureOptions): () => void {
  const threadId = `thread-${Date.now()}`;
  const es = new EventSource<AGUIEventType>(`${API_BASE_URL}/api/ag-ui`, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    method: "POST",
    body: JSON.stringify({
      messages: [{ id: `msg-${Date.now()}`, role: "user", content: message }],
      thread_id: threadId,
      run_id: `run-${Date.now()}`,
    }),
    pollingInterval: 0,
  });

  let result = "";

  es.addEventListener("message", (event) => {
    if (!event.data) return;
    try {
      const parsed = JSON.parse(event.data);
      switch (parsed.type) {
        case "STEP_STARTED":
          callbacks.onStepStart?.(parsed.stepName);
          break;
        case "STEP_FINISHED":
          callbacks.onStepFinish?.(parsed.stepName);
          break;
        case "TEXT_MESSAGE_CONTENT":
          if (parsed.delta) {
            result += parsed.delta;
            callbacks.onTextDelta?.(parsed.delta);
          }
          break;
        case "TOOL_CALL_START":
          callbacks.onToolCallStart?.(parsed.toolCallName);
          break;
        case "TOOL_CALL_END":
          callbacks.onToolCallEnd?.(parsed.toolCallName);
          break;
        case "CUSTOM":
          if (parsed.name === "HITL_REQUIRED") {
            callbacks.onHITLRequired?.(
              parsed.value?.threadId ?? threadId,
              result
            );
          }
          break;
        case "RUN_FINISHED":
          callbacks.onComplete(result);
          es.close();
          break;
      }
    } catch {
      // Ignore malformed JSON
    }
  });

  es.addEventListener("error", (event) => {
    const errorMessage = "message" in event ? event.message : "Connection error";
    callbacks.onError(errorMessage);
    es.close();
  });

  return () => {
    es.removeAllEventListeners();
    es.close();
  };
}

/**
 * Send a clarification response to resume a paused HITL workflow.
 */
export function sendClarification({
  threadId,
  response,
  apiKey,
  callbacks,
}: {
  threadId: string;
  response: string;
  apiKey: string;
  callbacks: StreamingCallbacks;
}): () => void {
  const es = new EventSource<AGUIEventType>(
    `${API_BASE_URL}/api/ag-ui/respond`,
    {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify({ thread_id: threadId, response }),
      pollingInterval: 0,
    }
  );

  let result = "";

  es.addEventListener("message", (event) => {
    if (!event.data) return;
    try {
      const parsed = JSON.parse(event.data);
      if (parsed.type === "TEXT_MESSAGE_CONTENT" && parsed.delta) {
        result += parsed.delta;
        callbacks.onTextDelta?.(parsed.delta);
      } else if (parsed.type === "RUN_FINISHED") {
        callbacks.onComplete(result);
        es.close();
      }
    } catch {
      // Ignore malformed JSON
    }
  });

  es.addEventListener("error", (event) => {
    const errorMessage = "message" in event ? event.message : "Connection error";
    callbacks.onError(errorMessage);
    es.close();
  });

  return () => {
    es.removeAllEventListeners();
    es.close();
  };
}
```

### Inbox Screen Component

```typescript
// File: mobile/app/inbox.tsx

import { useState, useCallback, useEffect } from "react";
import { View, Text, FlatList, Pressable, StyleSheet, RefreshControl } from "react-native";
import { router } from "expo-router";
import { API_BASE_URL, API_KEY } from "../constants/config";

interface InboxItem {
  id: string;
  rawText: string;
  title: string | null;
  status: string;
  createdAt: string;
  classificationMeta: {
    bucket: string;
    confidence: number;
    agentChain: string[];
  } | null;
}

export default function InboxScreen() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchInbox = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/inbox?limit=20`, {
        headers: { Authorization: `Bearer ${API_KEY}` },
      });
      const data = await res.json();
      setItems(data.items);
    } catch {
      // Handle error
    }
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchInbox();
    setRefreshing(false);
  }, [fetchInbox]);

  useEffect(() => { fetchInbox(); }, [fetchInbox]);

  const renderItem = ({ item }: { item: InboxItem }) => (
    <Pressable
      style={styles.item}
      onPress={() => {
        if (item.status === "low_confidence") {
          router.push(`/conversation/${item.id}`);
        }
      }}
    >
      <Text style={styles.title}>{item.title || item.rawText.slice(0, 50)}</Text>
      {item.classificationMeta && (
        <View style={styles.meta}>
          <Text style={styles.bucket}>{item.classificationMeta.bucket}</Text>
          <Text style={styles.confidence}>
            {(item.classificationMeta.confidence * 100).toFixed(0)}%
          </Text>
          <Text style={styles.chain}>
            {item.classificationMeta.agentChain.join(" -> ")}
          </Text>
        </View>
      )}
    </Pressable>
  );

  return (
    <FlatList
      data={items}
      keyExtractor={(item) => item.id}
      renderItem={renderItem}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
      style={styles.list}
    />
  );
}
```

### Agent Step Indicator Component

```typescript
// File: mobile/components/AgentSteps.tsx

import { View, Text, StyleSheet } from "react-native";

interface AgentStepsProps {
  currentStep: string | null;
  completedSteps: string[];
}

export function AgentSteps({ currentStep, completedSteps }: AgentStepsProps) {
  const steps = ["Orchestrator", "Classifier"];

  return (
    <View style={styles.container}>
      {steps.map((step) => {
        const isActive = step === currentStep;
        const isComplete = completedSteps.includes(step);
        return (
          <View key={step} style={styles.step}>
            <View style={[
              styles.dot,
              isActive && styles.dotActive,
              isComplete && styles.dotComplete,
            ]} />
            <Text style={[
              styles.label,
              isActive && styles.labelActive,
              isComplete && styles.labelComplete,
            ]}>
              {step}
            </Text>
          </View>
        );
      })}
    </View>
  );
}
```

## State of the Art

| Old Approach (Phase 3) | Current Approach (Phase 4) | Impact |
|-------------------------|---------------------------|--------|
| Both agents autonomous, fire-and-forget | Orchestrator autonomous, Classifier interactive | Enables HITL clarification flow |
| Only RUN_FINISHED and error events consumed | Full AG-UI event stream: steps, text, tools, custom | Real-time agent chain visibility |
| Single endpoint, no thread persistence | Thread-based workflow persistence for HITL | Multi-turn clarification exchange |
| Toast-only result display | Streaming text + step indicators + conversation view | Rich real-time feedback |
| No Inbox view | REST-backed Inbox with FlatList | History of all captures with agent chain metadata |
| Echo bug accepted | Echo filtered (server-side preferred) | Clean text display in streaming UI |

**Still current from Phase 3:**
- `react-native-sse` for SSE transport (stable, well-tested)
- `AGUIWorkflowAdapter` for bridging workflow to AG-UI (extended, not replaced)
- `ClassificationTools.classify_and_file` low-confidence logic (already returns guidance text)
- `HandoffBuilder` for multi-agent orchestration (used with different mode config)

## Open Questions

1. **WorkflowEvent.executor_id availability for step tracking**
   - What we know: `WorkflowEvent` has a `type` and `data` field. The `executor_id` field was observed in the existing adapter code.
   - What's unclear: Whether `executor_id` consistently maps to agent names during handoff transitions.
   - Recommendation: Log all WorkflowEvent fields during development. If `executor_id` is unreliable, fall back to detecting agent name changes in `event.data.agent_response.messages[-1].author_name`.

2. **Echo bug fix timeline (Issue #3206)**
   - What we know: Still open as of 2026-02-22. Root cause identified.
   - What's unclear: Whether it will be fixed before Phase 4 implementation.
   - Recommendation: Implement server-side echo filtering regardless. If the bug is fixed, the filter becomes a no-op (no harm).

3. **Workflow memory cleanup for abandoned HITL sessions**
   - What we know: If a user receives a clarification question but never responds, the workflow stays in `_pending_sessions` forever.
   - What's unclear: How much memory a pending workflow consumes.
   - Recommendation: Add a TTL-based cleanup (e.g., remove sessions older than 1 hour). For single-user hobby project, this is low priority.

4. **AG-UI respond endpoint -- SSE or JSON response?**
   - What we know: The initial capture uses SSE streaming. The clarification response also produces AG-UI events (classification confirmation).
   - What's unclear: Whether the respond endpoint should also stream SSE events or return a simple JSON response.
   - Recommendation: Use SSE streaming for the respond endpoint too. The user should see the same real-time feedback (step events, classification result) as the initial capture.

## Sources

### Primary (HIGH confidence)
- [Microsoft Agent Framework: Handoff Orchestration](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/handoff) -- Interactive mode, autonomous mode per-agent, `request_info` events, `HandoffAgentUserRequest`, `workflow.run(responses=...)`. Updated 2026-02-13.
- [Microsoft Agent Framework: Human-in-the-Loop Workflows](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/human-in-the-loop) -- `request_info` event flow, `WorkflowContext.request_info()`, response handling. Updated 2026-02-13.
- [Microsoft Agent Framework: Using Workflows as Agents](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/as-agents) -- `workflow.as_agent()`, event conversion table, pending requests handling. Updated 2026-02-20.
- [AG-UI: Human-in-the-Loop with AG-UI](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/human-in-the-loop) -- `@tool(approval_mode="always_require")`, `AgentFrameworkAgent` wrapper, approval events. Updated 2026-02-13.
- [AG-UI Event Types](https://docs.ag-ui.com/concepts/events) -- Complete event schema: 7 categories, 25+ event types including StepStarted/StepFinished, Custom, and all streaming patterns.
- Local codebase: `workflow.py` AGUIWorkflowAdapter already handles WorkflowEvent and request_info (skips it).

### Secondary (MEDIUM confidence)
- [AG-UI StepStarted/StepFinished events for sub-task visibility](https://www.copilotkit.ai/blog/master-the-17-ag-ui-event-types-for-building-agents-the-right-way) -- CopilotKit blog describing step events for progress tracking.
- [Agent Framework Issue #3534: Request info naming](https://github.com/microsoft/agent-framework/issues/3534) -- Open issue noting `request_info` naming confusion and lack of event filtering. No assignees yet.
- [Agent Framework Issue #3206: Echo bug](https://github.com/microsoft/agent-framework/issues/3206) -- Open. User input echoed in streamed response from `as_agent()`.
- [Building Enterprise-Level SSE Systems in React Native](https://medium.com/doping-technology-blog/building-enterprise-level-sse-systems-in-react-native-a-complete-guide-d84786eecbeb) -- Connection management, retry strategies, state management patterns.
- [react-native-gifted-chat](https://github.com/FaridSafi/react-native-gifted-chat) -- Evaluated and rejected for Phase 4; too many dependencies for a 2-3 message exchange.

### Tertiary (LOW confidence)
- [react-native-sse npm](https://www.npmjs.com/package/react-native-sse) -- Community package docs. Limited documentation but package is stable (used successfully in Phase 2/3).
- [FlatList performance patterns](https://reactnative.dev/docs/flatlist) -- Official React Native docs for list optimization (removeClippedSubviews, maxToRenderPerBatch).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies needed; all patterns use existing installed packages
- Architecture (HITL): HIGH -- HandoffBuilder interactive mode and `request_info` are first-party documented patterns
- Architecture (streaming): MEDIUM -- StepStarted/StepFinished events are AG-UI standard but must be emitted manually from adapter (framework doesn't do it automatically for handoff transitions)
- Architecture (mobile UI): HIGH -- FlatList, pull-to-refresh, dynamic routes are mature React Native patterns
- Pitfalls: HIGH -- based on Phase 3 experience with the actual codebase and known issues (#3206, #3534)
- Echo bug handling: MEDIUM -- workaround approach is sound but exact behavior depends on framework version

**Research date:** 2026-02-22
**Valid until:** 2026-03-22 (check Agent Framework releases for echo bug fix and any request_info changes)

---

## Deep Dive Addendum (Codebase Verification)

*Added 2026-02-22 after deep investigation of installed packages and existing codebase.*

### 1. HITL request_info Flow — VERIFIED

**HandoffAgentUserRequest** (exact location: `agent_framework_orchestrations/_handoff.py:146-181`):
```python
@dataclass
class HandoffAgentUserRequest:
    agent_response: AgentResponse

    @staticmethod
    def create_response(response: str | list[str] | Message | list[Message]) -> list[Message]:
        ...

    @staticmethod
    def terminate() -> list[Message]:
        return []
```

**request_info WorkflowEvent fields:**
- `event.type` = `"request_info"`
- `event.data` = `HandoffAgentUserRequest` instance (contains agent's response with clarifying question)
- `event.request_id` = UUID string for correlating response
- `event.source_executor_id` = Agent that requested user input
- `event.response_type` = `list[Message]`

**Emission point** (HandoffAgentExecutor._run_agent_and_emit, line 434):
```python
# Agent completes turn without handoff AND not in autonomous mode:
await ctx.request_info(HandoffAgentUserRequest(response), list[Message])
```

**workflow.run(responses=...)** — verified:
```python
def run(self, message=None, *, stream=False, responses: dict[str, Any] | None = None, ...):
```
- `message` and `responses` are **mutually exclusive**
- Keys = request_ids, Values = response data matching response_type
- Example: `workflow.run(responses={"req-uuid": HandoffAgentUserRequest.create_response("user input")})`

**with_autonomous_mode()** — verified selective support:
```python
def with_autonomous_mode(self, *, agents=None, prompts=None, turn_limits=None):
```
- `agents`: If provided, ONLY those agents are autonomous; others are interactive (emit request_info)
- Current code: `agents=[self._orchestrator, self._classifier]` → Phase 4 change: `agents=[self._orchestrator]`

**Current adapter skip** (workflow.py:118): `if event.type == "request_info": continue`

### 2. Echo Bug — ROOT CAUSE IDENTIFIED

**The echo is NOT from the user's input being prepended.** It's from the **Orchestrator Agent's TEXT_MESSAGE_CONTENT** events.

**Event sequence during a capture:**
1. Orchestrator receives user message, generates routing response (which echoes input)
2. Orchestrator's response streams as TEXT_MESSAGE_CONTENT deltas
3. Handoff to Classifier occurs
4. Classifier's response streams as TEXT_MESSAGE_CONTENT deltas
5. Client accumulates ALL TEXT_MESSAGE_CONTENT → gets Orchestrator echo + Classifier result

**Current client code** (ag-ui-client.ts:39-61):
```typescript
if (parsed.type === "TEXT_MESSAGE_CONTENT" && parsed.delta) {
    result += parsed.delta;  // Accumulates ALL deltas from ALL agents
}
```

**Best fix: Server-side filtering in adapter.** Options:
1. Track which agent is emitting via `event.executor_id` and only yield Classifier events
2. Or: When Orchestrator completes and Classifier starts, reset the text accumulation
3. Server-side is preferred — single source of truth, reduces bandwidth

**Note:** If AG-UI events include `author_name` in TEXT_MESSAGE_CONTENT, the client can also filter by agent name.

### 3. Step Event Emission — KEY FINDING: `handoff_sent` Event

**The `"handoff_sent"` event is the definitive agent transition marker.**

WorkflowEvent types relevant to step tracking:
| Event Type | executor_id | Use |
|---|---|---|
| `"executor_invoked"` | ✓ (agent name) | Agent started processing |
| `"executor_completed"` | ✓ (agent name) | Agent finished processing |
| `"handoff_sent"` | ✗ | **Agent transition** — `event.data` is `HandoffSentEvent(source, target)` |
| `"data"` | ✓ (agent name) | Agent response/tool result |

**AG-UI step event classes** (ag_ui/core/events.py):
```python
class StepStartedEvent(BaseEvent):
    type: Literal[EventType.STEP_STARTED] = EventType.STEP_STARTED
    step_name: str
    timestamp: Optional[int] = None

class StepFinishedEvent(BaseEvent):
    type: Literal[EventType.STEP_FINISHED] = EventType.STEP_FINISHED
    step_name: str
    timestamp: Optional[int] = None
```

**Implementation plan for adapter:**
1. On `"executor_invoked"` with executor_id → emit `StepStartedEvent(step_name=executor_id)`
2. On `"executor_completed"` with executor_id → emit `StepFinishedEvent(step_name=executor_id)`
3. `"handoff_sent"` confirms transition (use for logging/debugging)

**Tool call events are already emitted** by the internal converter (`_convert_workflow_event_to_agent_response_updates` handles FunctionCallContent).

### 4. Conversation UX Flow — GAP ANALYSIS

**Current state:**
- Mobile: 2 screens (home + text capture modal), stack navigation, no tabs
- thread_id: Generated as `thread-${Date.now()}`, NOT persisted
- No state management (no Context, no Zustand, no Redux)
- Fire-and-forget UX — once RUN_FINISHED, capture is done
- No /respond endpoint on server

**What HITL needs:**
1. **Thread persistence**: Store threadId when HITL_REQUIRED custom event arrives
2. **Conversation screen**: `app/conversation/[threadId].tsx` (dynamic expo-router route)
3. **State container**: React Context + useReducer (simplest, no new deps) for active conversations
4. **Respond endpoint**: `POST /api/ag-ui/respond` on backend
5. **Navigation**: From SSE callback → store thread → `router.push(\`/conversation/${threadId}\`)`

**Recommended flow:**
```
sendCapture() → SSE stream → CUSTOM(HITL_REQUIRED) event arrives
  → Store {threadId, question} in ConversationContext
  → router.push(`/conversation/${threadId}`)
  → ConversationScreen reads params, displays question + TextInput
  → User responds → sendClarification({threadId, response}) → new SSE stream
  → RUN_FINISHED → navigate back with success toast
```

**Inbox screen** also needs:
- `GET /api/inbox` REST endpoint (not SSE)
- FlatList with pull-to-refresh
- Items show rawText, bucket, confidence, agentChain
- Low-confidence items tap → navigate to conversation

### 5. Cosmos DB Consideration

Inbox documents already have `classificationMeta.agentChain` (array of agent names) and `status` field. For Inbox listing:
- Query: `SELECT * FROM c WHERE c.userId = @userId ORDER BY c.createdAt DESC OFFSET 0 LIMIT @limit`
- Partition key: `"will"`
- **Add composite index** on `(userId ASC, createdAt DESC)` for efficient ordered queries
