---
phase: 06-foundry-infrastructure
plan: 01
subsystem: infra
tags: [cleanup, fastapi, dead-code-removal, ag-ui-removal]

# Dependency graph
requires:
  - phase: 05-voice-capture
    provides: "Complete v1.0 codebase with AG-UI pipeline"
provides:
  - "Clean FastAPI shell with no AG-UI or old agent code"
  - "AsyncDefaultAzureCredential persisted on app.state for Foundry use"
  - "Clean test fixtures without AG-UI mocks"
affects: [06-02, 06-03, 07-classifier-agent]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Credential persistence: AsyncDefaultAzureCredential stored on app.state across lifespan"
    - "Clean lifespan: Key Vault + Cosmos DB only, credential closed in finally block"

key-files:
  created: []
  modified:
    - "backend/src/second_brain/main.py"
    - "backend/tests/conftest.py"

key-decisions:
  - "Persist AsyncDefaultAzureCredential on app.state (not close after Key Vault) for Plan 02 Foundry client use"
  - "Keep classifier.py intact (reused in Phase 7) and blob_storage.py (file only, removed from lifespan)"
  - "Pre-existing ruff E501 errors in classifier.py, classification.py, test_classification.py left as-is (out of scope)"

patterns-established:
  - "Credential lifecycle: credential created at lifespan start, stored on app.state, closed in finally block"

requirements-completed: [INFRA-14, AGNT-04]

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 6 Plan 01: Delete Old Orchestration Code Summary

**Deleted 7 old agent/workflow/AG-UI files (899 lines) and rewrote main.py as a clean 104-line FastAPI shell with persistent async credential**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T01:24:48Z
- **Completed:** 2026-02-27T01:27:24Z
- **Tasks:** 2
- **Files modified:** 9 (7 deleted, 2 rewritten)

## Accomplishments
- Deleted all old orchestration code: orchestrator.py, perception.py, echo.py, workflow.py (541 lines), transcription.py
- Deleted AG-UI test files: test_agui_endpoint.py, test_integration.py
- Rewrote main.py from 1025 lines to 104 lines -- clean FastAPI shell with Key Vault, Cosmos DB, health router, inbox router, and middleware only
- Cleaned conftest.py: removed MockAgentFrameworkAgent, AG-UI mock endpoint, and all ag_ui/agent_framework_ag_ui imports
- Persisted AsyncDefaultAzureCredential on app.state for future Foundry client use (Plan 02)

## Task Commits

Each task was committed atomically:

1. **Task 1: Delete old source and test files** - `30cef45` (chore)
2. **Task 2: Rewrite main.py as clean FastAPI shell** - `5233225` (feat)

## Files Created/Modified
- `backend/src/second_brain/agents/orchestrator.py` - DELETED (Orchestrator agent)
- `backend/src/second_brain/agents/perception.py` - DELETED (Perception agent)
- `backend/src/second_brain/agents/echo.py` - DELETED (Phase 1 test agent)
- `backend/src/second_brain/agents/workflow.py` - DELETED (HandoffBuilder + AGUIWorkflowAdapter, 541 lines)
- `backend/src/second_brain/tools/transcription.py` - DELETED (Whisper transcription tool)
- `backend/tests/test_agui_endpoint.py` - DELETED (AG-UI endpoint tests)
- `backend/tests/test_integration.py` - DELETED (Integration tests for AG-UI pipeline)
- `backend/src/second_brain/main.py` - Rewritten as clean FastAPI shell (1025 -> 104 lines)
- `backend/tests/conftest.py` - Cleaned: removed AG-UI mocks and imports

## Decisions Made
- Persisted AsyncDefaultAzureCredential on app.state instead of closing after Key Vault fetch -- Plan 02 will use it for AzureAIAgentClient
- Kept classifier.py and blob_storage.py intact per locked decisions (classifier reused in Phase 7)
- Pre-existing ruff E501 errors in 3 unrelated files left untouched (scope boundary -- not caused by this plan's changes)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `Request` import and fixed line-too-long in main.py**
- **Found during:** Task 2 (main.py rewrite)
- **Issue:** ruff found unused `Request` import (F401) and one line exceeding 88 chars (E501)
- **Fix:** Removed `Request` from import, split long string across two lines
- **Files modified:** backend/src/second_brain/main.py
- **Verification:** `ruff check src/second_brain/main.py` passes with zero errors
- **Committed in:** 5233225 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Minor formatting fix. No scope creep.

## Issues Encountered
None

## Deferred Items
5 pre-existing ruff E501 (line too long) errors in files not modified by this plan:
- `backend/src/second_brain/agents/classifier.py` (1 error)
- `backend/src/second_brain/tools/classification.py` (2 errors)
- `backend/tests/test_classification.py` (2 errors)

These are out of scope for this plan (not caused by current changes).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Clean FastAPI shell ready for Plan 02: Foundry SDK, AppInsights, config.py update, AzureAIAgentClient init
- AsyncDefaultAzureCredential on app.state ready for Foundry client initialization
- No blockers

## Self-Check: PASSED

All 7 deleted files confirmed absent. Both modified files confirmed present. Both task commits (30cef45, 5233225) confirmed in git log. SUMMARY.md exists on disk.

---
*Phase: 06-foundry-infrastructure*
*Completed: 2026-02-27*
