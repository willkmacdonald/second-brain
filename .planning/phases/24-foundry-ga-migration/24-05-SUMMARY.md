---
phase: 24-foundry-ga-migration
plan: 05
subsystem: api
tags: [agent-framework, foundry-ga, investigation-agent, tool-binding, ast-scan]

# Dependency graph
requires:
  - phase: 24-foundry-ga-migration
    provides: GA Agent + FoundryChatClient wiring for Investigation Agent (24-04)
provides:
  - InvestigationTools class with 9 decorator-free async tool methods
  - GA-ready bound-method shape consumable by Agent(tools=[instance.method, ...])
  - tools/investigation.py cleared from RC SDK offender list (AST scan: 9 -> 8 files)
affects:
  - 24-06 (KQL update -- independent, but consumes the same tools class)
  - 24-07 (streaming/investigation_adapter.py rewrite -- consumes the GA Agent built from these tools)
  - 24-09, 24-14 (Admin + Classifier tool decorator strips inherit this mechanical pattern)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GA tool registration via Agent(tools=[instance.method, ...]) without @tool decorator"
    - "Annotated[T, Field(description=...)] parameter shape + docstring serve as GA tool descriptions"
    - "RC <-> GA type-hint decoupling via typing.Any for cross-migration-window compatibility"

key-files:
  created: []
  modified:
    - backend/src/second_brain/tools/investigation.py

key-decisions:
  - "Replace AzureAIAgentClient type hints with typing.Any (instead of GA Agent type) -- the runtime objects passed at app.state.classifier_client / .admin_client are still RC AzureAIAgentClient until plans 24-09 and 24-14 migrate them; Any preserves the file's source-level cleanliness for the AST scan while remaining compatible across the migration window."
  - "Module + InvestigationTools class docstrings updated to drop stale '@tool function' wording -- Rule 1 doc accuracy fix; method docstrings untouched per plan invariant."

patterns-established:
  - "GA tool binding pattern: plain async methods on tools class, registered via Agent(tools=[bound.method, ...]). Decorator-less."
  - "Cross-migration-window type-hint pattern: typing.Any for params that hold RC-typed runtime objects until later plans migrate them to GA types."

requirements-completed: [F-08, D-05, D-06]

# Metrics
duration: 8min
completed: 2026-05-10
---

# Phase 24 Plan 05: Strip RC @tool decorators from InvestigationTools Summary

**Stripped all 9 `@tool(approval_mode="never_require")` decorators from InvestigationTools so GA `Agent(tools=[instance.method, ...])` binds the methods natively at construction time.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-10T18:25:00Z (approx)
- **Completed:** 2026-05-10T18:33:52Z
- **Tasks:** 1
- **Files modified:** 1
- **Lines:** +14 / -20 (net -6)

## Accomplishments

- Removed all 9 `@tool(approval_mode="never_require")` decorator lines (was at file lines 112, 179, 250, 297, 372, 485, 594, 663, 743 in pre-strip file)
- Removed `from agent_framework import tool` import (unused after strip)
- Removed `from agent_framework.azure import AzureAIAgentClient` TYPE_CHECKING import
- Relaxed `classifier_client` / `admin_client` __init__ type hints from `AzureAIAgentClient | None` to `Any`
- Added `Any` to typing imports
- Updated module docstring + class docstring to drop stale "@tool function" wording and add Phase 24 GA migration paragraph
- All 9 method bodies, signatures, and docstrings preserved unchanged
- All 15 `Annotated[..., Field(description=...)]` parameter shapes preserved unchanged
- __init__ signature shape preserved unchanged (Cosmos DI invariant per D-06)

## Task Commits

1. **Task 1: Strip @tool(approval_mode=...) from all 9 InvestigationTools methods + cleanup imports** -- `aa5ad76` (feat)

(Plan metadata commit follows this summary.)

## Files Created/Modified

- `backend/src/second_brain/tools/investigation.py` -- 9 decorator strips + 2 import cleanups + 2 type-hint relaxations + 2 docstring touch-ups

## Decisions Made

1. **`AzureAIAgentClient` type hints -> `typing.Any` (not `Agent` from GA agent-framework).** The runtime objects that flow through `InvestigationTools.__init__` for `classifier_client` and `admin_client` come from `app.state.classifier_client` / `app.state.admin_client`, which are RC `AzureAIAgentClient` instances today. Plans 24-09 (Admin) and 24-14 (Classifier) will migrate those to GA `Agent` later. Using `Any` keeps `tools/investigation.py` source-clean for the AST scan immediately and avoids re-touching this file when the other agents migrate. The internal methods (`run_classifier_eval`, `run_admin_eval`) call helper functions in `eval/runner.py` -- these accept whatever object is passed; the type-hint relaxation is invisible at runtime.

2. **Module + class docstring updates** (Rule 1 doc accuracy fix). The module docstring said "Uses the class-based tool pattern to bind LogsQueryClient references to @tool functions"; the class docstring said "Each @tool function wraps a query..." Both became false after the strip. Updated both to say "async tool methods" / "Each tool method", plus added a Phase 24 GA migration paragraph to the module docstring noting the D-05/D-06 pattern. Method docstrings untouched per plan invariant (those serve as GA tool descriptions).

## Deviations from Plan

The plan's <action> step 7 specifies running `tests/test_investigation.py` after the strip. That file does not exist in this repo -- the actual InvestigationTools-adjacent tests are `tests/test_investigation_client.py` and `tests/test_investigation_queries.py`. Ran both (12/12 pass). Not treated as a deviation -- the plan's success criterion is "Existing unit tests still pass with mocked deps", which holds.

Beyond that, no deviations:
- No bugs (Rule 1) -- the decorator strip is mechanical
- No missing critical functionality (Rule 2)
- No blockers (Rule 3) -- the file compiles, imports, and lints cleanly
- No architectural changes (Rule 4)

The doc-accuracy fix is recorded above as a "Decision Made" because it's narrow scope that the plan's must-haves don't constrain ("Docstrings preserved on every tool method" was satisfied -- method docstrings unchanged; only the module + class docstrings were touched).

## Issues Encountered

**Auto-format hook trap** (per MEMORY): the ruff PostToolUse hook strips unused imports immediately after each Edit. The first attempt did `from agent_framework import tool` removal via Edit, which left the 9 `@tool(...)` references undefined and broke the file. Resolved by switching to a single `Write` of the full file that lands all changes atomically -- decorator strips + import removal + type-hint changes + docstring updates in one disk write -- so ruff sees a self-consistent file when it runs.

## Verification

### Acceptance criteria (per plan)

- [x] `grep -c "@tool(approval_mode=" backend/src/second_brain/tools/investigation.py` -> 0 (was 9)
- [x] `grep -c "async def"` -> 9 (one per tool method, unchanged)
- [x] `grep -c "Annotated\["` -> 15 (parameter shapes preserved)
- [x] `grep -c "Field(description="` -> 4 lines (15 total Field invocations across multi-line params, all preserve description= kwarg)
- [x] `grep -c "class InvestigationTools"` -> 1 (class shape preserved)
- [x] `grep -c "def __init__"` -> 1 (DI signature preserved)
- [x] InvestigationTools imports and is reachable; all 9 methods are async coroutines (verified via runtime + AST)
- [x] `python -m py_compile` passes
- [x] `ruff check` passes -- All checks passed

### Success criteria (per executor prompt)

- [x] backend/src/second_brain/tools/investigation.py: zero `@tool(approval_mode=` matches
- [x] backend/src/second_brain/tools/investigation.py: zero `from agent_framework import tool` matches
- [x] backend/src/second_brain/tools/investigation.py: zero `from agent_framework.azure import AzureAIAgentClient` matches (type hints replaced with `Any`)
- [x] All 9 methods retain Annotated[...] + Field(description=...) params
- [x] AST scan `test_no_rc_imports_after_cleanup.py` offender file count drops from 9 -> 8 (`tools/investigation.py` cleared from the list)
- [x] Phase 24 invariant tests still pass: 5/5 (test_legacy_middleware_imports_survive.py + test_foundry_credential_shape.py)
- [x] Existing InvestigationTools-adjacent tests pass: 12/12 (test_investigation_client.py + test_investigation_queries.py)
- [x] All tasks committed with --no-verify
- [x] No modifications to STATE.md or ROADMAP.md (per parallel_execution directive)

### Test runs

```
$ uv run pytest tests/test_legacy_middleware_imports_survive.py tests/test_foundry_credential_shape.py -v
... 5 passed

$ uv run pytest tests/test_investigation_client.py tests/test_investigation_queries.py -v
... 12 passed

$ uv run pytest tests/test_no_rc_imports_after_cleanup.py -v
... 1 failed (expected -- remaining 8 offender files; tools/investigation.py NOT in list)

Remaining offender files (8):
  - second_brain/agents/admin.py
  - second_brain/agents/classifier.py
  - second_brain/eval/runner.py
  - second_brain/main.py
  - second_brain/processing/admin_handoff.py
  - second_brain/streaming/adapter.py
  - second_brain/streaming/investigation_adapter.py
  - second_brain/warmup.py
```

## Next Phase Readiness

- Plan 24-06 (KQL `AGENT_RUNS` template update) is independent and unaffected -- it touches `observability/queries.py` only.
- Plan 24-07 (streaming/investigation_adapter.py rewrite) will consume the GA Agent built from these tools in 24-04 and pass requests through the now-decorator-free `investigation_tools.{method}` references already wired in main.py.
- Plans 24-09 (AdminTools strip) and 24-14 (ClassifierTools strip) will follow the exact same mechanical pattern established here.
- AST scan `test_no_rc_imports_after_cleanup.py` continues to be RED (8 offenders remaining) per the test's documented design: it stays RED until 24-19 clears the last RC import.

## Self-Check: PASSED

**Verification of claims:**

- [x] FOUND: backend/src/second_brain/tools/investigation.py (modified, 14+/20-)
- [x] FOUND: commit aa5ad76 in `git log --oneline`
- [x] FOUND: 0 occurrences of `@tool(approval_mode=` in the modified file
- [x] FOUND: 0 occurrences of `from agent_framework` in the modified file
- [x] FOUND: 0 occurrences of `AzureAIAgentClient` in the modified file
- [x] FOUND: 9 `async def` method definitions in the modified file
- [x] FOUND: 8 distinct offender files in test_no_rc_imports_after_cleanup.py (was 9 pre-strip)

---
*Phase: 24-foundry-ga-migration*
*Plan: 05*
*Completed: 2026-05-10*
