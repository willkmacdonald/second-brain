---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: Observability & Evals
status: active
last_updated: "2026-04-05T00:00:00.000Z"
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-05)

**Core value:** One-tap capture from a phone instantly routes through an agent that classifies, files, and clarifies -- with zero organizational effort.
**Current focus:** v3.1 Phase 16 -- Query Foundation

## Current Position

Phase: 16 of 22 (Query Foundation)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-04-05 -- Roadmap created for v3.1

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity (v3.0):**
- Total plans completed: 33
- Average duration: 3.1 min
- Timeline: 2026-03-01 to 2026-03-23 (22 days)

**Velocity (v2.0):**
- Total plans completed: 16
- Average duration: 3.3 min
- Timeline: 2026-02-26 to 2026-03-01 (4 days)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
v3.0 decisions archived to .planning/milestones/v3.0-ROADMAP.md

**v3.1 decisions (from research):**
- KQL programmatic queries use workspace schema (traces/requests), NOT portal schema (AppTraces/AppRequests)
- Investigation agent uses parameterized @tool functions, NOT free-form LLM-generated KQL
- Classifier evals use deterministic metrics (exact match, confusion matrix), NOT LLM-as-judge
- MCP server is standalone process with stdio transport, NOT inside Docker image
- Eval pipeline runs as CLI + GitHub Actions, NOT inside FastAPI request-response cycle
- Evaluate Azure MCP Server first before building custom MCP tool

### Pending Todos

None.

### Blockers/Concerns

- [Open]: Log Analytics Reader RBAC needed for Container App managed identity and local dev credential
- [Open]: azure-ai-evaluation SDK migration status (toward azure-ai-projects v2) -- check when Phase 21 starts

## Session Continuity

Last session: 2026-04-05
Stopped at: Phase 16 context gathered
Resume action: Plan Phase 16 with /gsd:plan-phase 16
