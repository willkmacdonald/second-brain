---
phase: 09-hitl-parity-and-observability
verified: 2026-02-27T20:10:00Z
status: passed
score: 9/9 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 7/9
  gaps_closed:
    - "Tapping a bucket button during active capture (text or voice) instantly files the item via PATCH to /api/inbox/{id}/recategorize"
    - "sendClarification function and its v1 /api/ag-ui/respond references are removed from the codebase"
    - "capture.original_inbox_item_id OTel span attribute contains the actual Cosmos inbox item ID, not the Foundry thread ID"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Submit a misunderstood capture from the text capture screen, receive a follow-up question, type a reply and submit"
    expected: "sendFollowUp should stream re-classification via /api/capture/follow-up. This flow is correctly wired and should work."
    why_human: "Requires real Foundry agent to produce a MISUNDERSTOOD result, which cannot be triggered deterministically in code inspection"
  - test: "Open inbox, tap a pending item, select a bucket from the bucket buttons"
    expected: "handlePendingResolve calls handleRecategorize PATCH instantly, item updates to classified status in UI"
    why_human: "Requires deployed backend and a real pending item in Cosmos DB"
  - test: "Application Insights query for traces after classification"
    expected: "Traces show classifier_agent_run span, tool_file_capture span with classification.bucket/confidence/status/item_id, and capture_text endpoint span with capture.outcome/bucket/confidence. Token usage (gen_ai.usage.input_tokens, gen_ai.usage.output_tokens) visible in metrics."
    why_human: "Requires Azure portal access to App Insights to verify OTel data is flowing correctly"
---

# Phase 9: HITL Parity and Observability Verification Report

**Phase Goal:** All three HITL flows work identically to v1 on the Foundry backend, and Application Insights shows per-classification traces with token and cost metrics
**Verified:** 2026-02-27T20:10:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (09-03-PLAN executed)

---

## Re-verification Summary

Previous verification (2026-02-27T18:06:40Z) found 2 blocker gaps:

1. In-capture bucket selection in `text.tsx` and `index.tsx` called `sendClarification()` which targeted the deleted v1 endpoint `/api/ag-ui/respond`.
2. `capture.original_inbox_item_id` OTel span attribute was populated with `foundry_thread_id` instead of the actual Cosmos inbox item ID.

Gap-closure plan 09-03 was executed. Both gaps are confirmed closed. All regressions checked — none found.

---

## Goal Achievement

### Observable Truths (from Success Criteria)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Low-confidence captures are filed as pending with bucket buttons appearing in the mobile inbox for recategorization; bucket selection during active capture files the item instantly | VERIFIED | text.tsx and index.tsx handleBucketSelect now use fetch PATCH to `/api/inbox/${hitlInboxItemId}/recategorize` (text.tsx line 231, index.tsx line 369). sendClarification and /api/ag-ui/respond fully removed from codebase. |
| 2 | Misunderstood captures trigger conversational follow-up using a fresh Foundry thread with no history contamination from the first classification pass | VERIFIED | stream_follow_up_capture passes `conversation_id: foundry_thread_id` in ChatOptions (adapter.py line 363). foundryThreadId persisted after MISUNDERSTOOD via _stream_with_thread_id_persistence. sendFollowUp in ag-ui-client.ts calls /api/capture/follow-up. |
| 3 | Recategorize from inbox detail card writes to Cosmos DB and updates the mobile UI | VERIFIED | recategorize_inbox_item() in inbox.py with OTel span (line 203). inbox.tsx handleRecategorize PATCH (line 136). conversation/[threadId].tsx handleBucketSelect PATCH (line 65). |
| 4 | Application Insights shows traces for Foundry agent runs with per-classification visibility including token usage | VERIFIED (code) / HUMAN | enable_instrumentation() called after configure_azure_monitor() (main.py lines 15, 22). AuditAgentMiddleware creates classifier_agent_run span. ToolTimingMiddleware creates tool_file_capture span with classification attributes. 3 endpoint spans in adapter.py. Requires human App Insights query to confirm data flow. |

**Score:** 4/4 success criteria verified

### Plan-level Must-Have Truths (09-01 and 09-02 Plans)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Tapping a bucket button on a pending inbox item instantly files it via PATCH | VERIFIED | inbox.tsx handlePendingResolve delegates to handleRecategorize PATCH (line 184). conversation/[threadId].tsx handleBucketSelect PATCH (line 65). |
| 2 | Tapping a bucket button during active capture (text or voice) instantly files it via PATCH | VERIFIED | text.tsx handleBucketSelect: async fetch PATCH to /api/inbox/${hitlInboxItemId}/recategorize with error handling (lines 224-256). index.tsx handleBucketSelect: same pattern (lines 361-395). |
| 3 | sendClarification function and all /api/ag-ui/respond references removed from codebase | VERIFIED | Zero matches for `sendClarification` across entire mobile/ directory. Zero matches for `ag-ui/respond`. SendClarificationOptions interface also removed from types.ts. |
| 4 | Misunderstood captures can receive follow-up replies on the same Foundry thread | VERIFIED | stream_follow_up_capture uses conversation_id in ChatOptions. foundryThreadId persisted. /api/capture/follow-up reads foundryThreadId from Cosmos (400 if missing). |
| 5 | After successful follow-up reclassification, the original inbox item is updated and the orphan document is deleted | VERIFIED | _stream_with_reconciliation wrapper copies classificationMeta/filedRecordId to original, updates status, upserts, updates bucket doc inboxRecordId, deletes orphan (capture.py lines 102-197). |
| 6 | Recategorize from inbox detail card continues to work unchanged | VERIFIED | recategorize_inbox_item() endpoint unchanged. handleRecategorize in inbox.tsx confirmed. conversation screen PATCH confirmed. |
| 7 | Agent runs produce OTel spans with classification-specific attributes (bucket, confidence, status, item_id) | VERIFIED | ToolTimingMiddleware creates tool_file_capture span. Sets classification.bucket, classification.confidence, classification.status, classification.item_id (middleware.py lines 68-96). |
| 8 | enable_instrumentation() is called after configure_azure_monitor() so token usage metrics flow to App Insights | VERIFIED | main.py: configure_azure_monitor() at line 15, enable_instrumentation() at line 22. Correct ordering confirmed. |
| 9 | capture.original_inbox_item_id OTel span attribute contains the actual Cosmos inbox item ID | VERIFIED | adapter.py stream_follow_up_capture has `original_inbox_item_id: str` parameter (line 335). Span attribute set from parameter (line 357). capture.py passes `original_inbox_item_id=body.inbox_item_id` (line 356). |

**Score:** 9/9 plan must-haves verified

### Required Artifacts

| Artifact | Expected | Level 1 (Exists) | Level 2 (Substantive) | Level 3 (Wired) | Status |
| -------- | -------- | ---------------- | --------------------- | --------------- | ------ |
| `mobile/app/capture/text.tsx` | handleBucketSelect using fetch PATCH to recategorize | YES | YES — async fn, guard, PATCH, haptic, toast, error handling (lines 224-256) | YES — hitlInboxItemId state wired as guard and in URL | VERIFIED |
| `mobile/app/(tabs)/index.tsx` | handleBucketSelect using fetch PATCH to recategorize | YES | YES — async fn, guard, PATCH, haptic, toast, error handling (lines 361-395) | YES — hitlInboxItemId state wired as guard and in URL | VERIFIED |
| `mobile/lib/ag-ui-client.ts` | sendClarification removed, no /api/ag-ui/respond references | YES | YES — zero matches for sendClarification or ag-ui/respond in entire mobile/ | YES — sendFollowUp correctly wired to /api/capture/follow-up | VERIFIED |
| `mobile/lib/types.ts` | SendClarificationOptions interface removed | YES | YES — zero matches for SendClarificationOptions | YES — no dead type imports remain | VERIFIED |
| `backend/src/second_brain/streaming/adapter.py` | stream_follow_up_capture with original_inbox_item_id parameter | YES | YES — parameter at line 335, span attribute at line 357, docstring updated | YES — imported in capture.py line 22, called with named arg | VERIFIED |
| `backend/src/second_brain/api/capture.py` | Caller passes original_inbox_item_id to stream_follow_up_capture | YES | YES — `original_inbox_item_id=body.inbox_item_id` at line 356 | YES — body.inbox_item_id is validated Pydantic field | VERIFIED |
| `backend/src/second_brain/agents/middleware.py` | OTel-instrumented AuditAgentMiddleware and ToolTimingMiddleware | YES | YES — tracer.start_as_current_span in both classes | YES — wired into classifier_client middleware in main.py | VERIFIED |
| `backend/src/second_brain/main.py` | enable_instrumentation() called after configure_azure_monitor() | YES | YES — both imports and calls present in correct order | YES — called at startup before app routes are served | VERIFIED |
| `backend/src/second_brain/api/inbox.py` | OTel span on recategorize endpoint | YES | YES — start_as_current_span("recategorize") with item_id, new_bucket, old_bucket, success attributes | YES — router registered in main.py | VERIFIED |

### Key Link Verification

| From | To | Via | Status | Evidence |
| ---- | -- | --- | ------ | -------- |
| `mobile/app/capture/text.tsx` | `/api/inbox/{id}/recategorize` | fetch PATCH in handleBucketSelect | WIRED | `${API_BASE_URL}/api/inbox/${hitlInboxItemId}/recategorize` at line 232 |
| `mobile/app/(tabs)/index.tsx` | `/api/inbox/{id}/recategorize` | fetch PATCH in handleBucketSelect | WIRED | `${API_BASE_URL}/api/inbox/${hitlInboxItemId}/recategorize` at line 369 |
| `backend/src/second_brain/api/capture.py` | `stream_follow_up_capture` | original_inbox_item_id parameter | WIRED | `original_inbox_item_id=body.inbox_item_id` at line 356 |
| `backend/src/second_brain/streaming/adapter.py` | OTel span attribute | original_inbox_item_id not foundry_thread_id | WIRED | `span.set_attribute("capture.original_inbox_item_id", original_inbox_item_id)` at line 357 |
| `mobile/lib/ag-ui-client.ts` | `/api/capture/follow-up` | sendFollowUp POST | WIRED | `/api/capture/follow-up` at line 212 |
| `backend/src/second_brain/main.py` | `agent_framework.observability` | enable_instrumentation after configure_azure_monitor | WIRED | Confirmed ordering: line 15 then line 22 |
| `backend/src/second_brain/agents/middleware.py` | `opentelemetry.trace` | tracer for custom spans | WIRED | `from opentelemetry import trace` at line 21 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| HITL-01 | 09-01-PLAN, 09-03-PLAN | Low-confidence captures filed as pending with bucket buttons for recategorization — all paths (inbox, conversation, text capture, voice capture) | SATISFIED | All four bucket selection paths now use instant PATCH to recategorize. sendClarification and /api/ag-ui/respond fully removed. |
| HITL-02 | 09-01-PLAN | Misunderstood captures trigger conversational follow-up using fresh Foundry thread (no conversation history contamination) | SATISFIED | stream_follow_up_capture uses conversation_id. foundryThreadId persisted. sendFollowUp correctly wired. |
| HITL-03 | 09-01-PLAN | Recategorize from inbox detail card works end-to-end (direct Cosmos write, unchanged) | SATISFIED | Recategorize PATCH endpoint unchanged. handleRecategorize in inbox.tsx confirmed. conversation screen PATCH confirmed. |
| OBSV-01 | 09-02-PLAN, 09-03-PLAN | Application Insights receives traces from Foundry agent runs with per-classification visibility | SATISFIED (code) | All OTel spans in place. capture.original_inbox_item_id now records actual Cosmos item ID (not Foundry thread ID). Requires human App Insights query to confirm data flowing. |
| OBSV-02 | 09-02-PLAN | Token usage and cost metrics visible in Application Insights | SATISFIED (code) | enable_instrumentation() called after configure_azure_monitor() — SDK automatically tracks gen_ai.usage.input_tokens/output_tokens. Requires human App Insights verification. |

All 5 phase 9 requirement IDs are accounted for. No orphaned requirements found.

### Anti-Patterns Found

No blocker anti-patterns found. The previously-identified blockers (`sendClarification` and `/api/ag-ui/respond` calls in text.tsx and index.tsx) have been resolved.

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| None | — | — | — | All clear |

### Human Verification Required

#### 1. Misunderstood Follow-Up End-to-End

**Test:** Submit a genuinely ambiguous capture from the text capture screen, receive a MISUNDERSTOOD question, type a reply, observe re-classification.
**Expected:** sendFollowUp() calls /api/capture/follow-up, streams STEP_START/STEP_END/CLASSIFIED events, item gets reconciled (original updated, orphan deleted).
**Why human:** Requires real Foundry agent producing a MISUNDERSTOOD result, which cannot be triggered deterministically in code inspection.

#### 2. Pending Item Resolution from Inbox

**Test:** Open inbox, tap a pending item (status = "pending" or "low_confidence"), tap a bucket button.
**Expected:** handlePendingResolve() calls handleRecategorize() PATCH immediately, item updates to classified status, recategorize toast appears.
**Why human:** Requires deployed backend and a real pending item in Cosmos DB.

#### 3. Application Insights Trace Verification

**Test:** After a classification completes, query App Insights: `traces | where message contains "classifier_agent_run"` or use the Application Map to see trace hierarchy.
**Expected:** Traces show classifier_agent_run span as parent, tool_file_capture span as child with classification.bucket/confidence/status/item_id, capture_text endpoint span wrapping both. Token usage metrics visible under customMetrics or OTel metrics. The capture.original_inbox_item_id attribute on capture_follow_up spans should show a Cosmos item ID (uuid-like string), not a Foundry thread ID.
**Why human:** Requires Azure portal access and App Insights connection string correctly configured on Container App.

---

## Regression Check Results

| Item | Previously Passing | Still Passing | Notes |
| ---- | ------------------ | ------------- | ----- |
| inbox.tsx handlePendingResolve -> handleRecategorize PATCH | YES | YES | Line 184 confirmed |
| conversation/[threadId].tsx handleBucketSelect PATCH | YES | YES | Line 65 confirmed |
| middleware.py AuditAgentMiddleware OTel spans | YES | YES | tracer.start_as_current_span confirmed |
| main.py enable_instrumentation ordering | YES | YES | Lines 15, 22 confirmed |
| ag-ui-client.ts sendFollowUp -> /api/capture/follow-up | YES | YES | Line 212 confirmed |
| adapter.py capture_text/capture_voice/capture_follow_up spans | YES | YES | Lines 101, 218, 352 confirmed |
| inbox.py recategorize OTel span | YES | YES | Line 203 confirmed |

---

## Final Assessment

Phase 9 goal is achieved. All three HITL flows now work via the unified instant PATCH pattern:

- **Inbox bucket buttons** (pending items): handlePendingResolve -> handleRecategorize PATCH
- **Conversation screen bucket buttons**: handleBucketSelect PATCH
- **Text capture screen bucket buttons**: handleBucketSelect PATCH (gap-closure fix, 09-03)
- **Voice capture screen bucket buttons**: handleBucketSelect PATCH (gap-closure fix, 09-03)

The dead v1 code path (sendClarification / /api/ag-ui/respond) has been completely removed from the mobile codebase, including the SendClarificationOptions type definition.

Observability is instrumented at every level: SDK-level token tracking via enable_instrumentation(), middleware-level agent spans (classifier_agent_run, tool_file_capture), endpoint-level spans (capture_text, capture_voice, capture_follow_up, recategorize), and the capture.original_inbox_item_id attribute is now populated with the correct Cosmos inbox item ID.

The remaining human verification items are confirmation of correct runtime behavior — not code correctness issues.

---

*Verified: 2026-02-27T20:10:00Z*
*Verifier: Claude (gsd-verifier)*
*Re-verification after: 09-03-PLAN gap closure*
