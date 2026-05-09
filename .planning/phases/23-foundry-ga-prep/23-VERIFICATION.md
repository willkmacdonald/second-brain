---
phase: 23-foundry-ga-prep
verified: 2026-05-09T21:09:11Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Confirm eval baseline admin 'failed' status is acceptable"
    expected: "Admin eval status is 'failed' because 0 admin golden-dataset cases are seeded. The classifier result (accuracy=0.9615) is the real baseline. Verify this is understood and acceptable for Phase 24's +/-2pp gate."
    why_human: "The admin eval failure is a known dataset gap, not a code bug. Operator must acknowledge it so Phase 24 planning knows whether to seed admin cases first."
  - test: "ROADMAP 23-05 checkbox is still unchecked"
    expected: "Mark 23-05-PLAN.md as [x] in ROADMAP.md Phase 23 plans section. All artifacts exist and all 3 commits landed."
    why_human: "Verifier does not modify ROADMAP.md; this is an orchestrator/operator task."
---

# Phase 23: Foundry GA Migration -- Prep Verification Report

**Phase Goal:** All Phase 24 prerequisites in place. Zero deployed change. No backend/src/ files touched.
**Verified:** 2026-05-09T21:09:11Z
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

Phase 23 has no formal `success_criteria` in ROADMAP.md. The phase defines 10 deliverables in a `Deliverables` list plus a boundary constraint. Must-haves are derived from PLAN frontmatter across all 5 plans, deduplicated against the ROADMAP deliverables list.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Candidate dep set resolves cleanly (agent-framework + agent-framework-foundry, no agent-framework-azure-ai) | VERIFIED | CANDIDATE-pyproject.toml contains `"agent-framework"` and `"agent-framework-foundry"`, zero occurrences of `agent-framework-azure-ai`. CANDIDATE-uv.lock (592KB) resolves `agent-framework-foundry`. DEP-RESOLUTION-NOTES.md records `ALL IMPORTS OK` and `OK: GA imports resolve`. |
| 2 | Foundry probe harness scaffolded with 5 real implementations (no stubs) | VERIFIED | `backend/scripts/foundry_probe.py` is 705 lines, valid Python, zero `NotImplementedError` remaining. All 5 probe functions present (streaming_shape, tool_call_extraction, tool_choice_required, session_rehydration, auth_probe). PROBES dispatch dict present. Imports `FoundryChatClient`, `AzureCliCredential`, `agent_framework`. Not imported by `backend/src/`. |
| 3 | All 5 probe fixtures exist, are valid JSON, and embed probe.run_id + probe.name | VERIFIED | 5 JSON files under `backend/tests/fixtures/foundry-probe/`: streaming_shape.json (19KB), tool_call_extraction.json (2.7KB), tool_choice_required.json (1.6KB), session_rehydration.json (3.4KB), auth_probe.json (3KB). Each validated: valid JSON with `probe.name` and `probe.run_id` present. |
| 4 | FOUNDRY-PROBE-FINDINGS.md answers the 4 design-mandated questions per probe and documents thread/session deletion | VERIFIED | 172 lines, 5 probe sections each with 4 numbered questions matching design spec. Section "SDK thread/session deletion" documents that no deletion API exists. References Phase 24 task groups. Critical GA SDK naming correction documented at top. |
| 5 | 18 golden-trace fixtures exist (5 investigation + 5 admin + 8 classifier) each with 4 files | VERIFIED | Investigation: 5 traces (recent_errors, system_health, usage_patterns, trace_lifecycle, audit_correlation). Admin: 5 traces (errand_routing, task_creation, recipe_extraction, destination_management, affinity_rule_edit). Classifier: 8 traces (text_person, text_project, text_idea, text_admin_errand, text_admin_task, voice_person, low_confidence_followup, deliberate_misunderstood). All 18 have input.json + sse.jsonl + spans.json + expected-deltas.md. FIXTURE-CAPTURE-LOG.md exists. |
| 6 | Pre-migration eval baseline JSON captured | VERIFIED | `backend/tests/fixtures/eval-baseline-pre-migration.json` exists (2.2KB). Contains classifier scores (accuracy=0.9615, 25/26 correct, per-bucket precision/recall, calibration bins) and admin result (status=failed, 0 admin golden-dataset cases). Captures timestamp, framework version, model deployment. |
| 7 | Portal instructions exported and investigation drift reconciled | VERIFIED | `CANDIDATE-instructions/classifier.md` (158 lines, 10KB), `admin.md` (87 lines, 4.8KB), `investigation.md` (285 lines, 18KB), `PORTAL-DRIFT.md` (125 lines, 6.5KB). PORTAL-DRIFT references `investigation-agent-instructions.md`. All files substantive. |
| 8 | CONFIG-DELTAS.md + SPAN-NAME-MAPPING.md complete with no unfilled placeholders | VERIFIED | CONFIG-DELTAS.md (181 lines, 12.8KB): FOUNDRY_MODEL, foundry_model, ManagedIdentityCredential, ENABLE_INSTRUMENTATION, azure_ai_classifier_agent_id, 3-step safe deploy sequence (Steps A/B/C), NEGATIVE assertion all present. Zero `<fill in:` placeholders. SPAN-NAME-MAPPING.md (145 lines, 17.8KB): invoke_agent, execute_tool, forced_tool_failure, task groups 23.1/23.2/23.3, zero `<verify>` or `<line range>` placeholders. EVAL-INVENTORY.md (153 lines, 9.3KB): EvalAgentInvoker reference present. |
| 9 | AUDITOR-VERIFICATION.md confirms auditor ready; both auditor file and calibration report exist | VERIFIED | AUDITOR-VERIFICATION.md (92 lines): status=READY, references gsd-framework-fidelity-auditor and FRAMEWORK-FIDELITY-calibration.md. Auditor file at `~/.claude/agents/gsd-framework-fidelity-auditor.md` exists (318 lines, 19360 bytes). Calibration report at `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-calibration.md` exists (37565 bytes), 19 F-## findings documented. |

**Score:** 9/9 truths verified

### Boundary Verification

| Check | Status | Evidence |
|-------|--------|---------|
| `backend/pyproject.toml` unchanged (RC dep present) | VERIFIED | `agent-framework-azure-ai` still present in `backend/pyproject.toml` |
| `backend/src/` untouched | VERIFIED | No probe imports found via `grep -rq` in `backend/src/` |
| `config.py` has no `foundry_model` | VERIFIED | `grep -c "foundry_model" backend/src/second_brain/config.py` returned 0 |
| `config.py` still has `azure_ai_classifier_agent_id` | VERIFIED | `grep -c "azure_ai_classifier_agent_id" backend/src/second_brain/config.py` returned 1 |
| Probe script not imported by app | VERIFIED | Zero references to `scripts.foundry_probe` or `scripts/foundry_probe` under `backend/src/` |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `CANDIDATE-pyproject.toml` | GA dep set, no RC dep | VERIFIED | agent-framework-foundry present, agent-framework-azure-ai absent |
| `CANDIDATE-uv.lock` | Resolved lockfile | VERIFIED | 592KB, contains agent-framework-foundry |
| `DEP-RESOLUTION-NOTES.md` | Spike notes with smoke test results | VERIFIED | Contains ALL IMPORTS OK, OK: GA imports resolve, --no-install-project rationale |
| `backend/scripts/foundry_probe.py` | 5 implemented probes + CLI | VERIFIED | 705 lines, 0 NotImplementedError, 5 probe functions, valid Python syntax |
| `backend/tests/fixtures/foundry-probe/*.json` | 5 probe fixtures | VERIFIED | 5 valid JSON files with probe.name + probe.run_id |
| `FOUNDRY-PROBE-FINDINGS.md` | Per-probe findings with 4 questions | VERIFIED | 172 lines, 5 sections, 4 questions each, thread deletion documented |
| `backend/tests/fixtures/investigation/*.{input,sse,spans,deltas}` | 5 investigation traces | VERIFIED | 5 traces, 4 files each, 20 files total |
| `backend/tests/fixtures/admin/*.{input,sse,spans,deltas}` | 5 admin traces | VERIFIED | 5 traces, 4 files each, 20 files total |
| `backend/tests/fixtures/classifier/*.{input,sse,spans,deltas}` | 8 classifier traces | VERIFIED | 8 traces, 4 files each, 32 files total |
| `FIXTURE-CAPTURE-LOG.md` | Capture log | VERIFIED | Exists |
| `eval-baseline-pre-migration.json` | Pre-migration eval scores | VERIFIED | Classifier accuracy=0.9615, admin status=failed (0 golden cases) |
| `EVAL-INVENTORY.md` | Eval module inventory + EvalAgentInvoker scope | VERIFIED | 153 lines, EvalAgentInvoker present |
| `CANDIDATE-instructions/classifier.md` | Exported classifier instructions | VERIFIED | 158 lines, 10KB, substantive |
| `CANDIDATE-instructions/admin.md` | Exported admin instructions | VERIFIED | 87 lines, 4.8KB, substantive |
| `CANDIDATE-instructions/investigation.md` | Reconciled investigation instructions | VERIFIED | 285 lines, 18KB, substantive |
| `CANDIDATE-instructions/PORTAL-DRIFT.md` | Drift diff record | VERIFIED | 125 lines, references investigation-agent-instructions.md |
| `CONFIG-DELTAS.md` | Config + env var changes for Phase 24 | VERIFIED | 181 lines, all required sections + safe deploy sequence |
| `SPAN-NAME-MAPPING.md` | RC to GA span name table + KQL consumers | VERIFIED | 145 lines, 17.8KB, no unfilled placeholders |
| `AUDITOR-VERIFICATION.md` | Auditor existence + calibration check | VERIFIED | 92 lines, status=READY |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `foundry_probe.py` | `agent_framework` / `agent_framework_foundry` | import statements | VERIFIED | `from agent_framework` and `from agent_framework_foundry` imports present |
| `foundry_probe.py` | `azure.identity.AzureCliCredential` | credential acquisition | VERIFIED | `AzureCliCredential` import and usage in `_build_client()` |
| `CANDIDATE-pyproject.toml` | `CANDIDATE-uv.lock` | uv lock generation | VERIFIED | Both reference agent-framework-foundry; lockfile resolves candidate |
| `FOUNDRY-PROBE-FINDINGS.md` | Phase 24 task groups | probe findings consumption | VERIFIED | References task groups 23.1, 23.2, 23.3 with specific probe-to-group mapping |
| `CONFIG-DELTAS.md` | Phase 24 task group 23.1/23.3 | config.py + env var specs | VERIFIED | foundry_model addition for 23.1, orphan cleanup for 23.3, safe deploy sequence |
| `SPAN-NAME-MAPPING.md` | Phase 24 task groups 23.1/23.2/23.3 | KQL query updates | VERIFIED | Per-query consumer table broken down by task group |
| `AUDITOR-VERIFICATION.md` | `~/.claude/agents/gsd-framework-fidelity-auditor.md` | existence check | VERIFIED | Auditor file exists (318 lines, 19360 bytes) |
| `eval-baseline-pre-migration.json` | Phase 24 eval gates | +/-2pp comparison | VERIFIED | Classifier accuracy baseline captured; admin baseline incomplete (0 cases) |
| `CANDIDATE-instructions/investigation.md` | `docs/foundry/investigation-agent-instructions.md` | reconciliation diff | VERIFIED | PORTAL-DRIFT.md documents the diff; investigation-agent-instructions.md exists |

### Data-Flow Trace (Level 4)

Not applicable. Phase 23 is artifact-only (documentation, fixtures, and a standalone probe script). No dynamic data rendering in production code.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| foundry_probe.py is valid Python | `python3 -c "import ast; ast.parse(...)"` | VALID PYTHON | PASS |
| All 5 probe fixtures are valid JSON with probe metadata | `json.load()` + probe.name/probe.run_id check on each | All 5 valid, all have probe.name + probe.run_id | PASS |
| CANDIDATE-pyproject.toml excludes RC dep | `grep -c "agent-framework-azure-ai"` | 0 occurrences | PASS |
| Boundary: config.py unchanged | `grep -c "foundry_model"` in config.py | 0 (not added) | PASS |
| 18 golden-trace sets all have 4 files | Per-trace file existence check | 18/18 complete (72 files) | PASS |
| No unfilled placeholders in Phase 24 docs | `grep "<fill in:" / "<verify>" / "<line range>"` | 0 matches across CONFIG-DELTAS + SPAN-NAME-MAPPING | PASS |

### Requirements Coverage

PREP-01 through PREP-09 are referenced in ROADMAP.md for Phase 23 and in individual PLAN frontmatter, but are NOT defined in REQUIREMENTS.md. This is an orphaned-requirements gap -- the requirement IDs exist in ROADMAP but have no formal definition in the requirements document.

| Requirement | Source Plan | Description (inferred from plan context) | Status | Evidence |
|-------------|-----------|------------------------------------------|--------|----------|
| PREP-01 | 23-01 | Candidate dep set resolves cleanly | SATISFIED | CANDIDATE-pyproject.toml + CANDIDATE-uv.lock + DEP-RESOLUTION-NOTES.md with successful smoke test |
| PREP-02 | 23-01 | Probe harness scaffolded | SATISFIED | foundry_probe.py with 5 probe functions + CLI dispatcher |
| PREP-03 | 23-02 | Probe functions implemented | SATISFIED | 0 NotImplementedError remaining, 705 lines of real implementation |
| PREP-04 | 23-02 | Probe findings documented | SATISFIED | FOUNDRY-PROBE-FINDINGS.md (172 lines, 4-question pattern per probe) |
| PREP-05 | 23-03 | Golden-trace fixtures captured | SATISFIED | 18 fixtures (5+5+8) with 4 files each, all valid |
| PREP-06 | 23-04 | Eval baseline + instructions exported | SATISFIED | eval-baseline-pre-migration.json + 3 instruction files + PORTAL-DRIFT.md |
| PREP-07 | 23-04 | Eval inventory documented | SATISFIED | EVAL-INVENTORY.md with EvalAgentInvoker scope |
| PREP-08 | 23-05 | Config deltas + span mapping documented | SATISFIED | CONFIG-DELTAS.md + SPAN-NAME-MAPPING.md with no placeholders |
| PREP-09 | 23-05 | Auditor verified | SATISFIED | AUDITOR-VERIFICATION.md, status=READY, both files exist |

**Note:** PREP-01 through PREP-09 should be added to REQUIREMENTS.md with formal definitions and traceability entries for this phase.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/scripts/foundry_probe.py` | (n/a) | Throwaway script: probe harness is designed for one-time use and will be irrelevant after Phase 24 | INFO | Expected per design; script lives outside `backend/src/` |
| `eval-baseline-pre-migration.json` | (admin section) | Admin eval status is "failed" with 0 golden-dataset cases seeded | WARNING | Phase 24's +/-2pp gate for admin eval is not gated by a real baseline; only classifier baseline is usable |
| `ROADMAP.md` | Phase 23 Plans | 23-05-PLAN.md checkbox still unchecked `[ ]` despite all artifacts existing and SUMMARY committed | INFO | Cosmetic ROADMAP update needed |

### Human Verification Required

### 1. Admin Eval Baseline Gap

**Test:** Confirm that the admin eval "failed" status (0 golden-dataset cases) is an acceptable known gap for Phase 24 planning.
**Expected:** Operator acknowledges that Phase 24's +/-2pp eval gate applies only to the classifier baseline (accuracy=0.9615). Admin eval gate requires seeding admin golden-dataset cases as a prerequisite, either in Phase 24 or before.
**Why human:** This is a dataset-seeding decision that affects Phase 24 scope. The verifier cannot determine whether admin eval coverage is required before Phase 24 begins or can be deferred.

### 2. ROADMAP Checkbox Update

**Test:** Mark 23-05-PLAN.md as `[x]` in ROADMAP.md Phase 23 plans section.
**Expected:** All 5 plans marked complete.
**Why human:** Verifier does not modify ROADMAP.md; this is an orchestrator/operator responsibility.

### Gaps Summary

No technical gaps found. All 10 ROADMAP deliverables exist, are substantive, and are properly wired. The boundary constraint (no backend/src/ changes) is verified. All 9 requirement IDs (PREP-01 through PREP-09) from PLAN frontmatter are satisfied by artifacts.

Two items require human attention:

1. The admin eval baseline is empty (0 golden-dataset cases), meaning Phase 24's +/-2pp admin eval gate has no real comparison point. This is not a Phase 23 defect -- Phase 23 correctly captured the current state -- but it needs operator acknowledgment before Phase 24 planning proceeds.

2. ROADMAP.md needs the 23-05 plan checkbox ticked.

One housekeeping note: PREP-01 through PREP-09 are referenced in ROADMAP.md but not formally defined in REQUIREMENTS.md. Adding them would complete the traceability chain.

---

_Verified: 2026-05-09T21:09:11Z_
_Verifier: Claude (gsd-verifier)_
