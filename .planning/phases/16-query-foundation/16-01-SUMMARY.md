---
phase: 16-query-foundation
plan: 01
subsystem: observability
tags: [azure-monitor-query, kql, log-analytics, pydantic, fastapi-lifespan]

# Dependency graph
requires:
  - phase: none
    provides: "First phase of v3.1 milestone -- builds on existing FastAPI lifespan and config patterns"
provides:
  - "observability/ module with LogsQueryClient lifecycle (create/close)"
  - "4 workspace-compatible KQL templates (capture trace, recent failures, system health, admin audit)"
  - "5 Pydantic result models (QueryResult, TraceRecord, FailureRecord, HealthSummary, AdminAuditRecord)"
  - "async query functions with partial result detection"
  - "LogsQueryClient wired into FastAPI lifespan as app.state.logs_client"
  - "log_analytics_workspace_id config setting"
affects: [17-investigation-agent, 18-mobile-chat, 19-mcp-tool]

# Tech tracking
tech-stack:
  added: [azure-monitor-query>=2.0.0]
  patterns: [workspace-kql-templates, partial-result-detection, non-fatal-client-init]

key-files:
  created:
    - backend/src/second_brain/observability/__init__.py
    - backend/src/second_brain/observability/client.py
    - backend/src/second_brain/observability/models.py
    - backend/src/second_brain/observability/kql_templates.py
    - backend/src/second_brain/observability/queries.py
  modified:
    - backend/pyproject.toml
    - backend/src/second_brain/config.py
    - backend/src/second_brain/main.py

key-decisions:
  - "LogsQueryClient init is non-fatal (warning + None) to match optional services pattern"
  - "SYSTEM_HEALTH consolidated from 5 portal sections into 1 programmatic query returning a single summary row"
  - "ADMIN_AUDIT split into two templates (LOG + SUMMARY) for different use cases"
  - "Original .kql files kept in backend/queries/ as archive/reference"

patterns-established:
  - "Workspace KQL: always use traces/requests/dependencies/exceptions, never AppTraces/AppRequests"
  - "Query results: always wrap in QueryResult with is_partial flag for partial result detection"
  - "Client lifecycle: create_X / close_X function pairs for lifespan management"

requirements-completed: [INV-01, INV-02, INV-03, INV-04, INV-05, MCP-01]

# Metrics
duration: 4min
completed: 2026-04-05
---

# Phase 16 Plan 01: Observability Module Summary

**Programmatic App Insights query layer with LogsQueryClient, 4 workspace-compatible KQL templates, and typed Pydantic result models**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-05T06:00:42Z
- **Completed:** 2026-04-05T06:05:28Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Created observability module with LogsQueryClient lifecycle management wired into FastAPI lifespan
- Migrated all 4 portal KQL templates to workspace schema (traces/requests, not AppTraces/AppRequests)
- Built typed async query functions with partial result detection via LogsQueryStatus

## Task Commits

Each task was committed atomically:

1. **Task 1: Add dependency, config setting, and create observability module with models and templates** - `5ee1de5` (feat)
2. **Task 2: Create query execution functions and wire LogsQueryClient into lifespan** - `d7b0f85` (feat)

## Files Created/Modified
- `backend/src/second_brain/observability/__init__.py` - Module marker
- `backend/src/second_brain/observability/client.py` - LogsQueryClient create/close lifecycle functions
- `backend/src/second_brain/observability/models.py` - Pydantic models: QueryResult, TraceRecord, FailureRecord, HealthSummary, AdminAuditRecord
- `backend/src/second_brain/observability/kql_templates.py` - 5 workspace-compatible KQL template strings
- `backend/src/second_brain/observability/queries.py` - async query functions: execute_kql, query_capture_trace, query_recent_failures, query_system_health, query_admin_audit
- `backend/pyproject.toml` - Added azure-monitor-query>=2.0.0 dependency
- `backend/src/second_brain/config.py` - Added log_analytics_workspace_id setting
- `backend/src/second_brain/main.py` - Wired LogsQueryClient into lifespan startup/shutdown

## Decisions Made
- LogsQueryClient initialization is non-fatal (logs warning, sets app.state.logs_client = None) to match the existing optional services pattern used by Cosmos, OpenAI, and Blob Storage
- SYSTEM_HEALTH query consolidated from 5 separate portal sections into a single query returning one summary row -- better for programmatic consumption
- ADMIN_AUDIT split into ADMIN_AUDIT_LOG (activity log) and ADMIN_AUDIT_SUMMARY (per-capture summary) as two separate templates for flexibility
- Original .kql files preserved in backend/queries/ as archive/reference per RESEARCH recommendation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff B905 zip() strict parameter**
- **Found during:** Task 2 (query execution functions)
- **Issue:** ruff B905 requires explicit `strict=` parameter on `zip()` calls
- **Fix:** Added `strict=True` to both `zip(columns, row)` calls in execute_kql
- **Files modified:** backend/src/second_brain/observability/queries.py
- **Verification:** ruff check passes
- **Committed in:** d7b0f85 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor lint compliance fix. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. The LOG_ANALYTICS_WORKSPACE_ID environment variable will need to be set on the Container App for production use, but this is handled in a later plan (16-03).

## Next Phase Readiness
- Observability module ready for Phase 17 (Investigation Agent) to import and use query functions
- LogsQueryClient available on app.state for dependency injection in API routes
- All KQL templates use workspace schema -- compatible with Log Analytics workspace queries

## Self-Check: PASSED

All 6 created files verified on disk. Both task commits (5ee1de5, d7b0f85) found in git log.

---
*Phase: 16-query-foundation*
*Completed: 2026-04-05*
