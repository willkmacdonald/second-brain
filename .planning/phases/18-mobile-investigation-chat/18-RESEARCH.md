# Phase 18: Mobile Investigation Chat - Research

**Researched:** 2026-04-12
**Domain:** React Native / Expo chat UI with SSE streaming and markdown rendering
**Confidence:** HIGH

## Summary

Phase 18 adds a conversational investigation chat and health dashboard to the existing Expo mobile app. The backend `/api/investigate` endpoint already exists and streams SSE events (`thinking`, `tool_call`, `tool_error`, `text`, `error`, `done`) with thread support for multi-turn conversations. The mobile app already uses `react-native-sse` (v1.2.1) for POST-based SSE streaming in the capture flow (`ag-ui-client.ts`). The primary new work is: (1) a new chat screen with message bubbles and markdown rendering, (2) a new SSE client adapter for the investigation endpoint's different event types, (3) dashboard cards on the Status screen, and (4) quick action chips.

The codebase is well-structured with clear patterns: Expo Router file-based routing, `react-native-sse` EventSource for streaming, `SafeAreaView` containers with the `#0f0f23` dark theme, and `useFocusEffect` for data refresh. The investigation chat will reuse these patterns directly. The main technical additions are a markdown rendering library (for agent responses containing bold, lists, tables, code blocks) and a new SSE adapter specific to the investigation event protocol.

**Primary recommendation:** Build an investigation-specific SSE client (`lib/investigate-client.ts`) following the same `react-native-sse` EventSource pattern as `ag-ui-client.ts`, add the chat screen as `app/investigate.tsx` (push screen from Status), render markdown in agent bubbles with `react-native-marked`, and add dashboard cards as a `ListHeaderComponent` in the Status screen's `SectionList`.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Chat screen layout:**
- Message bubbles (iMessage-style): user questions right-aligned, agent responses left-aligned
- Agent responses render formatted markdown inside bubbles (bold, lists, tables)
- "Thinking..." indicator while agent works -- no tool call visibility (don't show which tools are being called)
- Conversation starts fresh each time the chat is opened -- no persistence across app sessions. Backend thread exists for follow-ups within a session.

**Dashboard cards:**
- 3 cards at the top of the Status screen (above errands/tasks): capture count, success rate, last error
- Eval scores card deferred to Phase 21 when eval framework exists -- don't show a placeholder
- Data sourced by calling the investigation agent (system_health query), not a separate endpoint
- Cards refresh on screen focus (same pattern as errands polling)

**Quick action chips:**
- Chips appear on the chat screen only, shown when the chat is empty
- 3 chips: "Recent errors", "Today's captures", "System health"
- Tapping a chip sends the query immediately (no pre-fill-then-edit)
- Chips disappear after the first message is sent

**Navigation & entry points:**
- Header icon on the Status screen opens the investigation chat (not a floating action button)
- Chat is a push screen (like conversation/[threadId]), not a modal or bottom sheet
- Header title: "Investigate"
- Header includes a "new chat" icon to reset the conversation without navigating back
- Last-error dashboard card is tappable -- deep-links to chat with a pre-filled query about the most recent error
- Other dashboard cards (capture count, success rate) are display-only
- Text input supports both text and voice (reuse existing voice capture pattern)

### Claude's Discretion

- Bubble color scheme and styling
- Markdown rendering library/approach
- Loading skeleton for dashboard cards while agent responds
- Voice input button placement and interaction pattern
- Exact chip text (the natural-language query sent to the agent)
- Header icon choice (magnifying glass, chat bubble, etc.)

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MOBL-01 | User can open a chat screen from the Status screen to ask investigation questions | Navigation pattern: header icon on Status screen pushes `investigate` screen via Expo Router. Existing pattern from `conversation/[threadId]` push screen. |
| MOBL-02 | Investigation agent streams responses via SSE with "Thinking..." indicator | Reuse `react-native-sse` EventSource with POST. New adapter for investigation event types (`thinking`, `text`, `done`). Hide `tool_call`/`tool_error` events per user decision. |
| MOBL-03 | User can ask follow-up questions in the same conversation thread | Backend already supports `thread_id` parameter on `/api/investigate`. Store `thread_id` from `done` event, pass it on subsequent requests. |
| MOBL-04 | User can tap quick-action chips for common queries (recent errors, today's captures, system health) | 3 chips rendered when messages array is empty. Each sends a pre-defined query string. Chips hidden after first message. Eval results chip deferred per CONTEXT.md. |
| MOBL-05 | User can see at-a-glance health dashboard cards (capture count, success rate, last error) | 3 cards as `ListHeaderComponent` on Status screen. Data fetched via investigation agent `system_health` query on focus. Eval scores card deferred to Phase 21 per CONTEXT.md. |
| MOBL-06 | User can tap a dashboard error card to jump to investigation chat with pre-filled query | Pass initial query as route param to `investigate` screen. Auto-send on mount when param present. |

</phase_requirements>

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| expo-router | ~6.0.23 | File-based routing, push navigation | Already used for all navigation |
| react-native-sse | ^1.2.1 | SSE EventSource with POST support | Already used for capture streaming |
| expo-speech-recognition | ^3.1.1 | On-device voice input | Already used for voice capture |
| react-native-safe-area-context | ~5.6.0 | Safe area handling | Already used on all screens |

### New (to install)
| Library | Version | Purpose | Why This Library |
|---------|---------|---------|------------------|
| react-native-marked | latest (supports RN 0.76+) | Markdown rendering in chat bubbles | Pure JS (no native modules), supports tables/bold/lists/code blocks, uses marked.js parser, customizable themes, actively maintained, compatible with RN 0.81 |
| react-native-svg | (peer dep of react-native-marked) | SVG rendering required by react-native-marked | Peer dependency -- may already be transitively available |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| react-native-marked | @ronradtke/react-native-markdown-display | More established but less actively maintained; uses markdown-it parser; also viable |
| react-native-marked | Custom Text parsing | Would miss table support, code blocks, nested lists -- too much hand-rolling |
| react-native-marked | WebView-based markdown | Poor performance in chat, no native feel, scroll conflicts |

**Installation:**
```bash
npx expo install react-native-marked react-native-svg
```

## Architecture Patterns

### Recommended File Structure
```
mobile/
  app/
    investigate.tsx            # Chat screen (push from Status)
    (tabs)/
      status.tsx               # Modified: add dashboard cards + header icon
  components/
    InvestigateBubble.tsx       # Message bubble (user/agent variants)
    DashboardCards.tsx          # Health dashboard card row
    QuickActionChips.tsx        # Pre-filled query chips
  lib/
    investigate-client.ts      # SSE client for /api/investigate
```

### Pattern 1: Investigation SSE Client
**What:** A dedicated SSE client module for the investigation endpoint, separate from the capture SSE client (`ag-ui-client.ts`).
**Why separate:** The investigation endpoint uses completely different SSE event types (`thinking`, `text`, `tool_call`, `done`) than the capture endpoint (`STEP_START`, `CLASSIFIED`, `COMPLETE`, etc.). Mixing them in one file would create confusion.
**When to use:** All investigation chat requests.
**Example:**
```typescript
// Source: Derived from existing ag-ui-client.ts pattern
import EventSource from "react-native-sse";
import { API_BASE_URL } from "../constants/config";

type InvestigateEventType = "message";

interface InvestigateCallbacks {
  onThinking: () => void;
  onText: (content: string) => void;
  onDone: (threadId: string) => void;
  onError: (message: string) => void;
}

export function sendInvestigation({
  question,
  threadId,
  apiKey,
  callbacks,
}: {
  question: string;
  threadId?: string;
  apiKey: string;
  callbacks: InvestigateCallbacks;
}): { cleanup: () => void } {
  const body: Record<string, string> = { question };
  if (threadId) body.thread_id = threadId;

  const es = new EventSource<InvestigateEventType>(
    `${API_BASE_URL}/api/investigate`,
    {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(body),
      pollingInterval: 0, // CRITICAL: prevents auto-reconnection
    },
  );

  es.addEventListener("message", (event) => {
    if (!event.data) return;
    try {
      const parsed = JSON.parse(event.data);
      switch (parsed.type) {
        case "thinking":
          callbacks.onThinking();
          break;
        case "text":
          callbacks.onText(parsed.content ?? "");
          break;
        case "done":
          callbacks.onDone(parsed.thread_id ?? "");
          es.close();
          break;
        case "error":
          callbacks.onError(parsed.message ?? "Investigation failed");
          es.close();
          break;
        // tool_call, tool_error, rate_warning: silently ignored
        // per user decision -- no tool call visibility
      }
    } catch {
      // Ignore malformed JSON
    }
  });

  es.addEventListener("error", (event) => {
    const msg = "message" in event ? event.message : "Connection error";
    callbacks.onError(msg);
    es.close();
  });

  return {
    cleanup: () => {
      es.removeAllEventListeners();
      es.close();
    },
  };
}
```

### Pattern 2: Chat Screen with Streaming Text Accumulation
**What:** FlatList-based chat UI where agent responses accumulate text as SSE `text` events arrive.
**When to use:** The investigate screen.
**Key details:**
- Messages stored as `{ role: "user" | "agent", content: string, isStreaming?: boolean }[]`
- When a new query is sent, add user message and an empty agent message with `isStreaming: true`
- Each `text` event appends to the current agent message's content
- `done` event sets `isStreaming: false`
- FlatList with `inverted` prop for chat-style bottom-anchored scroll
- `KeyboardAvoidingView` wraps the whole screen for input visibility

```typescript
// Message state shape
interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  isStreaming: boolean;
}
```

### Pattern 3: Dashboard Cards via Investigation Agent
**What:** Cards on Status screen that show system health data, fetched by calling the investigation agent with a `system_health`-type question.
**When to use:** Status screen header.
**Key details:**
- Call `/api/investigate` with question like "Give me a system health summary" on screen focus
- Parse the text response to extract capture count, success rate, last error
- **Important:** The investigation agent returns free-form text, not structured JSON. The dashboard needs to parse key metrics from the text response OR use a structured query approach.
- Alternative: Ask the agent three specific questions and parse each response. This is simpler but slower.
- **Recommended approach:** Send a single health query and parse the structured text response. The investigation agent's `system_health` tool returns formatted data with consistent structure (capture counts, error rates, etc.).

### Pattern 4: Voice Input Reuse
**What:** Reuse the existing `expo-speech-recognition` pattern from the capture screen for voice input in the investigation chat.
**When to use:** Investigation chat voice input.
**Key details:**
- Import `startOnDeviceRecognition`, `stopRecognition`, `requestSpeechPermissions` from `lib/speech.ts`
- Use `useSpeechRecognitionEvent("result", ...)` hook for interim results
- Use `useSpeechRecognitionEvent("end", ...)` hook to submit final text
- Voice button placement: beside the send button in the text input bar

### Anti-Patterns to Avoid
- **Don't reuse `ag-ui-client.ts` for investigation:** The event protocols are completely different (capture uses CLASSIFIED/COMPLETE/MISUNDERSTOOD, investigation uses thinking/text/done). Creating a shared abstraction would be forced and fragile.
- **Don't persist chat messages to AsyncStorage:** User explicitly decided conversations start fresh each time. Backend thread handles context within a session.
- **Don't show tool calls:** User explicitly decided against showing which tools the agent calls. Only show "Thinking..." while the agent works.
- **Don't build a separate health endpoint:** User decided dashboard data comes from the investigation agent, not a new API endpoint.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown rendering | Custom Text parsing with regex | react-native-marked | Tables, nested lists, code blocks, bold/italic are deceptively complex to parse correctly |
| SSE connection management | Raw XMLHttpRequest with manual parsing | react-native-sse EventSource | Already proven in the codebase, handles reconnection, error events, cleanup |
| Keyboard avoidance | Manual keyboard height tracking | React Native `KeyboardAvoidingView` | Platform differences between iOS keyboard behavior are subtle |
| On-device speech recognition | Audio recording + Whisper API | expo-speech-recognition (existing) | Already implemented in lib/speech.ts with permission handling |

**Key insight:** The investigation chat is primarily a UI assembly task -- all the hard backend and streaming infrastructure already exists. The risk is in the UI details (keyboard behavior, scroll anchoring, markdown rendering edge cases), not in the backend integration.

## Common Pitfalls

### Pitfall 1: react-native-sse pollingInterval Default
**What goes wrong:** EventSource auto-reconnects and sends duplicate requests.
**Why it happens:** `react-native-sse` defaults to polling/reconnection. If `pollingInterval` is not set to `0`, the EventSource will reconnect after the stream ends, sending the investigation query again.
**How to avoid:** Always set `pollingInterval: 0` on every EventSource constructor call. This is already done correctly in `ag-ui-client.ts`.
**Warning signs:** Agent answers appearing twice, backend logs showing duplicate investigation queries.

### Pitfall 2: FlatList Inverted Scroll with Streaming
**What goes wrong:** Auto-scroll to bottom doesn't work, or content jumps during streaming.
**Why it happens:** FlatList `inverted` reverses the scroll direction, so "bottom" is visually at the top. When streaming new text into the last message, the list needs to stay anchored at the newest content.
**How to avoid:** Use `inverted={true}` on FlatList and reverse the messages array (newest first). As the agent message grows, FlatList will naturally keep the latest content visible. Avoid manual `scrollToEnd` calls which behave unexpectedly with inverted lists.
**Warning signs:** User sees the top of the agent's response during streaming instead of the latest text.

### Pitfall 3: Empty String Falsy in JS
**What goes wrong:** Guards like `if (parsed.thread_id)` silently drop empty strings.
**Why it happens:** Empty string `""` is falsy in JavaScript. The backend sometimes sends `thread_id: ""` in events.
**How to avoid:** Use explicit null/undefined checks: `parsed.thread_id !== undefined && parsed.thread_id !== null`. This bug was previously encountered in the capture flow (documented in MEMORY.md).
**Warning signs:** Thread continuity breaking -- follow-up questions not maintaining context.

### Pitfall 4: KeyboardAvoidingView Platform Differences
**What goes wrong:** Text input is hidden behind keyboard on one platform but works on another.
**Why it happens:** iOS and Android handle keyboard differently. iOS needs `behavior="padding"`, Android often needs `behavior="height"` or no behavior prop at all.
**How to avoid:** Use `behavior={Platform.OS === "ios" ? "padding" : "height"}` and test on a real device. The `keyboardVerticalOffset` may need adjustment to account for the header height.
**Warning signs:** Input field disappears behind keyboard when user starts typing.

### Pitfall 5: Voice Input Hook Placement
**What goes wrong:** `useSpeechRecognitionEvent` hooks throw "hooks can only be called at top level" errors.
**Why it happens:** The hooks from `expo-speech-recognition` must be called unconditionally at the top level of the component, not inside callbacks or conditionals. The existing capture screen (index.tsx) demonstrates correct placement.
**How to avoid:** Declare all `useSpeechRecognitionEvent` hooks at the top of the component, use refs to communicate between event handlers and component logic.
**Warning signs:** Runtime errors about hook rules.

### Pitfall 6: Dashboard Health Query Parsing
**What goes wrong:** Dashboard cards show raw agent text instead of extracted metrics.
**Why it happens:** The investigation agent returns natural language text, not structured JSON. Parsing metrics from free-form text is fragile.
**How to avoid:** Send a very specific question like "What is the current capture count, success rate, and most recent error? Answer with just the numbers." and parse the structured portions. Alternatively, accept that the dashboard might show "Loading..." briefly while the agent responds, and display a simplified summary. Consider caching the last successful response.
**Warning signs:** Dashboard showing "I'd be happy to help..." instead of "47 captures".

### Pitfall 7: Expo Install vs npm Install
**What goes wrong:** Package version incompatibility with Expo SDK 54.
**Why it happens:** Direct `npm install` may pull versions incompatible with the current Expo SDK.
**How to avoid:** Always use `npx expo install <package>` for Expo projects (documented in MEMORY.md). This ensures SDK-compatible versions.
**Warning signs:** Metro bundler errors, native module version mismatches.

## Code Examples

### Chat Message Bubble with Markdown
```typescript
// Recommended component structure
import Markdown from "react-native-marked";
import { View, Text, StyleSheet } from "react-native";

interface BubbleProps {
  role: "user" | "agent";
  content: string;
  isStreaming: boolean;
}

function InvestigateBubble({ role, content, isStreaming }: BubbleProps) {
  if (role === "user") {
    return (
      <View style={styles.userBubble}>
        <Text style={styles.userText}>{content}</Text>
      </View>
    );
  }

  return (
    <View style={styles.agentBubble}>
      {content ? (
        <Markdown
          value={content}
          flatListProps={null} // Render inline, not in its own FlatList
          theme={{
            colors: {
              text: "#ffffff",
              code: "#e0e0e0",
              link: "#4a90d9",
              border: "#333",
            },
          }}
        />
      ) : isStreaming ? (
        <Text style={styles.thinkingText}>Thinking...</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  userBubble: {
    alignSelf: "flex-end",
    backgroundColor: "#4a90d9",
    borderRadius: 16,
    padding: 12,
    marginVertical: 4,
    marginHorizontal: 16,
    maxWidth: "80%",
  },
  agentBubble: {
    alignSelf: "flex-start",
    backgroundColor: "#1a1a2e",
    borderRadius: 16,
    padding: 12,
    marginVertical: 4,
    marginHorizontal: 16,
    maxWidth: "90%",
  },
  userText: {
    color: "#ffffff",
    fontSize: 16,
    lineHeight: 22,
  },
  thinkingText: {
    color: "#888",
    fontSize: 14,
    fontStyle: "italic",
  },
});
```

### Quick Action Chips
```typescript
// Chips shown when conversation is empty
const QUICK_ACTIONS = [
  { label: "Recent errors", query: "Show me recent errors from the last 24 hours" },
  { label: "Today's captures", query: "How many captures were processed today and what were the results?" },
  { label: "System health", query: "Give me a system health overview" },
];

function QuickActionChips({ onSelect }: { onSelect: (query: string) => void }) {
  return (
    <View style={chipStyles.container}>
      <Text style={chipStyles.hint}>Quick actions</Text>
      <View style={chipStyles.row}>
        {QUICK_ACTIONS.map((action) => (
          <Pressable
            key={action.label}
            style={chipStyles.chip}
            onPress={() => onSelect(action.query)}
          >
            <Text style={chipStyles.chipText}>{action.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}
```

### Status Screen Header with Investigate Icon
```typescript
// In app/(tabs)/status.tsx or tabs layout
// The Status screen currently has headerShown: false in the tab layout.
// Options to add the header icon:
// 1. Enable header on the Status tab and add headerRight
// 2. Add a custom header row inside the Status screen itself

// Option 2 (recommended -- avoids changing tab layout for all screens):
<View style={styles.screenHeader}>
  <Text style={styles.screenTitle}>Status</Text>
  <Pressable onPress={() => router.push("/investigate")}>
    <Text style={styles.headerIcon}>{/* magnifying glass or chat icon */}</Text>
  </Pressable>
</View>
```

### Dashboard Cards Component
```typescript
// Rendered as ListHeaderComponent on the Status SectionList
interface DashboardData {
  captureCount: number | null;
  successRate: number | null;
  lastError: string | null;
  loading: boolean;
}

function DashboardCards({
  data,
  onErrorPress,
}: {
  data: DashboardData;
  onErrorPress: (errorMessage: string) => void;
}) {
  return (
    <View style={dashStyles.container}>
      <View style={dashStyles.card}>
        <Text style={dashStyles.cardLabel}>Captures (24h)</Text>
        <Text style={dashStyles.cardValue}>
          {data.loading ? "..." : data.captureCount ?? "--"}
        </Text>
      </View>
      <View style={dashStyles.card}>
        <Text style={dashStyles.cardLabel}>Success Rate</Text>
        <Text style={dashStyles.cardValue}>
          {data.loading ? "..." : data.successRate != null ? `${data.successRate}%` : "--"}
        </Text>
      </View>
      <Pressable
        style={[dashStyles.card, dashStyles.errorCard]}
        onPress={() => data.lastError && onErrorPress(data.lastError)}
      >
        <Text style={dashStyles.cardLabel}>Last Error</Text>
        <Text style={dashStyles.cardValueError} numberOfLines={2}>
          {data.loading ? "..." : data.lastError ?? "None"}
        </Text>
      </Pressable>
    </View>
  );
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| react-native-markdown-display | react-native-marked or react-native-enriched-markdown | 2025 | Original library unmaintained; newer options have better RN 0.80+ support |
| FlatList chat | FlatList inverted chat | Stable | Inverted FlatList is the standard React Native chat pattern |
| Custom keyboard handling | KeyboardAvoidingView | Stable | Built into React Native core |

**Deprecated/outdated:**
- `react-native-markdown-display` (original by iamacup): Unmaintained for 2+ years. Use `react-native-marked` or `@ronradtke/react-native-markdown-display` fork instead.

## Open Questions

1. **Dashboard data parsing from agent text**
   - What we know: The investigation agent returns free-form text. The `system_health` tool provides structured metrics internally but the agent formats them as natural language.
   - What's unclear: Whether the text output is consistent enough to reliably parse numbers for dashboard cards.
   - Recommendation: Start with a best-effort text parse. If fragile, fall back to showing the last error as a short text snippet and capture count/success rate as "Available in chat". The dashboard is a nice-to-have convenience; the chat screen is the primary interface.

2. **react-native-marked rendering in inverted FlatList**
   - What we know: react-native-marked renders markdown as a component tree. When used inside an inverted FlatList item, scroll behavior should work naturally.
   - What's unclear: Whether react-native-marked's internal FlatList (if it uses one for rendering) conflicts with the outer chat FlatList.
   - Recommendation: Use react-native-marked's `flatListProps={null}` or equivalent prop to disable internal scrolling. Test with a long markdown response containing tables and code blocks.

3. **Streaming markdown rendering**
   - What we know: Agent text arrives in chunks via SSE. The full content grows as chunks arrive.
   - What's unclear: How react-native-marked handles re-rendering with incomplete markdown (e.g., a partial table or unterminated bold).
   - Recommendation: Accept that mid-stream markdown may render imperfectly. The final render after `done` will be correct. This is acceptable UX for streaming chat.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `mobile/lib/ag-ui-client.ts` -- existing SSE pattern with react-native-sse
- Codebase inspection: `backend/src/second_brain/api/investigate.py` -- investigation endpoint contract
- Codebase inspection: `backend/src/second_brain/streaming/investigation_adapter.py` -- SSE event types (thinking, text, tool_call, tool_error, done, error)
- Codebase inspection: `mobile/app/(tabs)/status.tsx` -- Status screen structure (SectionList, useFocusEffect pattern)
- Codebase inspection: `mobile/app/_layout.tsx` -- Root layout with Stack screens
- Codebase inspection: `mobile/lib/speech.ts` -- Voice input pattern

### Secondary (MEDIUM confidence)
- [react-native-marked GitHub](https://github.com/gmsgowtham/react-native-marked) -- RN 0.76+ compatibility confirmed, table/list/code support, react-native-svg peer dependency
- [react-native-sse GitHub](https://github.com/binaryminds/react-native-sse) -- POST support via method option, pollingInterval behavior
- [Expo SDK 54 changelog](https://expo.dev/changelog/sdk-54) -- React Native 0.81 compatibility

### Tertiary (LOW confidence)
- react-native-marked streaming behavior with partial markdown -- needs validation during implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All core libraries already in the project; only react-native-marked is new and verified compatible
- Architecture: HIGH - Patterns directly derived from existing codebase (SSE client, push screens, useFocusEffect)
- Pitfalls: HIGH - Most pitfalls documented from actual project history (pollingInterval, empty string falsy, expo install)
- Dashboard parsing: MEDIUM - Free-form text parsing from agent is inherently uncertain

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (30 days -- stable ecosystem, no fast-moving dependencies)
