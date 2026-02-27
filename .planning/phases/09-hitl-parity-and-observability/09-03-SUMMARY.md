---
phase: 09-hitl-parity-and-observability
plan: 03
subsystem: api, ui
tags: [hitl, recategorize, otel, patch, bucket-selection, gap-closure]

# Dependency graph
requires:
  - phase: 09-hitl-parity-and-observability (plan 01)
    provides: HITL parity with recategorize PATCH pattern in inbox and conversation screens
  - phase: 09-hitl-parity-and-observability (plan 02)
    provides: OTel spans on streaming adapter and middleware
provides:
  - All four bucket selection paths use unified PATCH recategorize pattern
  - Dead sendClarification code and /api/ag-ui/respond references removed
  - Accurate OTel span attribute for follow-up capture inbox item ID
affects: [mobile-capture, observability, hitl-workflow]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Direct fetch PATCH for instant bucket filing (no SSE needed)"

key-files:
  created: []
  modified:
    - mobile/app/capture/text.tsx
    - mobile/app/(tabs)/index.tsx
    - mobile/lib/ag-ui-client.ts
    - mobile/lib/types.ts
    - backend/src/second_brain/streaming/adapter.py
    - backend/src/second_brain/api/capture.py

key-decisions:
  - "Guard on hitlInboxItemId (not hitlThreadId) since PATCH uses inbox ID"
  - "No SSE connection needed for bucket filing -- simple PATCH/response is sufficient"

patterns-established:
  - "All bucket selection (inbox, conversation, text capture, voice capture) uses fetch PATCH to /api/inbox/{id}/recategorize"

requirements-completed: [HITL-01, OBSV-01]

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 9 Plan 3: Gap Closure Summary

**Unified all capture bucket selection to direct PATCH recategorize and fixed OTel span to record actual inbox item ID**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T19:42:25Z
- **Completed:** 2026-02-27T19:45:20Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- All four bucket selection paths (inbox, conversation, text capture, voice capture) now use the same instant PATCH pattern to /api/inbox/{id}/recategorize
- Removed dead sendClarification function and all references to deleted v1 endpoint /api/ag-ui/respond
- Fixed capture.original_inbox_item_id OTel span attribute to record the Cosmos inbox item ID instead of the Foundry thread ID

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace sendClarification with direct PATCH in capture screens** - `796d3bf` (fix)
2. **Task 2: Fix capture.original_inbox_item_id OTel span attribute** - `1d30b8c` (fix)

## Files Created/Modified
- `mobile/app/capture/text.tsx` - handleBucketSelect now uses fetch PATCH to recategorize endpoint
- `mobile/app/(tabs)/index.tsx` - handleBucketSelect now uses fetch PATCH to recategorize endpoint
- `mobile/lib/ag-ui-client.ts` - Removed sendClarification function and /api/ag-ui/respond SSE call
- `mobile/lib/types.ts` - Removed SendClarificationOptions interface
- `backend/src/second_brain/streaming/adapter.py` - Added original_inbox_item_id parameter, fixed span attribute
- `backend/src/second_brain/api/capture.py` - Passes body.inbox_item_id to stream_follow_up_capture

## Decisions Made
- Guard handleBucketSelect on hitlInboxItemId (not hitlThreadId) since the PATCH endpoint needs the inbox item ID, not the thread ID
- No SSE connection needed for bucket filing -- a simple PATCH request/response is sufficient (same pattern as inbox.tsx and conversation/[threadId].tsx)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Removed SendClarificationOptions from types.ts**
- **Found during:** Task 1
- **Issue:** Plan mentioned removing sendClarification from ag-ui-client.ts but did not explicitly mention removing the SendClarificationOptions interface from types.ts
- **Fix:** Removed the interface and its import reference since it is dead code after sendClarification removal
- **Files modified:** mobile/lib/types.ts
- **Verification:** `grep -r "SendClarificationOptions" mobile/` returns zero results; `npx tsc --noEmit` passes
- **Committed in:** 796d3bf (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential cleanup to avoid dead type definitions. No scope creep.

## Issues Encountered
- `npx expo lint` fails due to pre-existing npm dependency resolution issue (eslint peer deps), not related to changes. TypeScript type-checking (`tsc --noEmit`) passes cleanly.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 09 fully complete -- all HITL parity and observability gaps closed
- Ready to proceed to Phase 10 (Scheduled Nudges)

---
*Phase: 09-hitl-parity-and-observability*
*Completed: 2026-02-27*
