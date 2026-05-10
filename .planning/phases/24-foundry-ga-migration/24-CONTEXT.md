# Phase 24: Foundry GA Migration — Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate all 3 production agents (Investigation, Admin, Classifier) from `agent-framework-azure-ai==1.0.0rc2` (RC) onto GA `agent-framework` + `agent-framework-foundry`. Single big-bang production deploy via one `git push origin main` after all pre-deploy gates pass locally. Internal task groups 23.1 (Investigation) → 23.2 (Admin) → 23.3 (Classifier) are sequential commit clusters on local `main` — no feature branches, all commits held back until the final push. A push guard installed at Task 0 prevents accidental push of the broken intermediate state.

In scope: agent rewrites, tool migrations, streaming adapters, capture-trace middleware, instructions in repo, custom span removal where framework provides equivalents, KQL `AGENT_RUNS` template update, EvalAgentInvoker facade (introduced 23.2, deleted 23.3), classifier voice path split, `tool_choice='required'`, `forced_tool_failure` SSE sub-code, per-call session rehydration via `AgentSession.session_id`, config additions, env-var sequencing, deploy + post-deploy UAT.

Out of scope (separate phase if pursued): Foundry-native eval cutover (D-04 → 21.1 follow-up), per-destination precision/recall metric expansion (deferred per EVAL-INVENTORY round-15), additional `Azure AI User` RBAC scope tightening beyond what minimal UAT confirms.

</domain>

<decisions>
## Implementation Decisions

### Voice path topology (D-07b implementation)
- **D-01:** Voice path becomes a direct async call to the Azure OpenAI transcription endpoint — NOT a registered tool. Classifier agent registers ONLY `file_capture`.
- **D-02:** `tool_choice='required'` (string form, probe-verified) is unambiguous because only one tool is registered.
- **D-03:** Python safety net (file-capture-as-MISUNDERSTOOD if model called nothing) is deleted in the same commit cluster.
- **D-04:** New SSE error sub-code `forced_tool_failure` introduced for the case where forced tool choice still fails (model returns malformed call, tool raises). Mobile already handles `ERROR`; the sub-code is for monitoring/dashboards to distinguish from generic errors.
- **Rationale:** On-device SFSpeechRecognizer (shipped Phase 12.5) is the primary voice path; cloud transcription on the backend is a rare fallback only. ~15 lines for the fallback. Architecture matches the deployed reality.

### Tools class binding pattern (sets shape for all 3 agents, 16 tools)
- **D-05:** Keep `InvestigationTools` / `AdminTools` / `ClassifierTools` classes unchanged. Drop `@tool(approval_mode="never_require")` decorator from every tool method. Pass `tools=[instance.method, ...]` to `Agent(tools=...)` at lifespan construction time.
- **D-06:** Cosmos manager DI continues via `__init__`. No globals, no factory closures. Mechanical change per tool: remove decorator line, add `Annotated[..., Field(description=...)]` to params, verify docstrings stand as tool descriptions.
- **D-07:** Existing unit tests survive with mocked deps — no test fixture rework needed.
- **Rationale:** Design's parenthetical "preserves Cosmos manager DI without globals" is the explicit nudge. Smaller diff per tool. Reviewable.

### Admin retry semantics (23.2)
- **D-08:** `tool_choice='required'` (string form) on Admin. Forces the model to call SOME tool. Post-hoc check of `response.messages` for which tool fired.
- **D-09:** If neither `add_errand_items` nor `add_task_items` ran (e.g., model only called `get_routing_context` or hallucinated a tool), retry once with a directive prompt. Bounded — exactly one retry, no loop.
- **D-10:** Provider-dict `tool_choice` (OpenAI-style by-name pinning) is NOT used. Probe 3 confirmed the GA SDK rejects it with `ContentError: tool_choice dict must contain 'mode' key` and the `'mode'` schema is undocumented. Spiking the schema during 23.2 was rejected as time-risky.
- **D-11:** D-07 explicit-justification entry recorded for the bounded retry: framework primitive `tool_choice='required'` does not pin to a subset of tools; bounded retry with directive prompt is a justified bridge, not parallel custom Python re-implementing what the framework provides.

### Wave parallelization + commit ordering
- **D-12:** Plans within each task group are fully sequential. Each plan = one commit. ~5-7 commits per task group, ~15-20 total commits in Phase 24 plus Task 0 (push guard install) and final unguard step.
- **D-13:** Within 23.1 specifically, capture-trace middleware lands FIRST, custom `tracer.start_as_current_span(...)` wrappers in `streaming/investigation_adapter.py` deleted SECOND. Local `main` commits stay individually runnable for debugging/bisect because `capture.trace_id` is always tagged at the source.
- **D-14:** Same middleware-first pattern applies to 23.2 (`processing/admin_handoff.py` custom spans) and 23.3 (`streaming/adapter.py` custom spans for `capture_text` / `capture_voice` / `capture_follow_up`).

### Claude's Discretion
The following decisions are NOT locked in this CONTEXT and are for the planner / executor to set:

- **Push guard mechanism (Task 0):** Design says Option A (`pre-push` hook + sentinel file at `.planning/phases/24/PUSH-GUARD-ACTIVE`) is preferred. Planner picks A by default; falls back to Option B (rename remote) only if hook installation fails on this machine.
- **`forced_tool_failure` SSE emission point:** Adapter level, agent level, or middleware level — planner picks based on where exception context is cleanest. Likely the streaming adapter, where SSE events are already constructed.
- **Routing-context injection for Admin:** Keep `get_routing_context` as a tool the agent calls (current pattern, lowest-risk). Move to `FunctionMiddleware` only if the planner finds a clean reason during 23.2 design.
- **RBAC verification timing:** Verify Container App managed identity has `Azure AI User` BEFORE the env-var update. If missing, assign via `az role assignment create` as part of the 23.3 deploy preparation. Do NOT wait until day-after UAT to discover a missing role.
- **`auth_probe` re-run policy:** Re-run from laptop one final time as part of 23.3's pre-push gate, not just trust the Phase 23 fixture. Cheap, fail-loud.
- **Plan count per task group:** Planner decides. ~5-7 plans per task group is the target; planner can split or merge based on natural commit boundaries.

### Folded Todos
None — `gsd-sdk query todo.match-phase 24` returned 0 matches.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design (master source of truth)
- [docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md](../../../docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md) — Approved design. D-01..D-08 decisions, D-07a layered capture-trace, D-07b voice path split + `tool_choice='required'`, framework-fidelity auditor checklist, validation contract, deploy sequence, rollback, open questions per phase. Note: design uses textual "Phase 23" labels for what GSD calls Phase 24 — they are synonyms (see design §1 reconciliation note).

### Phase 23 prerequisite outputs (consumed by Phase 24)
- [.planning/phases/23-foundry-ga-prep/FOUNDRY-PROBE-FINDINGS.md](../23-foundry-ga-prep/FOUNDRY-PROBE-FINDINGS.md) — All 5 probe results + GA SDK API name corrections (`AgentResponse`, `AgentResponseUpdate`, `AgentSession`, `agent.run(stream=True)`, `options=ChatOptions(tool_choice="required")`, `FoundryChatClient(project_endpoint=..., model=...)`, `session_id` on Inbox doc, etc.). Phase 24 mocks shape against probe fixtures.
- [.planning/phases/23-foundry-ga-prep/CONFIG-DELTAS.md](../23-foundry-ga-prep/CONFIG-DELTAS.md) — Config + env-var changes for Phase 24 (add `foundry_model`, env var sequence Step A → B → C, NEGATIVE assertion: NEVER remove `AZURE_AI_*_AGENT_ID` before GA image deploys, Container App managed identity RBAC verification commands).
- [.planning/phases/23-foundry-ga-prep/SPAN-NAME-MAPPING.md](../23-foundry-ga-prep/SPAN-NAME-MAPPING.md) — RC→GA span Name table. ONLY `AGENT_RUNS` template needs updating (`Name endswith "_agent_run"` → `Name == "invoke_agent"`). Custom spans `capture_text`/`capture_voice`/`capture_follow_up`/`investigate`/`admin_agent_process`/`admin_agent_batch_process` deleted (F-14/F-15/F-16). Pre-push grep guard documented.
- [.planning/phases/23-foundry-ga-prep/EVAL-INVENTORY.md](../23-foundry-ga-prep/EVAL-INVENTORY.md) — Existing eval module surface, RC-shaped call sites at `eval/runner.py:133-149` (classifier) and `:278-294` (admin), `EvalAgentInvoker` interface for 23.2 introduction + 23.3 deletion, and the per-destination precision/recall scope-creep guard.
- [.planning/phases/23-foundry-ga-prep/AUDITOR-VERIFICATION.md](../23-foundry-ga-prep/AUDITOR-VERIFICATION.md) — Confirms `~/.claude/agents/gsd-framework-fidelity-auditor.md` exists (318 lines) and was calibrated against current RC backend (19 ❌ findings F-01..F-19, 1 ⚠️, 3 pass). Phase 24 plans MUST include auditor invocation tasks at end of each task group + cumulative pre-push.
- [.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-calibration.md](FRAMEWORK-FIDELITY-calibration.md) — The 19 calibration findings are the target list Phase 24 must close. Each F-## describes specific RC → GA migration work.

### Probe fixtures (consumed as ground truth for SDK behavior)
- [backend/tests/fixtures/foundry-probe/streaming_shape.json](../../../backend/tests/fixtures/foundry-probe/streaming_shape.json) — 25-update sequence shape for `agent.run(stream=True)` with a 1-tool agent + forced tool call.
- [backend/tests/fixtures/foundry-probe/tool_call_extraction.json](../../../backend/tests/fixtures/foundry-probe/tool_call_extraction.json) — `AgentResponse.messages` walking pattern; `response.text` for final answer; `response.usage_details` for token counts. Source of truth for Admin output-tool detection.
- [backend/tests/fixtures/foundry-probe/tool_choice_required.json](../../../backend/tests/fixtures/foundry-probe/tool_choice_required.json) — Confirms `tool_choice='required'` (string form) works; provider-dict raises `ContentError`. Load-bearing for D-07b.
- [backend/tests/fixtures/foundry-probe/session_rehydration.json](../../../backend/tests/fixtures/foundry-probe/session_rehydration.json) — `AgentSession.session_id` is the rehydration key; replaces `foundryThreadId` on Inbox doc.
- [backend/tests/fixtures/foundry-probe/auth_probe.json](../../../backend/tests/fixtures/foundry-probe/auth_probe.json) — `FoundryChatClient(credential=...)` accepts azure-credential object; `Azure AI User` role sufficient (Owner is overly broad).

### Golden-trace fixtures (consumed by pre-deploy replay tests)
- `backend/tests/fixtures/investigation/` — 5 fixtures for Investigation chat (per agent: `*.input.json`, `*.sse.jsonl`, `*.spans.json`, `*.expected-deltas.md`)
- `backend/tests/fixtures/admin/` — 5 fixtures for Admin captures
- `backend/tests/fixtures/classifier/` — 8 fixtures for Classifier (text + voice + low-confidence + deliberate misunderstood)
- `backend/tests/fixtures/eval-baseline-pre-migration.json` — Pre-migration eval scores; ±2pp post-migration gate compares against this.

### Project / standards
- [.planning/PROJECT.md](../../PROJECT.md) — v3.1 milestone goals; observability and eval as the active focus.
- [.planning/ROADMAP.md](../../ROADMAP.md) §"Phase 24" — phase goal, deliverables, dependency on Phase 23.
- [docs/foundry/investigation-agent-instructions.md](../../../docs/foundry/investigation-agent-instructions.md) — Source content for `agents/instructions/investigation.md` (per D-02).

### Auditor / calibration
- `~/.claude/agents/gsd-framework-fidelity-auditor.md` — Subagent definition. Invoked at end of each task group + cumulative pre-push.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`backend/scripts/foundry_probe.py`** (272 lines) — Probe harness from Phase 23. NOT imported by the running app; safe to delete after Phase 24. Provides `_setup_probe_telemetry()` pattern for capture.trace_id propagation that Phase 24 middleware mirrors.
- **`backend/src/second_brain/observability/span_processor.py`** — `CaptureTraceSpanProcessor` retained per D-07a. Narrowed responsibility (non-framework spans only) is documented in calibration W-01 but no code change required — the processor's behavior is unchanged; its scope shrinks because the framework now handles agent + tool spans natively.
- **`backend/src/second_brain/tools/transcription.py`** — Direct Azure OpenAI Whisper-style call already exists as a helper. Voice path D-04 reuses this — no new transcription code needed, just remove `transcribe_audio` from classifier tool registration and call this helper directly when audio is on the request.
- **Existing tools classes** (`InvestigationTools`, `AdminTools`, `ClassifierTools`) — All keep their `__init__(...)` shape and Cosmos DI. Methods stay methods.
- **Existing unit test fixtures** under `backend/tests/` — Constructed against tools classes with mocked Cosmos. Survive D-05 / D-06 unchanged.

### Established Patterns
- **Per-capture trace ID propagation via `ContextVar`** — Set in `api/capture.py`, read by `CaptureTraceSpanProcessor.on_start()`. Phase 24 capture-trace middleware reads from the same ContextVar (`capture_trace_id_var`) to set `capture.trace_id` on framework agent + tool spans. The ContextVar pattern is preserved end-to-end.
- **Cosmos DI via tools-class `__init__`** — Established Phase 10. Phase 24 keeps it.
- **Lifespan-singleton agents** — One instance per agent type, constructed at app startup (`main.py` lifespan). Phase 24 keeps the singleton; per-call rehydration via `AgentSession(session_id=stored_id)` threads continuity for follow-ups.
- **Sequential commit-cluster phases** — Phase 23.0 already used this pattern (5 plans, sequential). Phase 24 inherits it for 23.1 / 23.2 / 23.3 commit clusters.

### Integration Points
- **`backend/src/second_brain/main.py` lifespan** — 10 RC client construction sites today (per F-01). Phase 24 replaces them with `FoundryChatClient(project_endpoint=..., model=..., credential=ManagedIdentityCredential())` and `Agent(client=..., instructions=load_instructions(...), tools=[instance.method, ...], middleware=[capture_trace_middleware])`.
- **`backend/src/second_brain/observability/queries.py`** — Only `fetch_agent_runs` requires update (KQL `AGENT_RUNS` template Name filter + property projection check). All other functions filter by HTTP route names, severity, or `Properties.component` — unaffected.
- **`backend/src/second_brain/api/capture.py:228`** — Direct `set_attribute("capture.trace_id", ...)` on the active AppRequests span stays. Per D-07a layered strategy, this is the FastAPI request-span tagging that agent middleware does NOT reach.
- **`backend/src/second_brain/eval/runner.py:133-149` and `:278-294`** — RC-shaped call sites that the `EvalAgentInvoker` facade replaces. Facade introduced in 23.2 (when Admin migrates), RC implementation deleted in 23.3 (when Classifier migrates and no caller remains).
- **`backend/src/second_brain/agents/middleware.py`** — RC `AuditAgentMiddleware` + `ToolTimingMiddleware` deleted (F-17). Replaced by GA `AgentMiddleware` + `FunctionMiddleware` in `agents/agent_middleware/capture_trace.py` (NEW path — see resolution_notes P1-3).

### Things NOT to touch (out of scope)
- `api/` route shapes and SSE wire contract (per design §"Out of scope")
- `models/documents.py` Cosmos schemas — except: `Inbox.foundryThreadId` field RENAMED-VIA-ADDITION to `sessionId` per D-07b probe finding + P0-2 amendment. Both fields coexist during the migration window; cleanup in 24-24 post-UAT.
- `cosmos/` manager
- `auth/` middleware  
- `mobile/`, `web/`, `mcp/` — no client-side change
- `infra/` — Container Apps deployment pipeline unchanged; only env vars added/removed
- `eval/foundry.py` Phase 21.1-01 evaluator path — preserved per D-04

</code_context>

<specifics>
## Specific Ideas

- **The on-device transcription reality matters.** Phase 12.5 (2026-03-23) shipped on-device SFSpeechRecognizer on iOS as the primary voice path. Cloud transcription on the backend is the rare fallback only — exercised when SFSpeechRecognizer fails. This is why the voice-path split (D-07b) is much smaller than the design implies on first read: a ~15-line direct-call rewrite of the rare fallback path is enough. Will explicitly noted "the on-device transcription works VERY well — and I believe removes a lot of complexity in the overall design" during discuss-phase.
- **Push guard preference:** Will accepted the design's recommendation of Option A (pre-push hook + sentinel) implicitly by selecting "Ready for context." Planner uses A by default.
- **Sequential plans, not parallel waves.** Will explicitly chose fully sequential to keep diffs reviewable and avoid parallel executor agents writing to overlapping files (`main.py`, `config.py`, `lifespan`). Trades speed for safety.
- **No fallback to RC behavior.** Voice path split, safety-net deletion, `tool_choice='required'`, and `forced_tool_failure` sub-code all land together in 23.3. There is no "defer D-07b" carve-out.

</specifics>

<deferred>
## Deferred Ideas

### From discussion (mechanical decisions left to planner)
- **`forced_tool_failure` SSE sub-code emission point** — adapter / agent / middleware level. Planner picks based on cleanest exception context.
- **Routing-context injection for Admin** — keep `get_routing_context` as a tool (current pattern, recommended) vs move to `FunctionMiddleware`. Planner can elevate to design-time decision in 23.2 if a clean reason emerges.
- **Per-destination precision/recall metric expansion** — Per EVAL-INVENTORY round-15: existing runner emits flat per-destination accuracy. The design's wording at L568 ("per-destination precision/recall") is internally consistent because the ±5pp class-specific drop check operates on whatever the runner emits on both sides of migration. Expanding to true precision/recall is a `eval/metrics.py` change, not a Phase 24 facade change. Tracked as separate follow-up.
- **`'mode'` dict schema for `tool_choice` provider-dict pinning** — Probe 3 showed it's required but undocumented. Could enable framework-pinned admin output-tool selection (collapsing the bounded retry to zero). Not pursued in 24 because of time risk.
- **Deletion of `backend/scripts/foundry_probe.py`** — After Phase 24 ships and is stable for 7 days, the probe harness is no longer needed. Defer cleanup commit until then.

### Out of scope (separate phase)
- Foundry-native eval cutover (Phase 21.1) — D-04 keeps custom eval framework as the migration gate; native cutover is its own follow-up phase.
- Self-monitoring loop (Phase 22) — independent of GA migration.

</deferred>

<resolution_notes>
## Defect Resolution Notes (added 2026-05-10)

Pre-execution review of plans 24-{01..23}-PLAN.md surfaced 8 defects (P0×2, P1×5, P2×1) captured in `.planning/phases/24-foundry-ga-migration/24-PLAN-DEFECTS.md`. All eight have been amended into the affected plans + new plans inserted + red tests landed. Net plan count: 23 → 27 (added 24-06.5, 24-13.5, 24-19.5, 24-24).

The locked decisions D-01..D-14 in this CONTEXT are unchanged. The amendments only refine implementation details that did not survive contact with deeper review.

| Defect | Resolution summary |
|---|---|
| P0-1 (session rehydration unproven) | NEW plan 24-06.5 extends foundry_probe with fresh-process session test; red test `tests/test_session_rehydration_fresh_process.py` gates 24-07/24-16/24-17; live probe runs against deployed RC, captures fixture `session_rehydration_fresh_process.json`; checkpoint blocks if `recalled_pineapple==false` |
| P0-2 (backfill deletes RC field pre-deploy) | Three-phase migration: (1) backfill ADDITIVE only — copies foundryThreadId→sessionId, keeps both (24-15 helper, 24-17 model addition, 24-17 backfill script); (2) GA code dual-reads via `cosmos/inbox_session_resolver.resolve_inbox_session_id()` (24-15 helper, 24-16 wires it, 24-20 Gate 9 verifies additive); (3) post-UAT cleanup deletes foundryThreadId in NEW plan 24-24 |
| P1-3 (middleware package shadows legacy module) | Package renamed to `agents/agent_middleware/` per operator decision (24-03); all callers use new path (24-04, 24-09, 24-14); legacy module unshadowed; red test `tests/test_legacy_middleware_imports_survive.py`; legacy file deleted in 24-18 with red test updated |
| P1-4 (RC dep removed before RC imports gone) | Plan 24-02 amended to ADD GA deps without removing RC; both packages installed mid-migration; NEW plan 24-19.5 removes RC dep + regenerates uv.lock after 24-19 cleared the last RC import; red test `tests/test_no_rc_imports_after_cleanup.py` |
| P1-5 (credential class disagreement) | Locked to sync `azure.identity.ManagedIdentityCredential` per CONFIG-DELTAS verbatim (operator decision); 24-04 imports the sync variant, 24-09 / 24-14 verify invariant, 24-20 Gate 4 uses sync credential; red test `tests/test_foundry_credential_shape.py` AST-scans main.py |
| P1-6 (probe replay unstable + /tmp redirect bug) | NEW helper `backend/scripts/foundry_probe_compare.py` with normalize_fixture() volatile-field scrubbing; 24-20 Gate 4 rewritten to use normalize-and-diff + invariant assertions; red tests `tests/test_probe_replay_invariants.py` + `tests/test_probe_replay_normalized_diff.py` |
| P1-7 (admin baseline empty) | Operator-locked decision: option (a) seed admin golden cases (≥10) and re-baseline. NEW plan 24-13.5 ships seed script `backend/scripts/seed_admin_golden_dataset.py` + cases manifest `backend/scripts/admin_golden_seed/cases.yaml` (operator curates real production captures at exec time); red test `tests/test_admin_eval_baseline_seeded.py` asserts admin.total>=10 |
| P2-8 (gates run before final cleanup) | Reorder approach (a): plan 24-21 now ships BEFORE 24-20. depends_on swapped: 24-21 depends_on [19.5], 24-20 depends_on [21]. NEW Gate 10 startup smoke runs as cheap insurance; red test `tests/test_app_startup_smoke.py` |

**Sequencing after amendments:**
```
24-01 → 24-02 → 24-03 → 24-04 → 24-05 → 24-06 → 24-06.5 → 24-07 → 24-08 → 
24-09 → 24-10 → 24-11 → 24-12 → 24-13 → 24-13.5 → 24-14 → 24-15 → 24-16 → 
24-17 → 24-18 → 24-19 → 24-19.5 → 24-21 → 24-20 → 24-22 → 24-23 → 24-24
```

The only ordering change vs. original: 24-21 now ships BEFORE 24-20 (P2-8). Everything else is sequential per CONTEXT D-12 — no parallelization introduced.

All 8 red tests are committed in their respective plans:
- `tests/test_session_rehydration_fresh_process.py` (24-06.5)
- `tests/test_inbox_dual_read.py` (24-15)
- `tests/test_legacy_middleware_imports_survive.py` (24-03; updated in 24-18)
- `tests/test_no_rc_imports_after_cleanup.py` (24-19.5)
- `tests/test_foundry_credential_shape.py` (24-04)
- `tests/test_probe_replay_invariants.py` + `tests/test_probe_replay_normalized_diff.py` (24-20)
- `tests/test_admin_eval_baseline_seeded.py` (24-13.5)
- `tests/test_app_startup_smoke.py` (24-20)

</resolution_notes>

---

*Phase: 24-foundry-ga-migration*
*Context gathered: 2026-05-09*
*Defect amendments applied: 2026-05-10*
</content>
</invoke>
