---
phase: 23-foundry-ga-prep
plan: 05
subsystem: docs
tags: [foundry, migration-prep, config, observability, kql, span-mapping, auditor]

# Dependency graph
requires:
  - phase: 23-foundry-ga-prep plan 02
    provides: FOUNDRY-PROBE-FINDINGS.md with GA SDK behavior findings
provides:
  - CONFIG-DELTAS.md enumerating every config.py + env var change for Phase 24
  - SPAN-NAME-MAPPING.md with RC-to-GA span name table and per-KQL-query consumer breakdown
  - AUDITOR-VERIFICATION.md confirming framework-fidelity auditor ready for Phase 24
affects: [24-foundry-ga-migration]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - .planning/phases/23-foundry-ga-prep/CONFIG-DELTAS.md
    - .planning/phases/23-foundry-ga-prep/SPAN-NAME-MAPPING.md
    - .planning/phases/23-foundry-ga-prep/AUDITOR-VERIFICATION.md
  modified: []

key-decisions:
  - "Only AGENT_RUNS KQL template needs span Name update (Name endswith _agent_run -> Name == invoke_agent); all other queries use HTTP route Names or component properties"
  - "ENABLE_INSTRUMENTATION presence in RC env needs operator verification before deploy"
  - "Azure AI User role alone likely sufficient for Container App managed identity (Owner overly broad)"

patterns-established:
  - "3-step safe deploy sequence: Step A (env-var add), Step B (GA image push), Step C (post-UAT orphan removal)"

requirements-completed: [PREP-08, PREP-09]

# Metrics
duration: 8min
completed: 2026-05-09
---

# Phase 23 Plan 05: Documentation Deliverables Summary

**CONFIG-DELTAS.md with 3-step safe deploy sequence, SPAN-NAME-MAPPING.md showing only AGENT_RUNS template needs update, AUDITOR-VERIFICATION.md confirming 19-finding calibration with no blind spots**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-09T20:51:28Z
- **Completed:** 2026-05-09T20:59:54Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- CONFIG-DELTAS.md: 1 config.py addition (foundry_model), 3 env vars (FOUNDRY_MODEL, ENABLE_INSTRUMENTATION, ENABLE_SENSITIVE_DATA), 3 orphan removals (azure_ai_*_agent_id), 3-step safe deploy sequence with negative assertion against premature env var removal
- SPAN-NAME-MAPPING.md: 8 RC span Names mapped to GA equivalents, only 1 KQL template (AGENT_RUNS at kql_templates.py line 378) needs updating, 15 query functions and 19 templates analyzed with no other span Name filters found
- AUDITOR-VERIFICATION.md: auditor file confirmed (318 lines, 19360 bytes), calibration report confirmed (19 F-## findings, 1 W-## warning, 3 passes), no-blind-spots claim validated against D-07 checklist, Phase 24 invocation contract documented

## Task Commits

Each task was committed atomically:

1. **Task 1: Write CONFIG-DELTAS.md** - `e448a9b` (docs)
2. **Task 2: Write SPAN-NAME-MAPPING.md** - `389712f` (docs)
3. **Task 3: Verify framework-fidelity-auditor + write AUDITOR-VERIFICATION.md** - `d29be8d` (docs)

## Files Created/Modified
- `.planning/phases/23-foundry-ga-prep/CONFIG-DELTAS.md` - Config + env var deltas for Phase 24 with safe deploy sequence
- `.planning/phases/23-foundry-ga-prep/SPAN-NAME-MAPPING.md` - RC-to-GA span Name mapping + per-KQL-query consumer table
- `.planning/phases/23-foundry-ga-prep/AUDITOR-VERIFICATION.md` - Framework-fidelity auditor existence + calibration verification

## Decisions Made
- Only AGENT_RUNS KQL template needs span Name update (endswith "_agent_run" to "invoke_agent"); all other 18 KQL templates and 14 query functions use HTTP route Names, component properties, or severity/attribute filters that are unaffected by RC-to-GA migration
- ENABLE_INSTRUMENTATION may already be present in RC Container App env; deploy step is idempotent
- Azure AI User role alone likely sufficient for managed identity RBAC (Owner at subscription scope is overly broad; verify during day-after UAT)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Calibration report's literal "X" emoji count via `grep -c` returned 3 (emoji appears in prose summary lines), but the actual failure count is confirmed as 19 via counting `### F-##` section headings, which matches the calibration report's own verdict table

## User Setup Required

None - no external service configuration required. All documents are planning artifacts consumed by Phase 24.

## Next Phase Readiness
- All 9 Phase 23 deliverables present (5 from plans 01-04 + 3 from plan 05 + calibration report from the 2026-05-08 detour)
- Phase 24 unblocked: CONFIG-DELTAS.md feeds task groups 23.1/23.3, SPAN-NAME-MAPPING.md feeds task group 23.1, AUDITOR-VERIFICATION.md confirms auditor ready for per-task-group fidelity gates
- Phase 23 closeout note: operator ready to run `/gsd-plan-phase 24`

## Self-Check: PASSED

---
*Phase: 23-foundry-ga-prep*
*Completed: 2026-05-09*
