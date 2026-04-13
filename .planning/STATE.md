---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: Observability & Evals
status: unknown
last_updated: "2026-04-13T23:06:31.753Z"
progress:
  total_phases: 15
  completed_phases: 13
  total_plans: 46
  completed_plans: 44
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-05)

**Core value:** One-tap capture from a phone instantly routes through an agent that classifies, files, and clarifies -- with zero organizational effort.
**Current focus:** v3.1 Phase 16 -- Query Foundation

## Current Position

Phase: 17.4 of 22 (Foundry Observability and Codex Code Review) -- COMPLETE
Plan: 4 of 4 in current phase -- COMPLETE
Status: Phase 17.4 complete. All 4 plans executed, deployed, and verified live.
Last activity: 2026-04-13 -- Plan 17.4-04 executed (Azure Monitor alerts, instrumentation docs, post-deploy verification)

Progress: [████████████████████] 100% (Phase 17.4: 4/4 plans complete)

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
- Plans completed: 12
- Last plan duration: 1min (17.4-03)
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
- [Phase 17.3]: Sentry disabled in __DEV__ to avoid noise from React strict mode double-rendering
- [Phase 17.3]: tracesSampleRate 1.0 appropriate for single-user app (no cost concern)
- [Phase 17.3]: initSentry() at module scope before rendering, not in useEffect (catches early crashes)
- [Phase 17.3]: Placeholder values for Sentry org/project/DSN -- user replaces before first EAS build
- [Phase 18]: Used useMarkdown hook from react-native-marked instead of Markdown component to avoid nested FlatList conflict
- [Phase 18]: Dashboard metrics parsed from investigation agent prose via regex (no separate backend endpoint)
- [Phase 18]: isRecordingRef guard prevents cross-screen speech event leaks (ref not state to avoid stale closures)
- [Phase 18]: Sentry.captureMessage additive alongside console.error (no-op in dev, active in production EAS builds)
- [Phase 18]: Dashboard prompt forces both system_health AND recent_errors tool calls for data provenance consistency with deep-link
- [Phase 17.4]: ErrorFallback uses error: unknown with instanceof narrowing (Sentry FallbackRender contract)
- [Phase 17.4]: Recipe tests use autouse DNS mock fixture to prevent live resolution
- [Phase 17.4]: MOBL-04/MOBL-05 eval items deferred to Phase 21 (not implemented in Phase 18)
- [Phase 17.4]: Client factory pattern for warmup self-heal (avoids private SDK attr access)
- [Phase 17.4]: Foundry health cache on app.state (not module global) for test isolation
- [Phase 17.4]: Investigation timeout reduced to 30s (from 60s) with user-friendly error message
- [Phase 17.4]: Review prompt scoped to PR diff only (not repo-wide) to reduce noise

### Pending Todos

None.

### Roadmap Evolution

- Phase 16.1 inserted after Phase 16: Improve deployment process (URGENT)
- Phase 16.1 complete: pre-build uv lockfile validation + commit-correlated revision naming (Plan 01) + post-deploy health verification, image SHA check, revision cleanup, deploy summary (Plan 02)
- Phase 17.3 inserted after Phase 17: Address critical observability gaps (URGENT) -- COMPLETE (Sentry crash reporting verified on device)
- Phase 17.4 inserted after Phase 17.3: Foundry Observability and Codex Code Review (URGENT) -- Zero visibility into Foundry agent internals; investigation agent hangs are a black box; discovered during 18-04 gap closure (2026-04-13)

### Blockers/Concerns

- [Resolved]: Log Analytics Reader RBAC assigned to Container App managed identity (Phase 16-03)
- [Open]: azure-ai-evaluation SDK migration status (toward azure-ai-projects v2) -- check when Phase 21 starts

## Session Continuity

Last session: 2026-04-13
Stopped at: Phase 17.4 complete -- all 4 plans executed, deployed, and verified live
Resume action: Next phase per roadmap
