# Expected deltas: classifier/text_admin_task

Captured: 2026-05-09 18:19 UTC
Trace ID: 1649253d-f7d8-4103-92d3-aff940e4426d
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- SSE event types and ORDER must match: STEP_START, STEP_END, CLASSIFIED, COMPLETE
- SSE CLASSIFIED bucket: "Admin" (confidence 0.95)
- Span attributes: capture.trace_id present on all spans

## Allowed-different (RC != GA, not a regression)

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- Confidence value may vary slightly

## D-07b notes (classifier-specific)

In GA, tool_choice='required' ensures file_capture is always called. Admin-classified items then go through admin processing.

## Notes

Text capture "Pay the electric bill before it is due next Friday" classified as Admin task. Re-captured because initial "Submit expense report" was classified as Projects by the model.
