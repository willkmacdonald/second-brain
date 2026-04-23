---
phase: 21-eval-framework
plan: 04
subsystem: eval
tags: [eval, api, investigation-tools, background-task, fastapi, cosmos]

# Dependency graph
requires:
  - phase: 21-eval-framework/03
    provides: run_classifier_eval, run_admin_eval async runner functions
provides:
  - "POST /api/eval/run: triggers background eval with 202 Accepted + run ID"
  - "GET /api/eval/status/{run_id}: real-time status polling for eval runs"
  - "GET /api/eval/results: recent eval results from Cosmos (stripped individualResults)"
  - "Investigation tools: run_classifier_eval, run_admin_eval, get_eval_results (D-05, D-06, D-07)"
  - "Single in-flight guard prevents concurrent evals of same type (T-21-07)"
affects: [21-eval-framework/05]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Background task eval with in-memory status tracking via shared _eval_runs dict", "Investigation tools call eval runner directly (internal, no HTTP roundtrip)", "ruff auto-format import stripping workaround: add import + usage in same edit or after usage exists"]

key-files:
  created:
    - backend/src/second_brain/api/eval.py
  modified:
    - backend/src/second_brain/tools/investigation.py
    - backend/src/second_brain/main.py
    - backend/tests/test_eval.py

key-decisions:
  - "Investigation eval tools import _eval_runs from api.eval module and call runner functions directly (no HTTP roundtrip)"
  - "InvestigationTools.__init__ extended with optional classifier_client and admin_client params (None default)"
  - "GET /api/eval/results strips individualResults from response to keep payload small (T-21-08)"

patterns-established:
  - "Eval API pattern: POST triggers background task, GET polls status, separate GET for historical results"
  - "Investigation tool eval pattern: shared _eval_runs dict for in-flight guard + tool calls runner directly"

requirements-completed: [EVAL-04, EVAL-05]

# Metrics
duration: 8min
completed: 2026-04-23
---

# Phase 21 Plan 04: Eval API & Investigation Tools Summary

**Eval API endpoint with background task execution, status polling, and 3 investigation agent tools for triggering and viewing evals from mobile chat or Claude Code**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-23T21:51:43Z
- **Completed:** 2026-04-23T22:00:24Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `api/eval.py` with POST /api/eval/run (202 background task), GET /api/eval/status/{run_id} (polling), GET /api/eval/results (Cosmos query with stripped individualResults)
- Added 3 investigation tools (run_classifier_eval, run_admin_eval, get_eval_results) enabling eval triggering from mobile investigation chat (D-05) and Claude Code (D-06)
- Wired eval_router and extended InvestigationTools with classifier_client/admin_client in main.py
- Single in-flight guard on both API endpoint and investigation tools prevents concurrent runs of same type (T-21-07)
- 11 new tests covering API endpoints (202/400/409/404) and investigation tools; full suite passes (491 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create eval API endpoint with background task and status polling** - `586e06d` (feat)
2. **Task 2: Add investigation eval tools and wire everything in main.py** - `97f0f98` (feat)

## Files Created/Modified

- `backend/src/second_brain/api/eval.py` - Eval API with POST /api/eval/run, GET /api/eval/status/{run_id}, GET /api/eval/results
- `backend/src/second_brain/tools/investigation.py` - 3 new tools (run_classifier_eval, run_admin_eval, get_eval_results), extended __init__ with classifier_client/admin_client
- `backend/src/second_brain/main.py` - eval_router wiring, InvestigationTools instantiation with agent clients, 9-tool investigation list
- `backend/tests/test_eval.py` - 11 new tests (17 total) covering API endpoints and investigation tools

## Decisions Made

- Investigation eval tools import `_eval_runs` from `api.eval` module and call runner functions directly -- avoids HTTP roundtrip and keeps the in-flight guard consistent between API and tool invocations
- InvestigationTools.__init__ extended with optional `classifier_client` and `admin_client` params (None default) matching existing optional `cosmos_manager` pattern
- GET /api/eval/results strips `individualResults` from response per T-21-08 (information disclosure mitigation)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Re-added eval_router import stripped by ruff auto-format**
- **Found during:** Task 2
- **Issue:** eval_router import was added in first Edit but ruff auto-format hook stripped it as unused (the `include_router` usage was added in a separate later Edit)
- **Fix:** Re-added the import after the `include_router` usage was already in place, so ruff recognized it as used
- **Files modified:** backend/src/second_brain/main.py
- **Verification:** Full test suite passes (491 tests)
- **Committed in:** 97f0f98 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking -- known ruff import stripping issue per MEMORY.md Phase 17.1 lesson)
**Impact on plan:** Expected behavior per project memory. No scope creep.

## Issues Encountered

None beyond the expected ruff auto-format import stripping.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Eval API fully wired: mobile investigation chat and Claude Code can trigger evals via investigation tools (D-05, D-06)
- Results viewable through get_eval_results tool with accuracy tables (D-07)
- Plan 05 (CI integration) can add GitHub Actions workflow that calls POST /api/eval/run against the deployed endpoint

## Self-Check: PASSED
