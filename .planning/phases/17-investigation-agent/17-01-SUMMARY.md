---
phase: 17-investigation-agent
plan: 01
subsystem: observability
tags: [kql, log-analytics, pydantic, percentile-latency, usage-patterns]

# Dependency graph
requires:
  - phase: 16-query-foundation
    provides: "LogsQueryClient, execute_kql(), base KQL templates, Pydantic result models"
provides:
  - "6 new/enhanced KQL templates: SYSTEM_HEALTH_ENHANCED, RECENT_FAILURES_FILTERED, LATEST_CAPTURE_TRACE_ID, USAGE_PATTERNS_BY_PERIOD, USAGE_PATTERNS_BY_BUCKET, USAGE_PATTERNS_BY_DESTINATION"
  - "EnhancedHealthSummary model with P95/P99 latency and trend comparison"
  - "UsagePatternRecord model for generic usage pattern rows"
  - "4 async query functions: query_latest_capture_trace_id, query_enhanced_system_health, query_recent_failures_filtered, query_usage_patterns"
  - "Configurable server_timeout on execute_kql() (30s for investigation, 60s default)"
affects: [17-02-investigation-tools, 18-mobile-chat, 19-mcp-tool]

# Tech tracking
tech-stack:
  added: []
  patterns: [parameterized-kql-templates, trend-comparison-query, kql-duration-parsing, server-timeout-headroom]

key-files:
  created: []
  modified:
    - backend/src/second_brain/observability/kql_templates.py
    - backend/src/second_brain/observability/models.py
    - backend/src/second_brain/observability/queries.py

key-decisions:
  - "SYSTEM_HEALTH_ENHANCED uses summarize approach (not toscalar+print) to support percentile() function"
  - "server_timeout=30 on investigation queries to leave headroom under agent's 60s timeout"
  - "Original SYSTEM_HEALTH and RECENT_FAILURES preserved as fallback alongside enhanced versions"
  - "execute_kql() gains optional server_timeout parameter (default 60, backward compatible)"
  - "_parse_kql_duration() helper maps KQL duration literals to timedelta for automatic timespan calculation"

patterns-established:
  - "Enhanced templates coexist with originals: SYSTEM_HEALTH_ENHANCED alongside SYSTEM_HEALTH"
  - "Component filter as string injection: empty string for no filter, KQL clause for active filter"
  - "query_usage_patterns routes to different templates based on group_by parameter"
  - "Automatic 2x timespan for trend comparison queries"

requirements-completed: [INV-02, INV-03, INV-04, INV-05]

# Metrics
duration: 3min
completed: 2026-04-06
---

# Phase 17 Plan 01: Enhanced KQL Templates and Query Functions Summary

**P95/P99 latency templates, component-filtered failures, usage pattern queries, and typed async functions for Investigation Agent tools**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-06T02:56:06Z
- **Completed:** 2026-04-06T02:59:24Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added 6 new/enhanced KQL templates covering system health with trend comparison, filtered failures, latest capture lookup, and three usage pattern dimensions
- Added EnhancedHealthSummary and UsagePatternRecord Pydantic models for typed query results
- Added 4 async query functions with server_timeout=30 and graceful empty-result handling
- Made execute_kql() server_timeout configurable (backward compatible, default 60)

## Task Commits

Each task was committed atomically:

1. **Task 1: Enhance KQL templates and add new USAGE_PATTERNS template** - `a8d2ea2` (feat)
2. **Task 2: Add Pydantic result models and async query functions** - `981c3a5` (feat)

## Files Created/Modified
- `backend/src/second_brain/observability/kql_templates.py` - 6 new templates: SYSTEM_HEALTH_ENHANCED (P95/P99 + trend), RECENT_FAILURES_FILTERED (component/severity/limit), LATEST_CAPTURE_TRACE_ID, USAGE_PATTERNS_BY_PERIOD, USAGE_PATTERNS_BY_BUCKET, USAGE_PATTERNS_BY_DESTINATION
- `backend/src/second_brain/observability/models.py` - EnhancedHealthSummary (with p95/p99/trend fields), UsagePatternRecord (label + count)
- `backend/src/second_brain/observability/queries.py` - query_latest_capture_trace_id(), query_enhanced_system_health(), query_recent_failures_filtered(), query_usage_patterns(), _parse_kql_duration() helper, execute_kql() server_timeout parameter

## Decisions Made
- SYSTEM_HEALTH_ENHANCED uses `summarize` approach instead of `toscalar()` + `print` to support `percentile()` function -- the original template's pattern is incompatible with percentile calculations
- server_timeout=30 on all investigation queries to leave headroom under the agent's 60-second timeout (per RESEARCH pitfall #3)
- Original SYSTEM_HEALTH and RECENT_FAILURES preserved unchanged as fallback for existing Phase 16 consumers
- execute_kql() gains optional server_timeout parameter with default 60, keeping backward compatibility with all existing callers
- _parse_kql_duration() maps known KQL durations ("1h", "6h", "24h", "3d", "7d") to timedelta, with fallback to 24h for unknown values

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added server_timeout parameter to execute_kql()**
- **Found during:** Task 2 (query functions)
- **Issue:** New query functions needed server_timeout=30 but execute_kql() had hardcoded server_timeout=60 with no parameter
- **Fix:** Added optional server_timeout parameter to execute_kql() with default 60 (backward compatible)
- **Files modified:** backend/src/second_brain/observability/queries.py
- **Verification:** All existing callers unaffected (use default 60), new callers pass 30
- **Committed in:** 981c3a5 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to support the plan's server_timeout=30 requirement. Backward compatible change, no scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. All changes are code-only enhancements to existing modules.

## Next Phase Readiness
- All 6 KQL templates ready for Plan 02's InvestigationTools to consume
- 4 query functions ready to be called from @tool-decorated methods
- EnhancedHealthSummary and UsagePatternRecord models ready for JSON serialization in tool responses
- server_timeout=30 ensures KQL queries complete well within agent's 60-second timeout

## Self-Check: PASSED

All 3 modified files verified on disk. Both task commits (a8d2ea2, 981c3a5) found in git log. SUMMARY.md exists.

---
*Phase: 17-investigation-agent*
*Completed: 2026-04-06*
