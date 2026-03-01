# Phase 9: HITL Parity and Observability - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

All three HITL classification flows (low-confidence pending, misunderstood conversational follow-up, recategorize from inbox) working identically to v1 on the Foundry backend. Application Insights connected with per-classification traces showing token usage and latency. No new HITL flows or specialist agent routing (Phase 10).

</domain>

<decisions>
## Implementation Decisions

### Misunderstood flow threading
- Reuse the same Foundry thread for follow-up conversation (not a new thread)
- Agent sees its own classification attempt and the user's responses in thread history
- Auto re-classify after each user reply — agent attempts classification on every message and files as soon as confident
- No limit on follow-up exchanges — conversation continues until classified or user navigates away (same as v1)

### Low-confidence filing behavior
- Pending items wait forever until user acts — no auto-timeout (same as v1)
- Bucket buttons in inbox highlight the Classifier's top guess, other buckets shown as secondary (same as v1)
- Tapping a bucket button is instant confirm — no SSE streaming steps, just immediate success toast + item update
- After confirmation, item stays in inbox with classified status (not removed)

### Recategorize mechanics
- Label change only — update bucket field in Cosmos DB. No specialist agent re-processing (that's Phase 10)
- Available for ALL inbox item statuses: classified, pending, misunderstood (same as v1)

### Observability
- Token usage + latency per classification (no cost calculation)
- Per-capture trace granularity — one trace covers full lifecycle from capture received to filing
- Manual App Insights queries only — no automated alerting
- Instrument both: middleware traces (AgentMiddleware, FunctionMiddleware) AND endpoint-level traces (capture, respond, recategorize)

### Claude's Discretion
- Recategorize endpoint contract design (keep v1 PATCH shape or redesign for v2)
- Data model for recategorize audit trail (preserve original classification vs overwrite)

</decisions>

<specifics>
## Specific Ideas

- "Match v1 behavior" was the guiding principle for all three HITL flows — parity, not reinvention
- Misunderstood flow uses same thread specifically so conversation continuity is preserved (agent can reference what it already said)

</specifics>

<deferred>
## Deferred Ideas

- Natural language agent for querying App Insights (ask questions in English, agent executes KQL queries) — future phase beyond v2.0

</deferred>

---

*Phase: 09-hitl-parity-and-observability*
*Context gathered: 2026-02-27*
