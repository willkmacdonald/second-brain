import Link from "next/link";

import { LocalTime } from "@/components/LocalTime";

interface FoundryRun {
  timestamp: string;
  name: string;
  duration_ms: number;
  success: boolean;
  result_code: string;
  agent_id: string;
  agent_name: string;
  run_id: string;
  thread_id: string;
  capture_trace_id: string;
  operation_id: string;
}

interface FoundryRunData {
  schema: "foundry_run";
  agent_id: string;
  agent_name: string;
  agent_runs: FoundryRun[];
  native_url: string;
}

export function FoundryRunDetail({ data }: { data: FoundryRunData }) {
  return (
    <div>
      <h2>
        {data.agent_name} runs ({data.agent_runs.length})
      </h2>
      <p style={{ color: "#888", fontSize: 13 }}>
        Agent ID: <code>{data.agent_id}</code>
      </p>
      {data.agent_runs.length === 0 ? (
        <p style={{ color: "#888" }}>No recent runs.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {data.agent_runs.map((r, i) => (
            <li
              key={i}
              style={{
                background: "#1a2028",
                padding: 12,
                marginBottom: 8,
                borderRadius: 6,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <div>
                  <strong>{r.name}</strong>
                  <span
                    style={{
                      marginLeft: 12,
                      color: r.success ? "#3a7d3a" : "#b33b3b",
                      fontSize: 12,
                    }}
                  >
                    {r.success ? "✓" : "✗"} {r.result_code}
                  </span>
                </div>
                <span style={{ color: "#888", fontSize: 12 }}>
                  {r.duration_ms}ms
                </span>
              </div>
              <div style={{ color: "#888", fontSize: 12, marginTop: 4 }}>
                <LocalTime iso={r.timestamp} />
              </div>
              <div
                style={{
                  color: "#666",
                  fontSize: 11,
                  marginTop: 4,
                  fontFamily: "monospace",
                }}
              >
                run={r.run_id}
                {r.thread_id && (
                  <>
                    {" · "}
                    <Link
                      href={`/correlation/thread/${encodeURIComponent(r.thread_id)}`}
                      style={{ color: "#9ecbff" }}
                    >
                      thread={r.thread_id}
                    </Link>
                  </>
                )}
                {r.capture_trace_id && (
                  <>
                    {" · "}
                    <Link
                      href={`/correlation/capture/${encodeURIComponent(r.capture_trace_id)}`}
                      style={{ color: "#9ecbff" }}
                    >
                      trace={r.capture_trace_id.slice(0, 8)}
                    </Link>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
