import EventSource from "react-native-sse";
import { API_BASE_URL } from "../constants/config";
import type { AGUIEventType, SendCaptureOptions } from "./types";

/**
 * Send a capture thought to the AG-UI backend via SSE POST.
 *
 * Accumulates TEXT_MESSAGE_CONTENT deltas to build the classification result
 * string (e.g., "Filed -> Projects (0.85)"), then passes it to onComplete.
 *
 * Returns a cleanup function to abort the connection if the component unmounts.
 */
export function sendCapture({
  message,
  apiKey,
  onComplete,
  onError,
}: SendCaptureOptions): () => void {
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
      thread_id: `thread-${Date.now()}`,
      run_id: `run-${Date.now()}`,
    }),
    pollingInterval: 0, // CRITICAL: prevents auto-reconnection and duplicate captures
  });

  // Accumulate classification result from TEXT_MESSAGE_CONTENT deltas
  let result = "";

  es.addEventListener("TEXT_MESSAGE_CONTENT", (event) => {
    if (event.data) {
      try {
        const parsed = JSON.parse(event.data) as { delta?: string };
        if (parsed.delta) {
          result += parsed.delta;
        }
      } catch {
        // Ignore malformed JSON chunks
      }
    }
  });

  es.addEventListener("RUN_FINISHED", () => {
    onComplete(result);
    es.close();
  });

  es.addEventListener("error", (event) => {
    const errorMessage =
      "message" in event ? event.message : "Connection error";
    onError(errorMessage);
    es.close();
  });

  // Return cleanup function for useEffect teardown
  return () => {
    es.removeAllEventListeners();
    es.close();
  };
}
