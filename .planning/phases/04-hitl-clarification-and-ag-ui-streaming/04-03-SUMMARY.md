---
phase: 04-hitl-clarification-and-ag-ui-streaming
plan: 03
subsystem: ui
tags: [expo-router, react-native, flatlist, pull-to-refresh, inbox, conversation, hitl, badge-count, modal]

# Dependency graph
requires:
  - phase: 04-hitl-clarification-and-ag-ui-streaming
    plan: 01
    provides: Backend HITL workflow, AG-UI step events, echo filter, respond endpoint, inbox API
  - phase: 04-hitl-clarification-and-ag-ui-streaming
    plan: 02
    provides: Tab navigation, streaming callbacks, sendClarification, AgentSteps component
provides:
  - Inbox screen with FlatList, pull-to-refresh, load-more pagination, and detail card modal
  - InboxItem component with orange dot status indicator for pending clarifications
  - Conversation screen for HITL clarification from inbox with 4 bucket buttons
  - Badge count on Inbox tab for pending clarifications
  - Complete Phase 4 UX flow verified end-to-end (6 verification steps passed)
affects: [05-voice-capture, 06-action-sharpening, mobile-inbox, mobile-conversation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FlatList with RefreshControl for pull-to-refresh inbox pattern"
    - "onEndReached pagination with offset parameter for load-more"
    - "React Native Modal for inline detail card overlay (no separate route)"
    - "useLocalSearchParams for dynamic route parameter extraction in conversation screen"
    - "Badge count via shared state callback from inbox to tab layout"

key-files:
  created:
    - mobile/app/(tabs)/inbox.tsx
    - mobile/app/conversation/[threadId].tsx
    - mobile/components/InboxItem.tsx
  modified:
    - mobile/app/(tabs)/_layout.tsx
    - mobile/lib/ag-ui-client.ts
    - mobile/lib/types.ts
    - backend/src/second_brain/agents/workflow.py
    - backend/src/second_brain/agents/classifier.py
    - backend/src/second_brain/main.py

key-decisions:
  - "InboxItem uses inline getRelativeTime utility (no library) for relative timestamps"
  - "Detail card as Modal overlay within inbox screen, not a separate route"
  - "Conversation screen fetches item detail via GET /api/inbox/{threadId} for context display"
  - "Expired HITL sessions handled gracefully with resubmission message"

patterns-established:
  - "Inbox list pattern: FlatList + RefreshControl + onEndReached pagination"
  - "Detail card as overlay: Modal triggered by tapping filed items"
  - "Conversation resolution: bucket buttons -> sendClarification -> router.back()"
  - "Badge count wiring: inbox screen updates tab badge via navigation options"

requirements-completed: [APPX-02, APPX-04]

# Metrics
duration: 12min
completed: 2026-02-22
---

# Phase 4 Plan 3: Inbox List View and Conversation Screen Summary

**Inbox screen with FlatList, pull-to-refresh, detail card modal, and conversation screen for resolving pending HITL clarifications from inbox**

## Performance

- **Duration:** 12 min (including checkpoint verification time)
- **Started:** 2026-02-22T08:16:00Z
- **Completed:** 2026-02-22T08:47:14Z
- **Tasks:** 3 (2 auto + 1 checkpoint:human-verify)
- **Files modified:** 9 (3 created, 6 modified)

## Accomplishments

- Inbox screen with FlatList showing captures with text preview, bucket, relative time, and orange dot for pending items
- Pull-to-refresh and load-more pagination for inbox list
- Detail card modal for filed items showing full text, bucket, confidence, agent chain, and timestamp
- Conversation screen for HITL clarification with original text, question, and 4 bucket buttons
- Badge count on Inbox tab for pending clarifications
- Complete Phase 4 UX verified end-to-end: tab navigation, high-confidence capture, inbox view, low-confidence HITL, inbox pending + conversation, pull-to-refresh (all 6 steps passed)

## Task Commits

Each task was committed atomically:

1. **Task 1: Inbox screen with FlatList, pull-to-refresh, detail card, and badge count** - `b0b98b7` (feat)
2. **Task 2: Conversation screen for HITL clarification from inbox** - `4500f5b` (feat)
3. **Task 3: Verify complete Phase 4 UX flow** - checkpoint:human-verify (approved, no commit)

**Additional fix commits applied during execution:**
- `daccddd` fix(04): restore classification flow, step events, and HITL detection
- `9cbebac` fix(04): convert "data" WorkflowEvents to "output" for converter
- `7c117c0` fix(04): resolve duplicate thread_id kwarg crash in workflow adapter

## Files Created/Modified

- `mobile/app/(tabs)/inbox.tsx` - Full inbox screen with FlatList, pull-to-refresh, load-more pagination, detail card modal, and badge count wiring
- `mobile/components/InboxItem.tsx` - Reusable list item component with text preview, bucket label, relative time, and orange dot status indicator
- `mobile/app/conversation/[threadId].tsx` - Conversation screen for HITL clarification with original text display, agent question, and 4 bucket buttons
- `mobile/app/(tabs)/_layout.tsx` - Updated tab layout with badge count support for pending clarifications
- `mobile/lib/ag-ui-client.ts` - Updated SSE client for conversation screen clarification flow
- `mobile/lib/types.ts` - Extended types for inbox items and conversation data
- `backend/src/second_brain/agents/workflow.py` - Fixed WorkflowEvent type handling and duplicate kwarg crash
- `backend/src/second_brain/agents/classifier.py` - Restored classification flow and HITL detection
- `backend/src/second_brain/main.py` - Fixed data->output WorkflowEvent conversion for SSE pipeline

## Decisions Made

- **InboxItem relative time utility**: Built a simple `getRelativeTime(dateString)` function inline rather than adding a library dependency, covering minutes, hours, and days ago formatting.
- **Detail card as Modal overlay**: Tapping a filed inbox item shows a React Native Modal within the inbox screen rather than navigating to a separate route. Keeps the UX lightweight.
- **Conversation screen data loading**: Fetches the inbox item via `GET /api/inbox/{threadId}` to display the original text and agent question. Falls back to "Which bucket does this belong to?" if no clarifying question is stored.
- **Expired session handling**: When a HITL thread is no longer in `_pending_sessions` (server restart, TTL), the conversation screen shows a "needs resubmission" message instead of crashing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Restored classification flow, step events, and HITL detection**
- **Found during:** Task 1 (end-to-end testing)
- **Issue:** Classification pipeline was not emitting step events correctly, and HITL detection was broken due to workflow adapter issues
- **Fix:** Restored proper classification flow, step event emission, and HITL session detection in workflow.py and classifier.py
- **Files modified:** backend/src/second_brain/agents/workflow.py, backend/src/second_brain/agents/classifier.py
- **Verification:** Full capture flow verified with step dots and HITL working
- **Committed in:** daccddd

**2. [Rule 1 - Bug] Fixed "data" WorkflowEvents conversion to "output" for AG-UI converter**
- **Found during:** Task 1 (end-to-end testing)
- **Issue:** WorkflowEvents of type "data" were not being converted to "output" type expected by the AG-UI event converter, causing events to be silently dropped
- **Fix:** Added type conversion in the SSE pipeline to map "data" WorkflowEvents to "output" before passing to converter
- **Files modified:** backend/src/second_brain/main.py
- **Verification:** Text streaming events now reach the mobile client correctly
- **Committed in:** 9cbebac

**3. [Rule 1 - Bug] Resolved duplicate thread_id kwarg crash in workflow adapter**
- **Found during:** Task 2 (conversation screen testing)
- **Issue:** `thread_id` was being passed as both a positional and keyword argument to the workflow run method, causing a TypeError crash
- **Fix:** Removed duplicate `thread_id` parameter from keyword arguments in workflow adapter
- **Files modified:** backend/src/second_brain/agents/workflow.py
- **Verification:** Clarification flow works without crash
- **Committed in:** 7c117c0

---

**Total deviations:** 3 auto-fixed (3 bugs)
**Impact on plan:** All three bugs blocked correct end-to-end operation. Fixes were essential for the Phase 4 UX verification to pass. No scope creep.

## Issues Encountered

None beyond the auto-fixed bugs above. All 6 verification steps passed on first attempt after bug fixes.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- Phase 4 complete: full capture-classify-file loop with real-time agent visibility and HITL clarification
- Inbox provides capture history browsing for future phases
- Conversation screen pattern can be reused for Action Agent clarification (Phase 6)
- Badge count pattern ready for notification integration (Phase 8)
- Ready for Phase 5 (Voice Capture), Phase 6 (Action Sharpening), or Phase 7 (People CRM)

## Self-Check: PASSED

All files verified present. All commit hashes found in git log.

---
*Phase: 04-hitl-clarification-and-ag-ui-streaming*
*Completed: 2026-02-22*
