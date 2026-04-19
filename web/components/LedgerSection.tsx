import Link from "next/link";

import { LocalTime } from "./LocalTime";
import type {
  SegmentLedgerMode,
  TransactionLedgerRow,
  WorkloadOutcome,
} from "@/lib/types";

const OUTCOME_COLOR: Record<WorkloadOutcome, string> = {
  success: "#3a7d3a",
  degraded: "#c89010",
  failure: "#b33b3b",
};

const DEFAULT_NATIVE_ONLY_MESSAGE =
  "This segment is native-only by design — no transactional events are expected. See the diagnostics section below for infrastructure telemetry.";

export interface LedgerSectionProps {
  segmentId: string;
  rows: TransactionLedgerRow[];
  mode: SegmentLedgerMode;
  emptyStateReason: string | null;
}

export function LedgerSection({
  segmentId,
  rows,
  mode,
  emptyStateReason,
}: LedgerSectionProps): JSX.Element {
  return (
    <section>
      <h2 style={{ marginTop: 24 }}>Recent transactions</h2>
      {rows.length === 0 ? (
        mode === "native_only" ? (
          <p
            style={{
              background: "#1a2028",
              borderLeft: "4px solid #555",
              borderRadius: 6,
              color: "#bbb",
              margin: "12px 0 0",
              padding: 12,
            }}
          >
            {emptyStateReason ?? DEFAULT_NATIVE_ONLY_MESSAGE}
          </p>
        ) : (
          <p style={{ color: "#888", marginTop: 12 }}>
            No recent transactions in the last hour for this segment.
          </p>
        )
      ) : (
        <table
          role="table"
          style={{
            borderCollapse: "collapse",
            marginTop: 12,
            width: "100%",
          }}
        >
          <thead>
            <tr style={{ color: "#888", fontSize: 12, textAlign: "left" }}>
              <th
                scope="col"
                style={{ borderBottom: "1px solid #2a3340", padding: "8px 12px" }}
              >
                Timestamp
              </th>
              <th
                scope="col"
                style={{ borderBottom: "1px solid #2a3340", padding: "8px 12px" }}
              >
                Operation
              </th>
              <th
                scope="col"
                style={{ borderBottom: "1px solid #2a3340", padding: "8px 12px" }}
              >
                Outcome
              </th>
              <th
                scope="col"
                style={{ borderBottom: "1px solid #2a3340", padding: "8px 12px" }}
              >
                Duration
              </th>
              <th
                scope="col"
                style={{ borderBottom: "1px solid #2a3340", padding: "8px 12px" }}
              >
                Correlation
              </th>
              <th
                scope="col"
                style={{ borderBottom: "1px solid #2a3340", padding: "8px 12px" }}
              >
                Error
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const correlationCell =
                row.correlation_kind && row.correlation_id ? (
                  <Link
                    href={`/correlation/${row.correlation_kind}/${encodeURIComponent(
                      row.correlation_id,
                    )}`}
                    style={{ color: "#9ecbff" }}
                  >
                    {row.correlation_id.length > 12
                      ? `${row.correlation_id.slice(0, 12)}…`
                      : row.correlation_id}
                  </Link>
                ) : (
                  <span style={{ color: "#555" }}>—</span>
                );
              return (
                <tr
                  key={`${row.segment_id}-${row.timestamp}-${index}`}
                  style={{ background: "#1a2028" }}
                >
                  <td
                    style={{
                      borderBottom: "1px solid #0f141a",
                      color: "#bbb",
                      fontSize: 13,
                      padding: "8px 12px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    <LocalTime iso={row.timestamp} />
                  </td>
                  <td
                    style={{
                      borderBottom: "1px solid #0f141a",
                      color: "#ddd",
                      padding: "8px 12px",
                    }}
                  >
                    <code>{row.operation}</code>
                  </td>
                  <td
                    style={{
                      borderBottom: "1px solid #0f141a",
                      color: OUTCOME_COLOR[row.outcome],
                      fontSize: 12,
                      padding: "8px 12px",
                      textTransform: "uppercase",
                    }}
                  >
                    {row.outcome}
                  </td>
                  <td
                    style={{
                      borderBottom: "1px solid #0f141a",
                      color: "#bbb",
                      fontSize: 13,
                      padding: "8px 12px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {row.duration_ms}ms
                  </td>
                  <td
                    style={{
                      borderBottom: "1px solid #0f141a",
                      fontSize: 13,
                      padding: "8px 12px",
                    }}
                  >
                    {correlationCell}
                  </td>
                  <td
                    style={{
                      borderBottom: "1px solid #0f141a",
                      color: row.error_class ? "#b33b3b" : "#555",
                      fontSize: 13,
                      padding: "8px 12px",
                    }}
                  >
                    {row.error_class ?? ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      <p style={{ color: "#555", fontSize: 12, marginTop: 8 }}>
        Segment: <code>{segmentId}</code>
      </p>
    </section>
  );
}
