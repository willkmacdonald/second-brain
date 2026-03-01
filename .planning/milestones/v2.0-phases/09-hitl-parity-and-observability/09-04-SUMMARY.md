---
phase: 09-hitl-parity-and-observability
plan: 04
subsystem: streaming, mobile
tags: [sse, low-confidence, bucket-buttons, hitl, ag-ui]

# Dependency graph
requires:
  - phase: 08-ag-ui-streaming
    provides: SSE event constructors and adapter pattern
  - phase: 09-03
    provides: HITL PATCH parity and bucket button UI on capture screens
provides:
  - LOW_CONFIDENCE SSE event type for pending captures
  - Mobile handling of LOW_CONFIDENCE with bucket button display
  - Reconciliation for LOW_CONFIDENCE events in follow-up stream
affects: [09-05, 09-06, uat]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "LOW_CONFIDENCE event mirrors CLASSIFIED structure with same reconciliation path"
    - "hitlTriggered=true prevents COMPLETE from double-firing onComplete"
    - "setShowSteps(true) required to make bucket buttons visible in conditional render"

key-files:
  created: []
  modified:
    - backend/src/second_brain/streaming/sse.py
    - backend/src/second_brain/streaming/adapter.py
    - backend/src/second_brain/api/capture.py
    - mobile/lib/types.ts
    - mobile/lib/ag-ui-client.ts
    - mobile/app/capture/text.tsx
    - mobile/app/(tabs)/index.tsx

key-decisions:
  - "LOW_CONFIDENCE event uses same value shape as CLASSIFIED (inboxItemId, bucket, confidence)"
  - "Follow-up re-classification returning LOW_CONFIDENCE auto-accepts with toast (user already provided context)"
  - "hitlTriggered=true on LOW_CONFIDENCE prevents COMPLETE from calling onComplete (same pattern as MISUNDERSTOOD)"

patterns-established:
  - "LOW_CONFIDENCE triggers bucket buttons on capture screen; CLASSIFIED triggers Filed toast"
  - "Follow-up LOW_CONFIDENCE auto-accepts since user already provided extra context"

requirements-completed: [HITL-01]

# Metrics
duration: 2min
completed: 2026-02-27
---

# Phase 9 Plan 4: LOW_CONFIDENCE Event Summary

**LOW_CONFIDENCE SSE event for pending captures with mobile bucket button display and follow-up reconciliation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-27T23:47:04Z
- **Completed:** 2026-02-27T23:49:37Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Backend emits LOW_CONFIDENCE event (not CLASSIFIED) when file_capture returns status="pending"
- Mobile shows bucket buttons on both text and voice capture screens for low-confidence captures
- Follow-up re-classification returning LOW_CONFIDENCE auto-accepts with a Filed toast
- _stream_with_reconciliation handles LOW_CONFIDENCE with same orphan cleanup as CLASSIFIED
- TypeScript compiles cleanly with no type errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add LOW_CONFIDENCE SSE event, emit for pending, update reconciliation** - `c60781e` (feat)
2. **Task 2: Handle LOW_CONFIDENCE in mobile SSE client with bucket buttons** - `0cc9936` (feat)

## Files Created/Modified
- `backend/src/second_brain/streaming/sse.py` - Added low_confidence_event constructor
- `backend/src/second_brain/streaming/adapter.py` - Split pending/classified in _emit_result_event, import low_confidence_event
- `backend/src/second_brain/api/capture.py` - Added LOW_CONFIDENCE handling in _stream_with_reconciliation
- `mobile/lib/types.ts` - Added LOW_CONFIDENCE to AGUIEventType, onLowConfidence to StreamingCallbacks
- `mobile/lib/ag-ui-client.ts` - Added LOW_CONFIDENCE switch case with hitlTriggered=true
- `mobile/app/capture/text.tsx` - Added onLowConfidence callbacks for sendCapture and sendFollowUp
- `mobile/app/(tabs)/index.tsx` - Added onLowConfidence callbacks for sendVoiceCapture and handleFollowUpSubmit

## Decisions Made
- LOW_CONFIDENCE event uses same value shape as CLASSIFIED (inboxItemId, bucket, confidence) for consistency
- Follow-up re-classification returning LOW_CONFIDENCE auto-accepts with a toast (user already provided extra context, so no need to ask again)
- hitlTriggered=true on LOW_CONFIDENCE prevents COMPLETE from calling onComplete (same pattern as MISUNDERSTOOD)
- setShowSteps(true) is critical in onLowConfidence callback -- bucket button UI is gated on {showSteps && ...}

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- LOW_CONFIDENCE event flow complete end-to-end (backend -> mobile)
- Ready for 09-05 (voice follow-up) and 09-06 (instruction tuning)
- CLASSIFIED, MISUNDERSTOOD, and UNRESOLVED paths unchanged

---
*Phase: 09-hitl-parity-and-observability*
*Completed: 2026-02-27*
