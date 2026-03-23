---
phase: 14-app-insights-operational-audit
plan: 03
subsystem: infra
tags: [kql, azure-monitor, alerts, app-insights, observability]

# Dependency graph
requires:
  - phase: 14-01
    provides: "Structured logging with capture_trace_id custom dimensions for KQL queries"
provides:
  - "4 version-controlled KQL query files for App Insights investigation"
  - "Azure Monitor action group with push notifications"
  - "3 scheduled query alert rules for error spikes, capture failures, and API health"
affects: []

# Tech tracking
tech-stack:
  added: [azure-monitor-scheduled-query, azure-action-groups]
  patterns: [version-controlled-kql-queries, push-notification-alerting]

key-files:
  created:
    - backend/queries/capture-trace.kql
    - backend/queries/recent-failures.kql
    - backend/queries/system-health.kql
    - backend/queries/admin-agent-audit.kql
    - backend/queries/README.md

key-decisions:
  - "KQL queries use AppTraces table name (portal queries) while alert rules use 'traces' table name (workspace-based scheduled queries)"
  - "Alert severity: API-Health-Check is severity 1 (important), error spike and capture failures are severity 2 (warning)"
  - "Push notifications via Azure mobile app (azureapppush) rather than email or SMS"

patterns-established:
  - "Version-controlled KQL queries in backend/queries/ with README for portal usage"
  - "Azure Monitor alert rules with auto-mitigate for self-resolving incidents"

requirements-completed: [OBS-07, OBS-08]

# Metrics
duration: 2min
completed: 2026-03-23
---

# Phase 14 Plan 03: KQL Queries and Azure Monitor Alerts Summary

**4 version-controlled KQL queries for App Insights investigation plus 3 Azure Monitor alert rules with push notification delivery via Azure mobile app**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-23T03:42:42Z
- **Completed:** 2026-03-23T03:44:23Z
- **Tasks:** 2
- **Files modified:** 5 (repo files) + 4 Azure resources (action group + 3 alert rules)

## Accomplishments
- 4 KQL query files covering capture lifecycle tracing, recent failures, system health overview, and Admin Agent audit
- README with step-by-step instructions for using queries in the App Insights portal
- Action group "SecondBrainAlerts" with Azure mobile app push notifications to will@willmacdonald.com
- 3 scheduled query alert rules: API-Error-Spike (>3 errors/5min), Capture-Processing-Failures (>2 admin failures/15min), API-Health-Check (>5 5xx/10min)
- All alert rules have auto-mitigate enabled for self-resolving incidents

## Task Commits

Each task was committed atomically:

1. **Task 1: Create KQL query files and README** - `3acc02c` (feat)
2. **Task 2: Configure Azure Monitor alert rules** - Azure CLI infrastructure only (no repo commit)

**Plan metadata:** (pending final commit)

## Files Created/Modified
- `backend/queries/capture-trace.kql` - Full lifecycle timeline query by capture_trace_id
- `backend/queries/recent-failures.kql` - ERROR+ logs and exceptions from last 24h
- `backend/queries/system-health.kql` - Capture volume, success rate, error trends, processing counts
- `backend/queries/admin-agent-audit.kql` - Admin Agent processing audit with per-capture outcomes
- `backend/queries/README.md` - Instructions for using queries in App Insights portal

## Azure Resources Created
- **Action Group:** SecondBrainAlerts (shared-services-rg) - Push notifications to will@willmacdonald.com
- **Alert Rule:** API-Error-Spike - severity 2, 5m window, >3 ERROR+ traces
- **Alert Rule:** Capture-Processing-Failures - severity 2, 15m window, >2 admin failures
- **Alert Rule:** API-Health-Check - severity 1, 10m window, >5 5xx responses

## Decisions Made
- KQL queries use `AppTraces` table name for portal queries while alert rules use `traces` (workspace-based Log Analytics table name required by scheduled query rules)
- API-Health-Check set to severity 1 (higher priority) since 5xx responses indicate service-level issues; error spike and capture failures set to severity 2
- Push notifications via Azure mobile app chosen over email/SMS for immediacy and mobile-first workflow

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Alert rule table name mismatch**
- **Found during:** Task 2 (alert rule creation)
- **Issue:** Plan specified `AppTraces` table for alert queries, but workspace-based App Insights requires `traces` table name for scheduled query rules
- **Fix:** Used `traces` and `requests` table names (Log Analytics workspace schema) instead of `AppTraces` and `AppRequests`
- **Files modified:** N/A (Azure CLI commands only)
- **Verification:** All 3 alert rules created successfully and show as enabled

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor syntax adjustment for workspace-based App Insights. No scope change.

## Issues Encountered
None beyond the table name adjustment documented above.

## User Setup Required
None - all Azure resources were created via CLI during execution. Push notifications will be delivered to the Azure mobile app when alert conditions are met.

## Next Phase Readiness
- Phase 14 is now complete -- all 3 plans executed
- Full observability stack in place: structured logging, per-capture trace IDs, mobile telemetry, KQL queries, and alerting
- No blockers for future phases

## Self-Check: PASSED

- [x] backend/queries/capture-trace.kql - FOUND
- [x] backend/queries/recent-failures.kql - FOUND
- [x] backend/queries/system-health.kql - FOUND
- [x] backend/queries/admin-agent-audit.kql - FOUND
- [x] backend/queries/README.md - FOUND
- [x] 14-03-SUMMARY.md - FOUND
- [x] Commit 3acc02c (Task 1) - FOUND
- [x] Azure alert rules verified via `az monitor scheduled-query list` - 3/3 enabled

---
*Phase: 14-app-insights-operational-audit*
*Completed: 2026-03-23*
