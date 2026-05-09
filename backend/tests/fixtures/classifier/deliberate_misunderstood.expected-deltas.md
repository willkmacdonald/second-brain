# Expected deltas: classifier/deliberate_misunderstood

Captured: 2026-05-09 18:18 UTC
Trace ID: a40f8178-20b8-4d8a-8976-2ca05da3d2f4
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- SSE event types and ORDER must match: STEP_START, STEP_END, MISUNDERSTOOD, COMPLETE
- MISUNDERSTOOD event contains questionText for follow-up
- Span attributes: capture.trace_id present on all spans

## Allowed-different (RC != GA, not a regression)

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- The specific questionText in the MISUNDERSTOOD event

## D-07b notes (classifier-specific)

Per design D-07b, in RC the Python safety net could file the capture as Misunderstood when the model called no tool. In GA, tool_choice='required' is set on a single-tool classifier (only file_capture registered). The MISUNDERSTOOD outcome in GA is therefore reached via the model deliberately choosing a bucket of "Misunderstood" (or equivalent). The replayed SSE should still emit the MISUNDERSTOOD event type -- the path to it is what differs.

For the new SSE error sub-code forced_tool_failure: this is GA-only. Replay assertion should NOT expect this in the RC fixture. Phase 24 task group 23.3 wires it into adapter.py.

## Notes

Deliberately incomprehensible input "asdf zxcv qwerty deliberately incomprehensible test input" triggered MISUNDERSTOOD via the model's own decision. The MISUNDERSTOOD event's inboxItemId was empty because the safety net path (model called no tool) does not create an inbox item in the RC. In GA, tool_choice=required means the model must call file_capture even for misunderstood captures.
