---
phase: 04-hitl-clarification-and-ag-ui-streaming
verified: 2026-02-23T16:30:00Z
status: passed
score: 12/12 must-haves verified
re_verification: true
  previous_status: gaps_found
  previous_score: 7/11 must-haves verified
  gaps_closed:
    - "Classifier asks a focused clarifying question before filing when confidence < 0.6"
    - "POST /api/ag-ui/respond resumes a paused HITL workflow and files the capture"
    - "HITL resolution updates the database via upsert_item on the existing Inbox document"
    - "inboxItemId flows from HITL_REQUIRED event through sendClarification to backend"
    - "Conversation screen shows real classifier reasoning (clarificationText), not hardcoded generic question"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Submit ambiguous text (e.g. 'Interesting conversation with Mike about moving to Austin'). Watch for HITL trigger."
    expected: "Bucket buttons appear with classifier's real LLM-generated clarifying question above them. Top 2 buckets (People and Ideas) should have filled blue buttons; other 2 should be outline/subdued."
    why_human: "Visual appearance and LLM reasoning content cannot be verified statically. Confirms classifier actually calls request_clarification at runtime."
  - test: "Submit low-confidence capture. Tap a bucket button on capture screen. Switch to Inbox and pull-to-refresh."
    expected: "Item that was Pending (orange dot) now shows as filed with chosen bucket and no orange dot. Confirms DB status updated via upsert."
    why_human: "Requires live Cosmos DB + backend. Verifies the full upsert path actually executes in production."
  - test: "Submit low-confidence capture without resolving inline. Switch to Inbox, tap the pending item, then tap a bucket."
    expected: "Navigates back to inbox. The previously-pending item now shows as filed. Confirms conversation screen passes item.id to sendClarification and upsert path works."
    why_human: "Requires live backend + Cosmos DB. E2E test of conversation screen resolution path."
  - test: "Step dot animation timing on any capture submission."
    expected: "Orchestrator pill lights up blue first, then turns green as Classifier activates (blue), then Classifier turns green when done."
    why_human: "React Native animation state timing cannot be verified statically."
---

# Phase 4: HITL Clarification and AG-UI Streaming Verification Report

**Phase Goal:** Will can see agents working in real time and respond to clarification questions when the system is unsure
**Verified:** 2026-02-23T16:30:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (Plans 04-04 and 04-05)

---

## Re-Verification Summary

All 3 blockers identified in the initial verification (2026-02-22) have been closed. Plans 04-04 (backend) and 04-05 (frontend) executed and verified.

**Blockers closed:**
1. Classifier now asks real clarifying questions via `request_clarification` tool before filing low-confidence captures
2. HITL resolution correctly updates the Cosmos DB document via `upsert_item` when `inboxItemId` is present
3. Conversation screen shows real `clarificationText` from the backend instead of hardcoded "Which bucket does this belong to?"

---

## Goal Achievement

### Success Criteria

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | User sees real-time visual feedback showing the agent chain processing their capture (Orchestrator -> Classifier -> Action) | VERIFIED | StepStarted/StepFinished events emitted in workflow.py lines 196-207; AgentSteps component renders horizontal pills; text.tsx wires onStepStart/onStepFinish callbacks |
| 2 | When classification confidence is < 0.6, the user is asked a focused clarifying question before filing | VERIFIED | Classifier Rule 1 updated: "When confidence < 0.6, call request_clarification instead". `request_clarification` tool creates pending Inbox doc with LLM-generated clarificationText and NO bucket container write. HITL_REQUIRED event carries inboxItemId and questionText. |
| 3 | Inbox view shows recent captures with the agent chain that processed each one | VERIFIED | inbox.tsx FlatList with InboxItem rows; detail card shows agentChain.join(" -> "); classificationMeta.agentChain stored by ClassificationTools |
| 4 | Conversation view opens when a specialist needs clarification, showing a focused chat | VERIFIED | Conversation screen fetches item via GET /api/inbox/{id}, shows clarificationText (LLM-generated), passes item.id as inboxItemId to sendClarification; bucket selection upserts Inbox document status to "classified" |

**Score:** 4/4 success criteria verified

---

## Observable Truths Verification

### Plan 04-04 Truths (Gap Closure — Backend)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When confidence < 0.6, the Classifier calls request_clarification instead of classify_and_file, creating a pending Inbox document with no bucket container record | VERIFIED | classifier.py Rule 2: "When confidence < 0.6, call request_clarification instead". classification.py request_clarification tool creates InboxDocument with status="pending", filedRecordId=None, NO bucket container write |
| 2 | request_clarification returns LLM-generated clarification text with top-2 bucket reasoning, stored as clarificationText on the InboxDocument | VERIFIED | classification.py line 207: `clarificationText=clarification_text` on InboxDocument; return format "Clarification → {uuid} | {text}" |
| 3 | HITL_REQUIRED custom event includes inboxItemId in its value payload so the client can pass it back for resolution | VERIFIED | workflow.py lines 283-290: CustomEvent with value={"threadId": thread_id, "inboxItemId": inbox_item_id, "questionText": clarification_text} |
| 4 | POST /api/ag-ui/respond with inbox_item_id updates the existing pending Inbox document status to 'classified' and files to the chosen bucket container | VERIFIED | main.py lines 346-401: reads existing doc, creates bucket record, upserts existing Inbox doc with status="classified", filedRecordId set |
| 5 | GET /api/inbox/{id} returns clarificationText field for conversation screen display | VERIFIED | inbox.py InboxItemResponse has `clarificationText: str | None = None`; list mapping includes `clarificationText=item.get("clarificationText")` |

### Plan 04-05 Truths (Gap Closure — Frontend)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 6 | When HITL_REQUIRED fires on capture screen, bucket buttons appear with the classifier's real clarifying question (not filing confirmation text) | VERIFIED | ag-ui-client.ts: `const questionText = parsed.value.questionText || result`; text.tsx sets `setHitlQuestion(questionText)` from event; hitlQuestion renders as question text above bucket buttons |
| 7 | Tapping a bucket button on capture screen sends inboxItemId to the respond endpoint, causing the DB to update | VERIFIED | text.tsx line 154: `inboxItemId: hitlInboxItemId ?? undefined` passed to sendClarification; ag-ui-client.ts sendClarification includes `inbox_item_id: inboxItemId` in POST body |
| 8 | Top 2 suggested buckets are visually emphasized (filled/primary style), other 2 are subdued (outline/secondary style) | VERIFIED | text.tsx: `isTopBucket ? styles.bucketButtonPrimary : styles.bucketButtonSecondary`; bucketButtonPrimary has backgroundColor "#4a90d9"; bucketButtonSecondary is transparent with border |
| 9 | Conversation screen shows the classifier's actual reasoning text from clarificationText field (not hardcoded generic question) | VERIFIED | conversation/[threadId].tsx line 126-127: `const question = item?.clarificationText || "Which bucket does this belong to?"` — clarificationText is primary, generic is fallback only |
| 10 | Tapping a bucket button on conversation screen sends inboxItemId to the respond endpoint, updating the DB | VERIFIED | conversation/[threadId].tsx line 71: `inboxItemId: item?.id` passed to sendClarification |
| 11 | After resolution from conversation screen, user navigates back to inbox and item shows as filed | VERIFIED | conversation/[threadId].tsx line 77: `router.back()` called onComplete; DB upsert sets status="classified" so orange dot disappears on next inbox fetch |
| 12 | Inbox UI recognizes both status='pending' (new flow) and status='low_confidence' (legacy) as pending items | VERIFIED | InboxItem.tsx line 49: `isPending = item.status === "pending" || item.status === "low_confidence"`; inbox.tsx line 53: `isPendingStatus = (s) => s === "pending" || s === "low_confidence"` for badge count and navigation routing |

**Overall truth score:** 12/12 truths verified

---

## Required Artifacts

### Plan 04-04 Artifacts (Backend Gap Closure)

| Artifact | Status | Exists | Substantive | Wired | Details |
|----------|--------|--------|-------------|-------|---------|
| `backend/src/second_brain/tools/classification.py` | VERIFIED | Yes | Yes — 246 lines, request_clarification tool with LLM-generated clarificationText | Wired via ClassificationTools -> classifier agent tools list | request_clarification creates pending Inbox doc, returns "Clarification → {uuid} | {text}" |
| `backend/src/second_brain/models/documents.py` | VERIFIED | Yes | Yes — InboxDocument has `clarificationText: str | None = None` at line 49 | Wired via InboxDocument used by request_clarification tool | Field exists and is set in request_clarification |
| `backend/src/second_brain/agents/classifier.py` | VERIFIED | Yes | Yes — Rule 2 and Low Confidence Handling section added; request_clarification in tools list at line 116 | Wired via create_classifier_agent -> main.py lifespan | "When confidence < 0.6, call request_clarification instead" instruction present |
| `backend/src/second_brain/agents/workflow.py` | VERIFIED | Yes | Yes — _CLARIFICATION_RE regex, _extract_clarification method, detected_clarification tracking, HITL_REQUIRED with inboxItemId | Wired via create_capture_workflow -> main.py | inboxItemId and questionText in CustomEvent value at lines 283-290 |
| `backend/src/second_brain/main.py` | VERIFIED | Yes | Yes — respond endpoint reads existing Inbox doc, creates bucket record, upserts with status="classified" at line 401 | Wired as /api/ag-ui/respond route | upsert_item used to update existing pending document |
| `backend/src/second_brain/api/inbox.py` | VERIFIED | Yes | Yes — InboxItemResponse has clarificationText field; mapping at line 81 includes it | Wired via include_router(inbox_router) in main.py | Both list and get endpoints return clarificationText |

### Plan 04-05 Artifacts (Frontend Gap Closure)

| Artifact | Status | Exists | Substantive | Wired | Details |
|----------|--------|--------|-------------|-------|---------|
| `mobile/lib/types.ts` | VERIFIED | Yes | Yes — onHITLRequired has `inboxItemId?: string` parameter; SendClarificationOptions has `inboxItemId?: string` | Imported by ag-ui-client.ts and text.tsx | Type contract updated for new flow |
| `mobile/lib/ag-ui-client.ts` | VERIFIED | Yes | Yes — AGUIEventPayload.value has inboxItemId/questionText; CUSTOM handler passes both to onHITLRequired | Imported by text.tsx and conversation/[threadId].tsx | `parsed.value.inboxItemId` extracted and forwarded |
| `mobile/app/capture/text.tsx` | VERIFIED | Yes | Yes — hitlInboxItemId state, extracted from onHITLRequired; passed to sendClarification; primary/secondary bucket styling | Wired to ag-ui-client.ts via sendCapture/sendClarification imports | inboxItemId flows: HITL_REQUIRED event -> state -> sendClarification |
| `mobile/app/conversation/[threadId].tsx` | VERIFIED | Yes | Yes — clarificationText used as primary question; item?.id passed as inboxItemId; topBuckets derived from allScores; primary/secondary styling | Wired via router.push from inbox.tsx; calls sendClarification | All 3 blockers fixed: real question, inboxItemId, top-2 emphasis |
| `mobile/components/InboxItem.tsx` | VERIFIED | Yes | Yes — InboxItemData has clarificationText and allScores fields; isPending checks both "pending" and "low_confidence" | Imported by inbox.tsx and conversation/[threadId].tsx | Dual-status pending recognition present |
| `mobile/app/(tabs)/inbox.tsx` | VERIFIED | Yes | Yes — isPendingStatus helper; badge count and navigation routing check both status values | Wired via expo-router tab file-system routing | Both statuses handled correctly |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `classifier.py` | `classification.py request_clarification` | Tool in tools list | VERIFIED | Line 116: `classification_tools.request_clarification` in tools list |
| `workflow.py _extract_clarification` | `HITL_REQUIRED CustomEvent.value.inboxItemId` | _CLARIFICATION_RE regex parsing | VERIFIED | Lines 152-155: regex extracts (inbox_item_id, clarification_text); lines 283-290: both included in CustomEvent value |
| `main.py respond endpoint` | `Cosmos DB Inbox container` | upsert_item on existing doc | VERIFIED | Line 401: `await inbox_container.upsert_item(body=existing)` after setting status="classified" |
| `ag-ui-client.ts CUSTOM handler` | `onHITLRequired callback` | `parsed.value.inboxItemId` | VERIFIED | Lines 63-73: inboxItemId extracted from parsed.value and passed as 3rd arg to callback |
| `text.tsx onHITLRequired` | `sendClarification` | `hitlInboxItemId` state | VERIFIED | Line 110: `setHitlInboxItemId(inboxItemId ?? null)`; line 154: `inboxItemId: hitlInboxItemId ?? undefined` in sendClarification call |
| `conversation/[threadId].tsx handleBucketSelect` | `sendClarification` | `item?.id` | VERIFIED | Line 71: `inboxItemId: item?.id` in sendClarification call |
| Previously broken: `text.tsx -> sendClarification` | `inboxItemId (DB filing)` | inboxItemId param | NOW WIRED | Was NOT_WIRED in initial verification; fixed in plan 04-05 |
| Previously broken: `conversation -> sendClarification` | `inboxItemId (DB filing)` | inboxItemId param | NOW WIRED | Was NOT_WIRED in initial verification; fixed in plan 04-05 |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CLAS-04 | 04-01, 04-04 | When confidence < 0.6, Classifier asks the user a focused clarifying question before filing | SATISFIED | Classifier Rule 2: "call request_clarification instead". Tool creates pending Inbox doc with LLM-generated clarificationText. No bucket container write until user responds. REQUIREMENTS.md traceability table marks CLAS-04 as Complete. |
| CAPT-02 | 04-01, 04-02 | User receives real-time visual feedback showing the agent chain processing their capture | SATISFIED | StepStarted/StepFinished events emitted; AgentSteps component renders agent chain progression; streaming text appears word-by-word |
| APPX-02 | 04-01, 04-03 | Inbox view shows recent captures with the agent chain that processed each one | SATISFIED | inbox.tsx FlatList with InboxItem; detail card shows agentChain; classificationMeta.agentChain stored by ClassificationTools |
| APPX-04 | 04-03, 04-05 | Conversation view opens when a specialist needs clarification, showing a focused chat | SATISFIED | Conversation screen shows LLM-generated clarificationText, passes item.id as inboxItemId, upserts Inbox doc on resolution, navigates back to inbox |

All 4 requirements fully satisfied.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `mobile/app/conversation/[threadId].tsx` | 99 | `useCallback` dependency array `[threadId, isResolving]` missing `item` while closure uses `item?.id` | Info | item is set once before bucket buttons are ever interactive (loading guard prevents render until item is loaded), so stale closure is not a practical runtime bug. React exhaustive-deps lint warning only. |

No blockers. No stubs. No placeholder implementations.

---

## Human Verification Required

### 1. Classifier Generates Real LLM Question

**Test:** Submit ambiguous text (e.g., "Interesting conversation with Mike about moving to Austin"). Watch for HITL trigger.
**Expected:** Bucket buttons appear with a specific LLM-generated question like "I'm torn between People (0.55) and Ideas (0.42). This mentions Mike but also a life change discussion. Which fits better?" — NOT a generic or static string. Top 2 mentioned buckets should have filled blue (#4a90d9) buttons; other 2 should be outline/subdued.
**Why human:** Confirms the classifier actually calls `request_clarification` at runtime (not `classify_and_file`), that the LLM generates a specific question, and that the visual emphasis is correct.

### 2. Capture Screen HITL Resolution Updates Database

**Test:** Submit low-confidence capture. Tap a bucket button inline on capture screen. Switch to Inbox tab and pull-to-refresh.
**Expected:** The item that was "Pending" (orange dot) now shows as filed with the chosen bucket — no orange dot, correct bucket label displayed.
**Why human:** Requires live Cosmos DB + backend. Verifies the upsert path at main.py:401 actually executes and updates status from "pending" to "classified".

### 3. Conversation Screen HITL Resolution Updates Database

**Test:** Submit low-confidence capture without resolving inline. Switch to Inbox. Tap the pending item (orange dot). Tap a bucket button on the conversation screen. Observe navigation back to inbox.
**Expected:** After tapping a bucket: navigates back to inbox. The previously-pending item now shows as filed (orange dot gone, chosen bucket displayed).
**Why human:** Requires live backend + Cosmos DB. Verifies the conversation screen passes item.id correctly and the upsert path succeeds end-to-end.

### 4. Step Dot Animation Timing

**Test:** Submit any text capture. Watch the step dots below the input.
**Expected:** Orchestrator pill activates (blue) first, transitions to completed (green) as Classifier activates (blue), then Classifier turns green when done.
**Why human:** React Native animation state transitions cannot be verified statically.

---

## Test Results

| Test Suite | Result | Count |
|------------|--------|-------|
| backend tests | PASSED | 34/34 |
| TypeScript compile (mobile) | PASSED | 0 errors |
| Ruff linting (backend) | PASSED | 0 issues |

New tests added by plan 04-04:
- `test_request_clarification_creates_pending_inbox` — PASSED
- `test_request_clarification_returns_parseable_string` — PASSED
- `test_request_clarification_invalid_bucket` — PASSED

---

## Gaps Summary

No gaps. All 3 blockers from the initial verification have been closed by plans 04-04 and 04-05:

**Blocker 1 (CLAS-04 — Classifier now asks real questions):** `classifier.py` Rule 1 was updated to a two-path decision: `classify_and_file` when confidence >= 0.6, `request_clarification` when confidence < 0.6. The `request_clarification` tool creates a pending Inbox document with LLM-generated `clarificationText` and no bucket container write. The workflow adapter detects the "Clarification → {uuid} | {text}" return format via `_CLARIFICATION_RE` regex and emits `HITL_REQUIRED` with `inboxItemId` and `questionText`.

**Blocker 2 (HITL resolution updates the database):** The respond endpoint was rewritten to read the existing pending Inbox document, create the bucket container record, and call `upsert_item` on the existing document with `status="classified"` and `filedRecordId` set. Both the capture screen (`text.tsx`) and conversation screen now pass `inboxItemId` to `sendClarification`, which includes it in the POST body as `inbox_item_id`. The backend upsert path requires `inbox_item_id` to be present.

**Blocker 3 (Conversation screen shows real classifier reasoning):** The `InboxItemData` type was updated with `clarificationText?: string`. The `GET /api/inbox/{id}` endpoint returns the full document including `clarificationText`. The conversation screen reads `item?.clarificationText` as the primary question source, with `"Which bucket does this belong to?"` as fallback only. The dead conditional (both branches returning the same hardcoded string) was replaced with the real data-driven expression.

**What works correctly (carried forward from initial verification):**
- AG-UI SSE step events (StepStarted/StepFinished) emitted and visualized correctly
- Text streaming word-by-word wired end-to-end
- Tab navigation (Capture/Inbox) with all 4 capture buttons preserved
- Inbox list with FlatList, pull-to-refresh, pagination, orange dot indicators, detail card modal, and badge count
- Echo filtering (Orchestrator text suppressed) implemented correctly
- All 34 backend tests pass
- TypeScript compiles without errors
- Dual-status pending recognition: both "pending" (new flow) and "low_confidence" (legacy) recognized for orange dot, badge count, and conversation navigation

---

_Verified: 2026-02-23T16:30:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification after gap closure (Plans 04-04, 04-05)_
