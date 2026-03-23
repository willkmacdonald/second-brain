# Phase 14: App Insights Operational Audit - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Review and streamline the full observability stack to ensure end-to-end transparency from mobile app through backend to Azure AI Foundry. App Insights is the single pane of glass — every component must feed into it. Audit log levels, add correlation tracing, create operational queries, configure alerts, and ensure no blind spots exist in the capture lifecycle.

</domain>

<decisions>
## Implementation Decisions

### Log Level Strategy
- Claude audits current codebase log statements and proposes a consistent level policy (what's error vs warning vs info)
- Fix any inconsistencies found during audit
- Goal: errors/failures are unmissable, noise is demoted

### Per-Capture Trace ID
- Every capture gets a unique trace ID that propagates end-to-end
- Mobile app generates the trace ID on capture, sends it with the API call
- Backend carries it through classification, Admin Agent processing, and shopping list writes
- Every log entry for that capture shares the ID — filter by one ID to see full journey
- Trace ID is visible in the mobile app so Will can copy it for debugging in App Insights

### End-to-End Observability Scope
- **Mobile app (Expo/React Native):** Client-side telemetry SDK sends errors, network failures, and performance metrics to App Insights
- **Backend API (FastAPI):** All request handling, classification, routing — already partially logged, needs audit
- **Azure AI Foundry / OpenAI calls:** Log full prompt and response content, plus metadata (model, latency, token count, success/failure)
- **Background processing (Admin Agent):** Probably a blind spot currently — Claude audits and ensures complete coverage of async tasks

### Operational Queries
- Saved KQL queries stored as files in the repo (version controlled, Claude can reference them)
- Four key queries needed:
  1. "What happened to capture X?" — trace a specific capture by ID through its full lifecycle
  2. "What failed recently?" — recent errors, failed processing, stuck/dropped items
  3. "How is the system doing overall?" — capture volume, success rate, processing time, error rate trends
  4. "What did the Admin Agent do?" — classification decisions, shopping list items created, rejections
- Lookup by capture ID is the primary investigation method
- Support both timeline view (chronological events for a capture) and error-first view (start from failures, drill down)

### Alert Configuration
- Starting from scratch — no alerts exist today
- Alert conditions:
  - API is down / unresponsive (health check failures, 5xx errors)
  - Captures failing to process (classification or Admin Agent failures)
  - Unusual error spike (rate jumps above baseline)
- Delivery: push notifications (Azure mobile app)
- Sensitivity: sustained problems only — not every transient blip
- Resolution: auto-resolve when condition clears

### Cost & Retention
- Hobby scale — cost is not a concern currently
- 30-day log retention
- Full fidelity logging — no sampling or filtering (volume too low to justify losing data)

### Claude's Discretion
- Exact log level assignments after audit
- Mobile telemetry SDK choice for Expo/React Native
- KQL query implementation details
- Alert threshold values (what constitutes "sustained")
- Structured log format (JSON fields, naming conventions)
- How to instrument Azure OpenAI calls for full prompt/response logging

</decisions>

<specifics>
## Specific Ideas

- "I'm not an ops guy — I looked in App Insights once and it was cryptic. I want an interface that lets me easily traverse logged information for root cause analysis without having to ask through an LLM"
- App Insights should be the single pane of glass for the entire system — no component should be a blind spot
- Background processing (Admin Agent async tasks) is suspected to be a current blind spot
- Full LLM prompt/response logging is desired for debuggability — privacy is not a concern for this personal hobby project

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-app-insights-operational-audit*
*Context gathered: 2026-03-22*
