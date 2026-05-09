# Expected deltas: admin/recipe_extraction

Captured: 2026-05-09 17:45 UTC
Stage A trace_id: 814ac3e1-43c3-407d-848d-8f78aa79ebea
Stage B trigger: GET /api/errands
Deployed system: brain.willmacdonald.com (RC)

## Same (RC == GA contract)

- Stage A SSE: same event types and order: STEP_START, STEP_END, CLASSIFIED, COMPLETE
- Stage A SSE bucket field value: "Admin"
- Spans contain admin processing artifacts: at least one AppDependencies row with Name == "admin_agent_process"
- admin_agent_process span carries Properties["admin.tool_invoked"] == "True" (agent called recipe extraction tools)

## Allowed-different

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- Recipe extraction success/failure if the test URL is unreachable on either side
- Which extractor tier fires (Jina Reader, httpx, Playwright) -- three-tier fetch per Phase 13

## Notes

Two-stage capture: Stage A classified as Admin with recipe URL, Stage B triggered admin processing. Three-tier fetch (Jina Reader -> httpx -> Playwright) per Phase 13. The recipe URL https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/ was used. If GA captures show only one tier exercised, that is a different model decision tree, not a wire-contract failure.
