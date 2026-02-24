---
phase: 04-hitl-clarification-and-ag-ui-streaming
plan: 04
subsystem: api
tags: [classification, hitl, cosmos-db, ag-ui, clarification, sse]

# Dependency graph
requires:
  - phase: 03-text-classification-pipeline
    provides: ClassificationTools, classify_and_file tool, InboxDocument model
  - phase: 04-hitl-clarification-and-ag-ui-streaming (plan 01)
    provides: AGUIWorkflowAdapter with HITL detection, custom AG-UI endpoint
provides:
  - request_clarification tool for low-confidence classification deferral
  - HITL_REQUIRED event with inboxItemId for client-side resolution
  - Respond endpoint that updates existing pending Inbox docs via upsert
  - clarificationText field on InboxDocument and InboxItemResponse
affects: [04-05-gap-closure-frontend, phase-05-voice-capture]

# Tech tracking
tech-stack:
  added: []
  patterns: [pending-then-upsert for HITL document lifecycle, clarification regex parsing in adapter]

key-files:
  created: []
  modified:
    - backend/src/second_brain/tools/classification.py
    - backend/src/second_brain/models/documents.py
    - backend/src/second_brain/agents/classifier.py
    - backend/src/second_brain/agents/workflow.py
    - backend/src/second_brain/main.py
    - backend/src/second_brain/api/inbox.py
    - backend/tests/test_classification.py
    - backend/tests/conftest.py

key-decisions:
  - "request_clarification returns 'Clarification -> {uuid} | {text}' format parsed by adapter regex"
  - "Respond endpoint uses upsert_item on existing Inbox doc (not classify_and_file re-call)"
  - "HITL_REQUIRED event includes inboxItemId and questionText for client resolution"
  - "Clarification detection takes priority over confidence detection in adapter scanning"

patterns-established:
  - "Pending-then-upsert: low-confidence creates status=pending Inbox doc, HITL resolution upserts to classified"
  - "Tool return string parsing: adapter extracts structured data from tool output via regex"

requirements-completed: [CLAS-04, APPX-04]

# Metrics
duration: 5min
completed: 2026-02-23
---

# Phase 4 Plan 04: Backend Gap Closure Summary

**request_clarification tool with pending Inbox docs, HITL_REQUIRED event carrying inboxItemId, and respond endpoint using upsert to update existing records**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-23T15:35:55Z
- **Completed:** 2026-02-23T15:40:48Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Classifier now has two paths: classify_and_file (>= 0.6) and request_clarification (< 0.6) with LLM-generated clarification questions
- HITL_REQUIRED SSE event carries inboxItemId so the client can pass it back for resolution
- Respond endpoint reads existing pending Inbox doc, creates bucket record, and upserts Inbox status from pending to classified
- InboxItemResponse returns clarificationText for conversation screen display

## Task Commits

Each task was committed atomically:

1. **Task 1: Add request_clarification tool, clarificationText field, and update classifier instructions** - `1ea896a` (feat)
2. **Task 2: Update adapter HITL detection, respond endpoint, and Inbox API response** - `0f71c9c` (feat)

## Files Created/Modified
- `backend/src/second_brain/tools/classification.py` - Added request_clarification tool creating pending Inbox docs
- `backend/src/second_brain/models/documents.py` - Added clarificationText field to InboxDocument
- `backend/src/second_brain/agents/classifier.py` - Updated instructions with Low Confidence Handling section, added tool to list
- `backend/src/second_brain/agents/workflow.py` - Added clarification regex, detection in text scanning, HITL_REQUIRED with inboxItemId
- `backend/src/second_brain/main.py` - Rewrote respond endpoint to upsert existing Inbox doc instead of re-calling classify_and_file
- `backend/src/second_brain/api/inbox.py` - Added clarificationText to InboxItemResponse and list mapping
- `backend/tests/test_classification.py` - Added 3 new tests for request_clarification tool
- `backend/tests/conftest.py` - Added upsert_item mock to container fixtures

## Decisions Made
- request_clarification returns "Clarification -> {uuid} | {text}" format that the adapter parses via regex -- keeps tool output human-readable while carrying structured data
- Respond endpoint uses upsert_item on the existing Inbox document rather than calling classify_and_file which would create a duplicate
- Clarification detection is prioritized over confidence detection in the adapter scanning logic since clarification is the new primary HITL path
- classifiedBy set to "User" with agentChain ["Orchestrator", "Classifier", "User"] for HITL-resolved captures

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing SIM102 lint warning in workflow.py**
- **Found during:** Task 2
- **Issue:** Nested if statements in run() method that ruff flagged as SIM102
- **Fix:** Combined into single `if "thread_id" not in kwargs and thread and hasattr(thread, "id"):`
- **Files modified:** backend/src/second_brain/agents/workflow.py
- **Verification:** ruff check passes
- **Committed in:** 0f71c9c (Task 2 commit)

**2. [Rule 1 - Bug] Removed unused classification_tools variable from respond endpoint**
- **Found during:** Task 2
- **Issue:** After rewriting respond to use direct Cosmos operations instead of classify_and_file, the classification_tools import was unused (F841)
- **Fix:** Removed the unused variable assignment
- **Files modified:** backend/src/second_brain/main.py
- **Verification:** ruff check passes
- **Committed in:** 0f71c9c (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for lint compliance. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backend gap closure complete -- all 3 verification blockers fixed on backend side
- Plan 04-05 (frontend gap closure) can now wire the client to send inboxItemId with respond requests
- clarificationText available for conversation screen display via GET /api/inbox/{id}

---
*Phase: 04-hitl-clarification-and-ag-ui-streaming*
*Completed: 2026-02-23*
