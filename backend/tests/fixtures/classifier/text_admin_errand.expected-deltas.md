# Expected deltas: classifier/text_admin_errand

Captured: 2026-05-09 18:17 UTC
Trace ID: 896fb189-2174-4173-a45f-c3d96e835ffa
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- SSE event types and ORDER must match: STEP_START, STEP_END, CLASSIFIED, COMPLETE
- SSE CLASSIFIED bucket: "Admin" (confidence 0.9)
- Span attributes: capture.trace_id present on all spans

## Allowed-different (RC != GA, not a regression)

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- Confidence value may vary slightly

## D-07b notes (classifier-specific)

In GA, tool_choice='required' ensures file_capture is always called. Admin-classified items then go through the admin processing pipeline via GET /api/errands.

## Notes

Text capture "Pick up the dry cleaning Friday" classified as Admin errand. This fixture only captures the classifier stage -- admin processing is covered by the admin fixtures.
