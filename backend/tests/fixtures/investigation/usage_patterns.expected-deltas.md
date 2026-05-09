# Expected deltas: investigation/usage_patterns

Captured: 2026-05-09 17:35 UTC
Trace ID: fc13fdb3-f0c5-4f0d-bd52-b8ad52455e5e (documentary only -- investigation endpoint does not read X-Trace-Id)
Thread ID out: thread_nnjeASbYY7VOecE2Sm2For1o
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- SSE event types and ORDER must match: thinking, tool_call, text (multiple), done
- SSE field values for contract fields: tool_call.tool == "usage_patterns", done.thread_id present
- Span attribute names:
  - The custom `investigate` span (AppDependencies kind, started by `tracer.start_as_current_span("investigate")` at `investigation_adapter.py:96`) carries `Properties["investigate.thread_id_out"]` matching the server-generated thread_id parsed from the SSE `done` event (`investigation_adapter.py:187-188`).
  - The AppRequests row inherits the same `OperationId` and is matched by URL pattern `endswith '/api/investigate'`.
  - `capture.trace_id` is NOT expected on investigation spans because `/api/investigate` doesn't read `X-Trace-Id` (per `api/investigate.py:30-50`). Phase 24 task group 23.1 (Investigation migration) adds proper trace correlation.

## Allowed-different (RC != GA, not a regression)

- Timestamps (TimeGenerated)
- Server-generated IDs (OperationId, ParentId, run_id, message_id)
- Span Names (per .planning/phases/23-foundry-ga-prep/SPAN-NAME-MAPPING.md -- produced by PLAN-05)
- Token counts and durations (model behavior may vary slightly)
- Free-text content of agent responses (model is non-deterministic)
- Specific capture counts and bucket breakdowns will differ between captures (time-dependent data)

## Notes

Agent called usage_patterns tool with a 7-day window and bucket breakdown. The actual capture counts and bucket distribution are non-deterministic and time-dependent. Only the event shape (tool called with appropriate parameters, response streamed as text) is the wire contract.
