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
