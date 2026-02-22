---
phase: 03-text-classification-pipeline
plan: 01
subsystem: agents
tags: [agent-framework, handoff-builder, classification, cosmos-db, pydantic, multi-agent]

# Dependency graph
requires:
  - phase: 01-02
    provides: Pydantic document models, CosmosManager singleton, CosmosCrudTools pattern
  - phase: 01-01
    provides: FastAPI server with AG-UI endpoint, AzureOpenAIChatClient pattern
provides:
  - ClassificationMeta Pydantic model with bucket, confidence, allScores, agentChain, timestamps
  - ClassificationTools with classify_and_file and mark_as_junk @tool methods
  - Orchestrator agent (routing only, no tools)
  - Classifier agent with 10 few-shot examples and confidence calibration
  - HandoffBuilder workflow (Orchestrator -> Classifier) exposed via AG-UI endpoint
  - Bi-directional linking between Inbox and bucket records
  - Configurable classification threshold (CLASSIFICATION_THRESHOLD env var)
affects: [03-02-PLAN, 04-HITL]

# Tech tracking
tech-stack:
  added: [agent-framework-orchestrations]
  patterns: [HandoffBuilder workflow -> as_agent() -> AG-UI endpoint, shared AzureOpenAIChatClient across agents, ClassificationTools class-based tool binding, autonomous mode for routing agents]

key-files:
  created:
    - backend/src/second_brain/tools/classification.py
    - backend/src/second_brain/agents/orchestrator.py
    - backend/src/second_brain/agents/classifier.py
    - backend/src/second_brain/agents/workflow.py
  modified:
    - backend/src/second_brain/models/documents.py
    - backend/src/second_brain/config.py
    - backend/src/second_brain/main.py
    - backend/pyproject.toml

key-decisions:
  - "Shared AzureOpenAIChatClient across all agents (one client, not one per agent)"
  - "Orchestrator autonomous, Classifier interactive (Phase 4 HITL readiness)"
  - "All four bucket scores stored in ClassificationMeta.allScores for future threshold tuning"
  - "Bi-directional linking: InboxDocument.filedRecordId <-> BucketDocument.inboxRecordId"
  - "Used str type for bucket param (not Literal) for Agent Framework JSON schema compatibility"
  - "AsyncDefaultAzureCredential for Key Vault, sync DefaultAzureCredential for AzureOpenAIChatClient"

patterns-established:
  - "HandoffBuilder workflow -> as_agent() -> add_agent_framework_fastapi_endpoint() for multi-agent AG-UI"
  - "Autonomous mode on routing agents to ensure immediate handoff without user interaction"
  - "ClassificationTools class-based tool binding (same pattern as CosmosCrudTools)"
  - "Pre-generated UUIDs for bi-directional linking between Inbox and bucket documents"

requirements-completed: [ORCH-01, ORCH-02, ORCH-06, CLAS-01, CLAS-02, CLAS-03, CLAS-07]

# Metrics
duration: 4min
completed: 2026-02-22
---

# Phase 3 Plan 01: Classification Pipeline Summary

**Multi-agent classification pipeline with Orchestrator -> Classifier handoff, classify_and_file tool writing to Cosmos DB Inbox + bucket with bi-directional links**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-22T04:06:09Z
- **Completed:** 2026-02-22T04:10:14Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- ClassificationMeta Pydantic model with bucket, confidence, allScores (all four scores), agentChain, classifiedBy, classifiedAt
- ClassificationTools with classify_and_file (validates, writes to Inbox + bucket, bi-directional links) and mark_as_junk (Inbox only, status "unclassified")
- Orchestrator agent with routing-only instructions, Classifier agent with 10 few-shot examples and confidence calibration guidance
- HandoffBuilder workflow with autonomous Orchestrator and interactive Classifier, exposed via AG-UI at /api/ag-ui
- Echo agent replaced in main.py with capture pipeline; echo.py kept for reference
- All 19 existing tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Document model updates, classification tool, and config** - `e2ab958` (feat)
2. **Task 2: Orchestrator, Classifier, workflow agents, and main.py wiring** - `c941283` (feat)

## Files Created/Modified
- `backend/src/second_brain/models/documents.py` - Added ClassificationMeta model; filedRecordId/status/title on InboxDocument; inboxRecordId on all bucket documents
- `backend/src/second_brain/tools/classification.py` - ClassificationTools with classify_and_file and mark_as_junk @tool methods
- `backend/src/second_brain/config.py` - Added classification_threshold setting (default 0.6)
- `backend/pyproject.toml` - Added agent-framework-orchestrations dependency, N815 ruff ignore for classification.py
- `backend/src/second_brain/agents/orchestrator.py` - Orchestrator agent creation function
- `backend/src/second_brain/agents/classifier.py` - Classifier agent with 10 few-shot examples, confidence calibration, junk detection
- `backend/src/second_brain/agents/workflow.py` - HandoffBuilder workflow wiring with autonomous Orchestrator
- `backend/src/second_brain/main.py` - Replaced echo agent with capture pipeline; shared chat client; import AsyncDefaultAzureCredential for Key Vault

## Decisions Made
- Shared AzureOpenAIChatClient across all agents per research anti-pattern guidance (one client, not one per agent)
- Orchestrator is autonomous (always hands off), Classifier is interactive (ready for Phase 4 HITL clarification)
- Used `str` type (not `Literal`) for bucket parameter in classify_and_file -- Agent Framework tools need simple types for JSON schema generation
- Renamed DefaultAzureCredential import for Key Vault to AsyncDefaultAzureCredential to disambiguate from the sync credential used by AzureOpenAIChatClient
- Pre-generate UUIDs for both Inbox and bucket documents before writing either, enabling bi-directional links in a single pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Upgraded agent-framework-ag-ui to match agent-framework-core**
- **Found during:** Task 2 (main.py import verification)
- **Issue:** Installing agent-framework-orchestrations upgraded agent-framework-core from 1.0.0b260210 to 1.0.0rc1. The existing agent-framework-ag-ui (1.0.0b260210) imported AgentThread from agent_framework which doesn't exist in rc1. ImportError on `from second_brain.main import app`.
- **Fix:** Ran `uv pip install agent-framework-ag-ui --prerelease=allow --upgrade` to upgrade from 1.0.0b260210 to 1.0.0b260219
- **Files modified:** None (runtime dependency only)
- **Verification:** `from second_brain.main import app` succeeds; all 19 tests pass
- **Committed in:** c941283 (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary fix for version compatibility. No scope creep. The pyproject.toml already has agent-framework-ag-ui as a dependency; the upgrade was a transitive version resolution issue.

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no new external service configuration required. Existing Cosmos DB and Azure OpenAI setup from Phase 1 is sufficient.

## Next Phase Readiness
- Classification pipeline fully wired: AG-UI POST -> Orchestrator -> Classifier -> classify_and_file -> Cosmos DB
- Ready for Plan 03-02 (frontend updates to display classification confirmation)
- Ready for Phase 4 (HITL clarification) -- Classifier is interactive, not autonomous
- Echo agent kept at backend/src/second_brain/agents/echo.py for reference

---
*Phase: 03-text-classification-pipeline*
*Completed: 2026-02-22*
