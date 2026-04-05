---
phase: 16-query-foundation
plan: 03
subsystem: infra
tags: [azure-rbac, log-analytics, cosmos-db, container-apps, ci-cd]

# Dependency graph
requires:
  - phase: 16-01
    provides: "LogsQueryClient lifecycle, KQL templates, azure-monitor-query dependency"
  - phase: 16-02
    provides: "Eval document models, CosmosManager registration, container creation script"
provides:
  - "Log Analytics Reader RBAC on Container App managed identity"
  - "LOG_ANALYTICS_WORKSPACE_ID env var on Container App"
  - "Feedback, EvalResults, GoldenDataset Cosmos containers created in Azure"
  - "Deployed backend with working LogsQueryClient and all observability features"
affects: [17-investigation-agent, 19-mcp-tool, 20-feedback-collection, 21-eval-framework]

# Tech tracking
tech-stack:
  added: []
  patterns: [management-plane-cosmos-container-creation]

key-files:
  created: []
  modified:
    - uv.lock

key-decisions:
  - "Cosmos container creation uses az CLI management plane (not data plane RBAC) due to 403 on AAD token"
  - "uv.lock must be regenerated after adding dependencies to pyproject.toml before deploying"

patterns-established:
  - "Cosmos container creation: use `az cosmosdb sql container create` (management plane), not Python SDK with AAD token (data plane RBAC does not authorize DDL)"
  - "Dependency changes: always run `uv lock` after modifying pyproject.toml to prevent ModuleNotFoundError on deploy"

requirements-completed: [INV-01, INV-02, INV-03, INV-04, INV-05, MCP-01, FEED-01, EVAL-01, EVAL-04]

# Metrics
duration: infrastructure (multi-step manual + CI/CD)
completed: 2026-04-05
---

# Phase 16 Plan 03: Infrastructure & Deploy Summary

**Azure RBAC, Log Analytics workspace ID, three Cosmos eval containers, and CI/CD deployment enabling programmatic App Insights queries in production**

## Performance

- **Duration:** Infrastructure plan (multi-step: RBAC, env vars, Cosmos containers, CI/CD deploy, verification)
- **Started:** 2026-04-05 (during Phase 16 execution session)
- **Completed:** 2026-04-05
- **Tasks:** 2 (1 infrastructure automation + 1 human verification checkpoint)
- **Files modified:** 1 (uv.lock regenerated)

## Accomplishments
- Log Analytics Reader role assigned to Container App managed identity for programmatic KQL queries
- LOG_ANALYTICS_WORKSPACE_ID environment variable set on the Container App
- Three new Cosmos containers (Feedback, EvalResults, GoldenDataset) created via Azure CLI management plane
- Updated backend deployed via CI/CD with working LogsQueryClient initialization confirmed in App Insights
- End-to-end verification: health endpoint returns 200, LogsQueryClient initialized in production logs

## Task Commits

Each task was committed atomically:

1. **Task 1: RBAC role assignment, workspace ID env var, and Cosmos container creation** - (infrastructure-only, no code commit -- all changes via Azure CLI)
2. **Task 2: Human verification checkpoint** - (approved by user, no commit)

**Related fix commit:** `cb61036` (fix: regenerate uv.lock with azure-monitor-query and add CI concurrency)

## Files Created/Modified
- `uv.lock` - Regenerated to include azure-monitor-query dependency (fix for deploy failure)

## Decisions Made
- Used Azure CLI management plane (`az cosmosdb sql container create`) for Cosmos container creation instead of Python SDK data plane, because AAD token-based data plane RBAC returns 403 for container creation operations
- Confirmed that uv.lock must always be regenerated after pyproject.toml dependency changes to prevent ModuleNotFoundError in containerized deployments

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Cosmos container creation script 403 Forbidden**
- **Found during:** Task 1 (Cosmos container creation)
- **Issue:** The Python script `create_eval_containers.py` attempted container creation via the Cosmos DB data plane using AAD token authentication. Azure Cosmos DB data plane RBAC does not authorize DDL operations (container creation), returning 403 Forbidden.
- **Fix:** Used `az cosmosdb sql container create` (management plane) to create all three containers directly via Azure CLI
- **Files modified:** None (Azure infrastructure only)
- **Verification:** All three containers visible in Azure Portal
- **Committed in:** N/A (infrastructure change, no code commit)

**2. [Rule 3 - Blocking] uv.lock not regenerated after adding azure-monitor-query**
- **Found during:** Task 1 (CI/CD deployment)
- **Issue:** Plan 01 added `azure-monitor-query` to `pyproject.toml` but did not regenerate `uv.lock`. The Docker build used `uv pip sync` which relies on the lockfile, causing ModuleNotFoundError on container startup.
- **Fix:** Ran `uv lock` locally and committed the updated lockfile, then redeployed
- **Files modified:** uv.lock
- **Verification:** Container started successfully after redeployment, health endpoint returned 200
- **Committed in:** `cb61036`

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both were blocking issues preventing successful deployment. The Cosmos script workaround is a pattern to follow going forward. The uv.lock fix prevents future deploy failures.

## Issues Encountered
- RBAC propagation delay: After assigning Log Analytics Reader role, there was a brief wait before the Container App could successfully query the workspace. This is expected Azure behavior (up to 5-10 minutes for RBAC propagation).

## User Setup Required
None - all infrastructure provisioned via Azure CLI during plan execution.

## Next Phase Readiness
- Phase 16 is fully complete: all infrastructure deployed and verified in production
- Phase 17 (Investigation Agent) can import and use the observability query functions against live App Insights data
- Phase 19 (MCP Tool) can use the same LogsQueryClient pattern
- Phase 20 (Feedback Collection) can write to the Feedback Cosmos container
- Phase 21 (Eval Framework) can write to EvalResults and GoldenDataset Cosmos containers
- Log Analytics Reader RBAC blocker from STATE.md is now resolved

## Self-Check: PASSED

- 16-03-SUMMARY.md verified present on disk
- Commit cb61036 verified in git log

---
*Phase: 16-query-foundation*
*Completed: 2026-04-05*
