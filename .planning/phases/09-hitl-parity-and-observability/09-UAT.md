---
status: diagnosed
phase: 09-hitl-parity-and-observability
source: [09-01-SUMMARY.md, 09-02-SUMMARY.md, 09-03-SUMMARY.md]
started: 2026-02-27T20:00:00Z
updated: 2026-02-27T20:35:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Text Capture Classification (Happy Path)
expected: Type a clear thought and submit. Step dots animate during processing. Classification result appears with bucket and confidence. Item shows in Inbox.
result: pass

### 2. Misunderstood Follow-Up Conversation
expected: Type something ambiguous/nonsensical. The system marks it as misunderstood and shows a follow-up conversation. You can reply to clarify, and the system reclassifies using the same conversation thread.
result: issue
reported: "Misunderstood flow triggers correctly and shows follow-up conversation screen. But when replying to clarify, get error 'Couldn't classify. Try again'. App Insights shows POST /api/capture/follow-up returning 404. Also no title shown - displays 'Untitled'."
severity: blocker

### 3. Pending Item Bucket Selection (Inbox)
expected: Find a pending/low-confidence item in the Inbox. Tap into its detail card. Bucket buttons should appear. Tapping a bucket instantly files the item and updates the status.
result: pass

### 4. Bucket Selection from Capture Screen
expected: After a capture is classified with low confidence, bucket buttons appear on the capture screen itself. Tapping a bucket instantly files the item via PATCH. The UI confirms the filing.
result: issue
reported: "Used 'thing about the place' - it triggered the misunderstood follow-up flow instead of low-confidence bucket buttons. Follow-up reply then failed with same 'Couldn't classify' error (same root cause as Test 2 - /api/capture/follow-up 404)."
severity: blocker

### 5. Recategorize from Inbox Detail
expected: Open an already-classified item from the Inbox. Tap a different bucket to recategorize. The item's bucket updates immediately in Cosmos and the UI reflects the change.
result: pass

### 6. OTel Traces in Application Insights
expected: After performing a few captures, go to Application Insights and query traces. You should see per-classification spans with attributes like bucket, confidence, and token usage metrics.
result: pass

### 7. Voice Capture End-to-End
expected: Tap Voice, record a short message, submit. You should see transcription step followed by classification. The transcribed text and classification result appear. Item shows in Inbox.
result: issue
reported: "Voice capture passed when classified as idea (happy path). Second voice attempt triggered misunderstood flow, replied with clarification ('I need to build a deck for a customer'), then got 'Couldn't classify' error. Same follow-up 404 root cause as Test 2."
severity: major

## Summary

total: 7
passed: 4
issues: 3
pending: 0
skipped: 0

## Gaps

- truth: "Follow-up conversation reply reclassifies the capture using the same Foundry thread"
  status: failed
  reason: "User reported: Follow-up reply fails with 'Couldn't classify. Try again'. App Insights shows POST /api/capture/follow-up returning 404. Also title shows 'Untitled'."
  severity: blocker
  test: 2
  root_cause: "Two issues: (1) Phase 9 commits never pushed to origin/main — deployed container is still at Phase 8, so /api/capture/follow-up route doesn't exist. (2) file_capture tool default title='Untitled' stored to Cosmos; InboxItem.tsx shows truthy 'Untitled' instead of falling back to rawText."
  artifacts:
    - path: "backend/src/second_brain/api/capture.py"
      issue: "follow-up endpoint exists locally but not deployed"
    - path: "backend/src/second_brain/tools/classification.py"
      issue: "default title='Untitled' stored for misunderstood items"
    - path: "mobile/components/InboxItem.tsx"
      issue: "title || rawText shows 'Untitled' instead of rawText"
  missing:
    - "Push Phase 9 commits to origin/main to deploy follow-up endpoint"
    - "Change default title from 'Untitled' to None"
    - "Fix InboxItem preview to treat 'Untitled' as falsy or use rawText fallback"
  debug_session: ".planning/debug/follow-up-endpoint-404.md"

- truth: "Low-confidence capture shows bucket buttons on capture screen for instant filing"
  status: failed
  reason: "User reported: Ambiguous input triggered misunderstood flow instead of low-confidence bucket buttons, then follow-up failed with same 404"
  severity: blocker
  test: 4
  root_cause: "Two issues: (1) Foundry agent instructions (in portal) don't clearly distinguish misunderstood vs pending — ambiguous text gets classified as misunderstood instead of low-confidence pending. (2) v2 SSE protocol has no LOW_CONFIDENCE event — adapter treats pending same as classified (both emit CLASSIFIED event), so bucket buttons never appear on capture screen."
  artifacts:
    - path: "backend/src/second_brain/streaming/adapter.py"
      issue: "_emit_result_event treats pending same as classified — both emit CLASSIFIED event"
    - path: "backend/src/second_brain/streaming/sse.py"
      issue: "No low-confidence event type exists"
    - path: "mobile/lib/ag-ui-client.ts"
      issue: "CLASSIFIED always calls onComplete, no low-confidence HITL path"
  missing:
    - "Update Foundry agent instructions to clarify misunderstood vs pending boundary"
    - "Add LOW_CONFIDENCE SSE event type in adapter"
    - "Add mobile handler for LOW_CONFIDENCE that shows bucket buttons on capture screen"
  debug_session: ".planning/debug/phase9-uat-dual-issues.md"

- truth: "Voice capture follow-up conversation works end-to-end"
  status: failed
  reason: "User reported: Voice capture works for happy path but follow-up reply after misunderstood fails with 'Couldn't classify' - same /api/capture/follow-up 404"
  severity: major
  test: 7
  root_cause: "Same as Gap 1 — Phase 9 commits not pushed to origin/main, so follow-up endpoint doesn't exist on deployed container."
  artifacts:
    - path: "backend/src/second_brain/api/capture.py"
      issue: "follow-up endpoint exists locally but not deployed"
  missing:
    - "Push Phase 9 commits to deploy follow-up endpoint (same fix as Gap 1)"
  debug_session: ".planning/debug/follow-up-endpoint-404.md"

- truth: "Follow-up clarification supports voice reply (default) with text as fallback"
  status: failed
  reason: "User reported: Clarification conversation only supports text replies. Should default to voice input with text as backup — consistent with the app's voice-first capture philosophy."
  severity: major
  test: 2
  root_cause: "Conversation screen only has a text input field. No voice recording option exists on the follow-up/clarification screen."
  artifacts:
    - path: "mobile/app/conversation/[threadId].tsx"
      issue: "Only text input for follow-up replies, no voice recording capability"
  missing:
    - "Add voice recording to conversation/clarification screen as the default input mode"
    - "Text input as secondary/fallback option"
    - "Backend follow-up endpoint needs to accept audio uploads (like /api/capture/voice) and transcribe before reclassifying"
  debug_session: ""

- truth: "Follow-up classification correctly routes action-oriented clarifications to Projects"
  status: failed
  reason: "User reported: After 'one two six seven' triggered misunderstood, clarification mentioning an action was filed as Ideas at 80% instead of Projects. Agent instructions need tuning for follow-up context."
  severity: minor
  test: 2
  root_cause: "Foundry classifier agent instructions (managed in AI Foundry portal) don't weight action-oriented language strongly enough toward Projects bucket during follow-up reclassification."
  artifacts:
    - path: "AI Foundry portal — agent asst_Fnjkq5RVrvdFIOSqbreAwxuq"
      issue: "Agent instructions need tuning for follow-up context — action verbs should signal Projects"
  missing:
    - "Update classifier agent instructions in Foundry portal to better handle follow-up context"
    - "Add examples: 'I need to build/do/make/schedule...' → Projects"
    - "Clarify that follow-up text provides critical context that should override initial ambiguity"
  debug_session: ""
