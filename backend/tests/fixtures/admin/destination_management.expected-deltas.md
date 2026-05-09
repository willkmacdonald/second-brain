# Expected deltas: admin/destination_management

Captured: 2026-05-09 17:46 UTC
Stage A trace_id: 95f0bf52-2a11-46bd-8371-05da81b36d5e
Stage B trigger: GET /api/errands
Deployed system: brain.willmacdonald.com (RC)

## Same (RC == GA contract)

- Stage A SSE: same event types and order: STEP_START, STEP_END, CLASSIFIED, COMPLETE
- Stage A SSE bucket field value: "Admin"
- Spans contain admin processing artifacts: at least one AppDependencies row with Name == "admin_agent_process"
- Admin agent attempted processing (admin_agent_process span present) but tool_invoked was False in all attempts -- the agent did not successfully call manage_destination during this capture

## Allowed-different

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- Whether admin agent successfully invokes manage_destination (model-behavior drift)
- Number of retry attempts before success/failure

## Notes

Two-stage capture: Stage A classified as Admin, Stage B triggered admin processing. The admin agent processed the "Add a new destination called Home Depot" item but did not successfully invoke manage_destination in any of the 5 processing attempts. This is a model-behavior observation, not a wire-contract failure. The fixture proves the admin_agent_process span is created and the agent attempts processing. GA replay should verify the admin processing path fires regardless of whether the tool is invoked.
