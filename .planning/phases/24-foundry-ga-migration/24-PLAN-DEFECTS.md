---
status: open
phase: 24-foundry-ga-migration
source: pre-execution plan review
created: 2026-05-10
amended: 2026-05-10
findings_count: 8
severity:
  P0: 2
  P1: 5
  P2: 1
---

# Phase 24 Plan Defects

Pre-execution review of `.planning/phases/24-foundry-ga-migration/24-{01..23}-PLAN.md`
surfaced 8 defects. None of the 23 plans have been executed. All findings have been
remediated as plan amendments + red tests (per `feedback_plan_defects_fix_with_red_tests.md`)
before execute-phase resumes.

## Resolution policy

For each finding, the gap-closure planner has:

1. Amended the affected plan(s) so the defect cannot recur.
2. Added a **red test** that fails today and turns green only when the amended plan ships.
   - Doc-only fixes are explicitly disallowed (see locked feedback).
3. Surfaced any cross-cutting plan reordering as new plan boundaries (e.g. `24-19.5`).

All eight findings are now closed pending operator final review.

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
- Extend `backend/scripts/foundry_probe.py` with a fresh-process session probe.
- Land that probe BEFORE plans that persist `session_id`.
- If the probe fails: stop. Phase 24 cannot proceed as written.

**Red test:**
`backend/tests/test_session_rehydration_fresh_process.py` — spawns a subprocess that
reuses a `session_id` from disk. Asserts turn 2 reflects turn 1 context.

**Resolution: amended in plan 24-06.5-PLAN.md (NEW)** — also referenced in 24-16, 24-17 pre-execution checks. Red test landed at `backend/tests/test_session_rehydration_fresh_process.py`. Plan 24-06.5 is a blocking checkpoint that runs the probe live; if `recalled_pineapple == false`, plans 24-16 / 24-17 must be re-amended before they ship.

---

## P0-2 — The Cosmos backfill is scheduled before deploy and deletes the RC field

**Affected plans:** 24-15, 24-16, 24-17, 24-20, plus NEW post-UAT cleanup plan.

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

**Resolution:**
- **amended in plan 24-15-PLAN.md** — adds dual-read helper `cosmos/inbox_session_resolver.py` + red test `tests/test_inbox_dual_read.py`.
- **amended in plan 24-16-PLAN.md** — wires `resolve_inbox_session_id()` into capture handler; new captures dual-write both fields.
- **amended in plan 24-17-PLAN.md** — InboxDocument ADDS sessionId field alongside foundryThreadId (NOT a rename); backfill script is ADDITIVE only.
- **amended in plan 24-20-PLAN.md** — Gate 9 verifies foundryThreadId still present post-backfill.
- **created new plan 24-24-PLAN.md** — post-UAT cleanup; runs only after 24-23 UAT passes.

---

## P1-3 — The middleware package plan breaks imports mid-migration

**Affected plans:** 24-03, 24-04, 24-09, 24-14, 24-18.

**Defect:**
- `24-03-PLAN.md:130` — Plan 24-03 creates `agents/middleware/` as a package
  (with `__init__.py`) and explicitly says old imports
  `from second_brain.agents.middleware import AuditAgentMiddleware` will error.
- `24-04-PLAN.md:223` — Plan 24-04 says to keep those legacy imports for
  Admin/Classifier until their respective migration plans.

These two are contradictory. Once `agents/middleware/` exists as a package, Python
imports the package, not the legacy `agents/middleware.py` module. Admin/Classifier
imports break the moment 24-03 lands, not when their migration plans land.

**Required fix:** use a non-colliding module/package name during the migration. Use `agents/agent_middleware/` per operator-locked decision.

After 24-18 deletes the legacy `middleware.py`, optional polish: rename
`agent_middleware/` → `middleware/`. Optional polish; not load-bearing.

**Red test:**
- `backend/tests/test_legacy_middleware_imports_survive.py` — asserts that during
  the migration window, the legacy imports still resolve.

**Resolution:**
- **amended in plan 24-03-PLAN.md** — package renamed to `agents/agent_middleware/`; legacy `agents/middleware.py` unshadowed; red test landed.
- **amended in plan 24-04-PLAN.md** — middleware imports use `second_brain.agents.agent_middleware.capture_trace` path.
- **amended in plan 24-09-PLAN.md** — same import path; reused from 24-04.
- **amended in plan 24-14-PLAN.md** — same import path; reused from 24-04.
- **amended in plan 24-18-PLAN.md** — legacy file deleted; red test updated (legacy-importable sub-test retired); optional rename agent_middleware/ → middleware/ deferred.

---

## P1-4 — The dependency cutover removes RC before RC imports are gone

**Affected plans:** 24-02, 24-04 through 24-19, plus NEW dep removal plan.

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

**Required fix:** keep RC installed until the last RC import is gone.

- 24-02: ADDS GA deps (`agent-framework`, `agent-framework-foundry`) but does NOT
  remove `agent-framework-azure-ai`. Both packages installed during migration window.
- New plan inserted between 24-19 and 24-20 (24-19.5):
  "Remove agent-framework-azure-ai now that no source imports it."

**Red test:**
`backend/tests/test_no_rc_imports_after_cleanup.py` — AST scan asserts zero matches
for `agent_framework.azure`, `AzureAIAgentClient`, `from agent_framework_azure_ai`
in `backend/src/second_brain/`.

**Resolution:**
- **amended in plan 24-02-PLAN.md** — additive deps only; both GA + RC trees pinned during migration window; mid-migration `uv sync` works cleanly.
- **created new plan 24-19.5-PLAN.md** — removes RC dep + regenerates uv.lock; AST scan red test committed at `backend/tests/test_no_rc_imports_after_cleanup.py`.

---

## P1-5 — The Foundry credential class conflicts with the probe/config source

**Affected plans:** 24-04, 24-09, 24-14, 24-20.

**Defect:**
- `.planning/phases/23-foundry-ga-prep/CONFIG-DELTAS.md:26` — wires synchronous
  `azure.identity.ManagedIdentityCredential()`.
- `backend/scripts/foundry_probe.py:51` — probe used synchronous
  `AzureCliCredential` (also sync).
- `24-04-PLAN.md:215` — switches to `azure.identity.aio.ManagedIdentityCredential`
  (async).

Three different credential classes across three "locked" sources.

**Required fix:** pick one. Default to **synchronous `ManagedIdentityCredential`**
because (a) CONFIG-DELTAS is locked, (b) the probe used a sync credential and
proved it works, (c) the lifespan construction call is a one-shot at app startup,
not a per-request hot path, so async credential is overengineering.

**Red test:**
`backend/tests/test_foundry_credential_shape.py` — instantiates `FoundryChatClient`
with the chosen credential class.

**Resolution:**
- **amended in plan 24-04-PLAN.md** — credential class changed to sync `azure.identity.ManagedIdentityCredential`; red test landed; AST scan asserts `azure.identity.aio` import is absent.
- **amended in plan 24-09-PLAN.md** — invariant verified (does not re-import).
- **amended in plan 24-14-PLAN.md** — invariant verified (does not re-import).
- **amended in plan 24-20-PLAN.md** — Gate 4 probe replay uses sync credential per CONFIG-DELTAS.

---

## P1-6 — Probe replay gate is not executable as written

**Affected plans:** 24-20.

**Defect:**
- `24-20-PLAN.md:134` — Gate 4 of the pre-deploy gate redirects probe stdout to
  `/tmp/*.json` and expects exact JSON diffs against committed fixtures.
- `backend/scripts/foundry_probe.py:74` — the probe writes JSON directly to the
  committed fixture path AND prints only status to stderr. There is no stdout
  JSON to redirect.

Even if the redirection bug were fixed, exact JSON diff is unstable.

**Required fix:** rewrite Gate 4 with two layers.
1. **Normalize then diff** — strip volatile fields from both sides.
2. **Invariant assertions** — supplement with shape checks.

**Red test:**
- `backend/tests/test_probe_replay_invariants.py` — replays each probe against
  the deployed backend, asserts shape invariants.
- `backend/tests/test_probe_replay_normalized_diff.py` — runs probe, normalizes
  output, diffs against committed fixture.

**Resolution: amended in plan 24-20-PLAN.md** — Gate 4 rewritten; helper `backend/scripts/foundry_probe_compare.py` created; both red tests landed; /tmp redirect language removed.

---

## P1-7 — The admin eval gate has no baseline (RESOLVED PER OPERATOR DECISION)

**Decision: option (a) — seed admin golden cases + re-baseline.**

**Affected plans:** 24-20, NEW seeding plan inserted before 24-20.

**Defect:**
- `24-20-PLAN.md:141` — Gate 6 requires admin + classifier eval within ±2pp
  of pre-migration baseline.
- `backend/tests/fixtures/eval-baseline-pre-migration.json:7` — admin baseline
  has zero cases and is marked `failed`.

**Required fix:** seed admin golden cases and re-baseline.

- New plan inserted between 24-13 (end of 23.2 task group) and 24-14:
  "Seed admin golden dataset (≥10 cases) and re-baseline pre-migration eval."

**Red test:**
`backend/tests/test_admin_eval_baseline_seeded.py` — asserts the baseline file
has `admin.total >= 10`, `admin.status == "completed"`, and `admin.routing_accuracy`
is a number.

**Resolution: created new plan 24-13.5-PLAN.md** — seed script `backend/scripts/seed_admin_golden_dataset.py` + cases manifest `backend/scripts/admin_golden_seed/cases.yaml` + red test landed. Operator curates ≥10 real production captures into cases.yaml at execution time.

---

## P2-8 — Full pre-deploy gates run before the last source-code cleanup

**Affected plans:** 24-20, 24-21.

**Defect:**
- `24-20-PLAN.md:169` — Plan 24-20 declares all gates green and unblocks the
  deploy.
- `24-21-PLAN.md:106` — Plan 24-21 then changes `config.py` and `main.py`
  (removes RC env-var settings + reads). Validation in 24-21 is import + grep
  only — no test rerun, no startup smoke.

**Required fix (operator-locked decision: Approach (a) — Reorder).** Move 24-21 BEFORE 24-20. The gates then run against the actual deploy artifact. Add Gate 10 startup smoke as cheap insurance.

**Red test:**
`backend/tests/test_app_startup_smoke.py` — boot the FastAPI app to lifespan
ready state, hit `/healthz`, assert 200.

**Resolution:**
- **amended in plan 24-21-PLAN.md** — `depends_on: [19.5]`; ships BEFORE 24-20.
- **amended in plan 24-20-PLAN.md** — `depends_on: [21]`; new Gate 10 startup smoke runs as part of pre-deploy gates; red test landed at `backend/tests/test_app_startup_smoke.py`.

---

## Summary table

| # | Plans amended | New plans | New tests | Severity | Status |
|---|---|---|---|---|---|
| P0-1 | 24-07, 24-16, 24-17 | 24-06.5 (probe extension) | test_session_rehydration_fresh_process | P0 | closed |
| P0-2 | 24-15, 24-16, 24-17, 24-20 | 24-24 (post-UAT cleanup) | test_inbox_dual_read | P0 | closed |
| P1-3 | 24-03, 24-04, 24-09, 24-14, 24-18 | — | test_legacy_middleware_imports_survive | P1 | closed |
| P1-4 | 24-02 | 24-19.5 (RC dep removal) | test_no_rc_imports_after_cleanup | P1 | closed |
| P1-5 | 24-04, 24-09, 24-14, 24-20 | — | test_foundry_credential_shape | P1 | closed |
| P1-6 | 24-20 | — | test_probe_replay_invariants, test_probe_replay_normalized_diff | P1 | closed |
| P1-7 | 24-20 | 24-13.5 (admin golden seeding) | test_admin_eval_baseline_seeded | P1 | closed |
| P2-8 | 24-20, 24-21 | — (reorder) | test_app_startup_smoke | P2 | closed |

**Net plan count:** original 23 + 4 new (24-06.5, 24-13.5, 24-19.5, 24-24) = 27 plans.

**Sequencing implication:** the new plans cluster around four points —
- pre-23.1 finalization (P0-1 probe → 24-06.5)
- end of 23.2 (P1-7 admin seeding → 24-13.5)
- end of 23.3 / before deploy gate (P1-4 RC dep removal → 24-19.5)
- post-UAT (P0-2 cleanup → 24-24)

All four insertion points are natural commit boundaries.

**Dependency reorder (P2-8):** 24-19 → 24-19.5 → 24-21 → 24-20 → 24-22 → 24-23 → 24-24.

---

## Out of scope for this gap closure

These came up in review but are NOT defects in the as-written plans:

- The 18 golden-trace fixtures replay timing in Gate 5 is unspecified but not
  broken; current language "replay all fixtures" is enough for executor.
- `forced_tool_failure` SSE emission point is left to the executor per CONTEXT
  D-04, which is fine — emission point is a mechanical decision.
- Per-destination precision/recall metric expansion stays deferred (EVAL-INVENTORY
  round-15 — separate phase).

---

## Status

All 8 defects have been amended in their affected plans, plus 4 new plans created (24-06.5, 24-13.5, 24-19.5, 24-24). Red tests landed for every defect. Awaiting operator final review before flipping `status: open` → `status: closed` in this file's frontmatter.
</content>
</invoke>
