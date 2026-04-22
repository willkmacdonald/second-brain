---
phase: 20-feedback-collection
plan: 01
subsystem: api
tags: [fastapi, cosmos-db, feedback, quality-signals, pydantic]

requires:
  - phase: 16-query-foundation
    provides: Cosmos container definitions including Feedback container
provides:
  - POST /api/feedback endpoint for explicit thumbs up/down signals
  - Inline FeedbackDocument writes in recategorize, HITL, and errand handlers
  - Fire-and-forget signal pattern (never blocks primary user actions)
affects: [20-feedback-collection, 21-eval-pipeline]

tech-stack:
  added: []
  patterns: [fire-and-forget feedback signals via try/except in handlers]

key-files:
  created:
    - backend/src/second_brain/api/feedback.py
    - backend/tests/test_feedback.py
  modified:
    - backend/src/second_brain/api/inbox.py
    - backend/src/second_brain/api/errands.py
    - backend/src/second_brain/main.py

key-decisions:
  - "Fire-and-forget pattern for inline signal writes per D-02 -- try/except wraps every FeedbackDocument write so failures never block primary actions"
  - "POST /api/feedback writes directly (not fire-and-forget) since it IS the primary action"
  - "signalType whitelist validation rejects anything outside thumbs_up/thumbs_down on explicit endpoint"

patterns-established:
  - "Inline feedback signal: wrap FeedbackDocument creation in try/except with logger.warning, after the primary DB operation"

requirements-completed: [FEED-01, FEED-02]

duration: 6min
completed: 2026-04-22
---

# Phase 20 Plan 01: Feedback Signal Infrastructure Summary

**POST /api/feedback endpoint for explicit thumbs up/down, plus inline FeedbackDocument writes in recategorize, HITL bucket pick, and errand re-route handlers**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-22T05:36:36Z
- **Completed:** 2026-04-22T05:43:16Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- POST /api/feedback endpoint validates signalType, writes FeedbackDocument to Cosmos Feedback container, returns 201
- Recategorize handler emits signalType="recategorize" with originalBucket and correctedBucket
- HITL same-bucket confirmation emits signalType="hitl_bucket"
- Errand re-route emits signalType="errand_reroute" with destination as correctedBucket
- All inline signal writes are fire-and-forget (failure never blocks primary action)
- 9 tests covering all signal types, validation, auth, error paths, and non-fatal failure

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test scaffold and feedback API endpoint** - `7005b92` (feat -- TDD RED+GREEN combined)
2. **Task 2: Add implicit signal emit to recategorize, HITL, and errand handlers + register router** - `2c02347` (feat)

## Files Created/Modified
- `backend/src/second_brain/api/feedback.py` - POST /api/feedback endpoint with FeedbackRequest model and signalType validation
- `backend/tests/test_feedback.py` - 9 tests covering explicit + implicit feedback signals
- `backend/src/second_brain/api/inbox.py` - Inline FeedbackDocument writes for recategorize and HITL bucket pick
- `backend/src/second_brain/api/errands.py` - Inline FeedbackDocument write for errand re-route
- `backend/src/second_brain/main.py` - Feedback router registered via app.include_router

## Decisions Made
- Fire-and-forget pattern for all inline signal writes (per D-02 design decision) -- try/except wraps with logger.warning
- POST /api/feedback uses direct Cosmos write (not fire-and-forget) since it IS the primary action
- signalType whitelist rejects anything outside thumbs_up/thumbs_down on the explicit endpoint
- captureTraceId=None for errand re-routes since errands don't carry trace IDs

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed ruff auto-format stripping unused FeedbackDocument import**
- **Found during:** Task 2 (inbox.py modification)
- **Issue:** Auto-format hook strips unused imports between edits (known MEMORY.md Phase 17.1 lesson)
- **Fix:** Used single Write for entire inbox.py and errands.py files with import + usage together; used noqa: F401 temporarily for main.py import until include_router added
- **Files modified:** inbox.py, errands.py, main.py
- **Verification:** All 9 tests pass, ruff check clean
- **Committed in:** 2c02347

**2. [Rule 1 - Bug] Fixed E501 line too long in feedback.py**
- **Found during:** Task 1 (pre-commit hook)
- **Issue:** Error detail string exceeded 88-char line limit
- **Fix:** Split f-string across multiple lines using implicit concatenation
- **Files modified:** backend/src/second_brain/api/feedback.py
- **Verification:** ruff check passes
- **Committed in:** 7005b92

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required. The Feedback Cosmos container already exists (created in Phase 16).

## Next Phase Readiness
- Feedback signal infrastructure is complete and ready for Plan 02 (signal promotion pipeline)
- All signal types (recategorize, hitl_bucket, errand_reroute, thumbs_up, thumbs_down) write to Feedback container
- Full test suite passes (449 passed, 3 skipped)

---
## Self-Check: PASSED

- All created files exist on disk
- Both task commit hashes found in git log
- All key patterns verified in modified files (recategorize, hitl_bucket, errand_reroute signals; feedback_router registration)

---
*Phase: 20-feedback-collection*
*Completed: 2026-04-22*
