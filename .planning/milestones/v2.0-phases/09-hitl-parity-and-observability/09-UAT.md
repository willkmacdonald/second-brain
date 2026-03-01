---
status: diagnosed
phase: 09-hitl-parity-and-observability
source: [09-01-SUMMARY.md, 09-02-SUMMARY.md, 09-03-SUMMARY.md, 09-04-SUMMARY.md, 09-05-SUMMARY.md, 09-06-SUMMARY.md]
started: 2026-02-27T21:00:00Z
updated: 2026-02-27T21:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Text Capture Happy Path (Classified)
expected: Type a clear, unambiguous thought and submit. Step dots animate during processing. A "Filed" toast appears with bucket and confidence. Item appears in Inbox under the correct bucket.
result: pass

### 2. Low-Confidence Capture Shows Bucket Buttons
expected: Type something vague but classifiable (e.g., "that thing about the place"). The system classifies it as LOW_CONFIDENCE and shows bucket buttons on the capture screen. Tapping a bucket instantly files the item via PATCH. A "Filed" toast confirms.
result: pass

### 3. Misunderstood Follow-Up Conversation (Text)
expected: Type something genuinely nonsensical (e.g., "asdf jkl qwerty"). The system marks it as misunderstood and shows a follow-up conversation. You can type a clarification reply. The system reclassifies using the same Foundry thread and shows the result.
result: issue
reported: "does not clean up the original junk note"
severity: major

### 4. Misunderstood Follow-Up Conversation (Voice)
expected: On the misunderstood follow-up screen, the default input mode is voice (compact record button). Tap record, speak a clarification, submit. The system transcribes and reclassifies. A "Type instead" toggle is available to switch to text input.
result: issue
reported: "same as voice version - after clarifying the misunderstood comment, it filed it under Admin but the original misunderstood note was never cleaned up and it was actually filed under the same bucket. So now two things instead of one clarified thing"
severity: major

### 5. Follow-Up Reclassification Routes Correctly
expected: After a misunderstood follow-up, provide an action-oriented clarification (e.g., "I need to build a deck for a customer"). The reclassification should route to Projects, not Ideas. Action verbs like build/create/schedule should signal Projects.
result: pass

### 6. Pending Item Bucket Selection (Inbox)
expected: Find a pending/low-confidence item in the Inbox. Tap into its detail card. Bucket buttons appear. Tapping a bucket instantly files the item and updates the status.
result: pass

### 7. Recategorize from Inbox Detail
expected: Open an already-classified item from the Inbox. Tap a different bucket to recategorize. The item's bucket updates immediately in Cosmos and the UI reflects the change.
result: pass

### 8. Voice Capture End-to-End
expected: Tap Voice, record a short message, submit. Transcription step followed by classification. The transcribed text and classification result appear. Item shows in Inbox.
result: pass

### 9. OTel Traces in Application Insights
expected: After performing a few captures, go to Application Insights and query traces. You should see per-classification spans with attributes like bucket, confidence, and token usage metrics.
result: pass

### 10. Title Display for Captured Items
expected: Items in the Inbox show a meaningful preview — either the agent-assigned title or the raw text of the capture. No items should display "Untitled".
result: pass

## Summary

total: 10
passed: 8
issues: 2
pending: 0
skipped: 0

## Gaps

- truth: "Follow-up reclassification cleans up the original misunderstood item, leaving only the clarified version"
  status: failed
  reason: "User reported: does not clean up the original junk note. After clarifying via text, the original misunderstood note remains in the inbox alongside the newly filed clarified item — two items instead of one."
  severity: major
  test: 3
  root_cause: "Two interacting bugs: (1) tool_result from file_capture is never populated in SSE events — Foundry streaming API doesn't propagate function_result content blocks back through the stream, so inboxItemId in all SSE events is always empty string. (2) The post-hoc reconciliation fallback in _stream_with_reconciliation fails silently — ContainerProxy.read_item returns Call status: false (visible in App Insights trace), and the broad except Exception handler swallows the error. The file_capture tool always creates a NEW inbox doc during follow-up instead of updating the existing misunderstood doc in-place."
  artifacts:
    - path: "backend/src/second_brain/streaming/adapter.py"
      issue: "_emit_result_event uses tool_result or detected_tool_args to get item_id, but tool_result is always None and detected_tool_args has no item_id field"
    - path: "backend/src/second_brain/api/capture.py"
      issue: "_stream_with_reconciliation fallback query and Cosmos read_item fails silently (Call status: false in App Insights trace)"
    - path: "backend/src/second_brain/tools/classification.py"
      issue: "file_capture always creates a NEW inbox doc with new UUID during follow-up instead of updating existing misunderstood doc"
  missing:
    - "Redesign follow-up so file_capture updates the existing misunderstood doc in-place instead of creating an orphan"
    - "Pass original_inbox_item_id into file_capture tool context so it can UPDATE instead of CREATE"
    - "Eliminate post-hoc reconciliation entirely — no orphan means no reconciliation needed"
  debug_session: ".planning/debug/followup-orphan-not-reconciled.md"

- truth: "Voice follow-up reclassification cleans up the original misunderstood item, leaving only the clarified version"
  status: failed
  reason: "User reported: same as voice version - after clarifying the misunderstood comment, it filed it under Admin but the original misunderstood note was never cleaned up and it was actually filed under the same bucket. So now two things instead of one clarified thing."
  severity: major
  test: 4
  root_cause: "Same root cause as Gap 1 — file_capture creates a new orphan doc during voice follow-up, and reconciliation fails silently."
  artifacts:
    - path: "backend/src/second_brain/api/capture.py"
      issue: "Same _stream_with_reconciliation failure applies to voice follow-up path"
  missing:
    - "Same fix as Gap 1 — update existing doc in-place during follow-up (both text and voice share the same code path)"
  debug_session: ".planning/debug/followup-orphan-not-reconciled.md"
