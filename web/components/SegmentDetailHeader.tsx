import Link from "next/link";

export function SegmentDetailHeader({
  segmentId,
  nativeUrl,
}: {
  segmentId: string;
  nativeUrl: string | null;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
      <div>
        <Link href="/" style={{ color: "#888", textDecoration: "none" }}>← Status board</Link>
        <h1 style={{ margin: "8px 0 0" }}>{segmentId}</h1>
      </div>
      {nativeUrl && (
        <a
          href={nativeUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            padding: "8px 16px",
            background: "#2563eb",
            color: "white",
            borderRadius: 6,
            textDecoration: "none",
            fontSize: 14,
          }}
        >
          Open in native tool ↗
        </a>
      )}
    </div>
  );
}
