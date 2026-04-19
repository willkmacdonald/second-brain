# Phase 19.2 — Integrated Release Verification Checklist

> **⚠️ DO NOT MERGE PLAN 02 ALONE.** Run this checklist only after Plans
> 02-05 are deployed together as a single integrated release. Plan 02
> ships emitter fixes with no read path; without Plans 03 (ledger API)
> and 04/05 (web ledger + transaction UI), the fixes move data into
> Cosmos containers that nothing user-visible reads. Shipping Plan 02
> alone produces an invisible half-state and defeats the phase goal.

---

## Scope

This checklist verifies that the six SPIKE-MEMO §5 fixes landed
correctly after the combined Plans 02-05 release deploys to Azure
Container Apps:

| § | Fix | File | Commit (Plan 02) |
|---|-----|------|-------------------|
| 5.1 | Wrap workload event in `IngestEvent(root=...)` before `record_event` | `backend/src/second_brain/spine/agent_emitter.py` | `b6394c7` |
| 5.2 | Same wrap for mobile crud_failure workload + liveness emits | `backend/src/second_brain/api/telemetry.py` | `c23befe` |
| 5.3 | Migrate recipe emitter to `emit_agent_workload`, thread `capture_trace_id`, log warning on failure | `backend/src/second_brain/tools/recipe.py` | `678d7fb` |
| 5.4 | CI regression test that walks every emit site against `_RootAccessingSpineRepo` | `backend/tests/test_spine_capture_correlation_contract.py` | `fdf320e` |
| 5.5 | Mobile Option B push-path — centralised `attachCallbacks` emit with single-fire guard, 10 terminal paths | `mobile/lib/ag-ui-client.ts` | `d310f93` |
| 5.6 | Classifier-side emit verification integration test | `backend/tests/test_spine_capture_correlation_contract.py` | `f9756bc` |

RED tests committed pre-fix: `8194116` (prior agent — Task 1 of this
plan). Stale assertions updated: `157e3a6` (Rule 1 deviation).

**Out of scope (per SPIKE-MEMO §5 "Out of scope for Plan 02"):**
- `backend_api` native-correlation fix (AppRequests missing `capture_trace_id`)
- Duplicate Key Vault secret cleanup (`sb-api-key` + `second-brain-api-key`)
- Mobile Option A (pre-capture emit with offline queue)
- Cosmos `activityId_g` → `capture_trace_id` mapping
- Thread-kind correlation tagging for investigation custom Foundry spans

---

## Pre-release baselines (captured 2026-04-18 during Plan 01 spike)

Copied from `SPIKE-DATA.md` §3a, §3b, §3c, §4a so the integrated-release
reviewer does not have to re-derive ground truth during rollout. These
are the **before** numbers; the **after** verification below compares
post-release queries to these counts.

### Per-segment workload event counts — last 24h (spine_events)

| Segment             | workload_count_24h | with_correlation_id | Category       |
|---------------------|-------------------:|--------------------:|----------------|
| backend_api         |             27,639 |                   3 | correlation_lost (deferred) |
| classifier          |                  0 |                   0 | **broken_emitter** — §5.1 target |
| admin               |                  0 |                   0 | **broken_emitter** — §5.1 target |
| investigation       |                  0 |                   0 | **broken_emitter** — §5.1 target |
| external_services   |                  0 |                   0 | **broken_emitter** — §5.3 target |
| mobile_ui (crud)    |                  0 |                   0 | latent broken_emitter — §5.2 target |
| mobile_capture      |                  0 |                   0 | **pull→push** — §5.5 target |
| cosmos              |                  0 |                   0 | pull_by_design (unchanged) |
| container_app       |                  0 |                   0 | pull_by_design (unchanged) |

### Per-segment liveness counts — last 10 min (proves segments are alive)

| Segment             | liveness_count_10m |
|---------------------|-------------------:|
| admin               |                 20 |
| backend_api         |                 20 |
| classifier          |                 20 |
| container_app       |                 20 |
| cosmos              |                 20 |
| external_services   |                 20 |
| investigation       |                 20 |
| mobile_capture      |                 20 |
| mobile_ui           |                 20 |

Liveness works today (it's driven by `spine/background.py::liveness_emitter`
which already wraps in `IngestEvent(root=...)`). This proves the
workload gap is specifically the emit-site bug, not infrastructure.

### Spike trace baseline (`spike-20260418T235549Z`)

**spine_correlation rows for the spike capture trace (pre-release):**

```
[ backend_api × 2 rows — POST /api/capture + GET /api/errands ]
```

Only backend_api joins `spine_correlation`. After the integrated
release, a freshly captured trace should join **at minimum** backend_api
+ classifier + cosmos (via classifier's Inbox write) rows — and admin +
mobile_capture if the capture routes to Admin.

**audit_correlation(kind="capture", limit=1, time_range_seconds=3600) — pre-release:**

```
clean_count: 0
warn_count: 0
broken_count: 1
instrumentation_warning: backend_api appears to have lost correlation_id tagging
```

---

## Post-release verification steps

Run these against `https://brain.willmacdonald.com` after Plans 02-05
are deployed together and CI is green.

### Step 1 — Issue a fresh tagged capture against the deployed backend

```bash
# Generate a unique trace id for this verification run
VERIFY_TRACE="verify-19.2-$(date -u +%Y%m%dT%H%M%SZ)"
echo "Verification trace id: $VERIFY_TRACE"

# Get the API key from Key Vault (use second-brain-api-key; the
# duplicate sb-api-key cleanup is a separate follow-up).
API_KEY=$(az keyvault secret show \
  --vault-name wkm-shared-kv \
  --name second-brain-api-key \
  --query value -o tsv)

# POST a capture that routes to Admin (so the admin + classifier paths
# both fire). Include X-Trace-Id so the middleware tags the trace id
# into spine_correlation for the backend_api row.
curl -sS -N \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: $VERIFY_TRACE" \
  -X POST https://brain.willmacdonald.com/api/capture \
  -d '{"text": "buy milk tomorrow", "thread_id": "verify-thread", "run_id": "verify-run"}' \
  | tee /tmp/capture-$VERIFY_TRACE.sse

# Sleep ~30s for background admin processing + cosmos write to complete.
sleep 30
```

### Step 2 — Query `spine_events` for the fresh trace (Cosmos)

Run these queries against the `second-brain` database in the
`shared-services-cosmosdb` account. Expected **after** the integrated
release:

```
SELECT c.segment_id, c.event_type, c.payload.operation,
       c.payload.outcome, c.payload.correlation_kind,
       c.payload.correlation_id, c.timestamp
FROM c
WHERE c.payload.correlation_id = @trace
ORDER BY c.timestamp
```

**Pass criteria per segment (after Plan 02 fixes):**

| Segment             | Expected ≥1 workload row? | correlation_kind | Evidence the fix landed         |
|---------------------|:-------------------------:|------------------|----------------------------------|
| backend_api         | YES (was YES)             | capture          | Unchanged — already worked       |
| classifier          | **YES (was NO)**          | capture          | §5.1 wrap lands — `operation` contains `capture_text` |
| admin               | **YES (was NO)**          | capture          | §5.1 wrap lands — only if trace routes to Admin |
| investigation       | N/A for capture trace; verify separately via `/investigate` with thread id | n/a / thread | §5.1 wrap |
| external_services   | Only if capture contains a recipe URL; skip for "buy milk tomorrow" | capture | §5.3 migration |
| mobile_capture      | N/A from curl (native mobile only); test from EAS build | capture | §5.5 fetch POST to `/api/spine/ingest` |
| mobile_ui (crud)    | Verify via mobile-initiated delete/recategorize | crud | §5.2 wrap — latent path, only fires on crud_failure |
| cosmos              | NO (pull_by_design)       | n/a              | No change expected               |
| container_app       | NO (pull_by_design)       | n/a              | No change expected               |

### Step 3 — Query `spine_correlation` for the fresh trace (Cosmos)

```
SELECT * FROM c
WHERE c.correlation_kind = "capture"
  AND c.correlation_id = @trace
ORDER BY c.timestamp
```

**Pass criteria:** The rows returned should match the "YES" rows in the
Step 2 table — if `spine_events` has a workload row with correlation
fields, `SpineRepository.record_event` (`storage.py:54-82`) upserts a
matching `spine_correlation` row in the same call. A segment in
`spine_events` without a paired `spine_correlation` row means the
correlation fields on the payload are missing or empty.

### Step 4 — Audit correlation via the MCP tool

```
audit_correlation(
  correlation_kind="capture",
  correlation_id="$VERIFY_TRACE",
  time_range_seconds=3600
)
```

**Pass criteria:**

| Field                | Pre-release value | Expected post-release |
|----------------------|-------------------|------------------------|
| `clean_count`        | 0                 | ≥ 2 (backend_api + classifier minimum) |
| `warn_count`         | 0                 | Any value OK — a residual `instrumentation_warning` on `backend_api` is expected and explicitly deferred |
| `broken_count`       | 1                 | 0 for the three §5.1 segments (classifier, admin, investigation); the single remaining `broken_count` from the `correlation_lost` backend_api gap is deferred |
| `instrumentation_warning` | present    | may remain — `backend_api appears to have lost correlation_id tagging` is the deferred follow-up (memo §3b) |

Also run the sample-mode audit (no specific trace):

```
audit_correlation(
  correlation_kind="capture",
  sample_size=5,
  time_range_seconds=3600
)
```

**Pass criteria:** Across 5 recent captures, the `clean_count` should
be > 0 (was 0 pre-release). `broken_count` for classifier should
transition from "every trace" to "zero traces" — traces where the
classifier emit fires correctly will appear as clean.

### Step 5 — Query App Insights for the AttributeError stacktrace (should be absent)

```kql
AppExceptions
| where TimeGenerated > ago(30m)
| where OuterMessage has "'_WorkloadEvent' object has no attribute 'root'"
   or InnermostMessage has "'_WorkloadEvent' object has no attribute 'root'"
| count
```

**Pass criteria:** 0 rows in the 30 minutes after the release deploys.
Pre-release, the spike window produced 3 rows in 22 seconds (memo §3a
evidence). Zero post-release proves the wrap fix is live for
classifier, admin, and investigation simultaneously.

### Step 6 — Verify the web ledger renders the fresh trace (Plans 04/05)

**URLs to confirm** (populated once Plans 04 and 05 are deployed):

- `https://<spine-web-url>/segment/classifier` — should render ledger
  rows for the verification capture within 30 seconds.
- `https://<spine-web-url>/segment/admin` — should render a row if the
  verification capture routed to Admin.
- `https://<spine-web-url>/correlation/capture/$VERIFY_TRACE` — should
  render the full transaction path (backend_api → classifier →
  admin → cosmos for an Admin-routed capture; backend_api →
  classifier → cosmos for non-Admin).

**Pass criteria:**
- Each segment page shows the newly-landed rows without a "no data"
  empty state.
- The transaction page shows a linked timeline with at least 3 rows
  (backend_api + classifier + at least one downstream) for an
  Admin-routed capture.
- Native diagnostics deep links (App Insights panels) are still
  reachable — this was working before Plan 02; re-confirm no
  regression.

### Step 7 — Mobile Option B verification (after mobile EAS build deploys)

After an EAS build of the updated mobile app is installed:

1. Capture a text thought on the phone with Wi-Fi connected.
2. Copy the capture trace id from the Sentry breadcrumb (or from the
   `/investigate` log lookup) — it's the `X-Trace-Id` the app generated.
3. Run the same Step 2 query with that trace id.
4. **Pass criteria:** a `mobile_capture` workload row appears in
   `spine_events` with `operation=submit_capture`, `outcome=success`
   (or `degraded` if HITL triggered, or `failure` if the SSE stream
   errored), `correlation_kind=capture`, `correlation_id=<traceId>`.

5. **Single-fire guard check:** issue a capture that returns a
   classification (triggers the CLASSIFIED event → emit → COMPLETE
   event). Query `spine_events` — there should be exactly **one**
   `mobile_capture` workload row for that trace id, not two.

---

## Residual gaps the memo deferred (by design)

Citations are to `SPIKE-MEMO.md` §5 "Out of scope for Plan 02
(deliberately deferred)". These are known and not in scope for Plan 02
or the integrated release; they will show up in the post-release
audit as the listed symptoms.

| Residual gap | Expected symptom after release | Memo citation | Follow-up tracker |
|---|---|---|---|
| `backend_api` native-correlation gap | `instrumentation_warning` still returned by `audit_correlation`; `AppRequests` rows for `/api/capture` still lack `capture_trace_id`; portal-native drill-down still defaults to operation_id | §5 "Out of scope" bullet 1; §3b | `project_followup_audit_first_findings.md` |
| Duplicate Key Vault secret | `sb-api-key` and `second-brain-api-key` both still present; use `second-brain-api-key` in Step 1 | §5 "Out of scope" bullet 2 | `project_followup_duplicate_api_key_secrets.md` |
| Mobile Option A (pre-capture emit with offline queue) | A capture that fails to reach `/api/capture` over the network produces no `mobile_capture` row and no `backend_api` row — the ledger shows "no transaction events for this trace id". Plan 04 surfaces this as an empty-state pointing at Sentry. | §5 "Out of scope" bullet 3; §4a trade-off disclosure; §4d UX concession | Revisit if operator experience shows the blind spot is costing diagnostic time |
| Cosmos `activityId_g` → `capture_trace_id` mapping | The cosmos segment's `activityId_g` still does not join the capture timeline; cosmos ledger rows appear by correlation-kind via the classifier's Inbox write alone | §5 "Out of scope" bullet 4 | Independent follow-up if join gap remains after §5.1 fix materialises classifier emit |
| Thread-kind span attribute on investigation Foundry custom spans | `/investigate`-side transaction page may be empty or show only backend_api rows for thread traces | §5 "Out of scope" bullet 5 | Revisit after Plan 02 if `/investigate` transaction page is empty |

---

## Sign-off checklist

- [ ] Step 1 — Fresh tagged capture issued; no HTTP error from the API
- [ ] Step 2 — Classifier workload row present in `spine_events` (was 0, expected ≥1)
- [ ] Step 2 — Admin workload row present if capture routed to Admin (was 0, expected ≥1)
- [ ] Step 3 — `spine_correlation` rows joinable for the fresh trace, matching Step 2
- [ ] Step 4 — `audit_correlation` `clean_count` > 0 for the fresh trace (was 0)
- [ ] Step 4 — `audit_correlation` targeted trace has `broken_count` = 0 for classifier/admin/investigation
- [ ] Step 5 — Zero AttributeError rows for `_WorkloadEvent.root` in App Insights in 30-min post-deploy window (was 3 in 22s during the spike)
- [ ] Step 6 — Web segment page renders fresh rows for classifier + admin (Plans 04/05 dependent)
- [ ] Step 6 — Web transaction page renders multi-segment timeline for the fresh trace (Plan 05 dependent)
- [ ] Step 7 — Mobile EAS build: `mobile_capture` row lands for a phone capture with single-fire guard honoured
- [ ] Residual gaps section acknowledged — no surprise regressions outside deferred items

---

*Produced as part of Phase 19.2 Plan 02 Task 3. Read-only. Do not ship
Plan 02 emitter fixes without Plans 03-05 ready to land together in a
single integrated release.*
