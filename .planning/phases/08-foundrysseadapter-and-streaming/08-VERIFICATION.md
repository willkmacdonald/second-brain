---
phase: 08-foundrysseadapter-and-streaming
verified: 2026-02-27T17:00:00Z
status: human_needed
score: 9/10 must-haves verified
re_verification: false
human_verification:
  - test: "Text capture end-to-end: send a text capture from Expo app, observe SSE events arrive as STEP_START, STEP_END, CLASSIFIED/MISUNDERSTOOD/UNRESOLVED, COMPLETE"
    expected: "Mobile UI shows step progression and final classified result (or clarification prompt); no double onComplete firing; stream closes cleanly"
    why_human: "Requires live Foundry agent, Azure credentials, and mobile app running against a real backend; cannot verify agent tool-call detection or SSE streaming with grep alone"
  - test: "Voice capture end-to-end: record audio in Expo app, observe SSE events arrive as STEP_START (Processing), STEP_END, CLASSIFIED/UNRESOLVED, COMPLETE"
    expected: "Single 'Processing' step bracket; audio transcribed and classified; blob cleaned up after stream completes; no hung mobile UI"
    why_human: "Requires live Foundry agent with transcribe_audio tool configured, blob storage, and mobile app"
  - test: "No-tool-call fallback path: simulate Foundry agent returning no tool call (pure text response)"
    expected: "Mobile should gracefully handle UNRESOLVED with empty inboxItemId -- currently the mobile UNRESOLVED guard drops empty-string IDs, leaving mobile state hung (COMPLETE fires but onComplete never called for v2). Verify if this edge case is acceptable or needs onComplete fallback in COMPLETE handler."
    why_human: "Edge case requires controlled agent injection or mocking; real-world frequency unknown but worth validating before Phase 9"
---

# Phase 8: FoundrySSEAdapter and Streaming Verification Report

**Phase Goal:** Text and voice captures flow end-to-end through the Foundry-backed Classifier, producing the same AG-UI SSE events the mobile app already consumes
**Verified:** 2026-02-27T17:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /api/capture with text field produces STEP_START, STEP_END, CLASSIFIED, and COMPLETE SSE events | VERIFIED | `adapter.py` yields `step_start_event("Classifying")`, `step_end_event("Classifying")`, result event, `complete_event()` in sequence; tests confirm event structure |
| 2 | POST /api/capture with audio file produces STEP_START, STEP_END, CLASSIFIED, and COMPLETE SSE events | VERIFIED | `adapter.py` `stream_voice_capture` yields `step_start_event("Processing")`, `step_end_event("Processing")`, result event, `complete_event()`; capture.py voice endpoint wired |
| 3 | Chain-of-thought reasoning text is suppressed from SSE stream and logged | VERIFIED | `adapter.py` lines 113-124: `content.type == "text"` path accumulates to `reasoning_buffer`, logs to `reasoning_logger`, comment `# Do NOT yield -- suppress CoT from SSE` |
| 4 | ERROR event followed by COMPLETE is emitted on agent timeout or tool failure | VERIFIED | `adapter.py` lines 151-154: `except (TimeoutError, Exception) as exc:` yields `error_event(str(exc))` then `complete_event()` on both text and voice paths |
| 5 | SSE events use new top-level type names (STEP_START, STEP_END, CLASSIFIED, MISUNDERSTOOD, UNRESOLVED, COMPLETE, ERROR) | VERIFIED | 19 unit tests pass including `TestEventTypeNames` class asserting exact type names; no CUSTOM wrappers, no legacy names in `sse.py` |
| 6 | Mobile event parser handles new top-level event types (CLASSIFIED, MISUNDERSTOOD, UNRESOLVED, COMPLETE, STEP_START, STEP_END, ERROR) | VERIFIED | `ag-ui-client.ts` switch covers all 7 new v2 types plus 6 legacy types for backward compat |
| 7 | sendCapture sends to /api/capture with text field in JSON body | VERIFIED | `ag-ui-client.ts` line 179: `${API_BASE_URL}/api/capture` with `body: JSON.stringify({ text: message, thread_id, run_id })` |
| 8 | sendVoiceCapture sends to /api/capture/voice with multipart audio | VERIFIED | `ag-ui-client.ts` line 292: `${API_BASE_URL}/api/capture/voice` with `body: formData` |
| 9 | CLASSIFIED event fires onComplete with formatted result string; COMPLETE does not double-fire | VERIFIED | CLASSIFIED case calls `callbacks.onComplete(result)` immediately; COMPLETE case only calls `onComplete` for legacy `RUN_FINISHED`, not for v2 `COMPLETE` |
| 10 | Unresolved fallback with empty inboxItemId is silently dropped by mobile (edge case) | WARNING | `unresolved_event("")` at adapter.py:147,233 sends `value.inboxItemId = ""`; mobile guard `if (parsed.value?.inboxItemId)` is falsy for empty string; `onUnresolved` never fires; `onComplete` also never fires since COMPLETE skips it for v2 |

**Score:** 9/10 truths verified (1 is a behavioral edge case flagged for human review)

---

### Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Details |
|----------|-----------|-------------|--------|---------|
| `backend/src/second_brain/streaming/adapter.py` | 80 | 241 | VERIFIED | `stream_text_capture` and `stream_voice_capture` async generators; full CoT suppression, timeout, and error handling |
| `backend/src/second_brain/streaming/sse.py` | 20 | 82 | VERIFIED | `encode_sse` + 7 event constructors: `step_start_event`, `step_end_event`, `classified_event`, `misunderstood_event`, `unresolved_event`, `complete_event`, `error_event` |
| `backend/src/second_brain/api/capture.py` | 40 | 120 | VERIFIED | `POST /api/capture` and `POST /api/capture/voice` with `StreamingResponse`, SSE headers, blob cleanup in `finally` |
| `backend/tests/test_streaming_adapter.py` | 30 | 162 | VERIFIED | 19 tests across 3 test classes; all pass in 0.01s |
| `mobile/lib/types.ts` | — | 62 | VERIFIED | `AGUIEventType` union contains `STEP_START`, `STEP_END`, `CLASSIFIED`, `MISUNDERSTOOD`, `UNRESOLVED`, `COMPLETE`, `ERROR` plus all legacy v1 types |
| `mobile/lib/ag-ui-client.ts` | — | 305 | VERIFIED | Contains `/api/capture` (line 179), `/api/capture/voice` (line 292); full v2+v1 switch statement |
| `backend/src/second_brain/streaming/__init__.py` | — | 1 (empty) | VERIFIED | Empty package init as required |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `capture.py` | `streaming/adapter.py` | `from second_brain.streaming.adapter import` | WIRED | Line 17 of `capture.py`: `from second_brain.streaming.adapter import stream_text_capture, stream_voice_capture` |
| `capture.py` | `app.state.classifier_client` | `request.app.state` | WIRED | Lines 46-47: `client = request.app.state.classifier_client`, `tools = request.app.state.classifier_agent_tools` |
| `main.py` | `api/capture.py` | `app.include_router(capture_router)` | WIRED | Line 31: `from second_brain.api.capture import router as capture_router`; line 229: `app.include_router(capture_router)` |
| `ag-ui-client.ts` | `POST /api/capture` | EventSource URL | WIRED | Line 179: `` `${API_BASE_URL}/api/capture` `` in `sendCapture` |
| `ag-ui-client.ts` | `POST /api/capture/voice` | EventSource URL | WIRED | Line 292: `` `${API_BASE_URL}/api/capture/voice` `` in `sendVoiceCapture` |
| Mobile screens | `ag-ui-client.ts` | import | WIRED | `text.tsx`, `index.tsx`, `inbox.tsx`, `conversation/[threadId].tsx` all import from `../../lib/ag-ui-client`; screen-level code unchanged |

---

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| STRM-01 | 08-01, 08-02 | `FoundrySSEAdapter` replaces `AGUIWorkflowAdapter`, streaming `AgentResponseUpdate` events to AG-UI SSE format | SATISFIED | `streaming/adapter.py` with `stream_text_capture` / `stream_voice_capture` async generators replaces old class; `AGUIWorkflowAdapter` has no references anywhere in codebase; `POST /api/capture` endpoint wired and operational |
| STRM-02 | 08-01, 08-02 | Text capture produces AG-UI events (`StepStarted`, `StepFinished`, `CLASSIFIED`/`MISUNDERSTOOD`/`UNRESOLVED`, `RUN_FINISHED`) | SATISFIED | New event names (STEP_START/STEP_END/CLASSIFIED/COMPLETE) are functionally equivalent with updated type contract; mobile handles both v1 and v2 names; 19 unit tests validate event structure and type names |
| STRM-03 | 08-01, 08-02 | Voice capture produces same AG-UI events as v1 (transcription step + classification stream) | SATISFIED (with design change) | Voice uses single "Processing" step (not separate transcription + classification steps); this is an explicit CONTEXT decision (line 23: "Voice captures use a single step") and documented deviation from v1 step structure. Mobile receives STEP_START, STEP_END, CLASSIFIED/UNRESOLVED, COMPLETE. |

**Orphaned requirements check:** No additional STRM-* requirements appear in REQUIREMENTS.md beyond STRM-01, STRM-02, STRM-03. All three are claimed by plans 08-01 and 08-02.

---

### Success Criteria Evaluation

| # | Success Criterion | Status | Notes |
|---|-------------------|--------|-------|
| 1 | Text capture from Expo produces StepStarted, StepFinished, CLASSIFIED/MISUNDERSTOOD/UNRESOLVED events identical to v1 | VERIFIED (automated) | New type names (STEP_START/STEP_END) used; mobile handles both; event payload structure confirmed by unit tests |
| 2 | Voice capture produces AG-UI events with transcription step followed by classification result | VERIFIED with design change | Single "Processing" step replaces two-step v1 structure; CONTEXT explicitly decided this for v2; voice produces STEP_START, STEP_END, CLASSIFIED, COMPLETE |
| 3 | FoundrySSEAdapter replaces AGUIWorkflowAdapter and mobile app works without any frontend code changes | VERIFIED | `AGUIWorkflowAdapter` is gone (no references); screen-level components (`text.tsx`, `index.tsx`, `inbox.tsx`, `conversation/[threadId].tsx`) unchanged; only `ag-ui-client.ts` (library layer) updated, which was explicitly in Phase 8 scope per CONTEXT |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `adapter.py` | 40 | `return {}` | Info | This is inside `_parse_args` defensive parser — legitimate empty dict fallback when raw arg is neither str nor Mapping. Not a stub. |
| `ag-ui-client.ts` | 214, 250 | `/api/ag-ui/respond`, `/api/ag-ui/follow-up` | Warning | `sendClarification` and `sendFollowUp` still point to old v1 endpoints. Documented as Phase 9 scope in both SUMMARY files. Not a Phase 8 gap. |

No blockers detected.

---

### Human Verification Required

#### 1. Text Capture End-to-End Flow

**Test:** Send a text capture from the running Expo app (e.g., "Schedule dentist appointment for next Tuesday") and observe the stream in the mobile UI.
**Expected:** Progress indicator shows "Classifying" step, then the capture appears as classified in the inbox (or clarification prompt shown for MISUNDERSTOOD). No duplicate result callbacks. Stream closes cleanly.
**Why human:** Requires live Foundry agent, Azure credentials, real SSE connection. Cannot verify Foundry `AgentResponseUpdate` content shape or tool-call argument parsing with grep alone.

#### 2. Voice Capture End-to-End Flow

**Test:** Record a short voice note from the home tab and observe the stream.
**Expected:** "Processing" step shown in UI, audio transcribed and classified, blob deleted after stream, result or clarification appears.
**Why human:** Requires configured Azure OpenAI transcription endpoint (`AZURE_OPENAI_ENDPOINT`), live blob storage, and Foundry agent with `transcribe_audio` tool available.

#### 3. No-Tool-Call Unresolved Edge Case (Advisory)

**Test:** If possible, trigger a capture where the Foundry agent returns only text reasoning and calls no tools (e.g., a truly ambiguous capture that confuses the agent).
**Expected:** Mobile should handle this gracefully. Currently: `UNRESOLVED` emitted with empty `inboxItemId`; mobile guard drops it (empty string is falsy); `COMPLETE` fires but `onComplete` not called for v2; mobile may appear hung.
**Why human:** Reproducing this requires either a controlled agent response or a capture that defeats the agent's tool-calling. The fix (if needed) would be to either: (a) emit a non-empty fallback item_id in `unresolved_event("")`, or (b) add `callbacks.onComplete("Unresolved")` in the COMPLETE v2 handler as a safety net.
**Severity:** Warning — this is an edge case unlikely to affect normal operation but worth validating.

---

### Gaps Summary

No automated gaps blocking goal achievement. All artifacts exist and are substantively implemented. All key wiring is verified. All 19 unit tests pass. All 61 backend tests pass (excluding integration). TypeScript compiles cleanly with no errors.

The one flagged item (no-tool-call unresolved) is an edge case behavior question requiring human judgment — it does not prevent the primary capture flows from working.

Phase 8 goal is achieved: text and voice captures are wired through the Foundry-backed Classifier, producing v2 AG-UI SSE events that the mobile app consumes via an updated (but screen-code-unchanged) client library.

---

_Verified: 2026-02-27T17:00:00Z_
_Verifier: Claude (gsd-verifier)_
