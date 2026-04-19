// Mirrors backend Pydantic models in backend/src/second_brain/spine/models.py
// Keep in sync manually (small contract surface, infrequent changes).

export type SegmentStatus = "green" | "yellow" | "red" | "stale";
export type CorrelationKind = "capture" | "thread" | "request" | "crud";

export interface RollupInfo {
  suppressed: boolean;
  suppressed_by: string | null;
  raw_status: SegmentStatus;
}

export interface SegmentStatusResponse {
  id: string;
  name: string;
  status: SegmentStatus;
  headline: string;
  last_updated: string;
  freshness_seconds: number;
  host_segment: string | null;
  rollup: RollupInfo;
}

export interface ResponseEnvelope {
  generated_at: string;
  freshness_seconds: number;
  partial_sources: string[];
  query_latency_ms: number;
  native_url?: string | null;
  cursor?: string | null;
}

export interface StatusBoardResponse {
  segments: SegmentStatusResponse[];
  envelope: ResponseEnvelope;
}

export interface CorrelationEvent {
  segment_id: string;
  timestamp: string;
  status: SegmentStatus;
  headline: string;
}

export interface CorrelationResponse {
  correlation_kind: CorrelationKind;
  correlation_id: string;
  events: CorrelationEvent[];
  envelope: ResponseEnvelope;
}

export interface SegmentDetailResponse {
  data: { schema: string; native_url?: string;[key: string]: unknown };
  envelope: ResponseEnvelope;
}

// ---------------------------------------------------------------------------
// Phase 19.2 — Transaction ledger types
// Mirrors TransactionLedgerRow / SegmentLedgerResponse / TransactionEvent /
// TransactionPathResponse in backend/src/second_brain/spine/models.py.
// Pydantic `Optional[T] = None` → TypeScript `T | null` (JSON null on the
// wire, not undefined).
// ---------------------------------------------------------------------------

export type SegmentLedgerMode = "transactional" | "native_only";

export type WorkloadOutcome = "success" | "failure" | "degraded";

export interface TransactionLedgerRow {
  segment_id: string;
  timestamp: string;
  operation: string;
  outcome: WorkloadOutcome;
  duration_ms: number;
  correlation_kind: CorrelationKind | null;
  correlation_id: string | null;
  error_class: string | null;
}

export interface SegmentLedgerResponse {
  segment_id: string;
  mode: SegmentLedgerMode;
  empty_state_reason: string | null;
  rows: TransactionLedgerRow[];
  envelope: ResponseEnvelope;
}

export interface TransactionEvent {
  segment_id: string;
  timestamp: string;
  status: SegmentStatus;
  operation: string | null;
  outcome: WorkloadOutcome | null;
  duration_ms: number | null;
  error_class: string | null;
  headline: string;
}

export interface TransactionPathResponse {
  correlation_kind: CorrelationKind;
  correlation_id: string;
  events: TransactionEvent[];
  missing_required: string[];
  present_optional: string[];
  unexpected: string[];
  envelope: ResponseEnvelope;
}
