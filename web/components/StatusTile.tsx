import Link from "next/link";
import type { SegmentStatusResponse, SegmentStatus } from "@/lib/types";

const STATUS_COLOR: Record<SegmentStatus, string> = {
  green: "#3a7d3a",
  yellow: "#c89010",
  red: "#b33b3b",
  stale: "#555",
};

export function StatusTile({ segment }: { segment: SegmentStatusResponse }) {
  return (
    <Link
      href={`/segment/${segment.id}`}
      style={{
        display: "block",
        padding: 16,
        background: "#1a2028",
        border: `2px solid ${STATUS_COLOR[segment.status]}`,
        borderRadius: 8,
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <strong>{segment.name}</strong>
        <span style={{ color: STATUS_COLOR[segment.status], fontSize: 12, textTransform: "uppercase" }}>
          {segment.status}
        </span>
      </div>
      <p style={{ margin: "8px 0 0", color: "#bbb", fontSize: 14 }}>{segment.headline}</p>
      <p style={{ margin: "8px 0 0", color: "#666", fontSize: 11 }}>
        {segment.freshness_seconds}s ago
      </p>
    </Link>
  );
}
