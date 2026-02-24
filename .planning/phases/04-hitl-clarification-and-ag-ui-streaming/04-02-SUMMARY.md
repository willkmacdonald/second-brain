---
phase: 04-hitl-clarification-and-ag-ui-streaming
plan: 02
subsystem: ui
tags: [expo-router, tabs, sse, streaming, hitl, step-dots, react-native, ag-ui]

# Dependency graph
requires:
  - phase: 04-hitl-clarification-and-ag-ui-streaming
    plan: 01
    provides: Backend HITL workflow, AG-UI step events, echo filter, respond endpoint, inbox API
  - phase: 02-expo-app-shell
    provides: Expo app shell with capture screen, CaptureButton component, SSE client
provides:
  - Tab navigation with Capture (default) and Inbox bottom tabs via expo-router Tabs
  - AgentSteps component with horizontal pill indicators (idle/active/completed states)
  - StreamingCallbacks interface for real-time SSE event dispatching
  - Updated SSE client with sendCapture (returns cleanup + threadId) and sendClarification
  - Text capture screen with step dots, streaming text, and inline HITL bucket buttons
  - Auto-reset after 2.5 seconds on successful classification
  - Ignored clarification handling (new capture clears HITL, pending stays in inbox)
affects: [04-03, mobile-inbox, mobile-conversation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tab navigation with expo-router Tabs component inside Stack root layout"
    - "StreamingCallbacks pattern: onStepStart/onStepFinish/onTextDelta/onHITLRequired/onComplete/onError"
    - "attachCallbacks shared helper for SSE event routing (used by both sendCapture and sendClarification)"
    - "AgentSteps progress stepper: pill indicators with connector lines, 3 visual states"
    - "Inline HITL resolution: bucket buttons displayed below step dots without navigation"

key-files:
  created:
    - mobile/app/(tabs)/_layout.tsx
    - mobile/app/(tabs)/index.tsx
    - mobile/app/(tabs)/inbox.tsx
    - mobile/components/AgentSteps.tsx
  modified:
    - mobile/app/_layout.tsx
    - mobile/app/capture/text.tsx
    - mobile/lib/types.ts
    - mobile/lib/ag-ui-client.ts

key-decisions:
  - "Shared attachCallbacks helper extracts SSE event routing logic used by both sendCapture and sendClarification"
  - "sendCapture returns { cleanup, threadId } object instead of just cleanup function to support HITL thread reference"
  - "Input area uses minHeight/maxHeight instead of flex: 1 to make room for step dots and streaming text below"
  - "Inbox placeholder tab created (Plan 04-03 implements full inbox) to satisfy tab layout requirement"
  - "TabIcon uses inline require('react-native') for Text to avoid circular import in tab layout"

patterns-established:
  - "Tab navigation: (tabs) group inside Stack root layout with modal screens alongside"
  - "Streaming UX: step dots -> streaming text -> HITL buttons (progressive disclosure)"
  - "Auto-reset pattern: setTimeout(resetState, 2500) after successful classification"
  - "HITL override: new capture clears HITL state, pending item stays in inbox"

requirements-completed: [CAPT-02, CLAS-04]

# Metrics
duration: 3min
completed: 2026-02-22
---

# Phase 4 Plan 2: Mobile Real-Time Capture UX Summary

**Tab navigation with step dots, word-by-word streaming text, and inline HITL bucket buttons for low-confidence classifications**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-22T07:59:06Z
- **Completed:** 2026-02-22T08:02:00Z
- **Tasks:** 2
- **Files modified:** 8 (4 created, 4 modified)

## Accomplishments

- Tab navigation with Capture (default) and Inbox bottom tabs using expo-router Tabs component
- AgentSteps component showing horizontal pill indicators that light up as Orchestrator -> Classifier process
- SSE client refactored with StreamingCallbacks for real-time step, text delta, and HITL event dispatch
- sendClarification function for posting bucket selections to /api/ag-ui/respond
- Text capture screen shows step dots, streams text word-by-word, and displays 4 bucket buttons for HITL clarification
- Auto-reset after 2.5 seconds on successful classification clears all state for rapid-fire input

## Task Commits

Each task was committed atomically:

1. **Task 1: Tab navigation, types, and SSE client with streaming callbacks** - `2fb41ad` (feat)
2. **Task 2: Capture screen with step dots, streaming text, and inline HITL bucket buttons** - `2e07db0` (feat)

## Files Created/Modified

- `mobile/app/(tabs)/_layout.tsx` - Tab bar layout with Capture and Inbox tabs, dark theme styling
- `mobile/app/(tabs)/index.tsx` - Capture screen moved from app/index.tsx, all 4 capture buttons preserved
- `mobile/app/(tabs)/inbox.tsx` - Placeholder inbox tab (Plan 04-03 implements full list)
- `mobile/components/AgentSteps.tsx` - Horizontal pill step indicator with idle/active/completed states and connector lines
- `mobile/app/_layout.tsx` - Root Stack wrapping (tabs) group with capture/text modal and conversation/[threadId] screen
- `mobile/app/capture/text.tsx` - Major update: step dots, streaming text, HITL bucket buttons, auto-reset
- `mobile/lib/types.ts` - Expanded AGUIEventType, StreamingCallbacks, SendCaptureOptions, SendClarificationOptions
- `mobile/lib/ag-ui-client.ts` - Refactored with attachCallbacks helper, sendCapture returns {cleanup, threadId}, new sendClarification function

## Decisions Made

- **attachCallbacks helper**: Extracted shared SSE event routing used by both sendCapture and sendClarification to avoid code duplication. Single place handles STEP_STARTED, STEP_FINISHED, TEXT_MESSAGE_CONTENT, CUSTOM, RUN_FINISHED, and error events.
- **sendCapture return type change**: Returns `{ cleanup, threadId }` object instead of just `() => void`. The threadId is needed by the capture screen to reference in sendClarification when the user selects a bucket.
- **Input area layout**: Changed from `flex: 1` to `minHeight: 120, maxHeight: 200` so the feedback area (step dots, streaming text, HITL buttons) renders below the input instead of being pushed off-screen.
- **Inbox placeholder**: Created a minimal inbox tab to satisfy the tab layout requirement. Plan 04-03 will implement the full inbox with pull-to-refresh, pending badges, and conversation navigation.
- **Old app/index.tsx removed**: Deleted to avoid expo-router route conflict with (tabs)/index.tsx which handles the root route.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Created inbox.tsx placeholder tab**
- **Found during:** Task 1 (tab layout setup)
- **Issue:** Tab layout references "inbox" tab but no inbox.tsx exists. Expo-router would fail to resolve the route.
- **Fix:** Created minimal placeholder inbox screen with title and subtitle.
- **Files modified:** mobile/app/(tabs)/inbox.tsx
- **Verification:** TypeScript compiles clean, tab layout references resolve
- **Committed in:** 2fb41ad (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (missing critical functionality)
**Impact on plan:** Necessary for tab navigation to function. No scope creep.

## Issues Encountered

None -- plan executed smoothly. TypeScript compiled clean after both tasks.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- Mobile real-time capture UX complete: step dots, streaming text, and inline HITL clarification
- Plan 04-03 (Inbox screen, conversation screen) can proceed to implement the full inbox list and conversation flow
- sendClarification function ready for use from both capture screen (inline) and conversation screen (inbox)
- Tab navigation provides the foundation for inbox with badge count support (tabBarBadge prop is declared)

## Self-Check: PASSED

All files verified present. All commit hashes found in git log.

---
*Phase: 04-hitl-clarification-and-ag-ui-streaming*
*Completed: 2026-02-22*
