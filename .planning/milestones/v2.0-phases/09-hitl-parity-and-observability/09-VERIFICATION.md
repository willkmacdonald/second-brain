---
phase: 09-hitl-parity-and-observability
verified: 2026-02-28T20:30:00Z
status: human_needed
score: 14/14 must-haves verified
re_verification:
  previous_status: human_needed
  previous_score: 12/12
  gaps_closed:
    - "Follow-up reclassification updates the original misunderstood inbox doc in-place (no orphan created)"
    - "Voice follow-up reclassification updates the original misunderstood inbox doc in-place (no orphan created)"
    - "_stream_with_reconciliation completely removed -- in-place update prevents orphan creation entirely"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Submit an ambiguous but classifiable capture (e.g. 'thing about the place') from text capture screen"
    expected: "Bucket buttons appear on capture screen (LOW_CONFIDENCE path), NOT follow-up conversation (MISUNDERSTOOD). Tapping a bucket files instantly via PATCH."
    why_human: "Requires deployed backend with updated Foundry portal instructions (09-06). Misunderstood vs pending boundary is controlled by agent instructions in portal, not code."
  - test: "Submit genuinely nonsensical capture ('asdf jkl'), observe the follow-up input UI"
    expected: "Compact 60x60 record button appears below the follow-up question bubble with 'Type instead' toggle. Text input is NOT shown by default. Recording voice then stopping reclassifies on same thread."
    why_human: "Requires deployed backend and real Foundry agent producing MISUNDERSTOOD. Visual layout and voice transcription path cannot be verified programmatically."
  - test: "After MISUNDERSTOOD, say 'I need to build a presentation for a customer' via voice follow-up, then observe inbox"
    expected: "Reclassification routes to Projects bucket with high confidence. Filed toast appears. Inbox shows exactly ONE item -- the original misunderstood item updated in-place -- NOT two items."
    why_human: "Requires deployed backend to confirm ContextVar-based in-place update works end-to-end. The orphan fix (09-07) cannot be fully validated without a live follow-up that triggers file_capture."
  - test: "After MISUNDERSTOOD text follow-up, check inbox item count for the capture"
    expected: "Inbox shows exactly ONE item for the original capture (status updated to classified or pending). The original misunderstood item is updated in-place, no second orphan doc exists."
    why_human: "Same as above -- in-place upsert path requires live Cosmos DB to confirm read_item -> upsert_item succeeds and no create_item is issued."
  - test: "Application Insights query for traces after classification"
    expected: "Traces show classifier_agent_run span, tool_file_capture span with classification.bucket/confidence/status/item_id, endpoint spans. Token usage metrics visible."
    why_human: "Requires Azure portal access to App Insights to verify OTel data is flowing correctly."
---

# Phase 9: HITL Parity and Observability Verification Report

**Phase Goal:** All three HITL flows work identically to v1 on the Foundry backend, and Application Insights shows per-classification traces with token and cost metrics
**Verified:** 2026-02-28T20:30:00Z
**Status:** human_needed
**Re-verification:** Yes -- after 09-07 gap closure (follow-up orphan fix via ContextVar in-place updates)

---

## Re-verification Summary

Previous verification (2026-02-27T23:00:00Z) had status `human_needed` with score 12/12. Two UAT gaps were identified in the 09-UAT.md (Tests 3 and 4): follow-up reclassification (both text and voice) created orphan inbox docs instead of updating the original in-place. Plan 09-07 was created and executed to fix this.

**Gap status after 09-07:**
- "Follow-up creates orphan doc instead of updating original" -- CLOSED
- "Voice follow-up creates orphan doc instead of updating original" -- CLOSED
- `_stream_with_reconciliation` completely deleted -- CONFIRMED (zero grep matches)
- New `_stream_with_follow_up_context` wrapper with ContextVar-based in-place update -- VERIFIED
- `_write_follow_up_to_cosmos` method with `read_item` + `upsert_item` pattern -- VERIFIED

Two new human verification items added (tests 3 and 4 from UAT) for the in-place update behavior, which requires a live Cosmos DB to confirm end-to-end.

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                        | Status        | Evidence                                                                                                                               |
|----|----------------------------------------------------------------------------------------------|---------------|----------------------------------------------------------------------------------------------------------------------------------------|
| 1  | Low-confidence captures show bucket buttons on the capture screen for instant filing         | VERIFIED      | `_emit_result_event` emits `low_confidence_event` for `status=="pending"`. Mobile `onLowConfidence` calls `setShowSteps(true)` on both screens. |
| 2  | Misunderstood captures default to voice follow-up, with text as fallback                     | VERIFIED      | `followUpMode` initialized to `"voice"` in both `text.tsx` and `index.tsx`. Voice record button and "Type instead" toggle rendered conditionally. |
| 3  | Voice follow-up transcribes and reclassifies via the same Foundry thread                     | VERIFIED      | `POST /api/capture/follow-up/voice` reads bytes in-memory, transcribes via `gpt-4o-transcribe`, passes `foundry_thread_id` from Cosmos to `stream_follow_up_capture`. |
| 4  | Follow-up reclassification updates the original inbox doc in-place, no orphan doc created    | VERIFIED      | `_write_to_cosmos` reads `_follow_up_inbox_item_id` ContextVar (line 144). When set, routes to `_write_follow_up_to_cosmos` which does `read_item` + `upsert_item` (lines 254-260, 274-296). No `create_item` on inbox doc in follow-up mode. `_stream_with_reconciliation` confirmed deleted (zero grep matches). |
| 5  | Voice follow-up reclassification also updates in-place, no orphan doc created                | VERIFIED      | `follow_up_voice` endpoint wraps stream in `_stream_with_follow_up_context(generator, inbox_item_id, cosmos_manager)` (capture.py line 375). Same ContextVar path as text follow-up. |
| 6  | Initial text/voice captures (non-follow-up) still create new inbox docs as before            | VERIFIED      | `_write_to_cosmos` normal path (lines 160-231) only reached when `_follow_up_inbox_item_id.get()` returns `None`. `_stream_with_thread_id_persistence` unchanged for initial captures. |
| 7  | Classifier correctly distinguishes nonsensical (misunderstood) from ambiguous (pending)       | HUMAN NEEDED  | Code supports both paths. Runtime behavior depends on Foundry portal instruction update (09-06). |
| 8  | Action-oriented follow-up clarifications route to Projects bucket                            | HUMAN NEEDED  | Code supports this. Requires live test to confirm "I need to build a deck" routes to Projects. |
| 9  | In-place update succeeds in production (Cosmos read_item + upsert_item)                      | HUMAN NEEDED  | Code logic verified. Requires live follow-up to confirm Cosmos call succeeds and inbox shows exactly one item. |
| 10 | All previously verified truths remain intact (regression)                                    | VERIFIED      | sendClarification absent (0 matches). ag-ui/respond absent (0 matches). LOW_CONFIDENCE SSE path intact. Voice follow-up UI intact. OTel spans intact. ruff check passes. |

**Score:** 7/10 truths code-verified, 3 human-needed

---

## Required Artifacts (09-07 additions)

| Artifact | Expected | Level 1 (Exists) | Level 2 (Substantive) | Level 3 (Wired) | Status |
|----------|----------|------------------|-----------------------|-----------------|--------|
| `backend/src/second_brain/tools/classification.py` | `_follow_up_inbox_item_id` ContextVar, `follow_up_context` manager, `_write_follow_up_to_cosmos` method | YES | YES -- ContextVar at line 31-33, `follow_up_context` at lines 36-43, `_write_follow_up_to_cosmos` at lines 233-329 with full `read_item` + `upsert_item` logic | YES -- `_write_to_cosmos` reads ContextVar at line 144 and routes to `_write_follow_up_to_cosmos` at line 149 when set | VERIFIED |
| `backend/src/second_brain/api/capture.py` | `_stream_with_follow_up_context` function, both follow-up endpoints using it | YES | YES -- `_stream_with_follow_up_context` at lines 99-145 with `follow_up_context` wrapping, MISUNDERSTOOD `foundryThreadId` persistence post-stream | YES -- text `follow_up` at line 287, voice `follow_up_voice` at line 375 both use `_stream_with_follow_up_context` | VERIFIED |
| `backend/src/second_brain/streaming/adapter.py` | Cleaned of stale `datetime` imports | YES | YES -- no unused `from datetime import UTC, datetime` import; `datetime` is used in `classification.py` not `adapter.py` | YES -- `ruff check src/` passes with zero errors | VERIFIED |

**Confirmed absent:** `_stream_with_reconciliation` -- zero grep matches in entire backend/src/ tree.

---

## Key Link Verification (09-07)

| From | To | Via | Status | Evidence |
|------|----|-----|--------|----------|
| `capture.py follow_up` | `classification.py _follow_up_inbox_item_id` | `_stream_with_follow_up_context` wraps stream with `follow_up_context(inbox_item_id)` | WIRED | `follow_up_context` imported at line 26. Called at line 114 inside `_stream_with_follow_up_context`. Text follow-up uses it at line 287. |
| `capture.py follow_up_voice` | `classification.py _follow_up_inbox_item_id` | `stream_with_cleanup` iterates `_stream_with_follow_up_context` | WIRED | Voice follow-up `stream_with_cleanup` at line 372-383 iterates `_stream_with_follow_up_context(generator, inbox_item_id, cosmos_manager)` at line 375. |
| `classification.py _write_to_cosmos` | `classification.py _write_follow_up_to_cosmos` | ContextVar gate: `existing_inbox_id = _follow_up_inbox_item_id.get()` | WIRED | Lines 144-157: reads ContextVar, routes to `_write_follow_up_to_cosmos` when not None. |
| `classification.py _write_follow_up_to_cosmos` | Cosmos Inbox container | `read_item` then `upsert_item` on existing doc | WIRED | Lines 254-260 (misunderstood path): `read_item` + `upsert_item`. Lines 274-296 (classified/pending path): `read_item` + `upsert_item`. No `create_item` on inbox doc. |
| `classification.py _write_follow_up_to_cosmos` | Cosmos bucket container | `create_item` for new bucket doc pointing to original inbox ID | WIRED | Lines 299-315: new bucket doc created with `inboxRecordId=existing_inbox_id`. |

---

## Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|--------------|-------------|--------|----------|
| HITL-01 | 09-01, 09-03, 09-04 | Low-confidence captures filed as pending with bucket buttons for recategorization | SATISFIED | LOW_CONFIDENCE SSE event emitted for pending status. Mobile `onLowConfidence` sets `showSteps(true)` on both capture screens. Four PATCH recategorize paths intact. |
| HITL-02 | 09-01, 09-05, 09-07 | Misunderstood captures trigger conversational follow-up using fresh Foundry thread | SATISFIED | Voice-first follow-up (09-05). In-place update (09-07) prevents orphan docs. Both text and voice follow-up endpoints use `_stream_with_follow_up_context`. `file_capture` updates existing doc in-place via ContextVar. |
| HITL-03 | 09-01, 09-06 | Recategorize from inbox detail card works end-to-end | SATISFIED | `recategorize_inbox_item()` endpoint unchanged. Classifier instructions tuned (Foundry portal, user-confirmed via 09-06-SUMMARY). |
| OBSV-01 | 09-02, 09-03 | Application Insights receives traces from Foundry agent runs with per-classification visibility | SATISFIED (code) | All OTel spans in adapter.py: `capture_text`, `capture_voice`, `capture_follow_up`. `capture.original_inbox_item_id` attribute present. Human App Insights query needed to confirm production data flow. |
| OBSV-02 | 09-02 | Token usage and cost metrics visible in Foundry portal or Application Insights | SATISFIED (code) | `enable_instrumentation()` called after `configure_azure_monitor()` in main.py. Human verification needed. |

All 5 phase 9 requirement IDs accounted for across plans 09-01 through 09-07. No orphaned requirements found.

---

## Anti-Patterns Found

Scanned all three files modified by 09-07:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `adapter.py` | 44 | `return {}` | Info | Defensive fallback in `_parse_args` when `raw` is neither str nor Mapping. NOT a stub -- this is a correct empty-dict return for an unexpected input type. No impact. |

No TODOs, FIXMEs, placeholder comments, empty implementations, or stale reconciliation references. `ruff check src/` passes with zero errors.

---

## Human Verification Required

### 1. Low-Confidence Capture Shows Bucket Buttons (Not Follow-Up Screen)

**Test:** From the text capture screen, submit "thing about the place". Observe the result.
**Expected:** Bucket buttons appear on the capture screen with a prompt like "Best guess: Ideas. Which bucket?" -- NOT a follow-up conversation screen. Tapping a bucket files the item instantly via PATCH and shows a confirmation toast.
**Why human:** Requires deployed backend with updated Foundry portal instructions (09-06). The misunderstood vs pending boundary is controlled entirely by agent instructions in the portal -- not by code.

### 2. Voice Follow-Up is Default Mode

**Test:** Submit a genuinely nonsensical capture ("asdf jkl"). When the follow-up question appears, observe the input UI.
**Expected:** A compact (60x60) circular record button appears below the follow-up question bubble with "Type instead" text below it. Text input is NOT shown by default. Tapping "Type instead" switches to a text input with a "Record instead" toggle.
**Why human:** Requires deployed backend and real Foundry agent producing a MISUNDERSTOOD result. Visual layout cannot be verified programmatically.

### 3. Text Follow-Up Updates In-Place (No Orphan Doc)

**Test:** Submit "asdf jkl qwerty" to trigger MISUNDERSTOOD. Type a clarification ("I need to track a project for a customer"). After reclassification, check the inbox.
**Expected:** Inbox shows exactly ONE item for this capture. The original misunderstood item is updated in-place (status changed to classified or pending, `clarificationText` set). No second orphan doc exists.
**Why human:** The ContextVar-based in-place update path (09-07) requires a live Cosmos DB to confirm `read_item` succeeds and `upsert_item` updates the correct doc. This was the failing UAT test 3.

### 4. Voice Follow-Up Updates In-Place (No Orphan Doc)

**Test:** Trigger MISUNDERSTOOD, then use the voice follow-up to record a clarification. After filing, check the inbox.
**Expected:** Inbox shows exactly ONE item. The original misunderstood item is updated in-place, not a new doc. Filed toast appears with the correct bucket.
**Why human:** Same reason as test 3. This was the failing UAT test 4. Both text and voice paths share the same `_stream_with_follow_up_context` wrapper and `_write_follow_up_to_cosmos` method, but end-to-end behavior requires live Cosmos.

### 5. Application Insights Trace Verification

**Test:** After performing a few captures, query App Insights: `traces | where message contains "classifier_agent_run"` or use Application Map.
**Expected:** Traces show `capture_text`/`capture_voice`/`capture_follow_up` spans with `capture.bucket`, `capture.confidence`, `capture.outcome`, and `capture.original_inbox_item_id` attributes. Token usage metrics visible.
**Why human:** Requires Azure portal access to App Insights to confirm OTel data is flowing correctly.

---

## Regression Check Results

| Item | Previously Passing | Still Passing | Notes |
|------|--------------------|---------------|-------|
| `sendClarification` removed from mobile | YES | YES | 0 matches in entire mobile/ codebase |
| `/api/ag-ui/respond` references removed | YES | YES | 0 matches in entire mobile/ codebase |
| LOW_CONFIDENCE SSE path (`_emit_result_event` for pending) | YES | YES | adapter.py line 83-84 unchanged |
| Voice follow-up `followUpMode="voice"` default | YES | YES | text.tsx line 56, index.tsx line 86 unchanged |
| `_stream_with_reconciliation` deleted | YES | YES | 0 grep matches in backend/src/ |
| `ruff check src/` passes | YES | YES | All checks passed (current run) |
| `follow_up_context` importable | YES | YES | `.venv/bin/python3` import confirmed |
| `_stream_with_follow_up_context` importable | YES | YES | `.venv/bin/python3` import confirmed |
| `capture.original_inbox_item_id` OTel attribute | YES | YES | adapter.py line 432 unchanged |
| Initial captures create new inbox docs (no ContextVar set) | YES | YES | `_write_to_cosmos` normal path at lines 159-231 reached when `_follow_up_inbox_item_id.get()` is None |

---

## Final Assessment

Phase 9 goal is fully implemented in code across plans 09-01 through 09-07.

The critical UAT gaps (tests 3 and 4) that caused orphan inbox docs during follow-up reclassification are fixed by 09-07. The architectural approach changed from fragile post-hoc reconciliation (`_stream_with_reconciliation`) to prevention via ContextVar-based in-place updates (`_write_follow_up_to_cosmos`). The old reconciliation wrapper is completely removed with zero remaining references.

**HITL-02** is now fully implemented: misunderstood captures trigger voice-first follow-up, text follow-up reclassification updates the original doc in-place, voice follow-up reclassification also updates in-place. Both paths use the same `_stream_with_follow_up_context` wrapper and `_write_follow_up_to_cosmos` method.

**All 5 requirement IDs** (HITL-01, HITL-02, HITL-03, OBSV-01, OBSV-02) are satisfied in code. The 5 human verification items test runtime behavior that requires a deployed backend -- they are not code correctness issues.

---

*Verified: 2026-02-28T20:30:00Z*
*Verifier: Claude (gsd-verifier)*
*Re-verification after: 09-07-PLAN gap closure (follow-up orphan fix)*
