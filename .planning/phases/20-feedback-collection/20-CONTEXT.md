# Phase 20: Feedback Collection - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Quality signals flow into the system automatically from user behavior and explicitly from user feedback. Three implicit signal types (recategorize, HITL bucket pick, errand re-route) are captured inline in existing handlers. Explicit thumbs up/down feedback is added to inbox items. Signals accumulate in the Feedback Cosmos container and can be promoted to the GoldenDataset container via the investigation agent. The investigation agent gains tools to query feedback data and promote entries.

</domain>

<decisions>
## Implementation Decisions

### Signal capture points
- **D-01:** Implicit signals are written inline in the existing handlers (recategorize endpoint, HITL resolution flow, errand re-route handler) — not via Change Feed or background tasks
- **D-02:** Signal write is fire-and-forget with try/except + logger.warning — a failed Feedback write NEVER blocks the primary user action (recategorize, HITL pick, re-route)
- **D-03:** Each signal creates a `FeedbackDocument` in the Feedback Cosmos container using the model already defined in `documents.py` (signalType, captureText, originalBucket, correctedBucket, captureTraceId)

### Golden dataset promotion
- **D-04:** Promotion is done through the investigation agent — no dedicated mobile screen. User asks the agent to show signals, then promotes individual ones via natural language command
- **D-05:** Investigation agent gets new @tool functions: one to query/list feedback signals, one to promote a signal to golden dataset
- **D-06:** Promotion requires agent confirmation before writing — agent shows the capture text and label, user confirms, then GoldenDatasetDocument is written
- **D-07:** Review and promote flow is conversational: "show me recent misclassifications" → agent lists them → "promote signal abc123" → agent confirms → user says yes → written to GoldenDataset container

### Claude's Discretion
- Thumbs up/down UI placement and interaction pattern on inbox items (inline buttons, detail screen, etc.)
- Investigation agent tool parameter design (time ranges, filters, pagination for signal queries)
- FEED-04 implementation: how the investigation agent answers "what are the most common misclassifications?" — Cosmos query against Feedback container with aggregation, response formatting
- Whether to add MCP tool equivalents for signal querying alongside the investigation agent @tools
- Exact signal deduplication strategy (if same capture is recategorized twice, store both or update)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Feedback data model
- `backend/src/second_brain/models/documents.py` — FeedbackDocument and GoldenDatasetDocument Pydantic models (already defined in Phase 16)

### Signal emit points
- `backend/src/second_brain/api/inbox.py` — recategorize_inbox_item handler (line ~197) — primary emit point for recategorize signals
- `backend/src/second_brain/streaming/investigation_adapter.py` — investigation agent adapter (may need HITL resolution signal hook reference)

### Investigation agent tools
- `backend/src/second_brain/tools/investigation.py` — InvestigationTools class with existing @tool pattern (trace_lifecycle, recent_errors, system_health, usage_patterns) — new feedback tools follow this pattern

### Cosmos containers
- `backend/src/second_brain/db/cosmos.py` — Feedback, EvalResults, GoldenDataset containers already provisioned

### Requirements
- `.planning/REQUIREMENTS.md` §Feedback & Signals — FEED-01 through FEED-04

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FeedbackDocument` model in `documents.py` — fully defined with signalType enum (recategorize, hitl_bucket, errand_reroute, thumbs_up, thumbs_down), self-contained snapshot fields
- `GoldenDatasetDocument` model in `documents.py` — individual test case documents
- `InvestigationTools` class pattern — add new @tool functions following existing trace_lifecycle/recent_errors pattern
- Cosmos "Feedback" and "GoldenDataset" containers already provisioned in `cosmos.py`
- Recategorize handler with full OTel spans — emit point is inside the existing try/except block
- Mobile inbox screen with detail modal and recategorize bucket picker

### Established Patterns
- @tool functions on InvestigationTools with `approval_mode="never_require"` and async implementation
- Fire-and-forget Cosmos writes with try/except logging (used in spine event emission)
- `CosmosManager` container access via `request.app.state.cosmos_manager`
- FeedbackDocument uses standalone BaseModel (not BaseDocument) per Phase 16 decision for non-bucket containers

### Integration Points
- Recategorize handler in `inbox.py` — add FeedbackDocument write after successful recategorize
- HITL bucket resolution flow — add signal emit when user picks bucket for low-confidence capture
- Errand re-route handler — add signal emit when errand destination changes
- InvestigationTools class — add query_feedback_signals and promote_to_golden_dataset @tools
- Mobile inbox item component — add thumbs up/down UI elements

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 20-feedback-collection*
*Context gathered: 2026-04-21*
