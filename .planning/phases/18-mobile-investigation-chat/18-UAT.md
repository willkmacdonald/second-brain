---
status: resolved
phase: 18-mobile-investigation-chat
source: [18-01-SUMMARY.md, 18-02-SUMMARY.md, 18-03-SUMMARY.md]
started: 2026-04-12T05:00:00Z
updated: 2026-04-13T06:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Open Investigation Chat Screen
expected: Navigate to the investigation chat screen. Screen loads with empty chat area, text input bar at bottom, and 3 quick action chips: "Recent errors", "Today's captures", "System health".
result: pass

### 2. Quick Action Chips
expected: Tap one of the quick action chips (e.g. "Recent errors"). The chip disappears along with the others, a user bubble appears with the chip text, and the agent starts streaming a response with markdown-formatted text appearing progressively in an agent bubble.
result: pass

### 3. Type and Send a Message
expected: Type a question in the input bar (e.g. "What errors happened today?") and send. A user bubble appears with your text, then an agent bubble streams the response with markdown rendering (headers, bold, lists, code blocks).
result: pass

### 4. Streaming Response Display
expected: While the agent is responding, text accumulates progressively in the agent bubble (not all at once). Markdown formatting renders correctly inline as text streams in.
result: pass

### 5. Thread Follow-up
expected: After receiving an agent response, send a follow-up question. The agent's reply is context-aware (references the previous exchange), confirming thread continuity via threadId.
result: pass

### 6. Voice Input
expected: Tap the voice/microphone input. Speak a question. On stopping speech, the transcribed text auto-submits and a user bubble appears with the transcription, followed by a streamed agent response.
result: pass

### 7. New Chat Reset
expected: Tap the "New" button in the header. The chat clears — all messages disappear, quick action chips reappear, and the thread resets (next message starts a fresh conversation).
result: pass

### 8. Dashboard Health Cards on Status Screen
expected: Open the Status screen. Three health metric cards appear near the top: capture count (24h), success rate (%), and errors (24h). Cards show real data or "--" fallback while loading. No errors on navigation.
result: pass (re-verified after 18-03 gap closure)

### 9. Error Card Deep-Link to Investigation Chat
expected: On the Status screen, tap the errors (24h) card. It navigates to the investigation chat screen with a pre-filled query about the error, which auto-sends and the agent provides relevant details about that error.
result: pass (resolved by 18-04 gap closure — prompt now forces both system_health + recent_errors tools)

### 10. Investigate Icon on Status Screen
expected: On the Status screen, there is a magnifying glass icon (🔍) in the header area. Tapping it opens the investigation chat screen.
result: pass

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0

## Gaps

- truth: "Error card deep-link query returns consistent results with the dashboard health summary that surfaced the error"
  status: resolved
  reason: "User reported: Dashboard health summary mentions an error ('count remained consistent at zero'), card displays it, deep-link sends 'Tell me about this recent error: count remained consistent at zero' to agent, but agent responds 'No errors found in the last 24h'. The dashboard and deep-link both query the same investigation agent but get inconsistent answers."
  severity: blocker
  test: 9
  root_cause: "Dashboard card asks agent for a free-text health summary, then regex-parses the response to extract an error string. The agent's health summary mentions something it interprets as an error condition (e.g. from usage patterns or eval results), but it's not an actual error in AppExceptions/AppTraces. When the deep-link re-asks about that specific error text via a different query, the agent searches recent_errors tool which queries AppExceptions — finds nothing — and says 'no errors'. The two queries use different tools/data scopes within the same agent."
  artifacts:
    - path: "mobile/app/(tabs)/status.tsx"
      issue: "Lines 97-144: health summary query uses free-text regex parsing to extract error, fragile and inconsistent with structured error lookup"
    - path: "mobile/app/(tabs)/status.tsx"
      issue: "Line 450: deep-link sends extracted error text as a new query, but agent can't find it because it came from a different tool's output"
  missing:
    - "Dashboard health query and error deep-link must use consistent data — either both use the same structured error data, or the health summary passes through enough context for the deep-link to find the same error"
  debug_session: ""
