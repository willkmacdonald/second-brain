---
phase: 11-admin-agent-and-capture-handoff
plan: 02
subsystem: processing
tags: [asyncio, fire-and-forget, background-tasks, admin-agent, sse, capture-pipeline]

# Dependency graph
requires:
  - phase: 11-admin-agent-and-capture-handoff
    plan: 01
    provides: "process_admin_capture() function and adminProcessingStatus field on InboxDocument"
  - phase: 10-data-foundation-and-admin-tools
    provides: "Admin Agent registration, AdminTools with add_shopping_list_items"
provides:
  - "Fire-and-forget Admin Agent trigger wired into capture SSE flow"
  - "background_tasks set on app.state for GC-safe asyncio task tracking"
  - "Admin refs (admin_client, admin_tools) passed through capture endpoints to adapter"
  - "End-to-end pipeline: Capture -> Classifier -> Admin bucket -> Admin Agent -> shopping list"
affects: [11.1-classifier-multi-bucket-splitting, shopping-list-features]

# Tech tracking
tech-stack:
  added: []
  patterns: ["GC-safe fire-and-forget via background_tasks set + add_done_callback(discard)", "getattr with safe defaults for optional app.state attributes"]

key-files:
  created: []
  modified:
    - backend/src/second_brain/main.py
    - backend/src/second_brain/api/capture.py
    - backend/src/second_brain/streaming/adapter.py

key-decisions:
  - "getattr with safe defaults for admin refs -- graceful degradation when Admin Agent registration fails"
  - "Admin Agent only on initial captures, not follow-ups -- follow-ups are reclassification, not new captures"
  - "Admin Agent instructions already correct in Foundry portal -- no update needed"

patterns-established:
  - "background_tasks set pattern: app.state.background_tasks = set() with task.add_done_callback(background_tasks.discard)"
  - "Optional service injection: getattr(app.state, 'service', default) for services that may not initialize"

requirements-completed: [AGNT-01, AGNT-03, SHOP-03, SHOP-04]

# Metrics
duration: 5min
completed: 2026-03-02
---

# Phase 11 Plan 02: Capture Handoff Wiring Summary

**Fire-and-forget Admin Agent trigger wired into text and voice capture SSE flow with GC-safe background task tracking, verified end-to-end through Cosmos**

## Performance

- **Duration:** 5 min (across sessions, including checkpoint verification)
- **Started:** 2026-03-02T02:12:00Z
- **Completed:** 2026-03-02T03:44:36Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Wired process_admin_capture into live capture flow via asyncio.create_task when Classifier returns bucket=="Admin"
- GC-safe task tracking: background_tasks set on app.state with add_done_callback(discard) prevents premature garbage collection
- Verified end-to-end pipeline: "need milk" capture classified as Admin, routed through Admin Agent, appeared in ShoppingLists Cosmos container as store=jewel, name=milk
- Graceful degradation: when admin_client is None (registration failed), no background task spawned, capture completes normally

## Task Commits

Each task was committed atomically:

1. **Task 1: Add background_tasks set to main.py lifespan and pass admin refs through capture endpoints** - `ecaf26c` (feat)
2. **Task 2: Add Admin detection and background task trigger to streaming adapter** - `4c3940c` (feat)
3. **Task 3: Update Admin Agent instructions and verify end-to-end flow** - checkpoint:human-verify (approved, no code changes)

## Files Created/Modified
- `backend/src/second_brain/main.py` - Added app.state.background_tasks = set() in lifespan for GC-safe task tracking
- `backend/src/second_brain/api/capture.py` - Passes admin_client, admin_agent_tools, background_tasks from app.state to adapter functions via getattr with safe defaults
- `backend/src/second_brain/streaming/adapter.py` - Admin detection in file_capture block: spawns asyncio.create_task(process_admin_capture) when bucket=="Admin"

## Decisions Made
- Used getattr with safe defaults for admin refs from app.state -- ensures graceful degradation when Admin Agent registration failed during startup
- Admin Agent processing only on initial captures, not follow-ups -- follow-ups are reclassification attempts for misunderstood captures, not new Admin work
- Admin Agent instructions in Foundry portal were already correct for store routing -- no manual update was needed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - Admin Agent instructions were already correct in Foundry portal. No manual configuration changes needed.

## Verification Results
- Single-item capture "need milk" verified: item appeared in ShoppingLists Cosmos container with store=jewel, name=milk
- Pipeline confirmed: Capture -> Classifier -> Admin bucket -> Admin Agent -> add_shopping_list_items -> Cosmos
- SSE stream completed quickly without waiting for Admin Agent processing

## Next Phase Readiness
- Complete capture-to-shopping-list pipeline is operational
- Ready for Phase 11.1 (Classifier Multi-Bucket Splitting) which handles captures with both Admin and non-Admin content
- Shopping list features can build on verified store routing (jewel, cvs, pet_store, other)

## Self-Check: PASSED

All 3 files verified present. Both commit hashes (ecaf26c, 4c3940c) verified in git log. Task 3 was checkpoint:human-verify (approved, no code commit).

---
*Phase: 11-admin-agent-and-capture-handoff*
*Completed: 2026-03-02*
