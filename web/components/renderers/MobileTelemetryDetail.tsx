interface SentrySource {
  schema: "sentry_event";
  events: Array<{
    id: string;
    title?: string;
    timestamp: string;
    tags?: Record<string, string>;
  }>;
  issues: unknown[];
  native_url: string;
  tag_filter: Record<string, string>;
}

interface TelemetrySource {
  schema: "mobile_telemetry";
  telemetry_events: Array<{
    timestamp: string;
    payload: {
      operation: string;
      outcome: string;
      error_class?: string | null;
    };
  }>;
  native_url: string;
}

interface CombinedData {
  schema: "mobile_telemetry_combined";
  sources: {
    sentry?: SentrySource;
    telemetry?: TelemetrySource;
  };
  partial_failures: string[];
  native_url: string;
}

export function MobileTelemetryDetail({ data }: { data: CombinedData }) {
  const sentryEvents = data.sources.sentry?.events ?? [];
  const telemetryEvents = data.sources.telemetry?.telemetry_events ?? [];

  type Row = {
    ts: string;
    source: "sentry" | "telemetry";
    label: string;
    detail: string;
  };
  const rows: Row[] = [
    ...sentryEvents.map((e) => ({
      ts: e.timestamp,
      source: "sentry" as const,
      label: e.title ?? "Sentry event",
      detail: JSON.stringify(e.tags ?? {}),
    })),
    ...telemetryEvents.map((e) => ({
      ts: e.timestamp,
      source: "telemetry" as const,
      label: e.payload.operation,
      detail: e.payload.error_class ?? e.payload.outcome,
    })),
  ].sort((a, b) => b.ts.localeCompare(a.ts));

  return (
    <div>
      {data.partial_failures.length > 0 && (
        <p style={{ color: "#c89010" }}>
          Partial source failures: {data.partial_failures.join(", ")}
        </p>
      )}
      <h2>Combined timeline ({rows.length} events)</h2>
      <p style={{ color: "#888", fontSize: 13 }}>
        Sources: Sentry ({sentryEvents.length}), backend telemetry (
        {telemetryEvents.length})
      </p>
      {rows.length === 0 ? (
        <p style={{ color: "#888" }}>No recent events.</p>
      ) : (
        <table
          style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}
        >
          <thead>
            <tr style={{ borderBottom: "1px solid #333" }}>
              <th style={{ textAlign: "left", padding: 8 }}>Time</th>
              <th style={{ textAlign: "left", padding: 8 }}>Source</th>
              <th style={{ textAlign: "left", padding: 8 }}>Operation</th>
              <th style={{ textAlign: "left", padding: 8 }}>Detail</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #1a2028" }}>
                <td style={{ padding: 8, color: "#888" }}>
                  {new Date(r.ts).toLocaleString()}
                </td>
                <td
                  style={{
                    padding: 8,
                    color: r.source === "sentry" ? "#c89010" : "#bbb",
                  }}
                >
                  {r.source}
                </td>
                <td style={{ padding: 8 }}>{r.label}</td>
                <td
                  style={{ padding: 8, fontFamily: "monospace", fontSize: 11 }}
                >
                  {r.detail}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
