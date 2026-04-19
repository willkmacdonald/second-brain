import Link from "next/link";
import { spine } from "@/lib/spine";
import { AppInsightsDetail } from "@/components/renderers/AppInsightsDetail";
import { FoundryRunDetail } from "@/components/renderers/FoundryRunDetail";
import { CosmosDiagnosticDetail } from "@/components/renderers/CosmosDiagnosticDetail";
import { MobileTelemetryDetail } from "@/components/renderers/MobileTelemetryDetail";
import { LedgerSection } from "@/components/LedgerSection";
import { LocalTime } from "@/components/LocalTime";
import { SegmentDetailHeader } from "@/components/SegmentDetailHeader";
import type {
  CorrelationKind,
  SegmentDetailResponse,
  SegmentLedgerResponse,
} from "@/lib/types";

export const dynamic = "force-dynamic";

const VALID_CORRELATION_KINDS = new Set<CorrelationKind>([
  "capture",
  "thread",
  "request",
  "crud",
]);

function parseCorrelationKind(value: string | undefined): CorrelationKind | undefined {
  if (!value || !VALID_CORRELATION_KINDS.has(value as CorrelationKind)) {
    return undefined;
  }
  return value as CorrelationKind;
}

function parseTimeRangeSeconds(value: string | undefined): number | undefined {
  if (!value) return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined;
  }
  return Math.floor(parsed);
}

export default async function SegmentPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams?: {
    correlation_kind?: string;
    correlation_id?: string;
    time_range_seconds?: string;
  };
}) {
  const correlationKind = parseCorrelationKind(searchParams?.correlation_kind);
  const correlationId =
    correlationKind && searchParams?.correlation_id
      ? searchParams.correlation_id
      : undefined;
  const timeRangeSeconds = parseTimeRangeSeconds(searchParams?.time_range_seconds);

  let detail: SegmentDetailResponse;
  try {
    detail = await spine.segmentDetail(params.id, {
      correlation_kind: correlationKind,
      correlation_id: correlationId,
      time_range_seconds: timeRangeSeconds,
    });
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

  // Ledger fetch is non-fatal: the native-telemetry section below still
  // renders if the /ledger/segment route is unavailable (graceful degradation
  // during partial deploys, env misconfig, etc.).
  let ledger: SegmentLedgerResponse | null = null;
  try {
    ledger = await spine.segmentLedger(params.id, {
      window_seconds: 3600,
      limit: 50,
    });
  } catch (e) {
    console.warn(`ledger fetch failed for segment ${params.id}:`, e);
  }

  const schema = detail.data.schema;

  return (
    <main style={{ padding: 24 }}>
      <SegmentDetailHeader
        segmentId={params.id}
        nativeUrl={detail.envelope.native_url ?? null}
      />
      {correlationKind && correlationId && (
        <p style={{ color: "#888", fontSize: 13, marginTop: 16 }}>
          Filtered to {correlationKind}{" "}
          <code>{correlationId}</code>.{" "}
          <Link
            href={`/correlation/${correlationKind}/${encodeURIComponent(correlationId)}`}
            style={{ color: "#9ecbff" }}
          >
            View correlation timeline
          </Link>
          .
        </p>
      )}

      {ledger ? (
        <LedgerSection
          segmentId={params.id}
          rows={ledger.rows}
          mode={ledger.mode}
          emptyStateReason={ledger.empty_state_reason}
        />
      ) : (
        <p style={{ color: "#666", fontSize: 12, marginTop: 24 }}>
          Ledger unavailable. Falling through to native diagnostics.
        </p>
      )}

      <h2 style={{ marginTop: 32 }}>Diagnostics (native telemetry)</h2>
      {schema === "azure_monitor_app_insights" ? (
        <AppInsightsDetail data={detail.data as never} />
      ) : schema === "foundry_run" ? (
        <FoundryRunDetail data={detail.data as never} />
      ) : schema === "azure_monitor_cosmos" ? (
        <CosmosDiagnosticDetail data={detail.data as never} />
      ) : schema === "mobile_telemetry_combined" ? (
        <MobileTelemetryDetail data={detail.data as never} />
      ) : (
        <p>No renderer registered for schema: <code>{schema}</code></p>
      )}
      <p style={{ color: "#666", fontSize: 12, marginTop: 24 }}>
        Fetched <LocalTime iso={detail.envelope.generated_at} /> ·
        Latency {detail.envelope.query_latency_ms}ms
      </p>
    </main>
  );
}
