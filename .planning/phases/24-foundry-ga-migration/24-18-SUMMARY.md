---
phase: 24-foundry-ga-migration
plan: 18
subsystem: backend
tags: [foundry-ga, f-17, p1-3, evalagentinvoker, rceavlagentinvoker-deletion, forced-tool-failure, kql-template, d-04, 23.3-cleanup]

# Dependency graph
requires:
  - phase: 24-foundry-ga-migration/03
    provides: "agent_middleware/ package + legacy import survival red test (24-03)"
  - phase: 24-foundry-ga-migration/12
    provides: "EvalAgentInvoker facade with RCEvalAgentInvoker + _MigrationHybridInvoker (24-12) — the temporary seam this plan deletes"
  - phase: 24-foundry-ga-migration/16
    provides: "Classifier streaming GA + forced_tool_failure SSE sub-code wired (24-16) — emission points for the new KQL template"
  - phase: 24-foundry-ga-migration/17
    provides: "InboxDocument conversationHistory + dry_run_tools.py decorator strip (24-17)"
  - phase: 23-foundry-ga-prep/EVAL-INVENTORY.md
    provides: "EvalAgentInvoker deletion trigger spec + side-effect contract"
  - phase: 23-foundry-ga-prep/SPAN-NAME-MAPPING.md
    provides: "forced_tool_failure KQL tracking guidance + dotted-key bracket-access pattern"
provides:
  - "agents/middleware.py DELETED (F-17 cleared)"
  - "test_legacy_middleware_imports_survive.py UPDATED post-deletion (legacy-importable sub-test retired; 2 remaining sub-tests assert gone-file invariant + GA path)"
  - "RCEvalAgentInvoker + _MigrationHybridInvoker classes DELETED from eval/invoker.py"
  - "AzureAIAgentClient TYPE_CHECKING import DELETED from eval/invoker.py (eval/ no longer in RC AST-scan offender list)"
  - "GA-only eval pipeline: api/eval.py + tools/investigation.py construct plain GAEvalAgentInvoker(classifier_agent=..., admin_agent=...) directly"
  - "InvestigationTools constructor: classifier_client + admin_client params DROPPED; classifier_agent added"
  - "FORCED_TOOL_FAILURE_COUNT KQL template (D-04 post-deploy monitoring gate)"
affects:
  - "24-19 (warmup + main.py GA migration: remaining AzureAIAgentClient references in main.py + warmup.py are the only RC AST-scan offenders left)"
  - "24-19.5 (RC dep removal: zero RC source imports under eval/ post-24-18)"
  - "24-20 (cumulative pre-deploy audit: RC AST-scan offender count 4 → 2)"
  - "24-22 (deploy: FORCED_TOOL_FAILURE_COUNT template available for post-deploy 7-day gate)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Final 23.3 cleanup pattern: delete the temporary 24-12 migration seam in a single plan once both sides are GA. Single deletion target per CONTEXT D-04 + EVAL-INVENTORY deletion trigger."
    - "W-03 partial cleanup: dead-code _make_*_client warmup factory bodies in main.py keep their AzureAIAgentClient shape (full sweep is 24-19 scope) but the legacy AuditAgentMiddleware/ToolTimingMiddleware refs swapped to CaptureTraceAgentMiddleware/CaptureTraceFunctionMiddleware so main.py stays importable after middleware.py deletion."
    - "KQL bracket-access for dotted property keys: Properties.[\"capture.outcome\"] (mandatory when the key name contains a dot; dot-access fails)."
    - "FORCED_TOOL_FAILURE_COUNT unions AppTraces + AppExceptions because the streaming adapter emits via both logger.warning (SeverityLevel=2, AppTraces) and logger.error(exc_info=True) (SeverityLevel=3, both AppTraces and AppExceptions). SeverityLevel >= 2 filter ensures both shapes contribute."
    - "Post-24-18 InvestigationTools shape: dependency injection of GA Agent singletons (classifier_agent, admin_agent) only; RC client handles are gone from the surface."

key-files:
  created:
    - .planning/phases/24-foundry-ga-migration/24-18-SUMMARY.md
  modified:
    - backend/src/second_brain/agents/middleware.py
    - backend/src/second_brain/eval/invoker.py
    - backend/src/second_brain/eval/runner.py
    - backend/src/second_brain/api/eval.py
    - backend/src/second_brain/tools/investigation.py
    - backend/src/second_brain/main.py
    - backend/src/second_brain/observability/kql_templates.py
    - backend/tests/test_legacy_middleware_imports_survive.py
    - backend/tests/test_observability.py
    - backend/tests/test_eval.py
  deleted:
    - backend/src/second_brain/agents/middleware.py

key-decisions:
  - "Optional P1-3 polish (rename agents/agent_middleware/ → agents/middleware/) DEFERRED. The plan explicitly allowed the operator to skip this; the agent_middleware/ name is acceptable as a permanent location. Keeps the diff small."
  - "Optional GA invoker rename (GAEvalAgentInvoker → EvalAgentInvoker single concrete class + drop Protocol) DEFERRED for the same diff-size reason. The plan explicitly noted this as optional."
  - "Bundled main.py cleanup with Task 1 (Rule 2 critical functionality + Rule 3 blocking). Plan task 1 said 'delete the file' but main.py still imports + uses AuditAgentMiddleware/ToolTimingMiddleware at module level. Without the import removal, main.py would fail at module load. Plan action step 2 covers test files but not main.py — same principle applies."
  - "W-03 dead-code factories (_make_classifier_client / _make_admin_client / _make_investigation_client) kept verbatim. Their middleware= lists swapped to the GA Capture* classes so the import resolves. Full _make_* cluster + AzureAIAgentClient sweep is 24-19's scope per CONTEXT D-13 / W-03-23.2."
  - "InvestigationTools constructor surface cleaned: classifier_client + admin_client params REMOVED entirely (not deprecated with stubs). The 24-12 hybrid is gone, no transitional shape needed."
  - "test_observability.py's 2 parameterized-middleware tests DELETED rather than rewritten. They tested RC AuditAgentMiddleware behavior (_span_name == 'classifier_agent_run'); GA CaptureTraceAgentMiddleware doesn't take agent_name nor expose _span_name. Coverage of the GA middleware lives in tests/test_agent_middleware_capture_trace.py (added in 24-03)."
  - "FORCED_TOOL_FAILURE_COUNT filters on Properties.[\"capture.outcome\"] (not Properties.sub_code as the plan's example suggested). Reason: the adapter logs structured extra={..., 'capture.outcome': 'forced_tool_failure'} — sub_code lives only in the SSE wire payload, not in the App Insights log Properties dict."
  - "FORCED_TOOL_FAILURE_COUNT unions AppTraces AND AppExceptions because the adapter emits at TWO severity tiers: SeverityLevel=2 (logger.warning for the empty-result branch) AND SeverityLevel=3 (logger.error with exc_info=True for the exception branch). Single-table queries would miss one or the other."
  - "FORCED_TOOL_FAILURE_COUNT ships as TEMPLATE ONLY; no query_*() helper in queries.py per plan's Task 4 action step 5. The corresponding helper + post-deploy 7-day gate land in a follow-up plan when monitoring needs are clearer."

requirements-completed: [F-17, F-06, D-04, D-12, P1-3]

# Metrics
duration: 9min
completed: 2026-05-11
---

# Phase 24 Plan 18: End-of-23.3 cleanup commit — Summary

**Final 23.3 cleanup: deleted agents/middleware.py (F-17), deleted RCEvalAgentInvoker + _MigrationHybridInvoker from eval/invoker.py (EVAL-INVENTORY deletion trigger), routed eval pipeline through GAEvalAgentInvoker directly, added FORCED_TOOL_FAILURE_COUNT KQL template, and retired the P1-3 legacy-importable sub-test.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-05-11T05:47:37Z
- **Completed:** 2026-05-11T05:56:05Z
- **Tasks:** 4
- **Files modified:** 9 (+ 1 deleted)
- **Files created:** 1 (this SUMMARY)

## Accomplishments

### F-17 cleared (Task 1)

- `backend/src/second_brain/agents/middleware.py` DELETED via `git rm`. Replaced by `agents/agent_middleware/capture_trace.py` in 24-03, wired into all 3 agents in 24-04 (Investigation), 24-09 (Admin), 24-14 (Classifier).
- `main.py` cleaned: removed the `AuditAgentMiddleware` / `ToolTimingMiddleware` import block at the top. Three dead-code `_make_*_client` warmup factory bodies (W-03) had their `middleware=[...]` lists swapped to use `CaptureTraceAgentMiddleware()` / `CaptureTraceFunctionMiddleware()` so the file stays importable post-deletion. Full factory cluster sweep is 24-19's scope per CONTEXT D-13.
- `test_observability.py` cleaned: the 2 parameterized-middleware tests (`test_parameterized_middleware_sets_distinct_span_names`, `test_parameterized_middleware_default_is_classifier`) deleted because they tested the RC `AuditAgentMiddleware._span_name` shape that no longer exists. Module docstring updated to reflect the GA middleware test file (`tests/test_agent_middleware_capture_trace.py`).
- Verified zero source-side references to `AuditAgentMiddleware` / `ToolTimingMiddleware` post-deletion via grep + AST scan. No shadowing package at `agents/middleware/`.

### P1-3 red test updated post-deletion (Task 2)

- `tests/test_legacy_middleware_imports_survive.py` reduced from 3 sub-tests (legacy importable + GA path + no shadowing) to 2 sub-tests:
  - **KEPT:** `test_new_ga_middleware_imports_at_distinct_path` — regression guard for the `agent_middleware/` package path.
  - **RETIRED:** `test_legacy_agents_middleware_module_still_importable` — the legacy module no longer exists post-24-18. The 24-03 docstring specifically anticipated this retirement: "After 24-18 deletes the legacy module, this test will fail — that's the trigger to retire the test."
  - **RENAMED:** `test_no_package_shadowing` → `test_legacy_middleware_module_is_gone`. New assertion: NEITHER a file at `agents/middleware.py` NOR a directory at `agents/middleware/` exists.
- Module docstring rewritten to reflect post-24-18 invariants.
- 2/2 remaining sub-tests pass.

### RCEvalAgentInvoker + _MigrationHybridInvoker deleted (Task 3)

EVAL-INVENTORY deletion trigger discharged. The 24-12 temporary migration seam is gone.

- `eval/invoker.py`:
  - DELETED `class RCEvalAgentInvoker:` (was 56 lines)
  - DELETED `class _MigrationHybridInvoker:` (was 35 lines)
  - DELETED the `TYPE_CHECKING` import `from agent_framework.azure import AzureAIAgentClient` (no longer needed; was only used by RC class typing)
  - KEPT: `class EvalAgentInvoker(Protocol):` + `class GAEvalAgentInvoker:`. The Protocol stays because the eval runner types its parameter against it and the test suite mocks it directly.
  - Module docstring rewritten to reflect post-24-18 GA-only state.
- `eval/runner.py`: Module docstring + 2 invoker= param docstrings rewritten to reflect post-24-18 state. Code body unchanged (already typed as Protocol, no signature change).
- `api/eval.py`:
  - DELETED `_build_migration_invoker` helper.
  - ADDED `_build_eval_invoker(classifier_agent, admin_agent) -> GAEvalAgentInvoker` helper. Constructs the GA invoker directly.
  - Route handlers (POST /api/eval/run classifier + admin branches) read `app.state.classifier_agent` (not `classifier_client`) and `app.state.admin_agent` (not `admin_client`). The 4 `getattr(request.app.state, "classifier_client", None)` / `getattr(..., "admin_client", None)` reads are replaced.
  - Imports cleaned: only `GAEvalAgentInvoker` imported; `RCEvalAgentInvoker` + `_MigrationHybridInvoker` imports removed.
  - Module docstring updated.
- `tools/investigation.py`:
  - `InvestigationTools.__init__` parameters: DROPPED `classifier_client` + `admin_client`. ADDED `classifier_agent`. KEPT `admin_agent`.
  - `_build_eval_invoker()` rewritten to return a plain `GAEvalAgentInvoker(classifier_agent=..., admin_agent=...)` (no more local imports of `RCEvalAgentInvoker` / `_MigrationHybridInvoker` — the auto-format-safe pattern from 24-12 is no longer needed because there's only ONE class to import).
  - `run_classifier_eval` guard updated: `if self._classifier_agent is None` (was `self._classifier_client is None`).
  - `run_admin_eval` guard simplified: `if self._admin_agent is None` (was `if self._admin_agent is None and self._admin_client is None`).
- `main.py`: `InvestigationTools(...)` constructor call updated to pass `classifier_agent` + `admin_agent` from `app.state` (using `getattr(app.state, "classifier_agent", None)` / `getattr(app.state, "admin_agent", None)`). The legacy `classifier_client=` + `admin_client=` kwargs removed.
- `tests/test_eval.py`:
  - `eval_app` fixture: `app.state.classifier_agent = AsyncMock()` + `app.state.admin_agent = AsyncMock()` (replaces `classifier_client` + `admin_client`).
  - `investigation_tools_with_eval` fixture: constructor kwargs `classifier_agent` + `admin_agent` (replaces `classifier_client` + `admin_client`).
  - `test_investigation_run_classifier_eval_no_client` renamed to `test_investigation_run_classifier_eval_no_agent`; constructor kwarg + assertions updated.
- 19/19 tests in `test_eval.py` pass post-cleanup.

### FORCED_TOOL_FAILURE_COUNT KQL template added (Task 4)

Per SPAN-NAME-MAPPING.md Section "Task group 23.3" + CONTEXT D-04:

- Added `FORCED_TOOL_FAILURE_COUNT` constant to `kql_templates.py` (47 lines including doc comment).
- Filter: `tostring(Properties.["capture.outcome"]) == "forced_tool_failure"` (bracket access because the property key has a dot).
- Source union: `(AppTraces | where SeverityLevel >= 2)` UNION `AppExceptions`. Covers BOTH adapter emission shapes — `logger.warning` (SeverityLevel=2, the empty-result branch) and `logger.error(exc_info=True)` (SeverityLevel=3, the exception branch; lands on AppExceptions too).
- Parameterised with single `{lookback}` (KQL duration literal, e.g. `"24h"`, `"7d"`).
- Output: `summarize count_ = count() by bin(timestamp, 1h), ItemType` — hourly trend, separated by Log vs Exception.
- NO corresponding `query_*()` function in `queries.py` (plan's explicit choice; post-deploy monitoring helper lands in a follow-up plan).

## Task Commits

| Task | Hash      | Title                                                                                       |
|------|-----------|---------------------------------------------------------------------------------------------|
| 1    | `1b93734` | chore(24-18): delete legacy agents/middleware.py (F-17 cleared)                             |
| 2    | `a9900d6` | test(24-18): retire legacy-importable sub-test (P1-3 post-deletion update)                  |
| 3    | `0f908b9` | feat(24-18): delete RCEvalAgentInvoker + _MigrationHybridInvoker; eval flows GA-only        |
| 4    | `255ef46` | feat(24-18): add FORCED_TOOL_FAILURE_COUNT KQL template (D-04 monitoring)                   |

(Plan metadata commit follows this SUMMARY.)

## Files Created/Modified

| Path | Change | Notes |
|------|--------|-------|
| `backend/src/second_brain/agents/middleware.py` | **DELETED** | F-17 cleared. Was 105 lines (AuditAgentMiddleware + ToolTimingMiddleware). |
| `backend/src/second_brain/main.py` | modified (-9 / +18) | Removed legacy middleware import block. Three dead-code _make_*_client factories: middleware=[...] lists swapped to GA path + W-03 inline comments. InvestigationTools call updated to pass classifier_agent + admin_agent. |
| `backend/src/second_brain/eval/invoker.py` | modified (-105 / +35) | DELETED RCEvalAgentInvoker + _MigrationHybridInvoker classes + AzureAIAgentClient TYPE_CHECKING import. Kept Protocol + GAEvalAgentInvoker. Docstring rewritten. |
| `backend/src/second_brain/eval/runner.py` | modified (+7 / -16) | Module docstring + 2 invoker= param docstrings updated to reflect GA-only state. Code unchanged. |
| `backend/src/second_brain/api/eval.py` | modified (-37 / +29) | _build_migration_invoker -> _build_eval_invoker (single GA factory). Route handlers read classifier_agent / admin_agent (not _client). Imports cleaned. |
| `backend/src/second_brain/tools/investigation.py` | modified (-25 / +20) | Constructor: classifier_client + admin_client params dropped; classifier_agent added. _build_eval_invoker rewritten to return plain GAEvalAgentInvoker. Two guards updated. |
| `backend/src/second_brain/observability/kql_templates.py` | modified (+47) | FORCED_TOOL_FAILURE_COUNT template added. |
| `backend/tests/test_legacy_middleware_imports_survive.py` | modified (-38 / +23) | 3 sub-tests -> 2. Module docstring rewritten. |
| `backend/tests/test_observability.py` | modified (-31 / +9) | Deleted 2 parameterized-middleware tests + AuditAgentMiddleware import. Module docstring updated. |
| `backend/tests/test_eval.py` | modified (-9 / +14) | eval_app + investigation_tools_with_eval fixtures updated (classifier_agent / admin_agent). One test renamed (_no_client -> _no_agent). |
| `.planning/phases/24-foundry-ga-migration/24-18-SUMMARY.md` | **CREATED** | This file. |

## Decisions Made

1. **Optional P1-3 polish DEFERRED** — the plan explicitly allowed the operator to skip renaming `agents/agent_middleware/` → `agents/middleware/`. Kept the diff small. The `agent_middleware/` name is acceptable as a permanent location.

2. **Optional GA invoker rename DEFERRED** — the plan explicitly allowed skipping `GAEvalAgentInvoker` → `EvalAgentInvoker` single-concrete-class rename. Same diff-size argument.

3. **Bundled main.py cleanup with Task 1 (Rule 2 + Rule 3)** — the plan task said "delete the file" but `main.py` still imported the legacy classes at module level. Without removing those imports, main.py would fail to load. Plan action step 2 covers test files; same principle applies to main.py. Documented as a deviation below.

4. **W-03 dead-code factories kept verbatim with middleware swap** — the three `_make_*_client` warmup factory bodies survive this plan because they are 24-19's scope per CONTEXT D-13 / W-03-23.2. Their `middleware=[...]` lists swapped to the GA `Capture*` classes so the symbols resolve. Inline comments added pointing to 24-19.

5. **InvestigationTools constructor surface cleaned to GA-only** — the 24-12 hybrid is gone, so there's no transitional shape needed. Dropped `classifier_client` + `admin_client` constructor params entirely (no deprecation stub). Tests updated to match.

6. **test_observability.py's 2 parameterized-middleware tests DELETED, not rewritten** — they tested RC `AuditAgentMiddleware._span_name == "classifier_agent_run"` shape; GA `CaptureTraceAgentMiddleware` doesn't take `agent_name` and doesn't expose `_span_name`. Coverage of the GA middleware already lives in `tests/test_agent_middleware_capture_trace.py` (added in 24-03).

7. **FORCED_TOOL_FAILURE_COUNT filters on `Properties.["capture.outcome"]`** (not `Properties.sub_code` as the plan's example suggested). The adapter logs `extra={..., "capture.outcome": "forced_tool_failure"}`. `sub_code` lives only in the SSE wire payload, not in the App Insights `Properties` dict.

8. **KQL template unions AppTraces AND AppExceptions** — the adapter emits via `logger.warning` (the empty-result branch, SeverityLevel=2, lands on AppTraces) AND `logger.error(exc_info=True)` (the exception branch, SeverityLevel=3, lands on AppTraces AND AppExceptions). Single-table queries would miss the warning-level emissions. SeverityLevel >= 2 floor ensures both shapes contribute.

9. **KQL template ships without a `query_*()` helper** — plan's Task 4 action step 5 explicitly says: "Do NOT add a corresponding `query_*` function in queries.py for now — the template is the gate; the query function can be added post-deploy when monitoring needs are clearer (or as a follow-up plan)."

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 + Rule 3 - Critical functionality + Blocking] Bundled main.py + test_observability.py cleanup into Task 1**

- **Found during:** Task 1 pre-flight grep
- **Issue:** Plan Task 1 action step 1 says "confirm zero references" before deleting `agents/middleware.py`. Grep found `main.py:53-56` (import block) and `main.py:829, 830, 846, 847, 861, 862` (factory body usages) PLUS `test_observability.py:16, 27, 28, 29, 43` (active unit tests). Without fixing the callers, `main.py` would crash at module load post-deletion.
- **Fix:** Bundled three changes into Task 1's commit (`1b93734`):
  - main.py import block removed
  - main.py factory `middleware=[...]` lists swapped to `CaptureTraceAgentMiddleware` / `CaptureTraceFunctionMiddleware` (full W-03 sweep stays in 24-19)
  - test_observability.py: deleted 2 RC-shape tests + the legacy import
- **Files modified:** `backend/src/second_brain/main.py`, `backend/tests/test_observability.py` (in addition to the planned `git rm` on `agents/middleware.py`).
- **Verification:** `grep "AuditAgentMiddleware\|ToolTimingMiddleware" backend/src/second_brain/main.py` returns 0; `cd backend && uv run python -c "from second_brain.agents.middleware import AuditAgentMiddleware"` raises `ModuleNotFoundError` (expected).
- **Committed in:** `1b93734` (Task 1)

**2. [Rule 1 + Rule 3 - Bug + Blocking] api/eval.py route handlers were reading the wrong app.state attribute**

- **Found during:** Task 3 plan review
- **Issue:** Post-24-14 `app.state.classifier_client` is permanently `None` (see main.py:621). After this plan deletes the hybrid invoker, the classifier eval path in api/eval.py would always hit the `if classifier_client is None: raise HTTPException(503)` guard and never run. The route was reading the wrong attribute name for the GA-only state.
- **Fix:** Route handlers now read `app.state.classifier_agent` (the GA Agent built by 24-14, exists at line 612 in main.py). Symmetric: the admin path now reads `app.state.admin_agent` only (the existing `getattr(..., "admin_agent", None)` reads were already correct; removed parallel `classifier_client` reads).
- **Files modified:** `backend/src/second_brain/api/eval.py` (lines 110-150 of the rewrite)
- **Verification:** Test fixture `eval_app` now seeds `app.state.classifier_agent = AsyncMock()` + `app.state.admin_agent = AsyncMock()`; `test_eval_run_returns_202` passes.
- **Committed in:** `0f908b9` (Task 3)

---

**Total deviations:** 2 auto-fixed (1 bundled cleanup + 1 wrong-attribute bug).
**Impact on plan:** Both deviations within natural scope of "delete the temporary migration seam + final cleanup commit." Deviation #1 was implied by plan action step 1 (the grep finds the offenders; the plan presumes the executor will fix them). Deviation #2 fixes a pre-existing latent bug exposed by the cleanup.

## Authentication Gates

None encountered. All verification ran locally:

- `git rm` for the deletion
- `grep` / `! grep -q` for acceptance criteria
- `uv run python -c "..."` for import smoke tests
- `uv run ruff check` for lint
- `uv run pytest` for the test suite

## Known Stubs

None. All affected paths are wired:

- `agents/agent_middleware/capture_trace.py` (24-03) is still the GA middleware, imported and used by all 3 agents (24-04, 24-09, 24-14) and the dead-code W-03 factories now (after this plan).
- `GAEvalAgentInvoker` is the single concrete class consumed by both `api/eval.py::_build_eval_invoker` and `tools/investigation.py::_build_eval_invoker`.
- `FORCED_TOOL_FAILURE_COUNT` template is read-ready; the corresponding `query_*` helper is plan-deferred (not a stub of this plan).
- `main.py` `app.state.classifier_client = None` and `app.state.classifier_client = None` short-circuits remain — they're mid-migration safe-defaults per CONTEXT D-13 + W-03-23.2 (24-19 scope).

## Threat Flags

None — this plan does not introduce new network endpoints, auth paths, file access patterns, or trust-boundary changes.

- Source code DELETIONS (legacy middleware + RC invoker classes) reduce attack surface.
- `app.state.classifier_agent` / `app.state.admin_agent` are the GA singletons already published in main.py lifespan (24-09, 24-14) — no new app.state attribute introduced.
- The KQL template only reads telemetry; no write surface.
- InvestigationTools constructor change drops two RC client handles from the dependency-injection surface; no new sensitive inputs.

## TDD Gate Compliance

Plan type is `execute` (not `tdd`). No RED/GREEN commits required. The 4 tasks each landed as a single feat/chore/test commit with verification gates per the plan's `<verify>` blocks.

## Verification Snapshot

### Task 1 (F-17)

| Criterion | Status |
|-----------|--------|
| `! test -f backend/src/second_brain/agents/middleware.py` | PASS (file deleted) |
| `! test -d backend/src/second_brain/agents/middleware` | PASS (no shadowing package) |
| `! grep -q "AuditAgentMiddleware\|ToolTimingMiddleware" backend/src/second_brain/main.py` | PASS (0 matches) |
| `! grep -q "from second_brain.agents.middleware" backend/src/second_brain/` | PASS (0 matches) |
| `from second_brain.agents.agent_middleware.capture_trace import CaptureTraceAgentMiddleware` succeeds | PASS |
| `from second_brain.agents.middleware import AuditAgentMiddleware` raises ImportError | PASS |
| `test_observability.py` legacy mw import removed | PASS |

### Task 2 (P1-3 red test update)

| Criterion | Status |
|-----------|--------|
| `! grep -q "test_legacy_agents_middleware_module_still_importable" tests/test_legacy_middleware_imports_survive.py` | PASS (retired) |
| `grep -q "test_new_ga_middleware_imports_at_distinct_path" tests/test_legacy_middleware_imports_survive.py` | PASS |
| `grep -q "test_legacy_middleware_module_is_gone" tests/test_legacy_middleware_imports_survive.py` | PASS |
| `cd backend && uv run pytest tests/test_legacy_middleware_imports_survive.py -x` | PASS (2/2) |

### Task 3 (RC invoker + hybrid deletion)

| Criterion | Status |
|-----------|--------|
| `! grep -q "class RCEvalAgentInvoker" backend/src/second_brain/eval/invoker.py` | PASS |
| `! grep -q "class _MigrationHybridInvoker" backend/src/second_brain/eval/invoker.py` | PASS |
| `! grep -rq "RCEvalAgentInvoker" backend/src/` (excluding docstrings) | PASS (only docstring narrative remains) |
| `! grep -rq "_MigrationHybridInvoker" backend/src/` (excluding docstrings) | PASS (only docstring narrative remains) |
| `grep -q "class GAEvalAgentInvoker" backend/src/second_brain/eval/invoker.py` | PASS |
| `grep -q "class EvalAgentInvoker(Protocol)" backend/src/second_brain/eval/invoker.py` | PASS |
| `! grep -E "^from agent_framework\.azure\\|AzureAIAgentClient" backend/src/second_brain/eval/invoker.py \| grep -v "^#" \| grep -v "^- "` | PASS (only docstring narrative remains) |
| `from second_brain.eval.invoker import EvalAgentInvoker, GAEvalAgentInvoker` succeeds | PASS |
| `hasattr(invoker_module, 'RCEvalAgentInvoker')` is False | PASS |
| `hasattr(invoker_module, '_MigrationHybridInvoker')` is False | PASS |
| InvestigationTools params == `['self', 'logs_client', 'workspace_id', 'cosmos_manager', 'classifier_agent', 'admin_agent']` | PASS |
| `! hasattr(api_eval_module, '_build_migration_invoker')` | PASS |
| `hasattr(api_eval_module, '_build_eval_invoker')` | PASS |
| `ruff check src/second_brain/eval/ + api/eval.py + tools/investigation.py` | PASS |

### Task 4 (FORCED_TOOL_FAILURE_COUNT)

| Criterion | Status |
|-----------|--------|
| `grep -q "FORCED_TOOL_FAILURE_COUNT" backend/src/second_brain/observability/kql_templates.py` | PASS |
| `grep -q 'forced_tool_failure' backend/src/second_brain/observability/kql_templates.py` | PASS |
| `grep -q 'tostring(Properties.\["capture.outcome"\]) == "forced_tool_failure"'` | PASS |
| `from second_brain.observability.kql_templates import FORCED_TOOL_FAILURE_COUNT` succeeds | PASS |
| Template renders with `{lookback}` via str.format | PASS |
| `ruff check src/second_brain/observability/kql_templates.py` | PASS |

### Cross-cutting test suite

```
tests/test_eval.py                                  19 passed
tests/test_eval_dry_run.py                          11 passed
tests/test_eval_metrics.py                           7 passed
tests/test_foundry_eval.py                          15 passed
tests/test_legacy_middleware_imports_survive.py      2 passed
tests/test_foundry_credential_shape.py               2 passed
tests/test_inbox_dual_read.py                        7 passed
                                                   ----------
                                                    63 passed total
```

### AST scan red test (test_no_rc_imports_after_cleanup.py)

```
$ uv run pytest tests/test_no_rc_imports_after_cleanup.py
1 failed (expected RED until 24-19). Offender list (2 files):
  - second_brain/main.py    (imports + references AzureAIAgentClient — 24-19 scope)
  - second_brain/warmup.py  (imports + references AzureAIAgentClient — 24-19 scope)
```

**Offender count: 4 → 2.** This plan cleared `eval/invoker.py` from the list (deleted the `AzureAIAgentClient` TYPE_CHECKING import). The remaining 2 offenders are both 24-19's scope (W-03 dead-code factory cluster + warmup loop migration).

## Out-of-Scope Discoveries

- **`test_observability.py` cannot collect** because it imports `from second_brain.warmup import MAX_CONSECUTIVE_FAILURES, agent_warmup_loop` and `warmup.py:8` does `from agent_framework.azure import AzureAIAgentClient` which fails post-Phase-23-strict-cutover. This is the D-13 strict-cutover state for `warmup.py`. Pre-existing (already broken in 24-15/24-16/24-17; not introduced by this plan). 24-19 scope.
- **`mcp/uv.lock`** shows uncommitted modification on disk (pre-existing on `main`, not touched by this plan). Per SCOPE BOUNDARY, not investigated. Same state as 24-15 / 24-16 / 24-17 SUMMARYs documented.

## Next Phase Readiness

- **Plan 24-19 (warmup + main.py GA migration):** unblocked. The plan's scope is now narrowed to:
  - `main.py`: strip the remaining `AzureAIAgentClient` import (line 33) + delete the 3 dead-code `_make_*_client` factories + `warmup_factories` + `_on_recreate` + `warmup_clients` list construction + `app.state.classifier_client = None` / `admin_client = None` / `investigation_client = None` short-circuits.
  - `warmup.py`: rewrite to use GA agents via `Agent.run()` health probes (or delete the warmup loop entirely if the GA Agent singletons don't need pinging).
- **Plan 24-19.5 (RC dep removal):** prerequisite is AST scan red test GREEN. Currently 2 offenders remain (main.py + warmup.py). Plan 24-19 should flip the test green; 24-19.5 then removes `agent-framework-azure-ai` from `pyproject.toml`.
- **Plan 24-20 (cumulative pre-deploy audit):** the cumulative diff for 24-09..24-18 should produce zero ❌ at the auditor (per plan's success criteria). The 4 warnings carried forward from 23.2 (W-01, W-02-23.2, W-03-23.2, W-04-23.2) get resolved:
  - W-01 — permanent retention (CaptureTraceSpanProcessor), no change.
  - W-02-23.2 — admin Content.name/function_name defensive read, no change (empirical verification deferred to post-deploy).
  - **W-03-23.2 — STILL OPEN.** Half-cleaned in this plan (middleware swap to GA path) but full `_make_*_client` sweep is 24-19.
  - **W-04-23.2 — RESOLVED by this plan.** `RCEvalAgentInvoker` deleted along with the `AzureAIAgentClient` TYPE_CHECKING import.
- **Plan 24-22 (deploy):** `FORCED_TOOL_FAILURE_COUNT` template is available. Post-deploy 7-day monitoring gate (per CONTEXT) can use this query directly via `LogsQueryClient.query_workspace(query=FORCED_TOOL_FAILURE_COUNT.format(lookback="7d"), ...)` once the helper function lands in a follow-up plan.

## Self-Check: PASSED

**Files claimed modified:**

- [x] DELETED: `backend/src/second_brain/agents/middleware.py` (git rm)
- [x] MODIFIED: `backend/src/second_brain/main.py` (legacy mw import removed; 3 factory middleware= swapped; InvestigationTools call updated)
- [x] MODIFIED: `backend/src/second_brain/eval/invoker.py` (RC + Hybrid classes deleted; AzureAIAgentClient TYPE_CHECKING removed)
- [x] MODIFIED: `backend/src/second_brain/eval/runner.py` (docstrings updated to post-24-18 GA-only state)
- [x] MODIFIED: `backend/src/second_brain/api/eval.py` (_build_migration_invoker -> _build_eval_invoker; reads classifier_agent / admin_agent)
- [x] MODIFIED: `backend/src/second_brain/tools/investigation.py` (constructor params reshaped; _build_eval_invoker returns plain GAEvalAgentInvoker; 2 guards updated)
- [x] MODIFIED: `backend/src/second_brain/observability/kql_templates.py` (FORCED_TOOL_FAILURE_COUNT added)
- [x] MODIFIED: `backend/tests/test_legacy_middleware_imports_survive.py` (3 -> 2 sub-tests; module docstring rewritten)
- [x] MODIFIED: `backend/tests/test_observability.py` (2 RC-shape tests removed; legacy mw import removed; module docstring updated)
- [x] MODIFIED: `backend/tests/test_eval.py` (eval_app + investigation_tools_with_eval fixtures + 1 test renamed)

**Commits claimed:**

- [x] FOUND: `1b93734` (Task 1: F-17 cleared)
- [x] FOUND: `a9900d6` (Task 2: P1-3 red test update)
- [x] FOUND: `0f908b9` (Task 3: RC invoker + hybrid deleted)
- [x] FOUND: `255ef46` (Task 4: FORCED_TOOL_FAILURE_COUNT)

**Acceptance grep claims:**

- [x] FOUND: 0 occurrences of `AuditAgentMiddleware` / `ToolTimingMiddleware` in backend/src/
- [x] FOUND: 0 occurrences of `class RCEvalAgentInvoker` / `class _MigrationHybridInvoker` in backend/src/
- [x] FOUND: `class GAEvalAgentInvoker` + `class EvalAgentInvoker(Protocol)` in eval/invoker.py
- [x] FOUND: `FORCED_TOOL_FAILURE_COUNT` constant in kql_templates.py
- [x] FOUND: `Properties.["capture.outcome"]` bracket access in the new KQL template
- [x] FOUND: 0 import of `from second_brain.agents.middleware` anywhere in backend/src/

**Test claims:**

- [x] 63/63 pass: test_eval.py + test_eval_dry_run.py + test_eval_metrics.py + test_foundry_eval.py + test_legacy_middleware_imports_survive.py + test_foundry_credential_shape.py + test_inbox_dual_read.py
- [x] AST scan offender count 4 → 2 (eval/invoker.py dropped off; main.py + warmup.py remain — both 24-19 scope)
- [x] Linter clean on all modified files (`ruff check` passes)

Verification commands executed:

```bash
git log --oneline -5
# 255ef46 0f908b9 a9900d6 1b93734 ab4922a

! test -f backend/src/second_brain/agents/middleware.py && echo OK
# OK

cd backend && uv run pytest tests/test_eval.py tests/test_eval_dry_run.py tests/test_eval_metrics.py \
  tests/test_foundry_eval.py tests/test_legacy_middleware_imports_survive.py \
  tests/test_foundry_credential_shape.py tests/test_inbox_dual_read.py
# 63 passed

cd backend && uv run pytest tests/test_no_rc_imports_after_cleanup.py
# 1 failed (expected RED), offender count: main.py + warmup.py (2 files; 24-19 scope)
```

---

*Phase: 24-foundry-ga-migration*
*Plan: 24-18*
*Completed: 2026-05-11*
