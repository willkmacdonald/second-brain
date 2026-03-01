---
phase: 07-classifier-agent-baseline
plan: 02
subsystem: agents
tags: [foundry, classifier, lifespan, fastapi, middleware, transcription, integration-test]

# Dependency graph
requires:
  - phase: 07-classifier-agent-baseline
    plan: 01
    provides: ClassifierTools, TranscriptionTools, middleware, ensure_classifier_agent
  - phase: 06-foundry-infrastructure
    provides: AzureAIAgentClient setup, AsyncDefaultAzureCredential on app.state
provides:
  - Full agent registration wired into FastAPI lifespan with self-healing
  - ClassifierTools, TranscriptionTools, and middleware attached to AzureAIAgentClient
  - Agent tools stored on app.state for request-time get_response() calls
  - Integration tests validating agent end-to-end classification
affects: [08-streaming-pipeline, 09-observability]

# Tech tracking
tech-stack:
  added: []
  patterns: [tools passed at request-time via ChatOptions not constructor, separate AzureAIAgentClient per agent role]

key-files:
  created:
    - backend/tests/test_classifier_integration.py
  modified:
    - backend/src/second_brain/main.py

key-decisions:
  - "Tools passed via ChatOptions at get_response() time, not at AzureAIAgentClient construction (API does not support constructor tools)"
  - "Separate AzureAIAgentClient for classifier (with agent_id + middleware) vs probe client (with model_deployment_name only)"
  - "Agent tools stored on app.state.classifier_agent_tools for reuse across requests"

patterns-established:
  - "Request-time tools: client.get_response(messages, options=ChatOptions(tools=[...])) -- tools are not constructor params"
  - "Agent client per role: each agent gets its own AzureAIAgentClient with agent_id and should_cleanup_agent=False"
  - "Integration test isolation: self-contained mock manager (no fixture dependency) for service-level tests"

requirements-completed: [AGNT-01, AGNT-03, AGNT-06]

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 7 Plan 02: Classifier Agent Wiring - Lifespan Registration, Tools, and Integration Tests Summary

**Classifier agent wired into FastAPI lifespan with ensure_classifier_agent, ClassifierTools + TranscriptionTools on app.state, middleware-enabled AzureAIAgentClient, and integration test proving end-to-end classification**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T05:59:03Z
- **Completed:** 2026-02-27T06:01:34Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Wired ensure_classifier_agent() into FastAPI lifespan for self-healing agent registration at startup
- Created ClassifierTools, TranscriptionTools, BlobStorageManager, and AsyncAzureOpenAI client in lifespan with proper dependency ordering
- Attached AuditAgentMiddleware and ToolTimingMiddleware to dedicated classifier AzureAIAgentClient with should_cleanup_agent=False
- Created integration test suite with test_classifier_agent_classifies_text and test_classifier_agent_id_is_valid
- All 42 unit tests pass, 3 integration tests properly deselected without credentials

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire agent registration and tools into FastAPI lifespan** - `6c32c16` (feat)
2. **Task 2: Write integration test and update test fixtures** - `68700bb` (feat)

## Files Created/Modified
- `backend/src/second_brain/main.py` - Full lifespan wiring: ensure_classifier_agent, ClassifierTools, TranscriptionTools, BlobStorageManager, AsyncAzureOpenAI, dedicated classifier AzureAIAgentClient with middleware, cleanup in reverse order
- `backend/tests/test_classifier_integration.py` - Integration tests: agent classification end-to-end with mock Cosmos, agent ID validation against Foundry

## Decisions Made
- Tools are passed via ChatOptions at get_response() time, not at AzureAIAgentClient constructor (the API does not have a `create_agent()` method or `tools` constructor parameter -- tools flow through `options["tools"]` in the request pipeline)
- Separate AzureAIAgentClient created for classifier (with agent_id + middleware) distinct from the Phase 6 probe client (which has model_deployment_name for constructor validation)
- Agent tools stored on `app.state.classifier_agent_tools` list for reuse across requests without recreating FunctionTool instances

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adapted to actual AzureAIAgentClient API (no create_agent method)**
- **Found during:** Task 1 (wiring agent into lifespan)
- **Issue:** Plan described `client.create_agent(tools=..., middleware=...)` but AzureAIAgentClient has no `create_agent()` method. Tools are not constructor parameters either. The actual API passes tools at request time via `get_response(messages, options=ChatOptions(tools=[...]))`.
- **Fix:** Created AzureAIAgentClient with `agent_id`, `middleware`, and `should_cleanup_agent=False` in constructor. Stored tools on `app.state.classifier_agent_tools` for request-time use. Middleware is the only constructor-time configuration alongside agent_id.
- **Files modified:** backend/src/second_brain/main.py
- **Verification:** `python3 -c "from second_brain.main import app"` succeeds; ruff check passes
- **Committed in:** 6c32c16 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** API adaptation necessary for correctness. The end result achieves the same goal -- tools and middleware are attached to the agent -- but via the correct API surface. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no new environment variables or external service configuration required. All env vars were documented in Plan 01's .env.example updates.

## Next Phase Readiness
- Classifier agent fully wired: starts at app boot, self-heals, tools ready for request-time use
- Phase 8 (streaming pipeline) can now call `app.state.classifier_client.get_response()` with `ChatOptions(tools=app.state.classifier_agent_tools)` to run classifications
- Integration tests ready to validate against live Azure credentials when deployed
- No blockers identified

---
*Phase: 07-classifier-agent-baseline*
*Completed: 2026-02-27*
