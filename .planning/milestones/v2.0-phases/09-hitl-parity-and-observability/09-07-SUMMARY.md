---
phase: 09-hitl-parity-and-observability
plan: 07
subsystem: api
tags: [contextvars, cosmos-db, follow-up, in-place-update, orphan-fix]

# Dependency graph
requires:
  - phase: 09-01
    provides: "Follow-up endpoints, _stream_with_reconciliation wrapper, SSE streaming"
  - phase: 09-05
    provides: "Voice follow-up endpoint with transcription"
provides:
  - "ContextVar-based follow-up mechanism preventing orphan inbox docs"
  - "In-place inbox doc updates during follow-up reclassification"
  - "Simplified follow-up wrapper (_stream_with_follow_up_context)"
affects: [10-specialist-agents, uat-retesting]

# Tech tracking
tech-stack:
  added: [contextvars]
  patterns: [context-var-for-implicit-tool-state, in-place-cosmos-update]

key-files:
  created: []
  modified:
    - backend/src/second_brain/tools/classification.py
    - backend/src/second_brain/api/capture.py
    - backend/src/second_brain/streaming/adapter.py

key-decisions:
  - "ContextVar instead of tool parameter for follow-up state (file_capture is a @tool called by Foundry agent, cannot add params)"
  - "Preserve original rawText on inbox doc, store follow-up as clarificationText field"
  - "Delete _stream_with_reconciliation entirely -- no orphan means no reconciliation needed"

patterns-established:
  - "ContextVar pattern: use contextvars.ContextVar for passing implicit state to @tool functions that cannot accept extra parameters"
  - "In-place update pattern: read_item -> modify fields -> upsert_item for Cosmos doc updates during follow-up"

requirements-completed: [HITL-02]

# Metrics
duration: 4min
completed: 2026-02-28
---

# Phase 9 Plan 7: Follow-up Orphan Fix Summary

**ContextVar-based in-place inbox doc updates replacing fragile orphan reconciliation for follow-up reclassification**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-28T19:48:39Z
- **Completed:** 2026-02-28T19:53:11Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Eliminated orphan inbox document creation during follow-up reclassification
- Replaced fragile post-hoc _stream_with_reconciliation (~160 lines) with clean _stream_with_follow_up_context (~50 lines)
- file_capture now updates existing misunderstood inbox doc in-place via ContextVar when in follow-up mode

## Task Commits

Each task was committed atomically:

1. **Task 1: Make file_capture update existing doc in-place during follow-up** - `d6fa189` (fix)
2. **Task 2: Verify no stale references and ensure adapter passes cosmos_manager correctly** - `77b8c3c` (chore)

**Plan metadata:** `929d556` (docs: complete plan)

## Files Created/Modified
- `backend/src/second_brain/tools/classification.py` - Added _follow_up_inbox_item_id ContextVar, follow_up_context manager, _write_follow_up_to_cosmos method for in-place updates
- `backend/src/second_brain/api/capture.py` - Replaced _stream_with_reconciliation with _stream_with_follow_up_context, updated docstrings, removed stale imports
- `backend/src/second_brain/streaming/adapter.py` - Removed unused datetime imports (cleanup)

## Decisions Made
- Used contextvars.ContextVar instead of adding a parameter to file_capture because file_capture is a @tool invoked by the Foundry agent service -- its signature cannot include parameters the agent does not know about
- Preserved original rawText on the inbox doc and stored the follow-up text in clarificationText (already existed on InboxDocument model)
- Deleted _stream_with_reconciliation entirely rather than fixing it -- preventing orphans is architecturally superior to cleaning them up after the fact
- Used synchronous @contextmanager (not async) for follow_up_context since it only sets/resets a ContextVar

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed unused datetime imports from adapter.py**
- **Found during:** Task 1 (ruff check verification)
- **Issue:** adapter.py had unused `from datetime import UTC, datetime` import causing ruff F401 errors
- **Fix:** Removed the unused import line
- **Files modified:** backend/src/second_brain/streaming/adapter.py
- **Verification:** ruff check passes cleanly
- **Committed in:** d6fa189 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Pre-existing unused import in adapter.py blocked ruff check from passing. Minimal change, no scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Follow-up reclassification now updates inbox docs in-place -- ready for UAT retesting
- Both text and voice follow-up paths use the same ContextVar mechanism
- Initial captures (non-follow-up) are completely unaffected

---
*Phase: 09-hitl-parity-and-observability*
*Completed: 2026-02-28*

## Self-Check: PASSED

All files exist, all commits verified.
