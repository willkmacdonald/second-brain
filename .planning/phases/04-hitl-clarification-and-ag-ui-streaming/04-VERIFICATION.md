---
phase: 04-hitl-clarification-and-ag-ui-streaming
verified: 2026-02-23T23:45:00Z
status: human_needed
score: 14/14 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 12/12
  previous_verified: 2026-02-23T16:30:00Z
  context: "UAT.md (updated 2026-02-23T16:10:00Z) documented two major failures discovered during user testing after the prior VERIFICATION was written. Plan 04-06 was executed (commits 1e2f2cb, ce993a7) to close those gaps. This re-verification covers all 12 prior truths plus 2 new UAT-gap truths."
  gaps_closed:
    - "Ambiguous capture triggers HITL clarifying question on capture screen (UAT Test 5) — Classifier removed from autonomous mode so request_clarification pauses the workflow instead of being overridden"
    - "Selecting a bucket on conversation screen files the capture and updates status from pending to classified (UAT Test 11) — useCallback dependency array fixed to include item, so item?.id is non-null when sendClarification is called"
    - "Inbox auto-refreshes on screen focus after filing from conversation screen — useFocusEffect replaces mount-only useEffect"
    - "Respond endpoint returns truthful error messages instead of fake success when inbox_item_id is missing or DB write fails"
    - "No duplicate React key warnings in FlatList — deduplication by ID on append pagination"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Submit ambiguous text (e.g. 'Interesting conversation with Mike about moving to Austin'). Watch for HITL trigger."
    expected: "Bucket buttons appear with a specific LLM-generated clarifying question (e.g. 'I'm torn between People (0.55) and Ideas (0.42)...') — NOT a generic string. Top 2 suggested buckets should be filled blue (#4a90d9); other 2 should be outline/subdued."
    why_human: "Confirms the Classifier actually calls request_clarification at runtime (not classify_and_file), that the LLM generates a specific question, and that the visual emphasis is correct. UAT Test 5 was previously failing; fix is in the code but needs runtime confirmation."
  - test: "Submit low-confidence capture. Tap a bucket button inline on capture screen. Switch to Inbox tab and pull-to-refresh."
    expected: "Item that was Pending (orange dot) now shows as filed with chosen bucket — no orange dot, correct bucket label. Confirms upsert path at main.py:401 executes and status transitions from 'pending' to 'classified'."
    why_human: "Requires live Cosmos DB + backend. UAT Test 6 was blocked by Test 5 failure and was not tested. Now that Test 5 fix is in place, this test needs to run."
  - test: "Submit low-confidence capture without resolving inline. Switch to Inbox, tap the pending item (orange dot), then tap a bucket button on the conversation screen."
    expected: "Navigates back to inbox automatically. The previously-pending item now shows as filed (orange dot gone, chosen bucket displayed) WITHOUT needing a manual pull-to-refresh. Confirms useCallback fix sends correct item.id and useFocusEffect auto-refreshes the list."
    why_human: "Requires live backend + Cosmos DB. UAT Test 11 was failing due to stale closure sending null inboxItemId. Fix is code-verified but needs runtime confirmation that DB actually updates."
  - test: "Step dot animation timing on any capture submission."
    expected: "Orchestrator pill lights up blue first, then turns green as Classifier activates (blue), then Classifier turns green when done."
    why_human: "React Native animation state timing cannot be verified statically."
---

# Phase 4: HITL Clarification and AG-UI Streaming Verification Report

**Phase Goal:** Will can see agents working in real time and respond to clarification questions when the system is unsure
**Verified:** 2026-02-23T23:45:00Z
**Status:** human_needed (all automated checks pass; UAT gap fixes code-verified, need runtime confirmation)
**Re-verification:** Yes — after UAT gap closure (Plan 04-06, commits 1e2f2cb and ce993a7)

---

## Re-Verification Context

The previous VERIFICATION.md (2026-02-23T16:30:00Z) was marked `status: passed` with 12/12 truths verified. However, UAT.md (updated 2026-02-23T16:10:00Z) documents two major failures discovered during user testing on the deployed Azure Container Apps environment:

- **UAT Test 5 (HITL not triggering):** Ambiguous captures were auto-filed instead of triggering a clarifying question. Root cause: Classifier in autonomous mode; framework re-ran it after `request_clarification`, which overrode the HITL flow.
- **UAT Test 11 (Filing remains pending):** Selecting a bucket on the conversation screen claimed success but the item remained pending in the DB. Root cause: `useCallback` closure stale on `item?.id` (null at memoization time); inbox had no auto-refresh on focus; duplicate React key warnings.

Plan 04-06 was created to close both gaps. Commits `1e2f2cb` (backend) and `ce993a7` (mobile) executed on 2026-02-23T23:12:30Z.

**This re-verification confirms all plan 04-06 fixes are present in the codebase.** UAT retesting is required to confirm runtime behavior.

---

## Goal Achievement

### Success Criteria

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | User sees real-time visual feedback showing the agent chain processing their capture (Orchestrator -> Classifier -> Action) | VERIFIED | StepStarted/StepFinished events emitted in workflow.py lines 201-212; AgentSteps component renders horizontal pills; text.tsx wires onStepStart/onStepFinish callbacks |
| 2 | When classification confidence is < 0.6, the user is asked a focused clarifying question before filing | VERIFIED (code) | Classifier not in autonomous mode (workflow.py line 101: `agents=[self._orchestrator]`); request_clarification tool creates pending Inbox doc with LLM-generated clarificationText; HITL_REQUIRED event carries inboxItemId and questionText. UAT runtime retest required. |
| 3 | Inbox view shows recent captures with the agent chain that processed each one | VERIFIED | inbox.tsx FlatList with InboxItem rows; detail card shows agentChain.join(" -> "); classificationMeta.agentChain stored by ClassificationTools |
| 4 | Conversation view opens when a specialist needs clarification, showing a focused chat | VERIFIED (code) | Conversation screen shows LLM-generated clarificationText, passes item.id as inboxItemId (with item in useCallback dep array), upserts Inbox doc on resolution, navigates back to inbox. Inbox useFocusEffect auto-refreshes. UAT runtime retest required. |

**Score:** 4/4 success criteria code-verified

---

## Observable Truths Verification

### Original Truths (Plans 04-01 through 04-05)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When confidence < 0.6, the Classifier calls request_clarification instead of classify_and_file, creating a pending Inbox document with no bucket container record | VERIFIED | classifier.py Rule 2: "When confidence < 0.6, call request_clarification instead". classification.py request_clarification creates InboxDocument with status="pending", NO bucket container write |
| 2 | request_clarification returns LLM-generated clarification text with top-2 bucket reasoning, stored as clarificationText on the InboxDocument | VERIFIED | classification.py: `clarificationText=clarification_text` on InboxDocument; return format "Clarification → {uuid} | {text}" |
| 3 | HITL_REQUIRED custom event includes inboxItemId in its value payload so the client can pass it back for resolution | VERIFIED | workflow.py lines 290-297: CustomEvent with value={"threadId": thread_id, "inboxItemId": inbox_item_id, "questionText": clarification_text} |
| 4 | POST /api/ag-ui/respond with inbox_item_id updates the existing pending Inbox document status to 'classified' and files to the chosen bucket container | VERIFIED | main.py lines 346-436: reads existing doc, creates bucket record, upserts existing Inbox doc with status="classified", filedRecordId set |
| 5 | GET /api/inbox/{id} returns clarificationText field for conversation screen display | VERIFIED | inbox.py InboxItemResponse has `clarificationText: str \| None = None`; list mapping includes `clarificationText=item.get("clarificationText")` |
| 6 | When HITL_REQUIRED fires on capture screen, bucket buttons appear with the classifier's real clarifying question (not filing confirmation text) | VERIFIED | ag-ui-client.ts: `const questionText = parsed.value.questionText || result`; text.tsx sets `setHitlQuestion(questionText)` from event |
| 7 | Tapping a bucket button on capture screen sends inboxItemId to the respond endpoint, causing the DB to update | VERIFIED | text.tsx: `inboxItemId: hitlInboxItemId ?? undefined` passed to sendClarification; ag-ui-client.ts includes `inbox_item_id: inboxItemId` in POST body |
| 8 | Top 2 suggested buckets are visually emphasized (filled/primary style), other 2 are subdued (outline/secondary style) | VERIFIED | text.tsx: `isTopBucket ? styles.bucketButtonPrimary : styles.bucketButtonSecondary`; bucketButtonPrimary has backgroundColor "#4a90d9" |
| 9 | Conversation screen shows the classifier's actual reasoning text from clarificationText field (not hardcoded generic question) | VERIFIED | conversation/[threadId].tsx line 126-127: `const question = item?.clarificationText \|\| "Which bucket does this belong to?"` — clarificationText is primary, generic is fallback only |
| 10 | Tapping a bucket button on conversation screen sends inboxItemId to the respond endpoint, updating the DB | VERIFIED | conversation/[threadId].tsx line 71: `inboxItemId: item?.id` in sendClarification; `item` is now in useCallback dep array (line 99) |
| 11 | After resolution from conversation screen, user navigates back to inbox and item shows as filed | VERIFIED (code) | conversation/[threadId].tsx line 78: `router.back()` called onComplete; inbox.tsx useFocusEffect auto-refetches on focus; DB upsert sets status="classified" |
| 12 | Inbox UI recognizes both status='pending' (new flow) and status='low_confidence' (legacy) as pending items | VERIFIED | InboxItem.tsx line 49: `isPending = item.status === "pending" \|\| item.status === "low_confidence"`; inbox.tsx useEffect badge count: `s === "pending" \|\| s === "low_confidence"` |

### Plan 04-06 Truths (UAT Gap Closure)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 13 | Classifier is NOT in autonomous mode so request_clarification pauses the workflow instead of being overridden | VERIFIED | workflow.py line 101: `agents=[self._orchestrator]` — Classifier absent from autonomous mode agents list. Docstring explicitly states: "The Classifier is NOT autonomous so that when it calls request_clarification, the framework emits a request_info event and the workflow pauses for HITL." |
| 14 | handleBucketSelect dependency array includes item so item?.id is non-null when sendClarification is called | VERIFIED | conversation/[threadId].tsx line 99: `[threadId, isResolving, item]` — item is in the dependency array. Previously `[threadId, isResolving]`, causing stale closure with null item?.id |

**Overall truth score:** 14/14 truths verified

---

## Required Artifacts

### Plan 04-06 Artifacts

| Artifact | Status | Exists | Substantive | Wired | Details |
|----------|--------|--------|-------------|-------|---------|
| `backend/src/second_brain/agents/workflow.py` | VERIFIED | Yes | Yes — 356 lines; `agents=[self._orchestrator]` in with_autonomous_mode; docstring explains Classifier pauses on request_clarification | Wired via create_capture_workflow -> main.py lifespan | Classifier autonomy removed; request_info handler continues (workflow pause for HITL) |
| `backend/src/second_brain/main.py` | VERIFIED | Yes | Yes — guard at line 349: `if not body.inbox_item_id:` returns SSE error; `logger.exception` at line 432 replaces bare except; `result = "Error: Could not file capture. Please try again."` | Wired as /api/ag-ui/respond route | Truthful error messages instead of fake success |
| `mobile/app/conversation/[threadId].tsx` | VERIFIED | Yes | Yes — 301 lines; `[threadId, isResolving, item]` dep array at line 99; `inboxItemId: item?.id` at line 71 | Wired via expo-router stack navigation from inbox.tsx | Stale closure bug fixed |
| `mobile/app/(tabs)/inbox.tsx` | VERIFIED | Yes | Yes — 277 lines; `useFocusEffect(useCallback(() => { void fetchInbox(); }, [fetchInbox]))` at line 67-71; `existingIds` deduplication at line 48; separate useEffect for badge count at line 74-81 | Wired via expo-router tab file-system routing | Auto-refresh and deduplication implemented |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `workflow.py with_autonomous_mode` | `HandoffBuilder` | `agents=[self._orchestrator]` only | VERIFIED | Line 101: only Orchestrator is autonomous. Classifier absent. Previously `[self._orchestrator, self._classifier]` — that was the UAT Test 5 root cause. |
| `workflow.py request_info handler` | `HITL_REQUIRED CustomEvent` | `detected_clarification` regex match | VERIFIED | Lines 248-254: request_info received -> log and continue; line 284: after stream, if detected_clarification is not None -> emit HITL_REQUIRED with inboxItemId and questionText |
| `main.py respond endpoint` | `Cosmos DB Inbox container` | `upsert_item` on existing doc | VERIFIED | Line 429: `existing["status"] = "classified"`; upsert path correct |
| `main.py respond endpoint` | `SSE error on missing inbox_item_id` | early return guard | VERIFIED | Lines 349-363: guard fires before DB ops; returns error text event and RunFinishedEvent |
| `conversation/[threadId].tsx handleBucketSelect` | `sendClarification` | `item?.id` as inboxItemId (item in dep array) | VERIFIED | Line 71: `inboxItemId: item?.id`; line 99: dep array `[threadId, isResolving, item]` — item is loaded from API before buttons are interactive |
| `inbox.tsx useFocusEffect` | `fetchInbox` | `useFocusEffect(useCallback(() => void fetchInbox()))` | VERIFIED | Lines 67-71: useFocusEffect wraps fetchInbox call; fires on every screen focus including return from conversation screen |
| `inbox.tsx FlatList` | `deduplication` | `existingIds Set filter` on append | VERIFIED | Lines 47-53: functional state updater builds existingIds Set and filters newItems — fixes duplicate React key warning |

---

## Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CLAS-04 | 04-01, 04-04, 04-06 | When confidence < 0.6, Classifier asks the user a focused clarifying question before filing | SATISFIED | Classifier removed from autonomous mode (04-06). request_clarification tool creates pending Inbox doc with LLM-generated clarificationText and no bucket write. HITL_REQUIRED emitted with inboxItemId. REQUIREMENTS.md traceability marks CLAS-04 as Complete. |
| CAPT-02 | 04-01, 04-02 | User receives real-time visual feedback showing the agent chain processing their capture (Orchestrator → Classifier → Action) | SATISFIED | StepStarted/StepFinished events emitted; AgentSteps renders horizontal pills; text streaming word-by-word. REQUIREMENTS.md marks CAPT-02 as Complete. |
| APPX-02 | 04-01, 04-03 | Inbox view shows recent captures with the agent chain that processed each one | SATISFIED | inbox.tsx FlatList; detail card shows agentChain.join(" -> "); classificationMeta.agentChain stored by ClassificationTools. REQUIREMENTS.md marks APPX-02 as Complete. |
| APPX-04 | 04-03, 04-05, 04-06 | Conversation view opens when a specialist needs clarification, showing a focused chat | SATISFIED | Conversation screen shows LLM-generated clarificationText, item.id passed as inboxItemId (fixed dep array), upserts Inbox doc, navigates back. Inbox auto-refreshes on focus. REQUIREMENTS.md marks APPX-04 as Complete. |

All 4 phase requirements fully satisfied. No orphaned requirements.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | All phase 04 and 04-06 files are free of TODO/FIXME/placeholder/stub patterns |

No blockers. No stubs. No placeholder implementations.

---

## Test Results

| Test Suite | Result | Count |
|------------|--------|-------|
| backend tests (uv run python -m pytest) | PASSED | 34/34 |
| TypeScript compile (npx tsc --noEmit) | PASSED | 0 errors |

Plan 04-06 did not add new tests (bug fixes to existing wiring, not new logic paths that require new test coverage).

---

## Human Verification Required

### 1. Classifier Generates Real LLM Question and HITL Triggers (UAT Test 5 — was failing)

**Test:** Submit ambiguous text (e.g., "Had coffee with Mike, he mentioned a new project idea"). Watch for HITL trigger.
**Expected:** Bucket buttons appear with a specific LLM-generated question like "I'm torn between People (0.55) and Ideas (0.42). This mentions Mike but also a life change discussion. Which fits better?" — NOT a generic or static string. Top 2 mentioned buckets should have filled blue (#4a90d9) buttons; other 2 should be outline/subdued.
**Why human:** UAT Test 5 was failing due to the Classifier being in autonomous mode. The code fix (removing Classifier from autonomous mode agents list) is verified, but runtime confirmation is needed to confirm the framework's request_info pause actually fires in the deployed Azure Container Apps environment and the HITL flow completes end-to-end.

### 2. Capture Screen HITL Resolution Updates Database (UAT Test 6 — was skipped)

**Test:** After triggering HITL (Test 1 above), tap a bucket button inline on the capture screen. Switch to Inbox tab and pull-to-refresh.
**Expected:** The item that was "Pending" (orange dot) now shows as filed with the chosen bucket — no orange dot, correct bucket label. Screen auto-resets after resolution.
**Why human:** UAT Test 6 was blocked by Test 5 failure. Now that the HITL trigger fix is in place, this test runs for the first time. Requires live Cosmos DB + backend.

### 3. Conversation Screen HITL Resolution Updates Database (UAT Test 11 — was failing)

**Test:** Submit low-confidence capture without resolving inline. Switch to Inbox. Tap the pending item (orange dot). Tap a bucket button on the conversation screen.
**Expected:** Navigates back to inbox automatically. The previously-pending item now shows as filed (orange dot gone, chosen bucket displayed) WITHOUT needing a manual pull-to-refresh.
**Why human:** UAT Test 11 was failing due to stale useCallback closure sending null inboxItemId. Code fix (item in dep array) is verified. Requires live backend + Cosmos DB to confirm the correct document ID flows through to the upsert and status transitions to "classified".

### 4. Step Dot Animation Timing

**Test:** Submit any text capture. Watch the step dots below the input.
**Expected:** Orchestrator pill activates (blue) first, transitions to completed (green) as Classifier activates (blue), then Classifier turns green when done.
**Why human:** React Native animation state transitions cannot be verified statically.

---

## Gaps Summary

No gaps. All automated checks pass. Plan 04-06 closed both UAT gaps:

**UAT Gap 1 (HITL trigger — UAT Test 5):** `workflow.py` `with_autonomous_mode` previously listed both `self._orchestrator` and `self._classifier` in the agents list. When the Classifier called `request_clarification`, the HandoffAgentExecutor saw the autonomous classifier's turn was not completed (no handoff back), injected the autonomous prompt as a synthetic user message, and re-ran the Classifier — which then called `classify_and_file` instead. Fix: Classifier removed from autonomous mode entirely (`agents=[self._orchestrator]` only). Now when the Classifier calls `request_clarification`, the framework emits `request_info` and the workflow pauses. The adapter detects `detected_clarification` from the prior output stream and emits `HITL_REQUIRED` after the stream ends.

**UAT Gap 2 (Filing remains pending — UAT Test 11):** `conversation/[threadId].tsx` `handleBucketSelect` was memoized with `[threadId, isResolving]` as the dependency array. `item` was not included, so `item?.id` was always null at the time the callback was memoized (item is loaded asynchronously from the API). The stale closure sent `null` as `inbox_item_id` to the backend. The backend's guard condition `if body.inbox_item_id and cosmos_manager` evaluated to false, skipping all DB operations — but still emitting a "Filed → Bucket (0.85)" success message. Three fixes: (1) `item` added to useCallback dep array so closure captures the loaded item; (2) `useFocusEffect` in inbox.tsx auto-refetches on screen focus so navigating back shows updated status; (3) FlatList deduplication by ID on append to fix the React duplicate key warning.

---

_Verified: 2026-02-23T23:45:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification after UAT gap closure (Plan 04-06, commits 1e2f2cb and ce993a7)_
