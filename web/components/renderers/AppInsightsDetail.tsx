import Link from "next/link";

interface AppInsightsData {
  schema: "azure_monitor_app_insights";
  app_exceptions: Array<{
    timestamp: string;
    message: string;
    outer_message?: string | null;
    outer_type?: string | null;
    innermost_message?: string | null;
    details?: string | null;
    component?: string | null;
    capture_trace_id?: string | null;
  }>;
  app_requests: Array<{
    timestamp: string;
    name: string;
    duration_ms: number | null;
    result_code: string;
    capture_trace_id?: string | null;
    operation_id?: string | null;
  }>;
}

export function AppInsightsDetail({ data }: { data: AppInsightsData }) {
  const exceptions = data.app_exceptions ?? [];
  const requests = data.app_requests ?? [];

  return (
    <div>
      <section>
        <h2>Recent exceptions ({exceptions.length})</h2>
        {exceptions.length === 0 ? (
          <p style={{ color: "#888" }}>No recent exceptions.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0 }}>
            {exceptions.map((e, i) => (
              <li key={i} style={{ background: "#1a2028", padding: 12, marginBottom: 8, borderRadius: 6 }}>
                <div style={{ fontSize: 12, color: "#888" }}>
                  {new Date(e.timestamp).toLocaleString()} · {e.component ?? "—"}
                </div>
                <div style={{ marginTop: 4, fontWeight: 600 }}>{e.outer_message ?? e.message}</div>
                {e.capture_trace_id && (
                  <div style={{ marginTop: 6 }}>
                    <Link
                      href={`/correlation/capture/${encodeURIComponent(e.capture_trace_id)}`}
                      style={{ color: "#9ecbff", fontSize: 12 }}
                    >
                      Trace {e.capture_trace_id.slice(0, 8)}
                    </Link>
                  </div>
                )}
                {e.outer_type && (
                  <div style={{ fontSize: 12, color: "#aaa", marginTop: 4 }}>
                    <code>{e.outer_type}</code>
                  </div>
                )}
                {e.innermost_message && e.innermost_message !== e.outer_message && (
                  <details style={{ marginTop: 8 }}>
                    <summary style={{ cursor: "pointer", color: "#888", fontSize: 12 }}>Inner cause</summary>
                    <pre style={{ marginTop: 4, fontSize: 12 }}>{e.innermost_message}</pre>
                  </details>
                )}
                {e.details && (
                  <details style={{ marginTop: 8 }}>
                    <summary style={{ cursor: "pointer", color: "#888", fontSize: 12 }}>Stack details</summary>
                    <pre style={{ marginTop: 4, fontSize: 11, overflow: "auto", maxHeight: 240 }}>{e.details.slice(0, 4000)}</pre>
                  </details>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section style={{ marginTop: 32 }}>
        <h2>Recent requests ({requests.length})</h2>
        {requests.length === 0 ? (
          <p style={{ color: "#888" }}>No recent requests.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #333" }}>
                <th style={{ textAlign: "left", padding: 8 }}>Time</th>
                <th style={{ textAlign: "left", padding: 8 }}>Operation</th>
                <th style={{ textAlign: "right", padding: 8 }}>Duration</th>
                <th style={{ textAlign: "right", padding: 8 }}>Status</th>
                <th style={{ textAlign: "left", padding: 8 }}>Trace</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r, i) => (
                <tr key={i} style={{ borderBottom: "1px solid #1a2028" }}>
                  <td style={{ padding: 8, color: "#888" }}>{new Date(r.timestamp).toLocaleTimeString()}</td>
                  <td style={{ padding: 8 }}>
                    <div>{r.name}</div>
                    {r.operation_id && (
                      <div style={{ color: "#666", fontFamily: "monospace", fontSize: 11, marginTop: 4 }}>
                        op={r.operation_id}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: 8, textAlign: "right" }}>
                    {r.duration_ms != null ? `${r.duration_ms}ms` : "—"}
                  </td>
                  <td style={{ padding: 8, textAlign: "right" }}>{r.result_code}</td>
                  <td style={{ padding: 8 }}>
                    {r.capture_trace_id ? (
                      <Link
                        href={`/correlation/capture/${encodeURIComponent(r.capture_trace_id)}`}
                        style={{ color: "#9ecbff", fontFamily: "monospace", fontSize: 12 }}
                      >
                        {r.capture_trace_id.slice(0, 8)}
                      </Link>
                    ) : (
                      <span style={{ color: "#666" }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
