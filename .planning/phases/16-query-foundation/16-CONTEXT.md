# Phase 16: Query Foundation - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Make App Insights telemetry queryable programmatically via LogsQueryClient and create Cosmos containers for eval data (Feedback, EvalResults, GoldenDataset). This is pure infrastructure enabling Phases 17-22. No user-facing features in this phase.

</domain>

<decisions>
## Implementation Decisions

### KQL Template Design
- Templates for known patterns (trace lookup, recent failures, system health, admin audit) + LLM-generated KQL fallback for novel questions with schema grounding
- Agent executes generated KQL directly — no approval step before running (read-only workspace access)
- Default time range: 24 hours when not specified
- Existing .kql files from Phase 14 need workspace-compatible equivalents

### Cosmos Data Model
- GoldenDataset: individual documents per test case (not a single dataset document). Easy to add/remove/query.
- Feedback: full capture snapshot in each signal document (capture text, original bucket, correction). Self-contained for analysis, no joins needed.
- EvalResults: each eval run stores both aggregate scores AND individual case results in a single document. One doc per eval run.

### Query API Surface
- New `observability/` module under `backend/src/second_brain/` — clean separation from capture/classification code
- Async functions (matching FastAPI pattern). LogsQueryClient async variant.
- Partial query results: flag + return (warning flag, let consumer decide if partial is acceptable)
- Pydantic models for query results (TraceResult, HealthSummary, etc.)

### Auth & Access
- DefaultAzureCredential for LogsQueryClient (managed identity in production, az login locally)
- Log Analytics Reader RBAC role assignment for Container App managed identity — set up in this phase via az CLI
- Log Analytics workspace ID configured as environment variable (LOG_ANALYTICS_WORKSPACE_ID) — not a secret, safe as plain config

### Claude's Discretion
- KQL schema migration strategy (workspace-only vs maintaining both portal and workspace versions)
- Partition key strategy for new Cosmos containers (userId consistency vs domain-specific keys)
- Exact Pydantic model shapes for query results
- LogsQueryClient initialization and lifecycle management

</decisions>

<specifics>
## Specific Ideas

- Workspace-based App Insights uses `traces`/`requests` tables (not `AppTraces`/`AppRequests`) — learned the hard way during Phase 14 testing
- Workspace ID is not a secret — it's a resource identifier like subscription ID or resource group name
- Existing RBAC pattern from Phase 12.3 used Azure CLI management plane for Cosmos container creation — reuse same approach for Log Analytics Reader assignment

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-query-foundation*
*Context gathered: 2026-04-05*
