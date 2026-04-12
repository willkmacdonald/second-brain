# Phase 18: Mobile Investigation Chat - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Investigation agent is accessible from the phone with a conversational chat interface and at-a-glance health dashboard. Users can type or speak questions, see streamed responses, and get quick answers via action chips. Dashboard cards on the Status screen show system health at a glance. Creating new investigation tools or backend capabilities is out of scope — this phase builds the mobile UI on top of the existing POST /api/investigate endpoint.

</domain>

<decisions>
## Implementation Decisions

### Chat screen layout
- Message bubbles (iMessage-style): user questions right-aligned, agent responses left-aligned
- Agent responses render formatted markdown inside bubbles (bold, lists, tables)
- "Thinking..." indicator while agent works — no tool call visibility (don't show which tools are being called)
- Conversation starts fresh each time the chat is opened — no persistence across app sessions. Backend thread exists for follow-ups within a session.

### Dashboard cards
- 3 cards at the top of the Status screen (above errands/tasks): capture count, success rate, last error
- Eval scores card deferred to Phase 21 when eval framework exists — don't show a placeholder
- Data sourced by calling the investigation agent (system_health query), not a separate endpoint
- Cards refresh on screen focus (same pattern as errands polling)

### Quick action chips
- Chips appear on the chat screen only, shown when the chat is empty
- 3 chips: "Recent errors", "Today's captures", "System health"
- Tapping a chip sends the query immediately (no pre-fill-then-edit)
- Chips disappear after the first message is sent

### Navigation & entry points
- Header icon on the Status screen opens the investigation chat (not a floating action button)
- Chat is a push screen (like conversation/[threadId]), not a modal or bottom sheet
- Header title: "Investigate"
- Header includes a "new chat" icon to reset the conversation without navigating back
- Last-error dashboard card is tappable — deep-links to chat with a pre-filled query about the most recent error
- Other dashboard cards (capture count, success rate) are display-only
- Text input supports both text and voice (reuse existing voice capture pattern)

### Claude's Discretion
- Bubble color scheme and styling
- Markdown rendering library/approach
- Loading skeleton for dashboard cards while agent responds
- Voice input button placement and interaction pattern
- Exact chip text (the natural-language query sent to the agent)
- Header icon choice (magnifying glass, chat bubble, etc.)

</decisions>

<specifics>
## Specific Ideas

- Chat should match the existing dark theme (#0f0f23 background, #ffffff text, #4a90d9 accent)
- Voice input should reuse the on-device speech recognition pattern from the capture screen (expo-speech-recognition)
- Dashboard data comes from the investigation agent's system_health tool — same data the /investigate terminal client can query

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-mobile-investigation-chat*
*Context gathered: 2026-04-12*
