import Link from "next/link";
import { notFound } from "next/navigation";

import { LocalTime } from "@/components/LocalTime";
import { spine } from "@/lib/spine";
import type {
  CorrelationKind,
  CorrelationResponse,
  SegmentStatus,
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

  let correlation: CorrelationResponse;
  try {
    correlation = await spine.correlation(kind, params.id);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return (
      <main style={{ padding: 24 }}>
        <h1 style={{ marginTop: 0 }}>Correlation Timeline</h1>
        <p style={{ color: "#c89010", marginTop: 24 }}>
          No data available for this correlation.
        </p>
        <p style={{ color: "#666", fontSize: 12, marginTop: 8 }}>{message}</p>
      </main>
    );
  }

  return (
    <main style={{ padding: 24 }}>
      <h1 style={{ marginTop: 0 }}>Correlation Timeline</h1>
      <p style={{ color: "#888", fontSize: 13 }}>
        {correlation.correlation_kind} <code>{correlation.correlation_id}</code>
      </p>
      {correlation.events.length === 0 ? (
        <p style={{ color: "#888", marginTop: 24 }}>
          No segment events recorded for this correlation.
        </p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, marginTop: 24 }}>
          {correlation.events.map((event, index) => (
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
                <span
                  style={{
                    color: STATUS_COLOR[event.status],
                    fontSize: 12,
                    textTransform: "uppercase",
                  }}
                >
                  {event.status}
                </span>
              </div>
              <div style={{ color: "#888", fontSize: 12, marginTop: 4 }}>
                <LocalTime iso={event.timestamp} />
              </div>
              <p style={{ color: "#bbb", margin: "8px 0 0" }}>{event.headline}</p>
              <p style={{ margin: "12px 0 0" }}>
                <Link
                  href={`/segment/${event.segment_id}?correlation_kind=${correlation.correlation_kind}&correlation_id=${encodeURIComponent(correlation.correlation_id)}`}
                  style={{ color: "#9ecbff" }}
                >
                  Open filtered segment detail
                </Link>
              </p>
            </li>
          ))}
        </ul>
      )}
      <p style={{ color: "#666", fontSize: 12, marginTop: 24 }}>
        Fetched <LocalTime iso={correlation.envelope.generated_at} /> ·
        Latency {correlation.envelope.query_latency_ms}ms
      </p>
    </main>
  );
}
