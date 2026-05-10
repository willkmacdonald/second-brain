# Design-Coverage Audit: 23-foundry-ga-prep

**Date:** 2026-05-08
**Design source:** [docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md](../../../docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md)
**Plans audited:**
- `.planning/phases/23-foundry-ga-prep/23-01-PLAN.md` (dep spike + probe scaffold)
- `.planning/phases/23-foundry-ga-prep/23-02-PLAN.md` (probe implementations + runs + FINDINGS)
- `.planning/phases/23-foundry-ga-prep/23-03-PLAN.md` (18 golden-trace fixtures)
- `.planning/phases/23-foundry-ga-prep/23-04-PLAN.md` (eval baseline + EVAL-INVENTORY + portal export)
- `.planning/phases/23-foundry-ga-prep/23-05-PLAN.md` (CONFIG-DELTAS + SPAN-NAME-MAPPING + AUDITOR-VERIFICATION)

## Verdict

**FAIL**: One ❌ WRONG-SOURCE finding — the eval baseline's classifier per-bucket metric verifier looks for key names that the runner does not produce. The actual `aggregateScores` shape from `runner.py:174-176` and `eval/metrics.py:14-67` writes top-level `precision` and `recall` per-bucket dicts (NOT under `perBucket`/`per_bucket`/`perClass`/`per_class`/`byBucket`/`by_bucket`).

| Counter | Value |
|---|---:|
| ✓ COVERED fields | 26 |
| ⚠️ PARTIAL coverage | 2 |
| ❌ MISSING | 0 |
| ❌ WRONG-SOURCE | 1 |
| Endpoint-field mismatches | 1 |

**Verdict states:**
- **PASS** = 0 ❌ AND 0 endpoint mismatches
- **PASS-WITH-WARNINGS** = 0 ❌, ≥1 ⚠️
- **FAIL** = ≥1 ❌

This is a single regression introduced when round-14 added the per-class metric requirement. The fix is local to the verify block in `23-04-PLAN.md` (Task 1 verify block + acceptance criteria) — the data IS produced by the runner; the verifier just looks under the wrong key names.

## ❌ WRONG-SOURCE — plan extracts from wrong endpoint or asserts on wrong field name

### W-01: classifier per-bucket precision/recall key name

- **Design line:** [`docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md:568`](../../../docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md)
  > "Pre-migration baseline output JSON includes: classifier overall accuracy, per-bucket precision/recall, admin routing accuracy, per-destination precision/recall, sample size, model name, framework version."
- **Pass criteria (design line 570):** "no class-specific precision drop > 5pp; no class-specific recall drop > 5pp."
- **Plan extracts from:** `/api/eval/results?eval_type=classifier&limit=5` at `23-04-PLAN.md:241-273`. The endpoint IS the right source — but the verifier asserts the wrong key names.
- **Verifier asserts (`23-04-PLAN.md:339`):**
  ```jq
  .classifier.aggregateScores | (has("perBucket") or has("per_bucket") or has("perClass") or has("per_class") or has("byBucket") or has("by_bucket"))
  ```
- **Actual source-of-truth:**
  - `backend/src/second_brain/eval/metrics.py:61-67` — `compute_classifier_metrics()` returns `{"accuracy": ..., "total": ..., "correct": ..., "precision": <per-bucket dict>, "recall": <per-bucket dict>}`. No top-level `perBucket` key exists.
  - `backend/src/second_brain/eval/runner.py:174-176` — runner does `metrics = compute_classifier_metrics(individual_results); calibration = compute_confidence_calibration(individual_results); metrics["calibration"] = calibration`, then writes `aggregateScores=metrics` at line 183.
  - `backend/src/second_brain/models/documents.py:208-210` — `EvalResultsDocument.aggregateScores` docstring literally says: `e.g., {"accuracy": 0.92, "precision": {...}, "recall": {...}}`.
- **Why it matters:** The verifier in step 9 is a hard `jq -e` assertion. Run the eval baseline today, fetch `aggregateScores` from `/api/eval/results`, and the JSON shape will be `{accuracy, total, correct, precision: {Person: ..., Projects: ...}, recall: {Person: ..., ...}, calibration: [...]}`. The `(has("perBucket") or has("per_bucket") or ...)` chain returns false → the verifier fails → the operator sees `FATAL` and the baseline is rejected even though the data IS present under the right semantic structure.
- **Recommended fix:** in `23-04-PLAN.md` Task 1 verify block, replace the classifier per-bucket key check with one that matches the actual runner output. Two equivalent options:
  - **Strict:** `jq -e '.classifier.aggregateScores | has("precision") and has("recall") and (.precision | type == "object") and (.recall | type == "object") and (.precision | length > 0)'`
  - **Defensive (preferred — keeps the round-14 forward-compat allow-list):** extend the existing `or has(...)` chain with `precision` and `recall`:
    ```jq
    .classifier.aggregateScores | (has("perBucket") or has("per_bucket") or has("perClass") or has("per_class") or has("byBucket") or has("by_bucket") or has("precision") or has("recall"))
    ```
    Then add a stronger inner-shape assertion: `(.precision | type == "object" and length > 0) and (.recall | type == "object" and length > 0)` so the verifier actually proves per-bucket entries exist (not just that the top-level key is present with no contents).
- **Knock-on action:** also update the discovery-on-failure hint in `23-04-PLAN.md:259-263` and `:314` (which currently tells the operator to run `jq '.results[0].aggregateScores | keys'` to discover key names). The hint will surface `precision` / `recall` correctly once the operator runs it; the verifier just needs to accept those names a priori so the failure path doesn't fire.

The admin per-destination check in the same verify block (`.admin.aggregateScores | (has("perDestination") or has("per_destination") or ...)`) IS correct: `compute_admin_metrics()` returns `{"routing_accuracy", "total", "correct", "per_destination"}` (verified at `eval/metrics.py:171-176`). The `per_destination` snake_case form matches one of the allow-list entries.

## ⚠️ PARTIAL — covered but not asserted, or asserted on wrong path

### P-01: admin per-destination "precision/recall" vs flat-accuracy

- **Design line:** [`design.md:568`](../../../docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md) — "per-destination precision/recall"
- **Plan capture:** the verifier requires `.admin.aggregateScores.per_destination` (or one of its allow-listed siblings) to exist as an object. ✓ This will pass.
- **Issue:** `compute_admin_metrics()` at `eval/metrics.py:165-169` writes `per_destination[dest] = sum(1 for c in correctness_list if c) / len(correctness_list)` — a single accuracy number per destination, NOT precision and recall separately. The design says "per-destination precision/recall" (two metrics per class). The runner produces only one (accuracy = correct/total per destination, which is recall when grouped by expected class).
- **Severity:** PARTIAL because (a) the plan correctly captures whatever the runner produces; (b) the gate computation in Phase 24 ("no class-specific precision drop > 5pp; no class-specific recall drop > 5pp") will operate on the same single-metric-per-destination shape on both sides of the migration; (c) the comparison is internally consistent. Whether this is a runner deficiency vs. a design imprecision is out of scope for this audit (the planner should not add fields the runtime doesn't produce — that's bucket-2). Flagged for visibility: when Phase 24 wires the ±5pp class-specific drop check, it operates on a single accuracy metric, not separate precision and recall. If the operator wants strict precision/recall per destination, that's a runner change in `metrics.py`, not a plan change.
- **Recommended:** No plan edit required. Document the asymmetry in `EVAL-INVENTORY.md` (Phase 24 task group 23.2 planner read) so the GA implementation doesn't accidentally introduce a stricter per-destination-precision/recall contract that the runner can't honor.

### P-02: admin handoff `admin.tool_invoked` value type

- **Design line:** Implicit — design line 568 area + 23-03 task 2 verifier expectation.
- **Plan asserts (`23-03-PLAN.md:755`):**
  ```jq
  any(.[]; .ItemType == "Dependency" and .Name == "admin_agent_process" and (.Properties["admin.tool_invoked"] == "true" or .Properties["admin.tool_invoked"] == true))
  ```
- **Actual source-of-truth:** `backend/src/second_brain/processing/admin_handoff.py:252` — `span.set_attribute("admin.tool_invoked", any_tool_called)` where `any_tool_called` is a Python `bool`. OTel span attributes go through Application Insights as either bool or string depending on backend serialization. The KQL `Properties` column may surface it as `"true"` (stringified) or as a JSON true; the plan defensively accepts both.
- **Issue:** the dual-form match is correct and defensive. The `_coerce` helper (introduced in round-7) preserves the dict shape so `Properties["admin.tool_invoked"]` reaches jq with the original type. Both branches of the OR fire correctly.
- **Severity:** PARTIAL only because future Application Insights ingestion changes could produce other forms (`"True"` capitalized, `1`/`0`, etc). Currently safe.
- **Recommended:** No edit required.

## ✓ COVERED — design field captured and asserted

### Eval baseline (design line 568 area, design D-04 + D-06)

| Field | Design line | Source endpoint/span | Plan file:line | Verifier file:line |
|---|---|---|---|---|
| `classifier.accuracy` (overall) | L568 | `/api/eval/results` (via `aggregateScores.accuracy` from `metrics.py:62`) and `/api/eval/status` (via `runner.py:208`) | `23-04-PLAN.md:329` | `23-04-PLAN.md:330` |
| `classifier.total` (sample size ≥50) | L568 | `/api/eval/status` (`runner.py:209`) | `23-04-PLAN.md:331` | `23-04-PLAN.md:331` |
| `classifier.correct` | L568 | `/api/eval/status` (`runner.py:210`) | `23-04-PLAN.md:332` | `23-04-PLAN.md:332` |
| `admin.routing_accuracy` | L568 | `/api/eval/results` (via `aggregateScores.routing_accuracy` from `metrics.py:172`) and `/api/eval/status` (`runner.py:360`) | `23-04-PLAN.md:335` | `23-04-PLAN.md:335` |
| `admin.total` (>0 per runner contract) | L568 | `/api/eval/status` (`runner.py:361`) | `23-04-PLAN.md:336` | `23-04-PLAN.md:336` |
| `admin.aggregateScores.per_destination` | L568 — "per-destination" | `/api/eval/results` row's `aggregateScores` from `metrics.py:175` | `23-04-PLAN.md:340` | `23-04-PLAN.md:340` |
| `evalType` (classifier+admin) | Design D-04 | POST `/api/eval/run` response (per `eval.py:115`); status endpoint does NOT preserve | `23-04-PLAN.md:227-238` (POST-time merge via shell vars) | `23-04-PLAN.md:329, 334` |
| `framework_version` (RC pin) | Implicit (design D-05) | composed at fixture time | `23-04-PLAN.md:288` | `23-04-PLAN.md:326` |
| `model_deployment` | L568 ("model name") | composed at fixture time | `23-04-PLAN.md:287` | indirect |
| `admin_routing_context_seed` (reproducibility) | Implicit (design D-13) | composed at fixture time | `23-04-PLAN.md:289` | `23-04-PLAN.md:327` |

### Foundry probe fixtures (design "Foundry probe harness" section, ~line 280)

| Field | Design line | Source endpoint/span | Plan file:line | Verifier file:line |
|---|---|---|---|---|
| `streaming_shape.update_count` (count of `AgentRunResponseUpdate` events) | L307 | `_write_fixture('streaming_shape', ...)` payload from `agent.run_stream()` loop | `23-02-PLAN.md:354-371` | `23-02-PLAN.md:882` |
| `streaming_shape.updates[]` (per-update `type`/`repr`/`fields`) | L307 — "every update yielded" | introspected via `dir(update)` | `23-02-PLAN.md:357-363` | `23-02-PLAN.md:882-887` |
| `streaming_shape.thread_deleted_after_run` | L293 ("Optional cleanup") | `_maybe_delete_thread` outcome | `23-02-PLAN.md:365-371` | implicit (FINDINGS section in 23-02 Task 3) |
| `tool_call_extraction.response_repr`/`response_fields` | L308 | `agent.run()` non-streaming response, full introspection | `23-02-PLAN.md:392-411` | `23-02-PLAN.md:881` |
| `tool_call_extraction.top_level_tool_calls` | L308 | `getattr(response, 'tool_calls', None) is not None` | `23-02-PLAN.md:409` | implicit (FINDINGS Probe 2 names extraction path) |
| `tool_call_extraction.messages_walk[]` | L308 — "messages[].content[]" | per-message introspection via `dir(msg)` | `23-02-PLAN.md:414-426` | implicit |
| `tool_choice_required.trials.auto` | L309 — baseline | `tool_choice="auto"` trial | `23-02-PLAN.md:457-468` | `23-02-PLAN.md:883` |
| `tool_choice_required.trials.required` | L309 — primary verification | `tool_choice="required"` trial | `23-02-PLAN.md:471-485` | `23-02-PLAN.md:884` |
| `tool_choice_required.trials.provider_dict` | L309 — fallback | `tool_choice={"type":"function",...}` trial | `23-02-PLAN.md:488-503` | `23-02-PLAN.md:885` |
| `tool_choice_required` verdict (one of three quoted strings) | L309, D-07b | FOUNDRY-PROBE-FINDINGS.md Probe 3 section | `23-02-PLAN.md:996-998` | `23-02-PLAN.md:1082-1093` (counts grep matches; exits if !=1) |
| `session_rehydration.thread_identifier_shape` | L310 — "stored identifier shape" | `dir(thread)` introspection of `AgentThread` | `23-02-PLAN.md:535-543` | `23-02-PLAN.md:886` |
| `session_rehydration.turn_one_updates`/`turn_two_updates` | L310 — "both turn outputs" | two `agent.run_stream` calls with same thread | `23-02-PLAN.md:528-549` | `23-02-PLAN.md:1015-1017` (FINDINGS structural assertion) |
| `session_rehydration` PINEAPPLE continuity check | L310 — "confirms continuity" | turn-2 messages reference turn-1 magic word | `23-02-PLAN.md:529, 547` | `23-02-PLAN.md:1016` (FINDINGS narrative — soft assert) |
| `auth_probe.token_acquisition.acquired` | L311 | `cred.get_token(...)` outcome | `23-02-PLAN.md:580-589` | implicit (FINDINGS Probe 5) |
| `auth_probe.rbac.role_assignments_raw` | L311 — "RBAC role names confirmed" | `az role assignment list` subprocess | `23-02-PLAN.md:593-607` | implicit (FINDINGS) |
| `auth_probe.invocation.succeeded` | L311 — "sample agent response" | `agent.run()` outcome | `23-02-PLAN.md:613-633` | implicit (FINDINGS) |
| `auth_probe.deployed_credential_class_note` (managed identity vs CLI distinction) | L311 — "Does NOT simulate ManagedIdentityCredential" | hardcoded note in payload | `23-02-PLAN.md:637` | implicit |
| `probe.run_id` + `probe.name` span tags | L291-292 — pollution containment | `ProbeTagSpanProcessor.on_start` | `23-02-PLAN.md:229-256` | KQL coverage check `23-02-PLAN.md:1130-1146` |

### Golden-trace fixtures (design "Validation contract details", L552-565)

| Field | Design line | Source endpoint/span | Plan file:line | Verifier file:line |
|---|---|---|---|---|
| `<name>.input.json` (request payload) | L556 | composed before curl | `23-03-PLAN.md:251-275` (inv), `:572-590` (admin), `:850-854` (clf) | per-task acceptance criteria |
| `<name>.sse.jsonl` (event stream, one per line) | L557 | curl `-N` SSE streaming, Python regex parser | `23-03-PLAN.md:283-321` | wc-l > 0 in each task verify |
| `<name>.spans.json` (App Insights span tree) | L558 | KQL `query_workspace` against shared-services-logs | `23-03-PLAN.md:344-426` (inv two-stage join), `:632-687` (admin/clf canonical) | `jq empty` + length > 0 |
| `<name>.expected-deltas.md` (allowed deltas) | L559 | hand-authored per fixture | `23-03-PLAN.md:436-462` | grep "## Same" + "## Allowed-different" |
| Investigation `Properties["investigate.thread_id_out"]` correlation | L92 + L518-522 | `tracer.start_as_current_span("investigate")` + `span.set_attribute("investigate.thread_id_out", final_thread)` at `investigation_adapter.py:96, 187` | `23-03-PLAN.md:329-340` (parse from SSE done) + `:368-394` (KQL two-stage) | `23-03-PLAN.md:486-491` (asserts exactly 1 custom investigate span + exactly 1 /api/investigate AppRequests row at same OperationId) |
| Admin `admin_agent_process` AppDependencies presence | L705 (expected-deltas) + design D-04 admin behavior | `processing/admin_handoff.py:177` (`tracer.start_as_current_span("admin_agent_process")`) | `23-03-PLAN.md:746-749` | `23-03-PLAN.md:746-750` (hard fail if ADMIN_SPAN_COUNT < 1) |
| Admin `admin.tool_invoked` attribute | round-14 P2 | `processing/admin_handoff.py:252` | `23-03-PLAN.md:751-757` | `23-03-PLAN.md:755-756` (hard fail unless allow-listed) |
| Capture `Properties["capture.trace_id"]` correlation (admin + classifier) | L92 — per-agent split | `api/capture.py:217, 366` reads X-Trace-Id; in-process handoff inherits | `23-03-PLAN.md:596-611` (admin), `:861-869` (classifier) | `23-03-PLAN.md:744` (admin), `:1054` (classifier dual-trace check) |
| Voice `file=@<path>` multipart form field | round-13 P1-B | `backend/src/second_brain/api/capture.py:271` (`file: UploadFile = File(...)`) | `23-03-PLAN.md:872-882` | `23-03-PLAN.md:1086` |
| `low_confidence_followup` body fields (`inbox_item_id`, `follow_up_text`, `follow_up_round`) | round-1 P1-A | `backend/src/second_brain/api/capture.py` `FollowUpBody` model | `23-03-PLAN.md:919-930` | `23-03-PLAN.md:1061` (`has("inbox_item_id") and has("follow_up_text") and has("follow_up_round")`) |
| `Properties` column type preserved as JSON object (not stringified) | round-7 P1-A | `_coerce` helper in KQL export | `23-03-PLAN.md:397-417` | `23-03-PLAN.md:493` (every task asserts `all(.[]; .Properties | type == "object")`) |

### Other artifacts (CONFIG-DELTAS, SPAN-NAME-MAPPING, AUDITOR-VERIFICATION, instructions)

| Field | Design line | Source endpoint/span | Plan file:line | Verifier file:line |
|---|---|---|---|---|
| `foundry_model` setting in CONFIG-DELTAS | L257 + design Section "Phase 23.0 deliverables" item 6 | hand-authored doc | `23-05-PLAN.md:140-156` | `23-05-PLAN.md:303` |
| `FOUNDRY_MODEL` / `ENABLE_INSTRUMENTATION` / `ENABLE_SENSITIVE_DATA` env vars | design "Deploy sequence" + L344-346 | hand-authored doc | `23-05-PLAN.md:158-184` | `23-05-PLAN.md:304-307` |
| `azure_ai_*_agent_id` orphan cleanup (read at `main.py:514, 596, 687`) | D-02 | hand-authored doc | `23-05-PLAN.md:188-196` | `23-05-PLAN.md:308` |
| Three-step staged deploy sequence (NEGATIVE assertion) | round-1 P1-C | hand-authored doc | `23-05-PLAN.md:198-267` | `23-05-PLAN.md:311-316` |
| `ManagedIdentityCredential` for Container App | design Section "Phase 23.0 planner — Open questions" | hand-authored doc | `23-05-PLAN.md:269-282` | `23-05-PLAN.md:310` |
| RC→GA span Name mapping (`invoke_agent`, `execute_tool`) | design "Observability — Delete" + "Framework-fidelity auditor checklist" | hand-authored doc | `23-05-PLAN.md:373-422` | `23-05-PLAN.md:474-481` |
| `forced_tool_failure` SSE sub-code (D-07b) | L119, design D-07b | hand-authored doc | `23-05-PLAN.md:426` | `23-05-PLAN.md:478` |
| Auditor existence + calibration ❌ count | design "Framework-fidelity audit workflow" | `test -f` + grep | `23-05-PLAN.md:524-541` | `23-05-PLAN.md:627-628` |
| EvalAgentInvoker facade (RC + GA) | design "Eval — Eval invocation facade" | hand-authored doc | `23-04-PLAN.md:451-477` | `23-04-PLAN.md:511-512` |
| Per-agent instructions export (D-02) | design D-02 | manual portal export | `23-04-PLAN.md:561-576` (clf), `:577-579` (admin), `:583-605` (inv) | `23-04-PLAN.md:680-698` |
| PORTAL-DRIFT.md investigation reconciliation | design "Phase 23.0 deliverables" item 3 | diff against canonicalized doc | `23-04-PLAN.md:608-651` | `23-04-PLAN.md:690-693` |

## Endpoint-Field Completeness

For each endpoint the plans invoke, this table shows (a) fields the response actually returns, (b) fields the plan reads, (c) discrepancies.

### `POST /api/eval/run`

- **Source:** `backend/src/second_brain/api/eval.py:28-115`
- **Response:** `{"runId": <str>, "status": "running", "evalType": <str>}` (line 115)
- **Plan reads:** `runId` + `evalType` (`23-04-PLAN.md:160-161, 192-193`)
- **Fields response has but plan ignores:** `status` — read at line 115 implicitly via the polling loop's "completed" check, not via the POST response. Acceptable.
- **Fields plan reads that response doesn't have:** none

### `GET /api/eval/status/{run_id}`

- **Source:** `backend/src/second_brain/api/eval.py:118-124` + `runner.py:205-211, 357-363`
- **Response (final state):** `{"runId", "status", "result_id", "accuracy"|"routing_accuracy", "total", "correct"}` — runner overwrites runs_dict at completion; `evalType` is NOT preserved (round-13 P1-A documented this)
- **Plan reads:** `runId`, `status`, `result_id`, `accuracy` (classifier) / `routing_accuracy` (admin), `total`, `correct` — all present
- **Fields response has but plan ignores:** none significant
- **Fields plan reads that response doesn't have:** none — plan correctly does NOT assert on `evalType` from the status endpoint anymore (round-13 P1-A fix applied; merge happens in step 5 from POST-time shell var)

### `GET /api/eval/results?eval_type=...&limit=...`

- **Source:** `backend/src/second_brain/api/eval.py:127-179`
- **Response per row:** `{"id", "evalType", "runTimestamp", "datasetSize", "aggregateScores", "modelDeployment"}` (line 161-167)
- **Plan reads:** `aggregateScores` via row whose `id` or `resultId` matches `result_id` from status response (`23-04-PLAN.md:257`)
- **Discrepancy ❌:** the plan's defensive `select(.id == $rid or .resultId == $rid)` accepts `.id` (Cosmos default — actually returned per `eval.py:162`) OR `.resultId` (which is NOT returned). The `or .resultId == $rid` branch is dead code. Not a bug — extra defensiveness — but worth noting that `.id` is the canonical match key.
- **Fields response has but plan ignores:** `evalType`, `runTimestamp`, `datasetSize`, `modelDeployment` — `evalType` is needed but plan sources it from the POST response instead (correct, since POST is authoritative).
- **Fields plan reads that response doesn't have:**
  - **W-01 (above):** `aggregateScores.perBucket` / `per_bucket` / `perClass` / `per_class` / `byBucket` / `by_bucket` are all dead-on-arrival key checks for classifier metrics. The actual response will have `aggregateScores = {accuracy, total, correct, precision: <per-bucket dict>, recall: <per-bucket dict>, calibration: [...]}`. The verifier will fail.

### `POST /api/capture` and `POST /api/capture/follow-up`

- **Source:** `backend/src/second_brain/api/capture.py:217, 271, 366` (text + voice + follow-up)
- **Headers:** reads `X-Trace-Id` (text + follow-up); voice currently `file: UploadFile = File(...)` multipart
- **SSE events emitted (per `streaming/sse.py:33-110`):** `inboxItemId`, `bucket`, `confidence`, `threadId`, `runId` — NO `trace_id` field
- **Plan reads:**
  - SSE: full event stream captured to JSONL (no field-by-field assertions in fixture)
  - Spans: filters on `Properties["capture.trace_id"]` matching the client-generated UUID (round-8 P1-A)
- **Discrepancy:** none — the round-8 fix correctly stopped trying to extract `trace_id` from SSE (which has no such field) and instead generates client-side UUID + sends as `X-Trace-Id` header.

### `POST /api/investigate`

- **Source:** `backend/src/second_brain/api/investigate.py:30-50`
- **Body:** `{question: str, thread_id: str | None}` (round-9 P1-A: NOT `{message: ...}`)
- **Headers:** does NOT read `X-Trace-Id` (round-8 P1-B). Spans are correlated via `Properties["investigate.thread_id_out"]` set on the custom AppDependencies span at `streaming/investigation_adapter.py:187`, NOT via `capture.trace_id`.
- **SSE events:** `thinking`, `text`, `done` — `done` carries `thread_id` (line 188 of investigation_adapter)
- **Plan reads:** `thread_id` from SSE done event → recorded as `input.json.thread_id_out` → KQL two-stage join finds custom `investigate` AppDependencies row by `Properties["investigate.thread_id_out"]`, then OperationId-joins all spans
- **Discrepancy:** none — round-10 P1 correctly identified that `investigate.thread_id_out` lives on the custom AppDependencies span, not the AppRequests row, and the verifier asserts exactly-one-of-each at the matching OperationId.

### `GET /api/errands`

- **Source:** `backend/src/second_brain/api/errands.py` (referenced) — admin processing trigger per Phase 12.1
- **Plan invokes:** `curl -s -H "X-API-Key: $API_KEY" "https://brain.willmacdonald.com/api/errands" > /dev/null` (`23-03-PLAN.md:624`)
- **Discrepancy:** none — plan does NOT read response body; it relies on the side-effect (admin handoff fires in-process, which emits the `admin_agent_process` AppDependencies span the verifier asserts)

### `~/.claude/agents/gsd-framework-fidelity-auditor.md`

- **Source:** the auditor markdown file (existence verified by `test -f`)
- **Plan reads:** existence + checklist content via grep (`23-05-PLAN.md:590`)
- **Discrepancy:** none

## Recommendations

Ordered by severity:

1. **W-01 (REQUIRED before plan execution):** in `23-04-PLAN.md` Task 1 verify block, replace the classifier per-bucket key check at line 339 with one that accepts `precision` and `recall` (the actual `compute_classifier_metrics` output keys). Add an inner-shape assertion that proves per-bucket entries exist. Touch points:
   - `23-04-PLAN.md:339` — extend the `or has(...)` chain to include `has("precision") or has("recall")` AND assert inner shape `(.precision | type == "object" and length > 0)` AND `(.recall | type == "object" and length > 0)`.
   - `23-04-PLAN.md:362` — update the corresponding acceptance-criteria bullet so the documented allow-list mirrors the verify regex.
   - `23-04-PLAN.md:259-263, 314` — update the discovery-on-failure hint message to reference `precision` + `recall` as the canonical keys (so an operator who hits the failure path runs the right diagnostic).
   - **No source-code changes required.** This is a planner-side mismatch with reality; the runner already produces the design-required data under `precision` and `recall`.

2. **P-01 (informational, no blocking action):** add a note to `EVAL-INVENTORY.md` (Phase 24 task group 23.2 planner read) that admin per-destination is single-metric (accuracy), not separate precision/recall. Phase 24's GA implementation should match that shape; if the design's "per-destination precision/recall" wording was strict, that's a runner-level enhancement to track separately, not a plan-level change.

3. **P-02 (informational):** the `admin.tool_invoked` value-type defensiveness is currently correct. No edit required, but add a comment in the verifier explaining the dual-form match is intentional defense against AppInsights serialization variance.

## Calibration Check

The auditor spec's `<calibration_notes>` says a freshly-planned Phase 23 — *before* round-13 + round-14 fixes — should produce:

- ❌ WRONG-SOURCE for eval `aggregateScores` (extracting from `/api/eval/status` which doesn't return it; actual source `/api/eval/results`)
- ❌ MISSING for per-bucket classifier + per-destination admin metrics (design L568)
- Endpoint mismatch for `evalType` asserted on status response

**Calibration outcome:**

- Round-13 P1-A (POST→merge `evalType` shell vars; remove `evalType` assertion against status endpoint): ✓ COVERED. Endpoint-completeness section "GET /api/eval/status" confirms.
- Round-14 P1 (fetch `aggregateScores` from `/api/eval/results` and merge into baseline): ✓ COVERED for admin (`per_destination` matches verifier allow-list); ❌ WRONG-SOURCE for classifier (verifier allow-list omits `precision`/`recall`, the actual key names).
- The pre-round-14 ❌ MISSING for per-bucket / per-destination metrics is now ❌ WRONG-SOURCE for classifier and ✓ COVERED for admin.

**This audit's blind-spot check:** the heuristic mapping prose "per-bucket precision/recall" → candidate field names (`perBucket`/`per_bucket`/`perClass`/`byBucket`) was the calibration's flagged fragile point. This audit grounded against `compute_classifier_metrics()` source AND the `EvalResultsDocument.aggregateScores` docstring example, which surfaced that the actual key names (`precision`/`recall`) were not in the round-14 allow-list. The bug 14 review rounds missed: round-14 added the requirement and a defensive `or has(...)` chain, but didn't ground that chain against `eval/metrics.py:14-67` to confirm the runner's actual output keys. Specifically, the round-14 P1 entry at `PLAN-CHECK.md:347` lists "perBucket / per_bucket / perClass / per_class / byBucket / by_bucket" as candidate names without citing where those names come from — they are guesses based on common naming conventions, not lifted from the codebase. The runner's `precision`/`recall` keys (literally `{"precision": <bucket dict>, "recall": <bucket dict>}` per the docstring at `models/documents.py:208-210`) are exactly the design-required per-bucket precision/recall data — just under names the verifier didn't anticipate.

## What 14 Review Rounds Missed

Beyond the W-01 finding above, two issues are worth flagging for visibility (neither blocks plan execution):

1. **`/api/eval/results` field-name dual-match (`.id or .resultId`):** the response only ever returns `.id` (line 162 of `eval.py`). The `.resultId` branch in the plan's `select(.id == $rid or .resultId == $rid)` is dead code. Round-14 P1 introduced this defensive double-match without grounding which key the endpoint actually returns — `.id` is the only one. Not a bug, but extra surface area for confusion. (Listed under "Endpoint-Field Completeness — `/api/eval/results`" above; not material to verdict.)

2. **Admin per-destination "precision/recall" vs flat-accuracy:** design L568 says "per-destination precision/recall" but `compute_admin_metrics` produces a single accuracy number per destination (line 167 of `metrics.py`). 14 rounds focused on field-name verifier correctness without flagging that the runner's per-destination metric is one number, not two. Phase 24's ±5pp class-specific drop check operates on whatever the runner produces, so internal consistency holds — but the design's strict reading isn't fulfilled. Worth surfacing in EVAL-INVENTORY.md so Phase 24 task group 23.2's GA implementation doesn't accidentally introduce a stricter contract. (Listed under P-01 above.)

The probe fixtures (5 of 5) all show ✓ COVERED with strong source-grounded evidence: every probe captures introspected `dir()` data + named verbatim-strings AST-walked (Invariants 1+2 in 23-02 verify) + KQL coverage assertion in the Task 4 checkpoint. No field gaps detected.

---

DESIGN COVERAGE: 26 ✓, 2 ⚠️, 1 ❌. Report at `.planning/phases/23-foundry-ga-prep/DESIGN-COVERAGE.md`.
