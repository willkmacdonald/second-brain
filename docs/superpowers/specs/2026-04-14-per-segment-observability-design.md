# Per-Segment Observability Design

**Date:** 2026-04-14
**Status:** Approved — ready for implementation planning
**Supersedes:** Phase 19.1 (KQL projection workaround for unified-schema model)
**Builds on:** Phase 17.4 (Backend API segment instrumentation, already shipped)

---

## Why This Exists

The Second Brain stack spans React Native (mobile), FastAPI (Container App), Azure AI Foundry (3 agents), Azure OpenAI (model inference), Cosmos DB, and external services (recipe scraping). Each of these surfaces telemetry in its own native shape — Foundry has agent-run timelines, Sentry has component stacks, Cosmos has RU consumption, App Insights has its own column model.

The current approach forces all of these into one schema (App Insights `AppTraces` / `AppExceptions` with our own `Properties` projections). Two failure modes follow:

1. **Information loss.** Native fields get coalesced into bare strings or dropped entirely. Symptom that surfaced this design: `HttpResponseError` showing as just the class name in App Insights queries because our KQL projection only pulled `Message` and `ExceptionType`, ignoring `OuterMessage`, `Details`, `OuterType`, `InnermostMessage`.
2. **Square-peg-round-hole growth.** Every new exception type, every new agent, every new segment adds new columns to the unified schema. The schema grows; the projections grow; the loss surface grows.

This spec replaces the unified-schema approach with a per-segment-native approach. Each segment reports in its own shape. A small "spine" provides cross-cutting status (red/yellow/green per segment) and trace correlation across segments. Drilling into any segment opens a renderer that shows that segment's data in its native shape — no normalization, no lossy projections.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         MOBILE (Expo)                           │
│                       Status Board UI                           │
│                                                                 │
│   [Mobile UI 🟢] [Capture 🟢] [API 🟢] [Classifier 🟢]          │
│   [Admin 🟡]    [Investigation 🟢] [Cosmos 🟢] [External 🟢]   │
│                                                                 │
│              tap red/yellow tile → deep link                    │
│                          ↓                                      │
└─────────────────────────────────────┬───────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────┐
│                       WEB SPINE UI  │  (Container App, served)  │
│                                                                 │
│  ┌───────────────┐   ┌─────────────────────────────────────┐   │
│  │ Status Board  │   │ Segment Detail (8 native shapes)    │   │
│  │ (mirrors      │   │  - Backend API: AppExceptions table │   │
│  │  mobile)      │   │  - Classifier: agent run timeline    │   │
│  │               │   │  - Foundry: Foundry runs detail     │   │
│  │               │   │  - Sentry: event detail             │   │
│  │               │   │  - Cosmos: diagnostic logs          │   │
│  │               │   │  + "Open in [Native Tool]" link     │   │
│  └───────────────┘   └─────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
┌─────────────────────────────────┼───────────────────────────────┐
│                   SPINE BACKEND │  (FastAPI, in Container App)  │
│                                                                 │
│   GET /api/spine/status          → all 8 tiles, current state   │
│   GET /api/spine/trace/{id}      → timeline for trace ID        │
│   GET /api/spine/segment/{id}    → segment-native detail        │
│   POST /api/spine/heartbeat      → push endpoint (5 segments)   │
│                                                                 │
│   Internal: pull adapters for 3 external segments               │
└──────┬──────────────────────────────────────────────────────────┘
       │
   ┌───┴──────────────────────────────────────────────────┐
   │                                                       │
   ▼ PUSH (5 segments)                ▼ PULL (3 segments)
                                                           
   - Backend API (FastAPI)            - Mobile UI (Sentry API)
   - Classifier agent                 - Cosmos DB (Azure Monitor)
   - Admin agent                      - Foundry (Foundry Runs API)
   - Investigation agent
   - External services (recipe)
```

### The 8 Segments

| # | Segment | Reporting | Native tool |
|---|---|---|---|
| 1 | Mobile UI | Pull (Sentry API) | sentry.io |
| 2 | Mobile capture pipeline | Pull (Sentry API) | sentry.io |
| 3 | Backend API gateway | Push (FastAPI) | Azure portal — App Insights |
| 4 | Classifier agent | Push (FastAPI host) | ai.azure.com — Foundry portal |
| 5 | Admin agent | Push (FastAPI host) | ai.azure.com — Foundry portal |
| 6 | Investigation agent | Push (FastAPI host) | ai.azure.com — Foundry portal |
| 7 | Cosmos DB | Pull (Azure Monitor Logs) | Azure portal — Cosmos blade |
| 8 | External services | Push (FastAPI) | Azure portal — App Insights |

---

## Spine Backend Contract

Four endpoints. This is the entire backend surface.

### `GET /api/spine/status`

Returns current state of all 8 segments. Powers both the mobile and web status boards.

```json
{
  "segments": [
    {
      "id": "backend_api",
      "name": "Backend API",
      "status": "green | yellow | red | stale",
      "last_updated": "2026-04-14T12:34:56Z",
      "headline": "Healthy" | "2 errors in last 1h" | "Stream timeout"
    }
    // ... 8 entries total
  ],
  "generated_at": "2026-04-14T12:35:00Z"
}
```

### `GET /api/spine/trace/{capture_trace_id}`

Returns the cross-segment timeline for a specific capture. Aggregates from each segment's native source filtered by trace ID.

```json
{
  "trace_id": "219b58c9-bed7-4be6-b115-f43714dc8920",
  "events": [
    {
      "segment_id": "mobile_capture",
      "timestamp": "2026-04-13T19:08:18.000Z",
      "status": "green",
      "headline": "Voice capture submitted"
    },
    {
      "segment_id": "backend_api",
      "timestamp": "2026-04-13T19:08:19.000Z",
      "status": "green",
      "headline": "POST /api/capture accepted"
    },
    {
      "segment_id": "classifier",
      "timestamp": "2026-04-13T19:08:19.297Z",
      "status": "red",
      "headline": "HttpResponseError (429)"
    }
  ]
}
```

Implementation: query each segment's native source in parallel, merge results, sort by timestamp. Cache responses for 30s.

### `GET /api/spine/segment/{segment_id}?trace_id={optional}&time_range={optional}`

Returns segment-native data. **No common schema** — each segment returns its native shape with a `schema` discriminator field that the web UI uses to pick the renderer.

```json
// For backend_api:
{
  "schema": "azure_monitor_app_insights",
  "app_exceptions": [/* native AppExceptions rows with OuterMessage, Details, etc */],
  "app_requests": [/* native AppRequests rows */]
}

// For classifier:
{
  "schema": "foundry_run",
  "agent_id": "asst_Fnjkq5RVrvdFIOSqbreAwxuq",
  "agent_runs": [/* native Foundry run objects */]
}

// For sentry-backed segments:
{
  "schema": "sentry_event",
  "events": [/* native Sentry event objects */],
  "breadcrumbs": [/* */]
}
```

### `POST /api/spine/heartbeat`

Push endpoint for segments that report from inside our code.

```json
// Request body:
{
  "segment_id": "classifier",
  "status": "green",
  "headline": "12 captures processed in last 5min",
  "native_payload": { /* whatever the segment wants stored */ }
}

// Response: 204 No Content
```

The `native_payload` is stored verbatim and returned as part of `/api/spine/segment/{id}` if no `trace_id` filter is supplied.

### Common schema is bounded forever

The only universal fields across all segments are:
- `status` enum: `green | yellow | red | stale`
- `headline` string: short, human-readable
- `last_updated` timestamp

Every other field is segment-specific and lives inside the native-shape `native_payload` (push) or response from the pull adapter. **There is intentionally NO `SegmentDetail` base class with shared fields beyond these three.** This is the architectural commitment that prevents sliding back into the unified-schema trap.

---

## Trace Correlation

For the `/api/spine/trace/{id}` endpoint to work across all segments, every segment must record `capture_trace_id` in a way the spine can query later.

**The contract:** *"When you ask my native API for events filtered by capture_trace_id, I will return them."*

How each segment fulfills this:

| Segment | Mechanism |
|---|---|
| Mobile UI | `Sentry.setTag("capture_trace_id", id)` — queryable via Sentry Issues API |
| Mobile capture pipeline | Same: Sentry tag + structured log sent to backend in capture request |
| Backend API | ContextVar → structured log → App Insights `Properties.capture_trace_id` (already done) |
| Classifier agent | Foundry thread/run metadata: `metadata={"capture_trace_id": id}` — queryable via Foundry Runs API |
| Admin agent | Same as Classifier |
| Investigation agent | Same as Classifier |
| Cosmos DB | `headers={"x-ms-client-request-id": id}` on every Cosmos call — queryable via Cosmos diagnostic logs |
| External services | Span tagged with `trace_id` + structured log to App Insights with `Properties.capture_trace_id` |

**Field name is universal:** `capture_trace_id`. **Encoding is segment-native.** The spine knows how to query each one because each pull adapter / each push payload format is segment-specific.

### Critical new integrations

1. **Foundry agent run metadata.** This is the most important new integration. Today, when an agent hangs, you can see your-side OTel timing out, but you can't pivot to "show me the Foundry run for trace X." Solution: pass `metadata={"capture_trace_id": trace_id}` when creating threads/runs. Then `/api/spine/segment/classifier?trace_id=X` calls Foundry's Runs API filtered by metadata.
2. **Cosmos diagnostic logs flowing to Log Analytics.** Sending the `client_request_id` header is free, but querying it requires Cosmos diagnostic settings to be enabled and routed to a Log Analytics workspace.
3. **Sentry tag (not context).** Sentry distinguishes "context" (rich, not indexed) from "tags" (indexed, queryable). For trace correlation, `capture_trace_id` MUST be a tag.

---

## Per-Segment Detail Views

Eight web renderers, one per segment. Each renders that segment's native data in its native shape. No common rendering base class.

### The pattern

```typescript
// Web UI: components/segment-detail/<SegmentName>Detail.tsx
function ClassifierDetail({ data, traceId }: Props) {
  // data is the raw Foundry-run JSON from /api/spine/segment/classifier
  return (
    <div>
      <Header
        title="Classifier Agent"
        nativeUrl={`https://ai.azure.com/build/agents/${data.agent_id}`}
      />
      <RunsList runs={data.agent_runs} highlightTraceId={traceId} />
    </div>
  );
}
```

Eight of these. Each ~100 lines. Each has its own visual idiom because each segment's data has its own shape.

### What each renderer shows

| Segment | Native shape rendered |
|---|---|
| Mobile UI / capture | Sentry events list (issue title, breadcrumbs, component stack), filterable by trace_id |
| Backend API | App Insights AppExceptions + AppRequests with NATIVE columns (OuterMessage, OuterType, Details, etc.) |
| Classifier / Admin / Investigation agents | Foundry run timeline: thread_id, run status, model, tokens, tool calls, step-by-step |
| Cosmos DB | Diagnostic logs (operation type, RU consumption, partition key, status, duration) + recent metrics |
| External services | Recipe scraping run log (URL, tier used, success/failure, duration, error class) |

### "Open in [Native Tool]" is first-class

Every renderer prominently surfaces a deep link to the native tool. This is the architectural commitment: **spine handles the common 80% of investigation; native tools handle the rest.** When the spine view doesn't have what you need, the link is right there.

### Backend adapter contract

```python
class SegmentAdapter(Protocol):
    async def fetch_detail(
        self,
        trace_id: str | None,
        time_range: str = "1h"
    ) -> dict:
        """Return native-shape data for this segment.

        The returned dict MUST include a 'schema' field that the
        web UI uses to pick the renderer. Everything else is
        segment-specific and not normalized.
        """
```

Push adapters store the most recent `native_payload` from heartbeats. Pull adapters call the native source live (no background polling for pull segments).

---

## Phased Rollout

Vertical slices. Each phase ships end-to-end. If you stop after Phase 1, you have a working spine for one segment.

### Phase 1 — Spine foundation + Backend API segment

**Goal:** Spine backend exists. Backend API segment fully integrated. Mobile shows one tile. Web shows one detail view. Phase 19.1's KQL projection work is absorbed.

**Deliverables:**
- New `spine` package in backend exposing 4 endpoints
- In-memory KV store for heartbeats (1 entry: `backend_api`)
- Backend API push: FastAPI middleware sends heartbeat every 30s
- Pull from App Insights for trace-filtered queries (extends KQL templates with OuterMessage / Details / OuterType / InnermostMessage projections from 19.1)
- New web app (framework TBD) with status board + Backend API detail renderer
- Mobile Status screen extended with one new tile
- Mobile tile tap → opens web spine URL via `Linking.openURL()`
- Trace correlation already in place for this segment (no new work)

**Estimated scope:** ~2 weeks

### Phase 2 — Three agent segments (Classifier, Admin, Investigation)

**Goal:** All three Foundry agents report through the spine. Foundry trace correlation working. Web has 3 new detail renderers (Foundry-run shape).

**Deliverables:**
- Push heartbeat from each agent's wrapper code (3 new tiles)
- Foundry agent run metadata: every thread/run created with `metadata={"capture_trace_id": trace_id}`
- Pull adapter that calls Foundry Runs API filtered by metadata
- 1 web renderer for Foundry-run shape (reused across all 3 agents)
- Mobile gets 3 new tiles
- Existing Phase 17.4 health-check + warmup logic continues; just adds spine as additional consumer

**Estimated scope:** ~1.5 weeks

### Phase 3 — External services + Cosmos

**Goal:** Two more segments. One push, one pull.

**Deliverables:**
- External services push: wrap recipe scraping with heartbeat-on-completion
- Cosmos pull adapter: Azure Monitor Logs query against Cosmos diagnostic logs
- Cosmos `client_request_id` wiring: pass `trace_id` as header on every Cosmos call
- 2 new web renderers
- 2 new mobile tiles

**Estimated scope:** ~1 week

### Phase 4 — Mobile + Sentry pull adapters + MCP migration

**Goal:** Final two segments. MCP tool migrates to spine.

**Deliverables:**
- Sentry pull adapter (filtered for "Mobile UI" vs "Mobile capture" by tag/project)
- Wire `Sentry.setTag("capture_trace_id", id)` on mobile side at trace creation
- 1 new web renderer (Sentry event shape, used for both mobile segments)
- 2 new mobile tiles
- Refactor `mcp/server.py` so each tool calls `/api/spine/*` instead of querying App Insights directly. MCP becomes a thin HTTP client over the spine.

**Estimated scope:** ~1 week

### Total: ~5.5 weeks across 4 phases

---

## Existing Planning Artifacts

### Phase 17.4 — Stays as-is

Phase 17.4 (already shipped, 2026-04-13) delivered parameterized OTel middleware (`AuditAgentMiddleware(agent_name=...)`), active `/health` checks, warmup self-heal, Azure Monitor alerts. All of this is preserved and becomes the **Backend API segment's existing instrumentation**. Phase 1 of this design adds the spine integration on top — no removals.

### Phase 19.1 — Cancelled as standalone, absorbed into Phase 1

Phase 19.1 (planned, not executed) was a workaround for the unified-schema problem — adding `OuterMessage` / `Details` / etc. projections to the existing KQL templates. In the new architecture, that work is still needed (the Backend API segment's pull adapter must surface real error detail), but it's done as part of Phase 1 of this design rather than as a separate phase.

**Action for Phase 19.1:**
- Mark Phase 19.1 as cancelled in ROADMAP.md with a note pointing to this spec
- Phase 19.1's plan (`19.1-01-PLAN.md`) is preserved as a reference for the KQL projection work that Phase 1 will absorb
- The Phase 19.1 directory stays in place; the work isn't lost, just rehomed

---

## Risks

1. **Foundry metadata field availability.** This design assumes `thread.metadata` and `run.metadata` accept arbitrary dict values and that `list_runs()` supports filtering by metadata. The Foundry SDK is moving fast (note the AI Foundry framework GA migration in `docs/ai-foundry-framework-GA-migration.md`). If `metadata` filtering isn't supported, Phase 2 needs a fallback (likely: query Foundry runs without filter, post-filter in adapter, accepting performance cost). Verify during Phase 2 research.
2. **Cosmos diagnostic logs latency.** Diagnostic logs flow to Log Analytics with 5–10 minute lag. Trace timelines for Cosmos events will lag real-time. Acceptable for retrospective investigation; not real-time.
3. **Web app deploy story.** No web frontend exists in this stack today. Phase 1 introduces one. Options to evaluate during Phase 1 planning: serve static files from existing FastAPI Container App, separate Container App, or Azure Static Web Apps.
4. **Heartbeat staleness during deploys.** When deploying a new Container App revision, push segments stop heartbeating for 30–60s during cutover. Spine will show them as `stale`. Acceptable for v1; revisit if false positives become annoying.
5. **Mobile-to-web deep linking on iOS.** `Linking.openURL()` opens in mobile Safari. Web spine must be mobile-responsive enough to be usable from a phone. Constraint, not a blocker.

---

## Decisions Deferred to Phase Planning

- Web framework choice (Next.js vs Astro vs plain React)
- Heartbeat KV storage (in-memory dict vs Cosmos container vs Azure Cache for Redis)
- Status board layout details (grid vs list, color choices, icons)
- Polling interval for status board (mobile + web)
- Authentication on the spine endpoints (likely reuses existing API key auth)

---

## Decisions Locked by This Spec

- Architecture: backend + 2 frontends, hybrid push/pull, no common detail schema
- 8 segments at the medium-grain boundary (the specific list above)
- Trace correlation via `capture_trace_id` propagated through every segment using each segment's native facility
- Spine-level common schema is exactly `{status, headline, last_updated}` — bounded forever
- 4-phase rollout, vertical slice per phase
- Phase 19.1 absorbed into Phase 1
- Phase 17.4 preserved as Backend API segment instrumentation
- MCP tool migrates to spine in Phase 4
