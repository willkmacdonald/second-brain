---
phase: 23-foundry-ga-prep
plan: 01
subsystem: infra
tags: [agent-framework, agent-framework-foundry, uv, dependency-resolution, foundry-ga]

# Dependency graph
requires:
  - phase: none
    provides: standalone artifact-only plan
provides:
  - Candidate pyproject.toml + uv.lock for GA agent-framework 1.3.0 + agent-framework-foundry 1.3.0
  - Standalone foundry_probe.py harness with 5 stubbed probe functions and CLI dispatcher
  - Fixture output directory for probe run results
  - GA SDK naming discovery (AgentResponse/AgentResponseUpdate/AgentSession)
affects: [23-foundry-ga-prep, 24-foundry-ga-migration]

# Tech tracking
tech-stack:
  added: [agent-framework 1.3.0, agent-framework-foundry 1.3.0, azure-ai-projects 2.1.0]
  patterns: [throwaway-spike-venv, candidate-dep-files, probe-harness-scaffold]

key-files:
  created:
    - .planning/phases/23-foundry-ga-prep/CANDIDATE-pyproject.toml
    - .planning/phases/23-foundry-ga-prep/CANDIDATE-uv.lock
    - .planning/phases/23-foundry-ga-prep/DEP-RESOLUTION-NOTES.md
    - backend/scripts/foundry_probe.py
    - backend/tests/fixtures/foundry-probe/.gitkeep
  modified: []

key-decisions:
  - "GA SDK uses AgentResponse/AgentResponseUpdate/AgentSession — NOT AgentRunResponse/AgentRunResponseUpdate/AgentThread from pre-GA docs"
  - "Both import paths work: canonical agent_framework_foundry (top-level) and agent_framework.foundry (submodule); probe harness uses top-level"
  - "agent-framework-core[all] 1.3.0 pulls many optional integration packages as transitives (194 total resolved); only agent-framework + agent-framework-foundry are directly imported"

patterns-established:
  - "Candidate dep files under .planning/phases/ — NOT applied to backend/ until Phase 24"
  - "Probe harness as standalone script under backend/scripts/ — NOT imported by backend/src/"
  - "Span-tagging contract: probe.run_id + probe.name on every probe span, no capture.trace_id"

requirements-completed: [PREP-01, PREP-02]

# Metrics
duration: 6min
completed: 2026-05-09
---

# Phase 23 Plan 01: Dependency Resolution + Probe Harness Scaffold Summary

**GA dep set (agent-framework 1.3.0 + agent-framework-foundry 1.3.0) resolves cleanly; probe harness scaffolded with 5 stubs and CLI dispatcher**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-09T03:32:37Z
- **Completed:** 2026-05-09T03:39:02Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Candidate pyproject.toml + uv.lock resolve cleanly: agent-framework 1.3.0, agent-framework-foundry 1.3.0, azure-ai-projects 2.1.0 (unblocking Phase 21.1 eval)
- GA SDK naming differences discovered and documented: AgentResponse (not AgentRunResponse), AgentResponseUpdate (not AgentRunResponseUpdate), AgentSession (not AgentThread)
- Probe harness scaffolded with 5 stubbed async probes, CLI dispatcher, span-tagging contract, and fixture output directory
- Both canonical (agent_framework_foundry) and submodule (agent_framework.foundry) import paths verified working

## Task Commits

Each task was committed atomically:

1. **Task 1: Local-only dependency-resolution spike** - `17711c5` (feat)
2. **Task 2: Scaffold foundry_probe.py with 5 stubbed probes + CLI dispatcher** - `ab1519a` (feat)

## Files Created/Modified
- `.planning/phases/23-foundry-ga-prep/CANDIDATE-pyproject.toml` - Candidate project config with GA deps (agent-framework + agent-framework-foundry, agent-framework-azure-ai removed)
- `.planning/phases/23-foundry-ga-prep/CANDIDATE-uv.lock` - Resolved candidate lockfile (194 packages)
- `.planning/phases/23-foundry-ga-prep/DEP-RESOLUTION-NOTES.md` - Spike notes: dep diff, resolved versions, import smoke test results, GA naming changes, secondary-path probe outcome
- `backend/scripts/foundry_probe.py` - Standalone GA SDK probe harness with 5 stubbed probes (streaming_shape, tool_call_extraction, tool_choice_required, session_rehydration, auth_probe), CLI dispatcher, span-tagging documentation
- `backend/tests/fixtures/foundry-probe/.gitkeep` - Empty fixture output directory for PLAN-02 probe results

## Resolved GA SDK Versions

| Package | Version |
|---------|---------|
| agent-framework | 1.3.0 |
| agent-framework-core | 1.3.0 |
| agent-framework-foundry | 1.3.0 |
| agent-framework-openai | 1.3.0 |
| azure-ai-projects | 2.1.0 |

## Decisions Made

- **GA SDK class names differ from design doc assumptions.** The GA SDK (agent-framework 1.3.0) exports `AgentResponse`, `AgentResponseUpdate`, and `AgentSession` — not `AgentRunResponse`, `AgentRunResponseUpdate`, and `AgentThread` as the design document anticipated. The probe harness and all downstream plans (PLAN-02, Phase 24) must use the actual GA names. Documented in DEP-RESOLUTION-NOTES.md.
- **Both import paths work but canonical is top-level.** `agent_framework_foundry.FoundryChatClient` (top-level package) and `agent_framework.foundry.FoundryChatClient` (submodule re-export) both resolve. Probe harness and Phase 24 use the canonical top-level path `agent_framework_foundry`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected GA SDK import names in probe harness and smoke test**
- **Found during:** Task 1 (import smoke test)
- **Issue:** Plan specified `AgentRunResponse`, `AgentRunResponseUpdate`, `AgentThread` — these names do not exist in agent-framework 1.3.0 GA SDK. The actual GA exports are `AgentResponse`, `AgentResponseUpdate`, `AgentSession`.
- **Fix:** Used correct GA names in both the import smoke test (Task 1) and the probe harness file (Task 2). Documented the naming difference in DEP-RESOLUTION-NOTES.md.
- **Files modified:** DEP-RESOLUTION-NOTES.md, backend/scripts/foundry_probe.py
- **Verification:** Import smoke test prints `ALL IMPORTS OK`; foundry_probe.py parses as valid Python
- **Committed in:** 17711c5 (Task 1), ab1519a (Task 2)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in plan's assumed GA SDK class names)
**Impact on plan:** Essential correction. The plan's class names were based on pre-GA documentation. Using the correct GA names is required for all downstream work (PLAN-02, Phase 24).

## Issues Encountered
None beyond the naming deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- PLAN-02 can fill the 5 probe function bodies and run them against the real Foundry endpoint
- The candidate dep set is proven to resolve and import correctly
- Phase 24 task group 23.1 can promote CANDIDATE-pyproject.toml + CANDIDATE-uv.lock into backend/
- All downstream imports must use `AgentResponse`/`AgentResponseUpdate`/`AgentSession` (not the plan-assumed names)

---
*Phase: 23-foundry-ga-prep*
*Completed: 2026-05-09*
