---
phase: 23-foundry-ga-prep
plan: 02
subsystem: testing
tags: [foundry, azure-ai, agent-framework, probes, fixtures, ga-sdk]

# Dependency graph
requires:
  - phase: 23-foundry-ga-prep plan 01
    provides: "foundry_probe.py scaffold with 5 stubs + candidate dep set"
provides:
  - "5 JSON probe fixtures capturing real GA SDK behavior (streaming shape, tool call extraction, tool_choice_required, session rehydration, auth)"
  - "FOUNDRY-PROBE-FINDINGS.md with empirical GA SDK API differences from docs"
  - "foundry_probe.py with 5 fully implemented probe bodies"
affects: [23-foundry-ga-prep plan 05, phase-24-foundry-ga-migration]

# Tech tracking
tech-stack:
  added: [agent-framework 1.3.0, agent-framework-foundry 1.3.0]
  patterns: [ProbeTagSpanProcessor for telemetry isolation, ContextVar-based span tagging at creation time]

key-files:
  created:
    - backend/tests/fixtures/foundry-probe/streaming_shape.json
    - backend/tests/fixtures/foundry-probe/tool_call_extraction.json
    - backend/tests/fixtures/foundry-probe/tool_choice_required.json
    - backend/tests/fixtures/foundry-probe/session_rehydration.json
    - backend/tests/fixtures/foundry-probe/auth_probe.json
    - .planning/phases/23-foundry-ga-prep/FOUNDRY-PROBE-FINDINGS.md
  modified:
    - backend/scripts/foundry_probe.py

key-decisions:
  - "GA SDK uses AgentResponse/AgentResponseUpdate/AgentSession -- NOT the pre-GA names AgentRunResponse/AgentRunResponseUpdate/AgentThread"
  - "Streaming uses agent.run(stream=True) returning ResponseStream -- NOT agent.run_stream()"
  - "tool_choice passed via options=ChatOptions(tool_choice=...) -- NOT as direct keyword argument"
  - "FoundryChatClient takes project_endpoint and model -- NOT endpoint and model_deployment_name"
  - "Framework handles tool execution internally during streaming -- adapter does NOT need manual tool call detection"
  - "AgentSession is client-side conversation history -- no server-side deletion needed"

patterns-established:
  - "ProbeTagSpanProcessor: ContextVar-based span tagging at creation time for telemetry isolation"
  - "Module-entry telemetry setup: _setup_probe_telemetry() called before any SDK construction"
  - "Probe body ordering: ContextVars set + processor installed BEFORE client/agent construction"

requirements-completed: [PREP-03, PREP-04]

# Metrics
duration: 12min
completed: 2026-05-09
---

# Phase 23 Plan 02: Foundry Probe Execution Summary

**5 Foundry GA SDK probes executed against real endpoint, capturing streaming shape, tool call extraction, tool_choice='required' behavior, session rehydration, and auth -- all fixtures + FINDINGS.md documenting critical GA SDK API name differences from pre-GA docs**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-09T20:35:00Z
- **Completed:** 2026-05-09T20:47:28Z
- **Tasks:** 4 (3 auto + 1 checkpoint approved)
- **Files modified:** 7

## Accomplishments
- Replaced all 5 NotImplementedError stubs in foundry_probe.py with real GA SDK probe implementations using ProbeTagSpanProcessor for telemetry isolation
- Executed all 5 probes against the live Foundry endpoint, capturing JSON fixtures that reveal the actual GA SDK wire format
- Discovered critical GA SDK API name differences: AgentResponse (not AgentRunResponse), agent.run(stream=True) (not run_stream()), ChatOptions(tool_choice=...) (not direct kwarg), project_endpoint/model (not endpoint/model_deployment_name)
- Wrote FOUNDRY-PROBE-FINDINGS.md answering all 4 design-mandated questions per probe, directly consumable by the Phase 24 planner

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement all 5 probe bodies** - `032948a` (feat), `fe20748` (fix: correct GA SDK API names), `b5ea236` (fix: correct FoundryChatClient params and message format)
2. **Task 2: Run all 5 probes, capture JSON fixtures** - `96c180c` (feat)
3. **Task 3: Write FOUNDRY-PROBE-FINDINGS.md** - `2a7db51` (docs)
4. **Task 4: Operator review checkpoint** - Approved (no commit; verification-only)

**Plan metadata:** [this commit] (docs: complete plan)

## Files Created/Modified
- `backend/scripts/foundry_probe.py` - 5 fully implemented GA SDK probes with ProbeTagSpanProcessor, telemetry setup, echo_back tool, session cleanup helper
- `backend/tests/fixtures/foundry-probe/streaming_shape.json` - 25 AgentResponseUpdate events from agent.run(stream=True) showing field shape and tool execution lifecycle
- `backend/tests/fixtures/foundry-probe/tool_call_extraction.json` - AgentResponse structure showing where tool calls appear (messages[].content[] walk)
- `backend/tests/fixtures/foundry-probe/tool_choice_required.json` - 3 trials (auto/provider_dict/required) showing tool_choice behavior via ChatOptions
- `backend/tests/fixtures/foundry-probe/session_rehydration.json` - Two-turn AgentSession round-trip with session_id/service_session_id shape
- `backend/tests/fixtures/foundry-probe/auth_probe.json` - AzureCliCredential token acquisition + agent execution under DefaultAzureCredential
- `.planning/phases/23-foundry-ga-prep/FOUNDRY-PROBE-FINDINGS.md` - Human-readable summary of all 5 probe results with Phase 24 implications

## Decisions Made
- GA SDK uses `AgentResponse`/`AgentResponseUpdate`/`AgentSession` -- the pre-GA names from docs and design spec are wrong
- Streaming is `agent.run(stream=True)` returning a `ResponseStream`, not `agent.run_stream()`
- `tool_choice` must go through `options=ChatOptions(tool_choice=...)`, not as a direct keyword argument
- `FoundryChatClient` takes `project_endpoint` and `model` params, not `endpoint` and `model_deployment_name`
- Messages are passed as plain strings or `Message` objects, not `{"role": "user", "content": "..."}` dicts
- Framework handles tool execution internally during streaming -- the adapter does NOT need manual tool call detection
- `AgentSession` is client-side only (no server-side deletion needed) -- probe cleanup returned false for all attempted method names

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected GA SDK API names in probe harness**
- **Found during:** Task 1
- **Issue:** Plan specified pre-GA names (`AgentRunResponse`, `AgentRunResponseUpdate`, `AgentThread`, `agent.run_stream()`) that do not exist in GA SDK 1.3.0
- **Fix:** Updated all imports and usages to GA names (`AgentResponse`, `AgentResponseUpdate`, `AgentSession`, `agent.run(stream=True)`)
- **Files modified:** backend/scripts/foundry_probe.py
- **Verification:** All 5 probes executed successfully against real endpoint
- **Committed in:** `fe20748`

**2. [Rule 1 - Bug] Corrected FoundryChatClient constructor params and message format**
- **Found during:** Task 1
- **Issue:** Plan specified `endpoint` and `model_deployment_name` params and dict-style messages; GA SDK uses `project_endpoint`, `model`, and string messages
- **Fix:** Updated FoundryChatClient construction and message passing throughout all 5 probes
- **Files modified:** backend/scripts/foundry_probe.py
- **Verification:** All 5 probes executed successfully against real endpoint
- **Committed in:** `b5ea236`

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes were necessary because the plan was written against pre-GA documentation. The probes themselves were designed to discover exactly these discrepancies. No scope creep.

## Issues Encountered
None beyond the expected GA SDK API name differences, which were the entire purpose of running the probes.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 23-05 (CONFIG-DELTAS.md + SPAN-NAME-MAPPING.md + AUDITOR-VERIFICATION.md) is unblocked -- it depends on the probe findings documented here
- Phase 24 planner has all empirical data needed for tool_choice='required', session rehydration, streaming shape, and tool call extraction
- All 5 fixtures are valid JSON with probe.run_id + probe.name embedded

## Self-Check: PASSED

All 7 files verified present. All 5 task commit hashes verified in git log.

---
*Phase: 23-foundry-ga-prep*
*Completed: 2026-05-09*
