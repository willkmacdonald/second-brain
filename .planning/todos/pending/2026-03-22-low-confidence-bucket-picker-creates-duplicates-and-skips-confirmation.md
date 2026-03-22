---
created: 2026-03-22T21:13:28.122Z
title: Low-confidence bucket picker creates duplicates and skips confirmation
area: ui
files:
  - mobile/src/ (capture flow components)
  - backend/src/second_brain/streaming/adapter.py
  - backend/src/second_brain/tools/classification.py
---

## Problem

When the Classifier returns a low-confidence / pending status and the mobile app shows the bucket picker ("Best guess: Ideas. Which bucket?"), selecting a bucket does not show the "filed" confirmation and the app returns to the same capture screen. The user retries, creating duplicate Inbox entries.

Observed behavior:
1. User captures `https://www.example.com` — Classifier returns `status: pending` with best guess "Ideas"
2. User taps "Ideas" from the bucket picker
3. App shows loading indicator briefly, then returns to the same capture screen (no "filed" confirmation)
4. User retries — same result, creating a second duplicate "Pending" entry
5. User selects "People" instead — this time gets confirmation and navigates home

Backend evidence: App Insights confirms the backend successfully files the item (201 on both Inbox and Ideas Cosmos writes) on the first attempt. The SSE stream completes with 200. The issue is in how the mobile app processes the SSE response after a bucket picker selection.

Result: Three Inbox entries for the same URL — two "Pending" (orange dot) from failed Ideas attempts, one "People" from manual recategorization.

## Solution

Investigate the mobile capture flow when handling bucket picker selections:
- Check if the SSE response after a bucket-picker selection uses the same event format the app expects
- The `stream_text_capture` path may emit a different SSE event sequence than what the follow-up/recategorization path expects
- Verify the mobile app's SSE event handler correctly processes CLASSIFIED events that come from bucket picker re-submissions
- May need to use `stream_follow_up_capture` or the recategorize endpoint instead of re-submitting as a new capture
