# Expected deltas: classifier/text_idea

Captured: 2026-05-09 18:17 UTC
Trace ID: 9beb580d-ba2c-4bbf-985d-9f384cdd2d0a
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- SSE event types and ORDER must match: STEP_START, STEP_END, CLASSIFIED, COMPLETE
- SSE CLASSIFIED bucket: "Ideas" (confidence 0.9)
- Span attributes: capture.trace_id present on all spans

## Allowed-different (RC != GA, not a regression)

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- Confidence value may vary slightly

## D-07b notes (classifier-specific)

In GA, tool_choice='required' ensures file_capture is always called. The CLASSIFIED path is the same.

## Notes

Text capture "What if errands could auto-suggest based on calendar context?" classified as Ideas.
