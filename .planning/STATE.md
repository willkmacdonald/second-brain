---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: Observability & Evals
status: unknown
last_updated: "2026-04-06T03:14:24.122Z"
progress:
  total_phases: 10
  completed_phases: 10
  total_plans: 35
  completed_plans: 35
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-05)

**Core value:** One-tap capture from a phone instantly routes through an agent that classifies, files, and clarifies -- with zero organizational effort.
**Current focus:** v3.1 Phase 16 -- Query Foundation

## Current Position

Phase: 17 of 22 (Investigation Agent) -- COMPLETE
Plan: 2 of 2 in current phase
Status: Phase 17 complete. Investigation Agent with 4 KQL tools, SSE streaming, POST /api/investigate endpoint.
Last activity: 2026-04-06 -- Plan 17-02 completed (InvestigationTools, agent registration, SSE adapter, API endpoint)

Progress: [████████████████████] 100% (Phase 17: 2/2 plans)

## Performance Metrics

**Velocity (v3.0):**
- Total plans completed: 33
- Average duration: 3.1 min
- Timeline: 2026-03-01 to 2026-03-23 (22 days)

**Velocity (v2.0):**
- Total plans completed: 16
- Average duration: 3.3 min
- Timeline: 2026-02-26 to 2026-03-01 (4 days)

**Velocity (v3.1):**
- Plans completed: 6
- Last plan duration: 7min (17-02)
- Timeline: 2026-04-05 to present

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
v3.0 decisions archived to .planning/milestones/v3.0-ROADMAP.md

**v3.1 decisions:**
- KQL programmatic queries use workspace schema (traces/requests), NOT portal schema (AppTraces/AppRequests)
- Investigation agent uses parameterized @tool functions, NOT free-form LLM-generated KQL
- Classifier evals use deterministic metrics (exact match, confusion matrix), NOT LLM-as-judge
- MCP server is standalone process with stdio transport, NOT inside Docker image
- Eval pipeline runs as CLI + GitHub Actions, NOT inside FastAPI request-response cycle
- Evaluate Azure MCP Server first before building custom MCP tool
- LogsQueryClient init non-fatal (warning + None) matching optional services pattern
- SYSTEM_HEALTH consolidated from 5 portal sections to 1 programmatic query
- [Phase 16]: Eval document models use standalone BaseModel (not BaseDocument) for non-bucket containers
- [Phase 16]: Cosmos container creation must use management plane (az CLI), not data plane RBAC (403 on DDL)
- [Phase 16]: Always regenerate uv.lock after pyproject.toml dependency changes before deploying
- [Phase 16.1]: uv version pinned to 0.5.4 in CI matching Dockerfile for lockfile format consistency
- [Phase 16.1]: Revision suffix uses sha- prefix (not bare SHA) so Azure naming rules always satisfied
- [Phase 16.1]: Health check polls 12s x 15 attempts (3min) balancing fast detection with cold start time
- [Phase 16.1]: Image SHA mismatch hard-fails; traffic weight non-100% is warning only (Azure transient behavior)
- [Phase 16.1]: Deploy summary uses if: always() so failed deploys still produce visible diagnostics
- [Phase 17]: SYSTEM_HEALTH_ENHANCED uses summarize (not toscalar+print) to support percentile() function
- [Phase 17]: server_timeout=30 on investigation queries to leave headroom under agent's 60s timeout
- [Phase 17]: Original SYSTEM_HEALTH and RECENT_FAILURES preserved as fallback alongside enhanced versions
- [Phase 17]: Investigation Agent tool_choice defaults to auto (not required) so agent can respond without calling tools
- [Phase 17]: Investigation text output is PRIMARY deliverable (SSE "text" events), not suppressed as reasoning
- [Phase 17]: SoftRateLimiter warns at 10 queries/min but never blocks requests

### Pending Todos

None.

### Roadmap Evolution

- Phase 16.1 inserted after Phase 16: Improve deployment process (URGENT)
- Phase 16.1 complete: pre-build uv lockfile validation + commit-correlated revision naming (Plan 01) + post-deploy health verification, image SHA check, revision cleanup, deploy summary (Plan 02)

### Blockers/Concerns

- [Resolved]: Log Analytics Reader RBAC assigned to Container App managed identity (Phase 16-03)
- [Open]: azure-ai-evaluation SDK migration status (toward azure-ai-projects v2) -- check when Phase 21 starts

## Session Continuity

Last session: 2026-04-06
Stopped at: Completed 17-02-PLAN.md -- Phase 17 complete (Investigation Agent with tools, SSE streaming, API endpoint)
Resume action: Begin Phase 18 planning (Mobile Chat UI for Investigation Agent)
