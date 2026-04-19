# Phase 19.2 Plan 01 — Spike Memo

**Status:** Awaiting human approval (Plan 01 Task 3 gate)
**Evidence:** See [SPIKE-DATA.md](./SPIKE-DATA.md) for raw query output, App Insights stack traces, and audit_correlation reports. This memo contains categorization and recommendations only — no raw data.

---

## 1. Summary (3 lines)

1. **Capture chain:** Every agent-side emitter (classifier / admin / investigation) is silently broken by a single Pydantic shape bug — `_WorkloadEvent` is being passed to `record_event` instead of `IngestEvent(root=_WorkloadEvent)`. All three sites fail with the same `AttributeError: '_WorkloadEvent' object has no attribute 'root'` the moment they fire. The code LOOKS right but the deployed behaviour is zero landed events.
2. **Thread chain:** Investigation never writes a `thread`-kind correlation row for the same reason (shared helper). The audit tool therefore reports `sample_size_returned=0` for thread correlations in every run.
3. **Mobile push-path decision:** **YES** — add normal-capture workload emission from `mobile_capture`. The operator UX CONTEXT.md describes ("mobile_capture seen, classifier missing" as an explicit gap on the transaction page) is only possible if mobile is in the ledger. Rationale and scope in §4.

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

### Rationale

CONTEXT.md's transaction-page UX is literally: _"gaps must be explicit: 'backend_api seen, classifier missing'"_. The very first example of an explicit gap is **mobile_capture → backend_api**. Without a mobile_capture emit path, the ledger cannot distinguish these two ops-scenarios:

- "Capture never arrived at backend" (network failure, bad URL, app down) — **mobile_capture emitted, backend_api missing**
- "Capture arrived at backend but classifier crashed" — **mobile_capture emitted, backend_api emitted, classifier missing**

Both collapse to a single observation today: _"no transaction rows for this trace_id."_ That's exactly the lossy signal CONTEXT.md's ledger UX is designed to avoid.

The RESEARCH.md "Pitfall 3" correctly warned NOT to pre-plan this as a bug fix — but the spike has now answered the question CONTEXT.md explicitly delegated to the spike. The operator UX demands mobile_capture be emit-first.

**`mobile_ui` is different.** Mobile UI is the CRUD-screen segment — it emits for destructive operations (delete errand, update destination, etc.), not for a capture. A capture doesn't "touch" mobile_ui. For the CAPTURE chain, `mobile_ui` is correctly `pull_by_design`. The crud_failure path it already has today is the right model. (However, `telemetry.py:105,120` is latently broken the same way `agent_emitter.py:63` is — both need the IngestEvent wrap. That's a prereq for mobile_ui being a functioning emitter at all for its native correlation_kind=`crud`.)

### Scope implications

If Will approves:

- **Plan 02 (emitter fixes)** additionally includes: a new push path from the Expo app — on every capture submission, POST a lightweight workload-event to `/api/spine/ingest` (already exists at `spine/api.py:59`) with `segment_id="mobile_capture"`, `correlation_kind="capture"`, `correlation_id=<the trace id sent in X-Trace-Id on the capture POST>`, `operation="submit_capture"`, `outcome="success"|"failure"` based on the HTTP response.
- **Plan 04 (UI)** stays as-planned — it just gets a richer ledger to render because mobile_capture will now show up.

If Will rejects:

- Plan 02 drops the mobile_capture task.
- Plan 04 UI must explicitly label mobile_capture and mobile_ui rows "native-only (Sentry) — see Sentry panel below" and not render them in the expected-chain gap callout.

---

## 5. Recommendation for Plan 02 (becomes Plan 02's task scope verbatim)

Plan 02 executes these fixes, in this order:

1. **Fix `emit_agent_workload` shape bug** — `backend/src/second_brain/spine/agent_emitter.py:63` — wrap event in `IngestEvent(root=event)`. This single edit repairs the classifier + admin + investigation emitters simultaneously because they all route through this helper. Add regression test: a repository double that asserts `record_event` received an `IngestEvent`, not a bare `_WorkloadEvent`.

2. **Fix `api/telemetry.py:105,120` (mobile crud-failure path)** — same wrap treatment for both the workload and liveness emits. Add regression test exercising `crud_failure` through a repository double.

3. **Fix `tools/recipe.py:185` (external_services)** — two-part:
   (a) wrap in `IngestEvent(root=event)` OR migrate to `emit_agent_workload` (preferred — it centralises correlation handling and this bug won't recur).
   (b) thread `capture_trace_id` into the `WorkloadPayload` so correlation rows land in `spine_correlation` (today the payload is missing `correlation_kind`/`correlation_id` even if the write succeeds — Pitfall 2 from RESEARCH.md).
   (c) replace bare `except: pass` with `except Exception: logger.warning("recipe spine emit failed", exc_info=True)`.

4. **Add a TEST that would have caught the shape bug pre-deploy** — a pytest that calls every emit site (classifier via `spine_stream_wrapper`, admin via `emit_agent_workload`, investigation similarly, recipe's `RecipeTool`) against a fake `SpineRepository` whose `record_event` uses the REAL `IngestEvent.root` access — so the next time someone forgets the wrap, CI fails.

5. **Add mobile_capture push path** (IF §4 answer is YES) — Expo app sends a fire-and-forget POST to `/api/spine/ingest` after `/api/capture` completes, with the same `X-Trace-Id` as `correlation_id`. Wire into the existing capture submit flow; use the existing `IngestEvent` wire format (the ingest endpoint takes an `IngestEvent` from the request body directly, so no shape bug possible).

6. **Add a classifier-side emit verification test** — integration test that runs a real `capture` handler against a Cosmos double and asserts a workload event for `segment_id=classifier` lands after the stream completes.

**Deliberately deferred to a follow-up (NOT Plan 02 scope):**

- **`correlation_lost` on `backend_api` (AppRequests native tagging).** This requires OTel request-span attribute propagation from `request.state.capture_trace_id` into the inbound HTTP auto-instrumentation. It's a real gap but it's independent from the ledger making sense — the ledger's `native_links` don't depend on AppRequests filters (they deep-link to the time window + operation name, and the user filters in the portal). Leave this to a Phase 19.1-style follow-up.
- **`cosmos` `activityId_g` → `capture_trace_id` mapping.** Same — independent follow-up. Today, spine correlation already has the per-capture row for the `cosmos` segment when the classifier writes to the Inbox container; fixing classifier emit (step 1) will materialise that row. If there's still a join gap afterwards, address separately.

---

## 6. Open questions for the human checkpoint

1. **Mobile push-path decision — confirm YES for `mobile_capture`, NO for `mobile_ui`.**
   - YES-YES: adds Expo push on EVERY crud too (e.g. pressing a `delete errand` emits to spine). Redundant with existing crud_failure path and much noisier.
   - YES-NO (recommended): mobile_capture gets a normal-capture emit; mobile_ui keeps its crud_failure-only model.
   - NO-NO: ledger UI must render both mobile segments as native-only badges for the capture chain.
2. **Should Plan 02 also take the `backend_api` native-correlation fix (§3b)?** I've recommended deferring to a follow-up. If you want it IN Plan 02 instead, bundle it as a separate task rather than mixing with the emitter shape fix — different mechanism, different risk profile.
3. **Should Plan 02 also fix the duplicate Key Vault secret (`sb-api-key` + `second-brain-api-key`)?** Spike tripped over it — both exist. Tracked as `project_followup_duplicate_api_key_secrets.md`. Unrelated to spine, so my default answer is NO (stay in Plan 02's scope).

---

*End of memo. If approved (`memo approved`), Plan 02 executes the numbered list in §5 verbatim.*
