import EventSource from "react-native-sse";
import { API_BASE_URL, API_KEY } from "../constants/config";
import { generateTraceId, reportError } from "./telemetry";
import { tagTrace } from "./sentry";
import type {
  AGUIEventType,
  SendCaptureOptions,
  SendFollowUpOptions,
  SendFollowUpVoiceOptions,
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
    buckets?: string[]; // For multi-split CLASSIFIED
    itemIds?: string[]; // For multi-split CLASSIFIED
  };
}

/**
 * SPIKE-MEMO §5.5 — Option B mobile push-path emit.
 *
 * Fire-and-forget POST to /api/spine/ingest after the SSE capture stream
 * terminates. Emits ONE workload event per capture, with outcome mapped
 * from the terminal SSE path (see §4c table). No retry, no queue; the
 * mobile error renderer (Sentry) already owns transport-failure
 * diagnosis for the case where both /api/capture AND this ingest POST
 * fail over the same broken network.
 *
 * Body conforms to backend/src/second_brain/spine/api.py:59's IngestEvent
 * (Pydantic RootModel), so no shape bug is possible on the mobile side.
 */
type MobileCaptureOutcome = "success" | "degraded" | "failure";

function emitMobileCaptureWorkload(
  traceId: string,
  outcome: MobileCaptureOutcome,
  durationMs: number,
): void {
  const body = {
    segment_id: "mobile_capture",
    event_type: "workload",
    timestamp: new Date().toISOString(),
    payload: {
      operation: "submit_capture",
      outcome,
      duration_ms: durationMs,
      correlation_kind: "capture",
      correlation_id: traceId,
    },
  };

  // Fire-and-forget — never block or delay the user callback. Swallow
  // network errors here because (a) we cannot retry without a new
  // subsystem (memo §4a explicitly defers that as Option A), and
  // (b) the user-visible capture has already completed or errored in
  // its own right via the SSE callbacks above.
  fetch(`${API_BASE_URL}/api/spine/ingest`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
    },
    body: JSON.stringify(body),
  }).catch(() => {
    /* transport failure surfaces via Sentry error reporting on the
       original capture path; we do not re-report here. */
  });
}

/**
 * Wire up an EventSource to dispatch streaming callbacks.
 *
 * Handles both v2 event types (STEP_START, STEP_END, CLASSIFIED,
 * MISUNDERSTOOD, UNRESOLVED, COMPLETE, ERROR) and legacy v1 types
 * (STEP_STARTED, STEP_FINISHED, TEXT_MESSAGE_CONTENT, CUSTOM,
 * RUN_FINISHED, RUN_ERROR) for backward compatibility during development.
 *
 * SPIKE-MEMO §5.5 — emits a `mobile_capture` workload event to the
 * spine on EVERY terminal path (success / degraded HITL / failure).
 * Single-fire guard ensures exactly one emit per stream even when
 * CLASSIFIED is followed by COMPLETE, or a HITL event is followed by
 * stream close. The emit is centralised here (not in per-sendX
 * wrappers) because HITL paths set `hitlTriggered=true` which
 * suppresses the downstream COMPLETE dispatch — per-sendX wrappers
 * would miss every HITL terminal path.
 *
 * Returns a cleanup function to abort the connection.
 */
function attachCallbacks(
  es: EventSource<AGUIEventType>,
  callbacks: StreamingCallbacks,
  traceId: string,
  startMs: number,
): () => void {
  let result = "";
  let hitlTriggered = false;
  // SPIKE-MEMO §5.5 — closure-scoped single-fire guard. Multiple
  // terminal events can arrive on one stream (e.g. CLASSIFIED followed
  // by COMPLETE); we must emit exactly once per capture lifecycle.
  let emitted = false;
  const emitOnce = (outcome: MobileCaptureOutcome): void => {
    if (emitted) return;
    emitted = true;
    emitMobileCaptureWorkload(traceId, outcome, Date.now() - startMs);
  };

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
            const buckets = parsed.value.buckets;
            const bucket = parsed.value.bucket ?? "?";
            const confidence = parsed.value.confidence ?? 0;

            if (buckets && buckets.length > 1) {
              // Multi-split: "Filed to Admin, Ideas"
              result = `Filed to ${buckets.join(", ")}`;
            } else {
              // Single: "Filed -> Admin (0.85)"
              result = `Filed -> ${bucket} (${confidence.toFixed(2)})`;
            }
            // SPIKE-MEMO §5.5 terminal path 1 — CLASSIFIED ⇒ success
            emitOnce("success");
            callbacks.onComplete(result);
          }
          break;

        case "MISUNDERSTOOD":
          // New v2: MISUNDERSTOOD is top-level
          if (parsed.value?.inboxItemId) {
            hitlTriggered = true;
            // SPIKE-MEMO §5.5 terminal path 3 — HITL ⇒ degraded
            emitOnce("degraded");
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
            // SPIKE-MEMO §5.5 terminal path 4 — HITL ⇒ degraded
            emitOnce("degraded");
            callbacks.onLowConfidence?.(
              parsed.value.inboxItemId ?? "",
              parsed.value.bucket ?? "?",
              parsed.value.confidence ?? 0,
            );
          }
          break;

        case "UNRESOLVED":
          // New v2: UNRESOLVED is top-level
          hitlTriggered = true; // Prevent COMPLETE from firing misleading onComplete
          // SPIKE-MEMO §5.5 terminal path 5 — HITL ⇒ degraded
          emitOnce("degraded");
          callbacks.onUnresolved?.(parsed.value?.inboxItemId ?? "");
          break;

        case "COMPLETE":
        case "RUN_FINISHED": // legacy compat
          if (!hitlTriggered) {
            if (parsed.type === "RUN_FINISHED" || !result) {
              // RUN_FINISHED (legacy): always fire onComplete.
              // COMPLETE (v2): fire onComplete if CLASSIFIED didn't already set result.
              // SPIKE-MEMO §5.5 terminal path 2 — non-HITL COMPLETE ⇒ success
              emitOnce("success");
              callbacks.onComplete(result || "Captured");
            } else {
              // CLASSIFIED already fired; just close. CLASSIFIED path
              // already called emitOnce("success"), which the guard
              // honours, so no double-fire here.
              emitOnce("success");
            }
          }
          es.close();
          break;

        case "ERROR":
        case "RUN_ERROR": // legacy compat
          // SPIKE-MEMO §5.5 terminal path 6 — backend error ⇒ failure
          emitOnce("failure");
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
            // SPIKE-MEMO §5.5 legacy terminal 8a — HITL_REQUIRED ⇒ degraded
            emitOnce("degraded");
            callbacks.onHITLRequired?.(
              parsed.value.threadId,
              questionText,
              inboxItemId,
            );
          }
          if (parsed.name === "MISUNDERSTOOD" && parsed.value?.inboxItemId) {
            hitlTriggered = true;
            // SPIKE-MEMO §5.5 legacy terminal 8b — MISUNDERSTOOD ⇒ degraded
            emitOnce("degraded");
            callbacks.onMisunderstood?.(
              parsed.value.threadId ?? "",
              parsed.value.questionText ?? "",
              parsed.value.inboxItemId,
            );
          }
          if (parsed.name === "UNRESOLVED" && parsed.value?.inboxItemId) {
            hitlTriggered = true;
            // SPIKE-MEMO §5.5 legacy terminal 8c — UNRESOLVED ⇒ degraded
            emitOnce("degraded");
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
    // SPIKE-MEMO §5.5 terminal path 7 — SSE transport error ⇒ failure.
    // Note: if the transport itself is broken (airplane mode, DNS
    // outage, etc.) the fire-and-forget fetch inside emitOnce will
    // also fail. That's the Option B blind spot documented in §4d —
    // Plan 04 surfaces an empty-state pointing the operator to Sentry.
    emitOnce("failure");
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
  captureSource,
}: SendCaptureOptions): { cleanup: () => void; threadId: string; traceId: string } {
  const threadId = `thread-${Date.now()}`;
  const traceId = generateTraceId();
  tagTrace(traceId);
  const startMs = Date.now();

  const headers: Record<string, string> = {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
    "X-Trace-Id": traceId,
  };
  if (captureSource) {
    headers["X-Capture-Source"] = captureSource;
  }

  const es = new EventSource<AGUIEventType>(`${API_BASE_URL}/api/capture`, {
    headers,
    method: "POST",
    body: JSON.stringify({
      text: message,
      thread_id: threadId,
      run_id: `run-${Date.now()}`,
    }),
    pollingInterval: 0, // CRITICAL: prevents auto-reconnection and duplicate captures
  });

  // Wrap error callback with telemetry reporting. The §5.5 mobile_capture
  // emit is handled inside attachCallbacks, not here — this wrapper is
  // only for Sentry error-path visibility.
  const wrappedCallbacks: StreamingCallbacks = {
    ...callbacks,
    onError: (error: string) => {
      reportError({
        eventType: "error",
        message: error,
        captureTraceId: traceId,
        metadata: { source: "sendCapture" },
      });
      callbacks.onError(error);
    },
  };

  const cleanup = attachCallbacks(es, wrappedCallbacks, traceId, startMs);

  return { cleanup, threadId, traceId };
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
  traceId: providedTraceId,
}: SendFollowUpOptions): { cleanup: () => void; traceId: string } {
  const traceId = providedTraceId ?? generateTraceId();
  tagTrace(traceId);
  const startMs = Date.now();

  const es = new EventSource<AGUIEventType>(
    `${API_BASE_URL}/api/capture/follow-up`,
    {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        "X-Trace-Id": traceId,
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

  // Wrap error callback with telemetry reporting
  const wrappedCallbacks: StreamingCallbacks = {
    ...callbacks,
    onError: (error: string) => {
      reportError({
        eventType: "error",
        message: error,
        captureTraceId: traceId,
        metadata: { source: "sendFollowUp" },
      });
      callbacks.onError(error);
    },
  };

  const cleanup = attachCallbacks(es, wrappedCallbacks, traceId, startMs);
  return { cleanup, traceId };
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
}: SendVoiceCaptureOptions): { cleanup: () => void; traceId: string } {
  const traceId = generateTraceId();
  tagTrace(traceId);
  const startMs = Date.now();

  const formData = new FormData();
  const isWav = audioUri.toLowerCase().endsWith(".wav");
  formData.append("file", {
    uri: audioUri,
    type: isWav ? "audio/wav" : "audio/m4a",
    name: isWav ? "voice-capture.wav" : "voice-capture.m4a",
  } as any);

  const es = new EventSource<AGUIEventType>(
    `${API_BASE_URL}/api/capture/voice`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "X-Trace-Id": traceId,
      },
      body: formData,
      pollingInterval: 0, // Disable auto-reconnect
    },
  );

  // Wrap error callback with telemetry reporting
  const wrappedCallbacks: StreamingCallbacks = {
    ...callbacks,
    onError: (error: string) => {
      reportError({
        eventType: "error",
        message: error,
        captureTraceId: traceId,
        metadata: { source: "sendVoiceCapture" },
      });
      callbacks.onError(error);
    },
  };

  const cleanup = attachCallbacks(es, wrappedCallbacks, traceId, startMs);
  return { cleanup, traceId };
}

/**
 * Send a voice follow-up for a misunderstood capture.
 *
 * Uploads audio to /api/capture/follow-up/voice which transcribes and
 * reclassifies on the same Foundry thread. Returns a cleanup function.
 */
export function sendFollowUpVoice({
  audioUri,
  inboxItemId,
  followUpRound,
  apiKey,
  callbacks,
  traceId: providedTraceId,
}: SendFollowUpVoiceOptions): { cleanup: () => void; traceId: string } {
  const traceId = providedTraceId ?? generateTraceId();
  tagTrace(traceId);
  const startMs = Date.now();

  const formData = new FormData();
  formData.append("file", {
    uri: audioUri,
    type: "audio/m4a",
    name: "follow-up.m4a",
  } as any);
  formData.append("inbox_item_id", inboxItemId);
  formData.append("follow_up_round", String(followUpRound));

  const es = new EventSource<AGUIEventType>(
    `${API_BASE_URL}/api/capture/follow-up/voice`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "X-Trace-Id": traceId,
      },
      body: formData,
      pollingInterval: 0,
    },
  );

  // Wrap error callback with telemetry reporting
  const wrappedCallbacks: StreamingCallbacks = {
    ...callbacks,
    onError: (error: string) => {
      reportError({
        eventType: "error",
        message: error,
        captureTraceId: traceId,
        metadata: { source: "sendFollowUpVoice" },
      });
      callbacks.onError(error);
    },
  };

  const cleanup = attachCallbacks(es, wrappedCallbacks, traceId, startMs);
  return { cleanup, traceId };
}
