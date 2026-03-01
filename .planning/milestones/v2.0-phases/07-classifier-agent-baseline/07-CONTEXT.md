# Phase 7: Classifier Agent Baseline - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Register the Classifier as a persistent Foundry agent with local @tool execution, validated in isolation via pytest integration tests. The agent reasons about classification; tools are filing helpers that write to Cosmos DB. Streaming pipeline and HITL conversational flows are wired in later phases (8, 9).

</domain>

<decisions>
## Implementation Decisions

### Tool behavior
- Rename `classify_and_file` to `file_capture` — the agent does classification reasoning, the tool is a Cosmos DB write helper
- Agent calls `file_capture(text, bucket, confidence, status)` with the classification result it determined
- `file_capture` returns a structured dict: `{"bucket": "Ideas", "confidence": 0.85, "item_id": "..."}` on success
- On failure (Cosmos write error, transcription failure), tools return an error dict `{"error": "...", "detail": "..."}` — no exceptions raised
- `transcribe_audio` returns just the transcript text string — no metadata
- Voice captures use two separate tool calls: `transcribe_audio` first, agent reads transcript and reasons, then `file_capture`
- Confidence threshold: 0.6 — same as v1 (>= 0.6 auto-files, < 0.6 goes pending)

### Agent instructions
- Three outcomes: classified (high confidence), pending (low confidence), misunderstood (can't parse OR junk — unified, no separate junk status)
- Detailed bucket definitions with boundaries, edge cases, and overlap rules for each of the four buckets (Admin, Ideas, People, Projects)
- Multi-bucket edge cases: agent picks strongest match — no priority hierarchy
- Port refined v1 decision logic for misunderstood detection (from 04.3-10) — junk and can't-parse are the same outcome
- Misunderstood items are filed via `file_capture` with `status=misunderstood` — conversational follow-up wired in Phase 9
- Light persona framing ("You are Will's second brain classifier") followed by functional classification rules
- Foundry portal is the source of truth for instructions — no local reference copy in repo
- Instructions editable in AI Foundry portal without redeployment

### Middleware & logging
- Standard detail: agent run start/end, tool calls with timing, tool retry counts
- Token usage tracking deferred to Phase 9 (Observability)
- Logs go to both Python logging (console/stdout) AND Application Insights from the start
- Tool failures logged at WARNING level — ERROR reserved for app-level issues
- Use Foundry's built-in thread/run IDs for correlation — no custom run_id
- Log classification result as structured fields (bucket, confidence, status) — queryable in AppInsights

### Registration & lifecycle
- Agent registered at app startup — self-healing (creates if missing)
- Check stored `AZURE_AI_CLASSIFIER_AGENT_ID` first; if valid in Foundry, use it. Only create if missing — idempotent
- If agent registration fails at startup, app fails to start (hard dependency)
- Validation via pytest integration test: creates thread, sends message, asserts Cosmos result

### Claude's Discretion
- Tool parameter design (separate params vs grouped object for file_capture)
- Whether to store original voice transcript alongside classified text in Cosmos
- Exact middleware implementation (decorator vs class vs hook pattern)
- Compression/format of structured AppInsights custom dimensions
- Agent instruction wording and prompt engineering for classification accuracy

</decisions>

<specifics>
## Specific Ideas

- "In v1 misunderstood asked for a clarification - up to 2 times" — this behavior is Phase 9, but the baseline should detect and file misunderstood correctly
- "Junk and misunderstood are very similar, should have similar treatment" — unified into one status
- The agent IS the classifier brain — tools are just hands that write to the database (Foundry-native pattern)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-classifier-agent-baseline*
*Context gathered: 2026-02-26*
