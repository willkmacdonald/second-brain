---
phase: 24-foundry-ga-migration
plan: 21
subsystem: backend
tags: [foundry-ga, f-19, d-02, d-12, p2-8, config-cleanup, settings, pydantic]

# Dependency graph
requires:
  - phase: 24-foundry-ga-migration/19
    provides: "Codebase under backend/src/second_brain/ is RC-free (AzureAIAgentClient / agent_framework.azure deleted); main.py lifespan no longer reads settings.azure_ai_*_agent_id"
  - phase: 24-foundry-ga-migration/02
    provides: "foundry_model field added to Settings (used by FoundryChatClient construction)"
  - phase: 23-foundry-ga-prep/CONFIG-DELTAS.md
    provides: "Step C spec — code-side orphan removal lands BEFORE post-deploy env-var removal (24-23)"
provides:
  - "Settings class has only GA-relevant fields (azure_ai_project_endpoint + foundry_model + non-Foundry config)"
  - "model_config['extra'] = 'ignore' so the GA image boots cleanly with AZURE_AI_*_AGENT_ID env vars still set on the Container App"
  - "Final pre-deploy artifact state — 24-20 cumulative audit + Gate 10 startup smoke now run against this exact source tree"
affects:
  - "24-20 (cumulative audit + pre-deploy gates): runs against post-24-21 artifact per P2-8 reorder"
  - "24-22 (deploy): Container App image now reads zero orphan agent_id settings; the AZURE_AI_*_AGENT_ID env vars remain set but are silently ignored"
  - "24-23 (post-UAT env-var removal): finalises Step C by removing the now-unread env vars from the Container App"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BaseSettings extra='ignore' for asymmetric code-now / env-later cleanup windows. Tolerates orphan env vars from a prior deploy cycle so the source-code cleanup can ship BEFORE the env-var removal (and the env-var removal can wait until post-UAT). Reusable any time a Container App env var needs to be deprecated."

key-files:
  created:
    - .planning/phases/24-foundry-ga-migration/24-21-SUMMARY.md
  modified:
    - backend/src/second_brain/config.py
  deleted: []

key-decisions:
  - "Add model_config extra='ignore' to Settings. Pydantic Settings v2 defaults to extra='forbid' which makes orphan env vars FATAL on startup. Without this, plan 24-22's deploy would crash with ValidationError because the Container App still has AZURE_AI_CLASSIFIER_AGENT_ID (and admin/investigation) set. The plan's NON-NEGOTIABLE assertion (Container App env vars are NOT touched in this plan) is only honourable with extra='ignore'. This is the canonical pattern for the asymmetric code-now / env-later cleanup window CONFIG-DELTAS Step C describes."
  - "Task 2 (main.py orphan reads) was verification-only — zero file modifications needed. All lifespan-slice reads of settings.azure_ai_*_agent_id were already removed by 24-04 (Investigation), 24-09 (Admin), 24-14 (Classifier), 24-19 (warmup + foundry_client probe). The plan explicitly anticipated this state ('Most should already be gone'). Acceptance gates run clean on the codebase as it stood post-Task-1; no Task 2 commit was created (executor protocol prohibits empty commits)."
  - "Plan's verification snippet (`from second_brain.config import settings`) was off — config.py exports get_settings() (an lru_cache'd factory), not a `settings` singleton. Used the actual API for verification."

requirements-completed: [F-19, D-02, D-12, P2-8]

# Metrics
duration: 4min
completed: 2026-05-11
---

# Phase 24 Plan 21: Final config orphan cleanup — Settings is GA-only

**Three `azure_ai_*_agent_id` orphan fields deleted from Settings; codebase under `backend/src/second_brain/` is in its final pre-deploy state. The asymmetric code-now / env-later cleanup pattern is now active — Settings tolerates the still-set Container App env vars via `extra='ignore'` until 24-23 removes them post-UAT.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-11T~ (Task 1 only file edit; Task 2 verification-only)
- **Completed:** 2026-05-11
- **Tasks:** 2 (1 file-modifying, 1 verification-only)
- **Files modified:** 1 (backend/src/second_brain/config.py)
- **Files created:** 1 (this SUMMARY)

## Accomplishments

### Task 1 — Three orphan fields deleted from Settings + extra='ignore' guard

`backend/src/second_brain/config.py` simplification:

- **Deleted three Settings fields:**
  ```python
  azure_ai_classifier_agent_id: str = ""
  azure_ai_admin_agent_id: str = ""
  azure_ai_investigation_agent_id: str = ""
  ```
- **Preserved fields (GA-relevant):**
  - `azure_ai_project_endpoint: str = ""` — used by `FoundryChatClient(project_endpoint=...)` construction in main.py lifespan
  - `foundry_model: str = "gpt-4o"` — used by `FoundryChatClient(model=...)`; added in 24-02
- **Added `model_config['extra'] = 'ignore'`** with a docstring tying it back to CONFIG-DELTAS Step C. This is load-bearing: without it, Pydantic Settings v2 defaults to `extra='forbid'`, and the GA image would crash on startup against the Container App's still-set `AZURE_AI_*_AGENT_ID` env vars (see Deviations section below for the live ValidationError repro).

The final config.py is 16 lines shorter — three field declarations gone, three lines of explanatory `model_config` extra='ignore' added.

### Task 2 — main.py orphan reads verified clean (zero file modifications)

`grep -rn "azure_ai_classifier_agent_id\|azure_ai_admin_agent_id\|azure_ai_investigation_agent_id" backend/src/second_brain/` returns empty after Task 1. Every lifespan-slice read of these settings was already removed across earlier waves:

- **24-04 (Investigation):** Lifespan no longer reads `settings.azure_ai_investigation_agent_id`; build_investigation_agent constructs the GA Agent via the shared FoundryChatClient.
- **24-09 (Admin):** Lifespan no longer reads `settings.azure_ai_admin_agent_id`; build_admin_agent path.
- **24-14 (Classifier):** Lifespan no longer reads `settings.azure_ai_classifier_agent_id`; build_classifier_agent path.
- **24-19 (warmup + foundry_client):** Even the legacy `foundry_client = AzureAIAgentClient(...)` connectivity probe was deleted; warmup factories rebuild GA Agents via `build_*_agent` helpers reading tool instances from `app.state`.

The plan explicitly anticipated this state in its action description: "Most should already be gone... this plan catches any leftover (e.g., dead code, unused local variable assignments)." There were none. Acceptance gates run clean against the codebase as it stood post-Task-1.

## Task Commits

| Task | Hash      | Title                                                           |
|------|-----------|-----------------------------------------------------------------|
| 1    | `d51aefd` | chore(24-21): remove agent_id orphan fields from Settings       |
| 2    | (n/a)     | Verification-only — no file modifications needed (gates pass)   |

(Plan metadata commit follows this SUMMARY.)

## Files Created/Modified

| Path | Change | Notes |
|------|--------|-------|
| `backend/src/second_brain/config.py` | modified (-4 / +7) | Three orphan field declarations deleted; `model_config['extra'] = 'ignore'` added with CONFIG-DELTAS Step C citation. |
| `.planning/phases/24-foundry-ga-migration/24-21-SUMMARY.md` | **CREATED** | This file. |

## Decisions Made

1. **Add `model_config['extra'] = 'ignore'` (Rule 2 deviation).** Pydantic Settings v2's default is `extra='forbid'`. With the three fields deleted but the Container App still setting `AZURE_AI_CLASSIFIER_AGENT_ID` (and admin/investigation), Settings instantiation raises a `ValidationError` on startup. This blows up the very pattern CONFIG-DELTAS Step C designed: source-code cleanup ships BEFORE post-UAT env-var removal. Adding `extra='ignore'` is the only way to honour the plan's NON-NEGOTIABLE: "Container App env vars are NOT touched in this plan." See Deviations section for the live ValidationError repro.

2. **Task 2 produced no commit (intentional).** All lifespan-slice reads were already removed by waves 1-4. The plan anticipated this. Per executor protocol, empty commits are prohibited. The verification gates documenting Task 2's PASS state are recorded here in the SUMMARY.

3. **Used `get_settings()` (factory) for verification, not `settings` (singleton).** The plan's snippet `from second_brain.config import settings` does not match the actual export. config.py provides `get_settings()` (lru_cache'd factory) and the `Settings` class — there is no `settings` module-level singleton. Used the actual API.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Critical functionality] Added `model_config['extra'] = 'ignore'` to Settings**

- **Found during:** Task 1 verification — `cd backend && uv run python -c "from second_brain.config import get_settings; get_settings()"` raised `pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings / azure_ai_classifier_agent_id / Extra inputs are not permitted [type=extra_forbidden, input_value='asst_Fnjkq5RVrvdFIOSqbreAwxuq', input_type=str]`.
- **Issue:** Pydantic Settings v2 defaults to `extra='forbid'`. With the three Settings fields deleted but the Container App still setting `AZURE_AI_CLASSIFIER_AGENT_ID` (per CONFIG-DELTAS NON-NEGOTIABLE — those env vars are removed post-UAT in 24-23, NOT in this plan), Settings instantiation would crash the GA image on startup. CONFIG-DELTAS Step C explicitly says: "The GA code does not read them, so this is safe." That assertion is only true if Settings tolerates orphan env vars. Without `extra='ignore'`, plan 24-22's deploy fails immediately on Container App startup with `ValidationError`, which would force an emergency rollback to the RC image. The asymmetric code-now / env-later cleanup pattern requires this guard.
- **Fix:** Added `"extra": "ignore"` to `Settings.model_config` with an inline comment citing 23-foundry-ga-prep/CONFIG-DELTAS.md Step C.
- **Files modified:** `backend/src/second_brain/config.py`
- **Verification:**
  - `cd backend && uv run python -c "from second_brain.config import get_settings; settings = get_settings(); assert not hasattr(settings, 'azure_ai_classifier_agent_id'); assert settings.foundry_model == 'gpt-4o'"` exits 0
  - Reproduced the live ValidationError pre-fix by reading `backend/.env` which still contains `AZURE_AI_CLASSIFIER_AGENT_ID=asst_Fnjkq5RVrvdFIOSqbreAwxuq` (same shape as the Container App's environment per CONFIG-DELTAS)
  - `cd backend && uv run python -c "import second_brain.main"` exits 0 post-fix
- **Committed in:** `d51aefd` (Task 1 commit — bundled with field deletions because the bare deletion without `extra='ignore'` would have broken `uv run python -c "import second_brain.main"`, the Task 2 acceptance gate)

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical functionality / startup-blocking gap)

**Impact on plan:** The deviation is essential. CONFIG-DELTAS Step C describes an asymmetric cleanup pattern (code now, env later) that mathematically requires Settings to tolerate orphan env vars during the window. The plan's NON-NEGOTIABLE assertion ("Container App env vars are NOT touched in this plan") is only honourable with `extra='ignore'`. Without this fix, plan 24-22's deploy would crash on Container App startup with a ValidationError. No scope creep — this is the smallest possible patch to honour the plan's own constraints.

## Issues Encountered

- **Plan verification snippet inaccuracy:** the plan suggests `from second_brain.config import settings; ...` but config.py exports `get_settings()` (lru_cache'd factory) and the `Settings` class — there is no `settings` singleton. Used `get_settings()` for verification. Not a defect of this plan's outcome; just a tweak of the verification incantation.

## User Setup Required

None — no external service configuration required by this plan. The Container App env-var removal happens in 24-23 (post-UAT), not here.

## Next Phase Readiness

- **Plan 24-20 (cumulative audit + pre-deploy gates):** unblocked. The codebase under `backend/src/second_brain/` is now in its final pre-deploy state. Per P2-8 reorder, 24-20's gates (including Gate 10 startup smoke) run against THIS exact artifact.
- **Plan 24-22 (deploy):** unblocked. Container App image now reads zero orphan agent_id settings AND tolerates the orphan env vars that remain set in the environment (extra='ignore'). Deploy is mechanically safe.
- **Plan 24-23 (post-UAT env-var removal):** still gated on 24-22 UAT success per CONFIG-DELTAS NEGATIVE assertion. The `extra='ignore'` guard added here is a temporary tolerance — 24-23 makes it unnecessary by removing the env vars.

## Threat Flags

None — this plan does not introduce new network endpoints, auth paths, file access patterns, or trust-boundary changes.

- The `extra='ignore'` change makes Settings tolerate ADDITIONAL env vars (currently the three orphan agent_id ones). It does NOT relax field validation on declared fields. There is no scope-widening on the trust boundary.
- Deletion of three field declarations REDUCES configuration surface area by 3 fields. Net: attack surface shrinks slightly.

## TDD Gate Compliance

Plan type is `execute` (not `tdd`). No RED/GREEN/REFACTOR commits required. The single file-modifying task landed as a `chore` commit (config-only change, no behaviour change beyond startup tolerance for orphan env vars).

## Verification Snapshot

### Task 1 acceptance gates

| Criterion | Status |
|-----------|--------|
| `! grep -q "azure_ai_classifier_agent_id" backend/src/second_brain/config.py` | PASS |
| `! grep -q "azure_ai_admin_agent_id" backend/src/second_brain/config.py` | PASS |
| `! grep -q "azure_ai_investigation_agent_id" backend/src/second_brain/config.py` | PASS |
| `grep -q "azure_ai_project_endpoint" backend/src/second_brain/config.py` | PASS (preserved) |
| `grep -q "foundry_model" backend/src/second_brain/config.py` | PASS (preserved) |
| `cd backend && uv run python -c "from second_brain.config import get_settings; settings=get_settings(); assert settings.foundry_model == 'gpt-4o'"` exits 0 | PASS |
| `cd backend && uv run python -c "from second_brain.config import get_settings; settings=get_settings(); assert not hasattr(settings, 'azure_ai_classifier_agent_id')"` exits 0 | PASS |
| `cd backend && uv run ruff check src/second_brain/config.py` | PASS (All checks passed!) |

### Task 2 acceptance gates

| Criterion | Status |
|-----------|--------|
| `! grep -rq "azure_ai_classifier_agent_id" backend/src/second_brain/` | PASS |
| `! grep -rq "azure_ai_admin_agent_id" backend/src/second_brain/` | PASS |
| `! grep -rq "azure_ai_investigation_agent_id" backend/src/second_brain/` | PASS |
| `cd backend && uv run python -c "import second_brain.main"` exits 0 | PASS |
| `! grep -r -e "AzureAIAgentClient" backend/src/second_brain/` | PASS (24-19 inheritance) |
| `! grep -r -e "agent_framework.azure" backend/src/second_brain/` | PASS (24-19 inheritance) |
| `! grep -r -e "@tool(approval_mode" backend/src/second_brain/` | PASS (24-05/10/17 inheritance) |
| `! grep -rE "_agent_run\b" backend/src/second_brain/` (word-boundary; false positive on `fetch_agent_runs` is expected) | PASS |
| `foundryThreadId` still present in `models/documents.py` (P0-2 invariant — KEEP until 24-24) | PASS |

### Cumulative regression-guard test suite

```
$ cd backend && uv run pytest tests/test_no_rc_imports_after_cleanup.py \
    tests/test_legacy_middleware_imports_survive.py \
    tests/test_foundry_credential_shape.py \
    tests/test_inbox_dual_read.py \
    tests/test_observability.py
======================== 19 passed, 2 warnings in 0.21s ========================
```

### Startup smoke (fallback per plan)

```
$ cd backend && uv run python -c "import second_brain.main; print('FastAPI app title:', second_brain.main.app.title); print('Routes count:', len(second_brain.main.app.routes))"
FastAPI app title: Second Brain API
Routes count: 26
```

The formal `test_app_startup_smoke.py` does not exist yet — 24-20 creates it (per plan note). Gate 10 in 24-20 will re-run this same check against the post-24-21 artifact.

## Out-of-Scope Discoveries

None. The pre-existing `mcp/uv.lock` working-tree drift documented in 24-15 / 24-16 / 24-17 / 24-18 / 24-19 SUMMARYs is still present but was not introduced by this plan and is not in this plan's scope.

## Self-Check: PASSED

**Files claimed modified:**

- [x] MODIFIED: `backend/src/second_brain/config.py` (3 fields deleted; `extra='ignore'` added)

**Files claimed created:**

- [x] CREATED: `.planning/phases/24-foundry-ga-migration/24-21-SUMMARY.md` (this file)

**Commits claimed:**

- [x] FOUND: `d51aefd` (Task 1: chore(24-21): remove agent_id orphan fields from Settings)

**Acceptance grep claims:**

- [x] FOUND: 0 occurrences of `azure_ai_classifier_agent_id` anywhere under `backend/src/second_brain/`
- [x] FOUND: 0 occurrences of `azure_ai_admin_agent_id` anywhere under `backend/src/second_brain/`
- [x] FOUND: 0 occurrences of `azure_ai_investigation_agent_id` anywhere under `backend/src/second_brain/`
- [x] FOUND: `azure_ai_project_endpoint` still in config.py (line 12)
- [x] FOUND: `foundry_model` still in config.py (line 13)
- [x] FOUND: `"extra": "ignore"` in config.py model_config block

**Test claims:**

- [x] `tests/test_no_rc_imports_after_cleanup.py` PASSES (1/1 — inheritance from 24-19)
- [x] 19/19 cumulative regression-guard suite passes
- [x] Linter clean on config.py
- [x] `import second_brain.main` exits 0

Verification commands executed:

```bash
git log --oneline -2
# d51aefd 1d3a705

! grep -rq "azure_ai_classifier_agent_id\|azure_ai_admin_agent_id\|azure_ai_investigation_agent_id" backend/src/second_brain/ && echo "CLEAN"
# CLEAN

cd backend && uv run python -c "from second_brain.config import get_settings; settings=get_settings(); print(settings.foundry_model, hasattr(settings, 'azure_ai_classifier_agent_id'))"
# gpt-4o False

cd backend && uv run pytest tests/test_no_rc_imports_after_cleanup.py tests/test_legacy_middleware_imports_survive.py tests/test_foundry_credential_shape.py tests/test_inbox_dual_read.py tests/test_observability.py
# 19 passed
```

---

*Phase: 24-foundry-ga-migration*
*Plan: 24-21*
*Completed: 2026-05-11*
