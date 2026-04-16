"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import type { StatusBoardResponse } from "@/lib/types";
import { StatusTile } from "./StatusTile";

export function StatusBoard({ data }: { data: StatusBoardResponse }) {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), 10_000);
    return () => clearInterval(id);
  }, [router]);

  const visible = data.segments.filter((s) => !s.rollup.suppressed);
  const suppressed = data.segments.filter((s) => s.rollup.suppressed);

  return (
    <div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 12,
        }}
      >
        {visible.map((s) => (
          <StatusTile key={s.id} segment={s} />
        ))}
      </div>
      {suppressed.length > 0 && (
        <details style={{ marginTop: 24 }}>
          <summary style={{ cursor: "pointer", color: "#888" }}>
            {suppressed.length} segment(s) suppressed by host outage
          </summary>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
              gap: 12,
              marginTop: 12,
              opacity: 0.5,
            }}
          >
            {suppressed.map((s) => (
              <StatusTile key={s.id} segment={s} />
            ))}
          </div>
        </details>
      )}
      <p style={{ color: "#666", fontSize: 12, marginTop: 24 }}>
        Updated {new Date(data.envelope.generated_at).toLocaleTimeString()} ·
        Freshness {data.envelope.freshness_seconds}s ·
        Latency {data.envelope.query_latency_ms}ms
      </p>
    </div>
  );
}
