# Per-Segment Correlation Audit Design

**Date:** 2026-04-18
**Status:** Pending implementation plan
**Builds on:** Per-Segment Observability Design (2026-04-14), MCP cutover (commits `7450e07`, `1aeea10`)

---

## Why This Exists

The spine is live with 9 segments, all reporting green. But "green" with most segments showing "Idle (no recent operations)" is the failure mode the spine was supposed to guard against: it could mean genuinely no traffic, or it could mean traffic is happening and the segment is silent.

The original handoff posed the question explicitly: *is each spine segment accurately reflecting what's happening in its domain?* That question decomposes into four failure modes:

- **D — Correlation broken:** events emit but `correlation_id` doesn't actually tie cross-segment events to the same real transaction
- **B — Mis-attribution:** events emit with the wrong `segment_id`, `outcome`, or `correlation_id`/`correlation_kind`
- **A — Silent under-reporting:** a segment looks idle/green but the underlying domain is doing work
- **C — Evaluator misinterpretation:** events are correct but the evaluator's status conclusion is wrong

Priority order: **D > B > A > C**. C is unit-test territory (the evaluator already has a test suite that can be extended); this spec covers D, B, and A through a single MCP tool the investigation agent can call on demand.

---

## Architectural Principles (locked)

1. **Trace-first, not segment-first.** The audit walker starts from a `correlation_id` and walks the expected segment chain. This matches the priority order — D is answered directly, B comes for free during the walk, A surfaces as a bounded side product.
2. **Native sources are ground truth.** The spine's own `spine_events` are the audit *subject*; App Insights, Cosmos diagnostic logs, and Sentry are the *reference*. The audit never trusts the spine to grade itself.
3. **Bounded scope per call.** A single audit call samples up to 20 traces or audits one specific ID. No full-population scans. If the agent needs deeper coverage, it makes more calls.
4. **Best-effort, not authoritative.** Mis-attribution and orphan checks have known sources of false positives (lag, naming convention drift). The report says "needs human review" rather than "broken." The agent surfaces signals; the human investigates.
5. **No new storage.** The audit reads existing `spine_correlation` and `spine_events` plus native sources. No audit history container. Every call is fresh.
6. **Agent-driven, not scheduled.** v1 ships as an MCP tool only. No CI gate, no synthetic probe, no notifications. If a passive canary is wanted later, the audit logic is the building block.

---

## Tool Surface

A new MCP tool on the existing `second-brain-telemetry` server:

```
audit_correlation(
    correlation_kind: "capture" | "thread" | "request" | "crud",
    correlation_id: str | None = None,    # if None, sample N most recent
    sample_size: int = 5,                  # only used when correlation_id is None
    time_range_seconds: int = 86400,       # window for sampling, default 24h
) -> AuditReport
```

Lives next to `recent_errors`, `trace_lifecycle`, `admin_audit` in the spine MCP server. Single-ID mode audits one specific trace (e.g., "the user reported this capture went missing"). Sample mode audits the N most-recent correlation_ids of that kind from `spine_correlation` (e.g., "is capture observability working right now").

**Tool description (what the agent reads to decide when to call it):**

> Audit whether spine events for a correlation_id (or a sample of recent ones) line up with what native sources actually saw. Use when the user asks whether observability is working, whether a specific trace was captured correctly, or whether segments are accurately reflecting their domain. Returns per-trace verdicts plus an aggregate roll-up.

**Out of scope for v1:**
- Segment-first scanner mode (deferred — different problem shape, likely a separate tool)
- Synthetic probe (deferred — agent-on-demand audit covers the same need without a passive canary)
- Scheduled / CI runs (deferred — build understanding of "broken" first)
- Web UI surface (audit is agent-driven; "run audit" button is a future task)
- Notifications when audit shows broken (existing Azure Monitor alerts cover the alerting layer)

---

## Expected Segment Chains

The walker needs ground truth for what a "complete" chain looks like per `correlation_kind`. Lives in code, not config — same principle as the evaluator registry.

```python
EXPECTED_CHAINS: dict[CorrelationKind, list[ExpectedSegment]] = {
    "capture": [
        ExpectedSegment("mobile_capture",   required=True),
        ExpectedSegment("backend_api",      required=True),
        ExpectedSegment("classifier",       required=True),
        ExpectedSegment("admin",            required=False),  # only Admin bucket
        ExpectedSegment("external_services", required=False), # only recipe URLs
        ExpectedSegment("cosmos",           required=False),  # pull adapter, may lag
    ],
    "thread": [
        ExpectedSegment("investigation", required=True),
        ExpectedSegment("backend_api",   required=True),
        ExpectedSegment("cosmos",        required=False),
    ],
    "request": [
        ExpectedSegment("backend_api", required=True),
        ExpectedSegment("cosmos",      required=True),  # CRUD-shape always hits Cosmos
    ],
    "crud": [
        ExpectedSegment("mobile_ui",   required=True),
        ExpectedSegment("backend_api", required=True),
        ExpectedSegment("cosmos",      required=True),  # CRUD-shape always hits Cosmos
    ],
}
```

**`required=True`** — chain must contain a workload event from this segment. Missing = correlation hole, contributes to `broken` verdict.

**`required=False`** — chain may contain an event from this segment, content-dependent. Present = good. Missing = not flagged.

**Why conditional segments (`admin`, `external_services`) are optional in `capture`:** Their participation depends on the capture's content (Admin bucket, recipe URL). The audit can't know from outside without re-classifying. Trade-off: false negatives on conditional segments, but no false positives.

**Why `cosmos` is required for `request`/`crud` but not `capture`/`thread`:** CRUD-shaped operations always hit Cosmos as their last step. Capture and thread paths may write to Cosmos *eventually* but the audit window doesn't reliably bound that. Lag is mitigated separately (see R1).

---

## The Three Checks Per Trace

For each `correlation_id` in the sample, the walker runs three checks against the spine + native sources.

### Check 1 — Correlation integrity (D)

**Inputs:**
- `spine_correlation` records for `(kind, id)` — which segments touched this trace
- `EXPECTED_CHAINS[kind]` — which segments should have

**Logic:** For each `required=True` segment in the expected chain, is there at least one record in `spine_correlation` for `(kind, id, segment_id)`?

**Outputs:**
- `missing_required: list[str]` — gaps (contributes to `broken`)
- `present_optional: list[str]` — informational
- `unexpected: list[str]` — segments that emitted for this trace but aren't in the expected chain (contributes to `warn`; may indicate routing bug or stale chain definition)

### Check 2 — Mis-attribution (B)

**Inputs:** for each segment that fired:
- `spine_event` workload payloads (outcome, error_class, duration_ms, operation)
- For backend-side segments: App Insights spans where `Properties.correlation_id == id` in the trace's time window
- For Cosmos: Cosmos diagnostic logs where `activityId_g == id` (or `client_request_id` matches)

**Three sub-checks per (segment, trace):**

1. **Outcome agreement** — spine `success` ⟺ App Insights/Cosmos has zero exceptions in window; spine `failure` ⟺ at least one exception present
2. **Operation name plausibility** — spine `payload.operation` should appear in App Insights `Name` for at least one matching span (loose check; exact match not required, naming conventions differ)
3. **Time window overlap** — spine `timestamp ± duration_ms` should overlap with at least one native operation in the same trace

**Output:** `misattributions: list[Misattribution]` — one per `(segment, sub-check)` failure, with a one-line reason.

### Check 3 — Bounded under-reporting (A)

**Inputs:** App Insights spans in the trace's full time window (earliest to latest `spine_event.timestamp` for this `correlation_id`, padded ±60s)

**Logic:** Count spans matching `Properties.correlation_id == id` that have NO corresponding `spine_event` for the same `(correlation_id, segment_id)`. These are operations the native source saw but the spine missed.

**Output:** `orphans: list[OrphanReport]` — per segment with non-zero orphans, includes count + top 3 sample operation names.

**Intentional scope limit:** Trace-bounded. Cannot detect a totally-silent segment (zero events ever) — that's `system_health`'s job. This check answers "does this trace have spine events for everything the native source saw," not "does the segment ever emit anything."

---

## Output Shape

```python
class TraceAudit(BaseModel):
    correlation_kind: str
    correlation_id: str
    verdict: Literal["clean", "warn", "broken"]
    headline: str  # one-line summary, agent uses verbatim if needed

    # Check 1 — correlation integrity
    missing_required: list[str]   # segment_ids
    present_optional: list[str]
    unexpected: list[str]

    # Check 2 — mis-attribution
    misattributions: list[Misattribution]

    # Check 3 — bounded under-reporting
    orphans: list[OrphanReport]

    # Context
    trace_window: TimeWindow      # earliest → latest spine_event timestamp
    native_links: dict[str, str]  # segment_id → "Open in App Insights / Foundry / Sentry"


class Misattribution(BaseModel):
    segment_id: str
    check: Literal["outcome", "operation", "time_window"]
    spine_value: str
    native_value: str
    reason: str  # human-readable one-liner


class OrphanReport(BaseModel):
    segment_id: str
    orphan_count: int
    sample_operations: list[str]  # top 3 native operation names


class AuditReport(BaseModel):
    correlation_kind: str
    sample_size_requested: int
    sample_size_returned: int  # may be less if not enough traces in window
    time_range_seconds: int

    traces: list[TraceAudit]
    summary: AuditSummary
    instrumentation_warning: str | None = None  # see R2


class AuditSummary(BaseModel):
    clean_count: int
    warn_count: int
    broken_count: int

    # Roll-ups across all sampled traces
    segments_with_missing_required: dict[str, int]   # segment_id → trace count
    segments_with_misattribution: dict[str, int]
    segments_with_orphans: dict[str, int]

    overall_verdict: Literal["clean", "warn", "broken"]
    headline: str
```

### Verdict roll-up rules

**Per trace:**
- `broken` if any `missing_required` OR any `misattribution` with `check == "outcome"` (outcome disagreement is the strongest signal)
- `warn` if any `unexpected`, any non-outcome misattribution, or any orphans
- `clean` otherwise

**Per report:**
- `broken` if any trace is broken
- `warn` if any trace is warn (and none broken)
- `clean` if all traces clean

### Why these shapes

- `headline` at both trace and report level so the agent has a ready one-liner without constructing from raw fields
- `native_links` per segment so when the agent surfaces a problem it can hand back the deep link (every drill-down points to native — preserves the spec's "native is first-class" principle)
- `summary.segments_with_*` roll-ups precompute the most common follow-up question ("which segment is the worst offender across the sample")
- Single-ID mode returns a `traces` list with one element. Sample mode returns N. Same shape, no agent-side branching.

---

## Implementation Boundaries

### Backend (FastAPI, Container App)

**New endpoint:** `POST /api/spine/audit/correlation`

Why HTTP and not direct Cosmos from the MCP server: every other spine read (`recent_errors`, `trace_lifecycle`, `admin_audit`) goes through the API. The MCP server holds an API key, not Cosmos creds. Keeps auth and access surface consistent with the cutover that just shipped.

Request body:
```python
class AuditRequest(BaseModel):
    correlation_kind: Literal["capture", "thread", "request", "crud"]
    correlation_id: str | None = None
    sample_size: int = Field(5, ge=1, le=20)
    time_range_seconds: int = Field(86400, ge=60, le=604800)  # 1min - 7d
```

Response: the `AuditReport` from the previous section.

**New module:** `backend/src/second_brain/spine/audit/`
- `chains.py` — `EXPECTED_CHAINS` constant + `ExpectedSegment` dataclass
- `walker.py` — `CorrelationAuditor` class with `audit(kind, id) -> TraceAudit` and `audit_sample(kind, n, window) -> AuditReport`
- `native_lookup.py` — three thin adapters: `app_insights_spans_for_correlation()`, `cosmos_diagnostic_for_correlation()`, `appinsights_exceptions_for_correlation()`. Reuses existing `LogsQueryClient` wiring.

**Reuses (no changes):**
- `SpineRepository.get_correlation_records(kind, id)` — already powers `/api/spine/correlation/{kind}/{id}`
- `SpineRepository.get_recent_events(segment_id, window_seconds)` — already powers the evaluator
- `LogsQueryClient` workspace queries from Phase 17.1

### MCP server

**New tool:** `audit_correlation` in `mcp/server.py`. Thin wrapper: validates args, calls `POST /api/spine/audit/correlation`, returns the parsed `AuditReport` as the MCP response payload. Approximately 30 lines.

### Investigation agent

No code change. The tool description in MCP server is enough for the agent to pick it up. If live use shows the agent needs more guidance, instructions are tweaked in `docs/foundry/investigation-agent-instructions.md`.

### Tests

Three layers:

1. **`walker.py` unit tests** with synthetic spine events + mocked native-source returns. Cover: complete chain, missing required, misattribution per sub-check, orphan detection, verdict roll-up logic, sample size truncation. Approximately 12 cases.
2. **`native_lookup.py` integration test** against a known recent `capture_trace_id` — proves the App Insights / Cosmos KQL templates actually return data. Marked `@pytest.mark.live` so it doesn't run in CI by default. Approximately 3 cases (one per native source).
3. **End-to-end MCP test** that calls the tool against the deployed backend with a real recent correlation_id and asserts the response is well-formed (not asserting verdict, just shape). Marked `@pytest.mark.live`.

---

## Risks

### R1 — Native-source lag creates false orphans

Cosmos diagnostic logs lag 5-10 minutes. App Insights ingestion lags ~1-3 minutes. If the audit runs against a trace from the last few minutes, Check 3 (orphans) could flag operations that just haven't been ingested yet.

**Mitigation:** When sampling, exclude traces whose latest spine event is within `max(acceptable_lag_seconds across involved segments) + 60s` of `now`. Trace-window padding (±60s in Check 3) absorbs smaller lag. Document the constraint in the tool description: "audit is for traces that have settled, not live ones."

### R2 — KQL projection drift

Check 2's outcome agreement and Check 3's orphan detection both depend on `Properties.correlation_id` being present in App Insights spans. Phase 17.4 wired this end-to-end, but if a future change drops the property from any segment, the audit would silently start reporting "missing native data" for that segment.

**Mitigation:** Walker has a sanity check — if a `required=True` segment has zero matching native spans for *every* sampled trace, the report includes a top-level `instrumentation_warning: "<segment> appears to have lost correlation_id tagging"`. Distinguishes "this trace is broken" from "the audit itself is broken."

### R3 — `EXPECTED_CHAINS` can drift from reality

The chain definitions are hardcoded. If the system grows a new segment or changes routing (e.g., affinity system adds a new path), the audit reports false `unexpected` segments or false `missing_required` until someone updates the file.

**Mitigation accepted, not engineered:** Same trade-off as the evaluator registry — config in code is intentional. Implementation plan should include a follow-up note to revisit chains when adding any new segment. The `unexpected` warning level (yellow, not red) means drift surfaces gradually rather than blocking.

### R4 — Sample mode masks tail problems

A 5-trace sample of `capture` correlation_ids from the last 24h will probably miss low-frequency edge cases (e.g., a recipe-URL capture that fires once a day). Aggregate verdict could be `clean` while a real bug lurks in the long tail.

**Mitigation:** Document this in the tool description. If thorough coverage is wanted, pass higher `sample_size` (max 20) or audit a specific suspect ID directly. Honest scope limit, not a thing to engineer around.

### R5 — Investigation agent might over-call this tool

`recent_errors` is the natural first move when the user reports trouble. If the agent starts calling `audit_correlation` for every "is anything broken" question, latency goes up (audit is heavier than `recent_errors` because it does N native queries per trace).

**Mitigation:** Tool description scoped narrowly: "audit whether spine events line up with native sources" — not "general health check." Tighten the description if over-calling appears in practice.

### R6 — Audit endpoint amplifies App Insights query cost

Each sampled trace fires approximately 3 native queries. A 20-trace sample = 60 KQL queries per call. Log Analytics has per-query and per-workspace cost characteristics.

**Mitigation:** `sample_size` capped at 20 in the request validator. Time window capped at 7 days. If cost becomes a concern in practice, add a cache keyed on `(kind, id, window)` — but YAGNI for v1.

---

## Decisions Locked by This Spec

- **Architecture:** trace-first walker, MCP tool surface, no segment-first mode in v1
- **Ground truth:** native sources (App Insights, Cosmos diagnostic logs); spine is the audit subject
- **Endpoint:** `POST /api/spine/audit/correlation` on the existing spine API; MCP server is a thin wrapper
- **Storage:** none — every call is fresh; no audit history
- **Expected chains:** hardcoded in `chains.py`; Cosmos required for `request`/`crud`, optional for `capture`/`thread`
- **Three checks per trace:** correlation integrity (D), mis-attribution (B), bounded under-reporting (A)
- **Verdict precedence per trace:** missing required OR outcome disagreement → `broken`; unexpected/non-outcome misattribution/orphans → `warn`; else `clean`
- **Sample size capped at 20**, time window capped at 7 days
- **Lag handling:** exclude unsettled traces from sampling; trace-window padding absorbs small lag
- **Tests:** unit tests for walker logic; live-marked integration tests for native lookups + end-to-end MCP

## Decisions Deferred

- Whether to add a segment-first scanner as a sibling tool (revisit after using v1)
- Whether to add a synthetic probe / canary (revisit if the on-demand audit proves insufficient)
- Whether to schedule the audit (revisit once the noise floor is known)
- Whether to cache native-query results (revisit if cost becomes visible)
- Whether to surface audit results in the web UI (revisit when the UI gets a "deeper investigation" surface)
- Evaluator-correctness audit (priority C) — handled separately by extending the evaluator's existing test suite, not in scope here
