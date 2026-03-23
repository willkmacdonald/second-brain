---
phase: 14-app-insights-operational-audit
plan: 02
subsystem: api, ui
tags: [telemetry, trace-id, uuid, expo-clipboard, pydantic, app-insights, observability]

# Dependency graph
requires:
  - phase: 14-01
    provides: Backend trace ID propagation via ContextVar and structured logging
provides:
  - Mobile trace ID generation (generateTraceId) for capture sessions
  - X-Trace-Id header injection on all 4 capture SSE functions
  - Tap-to-copy trace ID display on capture screen
  - POST /api/telemetry backend proxy for mobile error reporting
  - reportError fire-and-forget telemetry client
affects: [14-03, mobile-debugging, app-insights-queries]

# Tech tracking
tech-stack:
  added: [expo-clipboard]
  patterns: [fire-and-forget telemetry reporting, trace ID header propagation, wrapped SSE error callbacks]

key-files:
  created:
    - mobile/lib/telemetry.ts
    - backend/src/second_brain/api/telemetry.py
  modified:
    - mobile/lib/ag-ui-client.ts
    - mobile/lib/types.ts
    - mobile/app/(tabs)/index.tsx
    - backend/src/second_brain/main.py

key-decisions:
  - "Telemetry JSON body uses snake_case (event_type, capture_trace_id) to match Python convention"
  - "reportError is fire-and-forget with swallowed errors to prevent telemetry from crashing the app"
  - "All 4 capture functions return traceId in their result objects for UI access"
  - "Follow-up functions accept optional traceId to reuse the original capture trace ID"
  - "Trace ID displayed as first 8 chars with ... truncation, full ID on clipboard tap"
  - "Backend telemetry endpoint uses WARNING level to ensure visibility in App Insights"

patterns-established:
  - "X-Trace-Id header convention: mobile generates UUID, backend reads from header"
  - "Error callback wrapping: ag-ui-client wraps all onError callbacks with reportError"
  - "Fire-and-forget telemetry: errors during reporting silently swallowed"

requirements-completed: [OBS-05, OBS-06]

# Metrics
duration: 6min
completed: 2026-03-23
---

# Phase 14 Plan 02: Mobile Observability Summary

**Mobile trace ID generation with X-Trace-Id header injection, tap-to-copy UI display, and backend telemetry proxy endpoint for Expo-compatible error reporting**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-23T03:28:16Z
- **Completed:** 2026-03-23T03:35:04Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Mobile generates UUID trace ID for every capture and sends it as X-Trace-Id header on all 4 SSE functions
- Trace ID displayed on capture screen toast with tap-to-copy via expo-clipboard
- Backend POST /api/telemetry proxy endpoint receives mobile errors and logs to App Insights with component=mobile
- SSE error callbacks wrapped with reportError for automatic telemetry on capture failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Mobile trace ID generation, header injection, and UI display** - `e2f1d0b` (feat)
2. **Task 2: Backend telemetry proxy endpoint** - `74da9e9` (feat)

## Files Created/Modified
- `mobile/lib/telemetry.ts` - generateTraceId (UUID v4) and reportError (fire-and-forget POST to /api/telemetry)
- `mobile/lib/ag-ui-client.ts` - X-Trace-Id header injection on all 4 capture functions, error callback wrapping
- `mobile/lib/types.ts` - Optional traceId field on SendFollowUpOptions and SendFollowUpVoiceOptions
- `mobile/app/(tabs)/index.tsx` - Trace ID state, tap-to-copy display in toast, lastTraceId passed to follow-ups
- `backend/src/second_brain/api/telemetry.py` - POST /api/telemetry endpoint with TelemetryEvent Pydantic model
- `backend/src/second_brain/main.py` - Registered telemetry_router

## Decisions Made
- Telemetry JSON body uses snake_case to match Python/backend convention (mobile transforms camelCase to snake_case)
- reportError is fire-and-forget -- errors during reporting silently swallowed to prevent app crashes
- All 4 capture functions (sendCapture, sendVoiceCapture, sendFollowUp, sendFollowUpVoice) return traceId for UI access
- Follow-up functions accept optional traceId to reuse original capture trace for debugging continuity
- Trace ID displayed as first 8 characters with "..." truncation; full UUID copied to clipboard on tap
- Backend telemetry endpoint logs at WARNING level so events always appear in App Insights queries

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] capture.tsx filename is actually index.tsx**
- **Found during:** Task 1
- **Issue:** Plan referenced `mobile/app/(tabs)/capture.tsx` but the capture screen is at `mobile/app/(tabs)/index.tsx`
- **Fix:** Applied changes to the correct file (index.tsx)
- **Files modified:** mobile/app/(tabs)/index.tsx
- **Verification:** File exists and contains traceId display code
- **Committed in:** e2f1d0b

**2. [Rule 1 - Bug] Return type alignment for sendVoiceCapture, sendFollowUp, sendFollowUpVoice**
- **Found during:** Task 1
- **Issue:** Plan only explicitly mentioned sendCapture returning { cleanup, traceId } but all 4 functions needed consistent return types. The original return types varied (some returned bare cleanup function)
- **Fix:** Updated all 4 functions to return { cleanup: () => void; traceId: string } and updated all call sites in index.tsx
- **Files modified:** mobile/lib/ag-ui-client.ts, mobile/app/(tabs)/index.tsx
- **Verification:** All call sites updated, verification script passes
- **Committed in:** e2f1d0b

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
- Pre-existing test failure in test_recipe_tools.py due to local SSL certificate issue -- unrelated to these changes. All 138 other tests pass.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Mobile trace ID generation and display complete -- ready for end-to-end observability testing after deployment
- Backend telemetry proxy ready to receive mobile errors
- Plan 03 (KQL dashboards and alerting) can now reference both backend trace IDs and mobile telemetry events

---
*Phase: 14-app-insights-operational-audit*
*Completed: 2026-03-23*
