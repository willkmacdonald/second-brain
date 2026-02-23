---
phase: 04-hitl-clarification-and-ag-ui-streaming
plan: 05
subsystem: ui
tags: [react-native, hitl, clarification, ag-ui, mobile, bucket-emphasis]

# Dependency graph
requires:
  - phase: 04-hitl-clarification-and-ag-ui-streaming (plan 04)
    provides: request_clarification tool, HITL_REQUIRED event with inboxItemId, respond endpoint with upsert, clarificationText field
provides:
  - Mobile screens display real classifier reasoning (clarificationText from backend)
  - inboxItemId flows from HITL_REQUIRED event through sendClarification to backend for DB update
  - Top 2 suggested buckets visually emphasized (filled primary vs outline secondary)
  - Both 'pending' and 'low_confidence' statuses recognized as pending across inbox UI
affects: [phase-05-voice-capture, phase-06-action-extraction]

# Tech tracking
tech-stack:
  added: []
  patterns: [top-2 bucket emphasis via primary/secondary button styling, dual-status pending recognition]

key-files:
  created: []
  modified:
    - mobile/lib/types.ts
    - mobile/lib/ag-ui-client.ts
    - mobile/app/capture/text.tsx
    - mobile/app/conversation/[threadId].tsx
    - mobile/components/InboxItem.tsx
    - mobile/app/(tabs)/inbox.tsx

key-decisions:
  - "Top 2 buckets derived from questionText pattern on capture screen (heuristic: first 2 BUCKETS mentioned)"
  - "Top 2 buckets derived from allScores sorting on conversation screen (data-driven from classification metadata)"
  - "clarificationText used as primary question, generic 'Which bucket does this belong to?' as fallback only"
  - "isPending checks both 'pending' (new request_clarification flow) and 'low_confidence' (legacy) for backward compatibility"

patterns-established:
  - "Primary/secondary button emphasis: top-2 buckets get filled #4a90d9 background, others get transparent with border"
  - "Dual-status pending: isPendingStatus helper checks both 'pending' and 'low_confidence'"

requirements-completed: [CLAS-04, APPX-04]

# Metrics
duration: 3min
completed: 2026-02-23
---

# Phase 4 Plan 05: Frontend Gap Closure Summary

**Real classifier clarification text, inboxItemId for DB updates, and top-2 bucket emphasis across capture and conversation screens**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-23T15:43:28Z
- **Completed:** 2026-02-23T15:46:37Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- HITL_REQUIRED event now carries inboxItemId and questionText from the backend, wired through AG-UI client to both capture and conversation screens
- Both screens pass inboxItemId to sendClarification, enabling the respond endpoint to update the correct Inbox document in Cosmos DB
- Conversation screen shows the classifier's actual clarificationText instead of a hardcoded generic question
- Top 2 suggested buckets are visually emphasized with filled blue primary buttons; other 2 get outline secondary styling
- InboxItemData type extended with clarificationText and allScores fields for data-driven UI
- Both 'pending' (new flow) and 'low_confidence' (legacy) statuses recognized as pending: orange dot, badge count, and conversation navigation all work for both

## Task Commits

Each task was committed atomically:

1. **Task 1: Update AG-UI client types and callback to carry inboxItemId and questionText** - `0a6d58c` (feat)
2. **Task 2: Update capture screen, conversation screen, inbox status checks, and InboxItemData type** - `94a7629` (feat)

## Files Created/Modified
- `mobile/lib/types.ts` - Added inboxItemId param to onHITLRequired callback signature
- `mobile/lib/ag-ui-client.ts` - Extended AGUIEventPayload.value with inboxItemId/questionText, updated HITL_REQUIRED handler
- `mobile/app/capture/text.tsx` - Stores inboxItemId, passes to sendClarification, top-2 bucket emphasis, top buckets extracted from questionText
- `mobile/app/conversation/[threadId].tsx` - Shows clarificationText, passes item.id as inboxItemId, derives top 2 from allScores
- `mobile/components/InboxItem.tsx` - Added clarificationText and allScores to InboxItemData, isPending checks both statuses
- `mobile/app/(tabs)/inbox.tsx` - Badge count and navigation routing recognize both 'pending' and 'low_confidence'

## Decisions Made
- Top 2 buckets on capture screen derived from questionText heuristic (first 2 BUCKETS mentioned in classifier text) -- keeps logic simple without needing separate allScores data on the capture path
- Top 2 buckets on conversation screen derived from allScores sorting (more accurate, data available from fetched inbox item)
- clarificationText is the primary question source; the generic "Which bucket does this belong to?" is fallback only
- Both 'pending' and 'low_confidence' recognized as pending for backward compatibility with any existing data

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 3 verification blockers from Phase 4 are now fixed on both backend (plan 04-04) and frontend (this plan)
- Phase 4 gap closure is complete -- HITL clarification and AG-UI streaming fully wired end-to-end
- Ready for Phase 5 (Voice Capture) when Whisper + expo-audio research is completed

## Self-Check: PASSED

All 7 modified/created files verified present on disk. Both task commits (0a6d58c, 94a7629) verified in git log.

---
*Phase: 04-hitl-clarification-and-ag-ui-streaming*
*Completed: 2026-02-23*
