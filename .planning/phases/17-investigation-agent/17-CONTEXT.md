# Phase 17: Investigation Agent - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Third Azure OpenAI Foundry assistant that answers natural language questions about captures and system health. Users ask questions, the agent queries App Insights telemetry via parameterized KQL tools, and returns human-readable answers streamed via SSE. Creating the mobile chat UI is Phase 18; MCP tooling is Phase 19.

</domain>

<decisions>
## Implementation Decisions

### Answer Style & Depth
- Clinical tone — precise, data-focused, no casual language
- Default to narrative summary; offer detailed data/timeline on follow-up request
- Tables for error reports (columns: Time, Component, Error, Trace ID)
- System health includes snapshot + trend comparison to previous period
- Full trace IDs, linkable (tappable on mobile in Phase 18)
- Usage pattern data as text with numbers (e.g., "Mon: 42, Tue: 38") — visualizable downstream
- Explicit confidence indicator when answer required interpretation (e.g., "Found 3 captures in the last hour. Showing the most recent one.")
- Suggest 1-2 relevant follow-up questions at end of each response

### Query Boundaries
- Default time range: last 24 hours when user doesn't specify
- Out-of-scope queries: explain scope clearly ("I can help with capture history, errors, system health, and usage patterns.")
- No results: state clearly + suggest widening time range or rephrasing
- Result cap: 10 items maximum, always mention total count ("Found 500 errors. Showing 10 most recent:")

### Agent Architecture
- New Azure OpenAI Assistants API assistant (third, alongside Classifier and Admin Agent)
- Named "Investigation Agent" — no special branding
- System prompt / instructions managed in Foundry portal (not in code)
- Multi-turn conversation threads — full context preserved across follow-ups
- Backend intercepts tool_calls, executes KQL via LogsQueryClient, returns results to assistant for formatting

### KQL Tool Design
- One tool per query type (not a general-purpose query tool):
  1. **trace_lifecycle** — Given trace ID or "last capture", full pipeline: classification → filing → admin processing with timing
  2. **recent_errors** — Errors/exceptions with component attribution, trace IDs, timestamps
  3. **system_health** — Error rates, capture volume, P95/P99 latency, success rates with trend comparison
  4. **usage_patterns** — Capture counts by period, bucket distribution, destination usage
- Strongly typed parameters (enums for time ranges, component names, severity levels — no freeform strings)

### Streaming & API
- SSE streaming endpoint: `POST /api/investigate`
- Request body: `{question, thread_id?}`
- SSE event types:
  - `thinking` — agent is processing / calling tools
  - `tool_call` — which KQL query is running (e.g., "Querying recent errors...")
  - `tool_error` — tool failure visible to user
  - `text` — response tokens streaming
  - `done` — response complete
- Client-managed thread_id (client stores, sends with request; omit for new thread)
- Same auth pattern as other API endpoints (no special auth)

### Error Handling & Resilience
- If some KQL tools succeed and one fails: report partial results, note what's missing
- Failed tool calls visible in SSE stream as `tool_error` events
- SSE stream break: send error event before disconnect; client shows "Connection lost. Tap to retry."
- App Insights unreachable: immediate HTTP 503 ("App Insights is unreachable. Investigation is unavailable.")

### Rate Limiting & Cost
- Soft rate limit: 10 queries per minute, warn but don't block
- Log estimated token usage and KQL query count to App Insights internally (not surfaced to user)

### Thread Lifecycle
- Threads persist indefinitely (no expiry, no max length)
- Assistants API manages context window limits naturally
- Client stores thread_id locally (no backend persistence in Cosmos)
- User can explicitly start a new thread by omitting thread_id

### Claude's Discretion
- Exact KQL query templates and parameterization
- SSE implementation details (chunking, keepalive intervals)
- Assistant system prompt wording
- Error message exact phrasing
- Soft rate limit implementation approach

</decisions>

<specifics>
## Specific Ideas

- Trace IDs should be full UUIDs and linkable — Phase 18 will make them tappable to drill into trace detail
- Tool visibility in SSE stream: user sees "Querying recent errors..." while the agent works, similar to ChatGPT's tool-use indicators
- Follow-up suggestions should be contextual (e.g., after showing errors, suggest "Want to see the trace for the most recent one?")

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-investigation-agent*
*Context gathered: 2026-04-05*
