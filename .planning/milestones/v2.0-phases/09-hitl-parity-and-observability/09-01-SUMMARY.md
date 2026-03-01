---
phase: 09-hitl-parity-and-observability
plan: 01
subsystem: api, streaming, mobile
tags: [foundry, sse, hitl, cosmos, conversation-threading, follow-up, recategorize]

# Dependency graph
requires:
  - phase: 08-foundrysseadapter-and-streaming
    provides: stream_text_capture/stream_voice_capture async generators and SSE event helpers
provides:
  - POST /api/capture/follow-up endpoint with Foundry thread reuse and orphan reconciliation
  - foundryThreadId field on InboxDocument for conversation threading
  - stream_follow_up_capture async generator with conversation_id in ChatOptions
  - stream_with_thread_id_persistence wrapper persisting foundryThreadId on MISUNDERSTOOD
  - Mobile pending resolve uses instant PATCH (no SSE)
  - sendFollowUp URL points to /api/capture/follow-up
affects: [09-02-observability, 10-specialist-agents]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wrapper generators for post-stream side effects (persistence, reconciliation)"
    - "conversation_id in ChatOptions for Foundry thread reuse"
    - "SSE event interception via JSON parsing in wrapper generators"

key-files:
  created: []
  modified:
    - backend/src/second_brain/models/documents.py
    - backend/src/second_brain/streaming/adapter.py
    - backend/src/second_brain/streaming/sse.py
    - backend/src/second_brain/api/capture.py
    - mobile/lib/ag-ui-client.ts
    - mobile/app/(tabs)/inbox.tsx
    - mobile/app/conversation/[threadId].tsx

key-decisions:
  - "Wrapper generator pattern for post-stream side effects -- keeps adapter pure (yields SSE) while endpoint handles persistence"
  - "foundryConversationId included in MISUNDERSTOOD event payload for wrapper extraction"
  - "Orphan reconciliation copies classification to original doc and deletes new doc (same pattern as v1)"
  - "handlePendingResolve delegates to handleRecategorize for instant PATCH confirm"

patterns-established:
  - "stream_with_thread_id_persistence: wrapper generator intercepts MISUNDERSTOOD events and upserts foundryThreadId after stream"
  - "stream_with_reconciliation: wrapper generator intercepts CLASSIFIED events from follow-up and reconciles orphan docs"

requirements-completed: [HITL-01, HITL-02, HITL-03]

# Metrics
duration: 5min
completed: 2026-02-27
---

# Phase 9 Plan 01: HITL Parity Summary

**Follow-up endpoint with Foundry thread reuse, orphan reconciliation, and instant PATCH for pending items**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-27T17:46:30Z
- **Completed:** 2026-02-27T17:51:30Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Created POST /api/capture/follow-up endpoint that reads foundryThreadId from Cosmos, streams follow-up classification on the same Foundry thread, and reconciles orphan inbox documents on success
- Added foundryThreadId capture from ChatResponseUpdate.conversation_id in both stream_text_capture and stream_voice_capture, with persistence via wrapper generator
- Simplified mobile pending resolve to use instant PATCH (handleRecategorize) instead of SSE streaming
- Updated sendFollowUp URL to /api/capture/follow-up and conversation screen to use direct PATCH

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend follow-up endpoint, adapter, and data model** - `e6870d1` (feat)
2. **Task 2: Mobile pending resolve fix and follow-up URL update** - `f8218fd` (feat)

## Files Created/Modified
- `backend/src/second_brain/models/documents.py` - Added foundryThreadId: str | None = None to InboxDocument
- `backend/src/second_brain/streaming/sse.py` - Added foundry_conversation_id parameter to misunderstood_event
- `backend/src/second_brain/streaming/adapter.py` - Captures conversation_id from updates, added stream_follow_up_capture generator
- `backend/src/second_brain/api/capture.py` - Added follow-up endpoint, stream_with_thread_id_persistence, stream_with_reconciliation wrappers
- `mobile/lib/ag-ui-client.ts` - Updated sendFollowUp URL to /api/capture/follow-up
- `mobile/app/(tabs)/inbox.tsx` - handlePendingResolve delegates to handleRecategorize, removed sendClarification import
- `mobile/app/conversation/[threadId].tsx` - handleBucketSelect uses direct PATCH, removed sendClarification and streamedText

## Decisions Made
- Used wrapper generator pattern for post-stream side effects (persistence, reconciliation) to keep the adapter pure -- it only yields SSE strings, while the endpoint handles Cosmos operations
- Included foundryConversationId in the MISUNDERSTOOD event payload so the wrapper can extract it via JSON parsing without coupling to the adapter internals
- Orphan reconciliation follows the same pattern as v1: copy classificationMeta/filedRecordId to original, update bucket doc's inboxRecordId, delete orphan
- Pending resolve simplified to instant PATCH by delegating to handleRecategorize -- no SSE overhead for simple bucket confirmation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff B904 lint error in follow-up endpoint**
- **Found during:** Task 1 (follow-up endpoint)
- **Issue:** `raise HTTPException` inside `except` block without `from` clause triggers B904
- **Fix:** Added `from exc` to the raise statement
- **Files modified:** backend/src/second_brain/api/capture.py
- **Verification:** ruff check passes
- **Committed in:** e6870d1 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor lint fix. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All three HITL flows are wired: pending (instant PATCH), misunderstood (follow-up SSE with thread reuse), recategorize (unchanged PATCH)
- Ready for Phase 9 Plan 02 (observability: enable_instrumentation, OTel middleware spans)
- The follow-up endpoint and reconciliation logic are ready for end-to-end testing after deployment

## Self-Check: PASSED

All 7 modified files verified on disk. Both task commits (e6870d1, f8218fd) found in git log. SUMMARY.md created.

---
*Phase: 09-hitl-parity-and-observability*
*Completed: 2026-02-27*
