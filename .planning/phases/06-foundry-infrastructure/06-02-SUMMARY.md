---
phase: 06-foundry-infrastructure
plan: 02
subsystem: infra
tags: [azure-ai-foundry, application-insights, opentelemetry, fastapi, agent-framework-azure-ai]

# Dependency graph
requires:
  - phase: 06-foundry-infrastructure
    plan: 01
    provides: "Clean FastAPI shell with AsyncDefaultAzureCredential on app.state"
provides:
  - "AzureAIAgentClient initialized at startup with fail-fast probe call"
  - "configure_azure_monitor() wired for Application Insights telemetry"
  - "Health endpoint reporting foundry + cosmos connectivity status"
  - "Updated pyproject.toml with Foundry SDK and observability packages"
  - "config.py with azure_ai_project_endpoint, azure_ai_classifier_agent_id, applicationinsights_connection_string"
affects: [06-03, 07-classifier-agent, 09-observability]

# Tech tracking
tech-stack:
  added:
    - "agent-framework-azure-ai 1.0.0rc2"
    - "azure-monitor-opentelemetry 1.8.6"
    - "azure-core-tracing-opentelemetry 1.0.0b12"
    - "azure-ai-agents 1.2.0b5 (transitive)"
  patterns:
    - "configure_azure_monitor() called after load_dotenv() and before Azure SDK imports"
    - "AzureAIAgentClient created in lifespan with agents_client.list_agents(limit=1) probe for fail-fast auth validation"
    - "Health endpoint uses getattr with defaults for safe state access"

key-files:
  created: []
  modified:
    - "backend/pyproject.toml"
    - "backend/src/second_brain/config.py"
    - "backend/src/second_brain/main.py"
    - "backend/src/second_brain/api/health.py"
    - "backend/.env.example"
    - "backend/uv.lock"

key-decisions:
  - "Pass model_deployment_name='gpt-4o' to AzureAIAgentClient constructor -- required when no agent_id is provided (Phase 7 sets agent_id)"
  - "Use agents_client.list_agents(limit=1) as probe call -- lightest-weight API call that exercises full auth path (credential -> token -> Foundry API)"
  - "Add fastapi + uvicorn[standard] as direct dependencies -- previously transitive via agent-framework-ag-ui which was removed"

patterns-established:
  - "Foundry probe pattern: async for _ in client.agents_client.list_agents(limit=1): break -- validates auth without creating resources"
  - "AppInsights init order: load_dotenv() -> configure_azure_monitor() -> Azure SDK imports"

requirements-completed: [INFRA-10, INFRA-11, INFRA-13]

# Metrics
duration: 4min
completed: 2026-02-27
---

# Phase 6 Plan 02: Foundry SDK + AppInsights Wiring Summary

**Wired AzureAIAgentClient with fail-fast probe and configure_azure_monitor() into FastAPI lifespan, with enhanced health endpoint reporting Foundry + Cosmos connectivity**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-27T01:29:55Z
- **Completed:** 2026-02-27T01:34:32Z
- **Tasks:** 2
- **Files modified:** 6 (pyproject.toml, config.py, main.py, health.py, .env.example, uv.lock)

## Accomplishments
- Replaced agent-framework-ag-ui/orchestrations with agent-framework-azure-ai + azure-monitor-opentelemetry in pyproject.toml
- Updated config.py: removed 5 old OpenAI/Whisper/OTel fields, added 3 new Foundry/AppInsights fields
- Wired configure_azure_monitor() at module level (after load_dotenv, before Azure SDK imports)
- Created AzureAIAgentClient in lifespan with agents_client.list_agents(limit=1) probe call for genuine fail-fast auth validation
- Enhanced health endpoint to report foundry + cosmos connectivity status as JSON
- Updated .env.example with all new environment variables

## Task Commits

Each task was committed atomically:

1. **Task 1: Update pyproject.toml dependencies and config.py settings** - `71bbac3` (chore)
2. **Task 2: Wire configure_azure_monitor(), AzureAIAgentClient, and enhanced health endpoint** - `6dca6c1` (feat)

## Files Created/Modified
- `backend/pyproject.toml` - Updated deps: removed AG-UI packages, added Foundry SDK + AppInsights + fastapi/uvicorn
- `backend/src/second_brain/config.py` - Replaced old OpenAI/Whisper/OTel settings with Foundry + AppInsights fields
- `backend/src/second_brain/main.py` - Added configure_azure_monitor(), AzureAIAgentClient with probe in lifespan
- `backend/src/second_brain/api/health.py` - Enhanced to return {status, foundry, cosmos} JSON
- `backend/.env.example` - Documents AZURE_AI_PROJECT_ENDPOINT, AZURE_AI_CLASSIFIER_AGENT_ID, APPLICATIONINSIGHTS_CONNECTION_STRING
- `backend/uv.lock` - Regenerated with new dependency tree

## Decisions Made
- Added `model_deployment_name="gpt-4o"` to AzureAIAgentClient constructor because the SDK requires it when no `agent_id` is provided (ValueError raised otherwise). Phase 7 will set `agent_id` for the Classifier agent.
- Used `async for _ in foundry_client.agents_client.list_agents(limit=1): break` as the probe call. The `AzureAIAgentClient` exposes the underlying `AgentsClient` via `agents_client` attribute, and `list_agents(limit=1)` is the lightest API call that validates the full auth path.
- Added `fastapi` and `uvicorn[standard]` as direct dependencies after discovering they were previously transitive via `agent-framework-ag-ui` (which was removed in Task 1).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added fastapi and uvicorn[standard] as direct dependencies**
- **Found during:** Task 2 (dependency installation)
- **Issue:** After removing agent-framework-ag-ui, FastAPI was no longer installed -- it was a transitive dependency of the removed package
- **Fix:** Added `"fastapi"` and `"uvicorn[standard]"` to pyproject.toml dependencies
- **Files modified:** backend/pyproject.toml
- **Verification:** `uv sync --prerelease=allow` installs FastAPI successfully
- **Committed in:** 6dca6c1 (Task 2 commit)

**2. [Rule 3 - Blocking] Used agents_client.list_agents() instead of agents.list()**
- **Found during:** Task 2 (Foundry client probe implementation)
- **Issue:** Plan specified `foundry_client.agents.list(limit=1)` but the actual API surface is `foundry_client.agents_client.list_agents(limit=1)` -- `agents_client` is the underlying `AgentsClient` instance
- **Fix:** Used correct method path and iterated async paging result
- **Files modified:** backend/src/second_brain/main.py
- **Verification:** Method exists on AgentsClient, accepts `limit` parameter
- **Committed in:** 6dca6c1 (Task 2 commit)

**3. [Rule 3 - Blocking] Added model_deployment_name to AzureAIAgentClient constructor**
- **Found during:** Task 2 (Foundry client initialization)
- **Issue:** AzureAIAgentClient raises ValueError when neither `agent_id` nor `model_deployment_name` is provided. Phase 6 has no agent_id yet (Phase 7 creates it).
- **Fix:** Passed `model_deployment_name="gpt-4o"` to satisfy constructor validation
- **Files modified:** backend/src/second_brain/main.py
- **Verification:** Inspected SDK source -- check is `if agent_id is None and not model_deployment_name`
- **Committed in:** 6dca6c1 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking issues)
**Impact on plan:** All three were necessary for the code to function. No scope creep. The plan anticipated potential API surface differences (noted in implementation note) and these were resolved as expected.

## Issues Encountered
None beyond the auto-fixed deviations above.

## Deferred Items
5 pre-existing ruff E501 (line too long) errors in files not modified by this plan:
- `backend/src/second_brain/agents/classifier.py` (1 error)
- `backend/src/second_brain/tools/classification.py` (2 errors)
- `backend/tests/test_classification.py` (2 errors)

These are out of scope (not caused by current changes). Carried forward from Plan 01.

## User Setup Required
None - no external service configuration required for this plan. RBAC and AppInsights portal configuration are handled in Plan 03.

## Next Phase Readiness
- AzureAIAgentClient initialized at startup with fail-fast probe call, ready for Phase 7 Classifier agent registration
- configure_azure_monitor() active, traces will flow to AppInsights once connection string is configured
- Health endpoint ready to report Foundry connectivity status from deployed container
- Plan 03 (RBAC + deployment validation) is the final phase 6 plan

## Self-Check: PASSED

All 6 modified files confirmed present. Both task commits (71bbac3, 6dca6c1) confirmed in git log. SUMMARY.md exists on disk.

---
*Phase: 06-foundry-infrastructure*
*Completed: 2026-02-27*
