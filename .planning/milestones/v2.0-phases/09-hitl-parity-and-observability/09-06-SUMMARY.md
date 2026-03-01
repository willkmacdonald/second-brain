---
phase: 09-hitl-parity-and-observability
plan: 06
subsystem: agent-instructions
tags: [classifier, foundry, prompt-engineering, hitl]

# Dependency graph
requires:
  - phase: 09-04
    provides: LOW_CONFIDENCE SSE event and pending capture flow
  - phase: 09-05
    provides: Voice follow-up for misunderstood clarifications
provides:
  - "Classifier agent instructions with explicit misunderstood vs pending boundary rules"
  - "Follow-up classification context weighting for action-verb routing to correct buckets"
affects: [10-specialist-agents, future-uat]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Instruction tuning for agent behavior boundaries"]

key-files:
  created: []
  modified: []

key-decisions:
  - "Misunderstood reserved for genuinely nonsensical input; any classifiable text (even 0.3 confidence) uses pending"
  - "Follow-up context overrides initial ambiguity entirely (not averaged with it)"
  - "Action-verb weighting: build/create -> Projects, reach out/call -> People, thinking/what if -> Ideas, pay/book -> Admin"

patterns-established:
  - "Status Decision Rules: concrete boundary between misunderstood and pending in agent instructions"
  - "Follow-up Classification Context: action-verb weighting section added after bucket definitions"

requirements-completed: [HITL-03]

# Metrics
duration: 1min
completed: 2026-02-27
---

# Phase 9 Plan 06: Classifier Instruction Tuning Summary

**Classifier agent instructions updated with misunderstood vs pending boundary rules and action-verb follow-up context weighting**

## Performance

- **Duration:** 1 min (human-action checkpoint -- portal update by user)
- **Started:** 2026-02-27
- **Completed:** 2026-02-27
- **Tasks:** 1
- **Files modified:** 0 (Foundry portal instructions only)

## Accomplishments
- Added "Status Decision Rules" section to classifier agent instructions defining the concrete boundary between misunderstood (genuinely nonsensical) and pending (vague but classifiable)
- Added "Follow-up Classification Context" section with action-verb weighting for follow-up reclassification routing (build/create -> Projects, reach out/call -> People, etc.)
- Follow-up context now overrides initial ambiguity entirely rather than being averaged with it

## Task Commits

1. **Task 1: Update classifier agent instructions in AI Foundry portal** - No code commit (manual Foundry portal action completed by user)

**Plan metadata:** See final docs commit below

## Files Created/Modified

No source files modified -- this plan updated the classifier agent instructions directly in the AI Foundry portal (agent ID: `asst_Fnjkq5RVrvdFIOSqbreAwxuq`).

## Decisions Made
- Misunderstood is reserved strictly for genuinely nonsensical, garbled, or meaningless input where no bucket can be assigned at all
- Any text where a bucket can be guessed (even at 0.3 confidence) should use pending status with LOW_CONFIDENCE event, not misunderstood
- Follow-up classification context is the most important signal and should override the initial ambiguity entirely
- Action-verb weighting provides concrete routing rules: build/create/make -> Projects, reach out/call/email -> People, thinking/what if -> Ideas, pay/book/register -> Admin

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - the plan consisted of a single human-action checkpoint (Foundry portal update) which the user completed successfully.

## User Setup Required

None - no external service configuration required beyond the portal update that was already completed.

## Next Phase Readiness
- Phase 9 gap closure is complete (all 6 plans done)
- Classifier instruction tuning addresses the two UAT-discovered issues: misunderstood vs pending boundary and follow-up context weighting
- Ready for Phase 10: Specialist Agents

## Self-Check: PASSED

- FOUND: 09-06-SUMMARY.md
- FOUND: 83fc28a (checkpoint commit)
- HITL-03 already marked complete in REQUIREMENTS.md

---
*Phase: 09-hitl-parity-and-observability*
*Completed: 2026-02-27*
