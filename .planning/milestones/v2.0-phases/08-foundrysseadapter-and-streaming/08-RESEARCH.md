# Phase 8: FoundrySSEAdapter and Streaming - Research

**Researched:** 2026-02-27
**Domain:** Azure AI Foundry Agent Service streaming API, AG-UI SSE event protocol, FastAPI StreamingResponse, ChatResponseUpdate event mapping
**Confidence:** HIGH

## Summary

Phase 8 bridges the Foundry agent streaming API (`AzureAIAgentClient.get_response(stream=True)`) to the AG-UI SSE event format the mobile Expo app already consumes. The old `AGUIWorkflowAdapter` (~540 lines, deleted in Phase 6) wrapped the HandoffBuilder workflow and the `ag_ui` Python package's `EventEncoder`. The new `FoundrySSEAdapter` replaces both: it iterates `ChatResponseUpdate` objects from the Foundry streaming response, maps them to AG-UI-compatible JSON payloads, and yields SSE-formatted strings directly -- no `ag_ui` package dependency.

The streaming API is verified from source code inspection of the installed `agent-framework-azure-ai==1.0.0rc2` and `azure-ai-agents==1.2.0b5`. `AzureAIAgentClient.get_response(messages, stream=True, options=ChatOptions(tools=[...]))` returns a `ResponseStream[ChatResponseUpdate, ChatResponse]`. This `ResponseStream` is an `AsyncIterable` -- iterate with `async for update in stream:`. Each `ChatResponseUpdate` has a `contents` list of `Content` objects with a `.type` string attribute (e.g., `"text"`, `"function_call"`, `"function_result"`, `"usage"`). The streaming pipeline handles the full tool call loop internally: when the Foundry service requests a tool call, the SDK intercepts it, executes the local `@tool` function, submits the result back to Foundry, and resumes streaming -- all transparently within the single `async for` loop.

The mobile app (react-native-sse `EventSource`) expects SSE messages with no `event:` field (defaults to `"message"` event type), containing `data: {JSON}\n\n` where the JSON has a `type` field. The client switches on `type`: `STEP_STARTED`, `STEP_FINISHED`, `TEXT_MESSAGE_CONTENT`, `CUSTOM`, `RUN_FINISHED`, `RUN_ERROR`. Custom events carry `name` (`CLASSIFIED`, `MISUNDERSTOOD`, `UNRESOLVED`) and `value` objects. The adapter must produce this exact wire format. No frontend changes are needed.

**Primary recommendation:** Build `FoundrySSEAdapter` as a module of async generator functions (not a class). One function per endpoint: `stream_text_capture()`, `stream_voice_capture()`. Each function takes the `AzureAIAgentClient`, messages, and tools; calls `get_response(stream=True)`; iterates `ChatResponseUpdate` objects; detects tool outcomes via `Content.type == "function_call"` / `"function_result"` inspection; yields SSE-formatted strings. Wire these generators into FastAPI `StreamingResponse` endpoints at `/api/ag-ui`, `/api/voice-capture`, `/api/ag-ui/respond`, and `/api/ag-ui/follow-up`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STRM-01 | `FoundrySSEAdapter` replaces `AGUIWorkflowAdapter`, streaming `AgentResponseUpdate` events to AG-UI SSE format | `AzureAIAgentClient.get_response(stream=True)` returns `ResponseStream[ChatResponseUpdate, ChatResponse]`. Each `ChatResponseUpdate` has `.contents` list of `Content` objects with `.type` (text, function_call, function_result, usage). The adapter iterates this stream and maps content types to AG-UI SSE JSON events. The SDK's `FunctionInvocationLayer` handles the tool call loop transparently -- the adapter sees function_call and function_result content as they flow through. |
| STRM-02 | Text capture produces same AG-UI events as v1 (`StepStarted`, `StepFinished`, `CLASSIFIED`/`MISUNDERSTOOD`/`UNRESOLVED`, `RUN_FINISHED`) | The adapter emits synthetic step events (`STEP_STARTED` for "Classifier", `STEP_FINISHED` when streaming ends), detects tool outcomes by inspecting `Content.type == "function_call"` with `content.name` in `{"file_capture"}`, parses `Content.type == "function_result"` for the result dict, and emits CUSTOM events (CLASSIFIED, MISUNDERSTOOD, UNRESOLVED) based on the `status` field in the tool arguments/result. Text deltas from `Content.type == "text"` are suppressed (chain-of-thought) and a clean result string is emitted at the end, matching v1 behavior. |
| STRM-03 | Voice capture produces same AG-UI events as v1 (transcription step + classification stream) | Voice capture is a single Foundry agent call -- the Classifier agent calls `transcribe_audio` first (appears as function_call/function_result in the stream), then calls `file_capture`. The adapter emits a synthetic "Transcription" step when it sees `transcribe_audio` function_call, and a "Classifier" step for the classification phase. The mobile app's `sendVoiceCapture()` POSTs to `/api/voice-capture` which uploads audio to Blob Storage, then calls the classifier agent with `blob_url` in the user message, and streams the result. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `agent-framework-azure-ai` | `1.0.0rc2` | `AzureAIAgentClient.get_response(stream=True)` | Already installed; provides `ResponseStream[ChatResponseUpdate, ChatResponse]` |
| `agent-framework` (core) | `1.0.0rc2` (transitive) | `ChatResponseUpdate`, `Content`, `ChatOptions`, `Message`, `ResponseStream` | Core streaming types |
| `fastapi` | existing | `StreamingResponse` with `media_type="text/event-stream"` | Already installed; standard SSE pattern |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `azure-storage-blob` | existing | Upload audio to Blob Storage before classification | Voice capture endpoint only |
| `python-multipart` | existing | Parse `UploadFile` in voice capture POST | Voice capture endpoint only |

### NOT Needed

| Library | Reason |
|---------|--------|
| `ag-ui-protocol` / `ag_ui` | Deleted in Phase 6. SSE format is trivial (`data: {json}\n\n`). No need for EventEncoder. |
| `sse-starlette` | Over-engineering. Raw `StreamingResponse` with `text/event-stream` is sufficient and proven in v1. |

**Installation:**
No new packages needed. All dependencies are already installed from Phase 6/7.

## Architecture Patterns

### Recommended Project Structure

```
backend/src/second_brain/
  api/
    capture.py         # NEW: /api/ag-ui, /api/ag-ui/respond, /api/ag-ui/follow-up, /api/voice-capture
  streaming/
    __init__.py
    adapter.py         # NEW: FoundrySSEAdapter -- async generator functions
    sse.py             # NEW: SSE formatting helpers (encode_sse_event, AG-UI event constructors)
```

### Pattern 1: FoundrySSEAdapter as Module Functions

**What:** The adapter is a module of async generator functions, not a class. Each function takes the classifier_client, messages, tools, and yields SSE-formatted strings.

**When to use:** Always for this phase. Functions are simpler than the old 540-line class because:
1. No HandoffBuilder/Workflow indirection -- direct `client.get_response(stream=True)`
2. No ag_ui EventEncoder -- plain string formatting
3. No orchestrator echo filtering -- single agent, no multi-agent routing

**Example:**
```python
# Source: Verified from agent-framework-azure-ai 1.0.0rc2 source code
import json
from collections.abc import AsyncGenerator
from agent_framework import ChatOptions, ChatResponseUpdate, Content, Message
from agent_framework.azure import AzureAIAgentClient


def encode_sse(data: dict) -> str:
    """Format a dict as an SSE message event.

    The mobile react-native-sse EventSource listens for the default
    'message' event type. No 'event:' field is needed.
    """
    return f"data: {json.dumps(data)}\n\n"


async def stream_text_capture(
    client: AzureAIAgentClient,
    user_text: str,
    tools: list,
    thread_id: str,
    run_id: str,
) -> AsyncGenerator[str, None]:
    """Stream a text capture through the Classifier agent as AG-UI SSE events.

    Iterates ChatResponseUpdate objects from the Foundry streaming API,
    detects tool outcomes, and yields SSE-formatted JSON matching the
    AG-UI protocol the mobile app expects.
    """
    messages = [Message(role="user", text=user_text)]
    options: ChatOptions = {"tools": tools}

    # Start SSE stream
    yield encode_sse({"type": "STEP_STARTED", "stepName": "Classifier"})

    # Outcome tracking
    detected_tool: str | None = None
    detected_tool_args: dict = {}
    tool_result: dict | None = None
    classifier_text_buffer: str = ""

    stream = client.get_response(messages=messages, stream=True, options=options)

    async for update in stream:
        for content in update.contents or []:
            if content.type == "text" and content.text:
                # Buffer classifier chain-of-thought (suppress from SSE)
                classifier_text_buffer += content.text

            elif content.type == "function_call":
                name = content.name
                if name == "file_capture":
                    detected_tool = name
                    # Parse arguments
                    args = content.arguments
                    if isinstance(args, str):
                        detected_tool_args = json.loads(args)
                    elif isinstance(args, dict):
                        detected_tool_args = dict(args)

            elif content.type == "function_result":
                result = content.result
                if isinstance(result, str):
                    try:
                        tool_result = json.loads(result)
                    except json.JSONDecodeError:
                        tool_result = {"raw": result}
                elif isinstance(result, dict):
                    tool_result = dict(result)

    # Step finished
    yield encode_sse({"type": "STEP_FINISHED", "stepName": "Classifier"})

    # Emit clean result text (matching v1 behavior)
    if detected_tool == "file_capture" and tool_result:
        bucket = tool_result.get("bucket", detected_tool_args.get("bucket", "?"))
        confidence = tool_result.get("confidence", detected_tool_args.get("confidence", 0.0))
        status = detected_tool_args.get("status", "classified")
        item_id = tool_result.get("item_id", "")

        # Construct clean result text
        if status == "misunderstood":
            question = detected_tool_args.get("title", "Could you clarify?")
            result_text = question
        elif status == "pending":
            result_text = f"Filed (needs review) -> {bucket} ({confidence:.2f})"
        else:
            result_text = f"Filed -> {bucket} ({confidence:.2f})"

        # Emit text message
        msg_id = f"msg-{run_id}"
        yield encode_sse({"type": "TEXT_MESSAGE_CONTENT", "messageId": msg_id, "delta": result_text})

        # Emit custom event based on status
        if status == "misunderstood":
            yield encode_sse({
                "type": "CUSTOM",
                "name": "MISUNDERSTOOD",
                "value": {
                    "threadId": thread_id,
                    "inboxItemId": item_id,
                    "questionText": detected_tool_args.get("title", ""),
                },
            })
        elif status == "pending":
            yield encode_sse({
                "type": "CUSTOM",
                "name": "HITL_REQUIRED",  # v1 compat
                "value": {
                    "threadId": thread_id,
                    "inboxItemId": item_id,
                    "questionText": result_text,
                },
            })
        else:
            yield encode_sse({
                "type": "CUSTOM",
                "name": "CLASSIFIED",
                "value": {
                    "inboxItemId": item_id,
                    "bucket": bucket,
                    "confidence": confidence,
                },
            })

    # RUN_FINISHED
    yield encode_sse({"type": "RUN_FINISHED", "threadId": thread_id, "runId": run_id})
```

### Pattern 2: Voice Capture with Synthetic Steps

**What:** Voice capture POSTs audio as multipart. The endpoint uploads to Blob Storage, then runs the Classifier agent with a message containing the blob URL. The agent calls `transcribe_audio` then `file_capture` as two separate tool calls. The adapter detects these in the stream and emits synthetic step events.

**When to use:** For the `/api/voice-capture` endpoint.

**Key difference from v1:** In v1, transcription was a separate "Perception" step done before the workflow. In v2, transcription is a `@tool` on the Classifier agent itself. The adapter must detect `transcribe_audio` function_call in the stream and emit a synthetic "Transcription" step.

**Example:**
```python
async def stream_voice_capture(
    client: AzureAIAgentClient,
    blob_url: str,
    tools: list,
    thread_id: str,
    run_id: str,
) -> AsyncGenerator[str, None]:
    """Stream voice capture: transcription step + classification step."""
    messages = [Message(
        role="user",
        text=f"Transcribe and classify this voice recording: {blob_url}",
    )]
    options: ChatOptions = {"tools": tools}

    current_step: str | None = None
    detected_tool_name: str | None = None
    # ... same outcome tracking as text capture ...

    stream = client.get_response(messages=messages, stream=True, options=options)

    async for update in stream:
        for content in update.contents or []:
            if content.type == "function_call":
                name = content.name

                if name == "transcribe_audio" and current_step != "Transcription":
                    # Emit transcription step start
                    yield encode_sse({"type": "STEP_STARTED", "stepName": "Transcription"})
                    current_step = "Transcription"

                elif name == "file_capture":
                    # Close transcription step if open
                    if current_step == "Transcription":
                        yield encode_sse({"type": "STEP_FINISHED", "stepName": "Transcription"})
                    # Start classifier step
                    yield encode_sse({"type": "STEP_STARTED", "stepName": "Classifier"})
                    current_step = "Classifier"
                    detected_tool_name = name
                    # ... parse args ...

            elif content.type == "function_result":
                # ... extract result ...
                pass

    # Close open step
    if current_step:
        yield encode_sse({"type": "STEP_FINISHED", "stepName": current_step})

    # ... emit result text and custom events same as text capture ...
    yield encode_sse({"type": "RUN_FINISHED", "threadId": thread_id, "runId": run_id})
```

### Pattern 3: FastAPI StreamingResponse SSE Endpoint

**What:** FastAPI endpoint accepts POST, creates SSE generator, returns StreamingResponse.

**Example:**
```python
from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api", tags=["Capture"])

@router.post("/ag-ui")
async def text_capture_endpoint(request: Request, body: CaptureRequest) -> StreamingResponse:
    """Stream text capture classification as AG-UI SSE events."""
    client = request.app.state.classifier_client
    tools = request.app.state.classifier_agent_tools
    thread_id = body.thread_id or f"thread-{uuid4()}"
    run_id = body.run_id or f"run-{uuid4()}"

    user_text = body.messages[0]["content"] if body.messages else ""

    generator = stream_text_capture(
        client=client,
        user_text=user_text,
        tools=tools,
        thread_id=thread_id,
        run_id=run_id,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

### Anti-Patterns to Avoid

- **DO NOT use `ag_ui` package:** Deleted in Phase 6. The SSE format is trivial -- `data: {json}\n\n`. Hand-rolling the encoder is 3 lines of code.
- **DO NOT create a class for the adapter:** The old `AGUIWorkflowAdapter` was a 540-line class because it wrapped the complex HandoffBuilder workflow. The Foundry streaming API is simpler -- async generator functions are sufficient.
- **DO NOT buffer the entire stream before yielding:** Yield SSE events incrementally as they are detected. The mobile app renders progress in real-time.
- **DO NOT use `event:` field in SSE:** The react-native-sse `EventSource` listens for `"message"` events (the default when no `event:` field is present). Adding `event: custom_type` would break the mobile client.
- **DO NOT use `sse-starlette` package:** It adds complexity for no benefit. Raw `StreamingResponse` is proven to work in v1.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tool call execution loop | Manual thread/run polling, tool output submission | `AzureAIAgentClient.get_response(stream=True)` | The SDK's `FunctionInvocationLayer` handles the entire tool call loop: detect function_call -> execute local @tool -> submit result -> resume streaming. This is transparent to the consumer. |
| Thread management | Manual `create_thread()` / `create_run()` / `get_run_steps()` | `get_response()` with `ChatOptions(conversation_id=thread_id)` | The SDK creates threads automatically. Pass `conversation_id` in options to reuse a thread for follow-up. |
| Response finalization | Manual update collection and message assembly | `ResponseStream.get_final_response()` | If needed after streaming, the stream's finalizer produces a `ChatResponse` from collected updates. |

**Key insight:** The biggest complexity reduction vs v1 is that the SDK handles the tool call loop. In v1, the HandoffBuilder workflow + WorkflowAgent did this; now the `FunctionInvocationLayer` mixin in `AzureAIAgentClient` does it automatically during `stream=True` iteration. The adapter just observes the content items flowing through.

## Common Pitfalls

### Pitfall 1: ResponseStream is Single-Consumption

**What goes wrong:** Iterating a `ResponseStream` twice raises an error or returns nothing. The stream tracks `_consumed` state internally.
**Why it happens:** `ResponseStream.__anext__` sets `_consumed = True` on `StopAsyncIteration` and runs cleanup hooks.
**How to avoid:** Iterate the stream exactly once inside the async generator. If you need to also call `get_final_response()`, do it after the `async for` loop completes -- the finalizer uses the internally collected `_updates` list.
**Warning signs:** Empty SSE stream, or `StopAsyncIteration` error on second consumption.

### Pitfall 2: Content.arguments Can Be str or dict

**What goes wrong:** Assuming `content.arguments` is always a `dict` and calling `.get()` on a JSON string, or vice versa.
**Why it happens:** The Azure AI Agents service may return function call arguments as a JSON string or as a parsed dict, depending on SDK version and streaming context.
**How to avoid:** Always check type: `if isinstance(args, str): args = json.loads(args)`.
**Warning signs:** `TypeError` or `AttributeError` when accessing function call arguments.

### Pitfall 3: SSE Double Newline Termination

**What goes wrong:** SSE events not being received by the mobile client.
**Why it happens:** SSE spec requires each event to end with `\n\n`. The react-native-sse parser splits on double-newline boundaries. Missing the trailing `\n\n` means the event is buffered indefinitely.
**How to avoid:** Always use `f"data: {json.dumps(payload)}\n\n"` -- never forget the double newline.
**Warning signs:** Mobile app appears frozen, no events received.

### Pitfall 4: Chain-of-Thought Leaking to Client

**What goes wrong:** The Classifier agent's reasoning text (chain-of-thought) is sent to the mobile app as `TEXT_MESSAGE_CONTENT` events, showing raw LLM reasoning to the user.
**Why it happens:** The agent produces text content during reasoning before calling tools. If the adapter naively yields all text content as SSE events, CoT leaks through.
**How to avoid:** Buffer ALL `Content.type == "text"` from the stream. Only emit a clean, constructed result string after the stream completes and the outcome is known (from function_call/function_result inspection). This matches v1 behavior exactly.
**Warning signs:** User sees internal reasoning like "Let me classify this as Admin..." in the app.

### Pitfall 5: Tool Result Shape Mismatch

**What goes wrong:** The adapter expects `content.result` to be a dict but gets a string, or the dict structure doesn't match expectations.
**Why it happens:** The `@tool` function returns a dict, but the SDK may serialize it to a JSON string in the `Content.result` field during streaming.
**How to avoid:** Parse `content.result` defensively: try `json.loads()` if it's a string, use `dict()` if it's a mapping. Always have fallback values.
**Warning signs:** `CLASSIFIED` event has wrong bucket/confidence, or missing `inboxItemId`.

### Pitfall 6: Missing X-Accel-Buffering Header

**What goes wrong:** SSE events are received in batches instead of individually.
**Why it happens:** Reverse proxies (nginx, Azure Container Apps ingress) buffer responses by default. Without `X-Accel-Buffering: no`, events accumulate until the buffer fills.
**How to avoid:** Always include `"X-Accel-Buffering": "no"` in StreamingResponse headers. Also include `"Cache-Control": "no-cache"` and `"Connection": "keep-alive"`.
**Warning signs:** Events arrive in bursts after long pauses.

### Pitfall 7: Conversation ID for Follow-Up Threads

**What goes wrong:** Follow-up re-classification creates a new Foundry thread, causing the orphaned inbox document problem from v1.
**Why it happens:** Each `get_response()` call creates a new Foundry thread by default. For follow-up classification, the combined text creates a new classification result that needs reconciliation with the original inbox item.
**How to avoid:** The follow-up endpoint must perform the same orphan reconciliation as v1: after the stream completes, copy the new classification metadata to the original inbox item, delete the orphaned inbox doc, and update the bucket doc's `inboxRecordId`. This is endpoint logic, not adapter logic.
**Warning signs:** Duplicate inbox entries after follow-up, or inbox item still showing as "misunderstood" after successful re-classification.

## Code Examples

### Example 1: Calling get_response with stream=True

```python
# Source: Verified from agent-framework-azure-ai 1.0.0rc2 source code
# AzureAIAgentClient._inner_get_response (streaming branch)

from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient

async def example_streaming(client: AzureAIAgentClient, tools: list):
    messages = [Message(role="user", text="Pick up prescription at Walgreens")]
    options: ChatOptions = {"tools": tools}

    # Returns ResponseStream[ChatResponseUpdate, ChatResponse]
    stream = client.get_response(messages=messages, stream=True, options=options)

    # Iterate updates -- SDK handles tool calls transparently
    async for update in stream:
        print(f"Role: {update.role}")
        print(f"Contents: {len(update.contents)} items")
        for content in update.contents:
            print(f"  type={content.type}")
            if content.type == "text":
                print(f"  text={content.text}")
            elif content.type == "function_call":
                print(f"  name={content.name}, args={content.arguments}")
            elif content.type == "function_result":
                print(f"  result={content.result}")
            elif content.type == "usage":
                print(f"  usage={content.usage_details}")
```

### Example 2: SSE Wire Format

```python
# What the mobile client receives (verified from react-native-sse source):
#
# data: {"type":"STEP_STARTED","stepName":"Classifier"}\n\n
# data: {"type":"STEP_FINISHED","stepName":"Classifier"}\n\n
# data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-123","delta":"Filed -> Admin (0.85)"}\n\n
# data: {"type":"CUSTOM","name":"CLASSIFIED","value":{"inboxItemId":"abc-123","bucket":"Admin","confidence":0.85}}\n\n
# data: {"type":"RUN_FINISHED","threadId":"thread-123","runId":"run-456"}\n\n
#
# Key: No 'event:' field. react-native-sse defaults to 'message' event type.
# Key: Each line ends with \n\n (double newline).
# Key: JSON is on a single line after 'data: '.

import json

def encode_sse(data: dict) -> str:
    """Encode a dict as an SSE data event."""
    return f"data: {json.dumps(data)}\n\n"
```

### Example 3: ChatResponseUpdate Content Types Observed During Streaming

```python
# Source: Verified from AzureAIAgentClient._process_stream source code

# During a text capture, the stream yields these ChatResponseUpdate sequences:
#
# 1. ThreadRun events (CREATED, QUEUED, IN_PROGRESS) -- contents=[], informational
# 2. RunStep events (CREATED, IN_PROGRESS) -- contents=[], set response_id
# 3. MessageDeltaChunk -- text content (agent's chain-of-thought reasoning)
# 4. ThreadRun REQUIRES_ACTION -- function_call content (agent wants to call file_capture)
#    [SDK intercepts, executes @tool, submits result, resumes streaming]
# 5. RunStep COMPLETED -- usage content (token counts)
# 6. MessageDeltaChunk -- text content (agent's final response after tool call)
#
# For voice capture (agent calls transcribe_audio then file_capture):
# 1-3. Same as above
# 4. ThreadRun REQUIRES_ACTION -- function_call for transcribe_audio
#    [SDK executes transcribe_audio @tool, submits transcript, resumes]
# 5. MessageDeltaChunk -- text content (agent reasoning about transcript)
# 6. ThreadRun REQUIRES_ACTION -- function_call for file_capture
#    [SDK executes file_capture @tool, submits result, resumes]
# 7. RunStep COMPLETED -- usage content
# 8. MessageDeltaChunk -- final text
```

### Example 4: Detecting Outcomes from Stream Content

```python
# Source: Pattern derived from v1 AGUIWorkflowAdapter._process_update
# and verified against ChatResponseUpdate.contents structure

def detect_outcome(content: Content) -> tuple[str | None, dict]:
    """Detect classification outcome from a Content item.

    Returns (tool_name, parsed_args) or (None, {}).
    """
    if content.type == "function_call" and content.name == "file_capture":
        args = content.arguments
        if isinstance(args, str):
            args = json.loads(args)
        elif isinstance(args, Mapping):
            args = dict(args)
        else:
            args = {}
        return ("file_capture", args)
    return (None, {})


def extract_result(content: Content) -> dict | None:
    """Extract the tool result dict from a function_result Content item."""
    if content.type != "function_result":
        return None
    result = content.result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return None
    elif isinstance(result, dict):
        return dict(result)
    return None
```

## State of the Art

| Old Approach (v1) | Current Approach (v2) | When Changed | Impact |
|---|---|---|---|
| `ag_ui.encoder.EventEncoder` | Raw `f"data: {json}\n\n"` | Phase 6 (ag_ui deleted) | No external dependency for SSE encoding |
| `HandoffBuilder` + `Workflow` + `WorkflowAgent` | Direct `AzureAIAgentClient.get_response(stream=True)` | Phase 6 (HandoffBuilder deleted) | ~540 lines reduced to ~150 lines |
| `AzureOpenAIChatClient` + `Agent` + `as_agent()` | `AzureAIAgentClient` with `agent_id` + `ChatOptions(tools=[...])` | Phase 7 | Persistent Foundry agent, tools at request time |
| `WorkflowEvent.executor_invoked/completed` | Synthetic step events from function_call detection | Phase 8 | No workflow events available; detect steps from tool calls |
| Separate Perception agent for transcription | `transcribe_audio` as `@tool` on Classifier | Phase 7 | Single agent, simpler streaming; transcription is a tool call in the stream |

**Deprecated/outdated:**
- `ag_ui` Python package: Deleted in Phase 6. SSE encoding is trivial.
- `HandoffBuilder` / `Workflow`: Deleted in Phase 6. Direct agent calls replace multi-agent orchestration.
- `AzureOpenAIChatClient`: Replaced by `AzureAIAgentClient` in Phase 6.
- Separate Perception/Orchestrator agents: Consolidated into single Classifier agent.

## Open Questions

1. **Content.result serialization during streaming**
   - What we know: In non-streaming mode (Phase 7 integration test), `file_capture` returns a dict `{"bucket": "...", "confidence": ..., "item_id": "..."}`. In streaming mode, `Content.result` may be a JSON string or a dict.
   - What's unclear: Exact serialization format of `Content.result` during streaming has not been tested empirically. The `_process_stream` method passes `raw_representation` from the Azure service.
   - Recommendation: Handle both str and dict defensively. The integration test for Phase 8 should verify the exact format by printing `content.result` and `type(content.result)` during a live streaming call. Confidence: MEDIUM.

2. **HITL_REQUIRED vs MISUNDERSTOOD event distinction**
   - What we know: v1 had two separate flows: HITL_REQUIRED for low-confidence (bucket buttons), MISUNDERSTOOD for can't-parse (conversation mode). In v2, `file_capture` has a `status` parameter: "classified" (high confidence), "pending" (low confidence), "misunderstood".
   - What's unclear: The mapping is: status="pending" -> HITL_REQUIRED, status="misunderstood" -> MISUNDERSTOOD. But the agent instructions need to ensure the agent uses the right status values. Need to verify the Foundry portal instructions match.
   - Recommendation: Map `status="pending"` to `HITL_REQUIRED` custom event and `status="misunderstood"` to `MISUNDERSTOOD`. Add assertions in tests. Confidence: HIGH.

3. **Blob cleanup after voice capture**
   - What we know: v1 deleted the blob after transcription. In v2, `transcribe_audio` downloads from blob URL, transcribes, and returns text. The blob is created by the endpoint before calling the agent.
   - What's unclear: Should the endpoint delete the blob after the stream completes, or should the `transcribe_audio` tool delete it?
   - Recommendation: The endpoint should delete the blob after the stream completes (in a `finally` block), matching v1 behavior. The tool should not delete -- it may need to retry. Confidence: HIGH.

## Sources

### Primary (HIGH confidence)
- `agent-framework-azure-ai==1.0.0rc2` installed source code -- `AzureAIAgentClient._inner_get_response`, `_process_stream`, `_create_agent_stream`
- `agent-framework==1.0.0rc2` installed source code -- `ResponseStream`, `ChatResponseUpdate`, `Content`, `FunctionInvocationLayer.get_response`
- `azure-ai-agents==1.2.0b5` installed source code -- `AgentStreamEvent` enum values
- Mobile client source: `mobile/lib/ag-ui-client.ts`, `mobile/lib/types.ts` -- AG-UI event contract
- Mobile SSE parser: `mobile/node_modules/react-native-sse/src/EventSource.js` -- SSE wire format parsing
- Old v1 adapter: `git show 30cef45^:backend/src/second_brain/agents/workflow.py` -- `AGUIWorkflowAdapter` event emission patterns
- Old v1 endpoints: `git show 30cef45^:backend/src/second_brain/main.py` -- endpoint signatures, SSE helpers, voice capture flow

### Secondary (MEDIUM confidence)
- [AG-UI Protocol Event Types](https://docs.ag-ui.com/concepts/events) -- official AG-UI event type documentation
- [FastAPI StreamingResponse SSE](https://fastapi.tiangolo.com/advanced/custom-response/) -- FastAPI custom response documentation

### Tertiary (LOW confidence)
- Content.result serialization format during streaming -- not empirically tested in v2 context. Based on source code analysis only.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All packages already installed, source code inspected
- Architecture: HIGH -- Direct source code reading of streaming pipeline, verified v1 patterns
- SSE wire format: HIGH -- react-native-sse parser source code verified, mobile client event handling confirmed
- Tool call detection: HIGH -- `_process_stream` source code shows exact Content types emitted
- Pitfalls: HIGH -- Based on v1 experience (540-line adapter with known issues) and source code analysis
- Content.result format in streaming: MEDIUM -- Source code analysis but not empirically tested

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable -- agent-framework SDK is RC, patterns unlikely to change significantly)
