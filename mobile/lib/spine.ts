import { API_BASE_URL, API_KEY } from "../constants/config";

export type SegmentStatus = "green" | "yellow" | "red" | "stale";

export interface SpineSegment {
  id: string;
  name: string;
  status: SegmentStatus;
  headline: string;
  last_updated: string;
  freshness_seconds: number;
  rollup: { suppressed: boolean; suppressed_by: string | null; raw_status: SegmentStatus };
}

export interface SpineStatus {
  segments: SpineSegment[];
  envelope: { generated_at: string; query_latency_ms: number };
}

export async function fetchSpineStatus(): Promise<SpineStatus> {
  const res = await fetch(`${API_BASE_URL}/api/spine/status`, {
    headers: { Authorization: `Bearer ${API_KEY}` },
  });
  if (!res.ok) {
    throw new Error(`spine status ${res.status}`);
  }
  return (await res.json()) as SpineStatus;
}

// Web spine ingress URL — set via env in production.
// EXPO_PUBLIC_SPINE_WEB_URL=https://spine-web.willmacdonald.com
export const SPINE_WEB_URL = process.env.EXPO_PUBLIC_SPINE_WEB_URL ?? "";
