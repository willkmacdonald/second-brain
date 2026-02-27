import EventSource from "react-native-sse";
import { API_BASE_URL } from "../constants/config";
import type {
  AGUIEventType,
  SendCaptureOptions,
  SendFollowUpOptions,
  SendVoiceCaptureOptions,
  StreamingCallbacks,
} from "./types";

/**
 * Parsed SSE event payload from the AG-UI backend.
 * Fields are optional because different event types carry different data.
 */
interface AGUIEventPayload {
  type?: string;
  delta?: string;
  name?: string;
  stepName?: string;
  message?: string; // For ERROR events
  threadId?: string; // For COMPLETE events
  runId?: string; // For COMPLETE events
  value?: {
    threadId?: string;
    inboxItemId?: string;
    questionText?: string;
    bucket?: string; // For CLASSIFIED
    confidence?: number; // For CLASSIFIED
  };
}

/**
 * Wire up an EventSource to dispatch streaming callbacks.
 *
 * Handles both v2 event types (STEP_START, STEP_END, CLASSIFIED,
 * MISUNDERSTOOD, UNRESOLVED, COMPLETE, ERROR) and legacy v1 types
 * (STEP_STARTED, STEP_FINISHED, TEXT_MESSAGE_CONTENT, CUSTOM,
 * RUN_FINISHED, RUN_ERROR) for backward compatibility during development.
 *
 * Returns a cleanup function to abort the connection.
 */
function attachCallbacks(
  es: EventSource<AGUIEventType>,
  callbacks: StreamingCallbacks,
): () => void {
  let result = "";
  let hitlTriggered = false;

  es.addEventListener("message", (event) => {
    if (!event.data) return;
    try {
      const parsed: AGUIEventPayload = JSON.parse(event.data);

      switch (parsed.type) {
        // --- New v2 events ---
        case "STEP_START":
        case "STEP_STARTED": // legacy compat
          callbacks.onStepStart?.(parsed.stepName ?? "Unknown");
          break;

        case "STEP_END":
        case "STEP_FINISHED": // legacy compat
          callbacks.onStepFinish?.(parsed.stepName ?? "Unknown");
          break;

        case "CLASSIFIED":
          // New v2: CLASSIFIED is top-level, result in value
          if (parsed.value) {
            const bucket = parsed.value.bucket ?? "?";
            const confidence = parsed.value.confidence ?? 0;
            result = `Filed -> ${bucket} (${confidence.toFixed(2)})`;
            callbacks.onComplete(result);
          }
          break;

        case "MISUNDERSTOOD":
          // New v2: MISUNDERSTOOD is top-level
          if (parsed.value?.inboxItemId) {
            hitlTriggered = true;
            callbacks.onMisunderstood?.(
              parsed.value.threadId ?? "",
              parsed.value.questionText ?? "",
              parsed.value.inboxItemId,
            );
          }
          break;

        case "LOW_CONFIDENCE":
          // Low-confidence classification -- show bucket buttons for manual filing
          if (parsed.value) {
            hitlTriggered = true; // Prevents COMPLETE from firing onComplete
            callbacks.onLowConfidence?.(
              parsed.value.inboxItemId ?? "",
              parsed.value.bucket ?? "?",
              parsed.value.confidence ?? 0,
            );
          }
          break;

        case "UNRESOLVED":
          // New v2: UNRESOLVED is top-level
          callbacks.onUnresolved?.(parsed.value?.inboxItemId ?? "");
          break;

        case "COMPLETE":
        case "RUN_FINISHED": // legacy compat
          if (!hitlTriggered) {
            if (parsed.type === "RUN_FINISHED" || !result) {
              // RUN_FINISHED (legacy): always fire onComplete.
              // COMPLETE (v2): fire onComplete if CLASSIFIED didn't already set result.
              callbacks.onComplete(result || "Captured");
            }
          }
          es.close();
          break;

        case "ERROR":
        case "RUN_ERROR": // legacy compat
          callbacks.onError(parsed.message ?? "Run failed");
          es.close();
          break;

        // --- Legacy v1 events (keep during dev) ---
        case "TEXT_MESSAGE_CONTENT":
          if (parsed.delta) {
            result += parsed.delta;
            callbacks.onTextDelta?.(parsed.delta);
          }
          break;

        case "CUSTOM":
          // Legacy v1 wrapper -- handle for backward compat
          if (parsed.name === "HITL_REQUIRED" && parsed.value?.threadId) {
            hitlTriggered = true;
            const questionText = parsed.value.questionText || result;
            const inboxItemId = parsed.value.inboxItemId;
            callbacks.onHITLRequired?.(
              parsed.value.threadId,
              questionText,
              inboxItemId,
            );
          }
          if (parsed.name === "MISUNDERSTOOD" && parsed.value?.inboxItemId) {
            hitlTriggered = true;
            callbacks.onMisunderstood?.(
              parsed.value.threadId ?? "",
              parsed.value.questionText ?? "",
              parsed.value.inboxItemId,
            );
          }
          if (parsed.name === "UNRESOLVED" && parsed.value?.inboxItemId) {
            callbacks.onUnresolved?.(parsed.value.inboxItemId);
          }
          break;
      }
    } catch {
      // Ignore malformed JSON chunks
    }
  });

  es.addEventListener("error", (event) => {
    const errorMessage =
      "message" in event ? event.message : "Connection error";
    callbacks.onError(errorMessage);
    es.close();
  });

  return () => {
    es.removeAllEventListeners();
    es.close();
  };
}

/**
 * Send a capture thought to the AG-UI backend via SSE POST.
 *
 * Dispatches streaming events (step progression, text deltas, HITL requests)
 * to the provided callbacks. Returns a cleanup function and the thread ID
 * used for the request.
 */
export function sendCapture({
  message,
  apiKey,
  callbacks,
}: SendCaptureOptions): { cleanup: () => void; threadId: string } {
  const threadId = `thread-${Date.now()}`;

  const es = new EventSource<AGUIEventType>(`${API_BASE_URL}/api/capture`, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    method: "POST",
    body: JSON.stringify({
      text: message,
      thread_id: threadId,
      run_id: `run-${Date.now()}`,
    }),
    pollingInterval: 0, // CRITICAL: prevents auto-reconnection and duplicate captures
  });

  const cleanup = attachCallbacks(es, callbacks);

  return { cleanup, threadId };
}

/**
 * Send a follow-up reply for a misunderstood capture to re-classify.
 *
 * POSTs to /api/capture/follow-up with the inbox item ID, follow-up text,
 * and round number. Streams the re-classification events through the same
 * callback pattern.
 *
 * Returns a cleanup function for the SSE connection.
 */
export function sendFollowUp({
  inboxItemId,
  followUpText,
  followUpRound,
  apiKey,
  callbacks,
}: SendFollowUpOptions): () => void {
  const es = new EventSource<AGUIEventType>(
    `${API_BASE_URL}/api/capture/follow-up`,
    {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify({
        inbox_item_id: inboxItemId,
        follow_up_text: followUpText,
        follow_up_round: followUpRound,
      }),
      pollingInterval: 0,
    },
  );

  return attachCallbacks(es, callbacks);
}

/**
 * Send a voice capture (audio file) to the backend via multipart upload.
 *
 * Uses react-native-sse EventSource with method: 'POST' and FormData body.
 * React Native's fetch doesn't support ReadableStream/getReader(), but
 * EventSource (backed by XMLHttpRequest) handles progressive SSE responses
 * natively. Reuses attachCallbacks for consistent event handling.
 *
 * Returns a cleanup/abort function.
 */
export function sendVoiceCapture({
  audioUri,
  apiKey,
  callbacks,
}: SendVoiceCaptureOptions): () => void {
  const formData = new FormData();
  formData.append("file", {
    uri: audioUri,
    type: "audio/m4a",
    name: "voice-capture.m4a",
  } as any);

  const es = new EventSource<AGUIEventType>(
    `${API_BASE_URL}/api/capture/voice`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
      },
      body: formData,
      pollingInterval: 0, // Disable auto-reconnect
    },
  );

  return attachCallbacks(es, callbacks);
}
