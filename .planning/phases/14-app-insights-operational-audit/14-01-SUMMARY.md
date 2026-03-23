---
phase: 14-app-insights-operational-audit
plan: 01
subsystem: observability
tags: [azure-monitor, opentelemetry, logging, app-insights, trace-id]

# Dependency graph
requires:
  - phase: 13-recipe-url-extraction
    provides: Complete backend with all capture/admin/errand paths
provides:
  - Scoped Azure Monitor logging (application loggers only, INFO+ visible)
  - Consistent log level policy across all 18 backend source files
  - Per-capture trace ID (capture_trace_id) threaded end-to-end
  - captureTraceId field on inbox documents for KQL filtering
  - ContextVar pattern for propagating trace ID through @tool functions
  - Component field on structured log extras for KQL component filtering
affects: [14-02, 14-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ContextVar for propagating request context into @tool functions"
    - "Structured log extras with capture_trace_id and component fields"
    - "logger_name scoping in configure_azure_monitor to filter SDK noise"

key-files:
  created: []
  modified:
    - backend/src/second_brain/main.py
    - backend/src/second_brain/api/capture.py
    - backend/src/second_brain/streaming/adapter.py
    - backend/src/second_brain/processing/admin_handoff.py
    - backend/src/second_brain/tools/classification.py
    - backend/src/second_brain/api/errands.py
    - backend/src/second_brain/api/inbox.py
    - backend/src/second_brain/api/tasks.py

key-decisions:
  - "capture_trace_id_var ContextVar pattern reuses the existing follow_up_context pattern for thread-safe propagation"
  - "captureTraceId stored directly on inbox document body (not in classificationMeta) for admin processing access"
  - "Voice capture transcribe_audio log demoted to DEBUG (routine per-request, not lifecycle)"
  - "Admin Agent retry exhaustion promoted from WARNING to ERROR (unrecoverable processing failure)"

patterns-established:
  - "Log level policy: ERROR=unrecoverable, WARNING=degraded/recoverable, INFO=lifecycle, DEBUG=routine"
  - "All capture-path logger calls include extra={'capture_trace_id': ..., 'component': ...}"
  - "ContextVar set/reset pattern in async generators for request-scoped propagation"

requirements-completed: [OBS-01, OBS-02, OBS-03, OBS-04]

# Metrics
duration: 12min
completed: 2026-03-22
---

# Phase 14 Plan 01: Logging & Trace ID Summary

**Scoped Azure Monitor to application loggers with INFO visibility, enforced log level policy across 18 files, and threaded per-capture trace ID end-to-end from X-Trace-Id header through classification to Admin Agent processing**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-23T03:12:34Z
- **Completed:** 2026-03-23T03:24:34Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Azure Monitor scoped with logger_name="second_brain" and INFO level set -- fixes the known issue where only WARNING+ appeared in App Insights
- Full log level audit across all 18 backend source files with 5 fixes applied (4 planned + 1 discovered)
- Per-capture trace ID (capture_trace_id) propagated end-to-end: X-Trace-Id header -> capture.py -> adapter.py -> classification.py -> inbox document -> admin_handoff.py
- Component field added to structured log extras enabling KQL component-level filtering

## Task Commits

Each task was committed atomically:

1. **Task 1: Azure Monitor scoping, INFO visibility fix, and log level audit** - `4eea231` (feat)
2. **Task 2: Per-capture trace ID propagation through all capture and admin paths** - `65055e4` (feat)

## Files Created/Modified
- `backend/src/second_brain/main.py` - Scoped configure_azure_monitor with logger_name and INFO level
- `backend/src/second_brain/api/capture.py` - X-Trace-Id extraction in all 4 endpoints, capture_trace_id threading
- `backend/src/second_brain/streaming/adapter.py` - capture_trace_id parameter on all stream functions, ContextVar set/reset, OTel span attributes
- `backend/src/second_brain/tools/classification.py` - capture_trace_id_var ContextVar, captureTraceId on inbox documents
- `backend/src/second_brain/processing/admin_handoff.py` - capture_trace_id parameter, reads captureTraceId from inbox doc, structured log extras
- `backend/src/second_brain/api/errands.py` - Demoted routine GET stats log to DEBUG
- `backend/src/second_brain/api/inbox.py` - Demoted routine GET stats log to DEBUG
- `backend/src/second_brain/api/tasks.py` - Demoted routine GET stats log to DEBUG

## Decisions Made
- Used ContextVar pattern (matching existing follow_up_context) to propagate trace ID from adapter into file_capture @tool function -- clean thread-safe approach for async generators
- captureTraceId stored on inbox document body directly (not nested in classificationMeta) so admin_handoff.py can read it without parsing classification metadata
- Voice capture transcribe_audio log demoted from INFO to DEBUG (fires on every voice capture, not a lifecycle event)
- Admin Agent retry exhaustion promoted from WARNING to ERROR (this is a processing failure, not a recoverable degradation)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Demoted voice capture transcribe_audio log to DEBUG**
- **Found during:** Task 1 (log level audit)
- **Issue:** adapter.py logged "Voice capture: transcribe_audio called" at INFO on every voice capture -- this is a routine per-request operation, not a lifecycle event
- **Fix:** Changed from logger.info to logger.debug
- **Files modified:** backend/src/second_brain/streaming/adapter.py
- **Verification:** Manual audit against log level policy
- **Committed in:** 4eea231 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug -- log level inconsistency)
**Impact on plan:** Minor -- one additional log level fix discovered during the full audit. No scope creep.

## Issues Encountered
- Pre-existing test failure in test_recipe_tools.py (SSL certificate verification error when hitting external URL) -- unrelated to changes, excluded from verification

## User Setup Required
None - no external service configuration required. Changes take effect after deployment via CI/CD.

## Next Phase Readiness
- Logging foundation complete: scoped, leveled, trace-id-aware
- Plan 02 (health endpoint + metrics) can build on this foundation
- Plan 03 (KQL queries) can now filter AppTraces by capture_trace_id in customDimensions
- After deployment, verify in App Insights: AppTraces should show INFO-level traces with capture_trace_id and component fields in customDimensions

## Self-Check: PASSED

- 14-01-SUMMARY.md: FOUND
- Commit 4eea231 (Task 1): FOUND
- Commit 65055e4 (Task 2): FOUND
- All 5 key modified files: FOUND

---
*Phase: 14-app-insights-operational-audit*
*Completed: 2026-03-22*
