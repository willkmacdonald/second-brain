---
phase: 21-eval-framework
verified: 2026-04-24T04:04:38Z
status: human_needed
score: 5/5
overrides_applied: 0
human_verification:
  - test: "Verify golden dataset has 50+ entries in Cosmos GoldenDataset container"
    expected: "Container has >= 50 documents with known-correct expectedBucket labels"
    why_human: "Data volume is a runtime property that cannot be verified by static code analysis. Seed script and containers verified to exist, but actual count requires Cosmos query against deployed system."
  - test: "Trigger classifier eval from mobile investigation chat and confirm results display"
    expected: "Agent responds with run ID, eval completes within 5 minutes, results show per-bucket precision/recall table with accuracy percentage"
    why_human: "End-to-end pipeline spans mobile -> Azure Container App -> Foundry agent -> Cosmos. Plan 05 SUMMARY claims e2e verification passed, but independent confirmation requires deployed system interaction."
---

# Phase 21: Eval Framework Verification Report

**Phase Goal:** Classifier and Admin Agent quality are measured with deterministic metrics against golden datasets
**Verified:** 2026-04-24T04:04:38Z
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A golden dataset of 50+ curated test captures with known-correct labels exists and can be run against the Classifier | VERIFIED | GoldenDatasetDocument model has `expectedBucket` field (documents.py:190). Seed script (`scripts/seed_golden_dataset.py`, 236 lines) provides export/import with `_review_status` approval flow. Runner reads from `GoldenDataset` container. E2E verified per Plan 05 SUMMARY (real eval ran on deployed system). Infrastructure complete; data volume is a human-verify item. |
| 2 | Classifier eval produces per-bucket precision/recall, overall accuracy, and confidence calibration metrics | VERIFIED | `compute_classifier_metrics` returns accuracy, total, correct, precision, recall (metrics.py:14-67). `compute_confidence_calibration` returns binned calibration data (metrics.py:70-134). Behavioral spot-check confirmed correct computation (accuracy=0.667 for 2/3 correct). 7 unit tests pass. |
| 3 | Admin Agent eval measures routing accuracy by destination and tool usage correctness | VERIFIED | `compute_admin_metrics` returns routing_accuracy, per_destination breakdown (metrics.py:137-176). `run_admin_eval` uses `DryRunAdminTools` to capture destinations without Cosmos writes (runner.py:177-321). Admin results include `all_destinations` and `task_count` (runner.py:248-256). 7 dry-run tool tests pass. |
| 4 | Eval results are stored with timestamps in Cosmos and logged to App Insights for trend tracking | VERIFIED | Runner writes `EvalResultsDocument` with `runTimestamp` to "EvalResults" container (runner.py:130-139, 276-285). Runner logs to App Insights with eval_type and accuracy (runner.py:142-153, 288-299). GET `/api/eval/results` queries Cosmos ordered by `runTimestamp DESC` (api/eval.py:127-179). |
| 5 | User can trigger an eval run on-demand from mobile or Claude Code and see results | VERIFIED | POST `/api/eval/run` returns 202 with run_id (api/eval.py:28-115). GET `/api/eval/status/{run_id}` returns progress (api/eval.py:118-124). Investigation tools `run_classifier_eval`, `run_admin_eval`, `get_eval_results` wired into InvestigationTools (investigation.py:591-842). Main.py wires eval_router (line 920) and adds 3 tools to investigation_tools list (lines 720-722). Portal instructions document all three tools (investigation-agent-instructions.md:192+). |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/second_brain/eval/__init__.py` | Eval module package init | VERIFIED | Exists, contains docstring comment (1 line) |
| `backend/src/second_brain/eval/metrics.py` | Classifier and admin eval metric computation | VERIFIED | 177 lines, exports `compute_classifier_metrics`, `compute_confidence_calibration`, `compute_admin_metrics` |
| `backend/src/second_brain/eval/dry_run_tools.py` | EvalClassifierTools and DryRunAdminTools classes | VERIFIED | 152 lines, both classes with `@tool` decorators and byte-identical parameter signatures |
| `backend/src/second_brain/eval/runner.py` | Core eval runner with run_classifier_eval and run_admin_eval | VERIFIED | 321 lines, both async functions with sequential iteration, fresh tools per case, metrics computation, Cosmos persistence, App Insights logging |
| `backend/src/second_brain/api/eval.py` | Eval API endpoint with background task + status polling | VERIFIED | 180 lines, POST /api/eval/run (202), GET /api/eval/status/{run_id}, GET /api/eval/results with in-flight guard |
| `backend/src/second_brain/tools/investigation.py` | Three new @tools for eval | VERIFIED | run_classifier_eval (line 595), run_admin_eval (line 664), get_eval_results (line 744) added to class |
| `backend/src/second_brain/main.py` | Eval router + investigation tools wiring | VERIFIED | eval_router imported (line 50), included (line 920), InvestigationTools gets classifier_client/admin_client (lines 697-698), 3 tools in list (lines 720-722) |
| `backend/scripts/seed_golden_dataset.py` | Export/import script for golden dataset seeding | VERIFIED | 236 lines, argparse with export/import subcommands, DefaultAzureCredential, _review_status approval flow |
| `backend/tests/test_eval_metrics.py` | Unit tests for metrics module | VERIFIED | 215 lines, 7 test functions, all pass |
| `backend/tests/test_eval_dry_run.py` | Unit tests for dry-run tools | VERIFIED | 148 lines, 7 test functions (with parametrize = 11 cases), all pass |
| `backend/tests/test_eval.py` | Unit tests for eval runner and API | VERIFIED | 617 lines, 17 test functions, all pass |
| `docs/foundry/investigation-agent-instructions.md` | Updated instructions with eval tool documentation | VERIFIED | Contains "## Evaluation Tools" section (line 192), documents all 3 tools with usage flows and formatting guidance |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| eval/metrics.py | models/documents.py | expectedDestination field distinguishes classifier vs admin cases | WIRED | runner.py filters on `item.get("expectedDestination") is not None` (line 67, 208) |
| eval/dry_run_tools.py | tools/classification.py | file_capture parameter signature match | WIRED | Byte-identical Annotated[str, Field(...)] parameters; verified by successful agent interaction in E2E test |
| eval/dry_run_tools.py | tools/admin.py | add_errand_items parameter signature match | WIRED | Byte-identical parameter signatures confirmed by tests |
| eval/runner.py | eval/metrics.py | imports compute_classifier_metrics, compute_confidence_calibration, compute_admin_metrics | WIRED | Import at line 22-26, used at lines 125-127, 273 |
| eval/runner.py | eval/dry_run_tools.py | instantiates EvalClassifierTools and DryRunAdminTools per eval case | WIRED | Import at line 21, fresh instance at lines 86, 227 |
| eval/runner.py | db/cosmos.py | reads GoldenDataset, writes EvalResults | WIRED | get_container("GoldenDataset") at lines 60, 201; get_container("EvalResults") at lines 138, 284 |
| api/eval.py | eval/runner.py | asyncio.create_task(run_classifier_eval/run_admin_eval) | WIRED | Import at line 11, create_task at lines 80-86, 93-101 |
| tools/investigation.py | api/eval.py | imports _eval_runs for shared in-flight state | WIRED | Import at line 28, used in 8 locations for in-flight guard and status tracking |
| tools/investigation.py | eval/runner.py | calls _run_classifier_eval, _run_admin_eval directly | WIRED | Imports at lines 30-31, create_task at lines 633, 712 |
| main.py | api/eval.py | app.include_router(eval_router) | WIRED | Import at line 50, include at line 920 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| eval/runner.py | test_cases | Cosmos GoldenDataset query | Yes -- parameterized KQL query with userId filter | FLOWING |
| eval/runner.py | individual_results | Agent get_response + dry-run tool capture | Yes -- dry-run tools capture actual agent predictions | FLOWING |
| eval/runner.py | metrics | compute_classifier_metrics(individual_results) | Yes -- pure computation from real results | FLOWING |
| api/eval.py (GET /results) | results | Cosmos EvalResults query | Yes -- parameterized query returning stored eval docs | FLOWING |
| tools/investigation.py (get_eval_results) | results | Cosmos EvalResults query + _eval_runs | Yes -- combines stored results with live status | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Metrics module importable with all exports | `python3 -c "from second_brain.eval.metrics import ..."` | All 3 functions imported successfully | PASS |
| Dry-run tools importable | `python3 -c "from second_brain.eval.dry_run_tools import ..."` | Both classes imported | PASS |
| Runner functions importable | `python3 -c "from second_brain.eval.runner import ..."` | Both functions imported | PASS |
| Eval router has correct routes | `python3 -c "from second_brain.api.eval import router; print([r.path for r in router.routes])"` | `['/api/eval/run', '/api/eval/status/{run_id}', '/api/eval/results']` | PASS |
| compute_classifier_metrics produces correct output | `python3 -c "... accuracy == 2/3 ..."` | accuracy=0.667, per-bucket precision/recall correct | PASS |
| Seed script valid Python | `python3 -c "import ast; ast.parse(...)"` | Syntax OK | PASS |
| All eval tests pass | `pytest tests/test_eval*.py tests/test_eval.py -x` | 35 passed in 0.12s | PASS |
| Full test suite passes (no regression) | `pytest tests/ -x` | 491 passed, 3 skipped, 1 warning in 13.98s | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-----------|-------------|--------|----------|
| EVAL-01 | 21-02, 21-03 | Golden dataset of 50+ test captures with known-correct bucket labels evaluates Classifier accuracy | SATISFIED | GoldenDatasetDocument model, seed script, runner reads and evaluates against golden dataset |
| EVAL-02 | 21-01, 21-03 | Classifier eval reports per-bucket precision/recall, overall accuracy, and confidence calibration | SATISFIED | compute_classifier_metrics + compute_confidence_calibration produce all specified metrics |
| EVAL-03 | 21-02, 21-03 | Admin Agent eval measures routing accuracy by destination and tool usage correctness | SATISFIED | DryRunAdminTools captures destinations, compute_admin_metrics computes per-destination routing accuracy |
| EVAL-04 | 21-01, 21-03, 21-04 | Eval results stored with timestamps for trend tracking (Cosmos + App Insights) | SATISFIED | EvalResultsDocument written to Cosmos with runTimestamp, logger.info with eval metrics to App Insights |
| EVAL-05 | 21-04, 21-05 | User can trigger eval run on-demand from mobile or Claude Code | SATISFIED | POST /api/eval/run, investigation tools (run_classifier_eval, run_admin_eval, get_eval_results), portal instructions updated |

No orphaned requirements found. All 5 EVAL requirements are mapped to plans and have implementation evidence.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| eval/metrics.py | 87 | `return []` | Info | Correct edge case handling for empty calibration input -- not a stub |

No blockers, no warnings. Code is clean with no TODOs, FIXMEs, placeholders, or stub implementations.

### Human Verification Required

### 1. Golden Dataset Volume

**Test:** Query Cosmos GoldenDataset container for document count: `SELECT VALUE COUNT(1) FROM c WHERE c.userId = "will"`
**Expected:** Count >= 50 documents with known-correct `expectedBucket` labels
**Why human:** Data volume is a runtime property in the deployed Cosmos instance. Code analysis confirms the infrastructure (model, seed script, containers) is complete, and Plan 05 SUMMARY confirms an eval ran successfully, but the exact count requires a deployed system query.

### 2. End-to-End Eval Pipeline on Deployed System

**Test:** Open mobile investigation chat, say "run classifier eval", wait 3-5 minutes, say "show eval results"
**Expected:** Agent displays per-bucket precision/recall table, overall accuracy percentage, and any failures with input snippet and expected vs actual
**Why human:** Full pipeline spans mobile app -> Azure Container App -> Foundry agent -> Cosmos. Plan 05 SUMMARY reports successful E2E verification (Ideas ~20%, Admin ~70% accuracy measured), but independent confirmation on current deployment is prudent after any code changes.

### Gaps Summary

No gaps found. All 5 roadmap success criteria verified through code analysis, import chain verification, behavioral spot-checks, and 35 passing tests (491 total suite). The eval framework is architecturally complete: metrics computation, dry-run tool capture, eval runner orchestration, API endpoints, investigation agent tools, and portal instructions are all implemented, wired, and tested.

The two human verification items are deployment-time concerns (data volume and end-to-end pipeline behavior on live infrastructure) rather than code gaps.

---

_Verified: 2026-04-24T04:04:38Z_
_Verifier: Claude (gsd-verifier)_
