# Phase 19.2 Plan 01 — Spike Memo

**Status:** Awaiting human approval (Plan 01 Task 3 gate) — **Round 3 revision** (pre-approved contingent on this fix)
**Evidence:** See [SPIKE-DATA.md](./SPIKE-DATA.md) for raw query output, App Insights stack traces, and audit_correlation reports. This memo contains categorization and recommendations only — no raw data.

**Round 3 changes vs. round 2** (in response to operator review of §4c / §5 item 5):
- §4c rewritten. Previously said "wrap onComplete / onError" which would miss `MISUNDERSTOOD` / `LOW_CONFIDENCE` / `UNRESOLVED` (all set `hitlTriggered=true` and suppress the downstream `COMPLETE` → `onComplete` dispatch) plus the legacy `CUSTOM` HITL paths and the SSE transport `error` listener. Now enumerates all seven (+ three legacy) terminal paths from the real `attachCallbacks` in `mobile/lib/ag-ui-client.ts`, centralises the emit inside `attachCallbacks` itself with a single-fire guard, and documents the outcome mapping (success / degraded / failure) including HITL-style outcomes as `degraded`.
- §5 item 5 rewritten to mirror §4c — emit fires exactly once per stream via the shared `attachCallbacks` helper covering every terminal path, not per-`sendX` onComplete/onError wrappers.

**Round 2 changes vs. round 1** (in response to operator review):
- §4 rewritten. Decision unchanged (YES for `mobile_capture`, NO for `mobile_ui`) but now explicitly picks **Option B (post-capture fire-and-forget)** after disclosing the honest trade-off between Option A (pre-capture emit with queue/retry — proves transport failure, but a new subsystem) and Option B (simpler, but cannot prove transport failure). §4a explains the trade-off; §4c maps Option B to concrete hook sites in `mobile/lib/ag-ui-client.ts`; §4d covers Plan 04's empty-state UX for the transport-failure blind spot.
- §5 updated. Mobile_capture task (item 5) now matches Option B specifically. New "Out of scope for Plan 02" subsection explicitly lists backend_api native-correlation and duplicate Key Vault secret as deferred (per operator confirmation).
- §6 updated. Round-1 open questions recorded as answered.
- **Line numbers re-verified** against current files. Corrections:
  - `agent_emitter.py:63` — confirmed correct (operator's "57" was off; stayed at 63).
  - `tools/recipe.py`: construction at line 175, `record_event(event)` call at line 185, bare-except at 186-187 (operator's "172" is the start of the `if self._spine_repo is not None:` guard; memo uses the specific callsite numbers instead).
  - `mobile/lib/ag-ui-client.ts`: `sendCapture` signature at line 201; `X-Trace-Id` header literal at line 209; `new EventSource(...)` at line 215 (operator cited 201 for the X-Trace-Id propagation point — resolved to line 209 where the header is actually set).
  - `mobile/lib/telemetry.ts`: `reportError` is at line 30 (confirmed); file is 51 lines long, so operator's "line 83" does not exist — the nearest-matching citation is the `fetch(...)` call at line 32. No impact on findings.
  - `backend/src/second_brain/spine/api.py:59` — `/api/spine/ingest` endpoint — confirmed correct.

---

## 1. Summary (3 lines)

1. **Capture chain:** Every agent-side emitter (classifier / admin / investigation) is silently broken by a single Pydantic shape bug — `_WorkloadEvent` is being passed to `record_event` instead of `IngestEvent(root=_WorkloadEvent)`. All three sites fail with the same `AttributeError: '_WorkloadEvent' object has no attribute 'root'` the moment they fire. The code LOOKS right but the deployed behaviour is zero landed events.
2. **Thread chain:** Investigation never writes a `thread`-kind correlation row for the same reason (shared helper). The audit tool therefore reports `sample_size_returned=0` for thread correlations in every run.
3. **Mobile push-path decision:** **YES for `mobile_capture`, NO for `mobile_ui`.** Plan 02 ships **Option B** (post-capture fire-and-forget emit): the ledger can distinguish downstream failures after backend receipt, but CANNOT prove transport failure when `/api/capture` itself fails. Rationale and scope in §4.

---

## 2. Per-segment categorization table

Segments are the 9 used by `EXPECTED_CHAINS` + the rollup node. Categories are exactly one of `broken_emitter` | `pull_by_design` | `correlation_lost` | `working_correctly`.

| Segment             | emit_site_exists                                   | events_in_spine_events (24h)                                       | correlation_tag_present (spine side)                              | native_record_tagged (App Insights side)                                     | **category**          |
| ------------------- | -------------------------------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------- | ---------------------------------------------------------------------------- | --------------------- |
| backend_api         | YES — `spine/middleware.py:70,95`                  | YES — 27,639 rows/24h                                              | YES for spike trace (2 rows in `spine_correlation`); only 3/27,639 of all rows carry any correlation_id | NO — `AppRequests` carries no `capture_trace_id` property or matching `OperationId`         | **correlation_lost**  |
| classifier          | YES — `spine/stream_wrapper.py:41` via `agent_emitter.py:63` | NO — 0 rows/24h                                          | n/a (nothing lands)                                               | Custom span `capture_text` in `AppDependencies` HAS `capture.trace_id`; `AppTraces` logs HAVE `capture_trace_id` | **broken_emitter**    |
| admin               | YES — `processing/admin_handoff.py:397` via `agent_emitter.py:63` | NO — 0 rows/24h                                    | n/a                                                               | Custom span `admin_agent_process` HAS `capture.trace_id`; `AppTraces` logs HAVE `capture_trace_id`             | **broken_emitter**    |
| investigation       | YES — `api/investigate.py:87` via `agent_emitter.py:63` | NO — 0 rows/24h; 0 thread-kind correlation rows ever        | n/a                                                               | `AppTraces` logs have `component=investigation_agent`; no thread-kind OTel span attribute today                | **broken_emitter**    |
| external_services   | YES — `tools/recipe.py:185` (direct `_WorkloadEvent`, `except: pass`) | NO — 0 rows/24h (also not exercised in this spike — no recipe URL) | Would be NO even if emit worked (payload omits `correlation_kind` / `correlation_id`) | Native HTTP call side = Jina/httpx/Playwright (not instrumented by App Insights at app layer)                  | **broken_emitter**\*  |
| cosmos              | NO direct emit (by design)                         | NO — 0 rows/24h                                                    | n/a — pulled by `CosmosAdapter` from `AzureDiagnostics`           | Cosmos Azure Diagnostics rows DO exist (they drive the CosmosAdapter); `activityId_g` carries per-request IDs but not `capture_trace_id` | **pull_by_design**   |
| mobile_ui           | Crud-failure-only emit at `api/telemetry.py:105,120`; broken the same way | NO — 0 rows/24h (no crud_failures during spike)      | n/a                                                               | Native source = Sentry (mobile SDK); not currently joined to captures by correlation id                        | **pull_by_design**\*\* |
| mobile_capture      | Same as mobile_ui — crud-failure only today        | NO — 0 rows/24h                                                    | n/a                                                               | Same — Sentry-native                                                                                           | **pull_by_design**\*\* |
| container_app       | NO direct emit (by design)                         | NO — 0 rows/24h                                                    | n/a — pulled by `ContainerAppAdapter` from App Insights log roll-up | Rolls up `backend_api` native data — inherits backend_api's correlation gap                                  | **pull_by_design**   |

\* **external_services** is categorised `broken_emitter` and not just `correlation_lost` because its emit call never lands ANY event (same AttributeError as the other three) — the missing correlation fields are a secondary bug that will only surface AFTER the primary fix. See §3 (fix order note).

\*\* **mobile_ui / mobile_capture** are categorised `pull_by_design` for the NORMAL-capture ledger UX. Their crud-failure emit path is independently broken (`telemetry.py:105` passes a raw `_WorkloadEvent`; line 120 passes a raw `_LivenessEvent`), but no crud_failures have been reported during the spike window so we can't observe the failure live. This is a latent bug. See §4 for the mobile push-path decision that changes mobile_capture from `pull_by_design` to emit-first.

---

## 3. Findings per category

### 3a. `broken_emitter` — root cause is ONE line

**All four broken emitters share a single shape bug** in `backend/src/second_brain/spine/agent_emitter.py:63`:

```python
# Current (broken)
try:
    await repo.record_event(event)          # event is _WorkloadEvent
```

`record_event` is typed `event: IngestEvent` and does `inner = event.root` (the Pydantic v2 `RootModel` accessor). Passing a bare `_WorkloadEvent` raises `AttributeError: '_WorkloadEvent' object has no attribute 'root'` EVERY time this helper is called. The same pattern bug appears at three other callsites. The fix is to wrap in `IngestEvent(root=...)` — the identical pattern that `spine/middleware.py:70,95` and `spine/background.py:70-77` already use successfully.

**Per-site findings:**

| Segment            | File:line                          | Failure type                                                                                                                | Fix                                                                                                                                                                                                                              |
| ------------------ | ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| classifier         | `backend/src/second_brain/spine/agent_emitter.py:63` | Raw `_WorkloadEvent` passed to `record_event` → AttributeError (App Insights `AppExceptions` 2026-04-18T23:55:56.242289Z) | Wrap: `await repo.record_event(IngestEvent(root=event))`. Fixing the helper fixes classifier + admin + investigation in one edit (all three call `emit_agent_workload`).                                                         |
| admin              | same                               | Same AttributeError (AppExceptions 23:56:14.990996Z)                                                                        | Same one-line fix — inherited via `emit_agent_workload`.                                                                                                                                                                         |
| investigation      | same                               | Same AttributeError (AppExceptions 23:56:18.467932Z)                                                                        | Same one-line fix.                                                                                                                                                                                                               |
| external_services  | `backend/src/second_brain/tools/recipe.py:185`       | Raw `_WorkloadEvent` passed to `record_event` AND `except: pass` silently swallows. Also: `WorkloadPayload` omits `correlation_kind` / `correlation_id` (Pitfall 2 from RESEARCH.md — direct `_WorkloadEvent` bypasses `emit_agent_workload`). | Two-part fix: (a) wrap in `IngestEvent(root=...)` OR migrate to `emit_agent_workload`; (b) add `correlation_kind="capture"` / `correlation_id=<capture_trace_id>` (recipe tool runs inside the classifier Foundry agent context — trace must be threaded through from the caller). Replace bare `except: pass` with `except Exception: logger.warning(..., exc_info=True)`. |
| mobile_ui (crud)   | `backend/src/second_brain/api/telemetry.py:105`      | Raw `_WorkloadEvent` — latent, no crud_failure in spike window but will fail the moment mobile reports a CRUD failure       | Wrap with `IngestEvent(root=event)`.                                                                                                                                                                                             |
| mobile_ui (liveness) | `backend/src/second_brain/api/telemetry.py:120`    | Raw `_LivenessEvent` — same latent bug                                                                                      | Wrap with `IngestEvent(root=liveness_event)`.                                                                                                                                                                                    |

**Why only backend_api and the background liveness loop work today:** both wrap with `IngestEvent(root=...)` (`middleware.py:70,95`; `background.py:70-77`). Everything else bypasses the wrap and fails.

**Evidence this is NOT an "emit site missing" problem:** All three broken segments (classifier / admin / investigation) show Python `logger.info` rows in `AppTraces` AND custom OTel spans in `AppDependencies` tagged with `capture.trace_id` during the spike window — proof the code ran. The emit call ran too; it just raised before the Cosmos write.

### 3b. `correlation_lost` — the one non-trivial native-side gap

**backend_api's native records (AppRequests) don't carry `capture_trace_id`.** This is the second-largest gap the spike exposes and reproduces the `instrumentation_warning` that audit_correlation emits (`"backend_api appears to have lost correlation_id tagging"`).

- Spine side: every `/api/capture` produces a correctly-correlated spine_events + spine_correlation row (proven for the spike trace).
- Native side: `AppRequests` does not carry `capture_trace_id` in `Properties` or as `OperationId`. The OTel HTTP-request auto-instrumentation is not reading `X-Trace-Id` into the span context.

Drop point: the capture handler (`api/capture.py:210-211`) sets `request.state.capture_trace_id = capture_trace_id` and passes it to the downstream `spine_stream_wrapper`, but the Azure Monitor OTel instrumentation for the INBOUND request had already captured its own `operation_Id` (random UUID) before the handler ran. There is no bridge that tags the auto-instrumented HTTP request span with the app-layer trace id. Phase 19.1 introduced AppException native-field projection (`OuterMessage` / `InnermostMessage` / `Details`) but did NOT wire `capture_trace_id` onto `AppRequests`.

This is a native-telemetry-correlation bug, not an emit-site bug. It's scoped to native panels and is independent from §3a (§3a fixes the SPINE ledger; §3b is about making the SPINE ledger's `native_links` actually resolve). This phase's "native diagnostics as secondary drill-down" promise still holds even if we defer §3b — a user clicking through from the spine ledger would still land in the right time window, just without a trace-id filter prewired.

**Recommendation:** Defer §3b to a dedicated follow-up (related to `project_followup_audit_first_findings.md`). Plan 02 scope should be the emitter fixes ONLY. If Will wants it in-scope, bundle into Plan 02 but separate the task (adds OTel context propagation, not just a shape fix).

### 3c. `pull_by_design` — no fix; UI must render as such

**cosmos + container_app + mobile_ui + mobile_capture (for the normal-capture path).**

- `cosmos`: pulled by `CosmosAdapter` from `AzureDiagnostics` (category `DataPlaneRequests`). No workload events expected in `spine_events`, ever. The ledger UX must render "no transaction rows — this segment is native-only" and defer to the native panel below. Already categorized this way by `audit/walker.py::_APPINSIGHTS_SEGMENTS` / `_segment_has_native_data`.
- `container_app`: pulled by `ContainerAppAdapter` which rolls up backend_api App Insights. Same treatment — no workload events expected.
- `mobile_ui` / `mobile_capture` (normal captures): Sentry-native today. The operator's mental model for the 19.2 ledger CURRENTLY matches Sentry, not spine. See §4 — this decision will flip if Will approves the push-path option.

### 3d. `working_correctly` — zero rows

No segment is fully working end-to-end. `backend_api` is the closest — its emit path works — but it fails native-side correlation. Classifying it as `correlation_lost` rather than `working_correctly` is the correct read.

---

## 4. Mobile push-path decision

**Question:** Should `mobile_capture` and `mobile_ui` emit normal-capture workload events to spine today, not just `crud_failure`?

**Decision: YES for `mobile_capture`. NO for `mobile_ui`.**

### 4a. Implementation choice: Option B (post-capture, fire-and-forget)

The current mobile client in `mobile/lib/ag-ui-client.ts` builds headers (including `X-Trace-Id`) at line 209 and opens the SSE POST to `/api/capture` at line 215. Telemetry reporting in `mobile/lib/telemetry.ts::reportError` (line 30) is invoked from the SSE `onError` wrapper (line 229-237) AFTER the capture attempt fails or completes. There is no pre-capture emit path today, and no offline queue / retry buffer.

Two honest framings were available:

**Option A — emit-before-capture with independent retry (stronger operator story, more work):**
> Mobile emits a `segment_id="mobile_capture"` workload event to `/api/spine/ingest` BEFORE issuing `/api/capture`, keyed by the same `X-Trace-Id`. The emit is queued to local storage if the network is down, and retried independently of the capture submission. If `/api/capture` never lands (network drop, DNS failure, backend returns 500 before any handler runs), the ledger still shows `mobile_capture` seen + `backend_api` missing — literally proving "capture never reached backend."
>
> **Implementation cost:** new queue/retry buffer in `ag-ui-client.ts` around line 209 (before the `new EventSource(...)` at 215); local persistence (AsyncStorage or similar); retry-on-reconnect hook; reconciliation semantics if the queue drains out of order; end-to-end tests for offline scenarios. This is a new subsystem, not a small edit.

**Option B — emit-after-capture fire-and-forget (narrower but honest story, simpler shipping — CHOSEN):**
> Mobile emits a `segment_id="mobile_capture"` workload event to `/api/spine/ingest` AFTER the `/api/capture` SSE stream completes or errors. Fire-and-forget, no queue, no retry. Uses the existing `X-Trace-Id` as `correlation_id`. The outcome is `"success"` if the stream reached `COMPLETE` / `CLASSIFIED` / `MISUNDERSTOOD`, `"failure"` if it hit `ERROR` or the SSE connection errored.
>
> **What this ledger CAN distinguish:** DOWNSTREAM failures after backend receipt. E.g. mobile_capture seen + backend_api seen + classifier missing ⇒ classifier crashed. Or mobile_capture seen + classifier seen + admin missing ⇒ admin handoff broke.
>
> **What this ledger CANNOT prove:** That `/api/capture` itself never reached the backend. If the capture POST fails (airplane-mode submission, DNS outage, TLS error, backend 500 before any handler runs), then `onError` fires ⇒ `reportError` fires ⇒ the mobile_capture emit to `/api/spine/ingest` ALSO fails over the same broken transport. The ledger ends up with NEITHER a `mobile_capture` row NOR a `backend_api` row. The operator must infer "transport failed" from the native mobile error renderer (the error toast / Sentry event with `source: "sendCapture"` metadata already emitted at `ag-ui-client.ts:234`), NOT from the ledger.

**Why Option B is the right choice for Plan 02:**

1. **Plan 02 scope is wave-1 emitter shape fixes.** Adding a mobile offline queue is a materially different workstream (new subsystem, new failure modes, new tests, new docs) and would push Plan 02 past its single-wave boundary.
2. **CONTEXT.md's canonical example ("backend_api seen, classifier missing") is a DOWNSTREAM gap**, which Option B covers natively. The transport-failure case is real but orthogonal — CONTEXT.md's ledger is not the only diagnostic surface for it; the native mobile error renderer + Sentry already owns that failure mode.
3. **The ledger asymmetry is honestly disclosable in the UI.** When a trace appears with no mobile_capture row AND no backend_api row, the transaction page can surface "no rows for this trace id — check Sentry for client-side transport errors." That's a stable, honest UX.
4. **Upgrading Option B → Option A later is additive, not rework.** If operator experience shows the transport-failure blind spot is costing diagnostic time, a future phase can add the pre-capture emit + queue with no schema change and no break to downstream consumers. Option B's wire format is exactly the same as Option A's — just fired at a different time.

### 4b. `mobile_ui`: NO for normal-capture emit

Mobile UI is the CRUD-screen segment — it emits for destructive operations (delete errand, update destination, etc.), not for a capture. A capture doesn't "touch" mobile_ui. For the CAPTURE chain, `mobile_ui` is correctly `pull_by_design`. The crud_failure path it already has today is the right model. (However, `api/telemetry.py:105,120` is latently broken the same way `agent_emitter.py:63` is — both need the `IngestEvent(root=...)` wrap. That's a prereq for mobile_ui being a functioning emitter at all for its native `correlation_kind="crud"` contract.)

### 4c. Mapping Option B onto the existing mobile client

**Critical constraint: emit MUST fire exactly once on every terminal path.** The SSE client in `mobile/lib/ag-ui-client.ts::attachCallbacks` has **seven distinct terminal paths** that each end a capture lifecycle, and wrapping only `onComplete` / `onError` in each `sendX` function would miss every HITL path because `MISUNDERSTOOD` / `LOW_CONFIDENCE` / `UNRESOLVED` all set `hitlTriggered = true` which suppresses the downstream `COMPLETE` → `onComplete` dispatch (see guard at `ag-ui-client.ts:121`). That would leave valid backend-reached captures with zero `mobile_capture` rows in the ledger.

**Enumerated terminal paths in the current `attachCallbacks` (line numbers as of 2026-04-18):**

1. `CLASSIFIED` at line 85 — fires `callbacks.onComplete(result)` (v2 normal success).
2. `COMPLETE` / `RUN_FINISHED` at line 119-129 — fires `callbacks.onComplete(...)` only when `!hitlTriggered && (RUN_FINISHED || !result)`; always calls `es.close()`. (The `!result` guard prevents a double-fire when `CLASSIFIED` already set `result` on the same stream.)
3. `MISUNDERSTOOD` at line 89 — fires `callbacks.onMisunderstood?.(...)` and sets `hitlTriggered = true` (HITL, suppresses COMPLETE).
4. `LOW_CONFIDENCE` at line 101 — fires `callbacks.onLowConfidence?.(...)` and sets `hitlTriggered = true` (HITL, suppresses COMPLETE).
5. `UNRESOLVED` at line 113 — fires `callbacks.onUnresolved?.(...)` and sets `hitlTriggered = true` (HITL, suppresses COMPLETE).
6. `ERROR` / `RUN_ERROR` at line 131-135 — fires `callbacks.onError(...)` and calls `es.close()` (backend-raised error).
7. SSE transport `error` listener at line 176-181 — fires `callbacks.onError(...)` and calls `es.close()` (connection-level failure: network drop, non-2xx response, parse error, etc).
8. **Legacy `CUSTOM` envelope at line 145-169** — three sub-paths (`HITL_REQUIRED` / `MISUNDERSTOOD` / `UNRESOLVED`) that each set `hitlTriggered = true` and fire their respective HITL callback. These are v1 backward-compat paths the v2 backend no longer emits but the client still handles; they must be covered for the same reason as paths 3-5.

**Design: centralize the emit in `attachCallbacks` itself, with a single-fire guard.**

- Do NOT wrap each `sendX` function's callbacks individually — that would require duplicating the guard and the emit across four call sites and would miss the HITL paths entirely (because the `sendX`-level wrappers only see `onError` / `onComplete`, not `onMisunderstood` / `onLowConfidence` / `onUnresolved`).
- Add the emit inside `attachCallbacks` where every terminal path is already observed. Every dispatch above is routed through `attachCallbacks`, so a shared wrapper there sees all seven.
- Implement a single-fire guard — mechanism is an implementation detail (a closure-scoped boolean like `let emitted = false` is sufficient given `attachCallbacks` runs per-stream; anything equivalent is fine).
- Add a `startMs = Date.now()` captured at the top of `attachCallbacks` (or threaded in from `sendX`) so `duration_ms` can be computed on emit.
- Thread `traceId` into `attachCallbacks` (today it's only in scope inside each `sendX`; extend the `attachCallbacks` signature to accept it).

**Outcome mapping** (resolves the operator's open question on HITL-style outcomes for `operation="submit_capture"`):

| Terminal path                              | `outcome`   | Rationale                                                                 |
| ------------------------------------------ | ----------- | ------------------------------------------------------------------------- |
| `CLASSIFIED`                               | `success`   | Normal success — backend classified and filed.                            |
| `COMPLETE` / `RUN_FINISHED` (non-HITL)     | `success`   | Same as above via the fallback path.                                      |
| `MISUNDERSTOOD`                            | `degraded`  | Reached backend and a classification attempt happened, but needs human follow-up (HITL). |
| `LOW_CONFIDENCE`                           | `degraded`  | Same — HITL-required manual bucket selection.                             |
| `UNRESOLVED`                               | `degraded`  | Same — HITL-required resolution.                                          |
| `ERROR` / `RUN_ERROR`                      | `failure`   | Backend emitted an error event — capture did not succeed.                 |
| SSE transport `error`                      | `failure`   | Connection / transport failed — capture did not complete successfully.    |
| Legacy `CUSTOM: HITL_REQUIRED`             | `degraded`  | Legacy equivalent of MISUNDERSTOOD.                                       |
| Legacy `CUSTOM: MISUNDERSTOOD`             | `degraded`  | Same.                                                                     |
| Legacy `CUSTOM: UNRESOLVED`                | `degraded`  | Same.                                                                     |

**General rule** for any future terminal path: reached backend and got a classification (regardless of HITL) ⇒ `success` or `degraded`; never reached backend OR backend raised an error ⇒ `failure`.

**Body shape** — conforms to `backend/src/second_brain/spine/api.py:59`'s `IngestEvent` parameter (Pydantic `RootModel`), so no shape bug is possible on the mobile side:

```
{ root: { segment_id: "mobile_capture",
          event_type: "workload",
          timestamp: <iso>,
          payload: { operation: "submit_capture",
                     outcome: "success" | "degraded" | "failure",
                     duration_ms: <measured from sendX start to terminal dispatch>,
                     correlation_kind: "capture",
                     correlation_id: <traceId> } } }
```

**Not the right hooks (for reference):**
- `mobile/lib/telemetry.ts::reportError` (line 30) — error-only and semantically about Sentry logging, not about the capture workload terminating.
- Per-`sendX` callback wrappers (the existing `wrappedCallbacks` at line 227-238, 284-295, 341-352, 398-409) — these only intercept `onError` today and would require adding wrappers for all five HITL callbacks per call site. Centralizing in `attachCallbacks` is both less code and strictly more correct.

### 4d. Scope implications for Plan 04

Plan 04 (UI) can render the transaction page exactly as CONTEXT.md describes for the DOWNSTREAM-gap case (`mobile_capture seen, classifier missing`). For the transport-failure case (no mobile_capture row + no backend_api row for a known trace id), Plan 04 should surface a dedicated empty-state: _"No transaction events recorded for this trace id. The capture request may never have reached the backend — see Sentry for client-side transport errors."_ This is the only operator-visible concession to Option B's blind spot.

---

## 5. Recommendation for Plan 02 (becomes Plan 02's task scope verbatim)

Plan 02 executes these fixes, in this order:

1. **Fix `emit_agent_workload` shape bug** — `backend/src/second_brain/spine/agent_emitter.py:63` (the line `await repo.record_event(event)` inside the `try:` block) — wrap event in `IngestEvent(root=event)`. This single edit repairs the classifier + admin + investigation emitters simultaneously because they all route through this helper via `stream_wrapper.py:41` / `admin_handoff.py:397`. Add regression test: a repository double that asserts `record_event` received an `IngestEvent`, not a bare `_WorkloadEvent`.

2. **Fix `api/telemetry.py:105,120` (mobile crud-failure path)** — same wrap treatment for both the workload emit at line 105 and the liveness emit at line 120. Add regression test exercising `crud_failure` through a repository double.

3. **Fix `tools/recipe.py:175,185 (external_services)`** — two-part:
   (a) wrap in `IngestEvent(root=event)` at line 185 OR migrate to `emit_agent_workload` (preferred — it centralises correlation handling and this bug won't recur). The `_WorkloadEvent` construction at line 175 would go away entirely in the migration path.
   (b) thread `capture_trace_id` into the `WorkloadPayload` so correlation rows land in `spine_correlation` (today the payload at line 179-183 is missing `correlation_kind`/`correlation_id` even if the write succeeds — Pitfall 2 from RESEARCH.md — `_WorkloadEvent` construction bypasses `emit_agent_workload`'s correlation precedence logic).
   (c) replace bare `except Exception: pass` at line 186-187 with `except Exception: logger.warning("recipe spine emit failed", exc_info=True)`.

4. **Add a TEST that would have caught the shape bug pre-deploy** — a pytest that calls every emit site (classifier via `spine_stream_wrapper`, admin via `emit_agent_workload`, investigation similarly, recipe's `RecipeTools`) against a fake `SpineRepository` whose `record_event` uses the REAL `IngestEvent.root` access — so the next time someone forgets the wrap, CI fails.

5. **Add mobile_capture push path (Option B — post-capture fire-and-forget)** — in `mobile/lib/ag-ui-client.ts`, centralise the emit inside the shared `attachCallbacks` helper (line 47) so it fires **exactly once on every terminal path**, covering all four submit flows (`sendCapture`, `sendVoiceCapture`, `sendFollowUp`, `sendFollowUpVoice`) in one edit. See §4c for the full terminal-path enumeration and the outcome-mapping table; the task must cover every path listed there:
   - `CLASSIFIED` → `outcome="success"`
   - `COMPLETE` / `RUN_FINISHED` (non-HITL) → `outcome="success"`
   - `MISUNDERSTOOD` / `LOW_CONFIDENCE` / `UNRESOLVED` → `outcome="degraded"` (HITL — backend reached, classification happened, human follow-up required)
   - `ERROR` / `RUN_ERROR` → `outcome="failure"`
   - SSE transport `error` listener → `outcome="failure"`
   - Legacy `CUSTOM: HITL_REQUIRED` / `MISUNDERSTOOD` / `UNRESOLVED` → `outcome="degraded"` (legacy equivalents)

   **Single-fire guard:** a closure-scoped boolean (`let emitted = false`) inside `attachCallbacks` ensures the emit fires once per stream even if multiple terminal events arrive (e.g. `CLASSIFIED` followed by `COMPLETE`, or a HITL event followed by stream close). Exact mechanism is an implementation detail — any equivalent single-fire primitive is fine.

   **Signature change:** extend `attachCallbacks(es, callbacks)` to `attachCallbacks(es, callbacks, traceId, startMs)` so the emit has `correlation_id` and `duration_ms` in scope. Each `sendX` passes the `traceId` it already owns and a `startMs = Date.now()` captured at the top of the function.

   **Body shape** (Pydantic `RootModel` — conforms to `backend/src/second_brain/spine/api.py:59`'s `IngestEvent`, no shape bug possible on mobile):
   ```
   { root: { segment_id: "mobile_capture", event_type: "workload",
             timestamp: <iso>,
             payload: { operation: "submit_capture",
                        outcome: "success" | "degraded" | "failure",
                        duration_ms: <Date.now() - startMs>,
                        correlation_kind: "capture",
                        correlation_id: <traceId> } } }
   ```
   Fire-and-forget (no retry, no queue). Issued as a `fetch(API_BASE_URL + "/api/spine/ingest", { method: "POST", ... })` AFTER the user's callback runs, so the ledger emit never blocks or delays the UI.

   **Tests:** integration tests that exercise each terminal path with a mocked EventSource + mocked `fetch` — one per outcome bucket at minimum (one `success` path, one `degraded` path, one `failure` path), plus a single-fire assertion that emits do not double up when `CLASSIFIED` and `COMPLETE` arrive on the same stream.

6. **Add a classifier-side emit verification test** — integration test that runs a real `capture` handler against a Cosmos double and asserts a workload event for `segment_id=classifier` lands after the stream completes.

### Out of scope for Plan 02 (deliberately deferred)

- **`correlation_lost` on `backend_api` (AppRequests native tagging).** OTel request-span attribute propagation from `request.state.capture_trace_id` into the inbound HTTP auto-instrumentation is a real native-correlation gap, but it's independent from the ledger making sense — the ledger's `native_links` deep-link to a time window + operation name, and the user filters in the portal. Confirmed deferred by operator feedback. Track as a dedicated follow-up (related to `project_followup_audit_first_findings.md`).
- **Duplicate Key Vault secret cleanup** (`sb-api-key` + `second-brain-api-key` both exist in `wkm-shared-kv`). Spike used the second during reproduction (see SPIKE-DATA.md §1). Pre-existing hygiene item, unrelated to spine. Tracked separately at `project_followup_duplicate_api_key_secrets.md`. Confirmed out-of-scope by operator feedback.
- **Mobile offline queue / pre-capture emit (Option A from §4a).** Option B is shipping instead — it covers the downstream-gap operator story natively and can be upgraded additively to Option A if operator experience later shows the transport-failure blind spot is costing diagnostic time. No schema change required for a future upgrade.
- **`cosmos` `activityId_g` → `capture_trace_id` mapping.** Independent follow-up. Today, spine correlation already writes a per-capture row for the `cosmos` segment when the classifier writes to the Inbox container; fixing classifier emit (step 1) will materialise that row. If a join gap remains afterwards, address separately.
- **Thread-kind correlation tagging for investigation custom spans.** Fix 1 repairs the investigation emit into `spine_events` but does not add a `thread_id` span attribute to the investigation Foundry custom spans. If the `/investigate`-side transaction page ends up empty after Plan 02 ships, address as a follow-up — again additive, no schema change.

---

## 6. Open questions for the human checkpoint

All three open questions from the first-round memo have been answered by the operator in the round-1 review. Recorded here for traceability:

1. **Mobile push-path decision — YES for `mobile_capture`, NO for `mobile_ui`.** CONFIRMED (round 1). Option A vs Option B was under-specified in round 1; round 2 picks **Option B (post-capture fire-and-forget)** — see §4a for the honest trade-off disclosure and §4d for how Plan 04 handles Option B's transport-failure blind spot.
2. **Backend_api native-correlation fix — DEFERRED (not in Plan 02).** CONFIRMED (round 1). Tracked as a separate follow-up, bundled with `project_followup_audit_first_findings.md`.
3. **Duplicate Key Vault secret cleanup — NOT in Plan 02.** CONFIRMED (round 1). Tracked at `project_followup_duplicate_api_key_secrets.md`, pre-existing hygiene item unrelated to spine.

No new open questions for this round. If the Option B framing and the explicit "Out of scope" subsection in §5 match your expectations, type `memo approved` and Plan 02 executes the numbered list verbatim.

---

*End of memo. If approved (`memo approved`), Plan 02 executes the numbered list in §5 verbatim.*
