# Expected deltas: classifier/low_confidence_followup

Captured: 2026-05-09 18:18 UTC
Trace ID: d720349e-7022-4ee8-bdd0-516d345c129f
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- Turn 1 SSE event types and ORDER must match: STEP_START, STEP_END, LOW_CONFIDENCE, COMPLETE
- LOW_CONFIDENCE event contains inboxItemId and bucket with low confidence
- Span attributes: capture.trace_id present on all spans

## Allowed-different (RC != GA, not a regression)

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- The specific bucket chosen at low confidence may differ
- Confidence value may vary

## D-07b notes (classifier-specific)

Per design D-07b, in RC the Python safety net could file the capture as Misunderstood when the model called no tool. In GA, tool_choice='required' is set on a single-tool classifier (only file_capture registered). The MISUNDERSTOOD outcome in GA is therefore reached via the model deliberately choosing a bucket of "Misunderstood" (or equivalent). LOW_CONFIDENCE is reached when the model calls file_capture with a low confidence score.

For the new SSE error sub-code forced_tool_failure: this is GA-only. Replay assertion should NOT expect this in the RC fixture. Phase 24 task group 23.3 wires it into adapter.py.

## Notes

Turn 1 sent "remind me about the thing" and got LOW_CONFIDENCE (Ideas, 0.4). Turn 2 follow-up was not captured because the RC follow-up endpoint requires a foundryThreadId on the inbox item, which is only set for MISUNDERSTOOD items. LOW_CONFIDENCE items use bucket-selection buttons (HITL) instead. In GA (D-07b), tool_choice=required ensures file_capture is always called, so MISUNDERSTOOD items will have a foundryThreadId and the follow-up path will be exercisable.
