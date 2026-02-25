import EventSource from "react-native-sse";
import { API_BASE_URL } from "../constants/config";
import type {
  AGUIEventType,
  SendCaptureOptions,
  SendClarificationOptions,
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
  value?: {
    threadId?: string;
    inboxItemId?: string;
    questionText?: string;
  };
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
  let hitlTriggered = false;

  es.addEventListener("message", (event) => {
    if (!event.data) return;
    try {
      const parsed: AGUIEventPayload = JSON.parse(event.data);

      switch (parsed.type) {
        case "STEP_STARTED":
          callbacks.onStepStart?.(parsed.stepName ?? "Unknown");
          break;

        case "STEP_FINISHED":
          callbacks.onStepFinish?.(parsed.stepName ?? "Unknown");
          break;

        case "TEXT_MESSAGE_CONTENT":
          if (parsed.delta) {
            result += parsed.delta;
            callbacks.onTextDelta?.(parsed.delta);
          }
          break;

        case "CUSTOM":
          if (parsed.name === "HITL_REQUIRED" && parsed.value?.threadId) {
            hitlTriggered = true;
            // Use questionText from event if available (new flow),
            // fall back to accumulated result (legacy flow)
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

        case "RUN_FINISHED":
          // Don't call onComplete if HITL was triggered — the client
          // is now showing bucket buttons for clarification
          if (!hitlTriggered) {
            callbacks.onComplete(result);
          }
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
  inboxItemId,
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
        inbox_item_id: inboxItemId,
      }),
      pollingInterval: 0,
    },
  );

  return attachCallbacks(es, callbacks);
}

/**
 * Send a follow-up reply for a misunderstood capture to re-classify.
 *
 * POSTs to /api/ag-ui/follow-up with the inbox item ID, follow-up text,
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
    `${API_BASE_URL}/api/ag-ui/follow-up`,
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
 * Uses fetch + ReadableStream for SSE parsing because react-native-sse
 * EventSource doesn't support multipart uploads. The SSE parsing logic
 * mirrors attachCallbacks for consistency.
 *
 * Returns a cleanup/abort function.
 */
export function sendVoiceCapture({
  audioUri,
  apiKey,
  callbacks,
}: SendVoiceCaptureOptions): () => void {
  let aborted = false;
  const abortController = new AbortController();

  (async () => {
    try {
      // Build multipart form data
      const formData = new FormData();
      formData.append("file", {
        uri: audioUri,
        type: "audio/m4a",
        name: "voice-capture.m4a",
      } as any);

      // POST multipart -- response is SSE stream
      const response = await fetch(`${API_BASE_URL}/api/voice-capture`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          // Do NOT set Content-Type -- fetch sets it with multipart boundary
        },
        body: formData,
        signal: abortController.signal,
      });

      if (!response.ok) {
        callbacks.onError(`Upload failed: ${response.status}`);
        return;
      }

      // Read SSE stream from response body
      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError("No response stream");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let result = "";
      let hitlTriggered = false;

      while (!aborted) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer (events separated by \n\n)
        const events = buffer.split("\n\n");
        buffer = events.pop() || ""; // Keep incomplete event in buffer

        for (const eventStr of events) {
          if (!eventStr.trim()) continue;
          const dataMatch = eventStr.match(/^data:\s*(.+)$/m);
          if (!dataMatch) continue;

          try {
            const parsed = JSON.parse(dataMatch[1]);
            switch (parsed.type) {
              case "STEP_STARTED":
                callbacks.onStepStart?.(parsed.stepName ?? "Unknown");
                break;
              case "STEP_FINISHED":
                callbacks.onStepFinish?.(parsed.stepName ?? "Unknown");
                break;
              case "TEXT_MESSAGE_CONTENT":
                if (parsed.delta) {
                  result += parsed.delta;
                  callbacks.onTextDelta?.(parsed.delta);
                }
                break;
              case "CUSTOM":
                if (parsed.name === "HITL_REQUIRED" && parsed.value?.threadId) {
                  hitlTriggered = true;
                  callbacks.onHITLRequired?.(
                    parsed.value.threadId,
                    parsed.value.questionText || result,
                    parsed.value.inboxItemId,
                  );
                }
                if (
                  parsed.name === "MISUNDERSTOOD" &&
                  parsed.value?.inboxItemId
                ) {
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
              case "RUN_FINISHED":
                if (!hitlTriggered) {
                  callbacks.onComplete(result);
                }
                break;
              case "RUN_ERROR":
                callbacks.onError("Run failed");
                break;
            }
          } catch {
            // Ignore malformed JSON
          }
        }
      }
    } catch (err: any) {
      if (!aborted) {
        callbacks.onError(err?.message || "Voice capture failed");
      }
    }
  })();

  return () => {
    aborted = true;
    abortController.abort();
  };
}
