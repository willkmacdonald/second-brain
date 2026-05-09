# Expected deltas: investigation/recent_errors

Captured: 2026-05-09 17:33 UTC
Trace ID: 58d60f86-8ce1-4232-bd74-c532042b6a38 (documentary only -- investigation endpoint does not read X-Trace-Id)
Thread ID out: thread_PQLeQCE8hilSFxh2XT5h1qGZ
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- SSE event types and ORDER must match: thinking, tool_call, text (multiple), done
- SSE field values for contract fields: tool_call.tool == "recent_errors", done.thread_id present
- Span attribute names:
  - The custom `investigate` span (AppDependencies kind, started by `tracer.start_as_current_span("investigate")` at `investigation_adapter.py:96`) carries `Properties["investigate.thread_id_out"]` matching the server-generated thread_id parsed from the SSE `done` event (`investigation_adapter.py:187-188`).
  - The AppRequests row inherits the same `OperationId` and is matched by URL pattern `endswith '/api/investigate'`.
  - `capture.trace_id` is NOT expected on investigation spans because `/api/investigate` doesn't read `X-Trace-Id` (per `api/investigate.py:30-50`). Phase 24 task group 23.1 (Investigation migration) adds proper trace correlation when the investigation surface is touched.

## Allowed-different (RC != GA, not a regression)

- Timestamps (TimeGenerated)
- Server-generated IDs (OperationId, ParentId, run_id, message_id)
- Span Names (per .planning/phases/23-foundry-ga-prep/SPAN-NAME-MAPPING.md -- produced by PLAN-05)
- Token counts and durations (model behavior may vary slightly)
- Free-text content of agent responses (model is non-deterministic)
- The specific errors found (or lack thereof) will differ between captures

## Notes

Agent called the recent_errors tool with a 1-hour time range. The RC capture returned no errors found in the last hour -- this is the expected happy path. If GA returns errors (because they actually exist), that is not a wire-contract failure.
