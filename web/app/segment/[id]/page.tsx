import { spine } from "@/lib/spine";
import { AppInsightsDetail } from "@/components/renderers/AppInsightsDetail";
import { SegmentDetailHeader } from "@/components/SegmentDetailHeader";
import type { SegmentDetailResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SegmentPage({ params }: { params: { id: string } }) {
  let detail: SegmentDetailResponse;
  try {
    detail = await spine.segmentDetail(params.id);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return (
      <main style={{ padding: 24 }}>
        <SegmentDetailHeader segmentId={params.id} nativeUrl={null} />
        <p style={{ color: "#c89010", marginTop: 24 }}>
          No data available for this segment.
        </p>
        <p style={{ color: "#666", fontSize: 12, marginTop: 8 }}>{message}</p>
      </main>
    );
  }

  const schema = detail.data.schema;

  return (
    <main style={{ padding: 24 }}>
      <SegmentDetailHeader
        segmentId={params.id}
        nativeUrl={detail.envelope.native_url ?? null}
      />
      {schema === "azure_monitor_app_insights" ? (
        <AppInsightsDetail data={detail.data as never} />
      ) : (
        <p>No renderer registered for schema: <code>{schema}</code></p>
      )}
      <p style={{ color: "#666", fontSize: 12, marginTop: 24 }}>
        Fetched {new Date(detail.envelope.generated_at).toLocaleString()} ·
        Latency {detail.envelope.query_latency_ms}ms
      </p>
    </main>
  );
}
