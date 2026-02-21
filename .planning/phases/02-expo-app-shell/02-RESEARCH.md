# Phase 2: Expo App Shell - Research

**Researched:** 2026-02-21
**Domain:** Expo/React Native mobile app with AG-UI SSE backend connectivity
**Confidence:** HIGH (core stack), MEDIUM (AG-UI client in React Native)

## Summary

Phase 2 builds the Expo mobile app shell: a minimal capture surface with four large buttons (Voice, Photo, Video, Text) where tapping Text opens a TextInput for one-tap thought submission. The app communicates with the Phase 1 FastAPI backend via AG-UI protocol (SSE streaming over HTTP POST).

The Expo ecosystem is mature and well-documented. SDK 53 (stable, released April 2025) is the recommended target -- it includes React Native 0.79, React 19, the New Architecture enabled by default, and critically, `expo/fetch` with native streaming `ReadableStream` support. SDK 54 (stable ~Sep 2025) added RN 0.81 and faster iOS builds. SDK 55 beta dropped Jan 2026 with RN 0.83.1. For a new project today, **use SDK 54** (latest stable with broad compatibility).

The critical technical challenge is consuming AG-UI SSE streams in React Native. The `@ag-ui/client` SDK (v0.0.45) provides `HttpAgent` which uses `fetch` + `ReadableStream` internally -- this works in browsers but React Native's default `fetch` lacks `ReadableStream` support. Two viable approaches exist: (1) use `react-native-sse` (29K weekly downloads, proven, uses XMLHttpRequest) to build a thin custom AG-UI client, or (2) use `expo/fetch` from `expo` package which provides WinterCG-compliant fetch with streaming. The recommended approach is **`react-native-sse`** for Phase 2 because it is battle-tested, has zero native dependencies, and handles SSE parsing natively -- avoiding the need to polyfill or debug `ReadableStream` edge cases.

**Primary recommendation:** Use Expo SDK 54 with `expo-router` (file-based routing), `react-native-sse` for AG-UI SSE consumption, and `expo-secure-store` for API key storage. Keep the app structure minimal -- this is a capture surface, not a content browser.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CAPT-01 | User can type a thought in the Expo app and submit it with one tap | TextInput + Pressable submit button. SSE client sends POST to `/api/ag-ui` with message, streams response. `react-native-sse` handles the AG-UI event stream. |
| CAPT-05 | Expo app runs on both iOS and Android | Expo SDK 54 with `create-expo-app` generates cross-platform project. `react-native-sse` uses XMLHttpRequest (no native modules). `expo-secure-store` works on both platforms. |
| APPX-01 | Main screen shows four large capture buttons (Voice, Photo, Video, Text) -- no settings, folders, or tags visible | Single `index.tsx` route with four `Pressable` components. No tab navigation, no drawer, no settings screen. Voice/Photo/Video buttons are placeholder-only for Phase 2. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `expo` | ~54.0.0 | Framework and runtime | Latest stable SDK, includes `expo/fetch` streaming, New Architecture default |
| `expo-router` | ~4.0.0 (bundled with SDK 54) | File-based navigation | 67% adoption in new Expo projects (2025 survey), built on React Navigation, typed routes |
| `react-native` | 0.81.x (bundled with SDK 54) | Core framework | Bundled with Expo SDK 54, New Architecture only |
| `react` | 19.1.x (bundled with SDK 54) | UI library | Bundled with Expo SDK 54 |
| `typescript` | ~5.3+ | Type safety | Default in `create-expo-app`, first-class Expo support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `react-native-sse` | ^1.2.1 | SSE EventSource for React Native | Consuming AG-UI SSE event streams from backend. Uses XMLHttpRequest internally, zero native deps. |
| `expo-secure-store` | ~14.2.x (bundled with SDK 54) | Encrypted key-value storage | Storing API key on-device. Uses Keychain (iOS) and Keystore (Android). 2048 byte value limit. |
| `expo-haptics` | ~14.x (bundled with SDK 54) | Haptic feedback | Tactile confirmation on button press (capture submitted). |
| `@ag-ui/core` | ^0.0.45 | AG-UI type definitions | TypeScript types for AG-UI events (RunStartedEvent, TextMessageContentEvent, etc.) for type-safe SSE parsing. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `react-native-sse` | `@ag-ui/client` HttpAgent + `expo/fetch` polyfill | HttpAgent expects browser-native `ReadableStream`. `expo/fetch` provides this but had streaming bugs in SDK 53 (issue #37310, fixed). More moving parts, less battle-tested on mobile. Could revisit when AG-UI ships React Native client (issue #510). |
| `react-native-sse` | `expo/fetch` + manual SSE parsing | Expo's WinterCG fetch streams chunks correctly in SDK 54, but you must manually parse SSE `data:` lines. `react-native-sse` does this for you. |
| `react-native-sse` | `react-native-fetch-api` + polyfills | The old polyfill approach (pre-SDK 53). Requires 4+ polyfill packages. `expo/fetch` made this obsolete. |
| `expo-secure-store` | `@react-native-async-storage/async-storage` | AsyncStorage is NOT encrypted. API keys must use SecureStore. |

### Installation
```bash
# Create project
npx create-expo-app@latest second-brain-app --template blank-typescript

# Install dependencies
npx expo install expo-secure-store expo-haptics
npm install react-native-sse @ag-ui/core
```

> **Note:** Use `blank-typescript` template, NOT the `default` template. The default template includes tab navigation boilerplate and example screens that would need to be deleted. `blank-typescript` gives a clean starting point.

## Architecture Patterns

### Recommended Project Structure
```
second-brain-app/
├── app/                        # Expo Router routes (screens)
│   ├── _layout.tsx             # Root layout (providers, splash screen)
│   ├── index.tsx               # Main capture screen (4 buttons)
│   └── capture/
│       └── text.tsx            # Text capture screen (TextInput + submit)
├── components/                 # Reusable UI components
│   ├── CaptureButton.tsx       # Large capture button component
│   └── ResponseStream.tsx      # AG-UI response display component
├── lib/                        # Business logic and services
│   ├── ag-ui-client.ts         # SSE client for AG-UI backend
│   ├── auth.ts                 # SecureStore API key management
│   └── types.ts                # Shared TypeScript types
├── constants/                  # App-wide constants
│   └── config.ts               # API URL, userId, etc.
├── app.json                    # Expo configuration
├── tsconfig.json               # TypeScript configuration
└── package.json
```

### Pattern 1: SSE Client with `react-native-sse`
**What:** A thin wrapper around `react-native-sse` that sends AG-UI protocol requests and parses streamed events.
**When to use:** Every time the app sends a capture to the backend.
**Why not use `@ag-ui/client` directly:** The `HttpAgent` uses `fetch` + `ReadableStream` internally, which is browser-oriented. React Native's default `fetch` does not support `ReadableStream`. While `expo/fetch` does, `react-native-sse` is simpler and more reliable for this use case.

**Example:**
```typescript
// lib/ag-ui-client.ts
import EventSource from "react-native-sse";

// AG-UI event types from the backend (SSE format):
// event: RUN_STARTED\ndata: {...}\n\n
// event: TEXT_MESSAGE_CONTENT\ndata: {"delta": "Hello"}\n\n
// event: RUN_FINISHED\ndata: {...}\n\n

type AGUIEventType =
  | "RUN_STARTED"
  | "TEXT_MESSAGE_START"
  | "TEXT_MESSAGE_CONTENT"
  | "TEXT_MESSAGE_END"
  | "RUN_FINISHED";

interface SendCaptureOptions {
  message: string;
  apiKey: string;
  onDelta: (text: string) => void;
  onComplete: () => void;
  onError: (error: string) => void;
}

const API_URL = "http://localhost:8003/api/ag-ui"; // dev default

export function sendCapture({
  message,
  apiKey,
  onDelta,
  onComplete,
  onError,
}: SendCaptureOptions): () => void {
  const es = new EventSource(API_URL, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    method: "POST",
    body: JSON.stringify({
      messages: [
        {
          id: `msg-${Date.now()}`,
          role: "user",
          content: message,
        },
      ],
      thread_id: `thread-${Date.now()}`,
      run_id: `run-${Date.now()}`,
    }),
    pollingInterval: 0, // Disable reconnection for one-shot requests
  });

  es.addEventListener("TEXT_MESSAGE_CONTENT", (event) => {
    if (event.data) {
      try {
        const parsed = JSON.parse(event.data);
        if (parsed.delta) {
          onDelta(parsed.delta);
        }
      } catch {
        // Skip unparseable events
      }
    }
  });

  es.addEventListener("RUN_FINISHED", () => {
    onComplete();
    es.close();
  });

  es.addEventListener("error", (event) => {
    onError(event.message || "Connection error");
    es.close();
  });

  // Return cleanup function
  return () => {
    es.removeAllEventListeners();
    es.close();
  };
}
```

### Pattern 2: Secure API Key Storage
**What:** Store and retrieve the API key using `expo-secure-store`.
**When to use:** App initialization (check for stored key) and first-run setup.

**Example:**
```typescript
// lib/auth.ts
import * as SecureStore from "expo-secure-store";

const API_KEY_STORE_KEY = "second-brain-api-key";

export async function getApiKey(): Promise<string | null> {
  return await SecureStore.getItemAsync(API_KEY_STORE_KEY);
}

export async function setApiKey(key: string): Promise<void> {
  await SecureStore.setItemAsync(API_KEY_STORE_KEY, key);
}

export async function hasApiKey(): Promise<boolean> {
  const key = await SecureStore.getItemAsync(API_KEY_STORE_KEY);
  return key !== null;
}
```

### Pattern 3: Root Layout with Providers
**What:** The `_layout.tsx` root layout handles splash screen and any global providers.
**When to use:** Every Expo Router project needs a root layout.

**Example:**
```typescript
// app/_layout.tsx
import { Stack } from "expo-router";

export default function RootLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen
        name="capture/text"
        options={{
          presentation: "modal",
          headerShown: true,
          headerTitle: "Capture Thought",
        }}
      />
    </Stack>
  );
}
```

### Pattern 4: Large Capture Button Component
**What:** Reusable Pressable with icon, label, and haptic feedback.
**When to use:** Main screen's four capture buttons.

**Example:**
```typescript
// components/CaptureButton.tsx
import { Pressable, Text, StyleSheet, View } from "react-native";
import * as Haptics from "expo-haptics";

interface CaptureButtonProps {
  label: string;
  icon: string; // emoji or icon name
  onPress: () => void;
  disabled?: boolean;
}

export function CaptureButton({ label, icon, onPress, disabled }: CaptureButtonProps) {
  const handlePress = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onPress();
  };

  return (
    <Pressable
      onPress={handlePress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        pressed && styles.pressed,
        disabled && styles.disabled,
      ]}
    >
      <Text style={styles.icon}>{icon}</Text>
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    flex: 1,
    aspectRatio: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#1a1a2e",
    borderRadius: 16,
    margin: 8,
    minHeight: 140,
  },
  pressed: {
    opacity: 0.7,
    transform: [{ scale: 0.96 }],
  },
  disabled: {
    opacity: 0.4,
  },
  icon: {
    fontSize: 40,
    marginBottom: 8,
  },
  label: {
    fontSize: 18,
    fontWeight: "600",
    color: "#ffffff",
  },
});
```

### Anti-Patterns to Avoid
- **Using `@ag-ui/client` HttpAgent directly in React Native:** It relies on browser `fetch` + `ReadableStream`. Will fail silently or throw on React Native's default fetch. Use `react-native-sse` instead.
- **Using `AsyncStorage` for API keys:** Not encrypted. Always use `expo-secure-store` for secrets.
- **Building tab navigation for Phase 2:** The app is a capture surface, not a content browser. One screen with four buttons. No tabs, no drawer, no settings.
- **Using `TouchableOpacity` instead of `Pressable`:** `Pressable` is the modern replacement. `TouchableOpacity` is semi-deprecated and less flexible.
- **Putting business logic in `app/` directory:** Expo Router treats everything in `app/` as a route. Components, hooks, and services go in separate top-level directories.
- **Polling interval > 0 with `react-native-sse`:** For one-shot AG-UI requests, set `pollingInterval: 0` to prevent auto-reconnection after the stream ends.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE parsing in React Native | Custom fetch + manual line parsing | `react-native-sse` | Handles reconnection, custom events, error recovery, TypeScript generics. 29K weekly downloads. |
| Encrypted storage | Custom encryption + AsyncStorage | `expo-secure-store` | Uses OS-level Keychain (iOS) / Keystore (Android). Audited, maintained by Expo team. |
| File-based routing | Manual React Navigation setup | `expo-router` | Automatic deep linking, typed routes, layout nesting. Reduces navigation boilerplate by ~70%. |
| Haptic feedback | Native module bridging | `expo-haptics` | Cross-platform API, works in Expo Go, zero config. |
| SSE event type definitions | Manual interface definitions | `@ag-ui/core` types | Official AG-UI TypeScript types for all event kinds. Stays in sync with protocol spec. |

**Key insight:** The Expo ecosystem provides first-party solutions for almost every concern in this phase. The one gap is SSE consumption in React Native, which `react-native-sse` fills reliably. Do not attempt to make `@ag-ui/client`'s `HttpAgent` work in React Native -- wait for the official React Native client (issue #510).

## Common Pitfalls

### Pitfall 1: `@ag-ui/client` HttpAgent fails silently in React Native
**What goes wrong:** `HttpAgent` uses `fetch()` with `Accept: text/event-stream` and reads `response.body` as a `ReadableStream`. React Native's default `fetch` does not return a `ReadableStream` body -- it returns `null`.
**Why it happens:** The AG-UI client SDK was designed for web browsers and Node.js. There is no official React Native client yet (GitHub issue #510, Oct 2025, labeled "Roadmap").
**How to avoid:** Use `react-native-sse` which uses `XMLHttpRequest` internally -- fully supported in React Native. Build a thin wrapper (see Code Examples).
**Warning signs:** `response.body` is `null`, no events received, silent failure with no error.

### Pitfall 2: `expo/fetch` streaming chunk batching (SDK 53)
**What goes wrong:** `expo/fetch` batches all SSE chunks and delivers them at once when the stream closes, rather than streaming incrementally.
**Why it happens:** Bug in SDK 53's native fetch implementation (GitHub issue #37310, fixed in later patches).
**How to avoid:** Use SDK 54 if relying on `expo/fetch` streaming. Or better, use `react-native-sse` which avoids this entirely by using XMLHttpRequest.
**Warning signs:** Response text appears all at once after a delay instead of streaming token by token.

### Pitfall 3: `react-native-sse` reconnection on one-shot requests
**What goes wrong:** After the AG-UI stream ends (RUN_FINISHED), `react-native-sse` automatically reconnects and sends the same request again, creating duplicate captures.
**Why it happens:** Default `pollingInterval` is 5000ms (5 seconds). SSE spec says clients should reconnect on close.
**How to avoid:** Set `pollingInterval: 0` in EventSource options to disable auto-reconnection. Call `es.close()` in the `RUN_FINISHED` handler.
**Warning signs:** Duplicate "Filed to Inbox" confirmations, backend logs show repeated POST requests.

### Pitfall 4: Placing non-route files in the `app/` directory
**What goes wrong:** Expo Router tries to treat utility files, hooks, or components as routes, causing build warnings or runtime errors.
**Why it happens:** Expo Router convention: every file in `app/` is a route (except `_layout.tsx`).
**How to avoid:** Put components in `components/`, services in `lib/`, hooks in `hooks/`. Only route screens go in `app/`.
**Warning signs:** "Found a route that is not a valid route" warnings, unexpected screens in navigation.

### Pitfall 5: SecureStore 2048-byte value limit
**What goes wrong:** Storing long tokens or data fails silently or throws.
**Why it happens:** `expo-secure-store` has a hard 2048-byte limit per value.
**How to avoid:** API keys are typically well under 2048 bytes. If storing longer data, split across multiple keys or use a different storage mechanism.
**Warning signs:** `setItemAsync` fails, stored value comes back as `null`.

### Pitfall 6: Missing `polyfillGlobal` for `ReadableStream` (if using `expo/fetch` path)
**What goes wrong:** Code that depends on `ReadableStream` throws `ReferenceError: Property 'ReadableStream' doesn't exist`.
**Why it happens:** React Native's Hermes engine does not include `ReadableStream` in its global scope. `expo/fetch` provides its own implementation but only when imported from `expo/fetch`.
**How to avoid:** Use `import { fetch } from 'expo/fetch'` explicitly -- do NOT rely on global `fetch`. Or use `react-native-sse` to sidestep the issue entirely.
**Warning signs:** `ReferenceError` on `ReadableStream`, crashes on app startup.

## Code Examples

### Main Capture Screen (index.tsx)
```typescript
// app/index.tsx
import { View, StyleSheet, SafeAreaView } from "react-native";
import { router } from "expo-router";
import { CaptureButton } from "../components/CaptureButton";

export default function CaptureScreen() {
  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.grid}>
        <CaptureButton
          label="Voice"
          icon="🎙️"
          onPress={() => {/* Phase 5 */}}
          disabled
        />
        <CaptureButton
          label="Photo"
          icon="📷"
          onPress={() => {/* Phase 5+ */}}
          disabled
        />
        <CaptureButton
          label="Video"
          icon="🎥"
          onPress={() => {/* Phase 5+ */}}
          disabled
        />
        <CaptureButton
          label="Text"
          icon="💬"
          onPress={() => router.push("/capture/text")}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
  },
  grid: {
    flex: 1,
    flexDirection: "row",
    flexWrap: "wrap",
    padding: 16,
    justifyContent: "center",
    alignContent: "center",
  },
});
```

### Text Capture Screen
```typescript
// app/capture/text.tsx
import { useState, useCallback } from "react";
import {
  View,
  TextInput,
  Pressable,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import * as Haptics from "expo-haptics";
import { router } from "expo-router";
import { sendCapture } from "../../lib/ag-ui-client";
import { getApiKey } from "../../lib/auth";

export default function TextCaptureScreen() {
  const [thought, setThought] = useState("");
  const [response, setResponse] = useState("");
  const [sending, setSending] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (!thought.trim() || sending) return;

    const apiKey = await getApiKey();
    if (!apiKey) {
      setResponse("No API key configured");
      return;
    }

    setSending(true);
    setResponse("");
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    sendCapture({
      message: thought.trim(),
      apiKey,
      onDelta: (delta) => setResponse((prev) => prev + delta),
      onComplete: () => {
        setSending(false);
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        // Optionally navigate back after a delay
      },
      onError: (error) => {
        setResponse(`Error: ${error}`);
        setSending(false);
      },
    });
  }, [thought, sending]);

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <TextInput
        style={styles.input}
        value={thought}
        onChangeText={setThought}
        placeholder="What's on your mind?"
        placeholderTextColor="#666"
        multiline
        autoFocus
        textAlignVertical="top"
      />
      {response ? <Text style={styles.response}>{response}</Text> : null}
      <Pressable
        onPress={handleSubmit}
        disabled={!thought.trim() || sending}
        style={({ pressed }) => [
          styles.submitButton,
          pressed && styles.submitPressed,
          (!thought.trim() || sending) && styles.submitDisabled,
        ]}
      >
        <Text style={styles.submitText}>
          {sending ? "Sending..." : "Capture"}
        </Text>
      </Pressable>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
    padding: 16,
  },
  input: {
    flex: 1,
    fontSize: 18,
    color: "#ffffff",
    padding: 12,
    backgroundColor: "#1a1a2e",
    borderRadius: 12,
    marginBottom: 12,
  },
  response: {
    color: "#a0a0b0",
    fontSize: 14,
    padding: 12,
    marginBottom: 12,
  },
  submitButton: {
    backgroundColor: "#4a90d9",
    padding: 16,
    borderRadius: 12,
    alignItems: "center",
  },
  submitPressed: {
    opacity: 0.7,
  },
  submitDisabled: {
    opacity: 0.4,
  },
  submitText: {
    color: "#ffffff",
    fontSize: 18,
    fontWeight: "600",
  },
});
```

### API Key Setup (temporary hardcode for Phase 2)
```typescript
// constants/config.ts
// Phase 2: hardcode for development. Phase 3+ will add proper key entry UI.
export const API_BASE_URL = __DEV__
  ? "http://localhost:8003"
  : "https://your-production-url.azurecontainerapps.io";

export const USER_ID = "will"; // Single-user system per PROJECT.md
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| React Navigation manual config | Expo Router file-based routing | Expo Router v1 (2023), now v4 stable | 67% adoption in new Expo projects. Automatic deep linking, typed routes. |
| `TouchableOpacity` / `TouchableHighlight` | `Pressable` core component | React Native 0.63 (2020) | `Pressable` is the standard. Supports `HitRect`, `PressRect`, style callbacks. |
| Polyfill-heavy streaming (4+ packages) | `expo/fetch` with native `ReadableStream` | Expo SDK 52-53 (2024-2025) | WinterCG-compliant fetch built into Expo. No polyfills needed for streaming. |
| Legacy Architecture (Bridge) | New Architecture (JSI, Fabric, TurboModules) | Default in SDK 53 (Apr 2025), only option in SDK 55 | Better performance, synchronous native calls, smaller bridge overhead. |
| `AsyncStorage` for everything | `expo-secure-store` for secrets, `AsyncStorage` for non-sensitive | Always, but often misused | Encrypted vs unencrypted storage. Security requirement for API keys. |
| Custom SSE parsing | `react-native-sse` library | v1.0 (2021), actively maintained | Handles reconnection, custom events, TypeScript generics, POST body support. |

**Deprecated/outdated:**
- `TouchableOpacity`: Semi-deprecated. Use `Pressable` with style callbacks instead.
- Manual polyfill stack (`react-native-fetch-api` + `web-streams-polyfill` + `@stardazed/streams-text-encoding` + `react-native-fast-encoder`): Replaced by `expo/fetch` in SDK 52+.
- React Native Legacy Architecture: Removed entirely in SDK 55 beta.
- `expo-app-loading`: Replaced by `expo-splash-screen` API.

## Open Questions

1. **AG-UI `react-native-sse` custom event names**
   - What we know: The backend sends SSE events with `event: RUN_STARTED`, `event: TEXT_MESSAGE_CONTENT`, etc. `react-native-sse` supports `addEventListener` for custom event types.
   - What's unclear: Whether `react-native-sse`'s custom event listener matches on the SSE `event:` field directly. The docs show custom events working, but AG-UI uses uppercase event names which is uncommon.
   - Recommendation: Test during implementation. If custom events don't work, fall back to listening on `"message"` and parsing the `event` field from the data payload.

2. **AG-UI request format compatibility with `react-native-sse`**
   - What we know: AG-UI expects `POST` with JSON body. `react-native-sse` supports `method: "POST"` and `body` options.
   - What's unclear: Whether `react-native-sse`'s POST + body produces correct SSE streaming behavior with the `agent_framework_ag_ui` endpoint. The library was designed for GET-based SSE but supports POST.
   - Recommendation: Validate early in implementation. If POST SSE doesn't work with `react-native-sse`, fall back to `expo/fetch` with manual SSE line parsing.

3. **Expo Go vs Development Build for testing**
   - What we know: `expo-secure-store` works in Expo Go (with caveats around Face ID). `react-native-sse` has no native modules.
   - What's unclear: Whether all pieces work together in Expo Go or if a development build is needed.
   - Recommendation: Start with Expo Go for speed. Switch to development build only if blocked.

## Sources

### Primary (HIGH confidence)
- Expo SDK 53 changelog (expo.dev/changelog/sdk-53) - New Architecture default, React 19, RN 0.79
- Expo SDK 54 beta announcement (expo.dev/changelog/sdk-54-beta) - RN 0.81, precompiled XCFrameworks
- Expo SDK 55 beta Reddit post (r/expo, Jan 2026) - RN 0.83.1, legacy architecture removed
- Expo Router core concepts (docs.expo.dev/router/basics/core-concepts) - File-based routing rules
- Expo SecureStore docs v53 (docs.expo.dev/versions/v53.0.0/sdk/securestore) - API reference, 2048 byte limit
- `expo/fetch` docs (docs.expo.dev/versions/latest/sdk/expo) - WinterCG-compliant streaming fetch
- `react-native-sse` npm (npmjs.com/package/react-native-sse) - v1.2.1, 29K weekly downloads, TypeScript, POST support
- `@ag-ui/client` npm (npmjs.com/package/@ag-ui/client) - v0.0.45, 245K weekly downloads, HttpAgent docs
- AG-UI client SDK docs (docs.ag-ui.com/sdk/js/client/overview) - HttpAgent, AbstractAgent, middleware
- AG-UI HttpAgent docs (docs.ag-ui.com/sdk/js/client/http-agent) - Uses `fetch` with `Accept: text/event-stream`, `ReadableStream`

### Secondary (MEDIUM confidence)
- AG-UI React Native client issue #510 (github.com/ag-ui-protocol/ag-ui/issues/510) - Labeled "Roadmap", "help wanted", still open
- AG-UI SSE spec bug #771 (github.com/ag-ui-protocol/ag-ui/issues/771) - `data:` vs `data: ` parsing, fixed in #772
- Expo SDK 53 fetch streaming bug #37310 (github.com/expo/expo/issues/37310) - Batch delivery bug, closed/fixed
- `create-expo-app` docs (docs.expo.dev/more/create-expo) - Template options: default, blank, blank-typescript
- Expo Router v4 production patterns (latestfromtechguy.com) - 850K weekly npm downloads

### Tertiary (LOW confidence)
- React Native streaming gist by @aretrace - Polyfill approach (pre-SDK 53), informative but outdated
- Expo Reddit timeout discussion (r/expo, Aug 2025) - `expo/fetch` 60-second timeout on stalled streams, fixed in SDK 53 patch

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Expo SDK, expo-router, expo-secure-store are well-documented first-party tools with clear versioning
- Architecture: HIGH - File-based routing pattern is official Expo recommendation, project structure follows Expo docs
- SSE/AG-UI connectivity: MEDIUM - `react-native-sse` with POST is well-documented but AG-UI custom event names need validation during implementation
- Pitfalls: HIGH - All pitfalls verified with official sources (GitHub issues, docs)

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (30 days - Expo ecosystem is stable, AG-UI is fast-moving)
