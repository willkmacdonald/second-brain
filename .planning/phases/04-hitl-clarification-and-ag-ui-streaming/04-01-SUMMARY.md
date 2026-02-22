---
phase: 04-hitl-clarification-and-ag-ui-streaming
plan: 01
subsystem: api
tags: [ag-ui, hitl, sse, workflow, step-events, inbox, cosmos-db, handoff-builder]

# Dependency graph
requires:
  - phase: 03-text-classification-pipeline
    provides: Classification pipeline with Orchestrator -> Classifier handoff, ClassificationTools, Cosmos DB documents
provides:
  - AGUIWorkflowAdapter with HITL pause/resume via _pending_sessions and request_info handling
  - AG-UI StepStarted/StepFinished events on agent transitions (executor_invoked/executor_completed)
  - Orchestrator echo filter (only Classifier text content reaches the client)
  - POST /api/ag-ui/respond endpoint for resuming paused HITL workflows via SSE
  - GET /api/inbox paginated listing endpoint (createdAt DESC, partition-scoped)
  - GET /api/inbox/{item_id} detail endpoint
  - Custom AG-UI SSE endpoint with mixed AgentResponseUpdate + BaseEvent support
  - Classifier low-confidence clarification instructions and bucket override handling
affects: [04-02, 04-03, mobile-streaming, mobile-inbox, mobile-conversation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mixed stream pattern: _stream_updates yields Union[AgentResponseUpdate, BaseEvent] for step events + text content"
    - "HITL session storage: class-level _pending_sessions dict keyed by thread_id -> (Workflow, request_id)"
    - "Custom AG-UI endpoint replacing add_agent_framework_fastapi_endpoint for full SSE control"
    - "Echo filtering by author_name: suppress Orchestrator text-only updates, pass through Classifier content"

key-files:
  created:
    - backend/src/second_brain/api/inbox.py
  modified:
    - backend/src/second_brain/agents/workflow.py
    - backend/src/second_brain/agents/classifier.py
    - backend/src/second_brain/main.py

key-decisions:
  - "Raw Workflow instead of WorkflowAgent for HITL: WorkflowAgent doesn't expose run(responses=...), so _create_workflow returns Workflow directly while keeping a separate WorkflowAgent for its converter method"
  - "Custom AG-UI endpoint instead of add_agent_framework_fastapi_endpoint: standard framework pipeline only processes AgentResponseUpdate; custom endpoint handles both AgentResponseUpdate and BaseEvent types"
  - "Echo filter by author_name: Orchestrator text-only AgentResponseUpdate objects are suppressed; tool call content from any agent passes through"
  - "Classifier interactive mode: removed from autonomous agents list so it emits request_info when it responds without handoff"

patterns-established:
  - "_stream_updates yields StreamItem (Union[AgentResponseUpdate, BaseEvent]) for mixed event streams"
  - "_stream_sse wraps mixed streams in RUN_STARTED/RUN_FINISHED lifecycle with EventEncoder"
  - "_convert_update_to_events converts AgentResponseUpdate to AG-UI BaseEvent objects"
  - "resume_with_response pops from _pending_sessions and calls workflow.run(responses=...)"

requirements-completed: [CLAS-04, CAPT-02, APPX-02]

# Metrics
duration: 9min
completed: 2026-02-22
---

# Phase 4 Plan 1: Backend HITL Workflow, AG-UI Step Events, Echo Filter, and Inbox API Summary

**HITL pause/resume via HandoffBuilder request_info with AG-UI step events, Orchestrator echo filter, respond endpoint, and paginated Inbox REST API**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-22T07:46:47Z
- **Completed:** 2026-02-22T07:55:59Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- AGUIWorkflowAdapter fully refactored for HITL: raw Workflow creation, _pending_sessions storage, resume_with_response for continuing paused workflows
- AG-UI StepStarted/StepFinished events emitted on executor_invoked/executor_completed for real-time agent chain visibility
- Orchestrator echo bug fixed server-side by filtering text-only updates from Orchestrator agent
- Custom AG-UI SSE endpoint replaces framework default to support mixed AgentResponseUpdate + BaseEvent streams
- POST /api/ag-ui/respond endpoint for HITL continuation via SSE
- GET /api/inbox and GET /api/inbox/{item_id} REST endpoints for mobile Inbox view
- Classifier instructions updated with low-confidence clarification flow and bucket override handling

## Task Commits

Each task was committed atomically:

1. **Task 1: HITL workflow + step events + echo filter** - `14eecf9` (feat)
2. **Task 2: Inbox API + respond endpoint + main.py wiring** - `e96284e` (feat)

## Files Created/Modified

- `backend/src/second_brain/agents/workflow.py` - AGUIWorkflowAdapter with HITL support (_pending_sessions, resume_with_response, step events, echo filter), raw Workflow creation, mixed StreamItem yield
- `backend/src/second_brain/agents/classifier.py` - Low-confidence clarification instructions, bucket override handling, updated rules for interactive mode
- `backend/src/second_brain/api/inbox.py` - GET /api/inbox (paginated list) and GET /api/inbox/{item_id} (detail) endpoints with Cosmos DB queries
- `backend/src/second_brain/main.py` - Custom AG-UI endpoint, /api/ag-ui/respond endpoint, inbox router inclusion, workflow_agent stored on app.state, SSE helpers (_stream_sse, _convert_update_to_events)

## Decisions Made

- **Raw Workflow instead of WorkflowAgent**: WorkflowAgent wraps the workflow and doesn't expose `run(responses=...)` needed for HITL resumption. Solution: `_create_workflow` returns raw `Workflow`; a separate `WorkflowAgent` instance is kept lazily for its `_convert_workflow_event_to_agent_response_updates` converter method.
- **Custom AG-UI endpoint**: The framework's `add_agent_framework_fastapi_endpoint` routes through `run_agent_stream` which only handles `AgentResponseUpdate` objects. Since the adapter now yields both `AgentResponseUpdate` and AG-UI `BaseEvent` objects (for step events and HITL custom events), a custom endpoint was created that handles both types and serializes via `EventEncoder`.
- **Echo filter by author_name**: The Orchestrator echoes user input as text in its response. Rather than complex text-matching heuristics, filtering by `author_name` on the `AgentResponseUpdate` is deterministic -- all text-only updates from the Orchestrator are suppressed.
- **Classifier interactive mode**: Removing the Classifier from `with_autonomous_mode(agents=[...])` causes it to emit `request_info` with `HandoffAgentUserRequest` when it responds without handing off. This is the framework's native HITL mechanism.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff linting violations**
- **Found during:** Task 2 (main.py and inbox.py)
- **Issue:** Unused imports (EventType, RunFinishedEvent, RunStartedEvent, Content, json), line too long, missing `raise from` in except clause
- **Fix:** Removed unused imports, wrapped long logger.info line, added `from exc` to CosmosResourceNotFoundError re-raise
- **Files modified:** workflow.py, inbox.py, main.py
- **Verification:** `ruff check` passes clean
- **Committed in:** e96284e (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (linting cleanup)
**Impact on plan:** Minor code quality fix. No scope creep.

## Issues Encountered

None -- plan executed smoothly. The main challenge was understanding how AG-UI events flow through the framework's `run_agent_stream` pipeline, which led to the custom endpoint decision.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- Backend fully supports HITL pause/resume, step events, echo filtering, and Inbox API
- Plan 04-02 (mobile streaming UI, step dots, inline clarification) can proceed
- Plan 04-03 (Inbox screen, conversation screen) can proceed
- The respond endpoint SSE stream format matches the standard AG-UI capture flow for consistent mobile handling

## Self-Check: PASSED

All files verified present. All commit hashes found in git log.

---
*Phase: 04-hitl-clarification-and-ag-ui-streaming*
*Completed: 2026-02-22*
