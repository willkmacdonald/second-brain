import Link from "next/link";
import { notFound } from "next/navigation";

import { LocalTime } from "@/components/LocalTime";
import { spine } from "@/lib/spine";
import type {
  CorrelationKind,
  SegmentStatus,
  TransactionPathResponse,
} from "@/lib/types";

export const dynamic = "force-dynamic";

const VALID_CORRELATION_KINDS = new Set<CorrelationKind>([
  "capture",
  "thread",
  "request",
  "crud",
]);

const STATUS_COLOR: Record<SegmentStatus, string> = {
  green: "#3a7d3a",
  yellow: "#c89010",
  red: "#b33b3b",
  stale: "#555",
};

const OUTCOME_COLOR: Record<"success" | "failure" | "degraded", string> = {
  success: "#3a7d3a",
  degraded: "#c89010",
  failure: "#b33b3b",
};

function parseCorrelationKind(value: string): CorrelationKind | null {
  if (!VALID_CORRELATION_KINDS.has(value as CorrelationKind)) {
    return null;
  }
  return value as CorrelationKind;
}

export default async function CorrelationPage({
  params,
}: {
  params: { kind: string; id: string };
}) {
  const kind = parseCorrelationKind(params.kind);
  if (!kind) {
    notFound();
  }

  let path: TransactionPathResponse;
  try {
    path = await spine.transactionPath(kind, params.id);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return (
      <main style={{ padding: 24 }}>
        <h1 style={{ marginTop: 0 }}>Transaction Path</h1>
        <p style={{ color: "#c89010", marginTop: 24 }}>
          No data available for this correlation.
        </p>
        <p style={{ color: "#666", fontSize: 12, marginTop: 8 }}>{message}</p>
      </main>
    );
  }

  return (
    <main style={{ padding: 24 }}>
      <h1 style={{ marginTop: 0 }}>Transaction Path</h1>
      <p style={{ color: "#888", fontSize: 13 }}>
        {path.correlation_kind} <code>{path.correlation_id}</code>
      </p>

      {/* Gap callouts — the headline feature of this page */}
      {path.missing_required.length > 0 && (
        <div
          style={{
            background: "#2a1a1a",
            border: `1px solid ${STATUS_COLOR.red}`,
            borderRadius: 6,
            padding: 12,
            marginTop: 16,
          }}
        >
          <strong style={{ color: STATUS_COLOR.red }}>
            Missing required segments:
          </strong>{" "}
          <span style={{ color: "#ddd" }}>
            {path.missing_required.join(", ")}
          </span>
          <p style={{ color: "#aaa", fontSize: 12, margin: "6px 0 0" }}>
            These segments were expected in the {path.correlation_kind} chain
            but did not emit a workload event for this correlation id.
          </p>
        </div>
      )}

      {path.unexpected.length > 0 && (
        <div
          style={{
            background: "#2a251a",
            border: `1px solid ${STATUS_COLOR.yellow}`,
            borderRadius: 6,
            padding: 12,
            marginTop: 12,
          }}
        >
          <strong style={{ color: STATUS_COLOR.yellow }}>
            Unexpected segments:
          </strong>{" "}
          <span style={{ color: "#ddd" }}>{path.unexpected.join(", ")}</span>
          <p style={{ color: "#aaa", fontSize: 12, margin: "6px 0 0" }}>
            These segments emitted workload events but are not part of the
            expected {path.correlation_kind} chain.
          </p>
        </div>
      )}

      {path.present_optional.length > 0 && (
        <p style={{ color: "#888", fontSize: 12, marginTop: 12 }}>
          Optional segments observed: {path.present_optional.join(", ")}.
        </p>
      )}

      {/* Full event timeline — chronological */}
      <h2 style={{ marginTop: 32 }}>Events ({path.events.length})</h2>
      {path.events.length === 0 ? (
        <p style={{ color: "#888", marginTop: 24 }}>
          No segment events recorded for this correlation.
        </p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, marginTop: 16 }}>
          {path.events.map((event, index) => (
            <li
              key={`${event.segment_id}-${event.timestamp}-${index}`}
              style={{
                background: "#1a2028",
                borderLeft: `4px solid ${STATUS_COLOR[event.status]}`,
                borderRadius: 6,
                marginBottom: 12,
                padding: 12,
              }}
            >
              <div
                style={{
                  alignItems: "baseline",
                  display: "flex",
                  gap: 12,
                  justifyContent: "space-between",
                }}
              >
                <strong>{event.segment_id}</strong>
                {event.outcome && (
                  <span
                    style={{
                      color: OUTCOME_COLOR[event.outcome],
                      fontSize: 12,
                      textTransform: "uppercase",
                    }}
                  >
                    {event.outcome}
                  </span>
                )}
              </div>
              <div style={{ color: "#888", fontSize: 12, marginTop: 4 }}>
                <LocalTime iso={event.timestamp} />
                {event.duration_ms !== null && <> · {event.duration_ms}ms</>}
              </div>
              {event.operation && (
                <p
                  style={{
                    color: "#bbb",
                    margin: "8px 0 0",
                    fontFamily: "monospace",
                    fontSize: 13,
                  }}
                >
                  {event.operation}
                </p>
              )}
              {event.error_class && (
                <p
                  style={{
                    color: STATUS_COLOR.red,
                    fontSize: 12,
                    margin: "4px 0 0",
                  }}
                >
                  Error: {event.error_class}
                </p>
              )}
              {!event.operation && event.headline && (
                <p style={{ color: "#bbb", margin: "8px 0 0" }}>
                  {event.headline}
                </p>
              )}
              <p style={{ margin: "12px 0 0" }}>
                <Link
                  href={`/segment/${event.segment_id}?correlation_kind=${path.correlation_kind}&correlation_id=${encodeURIComponent(path.correlation_id)}`}
                  style={{ color: "#9ecbff" }}
                >
                  Open segment diagnostics for this transaction
                </Link>
              </p>
            </li>
          ))}
        </ul>
      )}

      <p style={{ color: "#666", fontSize: 12, marginTop: 24 }}>
        Fetched <LocalTime iso={path.envelope.generated_at} /> · Latency{" "}
        {path.envelope.query_latency_ms}ms
      </p>
    </main>
  );
}
