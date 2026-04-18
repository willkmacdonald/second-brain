interface CosmosLog {
  timestamp: string;
  operation_name: string;
  status_code: number;
  duration_ms: number;
  request_charge: number;
  request_length: number;
  response_length: number;
  partition_key_range_id: string;
  client_request_id: string;
  collection_name: string;
}

interface CosmosData {
  schema: "azure_monitor_cosmos";
  diagnostic_logs: CosmosLog[];
  native_url: string;
}

export function CosmosDiagnosticDetail({ data }: { data: CosmosData }) {
  return (
    <div>
      <h2>Cosmos diagnostic logs ({data.diagnostic_logs.length})</h2>
      <p style={{ color: "#888", fontSize: 13 }}>
        Diagnostic logs lag 5–10 minutes; data shown may not be real-time.
      </p>
      {data.diagnostic_logs.length === 0 ? (
        <p style={{ color: "#888" }}>No recent operations.</p>
      ) : (
        <table
          style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}
        >
          <thead>
            <tr style={{ borderBottom: "1px solid #333" }}>
              <th style={{ textAlign: "left", padding: 8 }}>Time</th>
              <th style={{ textAlign: "left", padding: 8 }}>Op</th>
              <th style={{ textAlign: "left", padding: 8 }}>Container</th>
              <th style={{ textAlign: "right", padding: 8 }}>RU</th>
              <th style={{ textAlign: "right", padding: 8 }}>Duration</th>
              <th style={{ textAlign: "right", padding: 8 }}>Status</th>
              <th style={{ textAlign: "left", padding: 8 }}>Request ID</th>
            </tr>
          </thead>
          <tbody>
            {data.diagnostic_logs.map((l, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #1a2028" }}>
                <td style={{ padding: 8, color: "#888" }}>
                  {new Date(l.timestamp).toLocaleTimeString()}
                </td>
                <td style={{ padding: 8 }}>{l.operation_name}</td>
                <td style={{ padding: 8 }}>{l.collection_name}</td>
                <td style={{ padding: 8, textAlign: "right" }}>
                  {l.request_charge?.toFixed(1) ?? "—"}
                </td>
                <td style={{ padding: 8, textAlign: "right" }}>
                  {l.duration_ms}ms
                </td>
                <td
                  style={{
                    padding: 8,
                    textAlign: "right",
                    color: l.status_code < 300 ? "#3a7d3a" : "#b33b3b",
                  }}
                >
                  {l.status_code}
                </td>
                <td
                  style={{
                    padding: 8,
                    fontFamily: "monospace",
                    fontSize: 11,
                  }}
                >
                  {l.client_request_id?.slice(0, 8) ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
