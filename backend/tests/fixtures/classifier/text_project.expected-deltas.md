# Expected deltas: classifier/text_project

Captured: 2026-05-09 18:17 UTC
Trace ID: 76ea0345-a367-4b2a-88e3-c3d64157f519
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- SSE event types and ORDER must match: STEP_START, STEP_END, CLASSIFIED, COMPLETE
- SSE CLASSIFIED bucket: "Projects" (confidence 0.9)
- Span attributes: capture.trace_id present on all spans

## Allowed-different (RC != GA, not a regression)

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- Confidence value may vary slightly

## D-07b notes (classifier-specific)

In GA, tool_choice='required' ensures file_capture is always called. The CLASSIFIED path is the same.

## Notes

Text capture "Backend refactor to migrate auth middleware to async" classified as Projects.
