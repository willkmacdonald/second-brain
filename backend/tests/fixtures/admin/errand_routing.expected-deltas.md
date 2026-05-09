# Expected deltas: admin/errand_routing

Captured: 2026-05-09 17:55 UTC
Stage A trace_id: 2a0819ba-2d2b-47f3-a47f-9c4f19146244
Stage B trigger: GET /api/errands
Deployed system: brain.willmacdonald.com (RC)

## Same (RC == GA contract)

- Stage A SSE: same event types and order: STEP_START, STEP_END, CLASSIFIED, COMPLETE
- Stage A SSE bucket field value: "Admin"
- Spans contain admin processing artifacts: at least one AppDependencies row with Name == "admin_agent_process" (emitted by processing/admin_handoff.py:177)
- admin_agent_process span carries Properties["admin.tool_invoked"] == "True" (agent called add_errand_items)

## Allowed-different

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- Specific destination chosen by routing (model-behavior drift)
- Number of retry attempts

## Notes

Two-stage capture: Stage A classified as Admin, Stage B triggered admin processing via GET /api/errands. The errand items were routed to the grocery store destination. Real errands were created in the live system.
