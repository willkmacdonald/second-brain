---
phase: 24-foundry-ga-migration
plan: 22
subsystem: infra
tags: [deploy, container-apps, oidc, github-actions, foundry-ga, hotfix, health-probe]

requires:
  - phase: 24-21
    provides: Final RC-free source state with Settings.extra='ignore' tolerating residual env vars
  - phase: 24-20
    provides: Cumulative fidelity audit PASS-WITH-WARNINGS, 0 in-scope ❌; pre-deploy gates resolved
provides:
  - Phase 24 GA backend deployed to brain.willmacdonald.com (revision sha-1bc40d8)
  - /health probe migrated from RC AzureAIAgentClient to per-agent attribute presence check
  - Container App env vars FOUNDRY_MODEL/ENABLE_INSTRUMENTATION/ENABLE_SENSITIVE_DATA set on RC revision BEFORE push (asymmetric pattern intact)
  - test_observability.py 4 health tests rewritten for GA shape (7/7 pass)
affects: [24-23, 24-24, post-deploy-UAT, mobile-dashboards, push-notifications]

tech-stack:
  added: [no new deps — deploy event]
  patterns: [asymmetric-code-now-env-later, agent-readiness-as-foundry-health-proxy]

key-files:
  modified:
    - backend/src/second_brain/api/health.py
    - backend/tests/test_observability.py
  deleted:
    - .planning/phases/24-foundry-ga-migration/PUSH-GUARD-ACTIVE

key-decisions:
  - "/health probe rewritten in 24-22 hotfix (not original plan scope): the executor's deferred-items.md flag from 24-19 surfaced as a deploy-time issue — telemetry showed 3 agents ready (GA) but /health reported degraded because the probe still read app.state.foundry_client (intentionally None per 24-19). Fix promotes per-agent readiness to the foundry-status signal: connected if all 3 agents present, degraded if some missing, not_configured if none."
  - "Cold-startup window matters: first /health probe within ~20s of revision creation can hit pre-warmup state (agents not yet on app.state) and report degraded. After warmup completes, reports ok. This is correct behavior, not a regression."
  - "CI/CD first attempt failed at actions/checkout with GitHub HTTP 500 (transient infrastructure issue, not Phase 24 defect); rerun succeeded clean."

patterns-established:
  - "Asymmetric code-now / env-later cleanup: Pydantic Settings.extra='ignore' (from 24-21) tolerates residual Container App env vars so GA image boots cleanly even before Step C removes AZURE_AI_*_AGENT_ID in 24-23"
  - "Agent-readiness as foundry-health proxy: with no central foundry_client (retired in 24-19), per-agent attribute presence on app.state IS the foundry connectivity signal"

requirements-completed: [D-12]

duration: ~35min (Step A 2min + Step B 1min + push 0min + 2 CI runs + 1 hotfix iteration)
completed: 2026-05-11
---

# Phase 24-22: Foundry GA Deploy Event Summary

**Phase 24 Foundry GA migration deployed to production. Revision `sha-1bc40d8` active, serving 100% traffic, /health reports `status=ok, foundry=connected, admin_agent=ready, investigation_agent=ready` after a hotfix migrated the /health probe to GA agent attributes.**

## Performance

- **Duration:** ~35 min (operator-driven push to verified-healthy GA revision)
- **Started:** 2026-05-11T13:48Z (Step A env-var update on RC revision)
- **Completed:** 2026-05-11T14:33Z (hotfix revision active + /health ok)
- **Tasks:** 3/3 (Step A automated, Step B automated, Step C operator-driven push)
- **Commits:** 2 (push-guard removal + /health hotfix)

## Accomplishments

- **Phase 24 GA backend live in production.** All RC SDK code (`AzureAIAgentClient`, `agent_framework.azure.*`) gone from deployed image. All 3 Foundry agents (Classifier/Admin/Investigation) constructed via GA `FoundryChatClient` + `Agent` factories.
- **Step A executed** on RC revision before push: `FOUNDRY_MODEL=gpt-4o`, `ENABLE_INSTRUMENTATION=true`, `ENABLE_SENSITIVE_DATA=false` added; `AZURE_AI_*_AGENT_ID` left intact per NEGATIVE assertion (24-23 removes them post-UAT).
- **Step B unguard**: `.planning/phases/24-foundry-ga-migration/PUSH-GUARD-ACTIVE` sentinel deleted, pre-push hook now exit 0.
- **Step C push**: operator pushed `695b532` to origin/main; OIDC build → ACR → Container Apps revision rolled out as `sha-695b532`.
- **/health hotfix shipped same session** (`1bc40d8`) — promotes per-agent readiness to foundry-status signal since `foundry_client` retired in 24-19.

## Task Commits

1. **Step A: Set GA env vars** — no commit (`az containerapp update`)
2. **Step B: Remove push guard** — `695b532` chore (sentinel deletion)
3. **Step C: git push origin main** — operator action
4. **Hotfix: /health probe GA migration** — `1bc40d8` fix (health.py + test_observability.py)

## Files Modified

- `backend/src/second_brain/api/health.py` — /health probe rewritten to read `classifier_agent`/`admin_agent`/`investigation_agent` attrs (replaced RC `foundry_client.agents_client.list_agents` probe). TTL cache removed (no longer needed for attribute presence checks).
- `backend/tests/test_observability.py` — 4 health tests rewritten for GA shape. Removed `_FOUNDRY_CACHE_TTL` import, removed `_FakeAgentsClient` mock, removed TTL/time-warp tests, removed `foundry_client` injection. New tests cover: all-3-agents=ok, missing-agent=degraded, no-agents=not_configured, investigation toggle. 7/7 pass.
- `.planning/phases/24-foundry-ga-migration/PUSH-GUARD-ACTIVE` — DELETED (push guard removed).
- `.planning/ROADMAP.md` — 24-22 checkbox ticked.

## Decisions Made

- **/health probe shape:** "foundry=connected" inferred from all-3-agents-present (since there's no central client to ping anymore). Three states: connected (3/3), degraded (1-2 of 3), not_configured (0/3). This is the right proxy because the probe's purpose is "can the system serve agent requests" — a per-agent attribute check answers that directly without an extra Foundry round-trip.
- **Cold-startup tolerance**: probe doesn't add an explicit "warming" state; during the ~20s revision-creation window before agents land on app.state, /health reports degraded — which is technically true at that moment. Self-resolves at warmup.
- **Hotfix in 24-22 vs. follow-up**: the executor's deferred-items.md from 24-19 flagged this as a known follow-up. Choice to hotfix inline rather than defer: dashboards/notifications consume /health, and a "system is degraded" signal trips operator alarms — fixing the false signal in-flight is higher-value than letting it lie.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Critical] /health probe migration to GA shape (hotfix)**
- **Found during:** post-deploy verification of Step C
- **Issue:** Step C succeeded — GA revision `sha-695b532` active, `Healthy`, all 3 agents `ready (GA)` per telemetry — but `/health` reported `status=degraded`, `foundry=not_configured`, `admin_agent/investigation_agent=not_initialized`. Root cause: `app.state.foundry_client` was intentionally `None` per 24-19 (RC client retired); `app.state.admin_client` and `app.state.investigation_client` were renamed to `*_agent` in 24-09/24-04. The /health probe still read the old attribute names.
- **Fix:** Rewrote /health to read `classifier_agent`/`admin_agent`/`investigation_agent` attrs. Rewrote 4 test_observability.py health tests for the GA shape (removed TTL/time-warp/list_agents mocks). New test file 7/7 pass.
- **Files modified:** `backend/src/second_brain/api/health.py`, `backend/tests/test_observability.py`
- **Verification:** GA revision `sha-1bc40d8` /health returns `{"status":"ok","foundry":"connected","cosmos":"connected","admin_agent":"ready","investigation_agent":"ready"}` after warmup completes (~15s post-revision-creation).
- **Committed in:** `1bc40d8` (separate hotfix commit, same session)

---

**Total deviations:** 1 auto-fixed (1 critical hotfix)
**Impact on plan:** Hotfix necessary to prevent false-alarm dashboards/notifications. Follow-up flagged by 24-19 executor was on the path; surfaced as deploy-time issue. No scope creep.

## Issues Encountered

- **CI/CD first run failed at actions/checkout** (HTTP 500 from GitHub, 3 retries all hit the same transient infrastructure issue). Rerun succeeded clean. Not a Phase 24 defect.
- **Cold-startup window** for /health: first probe within ~20s of revision creation hit pre-warmup state and reported degraded; self-resolved after agents lifecycled in. Not a regression.

## User Setup Required

None — deploy event is complete.

## Next Phase Readiness

- **Wave 7 (24-23) UNBLOCKED**: day-after UAT can begin. Operator runs golden-path captures from mobile (errand, task, recipe URL, multi-turn HITL via voice / clarification) against the deployed GA revision; if all pass, plan 24-23 also removes the orphan `AZURE_AI_*_AGENT_ID` env vars from Container App (Step C of CONFIG-DELTAS).
- **Wave 8 (24-24) blocked on 24-23 UAT**: post-UAT P0-2 cleanup (backfill script + `foundryThreadId` field removal) requires UAT to confirm Option A history field is reliable.

---
*Phase: 24-foundry-ga-migration*
*Completed: 2026-05-11*
