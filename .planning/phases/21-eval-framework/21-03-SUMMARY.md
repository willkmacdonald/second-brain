---
phase: 21-eval-framework
plan: 03
subsystem: eval
tags: [eval, runner, agent-framework, cosmos, metrics, golden-dataset]

# Dependency graph
requires:
  - phase: 21-eval-framework/01
    provides: compute_classifier_metrics, compute_confidence_calibration, compute_admin_metrics
  - phase: 21-eval-framework/02
    provides: EvalClassifierTools, DryRunAdminTools dry-run tool classes
provides:
  - "run_classifier_eval: orchestrates classifier eval against golden dataset with dry-run tools"
  - "run_admin_eval: orchestrates admin agent eval against golden dataset with dry-run tools"
  - "In-memory run status tracking with progress, completion, and failure states"
affects: [21-eval-framework/04, 21-eval-framework/05]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Sequential eval runner with fresh tool instance per case (no state leakage)", "In-memory runs_dict for eval status tracking"]

key-files:
  created:
    - backend/src/second_brain/eval/runner.py
  modified:
    - backend/tests/test_eval.py

key-decisions:
  - "ChatOptions is a dict subclass -- tests use bracket notation options['tools'] not attribute access"
  - "Input text truncated to 100 chars in individualResults for information disclosure mitigation (T-21-04)"
  - "60-second per-case timeout prevents runaway agent calls (T-21-05)"
  - "model_dump(mode='json') used for EvalResultsDocument Cosmos serialization to handle datetime fields"

patterns-established:
  - "Eval runner pattern: read golden dataset, iterate sequentially with fresh tools, compute metrics, persist results, track status"
  - "Agent mock pattern for eval tests: side_effect function invokes dry-run tool from options['tools'] dict"

requirements-completed: [EVAL-01, EVAL-02, EVAL-03, EVAL-04]

# Metrics
duration: 5min
completed: 2026-04-23
---

# Phase 21 Plan 03: Eval Runner Summary

**Core eval runner orchestrating golden dataset evaluation for Classifier and Admin Agent with sequential case execution, dry-run tools, metric computation, Cosmos persistence, and in-memory status tracking**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-23T21:43:05Z
- **Completed:** 2026-04-23T21:48:43Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Built `run_classifier_eval` function: reads golden dataset from Cosmos, filters classifier-only cases, runs each through Foundry agent with fresh EvalClassifierTools per case, computes accuracy/precision/recall/calibration metrics, writes EvalResultsDocument to Cosmos, logs to App Insights, tracks run status in-memory
- Built `run_admin_eval` function: same pattern with DryRunAdminTools, routing accuracy metrics, and per-destination breakdown
- Individual case errors (timeouts, agent exceptions) handled gracefully without aborting the entire run
- Full TDD cycle: RED (6 failing tests) then GREEN (implementation passing all 6 tests)
- Full regression suite passes (480 tests, 3 skipped, no failures)

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for eval runner** - `d1fbf5b` (test)
2. **Task 1 (GREEN): Implement eval runner + fix test mocks** - `1912306` (feat)

_TDD task with RED/GREEN commits. Refactor phase skipped (code clean)._

## Files Created/Modified

- `backend/src/second_brain/eval/runner.py` - Core eval runner with `run_classifier_eval` and `run_admin_eval` async functions
- `backend/tests/test_eval.py` - 6 unit tests covering accuracy, empty dataset, Cosmos persistence, progress tracking, timeout handling, top-level exception handling

## Decisions Made

- ChatOptions is a dict subclass in agent_framework -- test mocks must use `options["tools"][0]` bracket notation, not `options.tools[0]` attribute access
- Input text truncated to 100 chars in individualResults to mitigate information disclosure (T-21-04)
- 60-second asyncio.timeout per agent call prevents runaway eval cases (T-21-05)
- `model_dump(mode="json")` serializes EvalResultsDocument for Cosmos to handle datetime fields correctly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ChatOptions dict access in test mocks**
- **Found during:** Task 1 GREEN phase
- **Issue:** Test mocks used `options.tools[0]` attribute access but ChatOptions is a dict subclass -- attribute access silently returned AsyncMock instead of the actual tool function, causing all predictions to be None/empty
- **Fix:** Changed all test mock `fake_get_response` functions to use `options["tools"][0]` bracket notation
- **Files modified:** backend/tests/test_eval.py
- **Verification:** All 6 tests pass with correct accuracy values
- **Committed in:** 1912306 (GREEN commit)

**2. [Rule 1 - Bug] Fixed timeout test assertion for correct count**
- **Found during:** Task 1 GREEN phase
- **Issue:** Test expected 2 correct cases but mock always predicts "Admin" -- only case-1 (expectedBucket=Admin) matches, case-3 (expectedBucket=Ideas) does not
- **Fix:** Updated assertion from `correct == 2` to `correct == 1` with explanatory comment
- **Files modified:** backend/tests/test_eval.py
- **Verification:** Test passes with correct assertion
- **Committed in:** 1912306 (GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 bugs in test code)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep.

## TDD Gate Compliance

- RED gate: `d1fbf5b` (test commit with 6 test functions, import fails)
- GREEN gate: `1912306` (feat commit with implementation passing all 6 tests)
- REFACTOR gate: Not needed -- code is clean and minimal

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `second_brain.eval.runner` ready for Plan 04 (eval API endpoint) to wrap as background task
- Both `run_classifier_eval` and `run_admin_eval` accept injected dependencies (cosmos_manager, agent_client, runs_dict) for easy wiring in FastAPI
- In-memory `runs_dict` pattern ready for status polling endpoint

## Self-Check: PASSED

All files created and commits verified.

---
*Phase: 21-eval-framework*
*Completed: 2026-04-23*
