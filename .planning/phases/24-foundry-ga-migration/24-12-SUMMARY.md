---
phase: 24-foundry-ga-migration
plan: 12
subsystem: backend/eval
tags: [foundry-ga, eval-facade, evalagentinvoker, migration-seam, d-04, d-07, f-06, f-07]

# Dependency graph
requires:
  - phase: 24-foundry-ga-migration/11
    provides: "Admin handoff fully on GA agent.run(...) - admin_agent available at app.state.admin_agent"
  - phase: 24-foundry-ga-migration/10
    provides: "AdminTools / RecipeTools decorator-free async methods (DryRunAdminTools mirrors signatures)"
  - phase: 23-foundry-ga-prep/EVAL-INVENTORY.md
    provides: "Facade interface spec + D-07 explicit-justification template + side-effect contract"
provides:
  - "EvalAgentInvoker Protocol facade in backend/src/second_brain/eval/invoker.py"
  - "Two concrete implementations: RCEvalAgentInvoker (lifted from runner.py:133-149 + 278-294) and GAEvalAgentInvoker (Agent.run with tools= kwarg per probe 2)"
  - "_MigrationHybridInvoker composing RC for classifier (until plan 24-18) and GA for admin (live now)"
  - "runner.py + foundry.py both routed through invoker - no direct client.get_response calls remain in eval/"
  - "D-07 EXPLICIT JUSTIFICATION block inline in invoker.py with deletion trigger pinned to plan 24-18"
affects:
  - "24-13 (Classifier kickoff): can ship without waiting on eval-side rework - the invoker hides the RC/GA split"
  - "24-13.5 (admin golden seeding): seed script + cases.yaml drive runner via the new invoker shape"
  - "24-18 (final cleanup): single deletion target - drop RCEvalAgentInvoker + _MigrationHybridInvoker, optionally inline GA invoker"
  - "tools/investigation.py + api/eval.py: both gain hybrid-invoker construction at the call-site (N-5 lock-in)"

# Tech tracking
tech-stack:
  added:
    - "agent_framework.ChatOptions on the GA classifier path (tool_choice='required' string form per probe 3)"
    - "agent.run(input, tools=[...], options=ChatOptions(...)) per-call tools binding for eval cases"
    - "_MigrationHybridInvoker composition pattern (RC classifier + GA admin) constructed at call-site"
  patterns:
    - "Side-effect contract on tools_instance preserved end-to-end: runner reads last_bucket / last_confidence / captured_destinations / captured_tasks, NOT the response object"
    - "RC types (Message, ChatOptions with tool_choice dict) imported INSIDE RCEvalAgentInvoker method bodies, not at module level - keeps invoker.py free of top-level RC dependency"
    - "Auto-format-safe pattern: in tools/investigation.py the invoker imports live inside _build_eval_invoker() helper method (local imports), preventing ruff from stripping them mid-edit"

key-files:
  created:
    - "backend/src/second_brain/eval/invoker.py"
    - ".planning/phases/24-foundry-ga-migration/24-12-SUMMARY.md"
  modified:
    - "backend/src/second_brain/eval/runner.py"
    - "backend/src/second_brain/eval/foundry.py"
    - "backend/src/second_brain/api/eval.py"
    - "backend/src/second_brain/tools/investigation.py"
    - "backend/src/second_brain/main.py"
    - "backend/tests/test_eval.py"

key-decisions:
  - "Hybrid composition lives in eval/invoker.py (N-5 lock-in), NOT in eval/runner.py. The runner only types its parameter as the Protocol; the call-site (api/eval.py + tools/investigation.py) constructs the hybrid. This makes plan 24-18 a single-file deletion."
  - "RC-only types (Message, ChatOptions with tool_choice dict) are imported INSIDE RCEvalAgentInvoker method bodies (local imports). The module-level surface of invoker.py only imports from agent_framework what GAEvalAgentInvoker actually uses (ChatOptions). This minimises the RC-dependency footprint and makes 24-18 cleanup mechanical."
  - "GAEvalAgentInvoker passes tools per-call via agent.run(tools=[...]) rather than constructing a fresh per-case Agent. Per probe tool_call_extraction.json this is supported. The per-case tools (EvalClassifierTools / DryRunAdminTools) hold case-scoped state - they cannot be lifespan-registered on the singleton agent."
  - "Admin path uses default tool_choice (auto) - matches the pre-migration admin eval contract per EVAL-INVENTORY call site 2 behavior. Only the classifier path forces tool_choice='required' (single tool registered)."
  - "generate_app_mediated_dataset constructs EvalClassifierTools / DryRunAdminTools instances per case INTERNALLY (not via the existing classifier_tools / admin_tools parameter pair). The tool_calls JSONL rows are synthesised from side-effect state (last_bucket, captured_items, captured_tasks) post-invocation. This collapses the parameter surface from 4 params (client + tools per agent) to 1 (invoker)."
  - "tools/investigation.py: new admin_agent= __init__ parameter (default None for back-compat) holds the GA Agent instance. Invoker construction happens lazily inside _build_eval_invoker() so eval tools can still degrade gracefully when only one side is configured."
  - "test_eval.py rewrite uses _make_classifier_invoker_mock / _make_admin_invoker_mock helpers returning AsyncMock with invoke_classifier(input_text, tools_instance) signatures that drive the same EvalClassifierTools.file_capture(...) / DryRunAdminTools.add_errand_items(...) side effects as the old per-tool mocks - test semantics preserved exactly."

patterns-established:
  - "Phase 24 eval-surface migration completed (F-06 + F-07 cleared). The eval pattern is now: api/eval.py or tools/investigation.py constructs _MigrationHybridInvoker(rc, ga) -> runner.run_*_eval(invoker=...) -> invoker.invoke_*(input_text, tools_instance) -> framework executes tools -> runner reads side effects. Plan 24-18 collapses this to GAEvalAgentInvoker only."
  - "RC types kept off module-level imports via local-import-inside-method pattern. Established for invoker.py and lifted into tools/investigation.py's _build_eval_invoker(). Pattern repeatable for any future temporary RC-bridge code."

requirements-completed: [F-06, F-07, D-04, D-07]

# Metrics
duration: ~13min
completed: 2026-05-11
---

# Phase 24-12: EvalAgentInvoker Facade Summary

**EvalAgentInvoker Protocol facade landed at `backend/src/second_brain/eval/invoker.py` with four classes (Protocol + RC impl + GA impl + _MigrationHybridInvoker) and a D-07 EXPLICIT JUSTIFICATION block inline. Both `eval/runner.py` admin (lines 278-294) and classifier (lines 133-149) call sites are now routed through `invoker.invoke_admin(...)` / `invoker.invoke_classifier(...)`; `eval/foundry.py`'s `generate_app_mediated_dataset` replaces the duck-typed `hasattr(msg, 'tool_calls')` extraction with the side-effect read pattern. F-06 and F-07 cleared. Per-destination flat-accuracy contract preserved unchanged. Deletion trigger pinned to plan 24-18.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-05-11T02:08:53Z
- **Completed:** 2026-05-11T02:22:10Z
- **Tasks:** 3
- **Files modified:** 7 (1 new: invoker.py; 6 modified: runner.py, foundry.py, api/eval.py, tools/investigation.py, main.py, test_eval.py)

## Accomplishments

### F-06 cleared (eval/runner.py)

Before (RC-shaped call sites at lines 133-149 and 278-294):

```python
# Classifier
messages = [Message(role="user", text=case["inputText"])]
options = ChatOptions(
    tools=[eval_tools.file_capture],
    tool_choice={"mode": "required", "required_function_name": "file_capture"},
)
await _call_with_retry(
    lambda m=messages, o=options: classifier_client.get_response(
        messages=m, options=o
    ),
    ...
)

# Admin (similar shape with admin_client.get_response)
```

After:

```python
await _call_with_retry(
    lambda et=eval_tools, txt=case["inputText"]: invoker.invoke_classifier(txt, et),
    ...
)

await _call_with_retry(
    lambda dt=dry_run_tools, txt=input_text, rc=routing_context: invoker.invoke_admin(txt, dt, rc),
    ...
)
```

The `from agent_framework import ChatOptions, Message` top-level import is gone from `runner.py`. The signature changes from `*_client: AzureAIAgentClient` to `invoker: EvalAgentInvoker`. The 7-step orchestration body (read cases, iterate, compute metrics, write Cosmos, update status) is byte-for-byte unchanged.

### F-07 cleared (eval/foundry.py)

Before (`generate_app_mediated_dataset` at lines 875-895 classifier, 918-944 admin):

```python
messages = [Message(role="user", text=item["inputText"])]
options = ChatOptions(tools=classifier_tools)
async with asyncio.timeout(60):
    response = await classifier_client.get_response(
        messages=messages, options=options
    )
if hasattr(response, "messages"):
    for msg in response.messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                row["tool_calls"].append({
                    "name": getattr(tc, "name", ""),
                    "arguments": getattr(tc, "arguments", {}),
                })
        if hasattr(msg, "text") and msg.text:
            row["response_text"] = msg.text
```

After:

```python
eval_tools = EvalClassifierTools()
async with asyncio.timeout(60):
    await invoker.invoke_classifier(item["inputText"], eval_tools)

# Side-effect read: synthesise the file_capture tool_call row from
# EvalClassifierTools state. Mirrors what the production classifier
# would have called via the file_capture tool stub.
if eval_tools.last_bucket is not None:
    row["tool_calls"].append(
        {
            "name": "file_capture",
            "arguments": {
                "text": item["inputText"],
                "bucket": eval_tools.last_bucket,
                "confidence": eval_tools.last_confidence or 0.0,
                "status": eval_tools.last_status or "",
            },
        }
    )
```

Admin path follows the same shape using `DryRunAdminTools` and synthesising `add_errand_items` / `add_task_items` rows from `captured_items` / `captured_tasks`. The function-level `from agent_framework import ChatOptions, Message` is gone. `run_classifier_eval` / `run_admin_eval` in foundry.py lose their `*_client` + `*_tools` parameter pairs in favour of a single `invoker: EvalAgentInvoker` keyword.

### EvalAgentInvoker facade with four classes

`backend/src/second_brain/eval/invoker.py` (NEW, 202 lines):

```python
"""EvalAgentInvoker -- temporary facade hiding RC/GA call shape during migration.

D-07 EXPLICIT JUSTIFICATION (per EVAL-INVENTORY.md round-15):

1. Framework primitive considered: Agent.run(messages) direct.
2. What custom code provides: translation between cases
   (input + expected label) and agent.run() call shape, AND adapting
   the response back to the runner's existing per-case dict format.
3. Why not middleware/context provider/tool/configuration: it CAN be
   solved by either, but during the migration window we have BOTH RC and
   GA call shapes alive (classifier on RC until plans 24-13..24-17,
   admin on GA after plans 24-09..24-11). The facade hides that split
   for one migration window.
4. Permanent or temporary: temporary. Deletion trigger: end of plan 24-18,
   when no RCEvalAgentInvoker caller remains.
"""

class EvalAgentInvoker(Protocol):
    async def invoke_classifier(...) -> None: ...
    async def invoke_admin(...) -> None: ...

class GAEvalAgentInvoker:
    # agent.run(input_text, tools=[...], options=ChatOptions(tool_choice="required"))

class RCEvalAgentInvoker:
    # classifier_client.get_response(messages=[Message(role="user", text=...)], options=ChatOptions(...))
    # Local imports of Message + RCChatOptions INSIDE methods (not module-level)

class _MigrationHybridInvoker:
    # routes invoke_classifier -> RC, invoke_admin -> GA
    # leading underscore = deletion-trigger-aligned private API
```

### Hybrid composition pattern (classifier->RC, admin->GA) at the call-site

Per N-5 lock-in: the runner takes a single `invoker: EvalAgentInvoker` parameter. Two call-sites construct the hybrid:

**1. `api/eval.py::_build_migration_invoker`:**

```python
def _build_migration_invoker(classifier_client, admin_agent) -> _MigrationHybridInvoker:
    rc_invoker = RCEvalAgentInvoker(classifier_client=classifier_client, admin_client=None)
    ga_invoker = GAEvalAgentInvoker(classifier_agent=None, admin_agent=admin_agent)
    return _MigrationHybridInvoker(rc_invoker=rc_invoker, ga_invoker=ga_invoker)
```

**2. `tools/investigation.py::InvestigationTools._build_eval_invoker`:**

```python
def _build_eval_invoker(self) -> Any:
    # Local imports keep the migration-temporary symbols out of the
    # module-level surface (auto-format-safe pattern).
    from second_brain.eval.invoker import (
        GAEvalAgentInvoker,
        RCEvalAgentInvoker,
        _MigrationHybridInvoker,
    )
    rc_invoker = RCEvalAgentInvoker(
        classifier_client=self._classifier_client, admin_client=None,
    )
    ga_invoker = GAEvalAgentInvoker(
        classifier_agent=None, admin_agent=self._admin_agent,
    )
    return _MigrationHybridInvoker(rc_invoker=rc_invoker, ga_invoker=ga_invoker)
```

The runner does NOT import `_MigrationHybridInvoker` directly; it only types the parameter as the Protocol. Plan 24-18 deletes the hybrid + RC class together; both call-sites collapse to constructing a plain `GAEvalAgentInvoker(classifier_agent=..., admin_agent=...)`.

### D-07 EXPLICIT JUSTIFICATION block inline

Per CONTEXT D-07 + EVAL-INVENTORY round-15, the facade's temporary nature is justified in the module docstring with the four-question template:

1. **Framework primitive considered:** `Agent.run(messages)` direct.
2. **What custom code provides:** Translation between cases and `agent.run()` call shape; adapter back to per-case dict format.
3. **Why not middleware/context provider/tool/configuration:** It could, but during the migration window BOTH RC and GA call shapes are alive (classifier on RC until 24-13..24-17, admin on GA after 24-09..24-11). The facade hides that split for one migration window.
4. **Permanent or temporary:** Temporary. **Deletion trigger: end of plan 24-18,** when no RCEvalAgentInvoker caller remains.

### Per-destination flat-accuracy contract preserved (NOT widened)

Per EVAL-INVENTORY round-15 P-01 + CONTEXT-deferred follow-up: `eval/metrics.py::compute_admin_metrics` continues to emit a single flat accuracy float per destination (line 137-176, unchanged). No precision/recall expansion. The +/-5pp class-specific drop check still operates on whatever the runner emits on both sides of the migration. Widening to true precision/recall is a separate `eval/metrics.py` follow-up tracked outside this plan.

### Side-effect contract preserved end-to-end

Per EVAL-INVENTORY call sites 1 and 2 behavior contracts:

- **Classifier:** `eval_tools.last_bucket` / `eval_tools.last_confidence` / `eval_tools.last_status` set inside `EvalClassifierTools.file_capture` when the model invokes the stub. Runner reads side effects, not response.
- **Admin:** `dry_run_tools.captured_destinations` / `dry_run_tools.captured_items` / `dry_run_tools.captured_tasks` set inside `DryRunAdminTools.add_errand_items` / `add_task_items` when the model invokes the stubs. Runner reads side effects, not response.

The invoker doesn't change this contract - it just hides the RC vs. GA call shape between input string and tool-stub invocation.

## Task Commits

| Task | Hash      | Title                                                                        |
|------|-----------|------------------------------------------------------------------------------|
| 1    | `1cea788` | feat(24-12): introduce EvalAgentInvoker facade (Protocol + RC + GA + hybrid) |
| 2    | `e498e0b` | feat(24-12): route runner.py classifier+admin paths through invoker          |
| 3    | `c53eba7` | feat(24-12): route foundry.py app-mediated path through invoker              |

_(Plan metadata commit will land separately as the final commit of this plan.)_

## Files Created/Modified

- **`backend/src/second_brain/eval/invoker.py`** (NEW, 202 lines) - Protocol + RC + GA + Hybrid. D-07 justification block in module docstring. RC types imported locally inside method bodies. Imports only `ChatOptions` from `agent_framework` at module level (used by GAEvalAgentInvoker). `TYPE_CHECKING` imports for `Agent`, `AzureAIAgentClient`, and the dry-run tools classes.
- **`backend/src/second_brain/eval/runner.py`** - Both `run_classifier_eval` and `run_admin_eval` signatures change from `*_client: AzureAIAgentClient` to `invoker: EvalAgentInvoker`. Top-level `from agent_framework import ChatOptions, Message` import dropped. Body changes are localised to the per-case `_call_with_retry(lambda: invoker.invoke_*(...))` lines. The TYPE_CHECKING block loses `AzureAIAgentClient`. Module docstring updated to explain the hybrid composition strategy + N-5 lock-in.
- **`backend/src/second_brain/eval/foundry.py`** - `generate_app_mediated_dataset` parameter list collapsed from `(classifier_client, classifier_tools, admin_client, admin_tools, project_client)` to `(invoker, project_client)`. Both classifier and admin branches construct `EvalClassifierTools()` / `DryRunAdminTools(routing_context=...)` per case and read side effects post-invocation to synthesise tool_calls JSONL rows. `run_classifier_eval` and `run_admin_eval` (foundry-side) signatures updated to match. Function-level `from agent_framework import ChatOptions, Message` removed.
- **`backend/src/second_brain/api/eval.py`** - Added `_build_migration_invoker(classifier_client, admin_agent)` helper. POST `/api/eval/run` handler reads `app.state.admin_agent` (GA) alongside `app.state.classifier_client` (RC) and constructs the hybrid. Module docstring updated.
- **`backend/src/second_brain/tools/investigation.py`** - `InvestigationTools.__init__` gains an optional `admin_agent: Any = None` parameter. New `_build_eval_invoker()` helper method with local imports of the migration-temporary symbols. Both `run_classifier_eval` and `run_admin_eval` tool methods construct the hybrid invoker inline. Admin guard updated from `if self._admin_client is None` to `if self._admin_agent is None and self._admin_client is None` for back-compat during migration window.
- **`backend/src/second_brain/main.py`** - Lifespan passes `admin_agent=getattr(app.state, "admin_agent", None)` to `InvestigationTools(...)` so the GA admin path is wired through to the tools.
- **`backend/tests/test_eval.py`** - `_make_classifier_agent_mock` / `_make_admin_agent_mock` renamed to `_make_classifier_invoker_mock` / `_make_admin_invoker_mock` returning AsyncMocks with `invoke_classifier(input_text, tools_instance)` / `invoke_admin(input_text, tools_instance, routing_context)` signatures that drive the SAME side-effect contract. All 19 test cases ported; semantics preserved. Inline `fake_get_response` fakes converted to `fake_invoke_classifier` shape across timeout, progress, retry-success, and exhaust-retries tests.

## Decisions Made

- **Hybrid lives in invoker.py, NOT runner.py (N-5 lock-in).** Plan explicitly required this. The runner takes a single invoker Protocol parameter; the call-site constructs the hybrid. Two call-sites for hybrid construction (api/eval.py + tools/investigation.py), one deletion target in 24-18.

- **RC types as local imports inside RCEvalAgentInvoker methods.** Module-level invoker.py only imports `ChatOptions` from agent_framework (used by GAEvalAgentInvoker). Inside RCEvalAgentInvoker methods, `from agent_framework import ChatOptions as RCChatOptions, Message` are local imports. This keeps the module surface RC-clean even though the file still contains an RC implementation. The AST scan red test test_no_rc_imports_after_cleanup.py picks up the TYPE_CHECKING-only import of AzureAIAgentClient - this is expected and goes away in 24-18 when RCEvalAgentInvoker is deleted.

- **Auto-format-safe pattern for invoker imports in tools/investigation.py.** The migration-temporary symbols (RCEvalAgentInvoker, GAEvalAgentInvoker, _MigrationHybridInvoker) are imported INSIDE `_build_eval_invoker()` method body as local imports, not at module-level. Two benefits: (1) ruff auto-format cannot strip them mid-edit because the usage is in the same code block as the import, (2) the symbol surface that gets deleted in 24-18 is bounded to a single method body. This pattern is now established for any future migration-temporary bridges.

- **generate_app_mediated_dataset constructs eval-side tool instances internally.** The function previously took external `classifier_tools` / `admin_tools` lists. Plan 24-12 collapses that surface to a single `invoker:` parameter; the function now constructs `EvalClassifierTools()` / `DryRunAdminTools(routing_context=...)` per case and reads side effects to synthesise tool_calls rows. This makes the JSONL artifact format independent of caller-supplied tools and matches the side-effect contract used by runner.py.

- **tools/investigation.py InvestigationTools.__init__ adds admin_agent parameter (default None).** Back-compat preserved for existing tests that only pass `classifier_client`. The new parameter holds the GA Agent instance from `app.state.admin_agent` (set by 24-09). Admin guard widened to `if self._admin_agent is None and self._admin_client is None` so the tool degrades gracefully if neither side is configured.

- **test_eval.py invoker mock helpers return AsyncMock with invoke_classifier/invoke_admin signatures.** The mocks directly drive the tools_instance side effects (file_capture, add_errand_items) the same way the old RC mocks drove options["tools"][0]. Test semantics are byte-for-byte preserved across all 19 cases.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Auto-format reflowed an admin lambda into a too-long line (E501)**

- **Found during:** Task 2 first ruff check after Edit on runner.py.
- **Issue:** The lambda `lambda dt=dry_run_tools, txt=case["inputText"], rc=routing_context: invoker.invoke_admin(txt, dt, rc)` got reformatted into a single line that exceeded 88 chars by 1 char.
- **Fix:** Hoisted `input_text = case["inputText"]` to a local variable, then used `txt=input_text` in the lambda so the call fits within line length. No behavioral change.
- **Files modified:** `backend/src/second_brain/eval/runner.py` (lines 286-292)
- **Verification:** `uv run ruff check src/second_brain/eval/runner.py` returns "All checks passed!".
- **Committed in:** `e498e0b` (Task 2 commit).

**2. [Rule 3 - Blocking] api/eval.py invoker imports got auto-format-stripped on first Edit attempt**

- **Found during:** Task 2 Edit on api/eval.py adding `from second_brain.eval.invoker import ...`.
- **Issue:** ruff auto-format hook ran between Edits and stripped the imports because the call sites (which use them) hadn't been updated yet (MEMORY.md Phase 17.1 lesson hit again).
- **Fix:** Used a single Write on the full file that landed the imports + helper function + call-site updates in one atomic operation, so ruff couldn't strip mid-step.
- **Files modified:** `backend/src/second_brain/api/eval.py` (full rewrite, +73 / -10 net)
- **Verification:** `uv run python -c "import second_brain.api.eval"` exits 0; imports survive auto-format.
- **Committed in:** `e498e0b` (Task 2 commit, bundled with runner.py).

**3. [Rule 2 - Critical functionality] Test fixture overhaul to match invoker shape**

- **Found during:** Task 2 pytest run after runner.py signature change.
- **Issue:** All 8 existing classifier/admin test cases passed `classifier_client=agent` / `admin_client=agent` with mocks whose `.get_response(messages=, options=)` was the side-effect driver. With the new `invoker:` parameter, every test broke with `TypeError: run_classifier_eval() got an unexpected keyword argument 'classifier_client'`.
- **Fix:** Rewrote `_make_classifier_agent_mock` / `_make_admin_agent_mock` as `_make_classifier_invoker_mock` / `_make_admin_invoker_mock` returning AsyncMocks with `invoke_classifier(input_text, tools_instance)` / `invoke_admin(...)` signatures. Inline fakes for timeout / progress / retry tests rewritten with the same signature. Test semantics (success/failure/empty/timeout/rate-limit-retry/rate-limit-exhaust/top-level-exception) are byte-for-byte preserved.
- **Files modified:** `backend/tests/test_eval.py` (8 sites updated)
- **Verification:** `uv run pytest tests/test_eval.py -x` -> 19/19 passed. Broader sweep across test_eval_dry_run.py + test_eval_metrics.py + test_foundry_eval.py + test_admin_handoff.py -> 71/71 passed.
- **Committed in:** `e498e0b` (Task 2 commit).

**4. [Rule 3 - Blocking] tools/investigation.py module-level invoker imports got auto-format-stripped**

- **Found during:** Task 2 first Edit attempt to add `from second_brain.eval.invoker import ...` at module top.
- **Issue:** Auto-format stripped the unused imports between Edits because the helper method using them hadn't been added yet.
- **Fix:** Moved the invoker imports INSIDE `_build_eval_invoker()` method body as local imports. Same name resolution, but auto-format can't strip them because the usage is in the same code block. This established the auto-format-safe pattern for migration-temporary symbols.
- **Files modified:** `backend/src/second_brain/tools/investigation.py` (lines 117-145, helper method)
- **Verification:** `uv run python -c "from second_brain.tools.investigation import InvestigationTools; t = InvestigationTools(logs_client=None, workspace_id='x'); print(hasattr(t, '_admin_agent'), hasattr(t, '_build_eval_invoker'))"` returns `True True`.
- **Committed in:** `e498e0b` (Task 2 commit).

**5. [Rule 2 - Critical functionality] main.py wiring of admin_agent to InvestigationTools**

- **Found during:** Task 2 - tools/investigation.py now accepts `admin_agent=` __init__ parameter (Rule 2 - critical functionality to actually use the GA admin agent in the pipeline). The lifespan didn't pass it.
- **Issue:** InvestigationTools would always see `admin_agent=None` so the GA path of the hybrid would never fire on production captures.
- **Fix:** Added `admin_agent=getattr(app.state, "admin_agent", None)` to the InvestigationTools(...) call in main.py lifespan with an inline comment explaining the 24-12 migration semantics.
- **Files modified:** `backend/src/second_brain/main.py` (line ~735, 5 lines added)
- **Verification:** AST scan still detects RC imports in main.py (expected per 24-19 plan); the change is additive only.
- **Committed in:** `e498e0b` (Task 2 commit).

---

**Total deviations:** 5 auto-fixed (1 lint reformatting + 2 auto-format-stripping workarounds + 1 test-suite migration + 1 critical wiring follow-on). No Rule 4 architectural changes. No scope expansion - all five deviations are within the natural scope of "introduce facade + wire through pipeline" + the plan-checker-acceptable subset of caller updates.

## Authentication Gates

None encountered. Plan validation is via import smoke + ruff + the test suite, none of which require Azure connectivity.

## Known Stubs

None. All data sources are wired:

- `app.state.classifier_client` (RC AzureAIAgentClient) - set by main.py lifespan, used by RCEvalAgentInvoker
- `app.state.admin_agent` (GA agent_framework.Agent) - set by 24-09 lifespan, used by GAEvalAgentInvoker
- The 6 tools on the admin agent + the file_capture tool on the classifier path are pre-registered or per-call-bound via `agent.run(tools=[...])`
- Side-effect contracts on EvalClassifierTools / DryRunAdminTools are exercised by the runner.py post-invocation reads

## Threat Flags

None - this plan does not introduce new network endpoints, auth paths, file access patterns, or trust-boundary changes. The invocation path that used to hit `classifier_client.get_response(...)` now hits `invoker.invoke_classifier(...)` which (via RCEvalAgentInvoker) hits the same `classifier_client.get_response(...)` call internally. Network surface unchanged. Cosmos write paths (EvalResults container) unchanged. Side-effect contracts on the dry-run tools unchanged.

## TDD Gate Compliance

This plan has `type: execute` in its frontmatter (not `type: tdd`), so the RED/GREEN/REFACTOR gate sequence does not apply. The plan's verification model is acceptance-grep + smoke imports + existing test suite re-pass, all of which are green.

## Verification Snapshot (post-execution)

```
=== Task 1 (invoker.py) ===
[OK] all 4 classes importable (EvalAgentInvoker, GAEvalAgentInvoker, RCEvalAgentInvoker, _MigrationHybridInvoker)
[OK] Protocol present
[OK] GA class present
[OK] RC class present
[OK] Hybrid in invoker.py
[OK] Hybrid NOT in runner.py
[OK] D-07 EXPLICIT JUSTIFICATION block inline
[OK] Deletion trigger: end of plan 24-18 documented
[OK] tool_choice="required" on GA classifier path

=== Task 2 (runner.py) ===
[OK] from second_brain.eval.invoker import EvalAgentInvoker
[OK] invoker.invoke_classifier call site
[OK] invoker.invoke_admin call site
[OK] no classifier_client.get_response
[OK] no admin_client.get_response

=== Task 3 (foundry.py) ===
[OK] no client.get_response
[OK] no hasattr(msg, "tool_calls") duck-typed extraction
[OK] invoker calls present
[OK] no top-level from agent_framework import ChatOptions, Message

=== Lint ===
uv run ruff check src/second_brain/eval/ src/second_brain/api/eval.py src/second_brain/tools/investigation.py src/second_brain/main.py: All checks passed!

=== Module imports ===
import second_brain.eval.invoker -> OK
import second_brain.eval.runner -> OK
import second_brain.eval.foundry -> OK
import second_brain.api.eval -> OK
import second_brain.tools.investigation -> OK

=== Test suite ===
tests/test_eval.py: 19 passed
tests/test_eval_dry_run.py + test_eval_metrics.py + test_foundry_eval.py: 36 passed
tests/test_admin_handoff.py + test_admin_integration.py + test_admin_task_tools.py + test_admin_tools.py: 53 passed + 1 skipped
Cumulative: 106 passed + 1 skipped

=== Phase 24 invariant tests ===
test_no_rc_imports_after_cleanup.py: still RED (expected). Offender file count 5:
  - second_brain/agents/classifier.py (cleared in 24-14)
  - second_brain/eval/invoker.py (cleared in 24-18 when RCEvalAgentInvoker deleted)
  - second_brain/main.py (cleared in 24-14/24-19)
  - second_brain/streaming/adapter.py (cleared in 24-14)
  - second_brain/warmup.py (cleared in 24-19)
  Net change: eval/runner.py removed from offender list, eval/invoker.py added in its place. Same count (5). Plan 24-18 deletes RCEvalAgentInvoker -> invoker.py drops off.
```

## Self-Check: PASSED

- `backend/src/second_brain/eval/invoker.py` - exists, 4 classes (Protocol + GA + RC + Hybrid), D-07 justification block inline, deletion trigger pinned
- `backend/src/second_brain/eval/runner.py` - exists, both call sites route through invoker, zero direct `client.get_response` calls
- `backend/src/second_brain/eval/foundry.py` - exists, `generate_app_mediated_dataset` routes through invoker, zero `hasattr(msg, "tool_calls")` duck-typed extraction, no top-level RC imports
- `backend/src/second_brain/api/eval.py` - exists, `_build_migration_invoker` helper wires hybrid at call-site
- `backend/src/second_brain/tools/investigation.py` - exists, new `admin_agent` param + `_build_eval_invoker()` helper
- `backend/src/second_brain/main.py` - exists, passes `admin_agent=` to InvestigationTools
- `backend/tests/test_eval.py` - exists, 19/19 tests pass against invoker-shaped mocks
- Commit `1cea788` - present in git log (Task 1)
- Commit `e498e0b` - present in git log (Task 2)
- Commit `c53eba7` - present in git log (Task 3)

## Next Phase Readiness

- **Plan 24-13 (Classifier kickoff):** unblocked - the gate suite can run with admin on GA + classifier on RC during the 23.2 migration window. The hybrid invoker hides the RC/GA split from `eval/runner.py`.
- **Plan 24-13.5 (admin golden seeding):** unblocked - the seed script + cases.yaml will drive `run_admin_eval(invoker=...)` via the same hybrid composition, so the pipeline executes against the GA admin agent immediately.
- **Plan 24-14 onwards (Classifier migration plans):** the pipeline absorbs the classifier migration without code changes inside `runner.py` or `foundry.py` - only the call-site needs to swap `RCEvalAgentInvoker` for `GAEvalAgentInvoker` constructors. When the last classifier migration commit lands, plan 24-18 collapses the hybrid + RC class together.
- **Plan 24-18 (RC cleanup):** single deletion target - drop `RCEvalAgentInvoker` + `_MigrationHybridInvoker` from `eval/invoker.py`, change the call-sites in `api/eval.py::_build_migration_invoker` and `tools/investigation.py::_build_eval_invoker` to construct plain `GAEvalAgentInvoker(classifier_agent=..., admin_agent=...)`, optionally rename or inline back into `runner.py`. The `TYPE_CHECKING` import of `AzureAIAgentClient` also goes; AST scan test_no_rc_imports_after_cleanup.py drops invoker.py from the offender list.
- **RC import offender list:** 5 distinct files - `agents/classifier.py` (cleared in 24-14), `eval/invoker.py` (cleared in 24-18), `main.py` (cleared in 24-14/24-19), `streaming/adapter.py` (cleared in 24-14), `warmup.py` (cleared in 24-19). Net change in this plan: `eval/runner.py` cleared, `eval/invoker.py` added; same count.
- **Pipeline shape (post-24-12):** `api/eval.py` or `tools/investigation.py` constructs `_MigrationHybridInvoker(rc, ga)` -> `runner.run_*_eval(invoker=...)` -> `invoker.invoke_*(input_text, tools_instance)` -> framework executes tools -> runner reads side effects on `tools_instance.last_*` / `captured_*` -> metrics computation -> Cosmos write. The shape is end-to-end GA-clean except for the RC implementation inside RCEvalAgentInvoker (deleted in 24-18).

---
*Phase: 24-foundry-ga-migration*
*Plan: 12*
*Completed: 2026-05-11*
