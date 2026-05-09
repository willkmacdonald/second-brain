---
phase: 23-foundry-ga-prep
plan: 03
subsystem: testing
tags: [golden-trace, fixtures, app-insights, sse, kql, investigation, admin, classifier]

requires:
  - phase: 23-foundry-ga-prep
    provides: "Foundry probe harness and candidate dep set from plans 01-02"
provides:
  - "18 golden-trace fixtures (5 investigation + 5 admin + 8 classifier)"
  - "FIXTURE-CAPTURE-LOG.md with per-fixture trace IDs and metadata"
  - "Wire-shape source of truth for Phase 24 pre-deploy replay gates"
affects: [23-foundry-ga-prep, 24-foundry-ga-migration]

tech-stack:
  added: []
  patterns: [golden-trace-fixture-format, two-stage-admin-capture, investigation-OperationId-join]

key-files:
  created:
    - backend/tests/fixtures/investigation/*.{input.json,sse.jsonl,spans.json,expected-deltas.md}
    - backend/tests/fixtures/admin/*.{input.json,sse.jsonl,spans.json,expected-deltas.md}
    - backend/tests/fixtures/classifier/*.{input.json,sse.jsonl,spans.json,expected-deltas.md}
    - backend/tests/fixtures/FIXTURE-CAPTURE-LOG.md
  modified: []

key-decisions:
  - "Auth header uses Authorization: Bearer (not X-API-Key) per actual auth.py middleware"
  - "Investigation spans correlate via OperationId-join on custom investigate AppDependencies span (not capture.trace_id)"
  - "Admin spans correlate via capture.trace_id inherited from classifier Stage A"
  - "audit_correlation fixture: agent chose trace_lifecycle tool (model-behavior, not wire-contract issue)"
  - "low_confidence_followup: turn-2 not captured because RC follow-up endpoint requires MISUNDERSTOOD with foundryThreadId"
  - "destination_management and affinity_rule_edit: admin agent did not invoke expected tools (model-behavior observation)"

patterns-established:
  - "Four-file fixture format: input.json, sse.jsonl, spans.json, expected-deltas.md"
  - "Two-stage admin capture: Stage A (POST /api/capture) + Stage B (GET /api/errands)"
  - "Investigation span export: thread_id_out -> AppDependencies -> OperationId join"

requirements-completed: [PREP-05]

duration: 57min
completed: 2026-05-09
---

# Phase 23 Plan 03: Golden-Trace Fixtures Summary

**18 golden-trace fixtures captured against deployed RC (brain.willmacdonald.com) covering investigation, admin, and classifier agent surfaces for Phase 24 replay gates**

## Performance

- **Duration:** 57 min
- **Started:** 2026-05-09T17:32:46Z
- **Completed:** 2026-05-09T18:30:33Z
- **Tasks:** 5/5 completed (Task 5 checkpoint approved by operator)
- **Files created:** 73

## Accomplishments

- 5 investigation fixtures (recent_errors, system_health, usage_patterns, trace_lifecycle, audit_correlation) with App Insights span trees
- 5 admin fixtures (errand_routing, task_creation, recipe_extraction, destination_management, affinity_rule_edit) with two-stage capture pattern
- 8 classifier fixtures (5 text buckets, 1 voice, 1 low-confidence, 1 deliberate-misunderstood) with D-07b documentation
- FIXTURE-CAPTURE-LOG.md recording all 18 trace IDs, timestamps, side effects, and re-capture protocol

## Task Commits

Each task was committed atomically:

1. **Task 1: Capture 5 investigation fixtures** - `d7120ee` (feat)
2. **Task 2: Capture 5 admin fixtures** - `4a3d15f` (feat)
3. **Task 3: Capture 8 classifier fixtures** - `2d26538` (feat)
4. **Task 4: Write FIXTURE-CAPTURE-LOG.md** - `c170f76` (docs)

## Files Created/Modified

- `backend/tests/fixtures/investigation/` - 20 files (5 fixtures x 4 files each)
- `backend/tests/fixtures/admin/` - 20 files (5 fixtures x 4 files each)
- `backend/tests/fixtures/classifier/` - 32 files (8 fixtures x 4 files each)
- `backend/tests/fixtures/FIXTURE-CAPTURE-LOG.md` - Operator log with all metadata

## Decisions Made

- Auth header uses `Authorization: Bearer` per actual `auth.py` middleware (plan specified `X-API-Key` which is incorrect)
- Investigation span export uses OperationId-join on custom `investigate` AppDependencies span (not capture.trace_id, which investigation endpoint does not propagate)
- audit_correlation fixture: agent autonomously chose `trace_lifecycle` tool instead of `audit_correlation`; documented as model-behavior observation
- low_confidence_followup: turn-2 follow-up not captured because the RC follow-up endpoint requires a `foundryThreadId` on the inbox item, only set for MISUNDERSTOOD items via the tool-call path
- text_admin_task re-captured: initial "Submit expense report" classified as Projects; replaced with "Pay the electric bill" which classified as Admin
- voice_person: audio generated via macOS TTS `say` command, uploaded as m4a with explicit `type=audio/m4a` content type

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Auth header format correction**
- **Found during:** Task 1 (investigation captures)
- **Issue:** Plan specified `X-API-Key: $API_KEY` header, but deployed backend uses `Authorization: Bearer <key>` per `auth.py` middleware
- **Fix:** Used correct `Authorization: Bearer $API_KEY` header for all 18 captures
- **Files modified:** No code files; curl commands corrected in execution
- **Verification:** All captures returned HTTP 200 (verified in spans.json AppRequests rows)

**2. [Rule 1 - Bug] Voice capture content type**
- **Found during:** Task 3 (voice_person capture)
- **Issue:** curl without explicit content type sent `application/octet-stream`, rejected by API (ALLOWED_AUDIO_TYPES whitelist)
- **Fix:** Added `type=audio/m4a` to curl `-F` flag
- **Verification:** Voice capture classified successfully as People (0.9)

**3. [Rule 1 - Bug] Admin tool_invoked case sensitivity**
- **Found during:** Task 2 verification
- **Issue:** Plan verifier checks `admin.tool_invoked == "true"` (lowercase) but Python OTel sets `"True"` (capital T)
- **Fix:** Adjusted verification to check both `"True"` and `"true"` variants
- **Verification:** 3/5 admin fixtures correctly show tool_invoked=True

---

**Total deviations:** 3 auto-fixed (3 bugs in plan assumptions)
**Impact on plan:** All fixes necessary for correct execution. No scope creep. Two admin fixtures (destination_management, affinity_rule_edit) have no tool invocations due to model behavior; documented in expected-deltas and capture log.

## Issues Encountered

- Admin fixtures errand_routing and task_creation initially had no admin_agent_process spans: the items were consumed by a batch Stage B call before individual span export. Fixed by re-capturing with immediate Stage B firing and wider export windows.
- text_admin_task initially classified as Projects instead of Admin. Re-captured with clearer admin-oriented text ("Pay the electric bill").
- destination_management and affinity_rule_edit admin processing failed to invoke tools (5 attempts and 1 attempt respectively). Documented as model-behavior observation, not wire-contract failure.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all fixtures contain real captured data.

## Next Phase Readiness

- 18 fixtures approved by operator and ready for Phase 24 pre-deploy replay gates
- PLAN-04 (eval baseline) can run against the same deployed system
- PLAN-05 (SPAN-NAME-MAPPING.md) is referenced by expected-deltas files but not yet produced

## Self-Check: PASSED

All 73 fixture files verified present. All 4 task commits verified in git log (d7120ee, 4a3d15f, 2d26538, c170f76). Task 5 checkpoint approved by operator. SUMMARY.md exists.

---
*Phase: 23-foundry-ga-prep*
*Completed: 2026-05-09*
