# Phase 24: Foundry GA Migration - Pattern Map

**Mapped:** 2026-05-09
**Files analyzed:** 27 (3 new, 24 modified)
**Analogs found:** 27 / 27 (everything has a strong in-repo analog)
**Grouping:** by task group 23.1 (Investigation) → 23.2 (Admin) → 23.3 (Classifier) where natural

This map binds every Phase 24 file to a concrete existing analog with line-numbered excerpts. The planner copies patterns from these excerpts and applies the calibration deltas (F-01..F-19) named in `FRAMEWORK-FIDELITY-calibration.md`.

---

## File Classification

### New files

| New File | Role | Data Flow | Closest Analog | Match Quality | Calibration Finding |
|----------|------|-----------|----------------|---------------|--------------------|
| `backend/src/second_brain/agents/instructions/investigation.md` | instructions (markdown text) | static-resource | `docs/foundry/investigation-agent-instructions.md` (already canonical text) | exact (already canonical) | F-19 |
| `backend/src/second_brain/agents/instructions/admin.md` | instructions (markdown text) | static-resource | `.planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/admin.md` | exact (drafted from portal export) | F-19 |
| `backend/src/second_brain/agents/instructions/classifier.md` | instructions (markdown text) | static-resource | `.planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/classifier.md` | exact (drafted from portal export) | F-19 |
| `backend/src/second_brain/agents/middleware/capture_trace.py` | middleware (AgentMiddleware + FunctionMiddleware) | event-driven (per-span tagging) | `backend/src/second_brain/agents/middleware.py` (RC `AuditAgentMiddleware` + `ToolTimingMiddleware`) AND `backend/src/second_brain/observability/span_processor.py` (`CaptureTraceSpanProcessor`) | role-match + data-flow-match (composite) | F-14, F-15, F-16, F-17 |
| `backend/src/second_brain/eval/invoker.py` | service / Protocol facade | request-response | `backend/src/second_brain/eval/runner.py` lines 133-149 + 278-294 (RC call sites the facade replaces) AND `backend/src/second_brain/eval/dry_run_tools.py` (peer eval module shape) | role-match (Protocol abstraction is novel; surrounding patterns are strong) | F-06, F-07 |
| `.git/hooks/pre-push` + `.planning/phases/24-foundry-ga-migration/PUSH-GUARD-ACTIVE` sentinel | config (shell script + flag file) | gate (deny push when sentinel present) | None in-repo; pattern is from CONTEXT D-12 + design doc Option A | no-analog | n/a (Task 0 only) |

### Modified files (Task group 23.1 - Investigation)

| Modified File | Role | Data Flow | Closest Analog | Calibration Finding |
|---------------|------|-----------|----------------|--------------------|
| `backend/pyproject.toml` | config | static-resource | `.planning/phases/23-foundry-ga-prep/CANDIDATE-pyproject.toml` (drop-in replacement) | F-01 |
| `backend/uv.lock` | config | static-resource | `.planning/phases/23-foundry-ga-prep/CANDIDATE-uv.lock` (drop-in replacement) | F-01 |
| `backend/Dockerfile` | config | static-resource | n/a (touch-up — verify `ENABLE_INSTRUMENTATION=true` already present from Phase 17.4) | n/a |
| `backend/src/second_brain/config.py` | config (Pydantic Settings) | static-resource | self (existing `Settings` class) | n/a (additions only in 23.1) |
| `backend/src/second_brain/main.py` (Foundry probe + Investigation lifespan slice) | controller (lifespan setup) | request-response (lifespan) | self lines 484-510 (Foundry probe), 685-723 (Investigation client) | F-01, F-12 |
| `backend/src/second_brain/agents/investigation.py` | service (agent registration) | request-response | self (current `ensure_investigation_agent`) — function body fully replaced | F-19 |
| `backend/src/second_brain/streaming/investigation_adapter.py` | controller (SSE adapter) | streaming (SSE async generator) | self (current `stream_investigation`) | F-04, F-05, F-13, F-15 |
| `backend/src/second_brain/observability/queries.py` (`fetch_agent_runs`) | service (KQL query exec) | request-response | self lines 600-645 | n/a (KQL update only) |
| `backend/src/second_brain/observability/kql_templates.py` (`AGENT_RUNS`) | config (KQL template) | static-resource | self lines 376-396 | n/a (template Name update) |
| `backend/src/second_brain/observability/span_processor.py` | middleware (span processor) | event-driven | self (no code change; documentation note only per W-01) | W-01 |

### Modified files (Task group 23.2 - Admin)

| Modified File | Role | Data Flow | Closest Analog | Calibration Finding |
|---------------|------|-----------|----------------|--------------------|
| `backend/src/second_brain/main.py` (Admin lifespan slice) | controller (lifespan setup) | request-response (lifespan) | self lines 593-629, 794-808 | F-01, F-12 |
| `backend/src/second_brain/agents/admin.py` | service (agent registration) | request-response | self (current `ensure_admin_agent`) | F-19 |
| `backend/src/second_brain/processing/admin_handoff.py` | service (background processor) | event-driven (post-classification handoff) | self (current `process_admin_capture` + `process_admin_captures_batch`) | F-03, F-08, F-13, F-16 |
| `backend/src/second_brain/tools/admin.py` | service (tools class with @tool methods) | request-response (per tool) | self (6 existing tool methods) | F-08 |
| `backend/src/second_brain/tools/recipe.py` | service (tools class with @tool methods) | request-response | self (existing `RecipeTools` class) | F-08 |
| `backend/src/second_brain/eval/runner.py` (admin call site, lines 278-294) | service (eval orchestration) | request-response per case | self plus `eval/invoker.py` (NEW) | F-06 |
| `backend/src/second_brain/eval/foundry.py` (lines 856-942) | service (eval-side dataset gen) | request-response | same call shape as `eval/runner.py:278-294` | F-07 |

### Modified files (Task group 23.3 - Classifier + cleanup)

| Modified File | Role | Data Flow | Closest Analog | Calibration Finding |
|---------------|------|-----------|----------------|--------------------|
| `backend/src/second_brain/main.py` (Classifier lifespan slice + agent_id removals) | controller (lifespan setup) | request-response (lifespan) | self lines 511-587, 779-793 | F-01, F-11, F-12 |
| `backend/src/second_brain/agents/classifier.py` | service (agent registration) | request-response | self (current `ensure_classifier_agent`) | F-19 |
| `backend/src/second_brain/streaming/adapter.py` | controller (SSE adapter) | streaming (SSE async generator) | self (3 functions: `stream_text_capture`, `stream_voice_capture`, `stream_follow_up_capture`) | F-04, F-09, F-10, F-11, F-13, F-14 |
| `backend/src/second_brain/api/capture.py` (lines 200-300) | controller (HTTP endpoint) | streaming entry | self (current capture/voice/follow-up route handlers) | F-11 (voice direct call insertion), F-13 (`session_id` field rename) |
| `backend/src/second_brain/tools/classification.py` | service (ClassifierTools class) | request-response | self (existing `file_capture` + helpers) | F-08 |
| `backend/src/second_brain/tools/transcription.py` | service (helper, no longer @tool) | request-response | self (existing `transcribe_audio`) | F-08, F-11 |
| `backend/src/second_brain/warmup.py` | service (background loop) | batch | self (current `agent_warmup_loop`) | F-02 |
| `backend/src/second_brain/eval/runner.py` (classifier call site, lines 133-149) | service (eval orchestration) | request-response per case | same as 23.2; final RC deletion | F-06 |
| `backend/src/second_brain/eval/dry_run_tools.py` | service (eval @tool stubs) | request-response | self (decorator strip same pattern as F-08) | F-08 |
| `backend/src/second_brain/agents/middleware.py` | middleware (DELETED) | n/a | replaced by `agents/middleware/capture_trace.py` | F-17 |
| `backend/src/second_brain/eval/invoker.py` (RC class deletion) | service | n/a | self (deletion only — facade collapses to GA-only) | n/a (deletion trigger per EVAL-INVENTORY) |
| `backend/src/second_brain/config.py` (agent_id removals) | config | static-resource | self | n/a (cleanup) |
| `backend/src/second_brain/models/documents.py` (`InboxDocument.foundryThreadId` → `sessionId`) | model (Pydantic) | static-resource | self lines 40-53 | F-13 (D-07b probe finding) |

### Tests

| Test File | Role | Data Flow | Closest Analog | Notes |
|-----------|------|-----------|----------------|-------|
| `backend/tests/test_*.py` (mocks rebased) | test | n/a | existing test suite (mocks `AzureAIAgentClient.get_response` today; new mocks shape against `agent.run()` / `agent.run(stream=True)`) | Mock shape from probe fixtures |
| `backend/tests/fixtures/foundry-probe/*.json` | test fixture (data) | static-resource | already on disk (Phase 23) | Reference, not modified |
| `backend/tests/fixtures/{investigation,admin,classifier}/*.{input.json,sse.jsonl,spans.json,expected-deltas.md}` | test fixture (golden trace) | static-resource | already on disk (Phase 23) | Replay tests reference these |
| `backend/tests/fixtures/eval-baseline-pre-migration.json` | test fixture (eval scores) | static-resource | already on disk (Phase 23) | ±2pp gate compares against this |

---

## Pattern Assignments

### Group A - Capture-trace middleware (drives 23.1 first, used by 23.2 + 23.3)

#### `backend/src/second_brain/agents/middleware/capture_trace.py` (NEW — middleware, event-driven)

**Composite analog #1:** `backend/src/second_brain/agents/middleware.py` (the very file that gets deleted)

**Imports pattern** (`agents/middleware.py:11-24`):
```python
import logging
import time
from collections.abc import Awaitable, Callable

from agent_framework import (
    AgentContext,
    AgentMiddleware,
    FunctionInvocationContext,
    FunctionMiddleware,
)
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("second_brain.agents")
```

The class hierarchy (`AgentMiddleware`, `FunctionMiddleware`) and the `process(self, context, call_next)` shape are GA-compatible — KEEP. The classifier-specific `file_capture` result extraction at lines 82-104 also stays (lifted into the new module to preserve `classification.bucket` / `classification.confidence` / `classification.status` / `classification.item_id` span attributes).

**Anti-pattern to NOT copy** (`agents/middleware.py:44, 72` — the F-17 violation):
```python
# DO NOT do this in the new middleware:
with tracer.start_as_current_span(self._span_name) as span:   # creates parallel span
    span.set_attribute("agent.name", self._agent_name)
    await call_next()
```

**Composite analog #2:** `backend/src/second_brain/observability/span_processor.py:16-30` — the source-of-truth for ContextVar-based capture-trace tagging

**Pattern to copy** (lines 26-30):
```python
def on_start(self, span: Span, parent_context: object = None) -> None:
    trace_id = capture_trace_id_var.get("")
    if trace_id:
        span.set_attribute("capture.trace_id", trace_id)
```

**ContextVar source** (`tools/classification.py:38-40`):
```python
capture_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "capture_trace_id_var", default=""
)
```

**Synthesised pattern for `agents/middleware/capture_trace.py`:**
```python
from agent_framework import (
    AgentContext, AgentMiddleware,
    FunctionInvocationContext, FunctionMiddleware,
)
from opentelemetry import trace
from second_brain.tools.classification import capture_trace_id_var

class CaptureTraceAgentMiddleware(AgentMiddleware):
    """Tag the framework-emitted invoke_agent span with capture.trace_id."""
    async def process(self, context: AgentContext, call_next):
        trace_id = capture_trace_id_var.get("")
        if trace_id:
            trace.get_current_span().set_attribute("capture.trace_id", trace_id)
        await call_next()

class CaptureTraceFunctionMiddleware(FunctionMiddleware):
    """Tag the framework-emitted execute_tool span with capture.trace_id +
    file_capture classification attributes."""
    async def process(self, context: FunctionInvocationContext, call_next):
        trace_id = capture_trace_id_var.get("")
        span = trace.get_current_span()
        if trace_id:
            span.set_attribute("capture.trace_id", trace_id)
        await call_next()
        # Lift classification.* attribute extraction here from
        # ToolTimingMiddleware lines 82-104 (file_capture + transcribe_audio).
```

**Probe fidelity check:** `streaming_shape.json` confirms framework auto-emits the `invoke_agent` / `execute_tool` spans during `agent.run(stream=True)`, so middleware tags ride those (no parallel span creation).

---

### Group B - 23.1 Investigation: agent + lifespan + adapter + KQL

#### `backend/src/second_brain/agents/investigation.py` (modified — service, request-response)

**Analog:** self (current `ensure_investigation_agent` function body — lines 21-69)

**Pattern to DELETE** (current implementation, F-19):
```python
async def ensure_investigation_agent(
    foundry_client: AzureAIAgentClient,
    stored_agent_id: str,
) -> str:
    if stored_agent_id:
        try:
            agent_info = await foundry_client.agents_client.get_agent(stored_agent_id)
            return stored_agent_id
        except Exception:
            ...
    new_agent = await foundry_client.agents_client.create_agent(
        model="gpt-4o", name="InvestigationAgent",
    )
    logger.info("NEW Investigation agent: id=%s -- SET INSTRUCTIONS IN AI FOUNDRY PORTAL ...")
    return new_agent.id
```

**New pattern (Agent constructed in repo):**
```python
from pathlib import Path
from agent_framework import Agent
from agent_framework_foundry import FoundryChatClient

INSTRUCTIONS_DIR = Path(__file__).parent / "instructions"

def load_instructions(name: str) -> str:
    return (INSTRUCTIONS_DIR / f"{name}.md").read_text()

def build_investigation_agent(
    chat_client: FoundryChatClient,
    tools: list,
    middleware: list,
) -> Agent:
    return Agent(
        client=chat_client,
        instructions=load_instructions("investigation"),
        tools=tools,
        middleware=middleware,
    )
```

The portal-shell creation path is fully removed; instructions are repo-owned (D-02). This file's signature changes — the planner must update `main.py` lifespan to call the new helper.

#### `backend/src/second_brain/main.py` Investigation lifespan (modified — controller, request-response)

**Analog (Foundry probe, lines 484-510):**
```python
try:
    foundry_client = AzureAIAgentClient(
        credential=credential,
        project_endpoint=settings.azure_ai_project_endpoint,
        model_deployment_name="gpt-4o",
    )
    async for _ in foundry_client.agents_client.list_agents(limit=1):
        break
    app.state.foundry_client = foundry_client
    logger.info("Foundry client initialized and connectivity validated: %s", ...)
except Exception:
    logger.error("FATAL: Could not initialize Foundry client", exc_info=True)
    raise  # Fail fast -- backend is useless without Foundry
```

**New shape (per CONFIG-DELTAS Step A + auth_probe finding):**
```python
from agent_framework_foundry import FoundryChatClient
from azure.identity.aio import ManagedIdentityCredential as AsyncManagedIdentityCredential

# Single FoundryChatClient is shared across all 3 Agent objects.
chat_client = FoundryChatClient(
    project_endpoint=settings.azure_ai_project_endpoint,
    model=settings.foundry_model,             # NEW config field, default "gpt-4o"
    credential=ManagedIdentityCredential(),    # auth_probe-confirmed
)
app.state.foundry_chat_client = chat_client
# Optional: a probe-call analog for the existing list_agents fail-fast.
# session_rehydration probe shows agent.run() works against a freshly built Agent;
# defer to warmup ping.
```

**Analog (Investigation client construction, lines 702-723):**
```python
investigation_client = AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    agent_id=investigation_agent_id,
    should_cleanup_agent=False,
    middleware=[
        AuditAgentMiddleware(agent_name="investigation"),
        ToolTimingMiddleware(),
    ],
)
app.state.investigation_client = investigation_client
app.state.investigation_tools = [
    investigation_tools.trace_lifecycle,
    investigation_tools.recent_errors,
    ...
]
```

**New shape (per D-05 + D-12):**
```python
from second_brain.agents.middleware.capture_trace import (
    CaptureTraceAgentMiddleware, CaptureTraceFunctionMiddleware,
)
from second_brain.agents.investigation import build_investigation_agent

investigation_agent = build_investigation_agent(
    chat_client=chat_client,
    tools=[
        investigation_tools.trace_lifecycle,
        investigation_tools.recent_errors,
        investigation_tools.system_health,
        investigation_tools.usage_patterns,
        investigation_tools.query_feedback_signals,
        investigation_tools.promote_to_golden_dataset,
        investigation_tools.run_classifier_eval,
        investigation_tools.run_admin_eval,
        investigation_tools.get_eval_results,
    ],
    middleware=[
        CaptureTraceAgentMiddleware(),
        CaptureTraceFunctionMiddleware(),
    ],
)
app.state.investigation_agent = investigation_agent
```

**Behavioral contract preserved:** non-fatal try/except around the whole block (Investigation is non-fatal per current lines 684-747); rate limiter persists at `app.state.investigation_rate_limiter`.

#### `backend/src/second_brain/streaming/investigation_adapter.py` (modified — controller, streaming)

**Analog:** self (current `stream_investigation` lines 69-222)

**RC patterns to REPLACE:**

Imports (lines 26-27):
```python
from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
```
→ become
```python
from agent_framework import Agent
```
(no Message/ChatOptions; messages are plain strings per probe; no client import — adapter takes Agent.)

Custom span (line 96, F-15 violation):
```python
with tracer.start_as_current_span("investigate") as span:
    span.set_attribute("investigate.question_length", len(question))
    span.set_attribute("investigate.thread_id", thread_id or "")
    ...
```
→ DELETE entirely. Capture-trace middleware tags the framework's `invoke_agent` span. The `investigate.*` attribute names migrate to either:
- the framework span via `trace.get_current_span().set_attribute(...)` inside the adapter pre-call (since the framework `invoke_agent` span IS current at that point), OR
- the AppRequests span (already tagged by `api/capture.py:228` pattern; mirror in `api/investigate.py`).

Message + options shape (lines 114-117):
```python
messages = [Message(role="user", text=question)]
options: ChatOptions = {"tools": tools}
if thread_id:
    options["conversation_id"] = thread_id
```
→ becomes (per probes 2 + 4):
```python
from agent_framework import AgentSession
session = AgentSession(session_id=thread_id) if thread_id else AgentSession()
# tools were pre-registered at lifespan; do not pass here per CONTEXT D-05.
```

Stream call (lines 128-132):
```python
stream = client.get_response(
    messages=messages, stream=True, options=options,
)
```
→ becomes
```python
stream = agent.run(question, session=session, stream=True)
```

Stream loop body (lines 134-183, content type matching):
```python
for content in update.contents or []:
    if content.type == "text" and getattr(content, "text", None):
        yield encode_sse({"type": "text", "content": content.text})
    elif content.type == "function_call":
        ...
    elif content.type == "function_result":
        ...
```
**KEEP THE FRAME** — but per Probe 1 (streaming_shape), `update.text` accumulates final user-visible text and during tool execution `text=''`. Switch the primary text emission to `update.text` (when non-empty) and KEEP `content.type` matching as a fallback for tool_call / tool_error sub-events. The `_TOOL_DESCRIPTIONS` dict (lines 36-41) and the rate limiter (lines 44-66, 102-110) are unchanged.

Session ID extraction (lines 136-137):
```python
if getattr(update, "conversation_id", None) and not conversation_id:
    conversation_id = update.conversation_id
```
→ replaced by reading `session.session_id` directly after the stream completes (Probe 4). Persist on response payload as `thread_id` for backward compat with mobile (no SSE shape change).

Error handling (lines 190-222) — KEEP unchanged. Timeout/error → `error` SSE event → `done` SSE event pattern is wire-compatible.

#### `backend/src/second_brain/observability/queries.py` `fetch_agent_runs` (modified)

**Analog:** self (lines 600-645)

**Single change** (in the same commit cluster as 23.1's Investigation rewrite, per SPAN-NAME-MAPPING):
```python
# kql_templates.py line 378: change
| where Name endswith "_agent_run"
# to
| where Name == "invoke_agent"
```

**Property projection check** — verify post-deploy that GA-emitted `invoke_agent` span uses these attribute names (current projection at lines 388-393):
```python
agent_id = tostring(Properties.agent_id),
agent_name = tostring(Properties.agent_name),
run_id = tostring(Properties.run_id),
thread_id = tostring(Properties.foundry_thread_id),
capture_trace_id = tostring(Properties.capture_trace_id),
```

Per SPAN-NAME-MAPPING + GA semantic conventions, the GA framework emits `agent.name` (already aliased here), `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`. The property names `agent_id` / `run_id` / `foundry_thread_id` are RC-era custom attributes set by `AuditAgentMiddleware` (deleted) — these projections will return empty strings for new spans. The 23.1 plan must verify post-deploy and add a follow-up to either rename projections to GA names or set application-level attributes via the new middleware.

#### `backend/src/second_brain/observability/span_processor.py` (no code change — W-01)

**Analog:** self

Per design D-07a, the processor is RETAINED unchanged. Phase 24 narrowing is documentation-only (a comment update in 23.1 noting that framework `invoke_agent` / `execute_tool` spans are now tagged at source by middleware, while this processor catches Azure SDK `AppDependencies` / Cosmos / `AppExceptions`). No `if span.name.startswith("invoke_agent"): return` guard is added because the framework middleware tags the same attribute name (`capture.trace_id`); a redundant tag from `on_start` is a no-op when the value matches.

---

### Group C - 23.2 Admin: agent + lifespan + handoff + tools + eval facade

#### `backend/src/second_brain/agents/admin.py` (modified)

**Analog:** self + already-shown `agents/investigation.py` migration pattern (Group B).

Same shape: replace `ensure_admin_agent` body with `build_admin_agent(chat_client, tools, middleware)`. `instructions=load_instructions("admin")` reads from `agents/instructions/admin.md` (drafted from `.planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/admin.md`). Non-fatal failure semantics preserved at the `main.py` call-site try/except.

#### `backend/src/second_brain/main.py` Admin lifespan slice (modified)

**Analog:** self lines 593-629 + 794-808 (warmup factory)

Same migration pattern as Investigation (Group B). Tools list (lines 616-623) becomes the `tools=[...]` arg to `Agent(...)`, plus `middleware=[CaptureTraceAgentMiddleware(), CaptureTraceFunctionMiddleware()]`. Recipe tool registration at line 651 (`app.state.admin_agent_tools.append(recipe_tools.fetch_recipe_url)`) STAYS but is appended to the list passed into `build_admin_agent(...)`.

**Note on routing context (CONTEXT D-flexibility item 3):** Keep `get_routing_context` as a registered tool (current pattern). Do not move to `FunctionMiddleware` injection unless the planner finds a clean reason during 23.2 design.

#### `backend/src/second_brain/processing/admin_handoff.py` (modified — service, event-driven)

**Analog:** self (`process_admin_capture` lines 140-414, `process_admin_captures_batch` lines 417-454)

**RC patterns to REPLACE:**

Imports (lines 14-15, F-03):
```python
from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
```
→ becomes
```python
from agent_framework import Agent
```

Custom span (line 177, F-16 violation):
```python
with tracer.start_as_current_span("admin_agent_process") as span:
    span.set_attribute("admin.inbox_item_id", inbox_item_id)
    span.set_attribute("admin.raw_text_length", len(raw_text))
    if capture_trace_id:
        span.set_attribute("capture.trace_id", capture_trace_id)
    ...
```
→ DELETE the `with tracer.start_as_current_span(...)`. The `admin.*` attributes either move onto the framework's `invoke_agent` span via `trace.get_current_span().set_attribute(...)` immediately before `agent.run(...)`, or are dropped to logger.info `extra=` dict (which already exists at lines 191, 203). Same for the batch span at line 441.

Agent call (lines 234-244, F-03):
```python
messages = [Message(role="user", text=enriched_text)]
options = ChatOptions(tools=admin_tools)

# Snapshot tool invocation counts before calling the agent
pre_count = _count_tool_invocations(admin_tools)
pre_output_count = _count_output_tool_invocations(admin_tools)

async with asyncio.timeout(60):
    response = await admin_client.get_response(
        messages=messages, options=options
    )
```
→ becomes (per probe `tool_call_extraction.json` + CONTEXT D-08):
```python
from agent_framework import ChatOptions

async with asyncio.timeout(60):
    response = await admin_agent.run(
        enriched_text,
        options=ChatOptions(tool_choice="required"),  # D-08 forces tool call
    )

# response.text → final assistant answer
# response.messages → walk for tool detection per probe finding
# response.usage_details → token counts (kept off span; framework emits via gen_ai.*)
```

**Tool detection — replace invocation_count snapshots with response inspection (per probe 2):**

The current code uses `_count_tool_invocations(admin_tools)` and `_count_output_tool_invocations(admin_tools)` — these read mutable counters on FunctionTool instances. Per `tool_call_extraction.json`, tool calls are visible in `response.messages`:
- `messages[0]`: role=`'assistant'`, contents=[Content tool-call request]
- `messages[1]`: role=`'tool'`, contents=[Content tool result]
- `messages[-1]`: role=`'assistant'`, contents=[Content final text], `text='...'`

**New shape:**
```python
# Replace pre/post invocation_count snapshots with post-hoc response.messages inspection
def _output_tool_called(response) -> tuple[bool, set[str]]:
    """Inspect response.messages for tool calls; return (output_called, tools_called)."""
    tools_called: set[str] = set()
    for msg in response.messages:
        if msg.role == "tool":
            for content in (msg.contents or []):
                name = getattr(content, "name", None) or getattr(content, "function_name", None)
                if name:
                    tools_called.add(name)
    return bool(tools_called & _OUTPUT_TOOL_NAMES), tools_called
```

The `_OUTPUT_TOOL_NAMES` constant (lines 46-52) is **unchanged** — it's the post-migration source of truth for output detection.

**Bounded retry (D-09):** KEEP the existing retry logic at lines 270-318 (the directive prompt nudge), but replace the second `admin_client.get_response(...)` call with `admin_agent.run(retry_prompt, options=ChatOptions(tool_choice="required"))`. One retry, no loop — exactly as today.

`_response_needs_delivery(response.text)` (lines 71-113) — UNCHANGED. Pure string-matching helper.

`_mark_inbox_failed` (lines 116-137) — UNCHANGED. Cosmos write path.

Spine emission at lines 401-414 — UNCHANGED. Outcome reasoning is post-response.

#### `backend/src/second_brain/tools/admin.py` (modified — F-08 mechanical)

**Analog:** self (current 6 tool methods at lines 121, 191, 235, 249, 370, 537)

**Mechanical change per tool method** (CONTEXT D-05/D-06):
```python
# DELETE this decorator line at lines 121, 191, 235, 249, 370, 537:
@tool(approval_mode="never_require")
```
KEEP `Annotated[..., Field(description=...)]` parameter shape (lines 122-138 etc.). KEEP the docstring as the tool description. KEEP `__init__(cosmos_manager)` signature for DI.

**Validation:** After dropping the decorator, the method becomes a plain async coroutine. `Agent(tools=[admin_tools.add_errand_items, ...])` accepts it directly per the GA pattern. No tests change (mocks shape against `cosmos_manager.get_container(...)`, not the tool decorator).

`tools/recipe.py` and the eval-side `eval/dry_run_tools.py` follow the same mechanical pattern.

#### `backend/src/second_brain/eval/invoker.py` (NEW — service, request-response)

**Analog #1:** `backend/src/second_brain/eval/runner.py` lines 133-149 (classifier RC call) and 278-294 (admin RC call) — verbatim shape the facade replaces

**Pattern to wrap (RC path, kept temporarily during migration window per EVAL-INVENTORY):**
```python
# RC implementation (eval/runner.py:133-149, transplanted into facade)
messages = [Message(role="user", text=input_text)]
options = ChatOptions(
    tools=[tools_instance.file_capture],
    tool_choice={"mode": "required", "required_function_name": "file_capture"},
)
await _call_with_retry(
    lambda: classifier_client.get_response(messages=messages, options=options),
    run_id=run_id, case_index=i, runs_dict=runs_dict,
)
```

**Pattern for GA path (per probe 2):**
```python
# GA implementation
from agent_framework import ChatOptions
response = await classifier_agent.run(
    input_text,
    options=ChatOptions(tool_choice="required"),
)
# Side effects already on tools_instance.last_bucket / last_confidence
# (the eval tool stub is invoked by the framework during run()).
```

**Analog #2:** `backend/src/second_brain/eval/dry_run_tools.py` (peer eval module — same package layout, naming convention, fileheader docstring style)

**Synthesised structure for `eval/invoker.py`:**
```python
"""EvalAgentInvoker — temporary facade hiding RC/GA call shape during migration.

Introduced in Phase 24 task group 23.2 when Admin migrates to GA. The RC
implementation is deleted at end of 23.3 when no caller remains.
Deletion trigger documented in EVAL-INVENTORY.md.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Protocol

from agent_framework import ChatOptions

if TYPE_CHECKING:
    from agent_framework import Agent
    from agent_framework.azure import AzureAIAgentClient
    from second_brain.eval.dry_run_tools import EvalClassifierTools, DryRunAdminTools


class EvalAgentInvoker(Protocol):
    async def invoke_classifier(self, input_text: str, tools_instance: "EvalClassifierTools") -> None: ...
    async def invoke_admin(self, input_text: str, tools_instance: "DryRunAdminTools", routing_context: str) -> None: ...


class GAEvalAgentInvoker:
    """GA implementation — calls Agent.run(...). Per probe tool_call_extraction.json."""
    def __init__(self, classifier_agent: "Agent", admin_agent: "Agent"): ...

    async def invoke_classifier(self, input_text, tools_instance):
        # Tools registered on the per-case Agent — pass via run(tools=[...])
        # OR construct a fresh case-scoped Agent. The probe shows tools=[...] kwarg works on agent.run().
        await self._classifier.run(
            input_text,
            tools=[tools_instance.file_capture],
            options=ChatOptions(tool_choice="required"),
        )
        # Side effects already on tools_instance.last_bucket etc.

    async def invoke_admin(self, input_text, tools_instance, routing_context):
        await self._admin.run(
            f"{routing_context}\n\n---\n{input_text}",
            tools=[
                tools_instance.add_errand_items,
                tools_instance.add_task_items,
                tools_instance.get_routing_context,
            ],
            # tool_choice not set per current admin eval contract (defaults to auto)
        )


class RCEvalAgentInvoker:
    """RC implementation — temporary, deleted at end of 23.3.
    Body lifted verbatim from eval/runner.py:133-149 + 278-294.
    """
    def __init__(self, classifier_client: "AzureAIAgentClient", admin_client: "AzureAIAgentClient"): ...
    # invoke_classifier and invoke_admin contain the existing client.get_response(...) calls.
```

**Wire-up (eval/runner.py lines 133-149 + 278-294 replacement, per EVAL-INVENTORY):**
```python
# Single change at runner call site:
await _call_with_retry(
    lambda: invoker.invoke_classifier(case["inputText"], eval_tools),
    run_id=run_id, case_index=i, runs_dict=runs_dict,
)
```

**Deletion trigger:** end of 23.3 final cleanup commit, when no `RCEvalAgentInvoker` caller remains. Optional rename `GAEvalAgentInvoker` → `EvalAgentInvoker` (drop Protocol, single concrete class).

---

### Group D - 23.3 Classifier: agent + lifespan + adapter + voice split + cleanup

#### `backend/src/second_brain/agents/classifier.py` (modified)

**Analog:** self + Group B `agents/investigation.py` migration pattern.

Same shape: `build_classifier_agent(chat_client, tools, middleware)`. Crucially per CONTEXT D-01..D-04 + F-11, the `tools` list is `[classifier_tools.file_capture]` ONLY — `transcribe_audio` is NOT registered. `instructions=load_instructions("classifier")` reads from `agents/instructions/classifier.md`.

#### `backend/src/second_brain/main.py` Classifier lifespan slice (modified)

**Analog:** self lines 511-587 (Classifier construction) + 779-793 (warmup factory)

**Change at lines 578-581 (the F-11 violation):**
```python
# DELETE this:
agent_tools = [classifier_tools.file_capture]
if app.state.transcription_tools:
    agent_tools.append(app.state.transcription_tools.transcribe_audio)
app.state.classifier_agent_tools = agent_tools
```

**New shape:**
```python
# Voice path is now a direct call from api/capture.py — see D-01.
classifier_agent = build_classifier_agent(
    chat_client=chat_client,
    tools=[classifier_tools.file_capture],   # ONLY file_capture (D-04)
    middleware=[CaptureTraceAgentMiddleware(), CaptureTraceFunctionMiddleware()],
)
app.state.classifier_agent = classifier_agent
# transcription_tools instance still constructed (lines 542-559) — its
# transcribe_audio method is no longer a @tool but a direct helper now
# called by the streaming adapter / capture endpoint.
```

The `app.state.transcription_tools` instance lives — `api/capture.py` (or `streaming/adapter.py`) calls `app.state.transcription_tools.transcribe_audio(blob_url)` directly when audio is on the request. Since `tools/transcription.py` already exists with the gpt-4o-transcribe call, no new transcription code is needed (CONTEXT explicit reusable asset).

#### `backend/src/second_brain/streaming/adapter.py` (modified — controller, streaming)

**Analog:** self (3 functions: `stream_text_capture` lines 154-350, `stream_voice_capture` lines 353-554, `stream_follow_up_capture` lines 557-705+)

**Imports change (lines 17-18, F-04):**
```python
from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
```
→ becomes
```python
from agent_framework import Agent, AgentSession, ChatOptions
```

**Custom-span deletion (3 sites — F-14):**

Lines 175-179 (`stream_text_capture`):
```python
with tracer.start_as_current_span("capture_text") as span:
    span.set_attribute("capture.type", "text")
    span.set_attribute("capture.thread_id", thread_id)
    span.set_attribute("capture.run_id", run_id)
    span.set_attribute("capture.trace_id", capture_trace_id)
```
→ DELETE the `with` block. The `capture.*` attributes go onto the AppRequests span (already done at `api/capture.py:228` for `capture.trace_id`); migrate the others (`capture.type`, `capture.thread_id`, `capture.run_id`) into a single helper called from `api/capture.py` like:
```python
_current = trace.get_current_span()
if _current.is_recording():
    _current.set_attribute("capture.type", "text")
    _current.set_attribute("capture.thread_id", thread_id)
    _current.set_attribute("capture.run_id", run_id)
    _current.set_attribute("capture.trace_id", capture_trace_id)
```

Lines 372-376 (`stream_voice_capture`) and 582-587 (`stream_follow_up_capture`) — same pattern. The `_current.set_attribute(...)` migration must happen in the API endpoint, BEFORE the `StreamingResponse` is returned (because the AppRequests span is the request span, not the generator span).

**`tool_choice` shape (lines 182-188, F-10):**
```python
options: ChatOptions = {
    "tools": tools,
    "tool_choice": {
        "mode": "required",
        "required_function_name": "file_capture",
    },
}
```
→ becomes (per probe 3):
```python
options = ChatOptions(tool_choice="required")  # string form, classifier registers ONLY file_capture
```

**Stream call (lines 200-203):**
```python
async with asyncio.timeout(60):
    stream = client.get_response(
        messages=messages, stream=True, options=options
    )
```
→ becomes
```python
async with asyncio.timeout(60):
    stream = agent.run(user_text, options=options, stream=True)
```

**Update loop body (lines 205-310 — KEEP frame, adjust field reads):**

Per probe 1 (streaming_shape):
- `update.text` accumulates final user-visible text (empty during tool execution)
- `update.contents` carries Content objects during tool-call phase
- `update.role` is always 'assistant'
- `update.finish_reason` is always None — adapter cannot rely on it
- The async iterator simply completes

The existing pattern reads `update.contents` and switches on `content.type` (text / function_call / function_result) — KEEP this. The `_parse_args(content.arguments)` and `_parse_result(content.result)` helpers (lines 40-58) — UNCHANGED.

`getattr(update, "conversation_id", None)` (line 207) — REMOVE. Session continuity comes from passing `session=AgentSession(session_id=stored_id)` into `agent.run()`. After the stream completes, read `session.session_id` for persistence (rename: per F-13 + D-07b probe finding, the persisted field is `sessionId`).

**Safety net deletion (lines 92-152, plus call sites at 324-334 + 526-538 + 676-686, F-09):**

Delete `_safety_net_file_as_misunderstood(...)` entirely. Replace each call site with the `forced_tool_failure` SSE sub-code emission (CONTEXT discretion item — adapter level is the cleanest exception context). New error event helper:
```python
# Add to streaming/sse.py (or local helper)
def forced_tool_failure_event(reason: str, thread_id: str = "") -> dict:
    return {
        "type": "error",
        "sub_code": "forced_tool_failure",
        "message": "The classifier failed to file this capture.",
        "reason": reason,
        "thread_id": thread_id,
    }
```
Mobile already handles the `error` event (per CONTEXT D-04); the `sub_code` is for monitoring/dashboards.

**Follow-up adapter (`stream_follow_up_capture` lines 557-700+):**

Same migration as text/voice. The `conversation_id` persistence at line 596 (`options["conversation_id"] = foundry_thread_id`) → becomes `session = AgentSession(session_id=stored_session_id)`. The Inbox doc field rename `foundryThreadId` → `sessionId` (F-13, D-07b probe finding) lands in this same commit cluster, with a one-shot Cosmos backfill for any in-flight follow-up rows.

#### `backend/src/second_brain/api/capture.py` lines 200-300 (modified — controller)

**Analog:** self (lines 201-268 — current `/api/capture` handler)

The bulk of the handler (capture_trace_id resolution, AppRequests span tagging, ContextVar set, generator construction) is UNCHANGED. The voice-path entry (line 271+, `/api/capture/voice`) gains a **direct transcription call BEFORE the generator is constructed**:

**Pattern (per CONTEXT D-01 + F-11):**
```python
# In the voice handler, BEFORE building stream_voice_capture generator:
transcription_tools = getattr(request.app.state, "transcription_tools", None)
if transcription_tools and audio_blob_url:
    try:
        transcript = await transcription_tools.transcribe_audio(audio_blob_url)
    except Exception as exc:
        logger.warning("Voice transcription failed: %s", exc, extra=log_extra)
        # Emit error SSE and return — voice without transcript is unrecoverable
        return StreamingResponse(_voice_transcription_failed_stream(...))
    # Then call the (now text-only) classifier on the transcript
    generator = stream_text_capture(
        agent=request.app.state.classifier_agent,
        user_text=transcript,
        thread_id=thread_id,
        run_id=run_id,
        cosmos_manager=cosmos_manager,
        capture_trace_id=capture_trace_id,
    )
```

`stream_voice_capture` as a separate function effectively collapses into `stream_text_capture` post-D-01. The voice path becomes: transcribe → text-classify, with one classifier agent and one tool (`file_capture`).

**Field rename for follow-up (F-13):** lines around 95-198 currently round-trip `foundryThreadId` from inbox doc. Rename load + store to `sessionId`. The one-shot backfill script lives in `backend/scripts/` (new file, idempotent) for any in-flight rows with the old field.

#### `backend/src/second_brain/tools/classification.py` (modified — F-08)

**Analog:** self (lines 75-139, `file_capture`)

**Mechanical change** (line 75):
```python
@tool(approval_mode="never_require")
async def file_capture(self, ...) -> dict:
```
→ becomes
```python
async def file_capture(self, ...) -> dict:
```
KEEP everything else: `Annotated[..., Field(description=...)]`, docstring, `_write_to_cosmos` helper, `capture_trace_id_var` ContextVar pattern (lines 38-40), `follow_up_context` contextmanager (lines 43-50).

#### `backend/src/second_brain/tools/transcription.py` (modified — F-08 + F-11)

**Analog:** self (lines 58-87, `transcribe_audio`)

**Mechanical change** (line 58):
```python
@tool(approval_mode="never_require")
async def transcribe_audio(self, blob_url: ...) -> str:
```
→ becomes
```python
async def transcribe_audio(self, blob_url: str) -> str:
    """..."""
```

**Critical:** Drop both the `@tool` decorator AND the `Annotated[..., Field(...)]` parameter shape — `transcribe_audio` is no longer a tool, it's a direct helper called from `api/capture.py`. The blob download + OpenAI transcription body (lines 77-87) is UNCHANGED. The `__init__(openai_client, credential, deployment_name)` signature stays.

#### `backend/src/second_brain/warmup.py` (modified — F-02)

**Analog:** self (current `agent_warmup_loop` lines 15-77)

**Imports change:**
```python
from agent_framework import Message
from agent_framework.azure import AzureAIAgentClient
```
→ becomes
```python
from agent_framework import Agent
```

**Ping body change (line 41):**
```python
messages = [Message(role="user", text="ping")]
...
await client.get_response(messages=messages)
```
→ becomes
```python
# per probe shape: agent.run(string_input)
await agent.run("ping")
```

The signature changes from `clients: list[tuple[str, AzureAIAgentClient]]` to `agents: list[tuple[str, Agent]]`, with corresponding factory dict update. Self-healing recreate logic (lines 53-76) is unchanged in shape but recreates `Agent` objects (factories from `main.py` now build `Agent` instances).

#### `backend/src/second_brain/agents/middleware.py` (DELETED — F-17)

**Analog:** self (the file being deleted)

The body of `AuditAgentMiddleware` (lines 27-53) and `ToolTimingMiddleware` (lines 56-104) is replaced by `agents/middleware/capture_trace.py` (Group A). All current attribute setters (`agent.name`, `agent.duration_ms`, `tool.name`, `tool.duration_ms`, `classification.bucket/confidence/status/item_id`, `transcription.success`) — the `classification.*` and `transcription.success` MUST be lifted into the new `CaptureTraceFunctionMiddleware` (lines 82-104 of the deleted file). `agent.duration_ms` and `tool.duration_ms` are **redundant** with the framework's automatic duration emission and may be dropped.

#### `backend/src/second_brain/eval/runner.py` (modified — final RC removal at 23.3)

**Analog:** self lines 21 (RC import), 133-149 (classifier call), 278-294 (admin call)

After 23.2 has introduced the facade and classifier migrated in 23.3, both call sites collapse to:
```python
await _call_with_retry(
    lambda: invoker.invoke_classifier(case["inputText"], eval_tools),
    run_id=run_id, case_index=i, runs_dict=runs_dict,
)
```
The `from agent_framework import ChatOptions, Message` import (line 21) is removed when the last RC caller leaves the module.

#### `backend/src/second_brain/eval/foundry.py` lines 856-942 (modified — F-07)

**Analog:** self (`generate_app_mediated_dataset` body)

Same `client.get_response(...)` → `invoker.invoke_classifier(...)` shape replacement as 23.2 (Admin) + 23.3 (Classifier) above. The duck-typed `hasattr(msg, "tool_calls")` extraction at lines 884-896 is replaced by inspecting `response.messages` per probe 2.

#### `backend/src/second_brain/config.py` (modified)

**Analog:** self (lines 12-15)

**23.1 addition:**
```python
foundry_model: str = "gpt-4o"   # NEW
```
inserted after `azure_ai_project_endpoint`.

**23.3 cleanup:** delete the three `azure_ai_*_agent_id` fields at lines 13-15. KEEP `azure_ai_project_endpoint` (reused by `FoundryChatClient`). The deploy-step orphan removal in Container App is decoupled per CONFIG-DELTAS Step C.

#### `backend/src/second_brain/models/documents.py` (modified — F-13)

**Analog:** self lines 40-53 (`InboxDocument`)

**Single field rename** at line 52:
```python
foundryThreadId: str | None = None
```
→ becomes
```python
sessionId: str | None = None    # per AgentSession.session_id, probe 4
```

The Pydantic camelCase exemption (`pyproject.toml` line 63) covers this. One-shot backfill script in `backend/scripts/` migrates in-flight rows: `UPDATE c SET c.sessionId = c.foundryThreadId, REMOVE c.foundryThreadId WHERE c.foundryThreadId IS NOT NULL`. Idempotent — safe to re-run.

---

## Shared Patterns

### S-1 Tool DI via class `__init__` (CONTEXT D-05 / D-06 — applied to all 16 tools)

**Source:** `backend/src/second_brain/tools/admin.py:80-94`, `tools/classification.py:53-73`, `tools/investigation.py:86-106`, `tools/transcription.py:35-44`

**Pattern (unchanged across migration):**
```python
class FooTools:
    """Doc.

    Usage:
        tools = FooTools(cosmos_manager, ...)
        agent_tools = [tools.bar, tools.baz]
    """
    def __init__(self, cosmos_manager: CosmosManager, ...) -> None:
        self._manager = cosmos_manager
        ...

    async def bar(self, x: Annotated[str, Field(description="...")]) -> dict:
        """Description shown to the agent as the tool description."""
        ...
```

**Apply to:** all 6 admin tools, 9 investigation tools, `file_capture`, transcribe_audio loses the decorator + becomes plain method (D-01), `fetch_recipe_url`, plus the eval-side `EvalClassifierTools.file_capture` and `DryRunAdminTools.*`.

**Single change per tool:** drop `@tool(approval_mode="never_require")` line. Nothing else.

---

### S-2 Per-capture trace ID propagation via ContextVar

**Source:**
- `backend/src/second_brain/tools/classification.py:38-40` (definition)
- `backend/src/second_brain/api/capture.py:222-228` (set + AppRequests span tag)
- `backend/src/second_brain/streaming/adapter.py:174` (refresh inside generator)
- `backend/src/second_brain/observability/span_processor.py:26-30` (universal tag)

**Pattern preserved end-to-end:**
```python
# api/capture.py
capture_trace_id_var.set(capture_trace_id)
_current = trace.get_current_span()
if _current.is_recording():
    _current.set_attribute("capture.trace_id", capture_trace_id)

# streaming/adapter.py (inside async generator)
trace_token = capture_trace_id_var.set(capture_trace_id)
try:
    ...
finally:
    capture_trace_id_var.reset(trace_token)

# agents/middleware/capture_trace.py (NEW — replaces middleware.py + supplements span_processor.py)
async def process(self, context, call_next):
    trace_id = capture_trace_id_var.get("")
    if trace_id:
        trace.get_current_span().set_attribute("capture.trace_id", trace_id)
    await call_next()

# observability/span_processor.py (unchanged — covers Azure SDK / Cosmos / non-framework)
def on_start(self, span, parent_context=None):
    trace_id = capture_trace_id_var.get("")
    if trace_id:
        span.set_attribute("capture.trace_id", trace_id)
```

**Apply to:** all three agents post-migration. The `capture.trace_id` attribute name is the load-bearing constant; KQL `query_capture_trace` (`observability/queries.py:105-133`) filters on `Properties.capture_trace_id` and that filter survives unchanged because the attribute name is preserved.

---

### S-3 Lifespan-singleton agent + per-call session rehydration

**Source:** `backend/src/second_brain/main.py` lifespan (10 RC client construction sites today)

**Pre-migration anti-pattern (F-12):**
```python
# Constructor-level agent_id pinning — every caller shares the singleton agent
classifier_client = AzureAIAgentClient(
    agent_id=classifier_agent_id,
    should_cleanup_agent=False,
    ...
)
```

**Post-migration pattern (per probe 4):**
```python
# Lifespan: one Agent singleton per agent type (3 total)
classifier_agent = Agent(client=chat_client, instructions=..., tools=[...], middleware=[...])
admin_agent = Agent(client=chat_client, instructions=..., tools=[...], middleware=[...])
investigation_agent = Agent(client=chat_client, instructions=..., tools=[...], middleware=[...])

# Per-call site (in adapter or handoff):
session = AgentSession(session_id=stored_session_id) if stored_session_id else AgentSession()
async for update in agent.run(user_input, session=session, stream=True):
    ...
# After: persist session.session_id on Inbox doc (sessionId field)
```

**Apply to:** all 3 agents — Investigation (multi-turn investigate chat), Classifier (follow-up after misunderstood), Admin (single-turn, session optional but cheap to pass).

---

### S-4 Capture-flow span attribute set (capture.* on AppRequests, not custom span)

**Source:** `backend/src/second_brain/api/capture.py:222-228`

**Established pattern:**
```python
# Tag the existing AppRequests span (created by ASGI auto-instrumentation)
_current = trace.get_current_span()
if _current.is_recording():
    _current.set_attribute("capture.trace_id", capture_trace_id)
```

**Migration extension (F-14/F-15/F-16 deletion):** all `capture.type` / `capture.thread_id` / `capture.run_id` / `capture.outcome` / `investigate.*` / `admin.*` attributes set inside deleted custom spans move onto the `AppRequests` span via this same pattern from the API endpoint. The framework's `invoke_agent` span is a child of `AppRequests`; KQL queries that filter on `Name has "/api/capture"` (`observability/kql_templates.py` `SYSTEM_HEALTH`, `USAGE_PATTERNS_BY_PERIOD`) continue to find them.

**Apply to:** `api/capture.py` (text + voice + follow-up handlers), `api/investigate.py` (mirror this pattern — current investigation_adapter.py creates its own custom span which is exactly the F-15 violation).

---

### S-5 Spine workload emission at boundary

**Source:** `backend/src/second_brain/processing/admin_handoff.py:184-186, 401-414`

**Established pattern (UNCHANGED across migration):**
```python
_spine_start = time.perf_counter()
_spine_outcome = "success"
_spine_error_class: str | None = None

try:
    ... # the core work
except Exception as exc:
    _spine_outcome = "failure"
    _spine_error_class = type(exc).__name__
    raise
finally:
    if spine_repo:
        _duration = int((time.perf_counter() - _spine_start) * 1000)
        await emit_agent_workload(
            repo=spine_repo,
            segment_id="admin",
            operation="process_capture",
            outcome=_spine_outcome,
            duration_ms=_duration,
            capture_trace_id=capture_trace_id or None,
            ...
        )
```

**Apply to:** `processing/admin_handoff.py` (already uses pattern — preserve), `streaming/adapter.py` capture path (already wrapped via `spine_stream_wrapper` per `api/capture.py:254-261` — preserve), `streaming/investigation_adapter.py` (currently has no spine emission — out of scope for this migration).

---

### S-6 Pre-existing Pydantic Settings + env-var convention

**Source:** `backend/src/second_brain/config.py:8-65`

**Pattern (additions only):**
```python
class Settings(BaseSettings):
    azure_ai_project_endpoint: str = ""
    foundry_model: str = "gpt-4o"   # NEW (Phase 24 task group 23.1)
    ...
    model_config = {"env_file": ".env", "case_sensitive": False}
```

**Apply to:** `config.py` — add `foundry_model`, delete agent_id fields per CONFIG-DELTAS Phase 24 task group 23.3 cleanup. Container App env-var sequence handled by operator commands per CONFIG-DELTAS Step A→B→C.

---

### S-7 Push guard sentinel pattern (Task 0 only)

**Source:** none in-repo. Pattern from CONTEXT D-12 + design doc Option A.

**Pattern:**
```bash
# .git/hooks/pre-push (executable)
#!/usr/bin/env bash
SENTINEL=".planning/phases/24-foundry-ga-migration/PUSH-GUARD-ACTIVE"
if [ -f "$SENTINEL" ]; then
    echo "Push blocked: PUSH-GUARD-ACTIVE sentinel present at $SENTINEL." >&2
    echo "Run /gsd-execute-phase Phase 24 to completion before pushing." >&2
    exit 1
fi
exit 0
```

The sentinel `.planning/phases/24-foundry-ga-migration/PUSH-GUARD-ACTIVE` is created by Task 0 and removed at the very end of 23.3 (final unguard step, immediately before the deploy push).

---

### S-8 Probe-fixture-driven mocks

**Source:** `backend/tests/fixtures/foundry-probe/` — already on disk (5 fixtures from Phase 23)

**Pattern:** shape every test mock against a probe fixture rather than against documentation:
- `agent.run(stream=True)` mocks → load `streaming_shape.json`, replay 25-update sequence
- `agent.run(...)` non-streaming mocks → load `tool_call_extraction.json`, return `AgentResponse`-shaped object with `messages=[...]`, `text='...'`, `usage_details={...}`
- `tool_choice='required'` mocks → assert `ChatOptions.tool_choice == "required"` per `tool_choice_required.json`
- Session round-trip mocks → use `AgentSession(session_id="...")` per `session_rehydration.json`
- Credential mocks → accept any azure-credential-shaped object per `auth_probe.json`

**Apply to:** every new test in `backend/tests/` that exercises agent runs, plus mocks already constructed against `client.get_response(...)` rebased to `agent.run(...)`.

---

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| `.git/hooks/pre-push` + `PUSH-GUARD-ACTIVE` sentinel | shell script + flag file | First time the project uses a per-phase push guard. Pattern from CONTEXT D-12 + design doc Option A — see S-7. |
| `backend/src/second_brain/agents/instructions/{investigation,admin,classifier}.md` | static markdown text files | Repo did not previously hold agent instruction text; portal was source. Source content already drafted (`docs/foundry/investigation-agent-instructions.md` + `.planning/phases/23-foundry-ga-prep/CANDIDATE-instructions/admin.md` + `classifier.md`). The "no analog" applies only to the destination directory layout — the content is already curated. |

---

## Consumption notes for the planner

- **23.1 plan order (per D-13):** capture-trace middleware FIRST → custom-span deletion in `streaming/investigation_adapter.py` SECOND. This keeps each commit individually runnable for `git bisect`.
- **23.2 plan order (per D-14):** `eval/invoker.py` introduction lands BEFORE the admin agent rewrite OR alongside in the same commit cluster. Confirm `EVAL-INVENTORY` deletion trigger gates correctly.
- **23.3 plan order (per D-13/D-14):** middleware-first pattern continues. Voice path direct call inserted into `api/capture.py` BEFORE the safety-net deletion in `streaming/adapter.py`. The `forced_tool_failure` emission point is adapter-level (cleanest exception context per CONTEXT discretion item 1).
- **Auditor invocation (CONTEXT D-13/D-14 implicit):** every task group's final commit includes a `gsd-framework-fidelity-auditor` invocation; cumulative audit at end of Phase 24, immediately before the unguard step.
- **Pre-push grep guard (per SPAN-NAME-MAPPING + CONFIG-DELTAS):**
  ```bash
  ! grep -rE '_agent_run|azure_ai_agent\.|AzureAIAgentClient|approval_mode' backend/src/second_brain/
  # Plus: ! grep -rE 'foundryThreadId' backend/src/second_brain/  (post-23.3)
  ```

## Metadata

**Analog search scope:** `backend/src/second_brain/`, `backend/tests/fixtures/foundry-probe/`, `backend/tests/fixtures/{investigation,admin,classifier}/`, `.planning/phases/23-foundry-ga-prep/`
**Files scanned:** 27 modified/new files mapped; 18 distinct analog files read
**Pattern extraction date:** 2026-05-09
