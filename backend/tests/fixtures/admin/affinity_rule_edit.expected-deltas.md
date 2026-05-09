# Expected deltas: admin/affinity_rule_edit

Captured: 2026-05-09 17:46 UTC
Stage A trace_id: b446e961-fe93-4001-8bc1-0a0639fec112
Stage B trigger: GET /api/errands
Deployed system: brain.willmacdonald.com (RC)

## Same (RC == GA contract)

- Stage A SSE: same event types and order: STEP_START, STEP_END, CLASSIFIED, COMPLETE
- Stage A SSE bucket field value: "Admin"
- Spans contain admin processing artifacts: at least one AppDependencies row with Name == "admin_agent_process"
- Admin agent attempted processing but tool_invoked attribute was absent on the initial attempt -- the agent's routing decision was not captured on this span

## Allowed-different

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- Whether admin agent calls manage_affinity_rule vs other tools

## Notes

Two-stage capture: Stage A classified as Admin, Stage B triggered admin processing. Voice-managed affinity rules per project_affinity_system.md. The admin agent processed the "When I mention tools route to Home Depot" item. The fixture proves the admin processing path fires. RC writes Cosmos directly. GA must show same processing path fires.
