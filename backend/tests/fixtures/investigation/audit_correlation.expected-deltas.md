# Expected deltas: investigation/audit_correlation

Captured: 2026-05-09 17:37 UTC
Trace ID: 6b5efa1d-2d1e-4a0f-924e-a108cfaaa6e6 (documentary only -- investigation endpoint does not read X-Trace-Id)
Thread ID out: thread_ggJLIOswMGRbMmg2eLoteytc
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- SSE event types and ORDER must match: thinking, tool_call, text (multiple), done
- SSE field values for contract fields: done.thread_id present
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
- Whether the agent calls audit_correlation or another tool is model-dependent

## Notes

Investigation agent was asked to "Audit correlation for capture de875d59-1335-4143-b3ef-1564e06d8ea9". The agent chose to call the trace_lifecycle tool (not audit_correlation directly) -- this is model-behavior dependent. If GA agent never calls audit_correlation for the same input, that is a model-behavior drift to be evaluated separately, not a wire-contract failure. The important contract is that the SSE event structure (thinking/tool_call/text/done sequence) remains the same.
