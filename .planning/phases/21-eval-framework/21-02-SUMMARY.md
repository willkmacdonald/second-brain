---
phase: 21-eval-framework
plan: 02
subsystem: eval
tags: [dry-run, golden-dataset, agent-framework, cosmos, argparse]

# Dependency graph
requires:
  - phase: 21-eval-framework/01
    provides: GoldenDatasetDocument model and EvalResults container
provides:
  - EvalClassifierTools dry-run tool class for classifier eval
  - DryRunAdminTools dry-run tool class for admin agent eval
  - Golden dataset seed script (export/import subcommands)
affects: [21-eval-framework/03, 21-eval-framework/04]

# Tech tracking
tech-stack:
  added: []
  patterns: [dry-run tool capture pattern, byte-identical parameter signatures]

key-files:
  created:
    - backend/src/second_brain/eval/dry_run_tools.py
    - backend/scripts/seed_golden_dataset.py
    - backend/tests/test_eval_dry_run.py
  modified: []

key-decisions:
  - "Confidence clamped to [0.0, 1.0] in EvalClassifierTools to prevent out-of-range predictions"
  - "DryRunAdminTools only includes 3 eval-relevant tools (add_errand_items, add_task_items, get_routing_context) -- management tools excluded from eval"

patterns-established:
  - "Dry-run tool pattern: mirror production tool parameter signatures byte-for-byte, capture predictions in instance attributes instead of writing to Cosmos"
  - "Seed script pattern: export subcommand writes JSON with _review_status for human curation, import filters to approved entries only"

requirements-completed: [EVAL-01, EVAL-03]

# Metrics
duration: 4min
completed: 2026-04-23
---

# Phase 21 Plan 02: Dry-Run Tools & Golden Dataset Summary

**Dry-run tool handlers for classifier and admin agent eval with golden dataset export/import seed script**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-23T21:36:06Z
- **Completed:** 2026-04-23T21:40:29Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- EvalClassifierTools captures bucket/confidence/status predictions without Cosmos writes, with confidence clamping
- DryRunAdminTools captures routing destinations and task items without Cosmos writes, returns fixed routing context
- Golden dataset seed script exports Inbox captures to JSON for human curation and imports approved entries as GoldenDatasetDocuments
- Parameter signatures byte-for-byte identical to production tools (Pitfall #3 prevention)
- 11 unit tests (7 test functions with parametrize) all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create dry-run tool handlers with tests (TDD RED)** - `c140b45` (test)
2. **Task 1: Create dry-run tool handlers with tests (TDD GREEN)** - `f6e5da6` (feat)
3. **Task 2: Create golden dataset seed script** - `0cc9ff8` (feat)

_Note: Task 1 followed TDD RED-GREEN cycle. Refactor phase skipped (code clean)._

## Files Created/Modified
- `backend/src/second_brain/eval/dry_run_tools.py` - EvalClassifierTools and DryRunAdminTools classes with production-identical parameter signatures
- `backend/scripts/seed_golden_dataset.py` - Export/import script for golden dataset seeding with argparse CLI
- `backend/tests/test_eval_dry_run.py` - 7 test functions covering capture, clamping, reset, accumulation

## Decisions Made
- Confidence clamped to [0.0, 1.0] in EvalClassifierTools to prevent out-of-range predictions corrupting metrics
- DryRunAdminTools only includes the 3 eval-relevant tools (add_errand_items, add_task_items, get_routing_context) -- destination/rule management tools excluded from eval since agents don't manage infrastructure during eval runs

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

- RED gate: `c140b45` (test commit with failing import)
- GREEN gate: `f6e5da6` (feat commit with implementation passing all tests)
- REFACTOR gate: skipped (code already clean)

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Dry-run tools ready for Plan 03 (eval runner CLI) to wire into Foundry agent evaluation loop
- Seed script ready for Will to export/curate/import golden dataset entries
- Full test suite passing (474 tests, 3 skipped, 1 warning)

---
*Phase: 21-eval-framework*
*Completed: 2026-04-23*
