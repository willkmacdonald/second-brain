# Per-Segment Observability Design

**Date:** 2026-04-14
**Revision:** 2 (architectural revision after critical review)
**Status:** Pending re-review
**Supersedes:** Phase 19.1 (KQL projection workaround for unified-schema model)
**Builds on:** Phase 17.4 (Backend API segment instrumentation, already shipped)

---

## Why This Exists

The Second Brain stack spans React Native (mobile), FastAPI (Container App), Azure AI Foundry (3 agents), Azure OpenAI (model inference), Cosmos DB, and external services (recipe scraping). Each surfaces telemetry in its own native shape — Foundry has agent-run timelines, Sentry has component stacks, Cosmos has RU consumption, App Insights has its own column model.

The current approach forces all of these into one schema (App Insights `AppTraces`/`AppExceptions` with our own `Properties` projections). Two failure modes follow:

1. **Information loss.** Native fields get coalesced into bare strings or dropped entirely. Symptom that surfaced this design: `HttpResponseError` showing as just the class name in App Insights queries because our KQL projection only pulled `Message` and `ExceptionType`, ignoring `OuterMessage`, `Details`, `OuterType`, `InnermostMessage`.
2. **Square-peg-round-hole growth.** Every new exception type, agent, or segment adds new columns. The schema grows; projections grow; loss surface grows.

This spec replaces the unified-schema approach with a per-segment-native approach. Each segment reports in its own shape. A small "spine" provides cross-cutting status (red/yellow/green per segment), correlation across segments, and operational history. Drilling into any segment opens a renderer that shows that segment's data in its native shape — no normalization, no lossy projections.

---

## Architectural Principles (locked)

These are the non-negotiable principles. Everything else is implementation detail open to revision.

1. **No segment-detail normalization.** Each segment's detail is rendered in its native shape. Reusing a renderer across segments that genuinely share a native shape (e.g., Foundry agents) is fine and expected. Forcing genuinely-different shapes into a common model is the failure mode.
2. **Native systems own native data.** The spine stores its own operational state (status, evaluator outputs, event history, correlation records) but never duplicates native payloads. Detail views fetch from native sources at query time.
3. **Native tools are first-class drill-downs.** Every detail view surfaces an "Open in [Native Tool]" link. The spine handles the common 80%; native tools handle the long tail.
4. **Health is layered.** A segment's status reflects multiple signals (liveness, readiness, recent workload outcomes), not just "did we hear from it recently."
5. **Correlation is generalized.** The spine supports multiple correlation kinds (capture, thread, request, CRUD), not just capture flows.

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
└─────────────────────────────────────┬───────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────┐
│                       WEB SPINE UI  │  (server-rendered)        │
│                                                                 │
│  ┌───────────────┐   ┌─────────────────────────────────────┐   │
│  │ Status Board  │   │ Segment Detail (renderer per shape) │   │
│  └───────────────┘   └─────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────┘
                                  │ (auth via session cookie set
                                  │  from API key, not embedded)
┌─────────────────────────────────┼───────────────────────────────┐
│                   SPINE BACKEND │  (FastAPI, in Container App)  │
│                                                                 │
│   POST /api/spine/ingest         → typed event ingest (push)    │
│   GET  /api/spine/status         → all 8 tiles, evaluated       │
│   GET  /api/spine/correlation/{kind}/{id}  → cross-segment view │
│   GET  /api/spine/segment/{id}   → segment-native detail        │
│                                                                 │
│   Internal: pull adapters for 3 external segments               │
│   Internal: status evaluator runs every 30s                     │
└──────┬──────────────────────────────────────────────────────────┘
       │
   ┌───┴──────────────────────────────────────────────────┐
   │                                                       │
   ▼ PUSH (5 segments)                ▼ PULL (3 segments)
                                                           
   - Backend API (FastAPI)            - Mobile UI (Sentry + telemetry)
   - Classifier agent                 - Mobile capture (Sentry + telemetry)
   - Admin agent                      - Cosmos DB (Azure Monitor)
   - Investigation agent              - Foundry (run_id/thread_id join)
   - External services (recipe)
```

### The 8 Segments

| # | Segment | Reporting | Native tool |
|---|---|---|---|
| 1 | Mobile UI | Pull (Sentry + backend telemetry) | sentry.io + Azure portal |
| 2 | Mobile capture pipeline | Pull (Sentry + backend telemetry) | sentry.io + Azure portal |
| 3 | Backend API gateway | Push (FastAPI) | Azure portal — App Insights |
| 4 | Classifier agent | Push (FastAPI host) | ai.azure.com — Foundry portal |
| 5 | Admin agent | Push (FastAPI host) | ai.azure.com — Foundry portal |
| 6 | Investigation agent | Push (FastAPI host) | ai.azure.com — Foundry portal |
| 7 | Cosmos DB | Pull (Azure Monitor Logs) | Azure portal — Cosmos blade |
| 8 | External services | Push (FastAPI) | Azure portal — App Insights |

---

## Spine Backend Contract

### Single typed ingest endpoint

`POST /api/spine/ingest` accepts a discriminated event type. One endpoint, multiple semantics.

```json
{
  "segment_id": "classifier",
  "event_type": "liveness" | "readiness" | "workload",
  "timestamp": "2026-04-14T12:34:56Z",
  "payload": { /* shape varies by event_type, see below */ }
}
```

**`liveness` events** — "I exist and my process is up."
```json
{ "segment_id": "classifier", "event_type": "liveness",
  "timestamp": "...", "payload": { "instance_id": "abc-123" } }
```
Emitted by every segment on a heartbeat (~30s). Evaluator marks segment `stale` if last liveness event > 2× expected interval.

**`readiness` events** — "My dependencies are reachable."
```json
{ "segment_id": "classifier", "event_type": "readiness",
  "timestamp": "...", "payload": {
    "checks": [
      { "name": "foundry_client", "status": "ok" },
      { "name": "azure_openai", "status": "ok" }
    ]
  }}
```
Emitted on a slower interval (~60s) or on dependency change. Evaluator can downgrade from `green` to `yellow` if any readiness check fails.

**`workload` events** — "I just finished an operation; here's how it went."
```json
{ "segment_id": "classifier", "event_type": "workload",
  "timestamp": "...", "payload": {
    "operation": "classify_capture",
    "outcome": "success" | "failure" | "degraded",
    "duration_ms": 1234,
    "correlation_kind": "capture",
    "correlation_id": "219b58c9-...",
    "error_class": "HttpResponseError"  // optional, only on failure
  }}
```
Emitted per-operation. This is the source of truth for "is the segment actually doing useful work successfully" — separate from liveness/readiness.

### Read endpoints

`GET /api/spine/status` — Returns evaluated status for all 8 segments. Powered by the evaluator (see Status Evaluators section).
```json
{
  "segments": [
    {
      "id": "backend_api",
      "name": "Backend API",
      "status": "green | yellow | red | stale",
      "headline": "12 requests, 0 errors in last 5min",
      "last_updated": "2026-04-14T12:34:56Z",
      "freshness_seconds": 12,
      "host_segment": null,
      "rollup": { "suppressed": false, "suppressed_by": null }
    }
  ],
  "envelope": { "generated_at": "...", "evaluator_version": "1.0" }
}
```

`GET /api/spine/correlation/{kind}/{id}` — Cross-segment view for any correlation type.
```
GET /api/spine/correlation/capture/219b58c9-bed7-4be6-b115-f43714dc8920
GET /api/spine/correlation/thread/thr_abc123
GET /api/spine/correlation/request/req_xyz789
```
Returns chronological events from each segment that touched that correlation_id. UI can present this as an "incident timeline" but the storage primitive is just correlation events.

`GET /api/spine/segment/{id}?correlation_kind={k}&correlation_id={id}&time_range={r}` — Native-shape detail.

### Response envelope (shared metadata)

Every spine response includes an `envelope` object:
```json
{
  "envelope": {
    "generated_at": "2026-04-14T12:35:00Z",
    "freshness_seconds": 12,           // age of most-stale data point
    "partial_sources": [],              // segments/sources that failed to fetch
    "query_latency_ms": 234,
    "native_url": "https://...",        // segment-detail responses only
    "cursor": null                      // for paginated responses
  },
  "data": { /* segment-specific shape */ }
}
```

The envelope is itself a contract — but it's about *delivery metadata*, not about *segment content*. Adding a new segment doesn't change the envelope. Changing a segment's native shape doesn't change the envelope.

**What's explicitly NOT in the envelope:**
- Segment-content fields (error counts, timestamps of segment events, native data of any kind)
- Correlation IDs (those live in segment data and correlation events)
- Status enum values (those live in segment status responses)

---

## Storage Model

The spine stores its own operational state in Cosmos DB. **It never duplicates native detail.** Native systems (Sentry, App Insights, Foundry, Cosmos diagnostic logs) remain the source of truth for their own data; the spine fetches live for detail views.

### Cosmos containers (4 new)

**`spine_segment_state`** — Current state per segment.
- Partition key: `/segment_id`
- Document per segment (8 total). Upserted on every status evaluation.
- Schema: `{ segment_id, status, headline, last_updated, evaluator_inputs }`
- TTL: none (always overwritten)

**`spine_events`** — Push event history (liveness, readiness, workload).
- Partition key: `/segment_id`
- One document per ingested event
- Schema: `{ segment_id, event_type, timestamp, payload, ingested_at }`
- TTL: 14 days (enough for flapping detection and recent-history investigation)

**`spine_status_history`** — Status snapshots over time.
- Partition key: `/segment_id`
- One document per evaluator run that produced a status change
- Schema: `{ segment_id, status, prev_status, headline, evaluator_outputs, timestamp }`
- TTL: 30 days (enough for "was this red 2 weeks ago?")

**`spine_correlation`** — Correlation envelope records.
- Partition key: `/correlation_kind`
- Composite secondary key: `correlation_id`
- One document per (segment, correlation_id) tuple
- Schema: `{ correlation_kind, correlation_id, segment_id, timestamp, status, headline, parent_correlation_kind, parent_correlation_id }`
- TTL: 30 days
- Used to power `/api/spine/correlation/{kind}/{id}` without re-querying every segment's native source

### What stays in native systems

| Data | Native system |
|---|---|
| Full Sentry events (stack traces, breadcrumbs, component info) | sentry.io |
| Full App Insights AppExceptions/AppRequests rows | App Insights workspace |
| Full Foundry agent run timelines (model, tokens, tool calls, steps) | Foundry portal / Runs API |
| Cosmos diagnostic logs (RU consumption, partition stats) | Cosmos diagnostic logs in Log Analytics |
| Original capture text, errand items, etc. | Cosmos data containers (existing) |

The spine's storage holds only what it needs to:
- Render the status board without calling 8 native sources every 5 seconds
- Show recent flapping/history without depending on native query latency
- Power the correlation view by knowing which segments touched a given correlation_id

For raw detail, the spine always fetches live.

---

## Correlation Model

Generalize beyond `capture_trace_id`. The spine supports multiple correlation kinds.

### Correlation envelope

Every correlatable event carries:
```
correlation_kind: "capture" | "thread" | "request" | "crud" | null
correlation_id: string | null
parent_correlation_kind: string | null  (optional)
parent_correlation_id: string | null    (optional)
```

**Kinds:**
- `capture` — A user-initiated capture flow (existing `capture_trace_id`)
- `thread` — An investigation agent thread (Foundry thread_id; CRITICAL because investigation flows are thread-shaped, not capture-shaped)
- `request` — A standalone backend request not tied to a capture (CRUD operations on `/api/inbox`, `/api/errands`, `/api/tasks`)
- `crud` — Same as `request` but specifically for inbox/errand/task mutations (separate kind because these are the silent failures from `docs/instrumentation.md` lines 71+89)
- `null` — Event has no correlation (background tasks, scheduled jobs)

**"Incident" is a UI concept, not a storage primitive.** The UI groups correlation events under labels (e.g., "Investigation thread X timed out across 3 segments") but storage just records correlation events.

### Per-segment recording

How each segment records its correlation IDs:

| Segment | Mechanism |
|---|---|
| Mobile UI | `Sentry.setTag("correlation_id", id)` + `correlation_kind` tag; backend telemetry includes it in payload |
| Mobile capture | Same as Mobile UI; `correlation_kind: "capture"` |
| Backend API | ContextVar → structured log → App Insights `Properties.correlation_kind` + `Properties.correlation_id` (extends existing `capture_trace_id` work) |
| Classifier agent | `run_id` and `foundryThreadId` are already persisted server-side and recorded on OTel spans; spine joins on these (Foundry metadata filtering is optional polish, not the critical path) |
| Admin agent | Same as Classifier |
| Investigation agent | Same as Classifier; primary `correlation_kind: "thread"` |
| Cosmos DB | `client_request_id` header set per call; queryable via Cosmos diagnostic logs |
| External services | Span tagged + structured log to App Insights with `Properties.correlation_kind` + `Properties.correlation_id` |

**Foundry correlation strategy (revised):** Use `run_id` and `foundryThreadId` as the primary join keys. Both are already generated by the backend, persisted, and recorded on spans. The spine queries by these IDs against App Insights spans (which we own) rather than depending on Foundry metadata filtering (vendor feature, unverified). If Foundry metadata filtering becomes available and stable, it's an optimization layered on top, not a precondition.

---

## Status Evaluators

Per-segment evaluators that run every 30s and produce a status enum. The evaluator is the *only* thing that decides a segment's status — push events are inputs, not status declarations.

### Hard rules (locked)

**Status precedence:** `red > yellow > green > stale`. If multiple signals would produce different statuses, the highest wins.

**No-data behavior:** A segment with no liveness event in 2× expected interval is `stale`, regardless of other signals. `stale` is distinct from `red` — it means "we don't know," not "we know it's broken."

**Source-lag handling:** Segments with known data lag (Cosmos diagnostic logs, ~5-10min) have an `acceptable_lag_seconds` field on their evaluator config. The evaluator does not flag staleness within that window. The status board displays `freshness_seconds` so users can see real data age.

**Deploy suppression:** During Container App revision cutovers, push segments stop heartbeating for 30-60s. The evaluator suppresses `stale` transitions for any segment whose `host_segment` is in a known deploy state. Deploy state is detected via Azure Monitor's revision-status API and cached for 5 minutes.

### Per-segment evaluator config

Each segment declares:
```python
EvaluatorConfig(
    segment_id="classifier",
    liveness_interval_seconds=30,
    workload_window_seconds=300,
    yellow_thresholds={
        "workload_failure_rate": 0.10,    # >10% failures in window → yellow
        "readiness_check_failed": True,    # any readiness failure → yellow
    },
    red_thresholds={
        "workload_failure_rate": 0.50,    # >50% failures → red
        "consecutive_failures": 3,         # 3 consecutive failures → red
    },
    acceptable_lag_seconds=0,             # this segment has no inherent lag
    host_segment="container_app",         # for rollup
)
```

Evaluator config lives in code (one Python module). New segment thresholds require a code change — intentional. Don't want config-driven evaluators that drift.

---

## Rollup and Suppression

When a `host_segment` (e.g., the Container App) goes red, dependent segments running on it (Backend API, all 3 agents, External services) often go red too — but the *root cause* is the host, not each dependent.

### Hard rules (locked)

**Suppression is computed at query time, not stored.** The raw status of every segment is preserved in `spine_segment_state`. The `/api/spine/status` endpoint applies suppression rules when constructing the response.

**Suppression rule:** If segment X has `host_segment: "Y"` AND segment Y's current status is `red`, then segment X's response is annotated:
```json
{
  "id": "classifier",
  "status": "red",
  "rollup": {
    "suppressed": true,
    "suppressed_by": "container_app",
    "raw_status": "red"
  }
}
```
The UI (mobile + web status board) groups suppressed segments under the root cause and shows them collapsed by default. A "show suppressed" toggle reveals them.

**Annotation, not suppression, when the host is `yellow`.** A yellow host doesn't fully explain a red dependent — the dependent might have its own problem. UI still shows the dependent's status but with a "host is degraded" annotation.

**Independent segments don't participate in rollup.** Cosmos DB, External services, Mobile UI, and Mobile capture have `host_segment: null` because their health is genuinely independent of the Container App (Cosmos and Sentry are external; mobile runs on a separate device). They're never suppressed by Container App outages.

### Host segment registry

| Segment | host_segment |
|---|---|
| Backend API | `container_app` |
| Classifier | `container_app` |
| Admin agent | `container_app` |
| Investigation agent | `container_app` |
| External services | `container_app` |
| Cosmos DB | `null` |
| Mobile UI | `null` |
| Mobile capture | `null` |

Note: `container_app` is itself a logical "segment" we add to the model for rollup purposes (status comes from Azure Monitor's revision/replica health). It's not in the 8-segment list because it's not user-facing — it's an internal node for rollup math.

---

## Per-Segment Detail Views

Renderers per *native shape*, not per segment. Segments that share a shape share a renderer (e.g., all 3 Foundry agents use one `FoundryRunDetail` renderer).

### Renderer/segment mapping

| Renderer | Segments using it | Source |
|---|---|---|
| `AppInsightsDetail` | Backend API, External services | App Insights AppExceptions + AppRequests |
| `FoundryRunDetail` | Classifier, Admin, Investigation | Foundry Runs API + App Insights spans (joined by run_id/thread_id) |
| `MobileTelemetryDetail` | Mobile UI, Mobile capture | Sentry events + backend `/api/telemetry` payload history |
| `CosmosDiagnosticDetail` | Cosmos DB | Azure Monitor Logs (Cosmos diagnostic logs) |

Four renderers, eight segments. Reuse where shapes match. New segment with a new shape requires a new renderer — that's the principle.

### Mobile segment data sources (revised)

Mobile is NOT Sentry-only. Three data sources combined:

1. **Sentry** — crashes, render failures, ErrorBoundary catches (already wired in `mobile/lib/sentry.ts`)
2. **Backend telemetry** — operational errors POSTed to `/api/telemetry` (already wired in `mobile/lib/telemetry.ts`, schema: `{ event_type, message, capture_trace_id, metadata }`)
3. **Targeted instrumentation for known silent failures** — the silent CRUD operations from `docs/instrumentation.md` lines 71+89 (Inbox load/refresh/pagination/recategorize/delete; Status screen errand load/dismiss/route). Phase plan adds `reportError()` calls at these specific call sites with `event_type: "crud_failure"` and a new `correlation_kind: "crud"`.

The MobileTelemetryDetail renderer combines all three sources, sorted chronologically, filterable by correlation_id.

**Explicitly out of scope for v1:** Passive checks like "no captures in N hours." Without lifecycle/session tracking (which doesn't exist today per `docs/instrumentation.md` line 102), these produce noise. Defer until lifecycle tracking exists.

### "Open in [Native Tool]" is first-class

Every renderer surfaces a deep link to the native tool (Sentry web UI, Foundry portal, Azure portal Cosmos blade, App Insights). When the spine's renderer doesn't have what you need, the link is right there. Spine = 80%; native = the long tail.

---

## Authentication

**Locked for v1:**

- **All spine read endpoints (`GET /api/spine/*`) require auth.** Reuses the existing API key auth (the same `Bearer` token used by mobile and MCP). Same `hmac.compare_digest` timing-safe comparison.
- **Spine ingest endpoint (`POST /api/spine/ingest`) requires the same API key.** Push segments use the same auth as everything else.
- **Web UI does NOT embed the API key.** Web is server-rendered (Next.js or similar) running on the same Container App as the backend. The web frontend reads the API key from server-side env (where the backend already has it via Key Vault). The browser never sees the key. If we later add a SPA, it goes through a session-cookie flow with backend-issued cookies — but v1 is server-rendered to avoid this entirely.

This locks the web framework choice indirectly: it must support server-side rendering. Next.js, Remix, SvelteKit, Astro with SSR endpoints all qualify. Plain client-rendered React does not.

---

## Phased Rollout

Vertical slices. Each phase ships end-to-end. If you stop after Phase 1, you have a working spine for one segment.

### Phase 1 — Spine foundation + Backend API segment

**Goal:** Spine backend exists. Backend API segment fully integrated end-to-end with all three event types. Mobile shows one tile. Web shows one detail view. Phase 19.1's KQL projection work absorbed.

**Deliverables:**
- New `spine` package in backend exposing 4 endpoints
- Cosmos containers created (`spine_segment_state`, `spine_events`, `spine_status_history`, `spine_correlation`) with TTLs
- Status evaluator runs every 30s as background task
- Backend API push: middleware sends liveness + readiness + per-request workload events
- Container App health rollup node (queries Azure Monitor for revision status, drives `host_segment` rollup)
- Pull from App Insights for trace-filtered detail (extends KQL templates with native AppExceptions field projections from 19.1's plan)
- Web app (server-rendered) with status board + AppInsightsDetail renderer
- Mobile Status screen extended with one new tile + `Linking.openURL()` to web
- API key auth wired on all spine endpoints

**Estimated scope:** ~2.5 weeks (added storage + evaluator + auth work)

### Phase 2 — Three agent segments

**Goal:** All three Foundry agents push liveness/readiness/workload events. Foundry correlation via run_id + thread_id (not vendor metadata). One new renderer (FoundryRunDetail) reused across all 3 agents.

**Deliverables:**
- Push events from each agent's wrapper code (classifier, admin, investigation)
- All three agents include `correlation_kind` + `correlation_id` in workload event payloads
- Spine joins App Insights agent spans by run_id/thread_id (no Foundry metadata dependency)
- FoundryRunDetail renderer (1 renderer, 3 segments)
- Mobile gets 3 new tiles
- Existing Phase 17.4 health-check + warmup logic continues; ingests results as readiness events into the spine

**Estimated scope:** ~1.5 weeks

### Phase 3 — External services + Cosmos + mobile silent-failure instrumentation

**Goal:** Two more segments + plug the known mobile silent-failure gaps (since they affect Phase 4's mobile segment).

**Deliverables:**
- External services push: wrap recipe scraping with workload events
- Cosmos pull adapter: Azure Monitor Logs query against Cosmos diagnostic logs
- Cosmos `client_request_id` wiring on every Cosmos call
- Targeted `reportError()` calls at silent CRUD sites in mobile (Inbox load/refresh/pagination/recategorize/delete; Status errand load/dismiss/route) with `event_type: "crud_failure"` and `correlation_kind: "crud"`
- 1 new renderer (CosmosDiagnosticDetail); reuses AppInsightsDetail for External services
- 2 new mobile tiles (External + Cosmos)

**Estimated scope:** ~1.5 weeks (added mobile instrumentation work)

### Phase 4 — Mobile segments + MCP migration with cutover gate

**Goal:** Final two segments. MCP migrates to spine. Explicit parity criteria gate the cutover.

**Deliverables:**
- Sentry pull adapter (one adapter, two segment configs differing by tag/project)
- Backend telemetry pull adapter (queries `/api/telemetry` history from existing storage)
- MobileTelemetryDetail renderer combining Sentry + backend telemetry + the new CRUD instrumentation from Phase 3
- 2 new mobile tiles (Mobile UI + Mobile capture)
- **MCP/spine parity test suite:** for each existing MCP tool (`recent_errors`, `system_health`, `trace_lifecycle`, `usage_patterns`, `admin_audit`, `run_kql`), an automated test that calls both the legacy direct-App-Insights path AND the new spine path and asserts equivalent results across a fixed set of canonical queries
- MCP tools refactored to call `/api/spine/*` only after parity tests pass for that tool
- Legacy KQL query layer in `mcp/server.py` removed only after all 6 tools have passed parity for 7 consecutive days

**MCP cutover gate (locked):** A tool is migrated only when (a) its parity test has run green for 7 days, AND (b) the legacy and new paths produce equivalent output on every canonical query in the test suite. Tools that fail parity stay on the legacy path indefinitely until the spine is fixed.

**Estimated scope:** ~2 weeks (parity test suite is real work)

### Total: ~7.5 weeks across 4 phases

(Increased from ~5.5 weeks in revision 1 due to storage layer, evaluator hardening, mobile silent-failure work, and parity test suite.)

---

## Existing Planning Artifacts

### Phase 17.4 — Stays as-is

Phase 17.4 (already shipped, 2026-04-13) delivered parameterized OTel middleware (`AuditAgentMiddleware(agent_name=...)`), active `/health` checks, warmup self-heal, Azure Monitor alerts. All preserved as Backend API segment instrumentation. In the new model, the active health check feeds *readiness events* into the spine; Azure Monitor alerts continue firing independently (alerting layer is orthogonal to the status board).

### Phase 19.1 — Cancelled as standalone, absorbed into Phase 1

Phase 19.1 (planned, not executed) was a workaround for the unified-schema problem. Its work (KQL OuterMessage / Details / OuterType / InnermostMessage projections) is needed for the Backend API segment's pull adapter and is folded into Phase 1.

**Action for Phase 19.1:**
- Mark cancelled in ROADMAP.md with a note pointing to this spec
- The plan (`19.1-01-PLAN.md`) is preserved as a reference for Phase 1's KQL work
- The directory stays in place; the work isn't lost, just rehomed

---

## Risks (revised)

1. **Cosmos write rate from `spine_events`.** With 5 push segments emitting liveness (every 30s) + readiness (every 60s) + workload (per-operation), and 14-day retention, this could be a non-trivial RU consumer. Phase 1 must measure this and add batching/sampling if needed.
2. **Status evaluator latency.** Running every 30s and reading recent `spine_events` documents per segment must complete in <5s to avoid drift. Phase 1 evaluator should be benchmarked under realistic event volume.
3. **MCP parity testing complexity.** The canonical query set must be representative of real MCP usage. Risk of either (a) too narrow a test set that lets regressions through, or (b) too broad a set that perpetually flags benign differences. Phase 4 starts with a small canonical set and expands as we learn.
4. **Web framework lock-in to SSR.** The auth model depends on server-side rendering. If we later want a richer SPA, we'll need to add session-cookie auth. Acceptable v1 trade-off — flagged for future awareness.
5. **Container App revision detection latency.** Deploy suppression depends on Azure Monitor's revision status, which has its own lag. Some `stale` false positives during deploys are still possible. Acceptable; revisit if annoying.
6. **Foundry SDK changes during AI Foundry framework GA migration.** The spec deliberately avoids depending on Foundry metadata filtering, but it does depend on the Foundry Runs API being available with `run_id` retrievability. If the GA migration changes this contract, Phase 2 needs adjustment.

---

## Decisions Locked by This Spec

- **Architecture:** backend + 2 frontends, hybrid push/pull, no segment-detail normalization
- **8 segments at the medium-grain boundary** (specific list above) + 1 internal `container_app` rollup node
- **Layered health:** liveness + readiness + workload events, status decided by per-segment evaluator
- **Storage:** spine state in Cosmos (4 containers with explicit TTLs); native data stays in native systems
- **Correlation envelope:** `correlation_kind` + `correlation_id` (+ optional parent), supporting capture/thread/request/crud kinds
- **Foundry correlation:** join by run_id/thread_id (not vendor metadata)
- **Response envelope:** locked field set for delivery metadata; segment-content fields explicitly NOT in envelope
- **Status precedence:** `red > yellow > green > stale`; `stale` is "unknown" not "broken"
- **Source-lag handling:** per-segment `acceptable_lag_seconds`; freshness exposed in envelope
- **Deploy suppression:** Container App revision status drives suppression for hosted segments
- **Rollup:** computed at query time, raw status preserved; `host_segment: container_app` for hosted segments, `null` for independent
- **Renderers per native shape:** 4 renderers for 8 segments; reuse where shapes match; new shape requires new renderer
- **Mobile data sources:** Sentry + backend telemetry + targeted CRUD instrumentation (NOT Sentry-only, NOT passive checks)
- **Auth:** API key auth on all spine endpoints v1; web is server-rendered (no embedded key)
- **Phased rollout:** 4 vertical slices (~7.5 weeks); Phase 19.1 absorbed into Phase 1; Phase 17.4 preserved
- **MCP migration:** cutover gated on 7-day parity test pass per tool

## Decisions Deferred to Phase Planning

- Specific web framework (must support SSR; Next.js, Remix, SvelteKit, Astro+SSR all viable)
- Status board layout details (grid vs list, color choices, icons)
- Polling interval for status board (mobile + web)
- Specific RU sizing for new Cosmos containers
- Specific canonical query set for MCP parity tests
