---
phase: 24-foundry-ga-migration
plan: 11
subsystem: backend/processing
tags: [foundry-ga, admin-agent, admin-handoff, tool-detection, f-03, f-08, f-13, f-16, d-08, d-09, d-11]

# Dependency graph
requires:
  - phase: 24-foundry-ga-migration/09
    provides: "app.state.admin_agent (GA Agent built via build_admin_agent, tools pre-registered at lifespan construction)"
  - phase: 24-foundry-ga-migration/10
    provides: "AdminTools + RecipeTools decorator-free async methods (Agent(tools=[instance.method, ...]) bind shape)"
  - phase: 24-foundry-ga-migration/03
    provides: "CaptureTraceAgentMiddleware tagging framework invoke_agent span with capture.trace_id at source"
provides:
  - "Admin background-processing surface fully on GA agent.run(input, options=ChatOptions(tool_choice='required')) contract"
  - "Post-hoc tool detection helper _output_tool_called(response) walking response.messages per probe 2"
  - "D-09 bounded retry preserved (exactly one retry with directive prompt + tool_choice=required)"
  - "Final removal of RC AzureAIAgentClient + Message(role=...) + invocation_count snapshots from processing/admin_handoff.py"
affects:
  - "24-12 (EvalAgentInvoker facade can wrap admin_agent now that handoff is GA-clean)"
  - "24-13 (Admin eval call site at eval/runner.py:278-294 uses the same agent.run+response.messages pattern)"
  - "24-13.5 (admin golden seeding can replay against the GA-shaped handoff)"
  - "api/errands.py wire: process_admin_capture* callers pass app.state.admin_agent; admin_agent_tools list pass-through dropped"

# Tech tracking
tech-stack:
  added:
    - "agent_framework.Agent + agent_framework.ChatOptions wired into Admin processing surface"
    - "Post-hoc tool detection: walk response.messages for role='tool' entries (replaces FunctionTool.invocation_count snapshots)"
  patterns:
    - "process_admin_capture(admin_agent: Agent, ...): tools pre-registered at lifespan; caller does not re-pass them"
    - "_output_tool_called(response) -> tuple[bool, set[str]] — probe-2 shape walks response.messages, reads Content.name or Content.function_name"
    - "D-07 EXPLICIT JUSTIFICATION block recorded inline above the initial agent.run() call per CONTEXT D-11"
    - "admin.* observability attributes ride structured logger.info(..., extra=log_extra) dicts (custom span deleted per F-16)"

key-files:
  created: []
  modified:
    - "backend/src/second_brain/processing/admin_handoff.py"
    - "backend/src/second_brain/api/errands.py"
    - "backend/tests/test_admin_handoff.py"

key-decisions:
  - "admin_tools list parameter DROPPED from process_admin_capture / process_admin_captures_batch signatures — Task 2 has no remaining caller (the invocation-count helpers are deleted). api/errands.py call sites updated to not pass admin_tools."
  - "_mark_inbox_failed kept the `span` parameter for signature back-compat; all post-Task-2 call sites pass None. The `if span:` guard inside the helper means dropping the span did not require body changes."
  - "from opentelemetry import trace dropped along with the module-level `tracer = trace.get_tracer(...)` line — both `with tracer.start_as_current_span(...)` blocks are gone and no other site uses `trace.*`."
  - "admin.* attributes (inbox_item_id, raw_text_length, retry, outcome) lifted onto structured log_extra dicts rather than trace.get_current_span().set_attribute(). Rationale: process_admin_capture runs in asyncio.create_task() AFTER the HTTP request span has ended, so trace.get_current_span() returns NoOpSpan outside agent.run(). Structured logs are the more reliable correlation surface; the framework invoke_agent span (tagged by 24-03 middleware with capture.trace_id) covers the agent run itself."
  - "Test file rewritten to mock AgentResponse-shaped objects with response.messages carrying role='tool' Content blocks (probe 2 shape) rather than mutating FunctionTool.invocation_count counters. 19/19 tests pass against the new shape."
  - "D-07 justification block recorded once above the initial call; a back-reference comment above the retry call cites it (D-09 + same D-07 reasoning) to avoid duplication."

patterns-established:
  - "Phase 24 admin-handoff rewrite is now complete (F-03 + F-16 cleared on Admin surface). The Admin GA pattern is: lifespan factory (24-09) -> @tool-free Tools class (24-10) -> agent.run(input, options=ChatOptions(tool_choice='required')) at the boundary (this plan, 24-11)."
  - "Post-hoc tool detection via response.messages walk is now the canonical pattern for ANY Agent.run() call site that needs to know which tools fired. Future plans (24-12 eval invoker, 24-13 eval runner admin path) inherit this shape."

requirements-completed: [F-03, F-08, F-13, F-16, F-18, D-08, D-09, D-10, D-11, D-14]

# Metrics
duration: 7min
completed: 2026-05-11
---

# Phase 24-11: admin_handoff.py GA Migration Summary

**Admin background-processing rewritten against GA `agent.run(input, options=ChatOptions(tool_choice='required'))`; custom `admin_agent_process` and `admin_agent_batch_process` spans deleted (F-16); post-hoc tool detection helper walks `response.messages` per probe 2 (replaces `FunctionTool.invocation_count` snapshots); D-09 bounded retry preserved with explicit D-07 justification recorded inline; tests rewritten to mock GA `AgentResponse` shape and pass 19/19.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-11T01:55:08Z
- **Completed:** 2026-05-11T02:02:11Z
- **Tasks:** 2
- **Files modified:** 3 (admin_handoff.py + api/errands.py + test_admin_handoff.py)

## Accomplishments

### F-03 cleared (RC imports gone from admin_handoff.py)

Before:
```python
from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
```

After:
```python
from agent_framework import Agent, ChatOptions
```

`Message` no longer needed — GA Agent.run() takes a plain string as first arg (not a `[Message(role="user", text=...)]` list). `AzureAIAgentClient` is replaced by the GA `Agent` singleton constructed in main.py lifespan (24-09).

### F-16 cleared (both custom spans deleted)

Before (process_admin_capture, line 177+):
```python
with tracer.start_as_current_span("admin_agent_process") as span:
    span.set_attribute("admin.inbox_item_id", inbox_item_id)
    span.set_attribute("admin.raw_text_length", len(raw_text))
    if capture_trace_id:
        span.set_attribute("capture.trace_id", capture_trace_id)
    ...
```

Before (process_admin_captures_batch, line 441+):
```python
with tracer.start_as_current_span("admin_agent_batch_process") as span:
    span.set_attribute("admin.batch_size", len(admin_items))
    span.set_attribute("capture.trace_id", capture_trace_id)
    for item in admin_items:
        ...
```

After: both `with` blocks deleted. Function bodies come down one indent level. The `from opentelemetry import trace` import + module-level `tracer = trace.get_tracer(...)` line are also removed since no remaining call site uses them. The `admin.*` attributes that used to ride on the custom span now live on structured `logger.info(..., extra=log_extra)` dicts (`inbox_item_id`, `raw_text_length`, `batch_size`, `capture_trace_id`, `component`, plus the `tools_called` + `outcome=...` keys logged inline at each decision branch).

Capture-trace correlation rides on the framework's auto-emitted `invoke_agent` span (tagged at source by `CaptureTraceAgentMiddleware` from 24-03). The pre-existing `CaptureTraceSpanProcessor` continues to cover non-framework spans (Azure SDK, Cosmos, AppExceptions) per design D-07a.

### Post-hoc tool detection via response.messages

Before (lines 29-40, 55-68, plus pre/post counter snapshots at 238-250):
```python
def _count_tool_invocations(tools: list) -> int:
    total = 0
    for t in tools:
        count = getattr(t, "invocation_count", None)
        if count is not None:
            total += count
    return total

# inside process_admin_capture:
pre_count = _count_tool_invocations(admin_tools)
pre_output_count = _count_output_tool_invocations(admin_tools)
response = await admin_client.get_response(...)
post_count = _count_tool_invocations(admin_tools)
post_output_count = _count_output_tool_invocations(admin_tools)
any_tool_called = post_count > pre_count
output_tool_called = post_output_count > pre_output_count
```

After:
```python
def _output_tool_called(response) -> tuple[bool, set[str]]:
    tools_called: set[str] = set()
    for msg in getattr(response, "messages", None) or []:
        if getattr(msg, "role", None) != "tool":
            continue
        for content in getattr(msg, "contents", None) or []:
            name = getattr(content, "name", None) or getattr(
                content, "function_name", None
            )
            if name:
                tools_called.add(str(name))
    return bool(tools_called & _OUTPUT_TOOL_NAMES), tools_called

# inside process_admin_capture:
response = await admin_agent.run(enriched_text, options=ChatOptions(tool_choice="required"))
output_fired, tools_called = _output_tool_called(response)
any_tool_fired = bool(tools_called)
```

The probe-2 fixture `tool_call_extraction.json` confirms the shape: `response.messages[i].role == "tool"` for tool-result messages, and `msg.contents[j].name` (or `function_name`) identifies the called function. `_OUTPUT_TOOL_NAMES` constant is unchanged — the post-migration source of truth for output detection. The helpers `_count_tool_invocations` and `_count_output_tool_invocations` are deleted (no callers remain).

### D-09 bounded retry with D-07 justification recorded inline (CONTEXT D-11)

```python
# D-07 EXPLICIT JUSTIFICATION (CONTEXT D-11):
# 1. Framework primitive considered: tool_choice='required' (forces
#    SOME tool call).
# 2. What custom code provides: pin which SUBSET of tools
#    (add_errand_items OR add_task_items) the model must call.
#    Framework primitive cannot pin a subset.
# 3. Why not middleware/context provider/tool/configuration:
#    provider-dict {"mode":"required",...} schema is undocumented
#    (probe 3 confirmed); spiking rejected as time-risky in
#    CONTEXT D-10.
# 4. Permanent or temporary: temporary bridge. Deletion trigger:
#    when 'mode' dict schema is documented OR Foundry adds
#    tool_choice subset pinning.
async with asyncio.timeout(60):
    response = await admin_agent.run(
        enriched_text,
        options=ChatOptions(tool_choice="required"),
    )
```

Retry path uses the same `tool_choice="required"` with a directive prompt that nudges the model toward `add_errand_items` / `add_task_items`. Exactly one retry, no loop — matches the pre-migration semantics verbatim.

### Function signature reshape

`process_admin_capture(admin_client: AzureAIAgentClient, admin_tools: list, ...)` becomes `process_admin_capture(admin_agent: Agent, ...)`. The `admin_tools` parameter is dropped entirely — the GA pattern pre-registers tools on the Agent at lifespan construction time (24-09), and post-hoc tool detection from `response.messages` doesn't need the list. Same change for `process_admin_captures_batch`.

### api/errands.py wire updated

```diff
- admin_client = getattr(request.app.state, "admin_client", None)
- if admin_client is not None:
+ admin_agent = getattr(request.app.state, "admin_agent", None)
+ if admin_agent is not None:

      ...
-     admin_tools = getattr(request.app.state, "admin_agent_tools", [])
      ...
      task = asyncio.create_task(
          process_admin_capture(
-             admin_client=admin_client,
-             admin_tools=admin_tools,
+             admin_agent=admin_agent,
              cosmos_manager=cosmos_manager,
              ...
          )
      )
```

`app.state.admin_agent` is set by the 24-09 lifespan; the `admin_agent_tools` attribute is no longer published on `app.state` (the list lives only inside `build_admin_agent`'s `tools=` arg). The errands handler's branching logic is unchanged otherwise.

### Test rewrite (test_admin_handoff.py)

Mocks rewritten to construct probe-2-shaped responses:

```python
def _tool_message(tool_name: str) -> MagicMock:
    msg = MagicMock()
    msg.role = "tool"
    msg.contents = [_tool_content(tool_name)]
    msg.text = ""
    return msg


def _agent_response(text: str, tool_names: list[str] | None = None) -> MagicMock:
    response = MagicMock()
    response.text = text
    messages = [_assistant_message("")]
    for name in tool_names or []:
        messages.append(_tool_message(name))
    messages.append(_assistant_message(text))
    response.messages = messages
    return response
```

Tests now exercise both the response-shape contract (mocks set up to mirror what the GA SDK actually returns) and the post-hoc helper's traversal logic. The fixture `mock_admin_agent` returns an AsyncMock whose `run()` is configured per-test. All 19 test cases pass (covering success, failure, no-tool-call, intermediate-only-with-retry-success, intermediate-only-with-retry-fail, timeout, and batch scenarios).

## Task Commits

| Task | Hash      | Title                                                                       |
|------|-----------|-----------------------------------------------------------------------------|
| 1    | `e94f1de` | feat(24-11): rewrite admin_handoff imports + signatures for GA Agent        |
| 2    | `081a2f6` | feat(24-11): post-hoc tool detection + custom span deletion in admin_handoff |

_(Plan metadata commit will land separately as the final commit of this plan.)_

## Files Created/Modified

- `backend/src/second_brain/processing/admin_handoff.py` — full rewrite. Imports: `Agent` + `ChatOptions` (no `Message`, no `AzureAIAgentClient`, no `from opentelemetry import trace`). Module-level `tracer = trace.get_tracer(...)` removed. New `_output_tool_called(response)` helper. Deleted `_count_tool_invocations` + `_count_output_tool_invocations`. Both `with tracer.start_as_current_span(...)` blocks deleted; bodies de-indented one level. Both call sites use `admin_agent.run(input, options=ChatOptions(tool_choice="required"))`. D-07 justification block landed inline above the initial call. admin.* attrs lifted onto structured log_extra. `admin_tools` param dropped from both function signatures. `_mark_inbox_failed`'s `span` param retained for signature back-compat; all call sites pass `None`. ~470 lines (was ~455; net +15 from added D-07 comment block + log-extra dicts).
- `backend/src/second_brain/api/errands.py` — `app.state.admin_client` -> `app.state.admin_agent` (line 172-173); `admin_tools = getattr(...)` line removed (line 202); both `process_admin_capture(admin_client=..., admin_tools=...)` and `process_admin_captures_batch(admin_client=..., admin_tools=...)` call sites updated to `(admin_agent=..., ...)` with the `admin_tools` kwarg removed.
- `backend/tests/test_admin_handoff.py` — full rewrite to GA shape (~497 lines). New `_agent_response()` / `_tool_message()` / `_assistant_message()` mock builders. `mock_admin_agent` fixture replaces `mock_admin_client` + `mock_admin_tools`. 19 test cases pass.

## Decisions Made

- **Dropped `admin_tools` param from `process_admin_capture` signature** (not in plan instructions, but follows logically from removing the invocation-count helpers). The plan's must-have truth says "Spine emission and _mark_inbox_failed unchanged" but doesn't pin the `admin_tools` param. Keeping it would have been dead weight; api/errands.py was already in scope for caller updates. Net result: cleaner signature, one fewer kwarg threaded through callers. The lifespan-bound tools list lives inside `Agent`'s `tools=` at construction (24-09) and is no longer threaded into the handoff.

- **`_mark_inbox_failed` signature preserved verbatim.** The plan's must-have truth pins this as "unchanged". The helper's `span` parameter is kept; all call sites now pass `None`. The `if span:` guard inside the helper means no behavioral change. Future plan can drop the param when no caller stubs it.

- **admin.* attributes lifted onto log_extra, not onto framework invoke_agent span via `trace.get_current_span().set_attribute()`.** Two reasons: (1) `process_admin_capture` runs in `asyncio.create_task()` AFTER the HTTP request span has ended, so `trace.get_current_span()` outside `agent.run()` returns the NoOpSpan; (2) the framework's `invoke_agent` span is created INSIDE `agent.run()` execution — code outside that scope cannot tag it. Structured logs are the more reliable correlation surface; capture-trace correlation rides on the framework span via CaptureTraceAgentMiddleware from 24-03. This is a divergence from the 24-07 Investigation pattern (which sets `investigate.*` on the AppRequests span via `api/capture.py:228`), driven by the fact that admin_handoff runs OFF the request thread.

- **Test rewrite landed in same commit as Task 2** (rather than as a separate test-only commit). The plan's Task 2 acceptance gate requires `cd backend && uv run pytest tests/test_admin_handoff.py -x` to exit 0. Splitting tests into their own commit would have left Task 2 in a RED state. Co-located commit keeps every commit individually green for the admin_handoff test suite.

- **`agent.run()` call signature uses positional `input` arg (not `messages=[...]`).** Per probe 2 `tool_call_extraction.json`: the GA `Agent.run(input, options=..., session=...)` shape takes a plain string as first positional arg. No `messages=` keyword. The probe fixture's `response.text='echo: probe two'` for input "echo: probe two" confirms the string-input flow. This matches the planner's interface block in the plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] D-07 justification comment block tripped ruff E501 (line-too-long) on two lines**

- **Found during:** Task 2 first ruff check after Write — lines 240 and 242 exceeded 88 chars by 4 and 2 chars respectively.
- **Issue:** The plan's literal-text D-07 justification block (in the `<interfaces>` section of the plan body) was 92 chars on line 1 and 90 chars on line 3. Pasting verbatim violated the 88-char limit.
- **Fix:** Reflowed the comment block onto more lines, preserving all 4 numbered justifications verbatim (the load-bearing prose is unchanged; only the line-break positions differ). The acceptance grep `grep -q "D-07 EXPLICIT JUSTIFICATION"` still matches.
- **Files modified:** `backend/src/second_brain/processing/admin_handoff.py` (lines 239-251 — reformatted in place)
- **Verification:** `uv run ruff check src/second_brain/processing/admin_handoff.py` returns "All checks passed!".
- **Committed in:** `081a2f6` (Task 2 commit — the reformat happened pre-commit; final file shows the reflowed version).

**2. [Rule 2 — Critical functionality] Test fixture overhaul to match GA response shape**

- **Found during:** Task 1 import smoke check passed, but Task 1's `pytest tests/test_admin_handoff.py -x` immediately failed with `TypeError: process_admin_capture() got an unexpected keyword argument 'admin_client'`.
- **Issue:** The existing 12-fixture test file was written entirely against the RC `AzureAIAgentClient.get_response()` shape. Every test passed `admin_client=...` and `admin_tools=[FunctionTool-shaped mock with .invocation_count]`. With Task 1's signature rename + Task 2's signature simplification, every test was broken.
- **Fix:** Whole-file rewrite of `tests/test_admin_handoff.py`. New mock builders (`_agent_response`, `_tool_message`, `_assistant_message`) construct probe-2-shaped responses. `mock_admin_agent` fixture replaces `mock_admin_client` + `mock_admin_tools`. All 19 test cases ported to the new shape. Test semantics are unchanged — success/failure/no-tool-call/intermediate-only/retry-success/timeout/batch coverage is preserved.
- **Files modified:** `backend/tests/test_admin_handoff.py` (full rewrite, +287 / -270 net)
- **Verification:** `uv run pytest tests/test_admin_handoff.py -x` -> 19 passed. `uv run pytest tests/test_admin_handoff.py tests/test_admin_integration.py tests/test_admin_task_tools.py tests/test_admin_tools.py` -> 54 passed, 1 skipped (the skipped one is pre-existing).
- **Committed in:** `081a2f6` (Task 2 commit — co-located with the implementation change so every commit is individually green).

**3. [Rule 3 — Blocking] api/errands.py call sites needed updating for the dropped `admin_tools` kwarg**

- **Found during:** Task 2 dropped the `admin_tools` param from `process_admin_capture` / `process_admin_captures_batch`. The plan's Task 1 part C already had us update errands.py to use `admin_agent=` and `app.state.admin_agent`. Task 2's additional drop of `admin_tools=` from those call sites was a follow-on.
- **Issue:** After dropping the parameter from the function signature, calling `process_admin_capture(admin_agent=..., admin_tools=..., ...)` would raise `TypeError: got an unexpected keyword argument 'admin_tools'`.
- **Fix:** Removed both the `admin_tools = getattr(request.app.state, "admin_agent_tools", [])` line and the two `admin_tools=admin_tools` kwargs in the `asyncio.create_task(...)` calls. errands.py imports cleanly post-change.
- **Files modified:** `backend/src/second_brain/api/errands.py` (lines 202, 221, 233 — local removal)
- **Verification:** `uv run python -c "from second_brain.api.errands import router; print('OK')"` exits 0.
- **Committed in:** `081a2f6` (Task 2 commit — bundled with the function-signature simplification).

---

**Total deviations:** 3 auto-fixed (1 lint reformatting, 1 test-suite migration, 1 caller-signature follow-on). No Rule 4 architectural changes. No scope expansion — all three deviations are within the natural scope of "rewrite admin_handoff against GA" + the plan-checker-acceptable subset of caller updates.

## Authentication Gates

None encountered. The local main.py is intentionally not buildable end-to-end (per CONTEXT D-13 relaxation — Classifier slice still on RC); plan validation is via import smoke + ruff + the GA-shaped test suite, none of which require Azure connectivity.

## Known Stubs

None. All data sources are wired: admin_agent is the lifespan-singleton from 24-09; the GA Agent has 6 (or 7 with Playwright) tools pre-registered; the post-hoc detection helper walks the real response.messages structure.

## Threat Flags

None — this plan does not introduce new network endpoints, auth paths, file access patterns, or trust-boundary changes. The Cosmos write paths (`_mark_inbox_failed`, "pending" upsert, "completed" upsert, `delete_item`) are byte-for-byte identical pre/post-migration. The spine emission helper (`emit_agent_workload`) is unchanged. Capture-trace correlation continues to ride the same `capture.trace_id` attribute name; KQL queries that filter on `Properties.capture_trace_id` continue to find admin-segment events.

## Verification Snapshot (post-execution)

```
=== Acceptance grep checks ===
[OK] no agent_framework.azure
[OK] Agent + ChatOptions imports
[OK] no Message(role=
[OK] admin_agent: Agent in signatures
[OK] no admin_client refs
[OK] no admin_agent_process span
[OK] no admin_agent_batch_process span
admin_agent.run( occurrences: 2 (expect 2)
[OK] tool_choice="required"
[OK] _output_tool_called helper
[OK] D-07 EXPLICIT JUSTIFICATION inline
[OK] no _count_tool_invocations
[OK] no _count_output_tool_invocations

=== Lint ===
uv run ruff check src/second_brain/processing/admin_handoff.py: All checks passed!
uv run ruff check src/second_brain/api/errands.py: All checks passed!
uv run ruff check tests/test_admin_handoff.py: All checks passed!

=== Module imports ===
from second_brain.processing.admin_handoff import process_admin_capture, _output_tool_called, process_admin_captures_batch -> OK
from second_brain.api.errands import router -> OK

=== Test suite ===
tests/test_admin_handoff.py: 19 passed
tests/test_admin_handoff.py + test_admin_integration.py + test_admin_task_tools.py + test_admin_tools.py: 54 passed, 1 skipped

=== Phase 24 invariant tests ===
test_legacy_middleware_imports_survive.py: 4 passed (P1-3 invariant green)
test_foundry_credential_shape.py: 1 passed (P1-5 invariant green)
test_no_rc_imports_after_cleanup.py: still RED (expected) — admin_handoff.py REMOVED from offender list; remaining 5 distinct files (classifier.py, eval/runner.py, main.py, streaming/adapter.py, warmup.py) are scope of 24-14 / 24-13 / 24-19. Offender file count: 6 -> 5.
```

## Self-Check: PASSED

- `backend/src/second_brain/processing/admin_handoff.py` — exists, GA-shaped (zero `AzureAIAgentClient` / `Message(role=` / `admin_client` / `admin_agent_process` / `admin_agent_batch_process` / `_count_tool_invocations` references)
- `backend/src/second_brain/api/errands.py` — exists, uses `app.state.admin_agent`, no `admin_tools` kwarg threaded into handoff calls
- `backend/tests/test_admin_handoff.py` — exists, 19/19 tests pass against GA shape
- Commit `e94f1de` — present in `git log --oneline -3` (Task 1)
- Commit `081a2f6` — present in `git log --oneline -3` (Task 2)
- D-07 EXPLICIT JUSTIFICATION block present inline above first agent.run() call
- 2 occurrences of `admin_agent.run(` (initial + bounded retry per D-09)

## Next Phase Readiness

- **Plan 24-12 (EvalAgentInvoker facade):** ready to wrap `admin_agent` — the GA-clean handoff exposes a stable `agent.run(input, options=ChatOptions(tool_choice="required"))` contract that the facade's `invoke_admin` method can call directly.
- **Plan 24-13 (admin eval call site at eval/runner.py:278-294):** inherits the same `agent.run()` + `response.messages` post-hoc detection pattern. The `_output_tool_called` helper could be lifted out of `admin_handoff` and shared if 24-13 wants to reuse it; alternatively, runner.py duplicates the ~10-line walk.
- **Plan 24-13.5 (admin golden seeding):** can replay against the new GA-shaped handoff. Seed cases drive `process_admin_capture(admin_agent=test_agent, ...)` directly; the GA shape is the call surface.
- **RC import offender list:** 6 -> 5 distinct files (admin_handoff.py cleared). Remaining offenders (classifier.py, eval/runner.py, main.py, streaming/adapter.py, warmup.py) clear in 24-14, 24-13, 24-13/14, 24-14, 24-19 respectively. AST scan red test stays RED until 24-19.
- **Admin processing pipeline:** the chain lifespan factory (24-09) -> @tool-free Tools class (24-10) -> GA agent.run boundary (24-11) is now end-to-end GA-clean. Plans 24-12/24-13 are eval-surface work; the production capture path is unaffected by them.

---
*Phase: 24-foundry-ga-migration*
*Plan: 11*
*Completed: 2026-05-11*
