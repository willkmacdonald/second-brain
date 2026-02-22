# Phase 4: HITL Clarification and AG-UI Streaming - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform fire-and-forget captures into a real-time interactive experience. Will sees agents working in real time (Orchestrator -> Classifier step progression) and can respond to clarification questions when the classifier is unsure (confidence < 0.6). Adds an Inbox view for capture history and a conversation screen for pending clarifications accessed from inbox. Voice capture, action sharpening, and search are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Real-time processing feedback
- Step dots (horizontal pills) showing Orchestrator -> Classifier, each lights up as it activates (progress stepper pattern)
- Step dots appear below the text input on the capture screen — no modal or overlay
- Streamed text response appears live word-by-word as the agent generates it (ChatGPT typing effect)
- After successful classification, result auto-resets after 2-3 seconds — input clears, ready for next capture

### Clarification conversation
- Clarification question appears inline below the step dots on the capture screen — no automatic navigation away
- Quick-tap bucket buttons for resolution (not open-ended text input)
- Show all 4 bucket buttons (People / Projects / Ideas / Admin) so user can override completely
- Agent's question text displayed above the buttons for context (e.g., "Is this about Mike or about moving?")
- Just bucket names on buttons — no confidence scores shown
- Tapping a bucket button files immediately — no confirmation step
- Classifier can ask up to 2 clarification exchanges before must-file with best guess
- If user ignores clarification and submits a new capture: pending item stays in inbox for later resolution

### Inbox view
- Each item shows: text preview, bucket, relative time (e.g., "2 min ago")
- Pending clarification items have a colored accent/badge (e.g., orange dot) to stand out from filed items
- Tapping a filed item opens a detail card (full text, bucket, confidence, agent chain, timestamp)
- Tapping a pending item navigates to a conversation screen for that thread
- Show last 20 captures, pull up to load more older batches
- Pull-to-refresh for latest data

### Navigation and screen flow
- Bottom tab bar with Capture and Inbox tabs — always one tap away
- Capture tab is the default when opening the app (primary action)
- Keep the existing 4 large capture buttons (Voice, Photo, Video, Text) on the capture screen — tabs added below
- Conversation screen for pending clarifications pushes from inbox (stack navigation on top of tabs)
- After filing from conversation screen, navigate back to inbox (item now shows as filed)
- Inbox tab shows a badge count for pending clarifications
- Inbox syncs immediately when a capture triggers clarification — if user switches to inbox tab, pending item already visible

### Claude's Discretion
- Step dot visual design (colors, sizes, animation style)
- Exact auto-reset timing within 2-3 second range
- Detail card layout and styling
- Loading states and error handling
- Badge color and style for pending items
- How to handle the echo bug filter (server-side vs client-side approach)
- Conversation screen layout for clarification from inbox
- React Context vs other state management for syncing capture state to inbox

</decisions>

<specifics>
## Specific Ideas

- Step dots should feel like a progress stepper — each dot lights up sequentially as agents activate
- Clarification flow is designed for speed: see question, tap bucket, done. No typing needed.
- Inline clarification on capture screen keeps you in flow; conversation screen from inbox is for revisiting pending items later
- Badge count on inbox tab creates gentle urgency to resolve pending items without being pushy

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-hitl-clarification-and-ag-ui-streaming*
*Context gathered: 2026-02-22*
