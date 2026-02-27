# Phase 8: FoundrySSEAdapter and Streaming - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the Foundry-backed Classifier agent into a streaming SSE endpoint that produces AG-UI-compatible events for both text and voice captures. The mobile app's event parser is updated to handle the simplified event surface. No new capture types, no HITL flows (Phase 9), no new agents.

</domain>

<decisions>
## Implementation Decisions

### SSE event contract
- Simplify event names but keep compatible payload structure
- Promote CLASSIFIED, MISUNDERSTOOD, UNRESOLVED to top-level event types (no longer wrapped in CUSTOM)
- Rename RUN_FINISHED to COMPLETE
- Rename STEP_STARTED/STEP_FINISHED to STEP_START/STEP_END
- Remove TEXT_MESSAGE_CONTENT event — result payload in CLASSIFIED carries all info the mobile needs (bucket, confidence, item_id)
- Step name labels are descriptive: "Classifying" for text captures, "Processing" for voice captures
- Voice captures use a single step (no synthetic transcription step) — one "Processing" bracket for the whole run

### Endpoint design
- New clean endpoint: POST /api/capture (replaces old AG-UI framework endpoint)
- Single endpoint for both text and voice — request body indicates type (text field or audio file)
- Voice captures use direct multipart upload — endpoint handles blob storage server-side (mobile no longer manages blob URLs)
- New capture.py router module — separate from inbox.py CRUD routes
- Mobile app URL updated to point to /api/capture

### Agent reasoning text
- Suppress chain-of-thought from SSE stream — mobile never sees reasoning text
- Log each reasoning chunk as it arrives (not buffered) to Application Insights
- Structured fields for AppInsights queryability: reasoning_text, agent_run_id, chunk_index
- Log level: INFO — reasoning visible in normal operation for future analysis and instruction tuning

### Error handling
- ERROR event emitted on any failure (agent timeout, network error, tool failure), followed by COMPLETE
- No automatic retry on Cosmos write failures — surface error immediately, user retries manually
- Voice file validation happens inside the agent (transcribe_audio tool handles format/size errors), not upfront 400 rejection
- 60-second timeout on entire agent run — ERROR event if exceeded

### Mobile event parser update (included in Phase 8)
- Mobile SSE parser updated to handle new top-level event types (CLASSIFIED, MISUNDERSTOOD, UNRESOLVED, COMPLETE, STEP_START, STEP_END, ERROR)
- Brief backward compatibility: handle both old and new event names during development

### Claude's Discretion
- Exact FoundrySSEAdapter class/function structure (async generator vs class)
- SSE encoding implementation details
- How multipart audio upload is handled server-side (temp file vs memory vs stream to blob)
- Exact structured log field names and AppInsights custom dimension format
- How to detect which tool call is in progress from the Foundry stream (for step name labeling)

</decisions>

<specifics>
## Specific Ideas

- The old AGUIWorkflowAdapter was 540 lines because it wrapped HandoffBuilder + Workflow + multi-agent orchestration. The new adapter should be dramatically simpler (~150 lines) since Foundry handles the tool loop.
- Voice capture simplification: v1 had a separate Perception agent step, v2 has transcribe_audio as a @tool on the Classifier, so the stream is simpler with one step bracket.
- The mobile's react-native-sse EventSource parses `data: {json}\n\n` format — a simple encode_sse() function on the backend is sufficient, no AG-UI package needed.

</specifics>

<deferred>
## Deferred Ideas

- "Tuning agent" — an agent that reviews classification reasoning patterns over time and recommends instruction tuning changes. Interesting meta-agent concept, capture as future phase idea.

</deferred>

---

*Phase: 08-foundrysseadapter-and-streaming*
*Context gathered: 2026-02-27*
