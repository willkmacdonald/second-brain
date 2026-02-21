import EventSource from "react-native-sse";
import { API_BASE_URL } from "../constants/config";
import type { AGUIEventType, SendCaptureOptions } from "./types";

/**
 * Send a capture thought to the AG-UI backend via SSE POST.
 *
 * Fire-and-forget: listens for RUN_FINISHED (success) or error (failure).
 * Does NOT consume TEXT_MESSAGE_CONTENT deltas -- that is Phase 4 work.
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

  es.addEventListener("RUN_FINISHED", () => {
    onComplete();
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
