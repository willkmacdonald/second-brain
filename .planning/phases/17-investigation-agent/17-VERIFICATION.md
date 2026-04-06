---
phase: 17-investigation-agent
verified: 2026-04-06T04:00:00Z
status: passed
score: 10/10 must-haves verified
re_verification: false
---

# Phase 17: Investigation Agent Verification Report

**Phase Goal:** Build a third AI Foundry assistant that answers natural-language questions about captures and system health, streaming responses as SSE events. Four tools (trace lifecycle, recent errors, system health, usage patterns) query App Insights via KQL, and the agent's text output is the primary deliverable.
**Verified:** 2026-04-06T04:00:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

Truths are sourced from both PLAN must_haves and ROADMAP success criteria.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SYSTEM_HEALTH KQL template returns P95/P99 latency and trend comparison to the previous period | VERIFIED | `kql_templates.py` lines 123-159: SYSTEM_HEALTH_ENHANCED uses `percentile(duration, 95)`, `percentile(duration, 99)`, and two-period comparison with `ago({time_range})` vs `ago(2 * {time_range})` |
| 2 | USAGE_PATTERNS KQL template exists and returns capture counts by period, bucket distribution, and destination usage | VERIFIED | `kql_templates.py` lines 211-246: USAGE_PATTERNS_BY_PERIOD (parameterized bin_size), USAGE_PATTERNS_BY_BUCKET (classifier traces), USAGE_PATTERNS_BY_DESTINATION (admin_agent traces) |
| 3 | RECENT_FAILURES KQL template accepts component filter and respects parameterized time range | VERIFIED | `kql_templates.py` lines 171-189: RECENT_FAILURES_FILTERED with `{component_filter}`, `{severity_filter}`, `{limit}` placeholders |
| 4 | CAPTURE_TRACE supports "last capture" lookup when no trace_id is provided | VERIFIED | `queries.py` lines 206-228: `query_latest_capture_trace_id()` uses LATEST_CAPTURE_TRACE_ID template; `investigation.py` lines 104-112: trace_lifecycle tool calls it when trace_id is None |
| 5 | All new KQL templates use workspace schema (traces, requests) not portal schema (AppTraces, AppRequests) | VERIFIED | Grep for AppTraces/AppRequests in kql_templates.py returns only docstring field mapping comments (lines 4-14), no actual KQL usage |
| 6 | POST /api/investigate accepts {question, thread_id?} and returns SSE stream | VERIFIED | `api/investigate.py` lines 29-87: InvestigateBody(question, thread_id), returns StreamingResponse with text/event-stream |
| 7 | SSE stream yields thinking, tool_call, tool_error, text, and done event types | VERIFIED | `investigation_adapter.py`: thinking (line 112), tool_call (lines 157-163), tool_error (lines 172-178), text (lines 142-147), done (line 188), error (lines 196-199) |
| 8 | Agent text output is streamed to client as text events (NOT suppressed as reasoning) | VERIFIED | `investigation_adapter.py` lines 141-147: `content.type == "text"` yields `{"type": "text", "content": content.text}` -- explicit comment on line 140: "Text output IS the answer" |
| 9 | Thread ID from Assistants API is captured and returned in the done event for multi-turn conversations | VERIFIED | `investigation_adapter.py` lines 136-137: captures `conversation_id` from first update; line 186-188: yields `{"type": "done", "thread_id": final_thread}` |
| 10 | tool_choice is auto (not required) so the agent can respond without calling tools | VERIFIED | `investigation_adapter.py` lines 119-121: explicit comment "tool_choice is intentionally NOT set (defaults to auto)"; no tool_choice in api/investigate.py |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/second_brain/observability/kql_templates.py` | 6 new/enhanced templates | VERIFIED | SYSTEM_HEALTH_ENHANCED, RECENT_FAILURES_FILTERED, LATEST_CAPTURE_TRACE_ID, USAGE_PATTERNS_BY_PERIOD, USAGE_PATTERNS_BY_BUCKET, USAGE_PATTERNS_BY_DESTINATION all present. Originals preserved. |
| `backend/src/second_brain/observability/models.py` | EnhancedHealthSummary and UsagePatternRecord | VERIFIED | EnhancedHealthSummary (lines 60-69) with p95/p99/trend fields. UsagePatternRecord (lines 75-78) with label + count. |
| `backend/src/second_brain/observability/queries.py` | 4 new async query functions | VERIFIED | query_latest_capture_trace_id, query_enhanced_system_health, query_recent_failures_filtered, query_usage_patterns all present with server_timeout=30. |
| `backend/src/second_brain/tools/investigation.py` | InvestigationTools with 4 @tool functions | VERIFIED | Class with trace_lifecycle, recent_errors, system_health, usage_patterns. TIME_RANGE_MAP with 5 entries. All return JSON, all catch exceptions. |
| `backend/src/second_brain/agents/investigation.py` | ensure_investigation_agent() | VERIFIED | Non-fatal registration function (lines 21-69). Validates stored agent ID or creates new one. |
| `backend/src/second_brain/streaming/investigation_adapter.py` | stream_investigation() + SoftRateLimiter | VERIFIED | Async generator (lines 69-218) with OTel span, 60s timeout, all SSE event types. SoftRateLimiter (lines 44-66) with sliding window. |
| `backend/src/second_brain/api/investigate.py` | POST /api/investigate endpoint | VERIFIED | Router with InvestigateBody model, 503 guards for logs_client and investigation_client, StreamingResponse with SSE headers. |
| `backend/src/second_brain/config.py` | azure_ai_investigation_agent_id setting | VERIFIED | Line 15: `azure_ai_investigation_agent_id: str = ""` alongside existing agent IDs. |
| `backend/src/second_brain/main.py` | Investigation agent wired into lifespan | VERIFIED | Lines 37, 45, 56-59: imports. Lines 320-376: non-fatal lifespan block. Line 460: router included. Lines 395-396: warmup loop registration. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tools/investigation.py` | `observability/queries.py` | Import and call query functions | WIRED | Lines 21-27: imports 5 query functions; lines 106, 114, 183, 241, 306: calls them |
| `observability/queries.py` | `observability/kql_templates.py` | Template import and str.format() | WIRED | Lines 9-19: imports all templates; lines 247, 312, 365/367/374: `.format()` calls |
| `observability/queries.py` | `observability/models.py` | Pydantic model construction | WIRED | Lines 22-28: imports models; lines 271-281, 388-403: constructs UsagePatternRecord, EnhancedHealthSummary |
| `streaming/investigation_adapter.py` | `streaming/sse.py` | Import encode_sse() | WIRED | Line 30: import; used 12 times for all SSE event types |
| `api/investigate.py` | `streaming/investigation_adapter.py` | Import stream_investigation() | WIRED | Line 15: import; line 75: called with all required args |
| `main.py` | `agents/investigation.py` | Import and call ensure_investigation_agent() | WIRED | Line 37: import; line 325: awaited in lifespan |
| `main.py` | `api/investigate.py` | Import and include investigate_router | WIRED | Line 45: import; line 460: app.include_router() |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INV-01 | 17-02 | User can ask natural language questions about captures and get human-readable answers | SATISFIED | POST /api/investigate accepts question string, agent formats human-readable answers as text SSE events |
| INV-02 | 17-01, 17-02 | User can trace a specific capture's full lifecycle by providing a trace ID | SATISFIED | trace_lifecycle tool calls query_capture_trace with trace_id; CAPTURE_TRACE KQL joins union of traces/dependencies/requests/exceptions |
| INV-03 | 17-01, 17-02 | User can view recent failures and errors with trace IDs and component attribution | SATISFIED | recent_errors tool calls query_recent_failures_filtered; RECENT_FAILURES_FILTERED includes Component and CaptureTraceId columns |
| INV-04 | 17-01, 17-02 | User can query system health (error rates, capture volume, latency trends) | SATISFIED | system_health tool calls query_enhanced_system_health; SYSTEM_HEALTH_ENHANCED returns capture_count, error_count, p95/p99, trend comparison |
| INV-05 | 17-01, 17-02 | User can query usage insights (capture counts by period, destination usage, bucket distribution) | SATISFIED | usage_patterns tool routes to USAGE_PATTERNS_BY_PERIOD, BY_BUCKET, BY_DESTINATION templates |

No orphaned requirements found -- REQUIREMENTS.md maps INV-01 through INV-05 to Phase 17, and all 5 are covered by plans 17-01 and 17-02.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | - | - | - | No anti-patterns detected |

All files scanned for TODO/FIXME/PLACEHOLDER/stub patterns -- none found. No empty implementations, no console.log-only handlers, no return null stubs.

### Human Verification Required

### 1. End-to-End SSE Streaming

**Test:** POST to /api/investigate with `{"question": "what happened to my last capture?"}` and observe the SSE event stream.
**Expected:** Events arrive in order: thinking -> (optional tool_call for trace_lifecycle) -> text (human-readable answer) -> done (with thread_id).
**Why human:** Requires deployed backend with configured Investigation Agent in AI Foundry portal and live App Insights data.

### 2. Multi-Turn Conversation Continuity

**Test:** Send a second question with the thread_id from the first response's done event.
**Expected:** Agent maintains conversation context and provides a relevant follow-up answer.
**Why human:** Requires Foundry Assistants API thread state, which can only be verified against live infrastructure.

### 3. Agent Text Quality

**Test:** Ask "how is the system doing?" and verify the response is a coherent, human-readable summary (not raw JSON).
**Expected:** Plain-English narrative describing capture counts, error rates, latency, and trends.
**Why human:** Text formatting depends on agent instructions configured in AI Foundry portal.

### 4. 503 Behavior When Services Unavailable

**Test:** Deploy with missing AZURE_AI_INVESTIGATION_AGENT_ID or without Log Analytics workspace configured.
**Expected:** POST /api/investigate returns HTTP 503 with clear message. Core capture flow (/api/capture) continues to work.
**Why human:** Requires observing actual Container App behavior with missing environment variables.

### Gaps Summary

No gaps found. All 10 observable truths are verified. All 9 artifacts exist, are substantive, and are wired. All 7 key links are connected. All 5 requirements (INV-01 through INV-05) are satisfied. No anti-patterns detected. All 4 task commits (a8d2ea2, 981c3a5, b29332c, dc2054c) verified in git log. All files pass ruff check.

The phase delivers a complete investigation agent stack: KQL templates querying App Insights via workspace schema, typed Pydantic models, async query functions with server_timeout=30, InvestigationTools with 4 @tool functions, SSE streaming adapter with text as primary output, POST /api/investigate endpoint with 503 guards, SoftRateLimiter, and non-fatal lifespan wiring with warmup registration.

---

_Verified: 2026-04-06T04:00:00Z_
_Verifier: Claude (gsd-verifier)_
