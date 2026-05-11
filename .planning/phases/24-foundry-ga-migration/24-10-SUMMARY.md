---
phase: 24-foundry-ga-migration
plan: 10
subsystem: backend/tools
tags: [foundry-ga, admin-agent, recipe-tools, tool-binding, decorator-strip, f-08]

# Dependency graph
requires:
  - phase: 24-foundry-ga-migration
    provides: GA Agent factory build_admin_agent + lifespan wiring (24-09)
provides:
  - AdminTools class with 6 decorator-free async tool methods
  - RecipeTools class with 1 decorator-free async tool method
  - GA-ready bound-method shape consumable by Agent(tools=[instance.method, ...])
affects:
  - 24-11 (admin_handoff.py rewrite — consumes GA Agent built from these tools)
  - 24-14 (Classifier tool decorator strip — inherits the same mechanical pattern)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GA tool registration via Agent(tools=[instance.method, ...]) without @tool decorator"
    - "Annotated[T, Field(description=...)] parameter shape + docstring serve as GA tool descriptions"
    - "Mechanical decorator-strip pattern mirrored from 24-05 (InvestigationTools)"

key-files:
  created: []
  modified:
    - backend/src/second_brain/tools/admin.py
    - backend/src/second_brain/tools/recipe.py

key-decisions:
  - "Mirror 24-05 pattern: single Write per file (not Edit) to land decorator strips + unused-import removal atomically, avoiding the auto-format trap where ruff strips imports before the dependent Edit lands"
  - "Module + class docstrings updated to reflect GA tool registration (admin.py mentions 'async tool methods' instead of '@tool functions'; recipe.py adds Phase 24 GA paragraph). Method docstrings untouched per plan invariant"
  - "Docstring grep-guard fix: original docstring contained the literal substring '@tool(approval_mode=...)' which tripped `! grep -q '@tool(approval_mode='` acceptance check. Reworded to 'RC tool-registration decorator' (same fix-class as 24-09 deviation #1)"

patterns-established:
  - "Phase 24 decorator-strip mechanical pattern is now proven across all 3 agents' tool surfaces (Investigation in 24-05, Admin+Recipe in 24-10, Classifier slated for 24-14). Single-Write-per-file is the agreed shape"

requirements-completed: [F-08, D-05, D-06]

# Metrics
duration: 4min
completed: 2026-05-11
---

# Phase 24 Plan 10: Strip RC @tool decorators from AdminTools + RecipeTools Summary

**Mechanical decorator strip across 7 tool methods (6 AdminTools + 1 RecipeTools), mirroring the 24-05 pattern.** AdminTools and RecipeTools class shapes, `__init__` signatures, `Annotated[..., Field(description=...)]` parameter shapes, and method docstrings are all preserved. The lifespan wiring in `main.py` (built in 24-09 / pre-existing for non-admin paths) already passes these as bound methods, so no caller changes were needed.

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-11T01:47:08Z
- **Completed:** 2026-05-11T01:50:50Z
- **Tasks:** 2
- **Files modified:** 2
- **Lines:** +24 / -13 (net +11, mostly from added GA-migration docstring paragraphs)

## Accomplishments

### Task 1 — AdminTools (6 strips)

- Removed 6 `@tool(approval_mode="never_require")` decorator lines from `tools/admin.py` at the F-08 calibration line numbers (121, 191, 235, 249, 370, 537). Every method confirmed by AST scan to have an empty `decorator_list`.
- Removed unused `from agent_framework import tool` import.
- All 6 public tool methods preserved as plain async coroutines with their `Annotated[..., Field(description=...)]` parameter shapes intact:
  - `add_errand_items` (1 Annotated param)
  - `add_task_items` (1 Annotated param)
  - `get_routing_context` (no params)
  - `manage_destination` (6 Annotated params)
  - `manage_affinity_rule` (7 Annotated params)
  - `query_rules` (1 Annotated param)
- Total `Annotated[` occurrences after strip: 17 (matches pre-strip count — fully preserved).
- Total `Field(description=` occurrences after strip: 10 (matches pre-strip — preserved).
- `__init__(cosmos_manager)` Cosmos DI signature unchanged (D-06 invariant).
- 7 internal helper methods (`_collect_query`, `_destination_*`, `_rule_*`) unchanged.
- Module docstring updated: dropped "@tool functions" wording; added a Phase 24 GA migration paragraph explaining decorator removal and the new `Agent(tools=[instance.method, ...])` binding model.
- Class docstring updated: "Each tool method is a plain async coroutine. GA Agent binds the bound methods directly via `tools=[instance.method, ...]` at construction time."

### Task 2 — RecipeTools (1 strip)

- Removed the `@tool(approval_mode="never_require")` decorator at line 102 of `tools/recipe.py`.
- Removed unused `from agent_framework import tool` import.
- `fetch_recipe_url` preserved as a plain async coroutine with its single `Annotated[str, Field(description=...)]` URL parameter intact.
- `__init__(browser, spine_repo)` signature unchanged.
- 3 private fetch helpers (`_fetch_jina`, `_fetch_simple`, `_fetch_playwright`) and module-level functions (`_is_safe_url`, `_extract_json_ld_recipe`, `_normalize_url`) unchanged.
- Module docstring updated: added a Phase 24 GA migration paragraph noting the GA binding pattern; the three-tier fetch strategy summary preserved.
- Class docstring updated: "URL fetching tools bound to a Playwright Browser instance. `fetch_recipe_url` is a plain async coroutine; GA Agent binds the bound method directly via `tools=[instance.fetch_recipe_url, ...]`."

## Task Commits

| Task | Hash      | Title                                                                |
|------|-----------|----------------------------------------------------------------------|
| 1    | `96e6fa0` | feat(24-10): strip RC @tool decorators from AdminTools               |
| 2    | `34fec9a` | feat(24-10): strip RC @tool decorator from RecipeTools.fetch_recipe_url |

(Plan metadata commit follows this summary.)

## Files Created/Modified

- `backend/src/second_brain/tools/admin.py` — 6 decorator strips + 1 import cleanup + 2 docstring touch-ups (+14/-10)
- `backend/src/second_brain/tools/recipe.py` — 1 decorator strip + 1 import cleanup + 2 docstring touch-ups (+10/-3)

## Decisions Made

1. **Single Write per file (not Edit-chain).** Per MEMORY's documented auto-format trap, the ruff PostToolUse hook strips unused imports immediately after each Edit. If the decorator strip and the `from agent_framework import tool` removal happen in separate Edits, ruff sees a moment where `@tool(...)` references are still present but the import has been removed — undefined-name errors. Solved by writing the whole file in one `Write` so the on-disk snapshot is self-consistent when ruff runs.

2. **Module + class docstring updates** (same Rule 1 doc-accuracy fix recorded in 24-05's "Decisions Made"). The original docstrings said "@tool functions" or "URL fetching tools bound" — both became technically inaccurate after the strip. Updated both module + class docstrings to reflect the new GA tool registration semantics. Method docstrings untouched per the plan invariant ("Docstrings preserved on every tool method") — those become the GA tool descriptions.

3. **Docstring grep-guard collision (same class as 24-09 deviation #1).** The new module docstring originally read `Phase 24 GA migration: per D-05/D-06, the RC \`@tool(approval_mode=...)\` decorator was removed...`. That literal substring tripped the plan's `! grep -q "@tool(approval_mode="` acceptance criterion. Reworded to `"the RC tool-registration decorator was removed..."` — preserves the migration note without violating the grep guard.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Docstring containing literal `@tool(approval_mode=...)` violated the plan's grep guard**

- **Found during:** Task 1 verification (`grep -c "@tool(approval_mode=" admin.py` returned 1).
- **Issue:** The first-attempt module docstring in `admin.py` included the literal substring `RC \`@tool(approval_mode=...)\` decorator`. The plan's automated acceptance check is a literal grep — it doesn't distinguish docstrings from code. Same fix-class as 24-09 deviation #1 (`ensure_admin_agent` mentioned in docstring violated `! grep -q "ensure_admin_agent"`).
- **Fix:** Reworded both `admin.py` and `recipe.py` module docstrings to say "the RC tool-registration decorator was removed" without quoting the literal name.
- **Files modified:** `backend/src/second_brain/tools/admin.py` (folded into commit `96e6fa0`); `backend/src/second_brain/tools/recipe.py` (preemptively avoided the issue — Task 2's docstring never quoted the literal substring after I learned from Task 1).
- **Commit:** Folded into Task 1 commit `96e6fa0`.

### Out-of-scope discoveries (logged to `deferred-items.md`)

**Pre-existing ruff E501 at `tools/admin.py:413`** — the line `description="True if this rule was auto-saved from a HITL routing answer"` exceeds the 88-char limit by 1 character. Stash-verified to be pre-existing on `main` (same violation on line 408 before my touch); the decorator strip merely shifted the line number. Per the SCOPE BOUNDARY rule (only auto-fix issues directly caused by the current task's changes), this is logged to `deferred-items.md` rather than fixed. The plan invariant ("Annotated[..., Field(description=...)] parameter shape preserved on every tool method") would be violated if I re-wrapped the description string here.

Beyond the docstring fix and the deferred E501, no deviations:
- No bugs introduced by the strip (Rule 1) — the decorator removal is mechanical.
- No missing critical functionality (Rule 2) — the GA `Agent(tools=[...])` binding pattern needs decorator-free methods; this plan completes that requirement for the Admin agent surface.
- No blockers (Rule 3) — both files compile, import, and lint cleanly (modulo the pre-existing E501 noted above).
- No architectural changes (Rule 4).

## Authentication Gates

None encountered. The strip is a pure source-code transformation; verification runs locally without Azure connectivity.

## Known Stubs

None. AdminTools retains its full 6-tool surface; RecipeTools retains `fetch_recipe_url`. Lifespan wiring in `main.py` (built in 24-09) already binds these as `tools=[instance.method, ...]` — the GA Agent receives a 7-tool surface (6 admin + 1 recipe) when Playwright launches successfully, or 6 tools when Playwright fails (graceful degradation, also wired in 24-09).

## Threat Flags

None — this plan does not introduce new network endpoints, auth paths, file access patterns, or trust-boundary changes. SSRF protection in `recipe.py` (`_is_safe_url`) is preserved verbatim. The Cosmos DI in `admin.py` (`AdminTools.__init__(cosmos_manager)`) is preserved verbatim.

## Verification

### Acceptance criteria (per plan)

**Task 1 — AdminTools:**

- [x] `grep -c "@tool(approval_mode=" backend/src/second_brain/tools/admin.py` returns 0 (was 6)
- [x] `grep -c "class AdminTools" backend/src/second_brain/tools/admin.py` returns 1 (preserved)
- [x] `grep -c "Annotated\[" backend/src/second_brain/tools/admin.py` returns 17 (preserved)
- [x] `grep -c "Field(description=" backend/src/second_brain/tools/admin.py` returns 10 (preserved)
- [x] `from agent_framework import tool` removed (0 `from agent_framework` matches)
- [x] AST scan: all 6 public tool methods have empty decorator_list
- [x] `uv run python -c "from second_brain.tools.admin import AdminTools; t = AdminTools.__init__"` exits 0
- [x] 34/34 admin tool unit tests pass (`test_admin_tools.py` + `test_admin_task_tools.py`)

**Task 2 — RecipeTools:**

- [x] `grep -c "@tool(approval_mode=" backend/src/second_brain/tools/recipe.py` returns 0 (was 1)
- [x] `grep -c "class RecipeTools" backend/src/second_brain/tools/recipe.py` returns 1 (preserved)
- [x] `grep -c "async def fetch_recipe_url" backend/src/second_brain/tools/recipe.py` returns 1 (preserved)
- [x] `grep -c "Annotated\[" backend/src/second_brain/tools/recipe.py` returns 1 (preserved)
- [x] `grep -c "Field(description=" backend/src/second_brain/tools/recipe.py` returns 1 (preserved)
- [x] `from agent_framework import tool` removed (0 `from agent_framework` matches)
- [x] AST scan: `fetch_recipe_url` has empty decorator_list; 3 internal helpers unchanged
- [x] `uv run python -c "from second_brain.tools.recipe import RecipeTools"` exits 0
- [x] `uv run ruff check src/second_brain/tools/recipe.py` — All checks passed
- [x] 17/17 recipe tests pass (`test_recipe_tools.py` + `test_recipe_workload_emission.py`)

### Phase 24 invariant tests (regression check)

```
$ uv run pytest tests/test_legacy_middleware_imports_survive.py tests/test_foundry_credential_shape.py -x
5 passed (P1-3 + P1-5 invariants green)

$ uv run pytest tests/test_legacy_middleware_imports_survive.py tests/test_foundry_credential_shape.py \
    tests/test_admin_tools.py tests/test_admin_task_tools.py
39 passed

$ uv run pytest tests/test_recipe_tools.py tests/test_recipe_workload_emission.py
17 passed
```

### AST scan red test status

Expected RED — clears in 24-19 per the test's documented design. The current offender list is 6 files (same as after 24-09; `tools/admin.py` and `tools/recipe.py` were never offenders because the AST scan flags RC SDK imports, not the `@tool` decorator):

```
$ uv run pytest tests/test_no_rc_imports_after_cleanup.py
1 failed (expected). Remaining offender files:
  - second_brain/agents/classifier.py
  - second_brain/eval/runner.py
  - second_brain/main.py
  - second_brain/processing/admin_handoff.py
  - second_brain/streaming/adapter.py
  - second_brain/warmup.py
```

## Next Phase Readiness

- **Plan 24-11** (admin_handoff.py rewrite) can now call `agent.run()` against the Admin Agent built in 24-09 with these GA-clean tools.
- **Plan 24-14** (ClassifierTools decorator strip) inherits the exact same mechanical pattern established here. Two remaining files in `tools/`: `classification.py` (1 `@tool` at line 75) + `transcription.py` (1 `@tool` at line 58). Per CONTEXT D-01 the voice path becomes a direct call, so `transcription.py` may be deleted entirely rather than stripped — 24-14 decides.
- AST scan `test_no_rc_imports_after_cleanup.py` continues to be RED with 6 offenders (down from 8 pre-24-07 and pre-24-09). Clears in 24-19.

## Self-Check: PASSED

**Verification of claims:**

- [x] FOUND: `backend/src/second_brain/tools/admin.py` (modified, +14/-10)
- [x] FOUND: `backend/src/second_brain/tools/recipe.py` (modified, +10/-3)
- [x] FOUND: commit `96e6fa0` in `git log --oneline`
- [x] FOUND: commit `34fec9a` in `git log --oneline`
- [x] FOUND: 0 occurrences of `@tool(approval_mode=` in `tools/admin.py`
- [x] FOUND: 0 occurrences of `@tool(approval_mode=` in `tools/recipe.py`
- [x] FOUND: 0 occurrences of `from agent_framework` in either file (decorator import cleanly removed)
- [x] FOUND: 1 `class AdminTools` + 1 `class RecipeTools` declaration (preserved)
- [x] FOUND: 6 public AdminTools methods + 1 public RecipeTools method, all decorator-free (AST verified)
- [x] FOUND: 6 remaining offender files in `test_no_rc_imports_after_cleanup.py` (consistent with the test's documented red-state design)
- [x] FOUND: `.planning/phases/24-foundry-ga-migration/deferred-items.md` documents the pre-existing E501 out-of-scope discovery

---
*Phase: 24-foundry-ga-migration*
*Plan: 10*
*Completed: 2026-05-11*
