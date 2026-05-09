# Expected deltas: investigation/trace_lifecycle

Captured: 2026-05-09 17:36 UTC
Trace ID: 4c415b01-c8e8-430d-a430-e5b08e9efbfe (documentary only -- investigation endpoint does not read X-Trace-Id)
Thread ID out: thread_tawNr7cX1vXGZHQDiG2XIK3r
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- SSE event types and ORDER must match: thinking, tool_call, text (multiple), done
- SSE field values for contract fields: tool_call.tool == "trace_lifecycle", done.thread_id present
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
- The specific trace lifecycle details will differ if a different capture trace_id is queried in GA

## Notes

Agent was asked about capture 08c31eb1-6815-452a-affb-1d290b7d5885 (a real capture from 2026-05-09). The trace_lifecycle tool was called with this UUID. For GA replay, a valid capture trace_id from the GA system should be substituted -- the important contract is that the tool IS called and returns span lifecycle data, not the specific trace_id queried.
