// Server-side spine client. Uses API key from process.env (server-only).
// NEVER imports into client components.

import "server-only";

import type {
  StatusBoardResponse,
  CorrelationResponse,
  SegmentDetailResponse,
  CorrelationKind,
} from "./types";

async function spineFetch<T>(path: string): Promise<T> {
  // Validate lazily — module-level throw breaks next build's "Collecting page
  // data" pass, which imports page modules even on force-dynamic routes.
  // The post-deploy health check polls the root page within ~30s of a deploy,
  // so a misconfigured Container App still fails the deploy gate, not silently.
  const BASE = process.env.SPINE_API_URL;
  const KEY = process.env.SPINE_API_KEY;
  if (!BASE || !KEY) {
    throw new Error("SPINE_API_URL and SPINE_API_KEY env vars are required");
  }

  const res = await fetch(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${KEY}` },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`spine ${res.status}: ${await res.text()}`);
  }
  return (await res.json()) as T;
}

export const spine = {
  status: () => spineFetch<StatusBoardResponse>("/api/spine/status"),
  correlation: (kind: CorrelationKind, id: string) =>
    spineFetch<CorrelationResponse>(`/api/spine/correlation/${kind}/${encodeURIComponent(id)}`),
  segmentDetail: (id: string, params?: { correlation_kind?: CorrelationKind; correlation_id?: string; time_range_seconds?: number }) => {
    const search = new URLSearchParams();
    if (params?.correlation_kind) search.set("correlation_kind", params.correlation_kind);
    if (params?.correlation_id) search.set("correlation_id", params.correlation_id);
    if (params?.time_range_seconds) search.set("time_range_seconds", String(params.time_range_seconds));
    const qs = search.toString();
    return spineFetch<SegmentDetailResponse>(`/api/spine/segment/${id}${qs ? `?${qs}` : ""}`);
  },
};
