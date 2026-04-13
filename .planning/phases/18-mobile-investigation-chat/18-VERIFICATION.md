---
phase: 18-mobile-investigation-chat
verified: 2026-04-13T03:30:00Z
status: passed
score: 18/18 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 14/14
  gaps_closed: []
  gaps_remaining: []
  regressions: []
notes:
  - "ROADMAP success criteria mention 'last eval results' chip and 'eval scores' dashboard card, but these were explicitly deferred to Phase 21 per user decision in 18-CONTEXT.md. Not a gap -- intentional scoping."
  - "Pre-existing TypeScript error in _layout.tsx (ErrorFallback type vs Sentry FallbackRender) from Phase 17.3. Not caused by Phase 18. Tracked in deferred-items.md."
  - "ROADMAP.md checkbox for 18-03 still shows [ ] despite commit cb8fe29 existing. Documentation-only issue, not a code gap."
  - "Plan 03 added 4 new truths (gap closure for UAT blockers 8 and 9). Total now 18 truths across 3 plans."
---

# Phase 18: Mobile Investigation Chat Verification Report

**Phase Goal:** Investigation agent is accessible from the phone with a conversational chat interface and at-a-glance health dashboard
**Verified:** 2026-04-13T03:30:00Z
**Status:** passed
**Re-verification:** Yes -- after Plan 03 gap closure execution

## Goal Achievement

### Observable Truths

**Plan 01 Truths (Chat Screen):**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can open a chat screen from the Status screen or any navigation | VERIFIED | `_layout.tsx:34-42` registers `investigate` Stack.Screen; `status.tsx:432` has `router.push("/investigate")` on header icon press |
| 2 | User can type a question and see the agent's streamed response appear in real-time | VERIFIED | `investigate.tsx:86-153` `handleSendWithText` creates user+agent messages, calls `sendInvestigation` with `onText` callback that appends content via functional state update |
| 3 | Agent responses render markdown (bold, lists, tables) inside chat bubbles | VERIFIED | `InvestigateBubble.tsx:51-65` `AgentMarkdown` uses `useMarkdown` hook from react-native-marked with dark color scheme |
| 4 | "Thinking..." indicator appears while agent works, no tool call visibility | VERIFIED | `InvestigateBubble.tsx:39-41` shows "Thinking..." when content empty + isStreaming; `investigate-client.ts:89` silently ignores tool_call/tool_error/rate_warning |
| 5 | User can ask follow-up questions in the same session thread | VERIFIED | `investigate.tsx:50` tracks `threadId` state; `investigate.tsx:112` passes `threadId` to `sendInvestigation`; `investigate.tsx:135` stores `newThreadId` from done event |
| 6 | User can tap a quick action chip to send a pre-filled query immediately | VERIFIED | `QuickActionChips.tsx:8-21` defines 3 chips with queries; `investigate.tsx:168-172` `handleChipSelect` calls `handleSendWithText` |
| 7 | Chips disappear after the first message is sent | VERIFIED | `investigate.tsx:238-245` `renderEmpty` renders chips only when `messages` is empty (ListEmptyComponent); sending a message adds to messages array |
| 8 | User can speak a question using on-device voice recognition | VERIFIED | `investigate.tsx:61-82` speech recognition hooks at top level; `investigate.tsx:177-189` `handleVoicePress` toggles recording; auto-submits on end event |
| 9 | User can reset the conversation with a "new chat" header icon | VERIFIED | `investigate.tsx:193-201` `handleNewChat` clears messages, threadId, inputText, loading; `investigate.tsx:257-260` renders "New" header button |

**Plan 02 Truths (Dashboard Cards):**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 10 | User sees 3 dashboard cards at the top of the Status screen: capture count, success rate, last error | VERIFIED | `DashboardCards.tsx:22-69` renders 3 cards in horizontal row; `status.tsx:442-454` renders DashboardCards in ListHeaderComponent |
| 11 | Dashboard data refreshes on screen focus | VERIFIED | `status.tsx:252-276` `useFocusEffect` calls `fetchDashboardData()` alongside `fetchData()`; cleanup calls `dashboardCleanupRef.current?.()` |
| 12 | User can tap the last error card to jump to investigation chat with a pre-filled query | VERIFIED | `DashboardCards.tsx:48-55` error card Pressable calls `onErrorPress`; `status.tsx:446-453` wires `onErrorPress` to `router.push` with `initialQuery` param; `investigate.tsx:205-214` auto-sends `initialQuery` on mount |
| 13 | Header icon on the Status screen opens the investigation chat | VERIFIED | `status.tsx:429-437` header row with magnifying glass icon, `router.push("/investigate")` on press |
| 14 | Capture count and success rate cards are display-only (not tappable) | VERIFIED | `DashboardCards.tsx:28-46` first two cards use plain `View` (not Pressable); only error card uses `Pressable` |

**Plan 03 Truths (UAT Gap Closure):**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 15 | Status screen opens without voice capture fallback errors | VERIFIED | `index.tsx:91` `isRecordingRef` created; `index.tsx:93-95` synced via useEffect; `index.tsx:139` audiostart handler guards with `if (!isRecordingRef.current) return`; `index.tsx:145` error handler guards with `if (!isRecordingRef.current) return` |
| 16 | Navigating from investigate screen back to Status does not trigger stale voice capture | VERIFIED | Same isRecordingRef guard prevents cross-screen speech events from investigate screen's `abortRecognition()` (investigate.tsx:221) from triggering capture screen handlers |
| 17 | Caught errors in onError callbacks are reported to Sentry via captureMessage | VERIFIED | `index.tsx:32` imports Sentry; `index.tsx:219` has `Sentry.captureMessage` after first console.error; `index.tsx:631` has `Sentry.captureMessage` after second console.error |
| 18 | Error card on Status screen shows real errors (not perpetually "None") | VERIFIED | Pipeline restored: caught errors -> Sentry.captureMessage (production) -> Sentry. `ag-ui-client.ts:316-321` sends correct MIME type (WAV vs M4A); `capture.py:45` accepts `audio/vnd.wave` |

**Score:** 18/18 truths verified

### Required Artifacts

**Plan 01 Artifacts:**

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `mobile/lib/investigate-client.ts` | SSE client for /api/investigate | VERIFIED | 110 lines, exports `sendInvestigation`, handles all event types, `pollingInterval: 0`, explicit null checks for thread_id |
| `mobile/components/InvestigateBubble.tsx` | Chat bubble with markdown | VERIFIED | 105 lines, user/agent variants, `useMarkdown` hook for inline rendering, "Thinking..." indicator |
| `mobile/components/QuickActionChips.tsx` | Quick action chip row | VERIFIED | 76 lines, 3 chips with queries, `onSelect` callback, proper styling |
| `mobile/app/investigate.tsx` | Investigation chat screen | VERIFIED | 382 lines, FlatList inverted, streaming SSE, voice input, quick chips, new chat, initialQuery deep-link, scaleY:-1 for empty component |
| `mobile/app/_layout.tsx` | Route registration | VERIFIED | Lines 34-42 register `investigate` Stack.Screen |
| `mobile/package.json` | react-native-marked dependency | VERIFIED | `react-native-marked: ^8.0.1` |

**Plan 02 Artifacts:**

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `mobile/components/DashboardCards.tsx` | Dashboard card row | VERIFIED | 109 lines, 3 cards, loading state, error card tappable with red border highlight, exports `DashboardData` interface |
| `mobile/app/(tabs)/status.tsx` | Modified Status screen | VERIFIED | 612 lines, DashboardCards in ListHeaderComponent, investigate header icon, `fetchDashboardData` via SSE, regex parsing for metrics |

**Plan 03 Artifacts:**

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `mobile/app/(tabs)/index.tsx` | Guarded speech event handlers | VERIFIED | `isRecordingRef` at line 91, synced at 93-95, guards at 139 and 145, Sentry import at 32, captureMessage at 219 and 631 |
| `mobile/lib/ag-ui-client.ts` | Correct MIME type detection | VERIFIED | Lines 316-321: `isWav` detection from URI extension, conditional `audio/wav`/`audio/m4a` |
| `backend/src/second_brain/api/capture.py` | Extended ALLOWED_AUDIO_TYPES | VERIFIED | Line 45: `audio/vnd.wave` added to frozenset |

### Key Link Verification

**Plan 01 Links:**

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `investigate.tsx` | `investigate-client.ts` | `sendInvestigation()` call | WIRED | Line 111: `sendInvestigation({ question, threadId, apiKey, callbacks })` |
| `investigate-client.ts` | `/api/investigate` | EventSource POST | WIRED | Line 57: `${API_BASE_URL}/api/investigate` with POST method |
| `investigate.tsx` | `InvestigateBubble.tsx` | FlatList renderItem | WIRED | Line 14 import, lines 229-233 usage in renderMessage |
| `investigate.tsx` | `lib/speech.ts` | Voice input hooks | WIRED | Lines 13, 18-23 imports; lines 61-82, 177-189 usage |

**Plan 02 Links:**

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `status.tsx` | `investigate-client.ts` | `sendInvestigation()` for health data | WIRED | Line 21 import, line 97 usage in `fetchDashboardData` |
| `status.tsx` | `investigate.tsx` | `router.push("/investigate")` | WIRED | Lines 432 (header icon) and 447-452 (error card deep-link with initialQuery param) |
| `DashboardCards.tsx` | `investigate.tsx` | `onErrorPress` callback | WIRED | DashboardCards.tsx:50-53 calls `onErrorPress`; status.tsx:446-453 wires to `router.push` with `initialQuery` |

**Plan 03 Links:**

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `index.tsx` | Sentry | `Sentry.captureMessage` in onError callbacks | WIRED | Line 32 imports Sentry; lines 219 and 631 call captureMessage |
| `index.tsx` | `ag-ui-client.ts` | `sendVoiceCapture` with correct MIME | WIRED | sendVoiceCapture called in error handler fallback path; MIME now correct via URI extension detection |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-----------|-------------|--------|----------|
| MOBL-01 | 18-01 | Open chat screen from Status screen | SATISFIED | Header icon in status.tsx navigates; _layout.tsx registers route |
| MOBL-02 | 18-01 | SSE streaming with "Thinking..." indicator | SATISFIED | SSE client streams events; bubble shows "Thinking..." when content empty |
| MOBL-03 | 18-01 | Follow-up questions in same thread | SATISFIED | threadId stored from done event, passed on subsequent sends |
| MOBL-04 | 18-01 | Quick action chips for common queries | SATISFIED | 3 chips: recent errors, today's captures, system health. "Last eval results" chip deferred to Phase 21 per 18-CONTEXT.md. |
| MOBL-05 | 18-02 | Dashboard health cards | SATISFIED | 3 cards: capture count, success rate, last error. Eval scores card deferred to Phase 21 per 18-CONTEXT.md. |
| MOBL-06 | 18-02 | Error card deep-link to investigation chat | SATISFIED | Error card tap navigates with initialQuery param; investigate screen auto-sends on mount |
| OBS-01 | 18-03 (supplementary) | Caught errors reported to Sentry | SATISFIED | Sentry.captureMessage added at both console.error sites in index.tsx |

**Note on MOBL-04/MOBL-05:** REQUIREMENTS.md text includes "last eval results" (MOBL-04) and "eval scores" (MOBL-05) but the user explicitly decided in 18-CONTEXT.md to defer these to Phase 21 "when eval framework exists." This is a documented scoping decision, not a gap. The core requirement behavior (chips work, cards display health data) is satisfied.

**No orphaned requirements.** All 6 MOBL requirements mapped to Phase 18 in REQUIREMENTS.md are claimed by plans and verified. OBS-01 was additionally addressed by Plan 03.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `_layout.tsx` | 22 | TypeScript: ErrorFallback type vs Sentry FallbackRender | Info | Pre-existing from Phase 17.3. Not caused by Phase 18. Tracked in deferred-items.md. Runtime unaffected. |
| `ROADMAP.md` | 151 | `[ ] 18-03-PLAN.md` checkbox not marked complete | Info | Documentation only. Commit cb8fe29 exists and code changes verified. |

No TODO/FIXME/PLACEHOLDER/HACK comments in any Phase 18 files.
No hardcoded localhost URLs.
No empty implementations (return null, return {}, => {}).
No console.log-only handlers.
No stub patterns detected.

### Human Verification Required

### 1. Streaming Chat Flow

**Test:** Open the Status screen, tap the magnifying glass icon. Type "Show me recent errors" and tap send.
**Expected:** "Thinking..." appears in an agent bubble, then streamed text replaces it progressively with markdown formatting (bold, lists, etc.).
**Why human:** SSE streaming behavior and visual markdown rendering quality cannot be verified programmatically.

### 2. Quick Action Chips

**Test:** Open investigation chat (empty state). Tap "Recent errors" chip.
**Expected:** Chip row disappears, user message "Show me recent errors from the last 24 hours" appears, agent responds with streamed answer.
**Why human:** Visual transition and chip disappearance timing need visual confirmation.

### 3. Voice Input

**Test:** Tap the microphone button, speak a question, wait for auto-submit.
**Expected:** Button turns red while recording, transcribed text appears in input field, auto-submits when speech ends, agent responds.
**Why human:** On-device speech recognition requires physical device interaction.

### 4. Dashboard Cards Data Quality

**Test:** Open the Status screen and observe the 3 dashboard cards.
**Expected:** Cards show "..." briefly while loading, then display capture count, success rate %, and last error (or "None"). Error card has red border if error exists.
**Why human:** Agent prose parsing via regex is best-effort; quality depends on agent response format.

### 5. Error Card Deep-Link

**Test:** If a last error is displayed, tap the error card.
**Expected:** Investigation chat opens with pre-filled query about the error, auto-sends, agent responds with error details.
**Why human:** End-to-end navigation flow and query content need visual confirmation.

### 6. New Chat Reset

**Test:** After a conversation, tap the "New" button in the header.
**Expected:** All messages clear, quick action chips reappear, thread context is reset. Next question starts a fresh thread.
**Why human:** State reset completeness and visual transition need confirmation.

### 7. Cross-Screen Voice Event Isolation (Plan 03 Fix)

**Test:** Open investigation chat, use voice input, navigate back to Status screen. Then open investigation chat again, use voice, navigate back.
**Expected:** No "Voice capture fallback error" appears. No spurious voice capture upload is triggered.
**Why human:** Cross-screen navigation timing and event lifecycle are hard to simulate programmatically.

### 8. Sentry Error Reporting (Plan 03 Fix)

**Test:** Trigger a caught error in a production EAS build. Check Sentry dashboard for the error event.
**Expected:** Error appears in Sentry with the message from captureMessage. (Note: will NOT work in dev builds due to `enabled: !__DEV__`.)
**Why human:** Requires production EAS build and Sentry dashboard access.

## Summary

All 18 observable truths verified across 3 plans. All 11 artifacts exist, are substantive (no stubs), and properly wired. All 9 key links confirmed connected. All 6 MOBL requirements satisfied (with eval-related sub-items explicitly deferred to Phase 21 per user decision in 18-CONTEXT.md). OBS-01 additionally addressed by Plan 03 gap closure. No blocker anti-patterns found.

The UAT blockers (tests 8 and 9) identified during initial testing have been addressed by Plan 03: cross-screen voice event leak is prevented by isRecordingRef guard, MIME types are correctly detected, and Sentry.captureMessage instrumentation is in place. These fixes are committed (cb8fe29) but need re-testing on a production EAS build to confirm the full observability pipeline (human verification items 7 and 8).

The phase goal -- "Investigation agent is accessible from the phone with a conversational chat interface and at-a-glance health dashboard" -- is achieved.

---

_Verified: 2026-04-13T03:30:00Z_
_Verifier: Claude (gsd-verifier)_
