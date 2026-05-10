---
status: open
phase: 24-foundry-ga-migration
source: pre-execution plan review
created: 2026-05-10
findings_count: 8
severity:
  P0: 2
  P1: 5
  P2: 1
---

# Phase 24 Plan Defects

Pre-execution review of `.planning/phases/24-foundry-ga-migration/24-{01..23}-PLAN.md`
surfaced 8 defects. None of the 23 plans have been executed. All findings must be
remediated as plan amendments + red tests (per `feedback_plan_defects_fix_with_red_tests.md`)
before execute-phase resumes.

## Resolution policy

For each finding, the gap-closure planner must:

1. Amend the affected plan(s) so the defect cannot recur.
2. Add a **red test** that fails today and turns green only when the amended plan ships.
   - Doc-only fixes are explicitly disallowed (see locked feedback).
3. Surface any cross-cutting plan reordering as new plan boundaries (e.g. `24-19.5`).

The eight findings, in order of severity:

---

## P0-1 — Session rehydration is not actually proven

**Affected plans:** 24-07, 24-16, 24-17, plus a NEW probe-extension plan.

**Defect:**
Phase 24 persists only `AgentSession.session_id` and reconstructs continuity with
`AgentSession(session_id=stored_id)` in:
- `.planning/phases/24-foundry-ga-migration/24-07-PLAN.md:55`
- `.planning/phases/24-foundry-ga-migration/24-16-PLAN.md:46`
- `.planning/phases/24-foundry-ga-migration/24-17-PLAN.md:39`

But `.planning/phases/23-foundry-ga-prep/FOUNDRY-PROBE-FINDINGS.md:118` shows
session continuity was verified by **reusing the same in-process session object**.
True cross-process rehydration would require server-side session state (Foundry's
internal history) to be retrievable from the persisted `session_id` alone. That
guarantee is unproven.

**Production risk:**
After deploy, the singleton agent constructed at app startup would have `session_id`
persisted on the Inbox doc, but a follow-up capture arriving at a *different*
container instance, or after a restart, may find the session has no recallable
prior turns. Follow-ups would silently lose context — no error, just degraded
classification continuity.

**Required fix:**
- Extend `backend/scripts/foundry_probe.py` with a fresh-process session probe:
  - Process A creates a session, sends turn 1, persists `session_id`, exits.
  - Process B (subprocess, fresh interpreter) loads `session_id`, sends turn 2,
    asserts the agent recalls turn 1 (e.g. via a deterministic recall question).
- Land that probe BEFORE plan 24-17 renames `foundryThreadId` to `sessionId` in
  `models/documents.py`.
- If the probe fails: stop. We need a different rehydration strategy (maybe persist
  full message history in Cosmos, or serialize `AgentSession` state explicitly).
  Phase 24 cannot proceed as written.

**Red test:**
`backend/tests/test_session_rehydration_fresh_process.py` — spawns a subprocess that
reuses a `session_id` from disk. Asserts turn 2 reflects turn 1 context. Fails
until the new probe lands AND verification confirms cross-process continuity works.

**Plan amendments:**
- New plan inserted between 24-06 and 24-07 (call it 24-06.5 or restructure):
  "Extend foundry_probe with fresh-process session test." Must run against
  deployed RC backend, capture results, commit fixture.
- 24-07 / 24-16 / 24-17: add probe-result reference. If the probe shows session
  state isn't actually recalled cross-process, those plans must persist whatever
  IS recallable (likely full message history in Inbox doc).

---

## P0-2 — The Cosmos backfill is scheduled before deploy and deletes the RC field

**Affected plans:** 24-17, 24-20, 24-22.

**Defect:**
- `24-17-PLAN.md:234` — `backend/scripts/backfill_inbox_session_id.py` copies
  `foundryThreadId` to `sessionId`, then **deletes** `foundryThreadId` from each
  Cosmos document.
- `24-20-PLAN.md:162` — Gate 9 of the pre-deploy gate runs that backfill script.
- `24-22-PLAN.md:39` — Production is still running the RC image at this point.
  Deploy happens later in plan 24-22 (env vars then push).

**Production risk:**
While the backfill is running and after it completes, production is still on RC.
RC code reads `foundryThreadId` from the Inbox doc. The backfill has just deleted
that field. Any in-flight follow-up capture against the RC backend during the
deploy window will fail to rehydrate the thread, dropping classification continuity
silently (or worse, throwing if the access is non-defensive).

**Required fix:** make the migration phased:
1. **Pre-deploy (additive only):** backfill copies `foundryThreadId` → `sessionId`
   on every doc but **leaves `foundryThreadId` intact**.
2. **GA code (24-17 + capture handler):** **dual-read** — prefer `sessionId`,
   fall back to `foundryThreadId` if absent. Both paths return the same string.
3. **Post-UAT cleanup (NEW, after 24-23):** separate cleanup script removes
   `foundryThreadId` from all docs, run only after 24-23 confirms GA UAT passed
   and no rollback is needed.

**Red test:**
`backend/tests/test_inbox_dual_read.py` — fixture Inbox docs in three states:
(a) only `foundryThreadId`, (b) both fields, (c) only `sessionId`.
Capture handler must resolve session from any of the three. Fails until dual-read
lands in 24-17.

**Plan amendments:**
- 24-17 task list: split the backfill into "additive copy" (current Phase 24)
  and "deletion of foundryThreadId" (post-UAT, NEW plan 24-24 or follow-up).
- 24-17: `models/documents.py` keeps both fields during migration window.
- 24-17 + 24-15/24-16: capture handler implements dual-read.
- 24-20 Gate 9: explicitly confirms additive-only.
- New post-UAT cleanup plan (24-24) added at end of phase.

---

## P1-3 — The middleware package plan breaks imports mid-migration

**Affected plans:** 24-03, 24-04, downstream Admin/Classifier plans.

**Defect:**
- `24-03-PLAN.md:130` — Plan 24-03 creates `agents/middleware/` as a package
  (with `__init__.py`) and explicitly says old imports
  `from second_brain.agents.middleware import AuditAgentMiddleware` will error.
- `24-04-PLAN.md:223` — Plan 24-04 says to keep those legacy imports for
  Admin/Classifier until their respective migration plans.

These two are contradictory. Once `agents/middleware/` exists as a package, Python
imports the package, not the legacy `agents/middleware.py` module. Admin/Classifier
imports break the moment 24-03 lands, not when their migration plans land.

**Required fix:** use a non-colliding module/package name during the migration.

Recommended naming (one of):
- `agents/agent_middleware/` — distinct package name, legacy `middleware.py` stays.
- `agents/middleware_ga/` — same idea, more explicit suffix.

After 24-18 deletes the legacy `middleware.py` (along with `AuditAgentMiddleware`
and `ToolTimingMiddleware`), a follow-up rename collapses `agent_middleware/` →
`middleware/`. Optional polish; not load-bearing.

**Red test:**
- `backend/tests/test_legacy_middleware_imports_survive.py` — asserts that during
  the migration window (every commit between 24-03 and 24-18), the legacy imports
  still resolve. Fails today against the as-written 24-03.
- Pre-push grep guard activated only AFTER 24-18:
  `! grep -rE "from second_brain.agents.middleware import (AuditAgentMiddleware|ToolTimingMiddleware)" backend/src/`

**Plan amendments:**
- 24-03: change package name from `agents/middleware/` to `agents/agent_middleware/`.
  Update plan body + `<files_modified>` + `<scope>`.
- 24-04, 24-09, 24-14: import GA middleware from the new package; legacy imports
  unaffected.
- 24-18: in addition to deleting `agents/middleware.py`, optional rename of
  `agents/agent_middleware/` → `agents/middleware/` if desired.

---

## P1-4 — The dependency cutover removes RC before RC imports are gone

**Affected plans:** 24-02, 24-04 through 24-19.

**Defect:**
- `24-02-PLAN.md:63` — Plan 24-02 removes `agent-framework-azure-ai` from
  `pyproject.toml` and regenerates `uv.lock`.
- `24-04-PLAN.md:212` — Plan 24-04 explicitly keeps `AzureAIAgentClient` imports
  in `main.py` (for Admin/Classifier construction) and warmup until plan 24-19
  migrates the warmup loop.

After 24-02, intermediate commits between 24-04 and 24-19 import a package that
isn't in `pyproject.toml`. They build only because the local venv hasn't been
re-synced from the new lock file. Anyone running `uv pip sync` mid-migration sees
ImportError on `agent_framework.azure`.

For Will's solo-dev workflow this is mostly a footgun, but if any CI lane (the
auto-format hook, ruff, type-check, the eval runner) re-syncs, the intermediate
commits break. Plus `git bisect` becomes unusable across the migration window —
which directly contradicts CONTEXT D-13 ("commits stay individually runnable").

**Required fix:** keep RC installed until the last RC import is gone.

- 24-02: ADDS GA deps (`agent-framework`, `agent-framework-foundry`) but does NOT
  remove `agent-framework-azure-ai`. Both packages installed during migration window.
- New plan inserted between 24-19 and 24-20 (call it 24-19.5):
  "Remove agent-framework-azure-ai now that no source imports it."
  - Edit `pyproject.toml` to drop the RC dep.
  - Regenerate `uv.lock` with `uv lock`.
  - Run AST scan over `backend/src/second_brain/` confirming zero RC imports.
  - Single commit.

**Red test:**
`backend/tests/test_no_rc_imports_after_cleanup.py` — AST scan asserts zero matches
for `agent_framework.azure`, `AzureAIAgentClient`, `from agent_framework_azure_ai`
in `backend/src/second_brain/`. Test exists from the start but is excluded from
the `pytest -x` gate until 24-19.5; from 24-19.5 onward it MUST pass.

Plus an additive scan that runs at every gate point: every commit between 24-02
and 24-19.5 has BOTH packages resolvable (`importlib.import_module` succeeds for
each). Fails if the as-written 24-02 lands.

**Plan amendments:**
- 24-02: amend Task 1 to ADD only, not REPLACE.
- New plan 24-19.5 created (or fold cleanup into 24-19's commit).
- 24-20 Gate 4 (probe replay): runs against the migration-window state where both
  packages exist. No change needed if the probe loads only what it imports.

---

## P1-5 — The Foundry credential class conflicts with the probe/config source

**Affected plans:** 24-04 (and CONFIG-DELTAS reference).

**Defect:**
- `.planning/phases/23-foundry-ga-prep/CONFIG-DELTAS.md:26` — wires synchronous
  `azure.identity.ManagedIdentityCredential()`.
- `backend/scripts/foundry_probe.py:51` — probe used synchronous
  `AzureCliCredential` (also sync).
- `24-04-PLAN.md:215` — switches to `azure.identity.aio.ManagedIdentityCredential`
  (async).

Three different credential classes across three "locked" sources. None of the
three has been verified to work with `FoundryChatClient(credential=...)` in
combination with the actual production scenarios (singleton agent, async lifespan,
agent.run(stream=True)).

**Required fix:** pick one. Default to **synchronous `ManagedIdentityCredential`**
because (a) CONFIG-DELTAS is locked, (b) the probe used a sync credential and
proved it works, (c) the lifespan construction call is a one-shot at app startup,
not a per-request hot path, so async credential is overengineering.

If async is genuinely required (e.g., the credential is refreshed on a per-request
basis), extend the probe FIRST and verify before plan 24-04 ships.

**Red test:**
`backend/tests/test_foundry_credential_shape.py` — instantiates `FoundryChatClient`
with the chosen credential class and asserts `client._credential` (or whatever
public accessor exists) matches `azure.identity.ManagedIdentityCredential` (sync).
Probe fixture replay in 24-20 must use the same credential class.

**Plan amendments:**
- 24-04: change credential class to `azure.identity.ManagedIdentityCredential`
  (drop `.aio`). Match CONFIG-DELTAS verbatim.
- All other plans that reference credentials (24-09, 24-14): match.
- 24-20 Gate 4: probe replay uses production credential class.

---

## P1-6 — Probe replay gate is not executable as written

**Affected plans:** 24-20.

**Defect:**
- `24-20-PLAN.md:134` — Gate 4 of the pre-deploy gate redirects probe stdout to
  `/tmp/*.json` and expects exact JSON diffs against committed fixtures.
- `backend/scripts/foundry_probe.py:74` — the probe writes JSON directly to the
  committed fixture path AND prints only status to stderr. There is no stdout
  JSON to redirect.

Even if the redirection bug were fixed, exact JSON diff is unstable:
- `run_id` is a fresh UUID per run.
- `captured_at` is a fresh ISO timestamp per run.
- `response_id` (Foundry's response ID) varies per call.
- Python `repr()` addresses (e.g., `<...object at 0x7f...>`) change.

So even a successful probe replay would diff non-zero against the fixture.

**Required fix:** rewrite Gate 4 with two layers.

1. **Normalize then diff** — strip volatile fields (`run_id`, `captured_at`,
   `response_id`, response timestamps, repr addresses) from both sides. Diff the
   normalized JSON. Either pass-as-clean or surface intentional shape changes.
2. **Invariant assertions** — supplement with shape checks that don't depend on
   exact JSON:
   - `tool_choice='required'` produces ≥1 tool call.
   - `agent.run(stream=True)` produces ≥1 update of expected types
     (text-delta, tool-call, completion).
   - `auth_probe` returns a valid token.
   - `session_rehydration` (post-P0-1 fix) shows recall.

**Red test:**
- `backend/tests/test_probe_replay_invariants.py` — replays each probe against
  the deployed backend, asserts shape invariants. Runs as part of Gate 4.
- `backend/tests/test_probe_replay_normalized_diff.py` — runs probe, normalizes
  output, diffs against committed fixture, asserts no semantic delta.

**Plan amendments:**
- 24-20 Gate 4: amend Task wording. Specify the normalize-and-diff helper script
  + invariant assertions. Drop the `/tmp` redirect language.
- New helper module: `backend/scripts/foundry_probe_compare.py` with
  `normalize_fixture(fixture: dict) -> dict` and CLI entry.

---

## P1-7 — The admin eval gate has no baseline (RESOLVED PER OPERATOR DECISION)

**Decision: option (a) — seed admin golden cases + re-baseline.**

**Affected plans:** 24-20, NEW seeding plan inserted before 24-20, plus
`backend/tests/fixtures/eval-baseline-pre-migration.json`.

**Defect:**
- `24-20-PLAN.md:141` — Gate 6 requires admin + classifier eval within ±2pp
  of pre-migration baseline.
- `backend/tests/fixtures/eval-baseline-pre-migration.json:7` — admin baseline
  has zero cases and is marked `failed`.

So the gate as written cannot produce a meaningful admin signal.

**Operator context:** Phone is showing a slew of admin-agent errors since the
migration began. Admin eval safety net is needed BEFORE migration, not after —
matches the locked feedback that plan defects need encoding as red tests, not
deferred to follow-ups.

**Required fix:** seed admin golden cases and re-baseline.

- New plan inserted between 24-13 (end of 23.2 task group) and 24-14:
  "Seed admin golden dataset (≥10 cases) and re-baseline pre-migration eval."
  - Curate ≥10 representative real admin captures (ideally from Will's actual
    history — phone errors imply real production traffic to draw from).
  - For each case: capture text, expected destination, expected tool call name.
  - Write seeding script: `backend/scripts/seed_admin_golden_dataset.py`.
  - Run against deployed RC backend. Capture eval scores.
  - Update `backend/tests/fixtures/eval-baseline-pre-migration.json` with real
    admin baseline metrics.
- 24-20 Gate 6 keeps current wording — admin ±2pp is now meaningful.

**Red test:**
`backend/tests/test_admin_eval_baseline_seeded.py` — asserts the baseline file
has `admin.total >= 10`, `admin.status == "completed"`, and `admin.routing_accuracy`
is a number. Fails today; passes after the seeding plan ships.

**Plan amendments:**
- New plan inserted between 24-13 and 24-14 (renumber as 24-13.5 or shift later
  plans):
  - Task: curate admin golden cases.
  - Task: write seeding script.
  - Task: run seeding + baseline against RC.
  - Task: commit updated baseline JSON.
- 24-20: no wording change; gate now meaningful.

---

## P2-8 — Full pre-deploy gates run before the last source-code cleanup

**Affected plans:** 24-20, 24-21.

**Defect:**
- `24-20-PLAN.md:169` — Plan 24-20 declares all gates green and unblocks the
  deploy.
- `24-21-PLAN.md:106` — Plan 24-21 then changes `config.py` and `main.py`
  (removes RC env-var settings + reads). Validation in 24-21 is import + grep
  only — no test rerun, no startup smoke.

So the gates passed against a state that's no longer the deploy artifact. If
24-21's edits introduce a runtime error (e.g., a stale reference to a removed
config setting), it slips through.

**Required fix:** one of two equivalent approaches.

**Approach (a) — Reorder.** Move 24-21 BEFORE 24-20. The gates then run against
the actual deploy artifact.

**Approach (b) — Add a final smoke gate.** Keep current ordering but add Gate 10
to 24-20 that re-runs after 24-21:
- pytest fast pass.
- App startup smoke (boot the app, hit `/healthz`, shut down).

**Recommendation:** Approach (a). Fewer moving parts; simpler ordering. Approach
(b) is acceptable if there's a reason to keep 24-20 before 24-21 (none surfaced
in the plan review).

**Red test:**
`backend/tests/test_app_startup_smoke.py` — boot the FastAPI app to lifespan
ready state, hit `/healthz`, assert 200. Run as part of 24-20 gates.

**Plan amendments:**
- Reorder 24-21 → 24-20 (or add Gate 10 to 24-20 with explicit re-run).
- 24-20: add final smoke gate regardless of approach (cheap insurance).

---

## Summary table

| # | Plans amended | New plans | New tests | Severity |
|---|---|---|---|---|
| P0-1 | 24-07, 24-16, 24-17 | 24-06.5 (probe extension) | test_session_rehydration_fresh_process | P0 |
| P0-2 | 24-15, 24-16, 24-17, 24-20, 24-22 | 24-24 (post-UAT cleanup) | test_inbox_dual_read | P0 |
| P1-3 | 24-03, 24-04, 24-09, 24-14, 24-18 | — | test_legacy_middleware_imports_survive | P1 |
| P1-4 | 24-02 | 24-19.5 (RC dep removal) | test_no_rc_imports_after_cleanup | P1 |
| P1-5 | 24-04, 24-09, 24-14, 24-20 | — | test_foundry_credential_shape | P1 |
| P1-6 | 24-20 | — | test_probe_replay_invariants, test_probe_replay_normalized_diff | P1 |
| P1-7 | 24-20 | 24-13.5 (admin golden seeding) | test_admin_eval_baseline_seeded | P1 |
| P2-8 | 24-20, 24-21 | — (reorder) | test_app_startup_smoke | P2 |

**Net plan count change:** +4 new plans, several existing plans amended. Phase 24
final plan count likely 27 (not the original 23).

**Sequencing implication:** the new plans cluster around three points —
- pre-23.1 finalization (P0-1 probe → 24-06.5)
- end of 23.2 (P1-7 admin seeding → 24-13.5)
- end of 23.3 / before deploy gate (P1-4 RC dep removal → 24-19.5)
- post-UAT (P0-2 cleanup → 24-24)

All four insertion points are natural commit boundaries.

---

## Out of scope for this gap closure

These came up in review but are NOT defects in the as-written plans:

- The 18 golden-trace fixtures replay timing in Gate 5 is unspecified but not
  broken; current language "replay all fixtures" is enough for executor.
- `forced_tool_failure` SSE emission point is left to the executor per CONTEXT
  D-04, which is fine — emission point is a mechanical decision.
- Per-destination precision/recall metric expansion stays deferred (EVAL-INVENTORY
  round-15 — separate phase).
