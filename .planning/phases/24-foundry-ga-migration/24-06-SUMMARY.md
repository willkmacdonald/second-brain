---
phase: 24-foundry-ga-migration
plan: 06
subsystem: observability
tags: [kql, app-insights, span-name, gen-ai-semconv, framework-fidelity, w-01]

# Dependency graph
requires:
  - phase: 23-foundry-ga-prep
    provides: SPAN-NAME-MAPPING.md (RC `*_agent_run` → GA `invoke_agent` table)
  - phase: 24-foundry-ga-migration
    provides: 24-03 CaptureTraceAgentMiddleware (framework-emitted spans now tag at source)
provides:
  - AGENT_RUNS KQL template using GA-native span Name `invoke_agent`
  - Documented degradation path for RC-only Properties.agent_id/run_id/foundry_thread_id (project as empty post-deploy)
  - W-01 narrowed-responsibility docstring on CaptureTraceSpanProcessor (layered D-07a strategy)
affects: [24-07-streaming, 24-08-admin, 24-09-classifier, 24-22-cleanup, post-deploy projection-rename follow-up]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "KQL templates target GA framework-emitted span Names (invoke_agent, execute_tool) instead of RC custom span Names (*_agent_run, tool_*)"
    - "Span-attribute degradation documented in code via inline comments rather than deleted projections, so the function keeps running post-deploy and returns empty strings for vanished RC attributes"
    - "Layered capture-trace tagging: framework middleware at source (CaptureTraceAgentMiddleware) for framework spans, SpanProcessor catches non-framework spans (Cosmos SDK, AppExceptions, custom). Both write to the same attribute name (capture.trace_id) — idempotent."

key-files:
  created:
    - .planning/phases/24-foundry-ga-migration/24-06-SUMMARY.md
  modified:
    - backend/src/second_brain/observability/kql_templates.py
    - backend/src/second_brain/observability/queries.py
    - backend/src/second_brain/observability/span_processor.py

key-decisions:
  - "Kept fetch_agent_runs projection list AS-IS rather than rewriting projections to GA semantic-convention names (gen_ai.usage.*, agent.name). Passive degradation: RC-only fields return empty strings, query keeps running, no schema break. Projection rewrite deferred to post-deploy follow-up when actual GA spans can be inspected in App Insights."
  - "W-01 documentation-only commit per plan: CaptureTraceSpanProcessor's on_start still tags every span; the narrowed-scope comment records the design intent (framework middleware tags framework spans at source, processor catches non-framework). The overlap on the same attribute name is idempotent, so this is correct without behavior change."

patterns-established:
  - "Pattern A: When a KQL template references a span Name that changes RC → GA, update the template Name filter in the same plan that the consuming application code is migrated to GA. (Done here for AGENT_RUNS in advance of streaming adapter rewrite per plan 24-07, since the template change is independent of the adapter rewrite.)"
  - "Pattern B: When a SpanProcessor's responsibility narrows due to new middleware, document the layered design in the class docstring rather than deleting the processor. Removal would lose correlation for non-framework spans the middleware doesn't see (Cosmos AppDependencies, library AppExceptions)."

requirements-completed: [W-01, F-14, F-15, F-16, F-17, D-07a]

# Metrics
duration: 4min
completed: 2026-05-10
---

# Phase 24-06: Observability layer KQL template migration — RC → GA invoke_agent span Names Summary

**AGENT_RUNS KQL template now filters by GA-native span Name `invoke_agent` (was RC `Name endswith "_agent_run"`); CaptureTraceSpanProcessor's narrowed-scope responsibility under D-07a is documented in its class docstring.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-10T18:38:52Z
- **Completed:** 2026-05-10T18:42:28Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- **AGENT_RUNS template Name filter migrated:** the single KQL line that filters on agent span Names now matches GA framework-emitted `invoke_agent` spans instead of the RC custom `*_agent_run` pattern. Per SPAN-NAME-MAPPING (Phase 23 prereq), this is the ONLY KQL template in the codebase that requires a span-Name update — all 17 other templates filter by HTTP route Names (`/api/capture`), severity levels, component properties (`Properties.component == "admin_agent"`), or correlation attributes (`Properties.capture_trace_id`), none of which change with the migration.
- **fetch_agent_runs RC→GA attribute degradation documented:** a 7-line comment above the projection-filter block in `fetch_agent_runs` records that RC-era `Properties.agent_id` / `Properties.run_id` / `Properties.foundry_thread_id` are no longer set by the GA framework. The projection list itself is unchanged — RC-only fields will project as empty strings post-deploy. Projection rewrite to GA semantic-convention names (`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `agent.name`) deferred to a post-deploy follow-up when actual GA spans can be inspected in App Insights.
- **W-01 layered-design docstring:** `CaptureTraceSpanProcessor` gains a class-docstring section recording its narrowed responsibility under D-07a — framework middleware (`CaptureTraceAgentMiddleware` / `CaptureTraceFunctionMiddleware` from plan 24-03) tags `invoke_agent` / `execute_tool` spans at source, while the processor continues to catch everything else (Cosmos AppDependencies, library AppExceptions, custom non-framework spans). No behavior change. The overlap on the same attribute name (`capture.trace_id`) is idempotent.

## Task Commits

Each task was committed atomically:

1. **Task 1: Update AGENT_RUNS KQL template span Name filter** — `43002ed` (feat)
2. **Task 2: Document fetch_agent_runs RC→GA attribute degradation** — `e184736` (docs)
3. **Task 3: Add W-01 narrowed-scope comment to CaptureTraceSpanProcessor** — `1ee634e` (docs)

**Plan metadata:** TBD (this SUMMARY commit).

## Files Created/Modified

### Modified

- **`backend/src/second_brain/observability/kql_templates.py`** — single-line change in the `AGENT_RUNS` template constant: KQL filter `| where Name endswith "_agent_run"` becomes `| where Name == "invoke_agent"`. All other 17 KQL templates unchanged (verified against SPAN-NAME-MAPPING table).
- **`backend/src/second_brain/observability/queries.py`** — 7-line comment added above the `fetch_agent_runs` `agent_filter` block documenting that RC-era custom Properties (`agent_id`, `run_id`, `foundry_thread_id`) will project as empty strings post-deploy. Projection list and function body otherwise untouched.
- **`backend/src/second_brain/observability/span_processor.py`** — 14-line docstring section added to `CaptureTraceSpanProcessor` recording its narrowed responsibility per W-01 / D-07a. No code logic edits (verified via `git diff`).

### Created

- **`.planning/phases/24-foundry-ga-migration/24-06-SUMMARY.md`** (this file)

## Decisions Made

1. **fetch_agent_runs projection list unchanged in this commit.** The plan explicitly authorized this passive-degradation choice over an aggressive rewrite. Rationale:
   - The function continues to work — RC-only fields project as empty strings, not as errors.
   - Investigation tools that consume the output filter empties downstream, so no UI break.
   - GA semantic-convention attribute names (`gen_ai.usage.input_tokens`, etc.) are documented but not yet observed in actual GA spans — the projection rewrite is best done after seeing real spans in App Insights post-deploy. This avoids a second migration if any GA attribute is named slightly differently than the spec suggests.

2. **W-01 docstring-only (no behavior change).** Per the calibration report W-01, the SpanProcessor must be RETAINED — narrowing it to skip framework-emitted spans is unnecessary because the overlap on the same attribute name is idempotent (both writers set `capture.trace_id` to the same ContextVar value). Documenting the layered design in the class docstring captures the intent for future readers and discharges the W-01 audit finding without code churn.

3. **Did NOT rename the function `fetch_agent_runs` to `fetch_invoke_agent_runs`.** The SPAN-NAME-MAPPING.md verification gate (`! grep -rE '_agent_run|azure_ai_agent\.' backend/src/second_brain/observability/`) still finds the function-name token. That cleanup belongs to a later Phase 24 plan (after streaming adapter / Investigation / Admin GA migration land) when the cumulative end-of-phase scan is run. Renaming now would create a noisy diff in a plan whose scope is KQL-template-only.

## Deviations from Plan

**None — plan executed exactly as written.**

The plan's three tasks were each completed with the exact text the plan specified (single-line KQL template change, 7-line comment block in queries.py matching the plan's quoted template, 14-line docstring section in span_processor.py matching the plan's quoted template). No auto-fixes (Rules 1-3) needed. No architectural decisions raised (Rule 4).

## Issues Encountered

- **Worktree base re-alignment at start.** The worktree was initialized at base `76707a82` instead of the target `dfccd1b170`. Resolved by detaching to `dfccd1b170` and force-resetting the worktree branch. No work-loss since no commits existed yet.
- **`test_observability.py` collection error (pre-existing).** This test file imports `warmup.py`, which still imports `AzureAIAgentClient` from `agent_framework.azure`. That symbol was removed from the GA-only dep set in 24-02. The collection error is pre-existing technical debt — `warmup.py` is one of the 8 expected RC-import offenders queued for migration in plans 24-07 through 24-22. Out of scope per the executor's Scope Boundary rule (only fix issues directly caused by this task's changes). No tests in `test_observability.py` exercise the 3 files modified by this plan.

## TDD Gate Compliance

Plan type is `execute` (not `tdd`) — no plan-level RED/GREEN/REFACTOR gate sequence required.

## Verification

| Acceptance criterion | Status |
| --- | --- |
| `grep -c 'Name endswith "_agent_run"' kql_templates.py` returns 0 | PASS (0) |
| `grep -c 'Name == "invoke_agent"' kql_templates.py` returns ≥1 | PASS (1) |
| `AGENT_RUNS` constant still exists | PASS |
| `test_kql_projections.py::test_agent_runs_template_filters_compose` passes | PASS |
| All 9 `test_kql_projections.py` tests pass | PASS (9/9) |
| `grep -q "Phase 24 task group 23.1" queries.py` | PASS |
| `grep -q "GA framework emits agent.name natively" queries.py` | PASS |
| `fetch_agent_runs` still importable | PASS |
| `grep -q "Phase 24 task group 23.1 narrowed scope" span_processor.py` | PASS |
| `grep -q "W-01" span_processor.py` | PASS |
| `CaptureTraceSpanProcessor` still importable + constructible | PASS |
| `git diff` of span_processor.py shows only docstring additions | PASS |
| `test_legacy_middleware_imports_survive.py` — 3/3 pass | PASS |
| `test_foundry_credential_shape.py` — 1/1 pass | PASS |
| `test_no_rc_imports_after_cleanup.py` offender count = 8 (unchanged) | PASS (8 files: admin, classifier, eval/runner, main, admin_handoff, adapter, investigation_adapter, warmup) |

### Post-deploy verification

Once the deployed app emits its first GA span, run:

```bash
az monitor app-insights query --app second-brain-insights --analytics-query \
  "AppDependencies | where TimeGenerated > ago(1h) | where Name == 'invoke_agent' or Name == 'execute_tool' | take 5" \
  --resource-group shared-services-rg -o json | jq '.tables[0].rows'
```

If rows are returned, the AGENT_RUNS template change is confirmed working end-to-end.

## User Setup Required

None — no external service configuration changes. The KQL template change only affects what gets matched in App Insights queries; the underlying telemetry pipeline is unchanged.

## Follow-ups

1. **Post-deploy projection rewrite (deferred from this plan):** Once GA `invoke_agent` spans land in App Insights, inspect actual span attributes via the verification query above. Update `fetch_agent_runs` projection list to use GA semantic-convention names: `Properties.['gen_ai.usage.input_tokens']`, `Properties.['gen_ai.usage.output_tokens']`, `Properties.['agent.name']`. Drop RC-only fields (`Properties.agent_id`, `Properties.run_id`, `Properties.foundry_thread_id`). Update the investigation-tool callers if any depend on the legacy field names.
2. **End-of-phase verification gate:** When the cumulative SPAN-NAME-MAPPING verification scan runs at end of Phase 24, the function name `fetch_agent_runs` will still match `_agent_run`. Rename to `fetch_invoke_agent_runs` (or similar) in the Phase 24 cleanup plan (24-22 or 24-24).
3. **Azure Monitor alert rule review (per SPAN-NAME-MAPPING):** No alert rules are expected to reference `_agent_run` patterns, but verify pre-push using:
   ```bash
   az monitor scheduled-query list --resource-group shared-services-rg -o json \
     | jq '.[] | {name, criteria: .criteria.allOf[0].query}' | grep -i "_agent_run\|invoke_agent"
   ```

## Next Phase Readiness

- **24-07 Streaming adapter GA rewrite:** Independent of this plan. AGENT_RUNS template change is now in place, so when streaming adapter starts emitting GA framework spans (via `agent.run_stream()` instead of `client.get_response(stream=True)`), the `query_agent_runs` investigation tool will already match them.
- **24-08 Admin GA migration / 24-09 Classifier GA migration:** Same independence — KQL consumer side is ready.
- **No blockers introduced.** AST scan offender count remains 8, matching the executor's expected mid-flight invariant.

## Self-Check

Verified post-write:

- File `backend/src/second_brain/observability/kql_templates.py` exists and contains `Name == "invoke_agent"` (1 match), `Name endswith "_agent_run"` (0 matches).
- File `backend/src/second_brain/observability/queries.py` exists and contains `Phase 24 task group 23.1` (1 match) + `GA framework emits agent.name natively` (1 match).
- File `backend/src/second_brain/observability/span_processor.py` exists and contains `Phase 24 task group 23.1 narrowed scope` (1 match) + `W-01` (1 match).
- All 3 modified files import cleanly via `uv run python -c "..."`.
- Commits `43002ed`, `e184736`, `1ee634e` all present in `git log` (verified at end of Task 3).

## Self-Check: PASSED

---
*Phase: 24-foundry-ga-migration*
*Completed: 2026-05-10*
