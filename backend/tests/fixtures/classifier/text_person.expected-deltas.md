# Expected deltas: classifier/text_person

Captured: 2026-05-09 18:17 UTC
Trace ID: dc32cc85-5e89-48a3-be04-04e11b445edf
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- SSE event types and ORDER must match: STEP_START, STEP_END, CLASSIFIED, COMPLETE
- SSE CLASSIFIED bucket: "People" (confidence 0.9)
- Span attributes: capture.trace_id present on all spans

## Allowed-different (RC != GA, not a regression)

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- Confidence value may vary slightly
- Free-text content differences

## D-07b notes (classifier-specific)

In GA, tool_choice='required' ensures file_capture is always called. The SSE event shape from the mobile client's perspective stays the same. The CLASSIFIED path is the same in both RC and GA.

## Notes

Text capture "Coffee with Sarah next Tuesday at the Blue Bottle" classified as People. Straightforward classification.
