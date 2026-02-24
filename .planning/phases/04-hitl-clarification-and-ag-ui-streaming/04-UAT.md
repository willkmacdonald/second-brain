---
status: resolved
phase: 04-hitl-clarification-and-ag-ui-streaming
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md]
started: 2026-02-23T15:55:00Z
updated: 2026-02-24T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Tab Navigation
expected: Opening the app shows two bottom tabs: "Capture" (selected by default) and "Inbox". Tapping Inbox switches to the inbox screen, tapping Capture switches back.
result: pass

### 2. Step Dots During Text Capture
expected: After typing a thought and tapping Send on the text capture screen, horizontal step indicator pills appear showing the agent chain processing (e.g., Orchestrator, Classifier). Pills light up in sequence as each agent starts and finishes.
result: pass

### 3. Streaming Classification Result
expected: After submitting a clear text capture (e.g., "Buy groceries tomorrow"), the classification result streams in word-by-word below the step dots (e.g., "Filed -> Admin (0.92)").
result: pass

### 4. Auto-Reset After High-Confidence Capture
expected: After a successful high-confidence classification, the capture screen resets automatically after ~2.5 seconds — input clears, step dots disappear, ready for next capture.
result: pass

### 5. Low-Confidence HITL on Capture Screen
expected: Submitting an ambiguous capture (e.g., "Had coffee with Mike, he mentioned a new project idea") triggers a clarifying question below the step dots — NOT a generic question, but something specific like "I'm torn between People (0.55) and Ideas (0.42)..." with 4 bucket buttons. The top 2 suggested buckets should be visually prominent (filled blue buttons) while the other 2 are subdued (outline style).
result: issue
reported: "did not trigger a clarifying question"
severity: major

### 6. HITL Resolution from Capture Screen
expected: Tapping one of the bucket buttons on the capture screen files the capture to that bucket. A confirmation appears (e.g., "Filed -> People (0.85)") and the screen resets for next capture.
result: skipped
reason: Blocked by Test 5 failure — HITL clarification never triggered on capture screen

### 7. Inbox List View
expected: Switching to the Inbox tab shows a list of recent captures. Each item shows the text preview, bucket label, and relative timestamp (e.g., "2 min ago"). Pending (unresolved) items show an orange dot indicator.
result: pass

### 8. Inbox Badge Count
expected: When there are pending clarification items, the Inbox tab shows a badge count (number) on the tab icon.
result: pass

### 9. Inbox Detail Card
expected: Tapping a filed (non-pending) inbox item opens a modal overlay showing full text, bucket, confidence score, agent chain, and timestamp. Tapping outside or closing dismisses the modal.
result: pass

### 10. Conversation Screen from Inbox
expected: Tapping a pending (orange dot) inbox item navigates to a conversation screen showing the original capture text, the classifier's real reasoning/question (not a generic "Which bucket?" question), and 4 bucket buttons with top-2 emphasis.
result: pass

### 11. HITL Resolution from Conversation Screen
expected: Selecting a bucket on the conversation screen files the capture, and navigating back to inbox shows the item is now filed (no more orange dot).
result: issue
reported: "Can select tab, it says its filing it, but it remains pending. Also getting an error on the screen (not sure if related) - 'encountered two children with the same key'. Oddly it looks like items created when I was running local have been carried over to the Cosmos DB environment. This suggests to me that we may be still running locally"
severity: major

### 12. Pull-to-Refresh Inbox
expected: Pulling down on the inbox list triggers a refresh, showing updated items.
result: pass

## Summary

total: 12
passed: 8
issues: 2
pending: 0
skipped: 1

## Gaps

- truth: "Ambiguous capture triggers HITL clarifying question on capture screen"
  status: resolved
  reason: "User reported: did not trigger a clarifying question"
  severity: major
  test: 5
  root_cause: "Classifier is in autonomous mode with prompt 'Classify this text and file it.' When request_clarification is called (low confidence), HandoffAgentExecutor sees no handoff, sees autonomous=on, injects the autonomous prompt as synthetic user message, and re-runs the Classifier — which then calls classify_and_file instead, bypassing HITL."
  artifacts:
    - path: "backend/src/second_brain/agents/workflow.py"
      issue: "_create_workflow() line 97-103 puts Classifier in autonomous mode agents list"
  missing:
    - "Remove classifier from with_autonomous_mode agents list — only orchestrator should be autonomous"
    - "Remove classifier autonomous prompt from prompts dict"
  debug_session: ".planning/debug/hitl-not-triggering.md"

- truth: "Selecting a bucket on conversation screen files the capture and removes pending status"
  status: resolved
  reason: "User reported: Can select tab, it says its filing it, but it remains pending. Also getting an error on the screen - 'encountered two children with the same key'. Items from local dev appear in Cosmos DB environment, suggesting app may still be running locally"
  severity: major
  test: 11
  root_cause: "useCallback closure bug in conversation screen: handleBucketSelect memoized with [threadId, isResolving] but references item?.id which is null on initial render. item is not in dependency array, so the stale closure always sends inboxItemId=null. Backend respond endpoint guard 'if body.inbox_item_id and cosmos_manager' skips all DB ops but still emits success text."
  artifacts:
    - path: "mobile/app/conversation/[threadId].tsx"
      issue: "useCallback missing item in dependency array (line 99) — item?.id always null"
    - path: "backend/src/second_brain/main.py"
      issue: "Respond endpoint skips DB ops when inbox_item_id is None (line 351), bare except swallows errors (line 414)"
    - path: "mobile/app/(tabs)/inbox.tsx"
      issue: "No useFocusEffect to auto-refresh on navigation back"
  missing:
    - "Add item to useCallback dependency array in conversation screen"
    - "Backend respond endpoint should return error when inbox_item_id is missing"
    - "Replace bare except with proper error reporting via SSE RUN_ERROR"
    - "Add useFocusEffect to inbox screen for auto-refresh on focus"
    - "Deduplicate items by ID in handleLoadMore to fix duplicate key warning"
  debug_session: ".planning/debug/filing-remains-pending.md"
