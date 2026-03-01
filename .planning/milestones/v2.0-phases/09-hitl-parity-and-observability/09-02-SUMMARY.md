---
phase: 09-hitl-parity-and-observability
plan: 02
subsystem: observability
tags: [opentelemetry, otel, application-insights, tracing, agent-framework, spans]

# Dependency graph
requires:
  - phase: 09-01
    provides: "HITL parity endpoints (follow-up, recategorize, pending PATCH)"
  - phase: 08-01
    provides: "Streaming adapter async generator functions"
  - phase: 07-02
    provides: "Middleware skeletons (AuditAgentMiddleware, ToolTimingMiddleware)"
provides:
  - "OTel spans on agent runs with agent.name and agent.duration_ms"
  - "OTel spans on tool calls with classification attributes (bucket, confidence, status, item_id)"
  - "OTel endpoint-level spans on capture_text, capture_voice, capture_follow_up"
  - "OTel span on recategorize endpoint with item_id, old_bucket, new_bucket, success"
  - "Automatic token usage tracking via enable_instrumentation()"
affects: [10-scheduled-nudges, 11-weekly-review, 12-polish]

# Tech tracking
tech-stack:
  added: [opentelemetry (already transitive via azure-monitor-opentelemetry)]
  patterns: [OTel tracer per module, span-inside-async-generator, classification-specific span attributes]

key-files:
  created: []
  modified:
    - backend/src/second_brain/main.py
    - backend/src/second_brain/agents/middleware.py
    - backend/src/second_brain/streaming/adapter.py
    - backend/src/second_brain/api/inbox.py

key-decisions:
  - "Spans created inside async generators (not endpoint handlers) to preserve OTel context across async boundaries"
  - "Debug-level logging retained alongside OTel spans as secondary observability channel"
  - "Defensive result extraction in middleware (hasattr/isinstance) handles both raw dict and FunctionResult wrapper"

patterns-established:
  - "OTel tracer per module: trace.get_tracer('second_brain.{module}') at module level"
  - "Span-inside-generator: OTel spans wrap entire async generator body including try/except"
  - "Classification span attributes: capture.outcome, capture.bucket, capture.confidence on endpoint spans"

requirements-completed: [OBSV-01, OBSV-02]

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 9 Plan 02: Observability Summary

**OTel spans on middleware (agent runs + tool calls) and streaming endpoints with classification-specific attributes, plus automatic token usage tracking via enable_instrumentation()**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T17:54:15Z
- **Completed:** 2026-02-27T17:57:43Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Upgraded middleware from console-only logging to OTel spans with classification-specific attributes (bucket, confidence, status, item_id)
- Added endpoint-level OTel trace spans inside all three streaming async generators (text, voice, follow-up)
- Enabled agent-framework SDK instrumentation for automatic token usage metrics (gen_ai.usage.input_tokens, gen_ai.usage.output_tokens)
- Added OTel span on recategorize PATCH endpoint per CONTEXT.md locked decision

## Task Commits

Each task was committed atomically:

1. **Task 1: Enable SDK instrumentation and upgrade middleware to OTel spans** - `63686a7` (feat)
2. **Task 2: Add endpoint-level trace spans in streaming adapter** - `dd75672` (feat)

## Files Created/Modified
- `backend/src/second_brain/main.py` - Added enable_instrumentation() call after configure_azure_monitor()
- `backend/src/second_brain/agents/middleware.py` - Replaced console logging with OTel spans in both middleware classes
- `backend/src/second_brain/streaming/adapter.py` - Wrapped all three streaming functions in endpoint-level OTel spans
- `backend/src/second_brain/api/inbox.py` - Wrapped recategorize endpoint in OTel span with item/bucket/success attributes

## Decisions Made
- Spans created inside async generators (not endpoint handlers) to preserve OTel context across async boundaries per RESEARCH pitfall 4
- Debug-level logging retained alongside OTel spans as secondary observability channel (dual output)
- Defensive result extraction in ToolTimingMiddleware uses hasattr/isinstance to handle both raw dict and FunctionResult wrapper

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. OTel spans flow automatically through the existing Azure Monitor exporter configured at startup.

## Next Phase Readiness
- Per-classification traces with token usage are now visible in Application Insights
- Phase 9 is complete (both plans done) - ready for Phase 10 (Scheduled Nudges)
- Spans provide baseline observability for monitoring agent costs and performance

## Self-Check: PASSED

All 4 modified files exist on disk. Both task commits (63686a7, dd75672) verified in git log.

---
*Phase: 09-hitl-parity-and-observability*
*Completed: 2026-02-27*
