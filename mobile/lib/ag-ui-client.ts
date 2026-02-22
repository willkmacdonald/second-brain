import EventSource from "react-native-sse";
import { API_BASE_URL } from "../constants/config";
import type {
  AGUIEventType,
  SendCaptureOptions,
  SendClarificationOptions,
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
  value?: { threadId?: string };
}

/**
 * Wire up an EventSource to dispatch streaming callbacks.
 *
 * Handles: STEP_STARTED, STEP_FINISHED, TEXT_MESSAGE_CONTENT,
 * CUSTOM (HITL_REQUIRED), RUN_FINISHED, and errors.
 *
 * Returns a cleanup function to abort the connection.
 */
function attachCallbacks(
  es: EventSource<AGUIEventType>,
  callbacks: StreamingCallbacks,
): () => void {
  let result = "";

  es.addEventListener("message", (event) => {
    if (!event.data) return;
    try {
      const parsed: AGUIEventPayload = JSON.parse(event.data);

      switch (parsed.type) {
        case "STEP_STARTED":
          callbacks.onStepStart?.(parsed.name ?? "Unknown");
          break;

        case "STEP_FINISHED":
          callbacks.onStepFinish?.(parsed.name ?? "Unknown");
          break;

        case "TEXT_MESSAGE_CONTENT":
          if (parsed.delta) {
            result += parsed.delta;
            callbacks.onTextDelta?.(parsed.delta);
          }
          break;

        case "CUSTOM":
          if (parsed.name === "HITL_REQUIRED" && parsed.value?.threadId) {
            // The accumulated result IS the clarifying question text
            callbacks.onHITLRequired?.(parsed.value.threadId, result);
          }
          break;

        case "RUN_FINISHED":
          callbacks.onComplete(result);
          es.close();
          break;

        case "RUN_ERROR":
          callbacks.onError("Run failed");
          es.close();
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
 * used for the request (needed for HITL sendClarification).
 */
export function sendCapture({
  message,
  apiKey,
  callbacks,
}: SendCaptureOptions): { cleanup: () => void; threadId: string } {
  const threadId = `thread-${Date.now()}`;

  const es = new EventSource<AGUIEventType>(`${API_BASE_URL}/api/ag-ui`, {
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
      thread_id: threadId,
      run_id: `run-${Date.now()}`,
    }),
    pollingInterval: 0, // CRITICAL: prevents auto-reconnection and duplicate captures
  });

  const cleanup = attachCallbacks(es, callbacks);

  return { cleanup, threadId };
}

/**
 * Send a clarification response (bucket selection) to resume a paused HITL workflow.
 *
 * POSTs to /api/ag-ui/respond with the thread_id and selected bucket,
 * then streams the continuation events through the same callback pattern.
 *
 * Returns a cleanup function for the SSE connection.
 */
export function sendClarification({
  threadId,
  bucket,
  apiKey,
  callbacks,
}: SendClarificationOptions): () => void {
  const es = new EventSource<AGUIEventType>(
    `${API_BASE_URL}/api/ag-ui/respond`,
    {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify({
        thread_id: threadId,
        response: bucket,
      }),
      pollingInterval: 0,
    },
  );

  return attachCallbacks(es, callbacks);
}
