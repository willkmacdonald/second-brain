---
phase: 20-feedback-collection
plan: 02
subsystem: api
tags: [fastapi, cosmos-db, investigation-agent, feedback, golden-dataset, foundry]

requires:
  - phase: 20-feedback-collection/01
    provides: Feedback Cosmos container writes (FeedbackDocument from recategorize, HITL, errand, thumbs signals)
  - phase: 17-investigation-agent
    provides: InvestigationTools class with @tool pattern and LogsQueryClient binding
provides:
  - query_feedback_signals @tool for investigation agent (misclassification queries)
  - promote_to_golden_dataset @tool with two-step confirm flow
  - CosmosManager injection into InvestigationTools
  - Updated investigation agent portal instructions with feedback tool docs
affects: [20-feedback-collection, 21-eval-pipeline]

tech-stack:
  added: []
  patterns: [two-step confirm flow for destructive agent actions (preview then write)]

key-files:
  created: []
  modified:
    - backend/src/second_brain/tools/investigation.py
    - backend/src/second_brain/main.py
    - backend/tests/test_feedback.py
    - docs/foundry/investigation-agent-instructions.md

key-decisions:
  - "Two-step promote flow (preview then confirm) per D-06 -- agent shows preview first, only writes after explicit user confirmation"
  - "CosmosManager passed as optional param (None default) so existing telemetry-only tools work without Cosmos"
  - "Misclassification summary uses Counter on recategorize signals for bucket transition counts"
  - "GoldenDatasetDocument tagged with source=promoted_feedback and signal type tag"

patterns-established:
  - "Two-step confirm pattern: @tool with confirm=bool param; False returns preview JSON, True executes write"
  - "Optional dependency injection: cosmos_manager defaults to None with early-return error JSON when unavailable"

requirements-completed: [FEED-03, FEED-04]

duration: 6min
completed: 2026-04-22
---

# Phase 20 Plan 02: Signal Promotion Pipeline Summary

**Investigation agent feedback tools: query_feedback_signals for misclassification analysis and promote_to_golden_dataset with two-step confirm flow for golden dataset curation**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-22T05:47:33Z
- **Completed:** 2026-04-22T05:53:33Z
- **Tasks:** 2 (Task 1 TDD with RED + GREEN commits)
- **Files modified:** 4

## Accomplishments
- query_feedback_signals @tool queries Feedback Cosmos container with optional signal_type filter, time_range, and limit; returns misclassification_summary with Counter-based bucket transition counts
- promote_to_golden_dataset @tool implements two-step flow: preview (confirm=False) shows signal details, confirm (confirm=True) writes GoldenDatasetDocument with source="promoted_feedback"
- Both tools registered in main.py investigation_tools list (6 tools total) with CosmosManager dependency injection
- Investigation agent instructions updated with tool descriptions, mandatory two-step promote flow, feedback review and golden dataset promotion usage patterns
- 7 new tests covering all tool behaviors (16 total in test_feedback.py)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add query_feedback_signals and promote_to_golden_dataset tools with tests**
   - `5d2ad72` (test -- TDD RED: failing tests)
   - `556ab63` (feat -- TDD GREEN: implementation passes all tests)
2. **Task 2: Wire tools into main.py and update investigation agent instructions** - `bba6cd4` (feat)

## Files Created/Modified
- `backend/src/second_brain/tools/investigation.py` - Added query_feedback_signals and promote_to_golden_dataset @tool methods with cosmos_manager injection
- `backend/src/second_brain/main.py` - Pass cosmos_manager to InvestigationTools, register 2 new tools in investigation_tools list
- `backend/tests/test_feedback.py` - 7 new tests for feedback investigation tools (16 total)
- `docs/foundry/investigation-agent-instructions.md` - Updated with feedback tool descriptions, usage patterns, two-step promote flow

## Decisions Made
- Two-step promote flow (preview then confirm) per D-06 design decision -- agent shows preview first, only writes GoldenDatasetDocument after explicit user confirmation
- CosmosManager passed as optional parameter (defaults to None) so existing telemetry-only tools work without Cosmos dependency
- Misclassification summary uses Counter on recategorize signals for bucket transition counts (e.g., "Ideas -> Admin: 2")
- GoldenDatasetDocument tagged with source="promoted_feedback" and tags=["from_feedback", signal_type]
- expectedBucket derived from correctedBucket (preferred) or originalBucket (fallback for thumbs_up)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test assertion for query parameter check**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** Operator precedence in ternary expression caused query_str to be empty string instead of the Cosmos SQL query
- **Fix:** Simplified assertion to `call_args[1].get("query", "")` without the OR/ternary fallback
- **Files modified:** backend/tests/test_feedback.py
- **Verification:** All 7 new tests pass
- **Committed in:** 556ab63

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test assertion fix. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviation above.

## User Setup Required
None - Feedback and GoldenDataset Cosmos containers already exist (created in Phase 16). Investigation agent portal instructions need manual paste into Foundry portal.

## Next Phase Readiness
- Signal promotion pipeline complete and ready for Plan 03 (mobile feedback UI)
- Investigation agent can now query feedback signals and promote to golden dataset via natural language
- Full test suite passes (456 passed, 3 skipped)

---
## Self-Check: PASSED

- All 4 modified files exist on disk
- All 3 task commit hashes found in git log (5d2ad72, 556ab63, bba6cd4)
- Key patterns verified: query_feedback_signals, promote_to_golden_dataset, cosmos_manager injection, two-step flow docs

---
*Phase: 20-feedback-collection*
*Completed: 2026-04-22*
