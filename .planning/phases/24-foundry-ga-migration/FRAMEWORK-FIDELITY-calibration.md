# Framework-Fidelity Audit: calibration

**Date:** 2026-05-07
**Scope:** calibration (audit subject = current state of `backend/src/second_brain/`)
**Diff command:** `git ls-files backend/src/second_brain/` (calibration substitute — no migration diff yet)
**Files in audit scope:** 78 files under `backend/src/second_brain/`
**Design reference:** `docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md`
**Audit subject snapshot:** `.planning/phases/23/AUDIT-DIFF-calibration.patch` (file list)

## Verdict

**FAIL** — current RC backend predates the framework-first principle (D-07). Pervasive RC SDK coupling, custom Python in cross-cutting concerns where framework primitives are required, and probe fixtures absent (Phase 23.0 has not run). This is the expected and correct outcome for a calibration run against pre-migration code.

| Counter | Value |
|---|---:|
| Pass findings (correct framework usage) | 3 |
| Warnings | 1 |
| Failures (blocking) | 19 |
| Prerequisite failures | 1 |

## Prerequisite Status

- **Probe fixtures missing** — `backend/tests/fixtures/foundry-probe/` does not exist. Phase 23.0 has not been executed yet. Every Phase 23.0 probe (`streaming_shape`, `tool_call_extraction`, `tool_choice_required`, `session_rehydration`, `auth_probe`) is unavailable, so any code that should consume these fixtures is automatically classified ⚠️. Strict probe-fidelity check is therefore degraded — see Probe Fixture table below.
- **No migration diff exists** — calibration uses the entire `backend/src/second_brain/` tree as the audit subject in lieu of a `git diff <sha>..HEAD` against committed migration work. The auditor proceeds against the snapshot.

## Failures (blocking)

### F-01: RC framework client pervasively imported / instantiated

- **File:** `backend/src/second_brain/main.py:33`, lifespan body lines 486-823 (10 distinct construction sites including 3 in `_make_*_client` factories)
- **Concern:** Tool / agent layer must use GA `agent-framework` + `agent-framework-foundry` (`FoundryChatClient`, `Agent(...)`). RC `agent_framework.azure.AzureAIAgentClient` must be removed.
- **Code (offending):**
```python
from agent_framework.azure import AzureAIAgentClient
...
foundry_client = AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    model_deployment_name="gpt-4o",
)
...
classifier_client = AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    agent_id=classifier_agent_id,
    should_cleanup_agent=False,
    middleware=[AuditAgentMiddleware(agent_name="classifier"), ToolTimingMiddleware()],
)
```
- **Framework primitive that should have been used:** GA `agent_framework_foundry.FoundryChatClient(project_endpoint=..., credential=...)` wrapped in `agent_framework.Agent(client=..., instructions=..., tools=[...], middleware=[...])`. Per design D-05 + Phase 23 task groups: every construction site replaced; agent_id-based persistent agent shells go away in favor of code-owned agents with instructions loaded from `agents/instructions/<agent>.md`.
- **Justification status:** None.

### F-02: RC framework client imported in `warmup.py`

- **File:** `backend/src/second_brain/warmup.py:8`, `warmup.py:16-19, 41`
- **Concern:** Same as F-01 (every consumer of agent client must be GA-shaped). Warmup pings the wrong type and uses RC `client.get_response(messages=...)` shape.
- **Code (offending):**
```python
from agent_framework.azure import AzureAIAgentClient
async def agent_warmup_loop(
    clients: list[tuple[str, AzureAIAgentClient]], ...
) -> None:
    ...
    await client.get_response(messages=messages)
```
- **Framework primitive that should have been used:** GA `Agent.run(...)` against a singleton `Agent` keyed by name; warmup ping becomes a single-tool no-op call against the GA agent.
- **Justification status:** None.

### F-03: RC framework client imported in `processing/admin_handoff.py`

- **File:** `backend/src/second_brain/processing/admin_handoff.py:14-15, 141, 235, 242-244, 295-302, 418`
- **Concern:** Admin handoff is the canonical Phase 23.2 surface. Replaces with GA `Agent.run(messages)` and `AgentRunResponse` extraction path captured by Phase 23.0 `tool_call_extraction.json` probe.
- **Code (offending):**
```python
from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
...
messages = [Message(role="user", text=enriched_text)]
options = ChatOptions(tools=admin_tools)
async with asyncio.timeout(60):
    response = await admin_client.get_response(messages=messages, options=options)
```
- **Framework primitive that should have been used:** `agent.run(messages, ...)` returning `AgentRunResponse` (path documented by `tool_call_extraction.json` probe fixture). RC `Message` / `ChatOptions` types disappear from this module.
- **Justification status:** None.

### F-04: RC framework client imported in `streaming/adapter.py`

- **File:** `backend/src/second_brain/streaming/adapter.py:17-18, 154-156, 353-355, 557-559`
- **Concern:** Classifier streaming consumes `client.get_response(stream=True)` returning `AsyncIterable[ChatResponseUpdate]`. Phase 23.3 must consume `agent.run_stream()` returning `AsyncIterable[AgentRunResponseUpdate]` per Phase 23.0 `streaming_shape.json` probe.
- **Code (offending):**
```python
from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
...
stream = client.get_response(messages=messages, stream=True, options=options)
async for update in stream:
    if (getattr(update, "conversation_id", None) and not foundry_conversation_id):
        foundry_conversation_id = update.conversation_id
    for content in update.contents or []:
        if content.type == "text" ...
```
- **Framework primitive that should have been used:** `agent.run_stream(messages, thread=..., tool_choice=...)` yielding `AgentRunResponseUpdate`. The exact field names (`update.text`, `update.contents[]`, `update.<session-id-field>`) are captured in `streaming_shape.json`.
- **Justification status:** None.

### F-05: RC framework client imported in `streaming/investigation_adapter.py`

- **File:** `backend/src/second_brain/streaming/investigation_adapter.py:26-27, 70-72, 114-117, 128-132`
- **Concern:** Same as F-04 for Investigation. Phase 23.1 (first task group) rewrites this against the GA streaming contract; this is one of the simplest surfaces and should already be GA-shaped before Admin/Classifier are migrated.
- **Code (offending):**
```python
from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
...
messages = [Message(role="user", text=question)]
options: ChatOptions = {"tools": tools}
if thread_id:
    options["conversation_id"] = thread_id
...
stream = client.get_response(messages=messages, stream=True, options=options)
```
- **Framework primitive that should have been used:** `agent.run_stream(messages, thread=AgentThread(...))` (or `agent.get_session(stored_id)` per Phase 23.0 `session_rehydration.json` probe).
- **Justification status:** None.

### F-06: RC framework types in `eval/runner.py` (RC-shaped eval invocation)

- **File:** `backend/src/second_brain/eval/runner.py:21, 32, 133-145, 278-290`
- **Concern:** Eval invocation facade. Per design D-04 + Phase 23.2/23.3 commit clusters, an `EvalAgentInvoker` interface inside `eval/` must hide RC vs. GA, and the GA implementation calls `agent.run(messages)` not `client.get_response(...)`. Today the runner calls RC `client.get_response()` with `Message` + `ChatOptions` directly — when Admin or Classifier becomes a GA `Agent`, these calls fail at runtime because the GA `Agent` exposes `run`/`run_stream`, not `get_response`.
- **Code (offending):**
```python
from agent_framework import ChatOptions, Message
...
messages = [Message(role="user", text=case["inputText"])]
options = ChatOptions(
    tools=[eval_tools.file_capture],
    tool_choice={"mode": "required", "required_function_name": "file_capture"},
)
await _call_with_retry(
    lambda m=messages, o=options: classifier_client.get_response(messages=m, options=o),
    ...
)
```
- **Framework primitive that should have been used:** `EvalAgentInvoker` facade, GA implementation invoking `agent.run(messages)` and adapting `AgentRunResponse`. RC implementation of the facade lives temporarily during the migration window and is deleted in 23.3 cleanup commit.
- **Justification status:** None.

### F-07: RC framework types in `eval/foundry.py` (app-mediated dataset generator)

- **File:** `backend/src/second_brain/eval/foundry.py:856-942` (and surrounding `generate_app_mediated_dataset`)
- **Concern:** Same as F-06. This module also calls `client.get_response()` with RC `Message`/`ChatOptions`. Must route through `EvalAgentInvoker` facade.
- **Code (offending):**
```python
from agent_framework import ChatOptions, Message
...
messages = [Message(role="user", text=item["inputText"])]
options = ChatOptions(tools=classifier_tools)
async with asyncio.timeout(60):
    response = await classifier_client.get_response(messages=messages, options=options)
if hasattr(response, "messages"):
    for msg in response.messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls: ...
```
- **Framework primitive that should have been used:** `EvalAgentInvoker.run(case)` returning a normalized result — internally `agent.run(messages)` for the GA path. Tool-call extraction follows the documented path from `tool_call_extraction.json`.
- **Justification status:** None. Note that this code already does duck-typed extraction (`hasattr(msg, "tool_calls")`), which is exactly the kind of guesswork the probe fixtures are designed to eliminate.

### F-08: RC `@tool(approval_mode="never_require")` decorator on every production tool

- **File (16 occurrences):**
  - `backend/src/second_brain/tools/admin.py:121, 191, 235, 249, 370, 537` (6)
  - `backend/src/second_brain/tools/classification.py:75` (1, file_capture)
  - `backend/src/second_brain/tools/investigation.py:112, 179, 250, 297, 372, 485, 594, 663, 743` (9)
  - `backend/src/second_brain/tools/recipe.py:102` (1, fetch_recipe_url)
  - `backend/src/second_brain/tools/transcription.py:58` (1, transcribe_audio)
- **Concern:** Tool registration. `approval_mode` is an RC concept removed in GA. Must drop the parameter; the bare `@tool` decorator (or no decorator + plain function) plus `Annotated[..., Field(description=...)]` is the GA pattern.
- **Code (offending) — representative:**
```python
@tool(approval_mode="never_require")
async def file_capture(
    self,
    text: Annotated[str, Field(description="The original captured text to file")],
    ...
```
- **Framework primitive that should have been used:** Either `@tool` (no kwarg) when name/description override is needed, or no decorator at all — function passed directly into `tools=[...]` on `Agent(...)`. The `Annotated[..., Field(description=...)]` coverage that is already present is correct and stays.
- **Justification status:** None.

### F-09: Python "safety net" in classifier streaming (D-07b explicit deletion target)

- **File:** `backend/src/second_brain/streaming/adapter.py:92-152` (`_safety_net_file_as_misunderstood`), call sites at lines 324-334, 526-538, 676-686.
- **Concern:** Required-tool semantics. D-07b explicitly states: "The classifier's Python safety net (`if the model didn't call file_capture, fire it ourselves as Misunderstood`) is **deleted**. Replaced by `tool_choice='required'` — but only after restructuring the classifier so this is safe." Voice path split (per D-07b) makes the safety net redundant by ensuring the classifier registers ONLY `file_capture` and `tool_choice='required'` is unambiguous.
- **Code (offending):**
```python
async def _safety_net_file_as_misunderstood(...) -> dict:
    """File a capture as misunderstood when the agent fails to call file_capture.

    This is a safety net -- the agent is an LLM and sometimes skips tool calls.
    Every capture MUST produce a filed item. When the agent doesn't cooperate,
    the adapter writes the misunderstood doc directly and emits a MISUNDERSTOOD
    event so the user gets a follow-up prompt instead of a dead end.
    """
    ...
    inbox_doc = InboxDocument(id=inbox_doc_id, ..., status="misunderstood")
    await inbox_container.create_item(...)
    span.set_attribute("capture.safety_net", True)
    logger.warning("Safety-net: agent skipped file_capture, ...")
```
- **Framework primitive that should have been used:** `tool_choice='required'` on `agent.run_stream(...)` (or provider-dict pinning `tool_choice={"type":"function","function":{"name":"file_capture"}}` if probe shows `'required'` doesn't enforce on Foundry Responses endpoint). With the voice path split, classifier registers only `file_capture` so `'required'` is unambiguous. Failures route to the new `forced_tool_failure` SSE sub-code, not silent fabrication.
- **Justification status:** None. Whole function deleted in Phase 23.3; behavioural shift from "silent MISUNDERSTOOD" to loud `forced_tool_failure` is intentional.

### F-10: RC-shaped `tool_choice` provider-dict in classifier streaming

- **File:** `backend/src/second_brain/streaming/adapter.py:182-188, 590-596`
- **Concern:** The current shape `{"mode": "required", "required_function_name": "file_capture"}` is the RC-era custom dict. Per design + `tool_choice_required.json` probe, the GA preferred form is `tool_choice='required'` (after voice split, only `file_capture` is registered) with provider-dict `{"type":"function","function":{"name":"file_capture"}}` as the documented fallback.
- **Code (offending):**
```python
options: ChatOptions = {
    "tools": tools,
    "tool_choice": {
        "mode": "required",
        "required_function_name": "file_capture",
    },
}
```
- **Framework primitive that should have been used:** `tool_choice='required'` on `agent.run_stream(...)` after voice path split has made `file_capture` the only tool registered on the classifier agent.
- **Justification status:** None.

### F-11: Voice tool registered on the same classifier agent as `file_capture` (blocks `tool_choice='required'`)

- **File:** `backend/src/second_brain/main.py:577-581`
- **Concern:** D-07b voice path split. Today the classifier agent has both `file_capture` and `transcribe_audio` registered, so `tool_choice='required'` cannot be unambiguous (model could be forced to call either). Phase 23.3 splits voice transcription out: it becomes either a direct transcription model call OR a single-tool sub-agent. The classifier agent registers ONLY `file_capture`.
- **Code (offending):**
```python
agent_tools = [classifier_tools.file_capture]
if app.state.transcription_tools:
    agent_tools.append(app.state.transcription_tools.transcribe_audio)
app.state.classifier_agent_tools = agent_tools
```
- **Framework primitive that should have been used:** Voice path becomes its own pipeline (probably a direct `AsyncAzureOpenAI.audio.transcriptions.create(...)` call before the classifier agent runs, mirroring what the follow-up-voice route already does at `api/capture.py:471`). Classifier agent gets `tools=[file_capture]` only.
- **Justification status:** None.

### F-12: Constructor-level `agent_id`-pinned RC clients are the conversation conflation hazard D-07's checklist warns against

- **File:** `backend/src/second_brain/main.py:564-574, 605-614, 702-712` and `_make_*_client` factories at `779-823`
- **Concern:** Conversation continuity. The RC `AzureAIAgentClient(agent_id=..., should_cleanup_agent=False)` constructor pattern is the analog of "constructor-level `conversation_id` on a singleton agent" — every caller of `classifier_client.get_response(...)` shares the same agent object and Foundry-side persistent agent shell. Per design + `session_rehydration.json` probe, the GA pattern is one `Agent` singleton per agent type AND per-call rehydration via `agent.get_session(stored_id)` (or `thread=AgentThread(...)`) using a durable identifier persisted on the Inbox doc.
- **Code (offending):**
```python
classifier_client = AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    agent_id=classifier_agent_id,
    should_cleanup_agent=False,
    middleware=[...],
)
```
- **Framework primitive that should have been used:** `Agent(client=FoundryChatClient(...), instructions=load_instructions("classifier"), tools=[file_capture], middleware=[...])` constructed once in lifespan; per-call rehydration via the API revealed by `session_rehydration.json`.
- **Justification status:** None.

### F-13: RC `conversation_id` round-trip (bypasses framework session API)

- **File:** `backend/src/second_brain/streaming/adapter.py:596` (classifier follow-up), `backend/src/second_brain/streaming/investigation_adapter.py:117` (investigation), captured throughout the stream loops at adapter.py 207-210, 404-407, 617-620 and capture.py 116-127, 169-191
- **Concern:** Conversation continuity. Storing/replaying `conversation_id` via `ChatOptions["conversation_id"]` is the RC opaque thread-id round-trip the design's checklist explicitly fails. Replace with the GA `AgentThread`/`get_session(stored_id)` shape that `session_rehydration.json` probe captures.
- **Code (offending):**
```python
options: ChatOptions = {
    "tools": tools,
    "tool_choice": {...},
    "conversation_id": foundry_thread_id,
}
```
- **Framework primitive that should have been used:** `agent.run_stream(messages, thread=AgentThread.from_id(stored_id))` or `thread = await agent.get_session(stored_id)` per the probe-captured GA API. The Inbox doc field rename from `foundryThreadId` to whatever the probe documents (likely `service_session_id`) is part of Phase 23.3.
- **Justification status:** None.

### F-14: Custom `tracer.start_as_current_span(...)` wrapping framework agent calls in `streaming/adapter.py`

- **File:** `backend/src/second_brain/streaming/adapter.py:175 ("capture_text"), 372 ("capture_voice"), 582 ("capture_follow_up")`
- **Concern:** Tracing. The framework emits its own `invoke_agent` / `execute_tool` spans. Hand-rolled spans wrapping `client.get_response(...)` create parallel custom Python around what the framework already does. Capture-context attributes (`capture.trace_id`, `capture.outcome`, etc.) belong on the framework-emitted agent span via the new `AgentMiddleware` in `agents/middleware/capture_trace.py` — not on a custom outer wrapper.
- **Code (offending):**
```python
with tracer.start_as_current_span("capture_text") as span:
    span.set_attribute("capture.type", "text")
    span.set_attribute("capture.thread_id", thread_id)
    ...
    stream = client.get_response(messages=messages, stream=True, options=options)
```
- **Framework primitive that should have been used:** `AgentMiddleware` reads the `capture_trace_id` ContextVar and calls `span.set_attribute("capture.trace_id", ...)` on the framework agent span — wrapping disappears. Capture-shape attributes either move to the agent span (where the framework already runs) or to the AppRequests span (which `api/capture.py:228` already tags).
- **Justification status:** None.

### F-15: Custom `tracer.start_as_current_span(...)` wrapping framework agent call in `streaming/investigation_adapter.py`

- **File:** `backend/src/second_brain/streaming/investigation_adapter.py:96 ("investigate")`
- **Concern:** Same as F-14, on the investigation surface. Custom `investigate` span wraps `client.get_response(...)` and duplicates the framework agent span.
- **Code (offending):**
```python
with tracer.start_as_current_span("investigate") as span:
    span.set_attribute("investigate.question_length", len(question))
    ...
    stream = client.get_response(messages=messages, stream=True, options=options)
```
- **Framework primitive that should have been used:** Same as F-14 — capture-trace `AgentMiddleware` puts the attribute on the framework `invoke_agent` span. Phase 23.1 is the first task group to fix this surface.
- **Justification status:** None.

### F-16: Custom `tracer.start_as_current_span(...)` wrapping framework agent call in `processing/admin_handoff.py`

- **File:** `backend/src/second_brain/processing/admin_handoff.py:177 ("admin_agent_process"), 441 ("admin_agent_batch_process")`
- **Concern:** Same as F-14, on the admin processing surface.
- **Code (offending):**
```python
with tracer.start_as_current_span("admin_agent_process") as span:
    span.set_attribute("admin.inbox_item_id", inbox_item_id)
    ...
    response = await admin_client.get_response(messages=messages, options=options)
```
- **Framework primitive that should have been used:** Same as F-14 — `AgentMiddleware` tags the framework agent span. Phase 23.2 fixes this surface.
- **Justification status:** None.

### F-17: Existing `AgentMiddleware` / `FunctionMiddleware` use `tracer.start_as_current_span` instead of operating on framework-emitted spans

- **File:** `backend/src/second_brain/agents/middleware.py:44 ("classifier_agent_run" etc.), 72 ("tool_<name>")`
- **Concern:** Capture-trace propagation (framework spans). Both `AuditAgentMiddleware` and `ToolTimingMiddleware` correctly extend the GA middleware base classes (good), but their bodies re-implement what the framework already does — they create *new* `tracer.start_as_current_span` blocks named e.g. `classifier_agent_run` and `tool_file_capture`, mirroring the framework's own `invoke_agent` / `execute_tool` spans. The result is span-doubling: framework emits its span, the custom middleware emits a parallel one, and AppRequests gains two siblings per agent run.
- **Code (offending):**
```python
class AuditAgentMiddleware(AgentMiddleware):
    async def process(self, context: AgentContext, call_next) -> None:
        with tracer.start_as_current_span(self._span_name) as span:
            span.set_attribute("agent.name", self._agent_name)
            await call_next()

class ToolTimingMiddleware(FunctionMiddleware):
    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        with tracer.start_as_current_span(f"tool_{func_name}") as span:
            span.set_attribute("tool.name", func_name)
            await call_next()
```
- **Framework primitive that should have been used:** Middleware reads from `context` and calls `set_attribute` on the framework's *current* span (e.g. `from opentelemetry import trace; trace.get_current_span().set_attribute(...)`), not start a new span. The new `agents/middleware/capture_trace.py` should:
  ```python
  class CaptureTraceAgentMiddleware(AgentMiddleware):
      async def process(self, context, call_next):
          trace_id = capture_trace_id_var.get("")
          if trace_id:
              trace.get_current_span().set_attribute("capture.trace_id", trace_id)
          await call_next()
  ```
- **Justification status:** None.

### F-18: Probe-fixture-shaped extraction code is missing — the migration is currently coded against documentation/imagination

- **Files:** `processing/admin_handoff.py` (admin tool-call extraction, ought to consume `tool_call_extraction.json`); `streaming/adapter.py` (streaming shape, ought to consume `streaming_shape.json`); classifier follow-up code in `api/capture.py` + `streaming/adapter.py:557-705` (session rehydration, ought to consume `session_rehydration.json`); classifier `tool_choice` in `streaming/adapter.py:182-188, 590-596` (ought to consume `tool_choice_required.json`); `main.py:484-510` Foundry client construction (ought to consume `auth_probe.json`).
- **Concern:** Strict probe fidelity (Q2). Phase 23.0 has not been executed. The migration cannot be planned faithfully without the probes — every code path that does field-name extraction (e.g. `getattr(content, "call_id", None)`, `getattr(update, "conversation_id", None)`, `hasattr(msg, "tool_calls")`) is currently guessing against the RC SDK's actual shape. Those guesses MAY transfer to GA, but probe fixtures are the only authoritative source.
- **Status:** ❌ pre-condition: probe fixtures must exist before any 23.x migration commit lands. Until then, all five rows of the probe-fidelity table below are forced "Missing".
- **Justification status:** N/A — this is a prerequisite, not a justifiable deviation.

### F-19: Classifier agent shell creates portal-managed agent with no instructions content (D-02 violation)

- **File:** `backend/src/second_brain/agents/classifier.py:55-65`, mirrored in `agents/admin.py:56-66` and `agents/investigation.py:58-68`
- **Concern:** D-02 — repo markdown is the only source of truth for agent instructions. Currently each `ensure_*_agent` creates a Foundry-portal-managed agent shell with NO instructions, then logs "SET INSTRUCTIONS IN AI FOUNDRY PORTAL." Every instruction change is portal-only with no git history, no diff, no rollback — exactly the inverted-priority pattern D-02 reverses.
- **Code (offending):**
```python
new_agent = await foundry_client.agents_client.create_agent(
    model="gpt-4o",
    name="Classifier",
)
logger.info(
    "NEW Classifier agent: id=%s -- "
    "SET INSTRUCTIONS IN AI FOUNDRY PORTAL and "
    "UPDATE AZURE_AI_CLASSIFIER_AGENT_ID in env",
    new_agent.id,
)
```
- **Framework primitive that should have been used:** `Agent(client=FoundryChatClient(...), instructions=load_instructions("classifier"), tools=[...], middleware=[...])` where `load_instructions` reads `agents/instructions/classifier.md`. The portal-managed-agent-id mechanism (`AZURE_AI_*_AGENT_ID` env vars) becomes orphaned and is removed in Phase 23.3 cleanup commit. Concomitantly, `agents/instructions/{classifier,admin,investigation}.md` files must exist (Phase 23.0 deliverable: export current portal text into `.planning/phases/23.0/CANDIDATE-instructions/`, reconcile drift, then promote).
- **Justification status:** None. Note that `docs/foundry/investigation-agent-instructions.md` was already canonicalized for Investigation in Phase 17.1 — that file is the source for `agents/instructions/investigation.md` per the design.

## Warnings

### W-01: `CaptureTraceSpanProcessor` retained as bulk tagger — narrowing required

- **File:** `backend/src/second_brain/observability/span_processor.py:16-39` (registered at `main.py:23` via `configure_azure_monitor(span_processors=[CaptureTraceSpanProcessor()])`)
- **Concern:** Capture-trace propagation (non-framework spans). The processor today tags **every** span (`on_start` runs for all). Per D-07a, it must be RETAINED — but with narrowed scope: only Azure SDK auto-instrumented `AppDependencies`, third-party library `AppExceptions`, and custom non-framework spans. Source-level tagging on framework agent + tool spans must move into `agents/middleware/capture_trace.py` (the new `AgentMiddleware`/`FunctionMiddleware` per D-07a).
- **Reason:** Pre-migration this is correct behavior (no framework middleware exists yet). Post-migration it becomes a **justified retention** under D-07a — the framework's middleware tags spans the framework emits; the processor catches everything else (Azure SDK, Cosmos `AppDependencies`, raw `AppExceptions`) so `query_capture_trace`'s `AppDependencies` correlation in `observability/kql_templates.py` keeps working. The auditor flags this as ⚠️ rather than ❌ because the design explicitly requires retention; the warning is to track that the narrowing edit (skip framework-emitted spans, since middleware already tagged them) lands in the same task group as the new middleware.
- **Justification (anticipated, lifted from design D-07a):** "Why this is framework-first: the framework gives us source-level tagging for spans it emits; the span processor keeps catching spans the framework doesn't emit (third-party SDKs, custom non-framework instrumentation). The fidelity auditor's checklist treats this hybrid as **justified** — the span processor is doing work the framework isn't designed to do, not duplicating it."

## Pass — Framework Primitives Correctly Used

- **Token metering:** `backend/src/second_brain/main.py:31` calls `enable_instrumentation()` correctly. No manual token counters were found anywhere in `streaming/`, `agents/`, or `processing/` (verified via `grep -rn "tokens_used\|prompt_tokens\|completion_tokens"`). Token-usage metrics emit via the framework's GenAI semantic conventions automatically.
- **App Insights export wiring:** `backend/src/second_brain/main.py:14, 21` uses `azure-monitor-opentelemetry`'s `configure_azure_monitor(...)` with no custom `SpanExporter` or duplicate pipeline. This is the GA-recommended exporter for App Insights and stays unchanged through the migration.
- **Tool parameter shape (`Annotated[..., Field(description=...)]` on RC tools):** Every `@tool(approval_mode=...)` function under `tools/` already uses `Annotated[<type>, Field(description=...)]` for parameters AND a docstring as tool description. After F-08 strips `approval_mode`, no further changes are needed for parameter shape. The class-bound-method pattern (`tools=[instance.method, ...]`) is also valid GA-style (per the design "Per-agent migration anatomy" #3).

## Probe Fixture Strict-Fidelity Check

| Fixture | Consumed by | Status | Notes |
|---|---|---|---|
| `streaming_shape.json` | `streaming/adapter.py` (text/voice/follow-up), `streaming/investigation_adapter.py` | Missing | Phase 23.0 has not run. Code currently uses RC `update.contents`, `content.type`, `getattr(content, "call_id", None)`, `getattr(update, "conversation_id", None)` — guesses against RC, not GA. Forced ⚠️ when the migration code lands without the probe fixture. |
| `tool_call_extraction.json` | `processing/admin_handoff.py`, `eval/foundry.py:880-942` | Missing | Phase 23.0 has not run. `eval/foundry.py:884-896` already does `hasattr(msg, "tool_calls")` duck typing — exactly the kind of code the probe is designed to replace with deterministic field paths. |
| `tool_choice_required.json` | `streaming/adapter.py:182-188, 590-596` (today RC dict shape); migration code at Phase 23.3 | Missing | Phase 23.0 has not run. Today's RC dict (`{"mode": "required", "required_function_name": "file_capture"}`) is not what `tool_choice='required'` looks like in GA. Phase 23.3 needs the probe to decide between `'required'` and provider-dict-by-name. |
| `session_rehydration.json` | `streaming/adapter.py:557-705` (follow-up) + `api/capture.py:95-198` (`_stream_with_thread_id_persistence`) + `streaming/investigation_adapter.py:117, 137-138` | Missing | Phase 23.0 has not run. Today the code stores `update.conversation_id` and replays it via `ChatOptions["conversation_id"]` — both RC. The GA equivalent (likely `service_session_id` + `agent.get_session(stored_id)` or `thread=AgentThread(...)`) is unknown until probe runs. |
| `auth_probe.json` | `main.py:430, 484-510` (Foundry client + connectivity validation) | Missing | Phase 23.0 has not run. Today `AsyncDefaultAzureCredential` + `AzureAIAgentClient` + force-iteration of `agents_client.list_agents(limit=1)`. GA equivalent is `FoundryChatClient(credential=DefaultAzureCredential(), project_endpoint=...)` + a probe-call; auth_probe verifies the credential class shape and RBAC alignment. |

All five fixtures are Missing — the probe directory `backend/tests/fixtures/foundry-probe/` does not exist. This is **expected** per the calibration brief (Phase 23.0 has not run yet).

## Cross-Task-Group Regression Check

Not applicable. Calibration is a one-shot snapshot audit — no `cumulative_start_sha` was supplied and no task groups have run.

## Files Outside Framework-First Scope (not audited)

- `mobile/**` — out-of-scope per design (does not change)
- `web/**` — out-of-scope per design
- `mcp/**` — out-of-scope per design
- `infra/**` — out-of-scope per design
- `docs/**`, `.planning/**` — documentation, not framework-fidelity surface
- `backend/tests/**` — tests are themselves verifiers, not the audit subject (will be flagged in their own pass when migration commits land in Phase 23.x)
- `backend/src/second_brain/spine/**` — spine workload events are a separate observability system (per CLAUDE.md context: "Spine workload events — separate system, out of scope"). Not part of agent-framework migration. Their RC-era `agent_emitter.py` calls work the same against either framework version because they don't talk to the agent SDK.
- `backend/src/second_brain/api/**`, `backend/src/second_brain/cosmos/**`, `backend/src/second_brain/auth.py`, `backend/src/second_brain/models/**` — explicitly listed "Out of scope (does NOT change)" in design. (Note: `api/capture.py:96-198` contains `foundryThreadId` round-tripping that DOES need an update in 23.3 since the field name changes — flagged via F-13. The route handler shape stays.)

## Recommendations

Ordered by severity. Each item names the file edits or planning artifact required for Phase 23.0/23.x to discharge.

1. **(Prerequisite)** Execute Phase 23.0 to create the 5 probe fixtures under `backend/tests/fixtures/foundry-probe/`. F-18 cannot be cleared until those fixtures exist; F-04, F-05, F-06, F-07, F-10, F-12, F-13 cannot be planned faithfully without them.
2. **(F-01, F-02, F-03, F-04, F-05)** Replace every `from agent_framework.azure import AzureAIAgentClient` with `from agent_framework_foundry import FoundryChatClient` + `from agent_framework import Agent`. Each consumer site (`main.py` lifespan, `warmup.py`, `processing/admin_handoff.py`, `streaming/adapter.py`, `streaming/investigation_adapter.py`) takes the GA `Agent` and calls `agent.run(...)` or `agent.run_stream(...)` instead of `client.get_response(...)`. Apply candidate `pyproject.toml` + `uv.lock` from Phase 23.0. (Phase 23 task groups 23.1 → 23.2 → 23.3.)
3. **(F-06, F-07)** Introduce `EvalAgentInvoker` facade in `backend/src/second_brain/eval/`. RC implementation kept temporarily during Phase 23.2 so RC-side callers (admin path) keep working until Phase 23.3 cleanup. GA implementation calls `agent.run(messages)` and adapts `AgentRunResponse` per `tool_call_extraction.json`. (Phases 23.2 + 23.3.)
4. **(F-08)** Strip `approval_mode="never_require"` from all 16 `@tool` decorators across `tools/`. (Phase 23.1 sets the pattern on `investigation.py`; 23.2 inherits for `admin.py`; 23.3 for `classification.py` + `transcription.py`. `recipe.py` rides whichever phase touches admin.)
5. **(F-09)** Delete `_safety_net_file_as_misunderstood` (lines 92-152, 324-334, 526-538, 676-686 of `streaming/adapter.py`). Replace with `tool_choice='required'` (F-10) after voice path split (F-11). Add `forced_tool_failure` SSE sub-code path. (Phase 23.3.)
6. **(F-10)** Rewrite `tool_choice` shape using whatever `tool_choice_required.json` documents — preferred form `tool_choice='required'`, fallback provider-dict by name. Applies to classifier streaming + classifier follow-up. (Phase 23.3.)
7. **(F-11)** Voice path split: implement either (a) direct `AsyncAzureOpenAI.audio.transcriptions.create(...)` call from a new pipeline step before classifier agent, or (b) a single-tool transcription sub-agent. Classifier agent registers ONLY `file_capture`. (Phase 23.3.)
8. **(F-12, F-13)** Replace constructor-level `agent_id` pinning with one `Agent` singleton per agent type + per-call rehydration via the API revealed by `session_rehydration.json` (`agent.get_session(stored_id)` or `thread=AgentThread(...)`). Rename `foundryThreadId` Inbox doc field to whatever the probe documents. (Phase 23.3 for classifier + investigation; 23.2 if admin uses sessions, but admin runs are non-streaming single-turn so likely no continuity needed.)
9. **(F-14, F-15, F-16)** Delete custom `tracer.start_as_current_span` blocks wrapping framework agent calls in `streaming/adapter.py` (3 sites), `streaming/investigation_adapter.py` (1 site), `processing/admin_handoff.py` (2 sites). Move their attribute setters into the new `agents/middleware/capture_trace.py` `AgentMiddleware` so they ride the framework span. (Phase 23.1 establishes the middleware on Investigation; 23.2 + 23.3 inherit.)
10. **(F-17)** Rewrite existing `AuditAgentMiddleware` and `ToolTimingMiddleware` to act on the framework's current span (`trace.get_current_span().set_attribute(...)`) rather than starting a new span. Or replace them entirely with the new `CaptureTraceAgentMiddleware` — the framework already emits `invoke_agent` / `execute_tool` spans with timing. (Phase 23.1.)
11. **(F-19)** Create `backend/src/second_brain/agents/instructions/{classifier,admin,investigation}.md` from Phase 23.0's `CANDIDATE-instructions/` export (Investigation already canonicalized at `docs/foundry/investigation-agent-instructions.md`). Replace `ensure_*_agent` portal-managed-shell pattern with `Agent(..., instructions=load_instructions(<name>))`. Remove `azure_ai_*_agent_id` settings in 23.3 cleanup commit. (Phases 23.1, 23.2, 23.3 — instruction file per agent ships with the agent's task group.)
12. **(W-01)** Narrow `CaptureTraceSpanProcessor` to skip framework-emitted agent + tool spans (e.g. drop tag if `span.name` matches framework prefixes like `invoke_agent.*` / `execute_tool.*`, since the new middleware already tags them at source). Retain for everything else. Add explicit-justification template entry to the deployment-checklist artifact. (Phase 23.1, alongside the new middleware.)

---

**FIDELITY AUDIT: 3 ✓, 1 ⚠️, 19 ❌. Report at `.planning/phases/23/FRAMEWORK-FIDELITY-calibration.md`.**
