# Design-Coverage Audit: 23-foundry-ga-prep (v2)

**Date:** 2026-05-09
**Design source:** [docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md](../../../docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md)
**Plans audited:**
- `.planning/phases/23-foundry-ga-prep/23-01-PLAN.md` (dep spike + probe scaffold)
- `.planning/phases/23-foundry-ga-prep/23-02-PLAN.md` (probe implementations + runs + FINDINGS)
- `.planning/phases/23-foundry-ga-prep/23-03-PLAN.md` (18 golden-trace fixtures)
- `.planning/phases/23-foundry-ga-prep/23-04-PLAN.md` (eval baseline + EVAL-INVENTORY + portal export)
- `.planning/phases/23-foundry-ga-prep/23-05-PLAN.md` (CONFIG-DELTAS + SPAN-NAME-MAPPING + AUDITOR-VERIFICATION)
**Prior audit:** `.planning/phases/23-foundry-ga-prep/DESIGN-COVERAGE.md` (v1, 2026-05-08) -- verdict FAIL (1 WRONG-SOURCE, 2 PARTIAL, 1 endpoint mismatch)
**v2 trigger:** W-01 fix applied to 23-04-PLAN.md in review round 15; v2 audit confirms fix landed and reclassifies findings

## Verdict

**PASS-WITH-WARNINGS**: 0 MISSING, 0 WRONG-SOURCE, 0 endpoint-field mismatches, 1 PARTIAL remaining.

| Counter | Value |
|---|---:|
| COVERED fields | 28 |
| PARTIAL coverage | 1 |
| MISSING | 0 |
| WRONG-SOURCE | 0 |
| Endpoint-field mismatches | 0 |

**Verdict states:**
- **PASS** = 0 MISSING/WRONG-SOURCE AND 0 endpoint mismatches
- **PASS-WITH-WARNINGS** = 0 MISSING/WRONG-SOURCE, at least 1 PARTIAL
- **FAIL** = at least 1 MISSING or WRONG-SOURCE

## Delta from v1 audit (2026-05-08)

### W-01: WRONG-SOURCE -> COVERED (classifier per-bucket metric key names)

**v1 finding:** The verify block at `23-04-PLAN.md` asserted naming-guess keys (`perBucket`/`byBucket`/`per_bucket`/`perClass`/`per_class`/`by_bucket`) that `compute_classifier_metrics` at `eval/metrics.py:14-67` never produces. The actual keys are `precision` and `recall` (top-level per-bucket dicts).

**v2 verification -- fix confirmed landed at three sites:**

1. **Verify block (`23-04-PLAN.md:342-347`):** Now asserts source-grounded key names:
   - Line 342: `jq -e '.classifier.aggregateScores | has("precision") and has("recall")'` -- matches `metrics.py:65-66`
   - Line 343: `jq -e '.classifier.aggregateScores.precision | type == "object" and length > 0'` -- proves per-bucket entries exist
   - Line 344: `jq -e '.classifier.aggregateScores.recall | type == "object" and length > 0'` -- same
   - Lines 345-346: inner-value shape assertions (floats in [0,1])
   - Line 347: `jq -e '.classifier.aggregateScores.calibration | type == "array"'` -- matches `runner.py:175-176`

   The old naming-guess chain (`perBucket`/`byBucket`/etc.) is fully removed from the executable verify block.

2. **Acceptance criteria (`23-04-PLAN.md:373`):** References "Source-grounded per-class key assertions (round-15 W-01 fix)" with explicit citation of `eval/metrics.py:14-67` as the grounding source.

3. **Action step 9 narrative (`23-04-PLAN.md:313-317`):** Explicitly states "round-15 audit: see DESIGN-COVERAGE.md W-01 -- earlier rounds asserted naming-guess keys ... that the runner never produces" and names the correct keys with citations to `eval/metrics.py` and `eval/runner.py`.

**Source-grounding cross-check (verbatim from source):**

| Verifier key | Runtime definition | Citation |
|---|---|---|
| `.precision` | `compute_classifier_metrics` returns `{"precision": precision}` where `precision` is a `dict[str, float]` | `eval/metrics.py:65` |
| `.recall` | `compute_classifier_metrics` returns `{"recall": recall}` where `recall` is a `dict[str, float]` | `eval/metrics.py:66` |
| `.calibration` | `metrics["calibration"] = compute_confidence_calibration(individual_results)` | `eval/runner.py:175-176` |
| `.per_destination` (admin) | `compute_admin_metrics` returns `{"per_destination": per_destination}` where `per_destination` is a `dict[str, float]` | `eval/metrics.py:175` |

No naming mismatch remains. W-01 is COVERED.

### Endpoint-field mismatch: resolved (`.resultId` dead branch removed)

**v1 finding:** Plan's `select(.id == $rid or .resultId == $rid)` at `/api/eval/results` included dead `.resultId` branch -- endpoint only returns `.id` per `eval.py:162`.

**v2 verification:** Lines 259 and 270 of `23-04-PLAN.md` now use `select(.id == $rid)` only. Commentary at lines 252-258 explicitly cites `eval.py:162` as grounding. The dead branch is removed from executable code.

Note: The acceptance criteria prose at line 372 still mentions "id or resultId" in a description sentence. This is a documentation remnant only -- the executable jq at lines 259 and 270 uses `.id` exclusively. Not material to verdict.

### P-02: reclassified PARTIAL -> COVERED (admin.tool_invoked value type)

**v1 finding:** The dual-form match (`"true"` or `true`) was classified PARTIAL because of theoretical future Application Insights serialization variance risk.

**v2 reclassification rationale:** The verifier at `23-03-PLAN.md:755` matches the current runtime behavior precisely. The `_coerce` helper preserves JSON types through the fixture pipeline. No Application Insights serialization change is pending or documented. The dual-form match is defensive correctness, not a gap. Reclassified to COVERED.

### Net counter movement

| Counter | v1 | v2 | Change |
|---|---:|---:|---|
| COVERED | 26 | 28 | +2 (W-01 reclassified + P-02 reclassified) |
| PARTIAL | 2 | 1 | -1 (P-02 promoted) |
| MISSING | 0 | 0 | -- |
| WRONG-SOURCE | 1 | 0 | -1 (W-01 resolved) |
| Endpoint mismatches | 1 | 0 | -1 (resolved) |

## PARTIAL -- covered but with design-vs-runtime semantic gap

### P-01: admin per-destination "precision/recall" vs flat-accuracy

- **Design line:** `design.md:568` -- "per-destination precision/recall"
- **Pass criteria (design line 570):** "no class-specific precision drop > 5pp; no class-specific recall drop > 5pp"
- **Runtime source:** `compute_admin_metrics` at `eval/metrics.py:165-169` writes `per_destination[dest] = sum(1 for c in correctness_list if c) / len(correctness_list)` -- a single accuracy number per destination, NOT separate precision and recall.
- **Plan capture:** The verifier at `23-04-PLAN.md:348-350` requires `.admin.aggregateScores | has("per_destination")` and asserts it is a non-empty object with floats in [0,1]. This will pass at runtime.
- **Issue:** The design says "per-destination precision/recall" (two metrics per class). The runner produces one (accuracy = correct/total per expected destination, which equals recall when grouped by expected class). The Phase 24 +-5pp class-specific drop check operates on the same single-metric shape on both sides of the migration, so internal consistency holds.
- **Mitigation already in place:**
  - `23-04-PLAN.md:315` includes inline note citing "P-01 from DESIGN-COVERAGE.md"
  - `23-04-PLAN.md:449-461` (the "Admin metric shape" subsection in the EVAL-INVENTORY template) dedicates a full section to documenting the flat-accuracy contract and explicitly warning Phase 24 task group 23.2 against silently widening to separate precision/recall
- **Severity:** PARTIAL. No plan edit required. The gap is between design prose and runner implementation, not between plan and runtime. The plan correctly captures what the runtime produces.

## COVERED -- design field captured and asserted

### Eval baseline (design line 568 area, design D-04 + D-06)

| Field | Design line | Source endpoint/span | Plan file:line | Verifier file:line |
|---|---|---|---|---|
| `classifier.accuracy` (overall) | L568 | `/api/eval/results` `aggregateScores.accuracy` (`metrics.py:62`) + `/api/eval/status` (`runner.py:208`) | `23-04-PLAN.md:329` | `23-04-PLAN.md:333` |
| `classifier.total` (>= 50) | L568 | `/api/eval/status` (`runner.py:209`) | `23-04-PLAN.md:331` | `23-04-PLAN.md:334` |
| `classifier.correct` | L568 | `/api/eval/status` (`runner.py:210`) | `23-04-PLAN.md:332` | `23-04-PLAN.md:335` |
| `classifier.aggregateScores.precision` | L568 "per-bucket precision" | `/api/eval/results` `aggregateScores.precision` (`metrics.py:65`) | `23-04-PLAN.md:259` | `23-04-PLAN.md:342-345` |
| `classifier.aggregateScores.recall` | L568 "per-bucket recall" | `/api/eval/results` `aggregateScores.recall` (`metrics.py:66`) | `23-04-PLAN.md:259` | `23-04-PLAN.md:342-346` |
| `classifier.aggregateScores.calibration` | L568 (implicit) | `/api/eval/results` `aggregateScores.calibration` (`runner.py:175-176`) | `23-04-PLAN.md:259` | `23-04-PLAN.md:347` |
| `admin.routing_accuracy` | L568 | `/api/eval/results` `aggregateScores.routing_accuracy` (`metrics.py:172`) + `/api/eval/status` (`runner.py:360`) | `23-04-PLAN.md:335` | `23-04-PLAN.md:338` |
| `admin.total` (> 0) | L568 | `/api/eval/status` (`runner.py:361`) | `23-04-PLAN.md:336` | `23-04-PLAN.md:339` |
| `admin.aggregateScores.per_destination` | L568 "per-destination" | `/api/eval/results` `aggregateScores.per_destination` (`metrics.py:175`) | `23-04-PLAN.md:270` | `23-04-PLAN.md:348-350` |
| `evalType` (classifier + admin) | D-04 | POST `/api/eval/run` response (`eval.py:115`); status endpoint does NOT preserve | `23-04-PLAN.md:227-238` | `23-04-PLAN.md:332, 337` |
| `framework_version` (RC pin) | D-05 | composed at fixture time | `23-04-PLAN.md:288` | `23-04-PLAN.md:329` |
| `model_deployment` | L568 "model name" | composed at fixture time | `23-04-PLAN.md:287` | indirect |
| `admin_routing_context_seed` | D-13 reproducibility | composed at fixture time | `23-04-PLAN.md:289` | `23-04-PLAN.md:330` |

### Foundry probe fixtures (design "Foundry probe harness" section, ~line 280)

| Field | Design line | Source | Plan file:line | Verifier |
|---|---|---|---|---|
| `streaming_shape.update_count` | L307 | `agent.run_stream()` loop | `23-02-PLAN.md:354-371` | `23-02-PLAN.md:882` |
| `streaming_shape.updates[]` | L307 "every update yielded" | `dir(update)` introspection | `23-02-PLAN.md:357-363` | `23-02-PLAN.md:882-887` |
| `streaming_shape.thread_deleted_after_run` | L293 | `_maybe_delete_thread` | `23-02-PLAN.md:365-371` | FINDINGS |
| `tool_call_extraction.response_repr/fields` | L308 | `agent.run()` introspection | `23-02-PLAN.md:392-411` | `23-02-PLAN.md:881` |
| `tool_call_extraction.top_level_tool_calls` | L308 | `getattr(response, 'tool_calls', None)` | `23-02-PLAN.md:409` | FINDINGS |
| `tool_call_extraction.messages_walk[]` | L308 | per-message introspection | `23-02-PLAN.md:414-426` | FINDINGS |
| `tool_choice_required.trials.auto` | L309 | `tool_choice="auto"` trial | `23-02-PLAN.md:457-468` | `23-02-PLAN.md:883` |
| `tool_choice_required.trials.required` | L309 | `tool_choice="required"` trial | `23-02-PLAN.md:471-485` | `23-02-PLAN.md:884` |
| `tool_choice_required.trials.provider_dict` | L309 | `tool_choice={"type":"function",...}` | `23-02-PLAN.md:488-503` | `23-02-PLAN.md:885` |
| `tool_choice_required` verdict | L309, D-07b | FINDINGS Probe 3 | `23-02-PLAN.md:996-998` | `23-02-PLAN.md:1082-1093` |
| `session_rehydration.thread_identifier_shape` | L310 | `dir(thread)` introspection | `23-02-PLAN.md:535-543` | `23-02-PLAN.md:886` |
| `session_rehydration` continuity | L310 | two `run_stream` calls | `23-02-PLAN.md:528-549` | `23-02-PLAN.md:1015-1017` |
| `auth_probe.token_acquisition.acquired` | L311 | `cred.get_token(...)` | `23-02-PLAN.md:580-589` | FINDINGS |
| `auth_probe.rbac.role_assignments_raw` | L311 | `az role assignment list` | `23-02-PLAN.md:593-607` | FINDINGS |
| `auth_probe.invocation.succeeded` | L311 | `agent.run()` | `23-02-PLAN.md:613-633` | FINDINGS |
| `probe.run_id` + `probe.name` span tags | L291-292 | `ProbeTagSpanProcessor.on_start` | `23-02-PLAN.md:229-256` | `23-02-PLAN.md:1130-1146` |

### Golden-trace fixtures (design "Validation contract details", L552-565)

| Field | Design line | Source | Plan coverage |
|---|---|---|---|
| `<name>.input.json` | L556 | composed before curl | per-task in `23-03-PLAN.md` |
| `<name>.sse.jsonl` | L557 | curl SSE streaming | per-task verify (wc -l > 0) |
| `<name>.spans.json` | L558 | KQL `query_workspace` | per-task verify (jq empty + length > 0) |
| `<name>.expected-deltas.md` | L559 | hand-authored | grep "## Same" + "## Allowed-different" |
| Investigation `investigate.thread_id_out` | L92, L518 | `investigation_adapter.py:96, 187` | `23-03-PLAN.md:329-394, 486-491` |
| Admin `admin_agent_process` span | D-04 | `admin_handoff.py:177` | `23-03-PLAN.md:746-750` |
| Admin `admin.tool_invoked` attribute | round-14 | `admin_handoff.py:252` | `23-03-PLAN.md:755-756` |
| Capture `capture.trace_id` correlation | L92 | `api/capture.py:217, 366` | `23-03-PLAN.md:596-611, 861-869, 744, 1054` |
| Voice multipart `file=@<path>` | L241 | `api/capture.py:271` | `23-03-PLAN.md:872-882, 1086` |
| Follow-up body fields | D-07b area | `api/capture.py` FollowUpBody | `23-03-PLAN.md:919-930, 1061` |
| `Properties` as JSON object | round-7 | `_coerce` helper | `23-03-PLAN.md:397-417, 493` |

### Other artifacts

| Field | Design line | Plan coverage | Verifier |
|---|---|---|---|
| `foundry_model` setting | L257 | `23-05-PLAN.md:140-156` | `23-05-PLAN.md:303` |
| `FOUNDRY_MODEL`/`ENABLE_INSTRUMENTATION`/`ENABLE_SENSITIVE_DATA` | deploy sequence | `23-05-PLAN.md:158-184` | `23-05-PLAN.md:304-307` |
| `azure_ai_*_agent_id` orphan cleanup | D-02 | `23-05-PLAN.md:188-196` | `23-05-PLAN.md:308` |
| Three-step staged deploy (NEGATIVE assertion) | round-1 | `23-05-PLAN.md:198-267` | `23-05-PLAN.md:311-316` |
| `ManagedIdentityCredential` | design open questions | `23-05-PLAN.md:269-282` | `23-05-PLAN.md:310` |
| RC-to-GA span mapping (`invoke_agent`, `execute_tool`) | design "Observability" | `23-05-PLAN.md:373-422` | `23-05-PLAN.md:474-481` |
| `forced_tool_failure` SSE sub-code | L119, D-07b | `23-05-PLAN.md:426` | `23-05-PLAN.md:478` |
| Auditor existence + calibration | design audit workflow | `23-05-PLAN.md:524-541` | `23-05-PLAN.md:627-628` |
| EvalAgentInvoker facade | design eval facade | `23-04-PLAN.md:451-477` | `23-04-PLAN.md:511-512` |
| Per-agent instructions export (D-02) | D-02 | `23-04-PLAN.md:561-605` | `23-04-PLAN.md:680-698` |
| PORTAL-DRIFT.md reconciliation | design deliverables | `23-04-PLAN.md:608-651` | `23-04-PLAN.md:690-693` |

## Endpoint-Field Completeness

### `POST /api/eval/run`

- **Source:** `backend/src/second_brain/api/eval.py:28-115`
- **Response:** `{"runId": <str>, "status": "running", "evalType": <str>}` (line 115)
- **Plan reads:** `runId` + `evalType` (`23-04-PLAN.md:160-161, 192-193`)
- **Mismatch:** none

### `GET /api/eval/status/{run_id}`

- **Source:** `backend/src/second_brain/api/eval.py:118-124` + `runner.py:205-211, 357-363`
- **Response (final):** `{"runId", "status", "result_id", "accuracy"|"routing_accuracy", "total", "correct"}` -- runner overwrites runs_dict; `evalType` NOT preserved
- **Plan reads:** all present fields; correctly does NOT assert `evalType` from status (merges from POST-time shell var)
- **Mismatch:** none

### `GET /api/eval/results?eval_type=...&limit=...`

- **Source:** `backend/src/second_brain/api/eval.py:127-179`
- **Response per row:** `{"id", "evalType", "runTimestamp", "datasetSize", "aggregateScores", "modelDeployment"}` (lines 161-167)
- **Plan reads:** `aggregateScores` via row whose `.id` matches `result_id` (`23-04-PLAN.md:259, 270`)
- **v1 dead-branch RESOLVED:** `.resultId` removed from executable jq; comments cite `eval.py:162`
- **Classifier `aggregateScores` keys verified:** verifier checks `precision`, `recall`, `calibration` -- matches `metrics.py:61-66` + `runner.py:175-176`
- **Admin `aggregateScores` keys verified:** verifier checks `per_destination` -- matches `metrics.py:171-175`
- **Mismatch:** none

### `POST /api/capture`, `POST /api/capture/follow-up`, `POST /api/investigate`, `GET /api/errands`

All verified in v1 with no findings. No changes between v1 and v2. No mismatches.

## Calibration Check

| Expected defect (per calibration spec) | v1 status | v2 status |
|---|---|---|
| WRONG-SOURCE: `aggregateScores` from wrong endpoint | COVERED (round-14 fixed to `/api/eval/results`) | COVERED |
| MISSING: per-bucket classifier metrics | WRONG-SOURCE (verifier used naming guesses) | COVERED (verifier grounded against `metrics.py:61-67`) |
| MISSING: per-destination admin metrics | COVERED (`per_destination` matched) | COVERED |
| Endpoint mismatch: `evalType` on status response | COVERED (POST-time merge) | COVERED |

All calibration defect classes resolved. The naming-guess heuristic (the calibration spec's flagged fragile point) was the v1 W-01 root cause and is now replaced by source-grounded key names.

## Recommendations

1. **P-01 (informational, no blocking action):** Admin per-destination is flat accuracy, not separate precision/recall. Already documented in `23-04-PLAN.md:315` and the EVAL-INVENTORY admin metric shape section. Phase 24 planner should not widen the runner's contract. No plan edit needed.

2. **Minor documentation nit (non-blocking):** Acceptance criteria prose at `23-04-PLAN.md:372` still references "id or resultId" in a description sentence, though the executable jq was fixed. This is cosmetic and does not affect plan execution.

---

DESIGN COVERAGE: 28 COVERED, 1 PARTIAL, 0 MISSING, 0 WRONG-SOURCE. Report at `.planning/phases/23-foundry-ga-prep/DESIGN-COVERAGE-v2.md`.
