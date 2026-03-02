---
phase: 10-data-foundation-and-admin-tools
plan: 02
subsystem: agents
tags: [foundry-agent, admin-agent, lifespan, azure-ai, integration-tests]

# Dependency graph
requires:
  - phase: 10-01
    provides: AdminTools class, ShoppingListItem model, CosmosManager ShoppingLists container
provides:
  - ensure_admin_agent() self-healing registration function
  - azure_ai_admin_agent_id config setting
  - Admin Agent lifespan wiring (separate AzureAIAgentClient)
  - Integration tests for Admin Agent and AdminTools
affects: [11-admin-agent-wiring, capture-flow]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Non-fatal agent registration: Admin Agent wrapped in try/except unlike Classifier fail-fast"
    - "Separate AzureAIAgentClient per agent: prevents tool/thread cross-contamination"

key-files:
  created:
    - backend/src/second_brain/agents/admin.py
    - backend/tests/test_admin_integration.py
  modified:
    - backend/src/second_brain/config.py
    - backend/src/second_brain/main.py

key-decisions:
  - "Admin Agent registration is non-fatal -- app continues if Foundry registration fails"
  - "Separate AzureAIAgentClient instance for Admin Agent (own agent_id, own middleware)"

patterns-established:
  - "Non-fatal agent registration: try/except + None state for optional agents"
  - "Agent tool list pattern: app.state.<agent>_agent_tools = [tools.method]"

requirements-completed: [AGNT-02]

# Metrics
duration: 2min
completed: 2026-03-02
---

# Phase 10 Plan 02: Admin Agent Registration Summary

**ensure_admin_agent() with self-healing Foundry registration, non-fatal lifespan wiring with separate AzureAIAgentClient, and integration tests for Foundry + Cosmos**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-02T00:49:48Z
- **Completed:** 2026-03-02T00:52:04Z
- **Tasks:** 4/4 (all complete)
- **Files modified:** 4

## Accomplishments
- ensure_admin_agent() mirrors classifier pattern with self-healing get/create flow
- Admin Agent lifespan wiring as non-fatal (try/except), separate from Classifier
- config.py extended with azure_ai_admin_agent_id setting
- 2 integration tests gated behind env var checks for Foundry and Cosmos

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ensure_admin_agent() and config setting** - `27e6dd4` (feat)
2. **Task 2: Wire Admin Agent into FastAPI lifespan** - `02c5c59` (feat)
3. **Task 3: Integration test for Admin Agent and AdminTools** - `5600188` (test)
4. **Task 4: Verify Azure setup and first deployment** - checkpoint:human-verify (approved)

## Files Created/Modified
- `backend/src/second_brain/agents/admin.py` - Self-healing Admin Agent registration function
- `backend/src/second_brain/config.py` - Added azure_ai_admin_agent_id setting
- `backend/src/second_brain/main.py` - Admin Agent lifespan wiring (non-fatal, separate client)
- `backend/tests/test_admin_integration.py` - 2 integration tests for Foundry and Cosmos

## Decisions Made
- Admin Agent registration is non-fatal (try/except with warning log) -- unlike Classifier which is fail-fast. Admin features are optional until Phase 11 wires the capture-to-admin handoff.
- Separate AzureAIAgentClient instance for Admin Agent ensures no tool/thread cross-contamination between Classifier and Admin agents.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required

Two manual Azure steps are required before Admin Agent features are operational:

1. **Create ShoppingLists container in Cosmos DB:**
   ```bash
   az cosmosdb sql container create \
     --account-name <your-cosmos-account> \
     --database-name second-brain \
     --name ShoppingLists \
     --partition-key-path "/store" \
     --resource-group shared-services-rg
   ```
   NOTE: Do NOT pass --throughput (serverless account rejects it)

2. **After first deployment:** Check Container App logs for "NEW Admin agent: id=asst_xxx". Copy that ID and set as AZURE_AI_ADMIN_AGENT_ID env var on Container App. Then set Admin Agent instructions in Foundry portal.

## Task 4: Azure Setup Verified

All manual Azure setup confirmed complete by user:
- ShoppingLists container exists in Cosmos DB with /store partition key (verified via az CLI and end-to-end test)
- Admin Agent created in Foundry: asst_17oFXNHNq7kzmspQGMUrgERM
- AZURE_AI_ADMIN_AGENT_ID env var set on Container App
- Admin Agent instructions configured in Foundry portal (store routing rules for jewel, cvs, pet_store, other)
- End-to-end write/read/delete test passed against live Cosmos

## Next Phase Readiness
- Admin Agent infrastructure complete: ensure_admin_agent(), separate client, tool list
- Phase 11 can wire capture-to-admin handoff using app.state.admin_client
- All 68 existing tests pass; 5 integration tests properly gated

## Self-Check: PASSED

All 4 files verified present. All 3 task commits verified in git log (27e6dd4, 02c5c59, 5600188).

---
*Phase: 10-data-foundation-and-admin-tools*
*Completed: 2026-03-02*
