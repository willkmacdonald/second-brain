import { API_BASE_URL, API_KEY } from "../constants/config";

/** Generate a unique trace ID for a capture session. */
export function generateTraceId(): string {
  // crypto.randomUUID is available in React Native Hermes engine
  // Fallback to manual UUID v4 if unavailable
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

interface TelemetryEvent {
  eventType: "error" | "network_failure" | "performance";
  message: string;
  captureTraceId?: string;
  metadata?: Record<string, string | number | boolean>;
}

/**
 * Report a client-side error or event to the backend telemetry endpoint.
 * Fire-and-forget -- errors during reporting are silently swallowed.
 */
export async function reportError(event: TelemetryEvent): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/telemetry`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_KEY}`,
      },
      body: JSON.stringify({
        event_type: event.eventType,
        message: event.message,
        capture_trace_id: event.captureTraceId,
        metadata: event.metadata,
      }),
    });
  } catch {
    // Swallow -- telemetry reporting must never crash the app
  }
}
