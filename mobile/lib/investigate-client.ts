import EventSource from "react-native-sse";
import { API_BASE_URL } from "../constants/config";

type InvestigateEventType = "message";

interface InvestigateEventPayload {
  type?: string;
  content?: string;
  thread_id?: string;
  message?: string;
  tool?: string;
  description?: string;
  error?: string;
}

export interface InvestigateCallbacks {
  onThinking: () => void;
  onText: (content: string) => void;
  onDone: (threadId: string) => void;
  onError: (message: string) => void;
}

/**
 * Send an investigation question to the backend via SSE POST.
 *
 * Streams events from /api/investigate and dispatches to callbacks.
 * Returns a cleanup function to abort the connection.
 *
 * Event types handled:
 * - thinking: agent is working (no-op, bubble shows "Thinking..." by default)
 * - text: streamed text content to append to the agent response
 * - done: investigation complete, includes thread_id for follow-ups
 * - error: investigation failed
 *
 * Silently ignored (per user decision -- no tool call visibility):
 * - tool_call, tool_error, rate_warning
 */
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
  // Use explicit null/undefined check -- empty string is falsy in JS
  // but a valid thread_id value (MEMORY.md pitfall)
  if (threadId !== undefined && threadId !== null) {
    body.thread_id = threadId;
  }

  const es = new EventSource<InvestigateEventType>(
    `${API_BASE_URL}/api/investigate`,
    {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(body),
      pollingInterval: 0, // CRITICAL: prevents auto-reconnection (Pitfall 1)
    },
  );

  es.addEventListener("message", (event) => {
    if (!event.data) return;
    try {
      const parsed: InvestigateEventPayload = JSON.parse(event.data);
      switch (parsed.type) {
        case "thinking":
          callbacks.onThinking();
          break;
        case "text":
          callbacks.onText(parsed.content ?? "");
          break;
        case "done":
          // Use explicit null/undefined check for thread_id
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
      // Ignore malformed JSON chunks
    }
  });

  es.addEventListener("error", (event) => {
    const errorMessage =
      "message" in event ? event.message : "Connection error";
    callbacks.onError(errorMessage ?? "Connection error");
    es.close();
  });

  return {
    cleanup: () => {
      es.removeAllEventListeners();
      es.close();
    },
  };
}
