---
phase: 17-investigation-agent
plan: 02
subsystem: api
tags: [foundry-agent, sse-streaming, investigation, app-insights, rate-limiter, opentelemetry]

# Dependency graph
requires:
  - phase: 17-investigation-agent
    plan: 01
    provides: "KQL query functions (query_enhanced_system_health, query_recent_failures_filtered, query_usage_patterns, query_capture_trace, query_latest_capture_trace_id) and Pydantic models"
  - phase: 16-query-foundation
    provides: "LogsQueryClient, execute_kql(), SSE encoding (encode_sse)"
provides:
  - "InvestigationTools class with 4 @tool functions: trace_lifecycle, recent_errors, system_health, usage_patterns"
  - "ensure_investigation_agent() non-fatal registration function"
  - "stream_investigation() SSE adapter yielding text/thinking/tool_call/tool_error/done events"
  - "POST /api/investigate endpoint with 503 guards and SSE streaming"
  - "SoftRateLimiter warn-only rate limiter (10 req/min sliding window)"
  - "azure_ai_investigation_agent_id config setting"
  - "Investigation agent wired into lifespan and warmup loop"
affects: [18-mobile-chat, 19-mcp-tool]

# Tech tracking
tech-stack:
  added: []
  patterns: [investigation-sse-protocol, soft-rate-limiting, text-as-primary-output, auto-tool-choice]

key-files:
  created:
    - backend/src/second_brain/tools/investigation.py
    - backend/src/second_brain/agents/investigation.py
    - backend/src/second_brain/streaming/investigation_adapter.py
    - backend/src/second_brain/api/investigate.py
  modified:
    - backend/src/second_brain/config.py
    - backend/src/second_brain/main.py

key-decisions:
  - "tool_choice defaults to auto (not required) so agent can respond without calling tools"
  - "Text output is PRIMARY deliverable -- yielded as 'text' SSE events, NOT suppressed as reasoning"
  - "SoftRateLimiter warns at 10 queries/min but never blocks requests"
  - "Investigation agent added to warmup loop for cold start prevention"
  - "TIME_RANGE_MAP maps user-friendly strings to both KQL literals and timedeltas"

patterns-established:
  - "Investigation SSE protocol: thinking -> tool_call* -> text* -> done (with thread_id)"
  - "Soft rate limiting pattern: SoftRateLimiter.check() returns bool, caller decides action"
  - "Non-fatal agent registration: try/except sets app.state to None, endpoint returns 503"
  - "Tool functions return JSON strings (not formatted text) -- agent formats for humans"

requirements-completed: [INV-01, INV-02, INV-03, INV-04, INV-05]

# Metrics
duration: 7min
completed: 2026-04-06
---

# Phase 17 Plan 02: Investigation Agent Core Summary

**Investigation Agent with 4 KQL tools, SSE streaming adapter, and POST /api/investigate endpoint for natural language observability queries**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-06T03:02:16Z
- **Completed:** 2026-04-06T03:08:55Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created InvestigationTools class with 4 @tool functions wrapping Plan 01 query functions: trace_lifecycle (auto-resolves latest capture), recent_errors (component filter, capped at 10), system_health (P95/P99 + trend comparison), usage_patterns (day/hour/bucket/destination grouping)
- Built SSE streaming adapter where text output is the PRIMARY deliverable (critical difference from Classifier which suppresses text as reasoning)
- Wired POST /api/investigate with 503 guards for missing LogsQueryClient or Investigation Agent, SoftRateLimiter at 10 queries/min, and 60-second timeout
- Non-fatal agent registration in lifespan with Investigation client added to warmup loop

## Task Commits

Each task was committed atomically:

1. **Task 1: Create InvestigationTools class with 4 @tool functions** - `b29332c` (feat)
2. **Task 2: Create agent registration, SSE adapter, API endpoint, rate limiter, and wire into lifespan** - `dc2054c` (feat)

## Files Created/Modified
- `backend/src/second_brain/tools/investigation.py` - InvestigationTools class with 4 @tool functions (trace_lifecycle, recent_errors, system_health, usage_patterns) and TIME_RANGE_MAP
- `backend/src/second_brain/agents/investigation.py` - ensure_investigation_agent() non-fatal registration following admin agent pattern
- `backend/src/second_brain/streaming/investigation_adapter.py` - stream_investigation() async generator yielding SSE events + SoftRateLimiter class
- `backend/src/second_brain/api/investigate.py` - POST /api/investigate endpoint with InvestigateBody model and 503 guards
- `backend/src/second_brain/config.py` - Added azure_ai_investigation_agent_id setting
- `backend/src/second_brain/main.py` - Investigation agent wired into lifespan (non-fatal), tools bound, client created, warmup registered, router included

## Decisions Made
- tool_choice defaults to auto (not "required") so the agent can respond conversationally without calling tools (e.g., "thanks", "what can you help with?") -- per RESEARCH pitfall #6
- Text output is the PRIMARY deliverable yielded as "text" SSE events -- this is the fundamental difference from the Classifier adapter which suppresses text as internal reasoning
- SoftRateLimiter warns but never blocks -- returning False from check() causes a rate_warning SSE event but does not prevent the query from executing
- Investigation client added to the warmup loop alongside classifier and admin agents for cold start prevention
- TIME_RANGE_MAP maps user-friendly strings ("1h", "6h", "24h", "3d", "7d") to both KQL duration literals and Python timedeltas for clean parameter validation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required

After deploying, the following environment variable must be set on the Container App:
- `AZURE_AI_INVESTIGATION_AGENT_ID` - Set to the agent ID after creating the Investigation Agent in AI Foundry portal with appropriate instructions

The agent will auto-create in Foundry on first startup if the env var is empty, but instructions must be configured manually in the AI Foundry portal.

## Next Phase Readiness
- POST /api/investigate endpoint ready for Phase 18 (mobile chat UI) to consume
- SSE event protocol (thinking/tool_call/text/done) ready for mobile EventSource client
- Thread ID in "done" event enables multi-turn conversation support
- All 5 INV requirements covered: NL questions (INV-01), trace lifecycle (INV-02), error viewing (INV-03), system health (INV-04), usage patterns (INV-05)
- Phase 17 is complete -- all 2 plans finished

## Self-Check: PASSED

All 7 files verified on disk (4 created, 2 modified, 1 SUMMARY). Both task commits (b29332c, dc2054c) found in git log. SUMMARY.md exists.

---
*Phase: 17-investigation-agent*
*Completed: 2026-04-06*
