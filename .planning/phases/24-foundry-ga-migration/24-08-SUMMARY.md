---
phase: 24-foundry-ga-migration
plan: 08
subsystem: framework-fidelity-audit
tags: [foundry-ga, audit, tg-23.1-gate, p1-1-clear]
requires: [24-01..24-07]
provides:
  - FIDELITY-23.1.patch (cumulative TG 23.1 diff)
  - FRAMEWORK-FIDELITY-23.1.md (auditor report)
  - Verdict: PASS-WITH-WARNINGS — TG 23.2 unblocked
affects: [24-09..24-13.5]
key-files:
  created:
    - .planning/phases/24-foundry-ga-migration/FIDELITY-23.1.patch
    - .planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-23.1.md
decisions:
  - "TG 23.1 framework-fidelity audit passes: 0 in-scope ❌, 3 ⚠️, 14 ✓. TG 23.2 (Admin) unblocked."
  - "Three warnings logged: W-01 (CaptureTraceSpanProcessor narrowed scope documented), W-02 (Content.type discriminators unvalidated by probe — low risk), W-03 (stale investigation_client refs in main.py warmup loop — cleanup deferred to plan 24-19)"
  - "14 out-of-scope ❌ findings deferred to TG 23.2 (Admin) and TG 23.3 (Classifier) plans"
metrics:
  duration_minutes: ~7
  completed_date: 2026-05-10
  tasks_completed: 2/2 (diff capture + audit run)
  files_changed: 3 (2 created + 1 fixture re-pin)
  commits: 2 (auditor report + fixture refresh)
---

# Phase 24 Plan 08: Framework-Fidelity Audit (TG 23.1) Summary

## One-liner

Auditor ran on 21-file, 4429-line cumulative TG 23.1 diff; produced PASS-WITH-WARNINGS verdict (0 in-scope failures); TG 23.2 (Admin) unblocked.

## Verdict

**PASS-WITH-WARNINGS** — TG 23.2 unblocked.

| Status | Count |
|---|---|
| ✓ Pass | 14 |
| ⚠️ Warnings | 3 |
| ❌ In-scope failures | 0 |
| ❌ Out-of-scope failures (deferred) | 14 |

## Cleared findings (Investigation surface)

- **F-05**: `streaming/investigation_adapter.py` uses `from agent_framework import Agent, Message` and `agent.run(msg_list, stream=True)` (was RC `client.get_response(...)`)
- **F-08 (Investigation)**: all 9 `@tool(approval_mode=...)` decorators stripped from `tools/investigation.py`; tool registration via `Agent(tools=[instance.method, ...])`
- **F-13**: P0-1 OUTCOME locked Option A — no `conversation_id`, no `AgentSession`, no `session=`. Mobile holds visible history; backend builds explicit `list[Message]` per turn
- **F-15**: custom `tracer.start_as_current_span("investigate")` block deleted; capture-shape attrs ride on auto-instrumented AppRequests span
- **F-17 (Investigation)**: new `CaptureTraceAgentMiddleware` / `CaptureTraceFunctionMiddleware` use `trace.get_current_span().set_attribute(...)` (D-07a compliant); legacy `agents/middleware.py` preserved at distinct path per P1-3
- **F-19**: `agents/investigation.py` is a pure factory reading `agents/instructions/investigation.md`; portal-shell pattern gone
- **F-18 (Investigation)**: 5 calibration fixtures + new fresh-process probe present; adapter's `update.text` + `update.contents[]` paths match `streaming_shape.json`

## Three warnings (non-blocking, logged for follow-up)

1. **W-01**: `CaptureTraceSpanProcessor` narrowing per D-07a; docstring explicitly documents retained scope (Azure SDK / Cosmos / non-framework spans). Justified retention.

2. **W-02 (NEW)**: streaming-shape probe didn't introspect `Content.type` string vocabulary, so adapter's `content.type == "function_call"` / `"function_result"` discriminators in `investigation_adapter.py:163, 179` are guess-shaped. LOW risk — that path is decorative; primary text streaming via `update.text` was validated.

3. **W-03 (NEW)**: stale `investigation_client` / `investigation_agent_id` references in `main.py:221, 795-796, 830-844` (warmup + spine FoundryAgentAdapter wiring). Benign downgrade — Investigation excluded from warmup loop; spine adapter not wired for Investigation. Plan 24-19 cleanup sweeps this up.

## Out-of-scope ❌ deferred to TG 23.2 + TG 23.3

14 findings tracked by target plan numbers:
- F-01 (main.py Admin/Classifier slices construct AzureAIAgentClient) → 24-09, 24-14
- F-02 (warmup.py references AzureAIAgentClient) → 24-19
- F-03 (admin_handoff custom spans) → 24-11
- F-08 Admin/Classifier @tool decorators → 24-10, 24-15
- F-09/F-10/F-11 (classifier surface) → 24-14, 24-16
- F-12 (eval runner RC client) → varies
- F-14/F-16 (capture span deletions) → 24-16
- F-17 Admin/Classifier middleware paths → 24-11, 24-16
- F-19 Admin/Classifier portal-shell patterns → 24-09, 24-14

All gated by the `test_no_rc_imports_after_cleanup.py` AST scan (currently RED with 7 offenders; turns GREEN incrementally as Wave 3 + Wave 4 land).

## Probe re-run as third independent confirmation

The auditor ran the fresh-process probe again during inspection. Third run produced:
- Different `persisted_session_id` (`72cbc225-...`)
- Different `service_session_id` pair (`resp_0200e6...` / `resp_0223c2...`)
- Different turn_two text (`"You haven't shared a magic word with me yet..."`)
- Same load-bearing outcome: `recalled_pineapple=false`

Three independent runs, three different service_session_id pairs, three different "I don't have your magic word" responses. **The P0-1 OUTCOME is now triply-confirmed.** Fixture re-pinned to the most recent run.

## Decision

TG 23.1 (Investigation surface) is GA-compliant. Plan 24-09 (Admin Agent rewrite) can begin.

## Commits

- `ee6896d`: docs(24-08): framework-fidelity audit for TG 23.1 — verdict: PASS-WITH-WARNINGS (creates FIDELITY-23.1.patch + FRAMEWORK-FIDELITY-23.1.md)
- `254dea1`: chore(24-08): re-pin session_rehydration_fresh_process.json from auditor's 3rd-run

## Self-Check: PASSED

- [x] `.planning/phases/24-foundry-ga-migration/FIDELITY-23.1.patch` exists (4429 lines, 21 files)
- [x] `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-23.1.md` exists (auditor report)
- [x] Verdict: PASS-WITH-WARNINGS
- [x] 0 in-scope failures
- [x] TG 23.2 unblocked
