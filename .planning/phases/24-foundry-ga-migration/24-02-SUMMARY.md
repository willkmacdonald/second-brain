---
phase: 24-foundry-ga-migration
plan: 02
subsystem: backend
tags: [dependencies, packaging, foundry-ga, agent-framework, config, ast-scan, regression-guard]

# Dependency graph
requires:
  - phase: 24-foundry-ga-migration
    provides: Push guard from 24-01 protects the broken-local-main window opened by this plan
  - phase: 23-foundry-ga-prep
    provides: CANDIDATE-pyproject.toml + CANDIDATE-uv.lock drop-ins (P1-4b corrected); CONFIG-DELTAS foundry_model spec
provides:
  - GA-only backend dep set (agent-framework-core>=1.3.0,<2 + agent-framework-foundry; agent-framework-azure-ai removed)
  - foundry_model: str = "gpt-4o" Pydantic Settings field reading FOUNDRY_MODEL env var
  - backend/tests/test_no_rc_imports_after_cleanup.py AST scan red test as permanent P1-4 regression guard
affects: [24-03, 24-04, 24-09, 24-11, 24-14, 24-19, 24-21]

# Tech tracking
tech-stack:
  added:
    - "agent-framework-core 1.3.0 (Microsoft Agent Framework GA core; replaces RC core 1.0.0rc2)"
    - "agent-framework-foundry 1.3.0 (Foundry chat client for FoundryChatClient)"
    - "agent-framework-openai 1.3.0 (transitive of foundry; provides agent_framework.openai)"
  patterns:
    - "Direct-pin to leaf packages instead of meta-package when meta-package transitive deps are unsafe (P1-4b lesson — agent-framework[all] pulls placeholder package)"
    - "AST scan as permanent regression guard for migration-induced import shapes — committed in red state, turns green incrementally as migration plans land"
    - "Strict cutover with intentional broken-local-main window protected by push guard (S-7); CONTEXT D-13 relaxation"

key-files:
  created:
    - backend/tests/test_no_rc_imports_after_cleanup.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
    - backend/src/second_brain/config.py

key-decisions:
  - "Direct-pin agent-framework-core>=1.3.0,<2 (NOT agent-framework meta-package) per P1-4b retraction; meta-package's [all] extra transitively pulls agent-framework-azure-ai-search==0.0.0a1 placeholder whose 0-byte agent_framework/__init__.py overwrites the real one"
  - "Strict cutover (not additive) per P1-4 retraction — RC and GA cannot coexist in shared agent_framework/ namespace dir; uv resolves silently to GA but RC's agent_framework.azure submodule breaks at import time"
  - "Settings.foundry_model added between azure_ai_project_endpoint and azure_ai_classifier_agent_id; three azure_ai_*_agent_id fields RETAINED (deferred deletion in 24-21 after GA image deploys, per CONFIG-DELTAS safe deploy sequence)"
  - "AST scan red test folded in from former plan 24-19.5 (deleted in P1-4 retraction); committed in red state with 10 source files still importing RC; turns green incrementally as 24-04, 24-09, 24-11, 24-14, 24-19 strip imports"
  - "Plan verification via AST parse + grep instead of `from second_brain.config import settings` (which would hit the RC import wall via downstream module imports)"

patterns-established:
  - "P1-4b direct-pin guard pattern: when a Microsoft meta-package's [all] extra is known to pull a placeholder, pin only the leaves the codebase actually imports + add a comment explaining why; verify with __init__.py size assertion (placeholder is 0 bytes, real is ~13KB)"
  - "Migration regression guard via AST scan: cheap, fast, structural — caught the 30 import/reference sites cleanly without any framework introspection"

requirements-completed: [F-01, D-12, P1-4-RETRACTED]

# Metrics
duration: 6min
completed: 2026-05-10
---

# Phase 24 Plan 02: Apply GA Dep Set + foundry_model Setting + AST Scan Red Test Summary

**GA-only dep set lands as a strict drop-in from Phase 23 CANDIDATE files (P1-4b direct-pin to agent-framework-core, NOT the agent-framework meta-package whose [all] extra pulls a 0-byte placeholder package); foundry_model setting added; AST scan red test committed in intentional red state as permanent P1-4 regression guard.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-10T17:46:07Z
- **Completed:** 2026-05-10T17:51:52Z
- **Tasks:** 3 / 3 atomic commits
- **Files modified:** 3 (pyproject.toml, uv.lock, config.py)
- **Files created:** 1 (test_no_rc_imports_after_cleanup.py)
- **Commits:** 3 task + 0 final-metadata (final-metadata commit deferred to orchestrator per parallel-executor protocol)
- **Execution attempt:** #3 (attempts #1 and #2 hit packaging defects P1-4 + P1-4b respectively; both retracted before this attempt)

## Accomplishments

- **Strict cutover replaced backend/pyproject.toml + backend/uv.lock verbatim from `.planning/phases/23-foundry-ga-prep/CANDIDATE-*` drop-ins** (P1-4b corrected). RC dep `agent-framework-azure-ai==1.0.0rc2` removed entirely. GA dep set: `agent-framework-core>=1.3.0,<2` + `agent-framework-foundry`. NOT the `agent-framework` meta-package — see P1-4b retraction note.
- **`uv sync` clean — 101 packages resolved, 0 errors.** Local venv now has GA only.
- **End-to-end import verification matches the orchestrator's prior independent verification:**
  - `agent_framework/__init__.py`: **13123 bytes** (real, not corrupted; placeholder would be 0 bytes — P1-4b regression guard satisfied)
  - `from agent_framework import Agent, ChatOptions, AgentSession`: works
  - `from agent_framework_foundry import FoundryChatClient`: works
  - `from agent_framework.azure import AzureAIAgentClient`: raises ImportError (load-bearing failure expected; this is the source-code's actual RC import shape that will be stripped by 24-04 / 24-09 / 24-14 / 24-19)
- **Settings.foundry_model = "gpt-4o" added** between `azure_ai_project_endpoint` and `azure_ai_classifier_agent_id` per CONFIG-DELTAS Section "Phase 24 task group 23.1 — config.py additions". All three `azure_ai_*_agent_id` fields retained (deferred deletion in plan 24-21 after GA image deploys, per the NEGATIVE assertion in CONFIG-DELTAS).
- **AST scan red test landed at backend/tests/test_no_rc_imports_after_cleanup.py** (folded in from former plan 24-19.5 per P1-4 retraction). Committed in **intentional red state** — fails with **30 offender lines** across **10 source files** that still import RC. Turns green incrementally as 24-04, 24-09, 24-11, 24-14, 24-19 strip RC imports. Permanent regression guard after 24-19.

## Task Commits

Each task was committed atomically with `--no-verify` (per parallel-executor protocol):

1. **Task 1: Strict cutover — replace pyproject.toml + uv.lock from CANDIDATE drop-ins** — `acec255` (feat)
2. **Task 2: Add foundry_model setting to config.py** — `4e2fec9` (feat)
3. **Task 3: Land AST scan red test (folded in from former plan 24-19.5)** — `f3b1fa5` (test, intentional red state)

## Files Modified / Created

| File | Action | Purpose |
|---|---|---|
| `backend/pyproject.toml` | Modified (verbatim drop-in from CANDIDATE-pyproject.toml) | GA-only dep set; comment block explains direct-pin rationale (P1-4b) |
| `backend/uv.lock` | Modified (verbatim drop-in from CANDIDATE-uv.lock) | Locked dep tree resolved against direct-pin pyproject.toml; placeholder package absent; size: 2352 lines (down from 2494) |
| `backend/src/second_brain/config.py` | Modified | Added `foundry_model: str = "gpt-4o"` after `azure_ai_project_endpoint`; three `azure_ai_*_agent_id` fields retained with KEEP-deleted-in-24-21 comments |
| `backend/tests/test_no_rc_imports_after_cleanup.py` | Created (90 lines) | AST scan walking `backend/src/second_brain/`; asserts zero references to `agent_framework.azure` / `agent_framework_azure_ai` modules and `AzureAIAgentClient` name |

## Verified Behaviour

```text
$ cd backend && uv sync
Resolved 101 packages in 3ms
Audited 94 packages in 11ms

$ cd backend && uv run python -c "import agent_framework, os; print(os.path.getsize(agent_framework.__file__))"
13123

$ cd backend && uv run python -c "from agent_framework import Agent, ChatOptions, AgentSession; from agent_framework_foundry import FoundryChatClient; print('GA imports OK')"
GA imports OK

$ cd backend && uv run python -c "from agent_framework.azure import AzureAIAgentClient" 2>&1 | tail -1
ImportError: cannot import name 'AzureAIAgentClient' from 'agent_framework.azure'

$ grep "foundry_model" backend/src/second_brain/config.py
    foundry_model: str = "gpt-4o"  # NEW (Phase 24 task group 23.1)

$ cd backend && uv run pytest tests/test_no_rc_imports_after_cleanup.py -x --noconftest 2>&1 | tail -3
FAILED tests/test_no_rc_imports_after_cleanup.py::test_no_rc_imports_under_src
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
============================== 1 failed in 0.12s ===============================
```

The test failure message lists 30 offender lines across these 10 source files (the F-01 — F-19 calibration target list):

- `agents/admin.py`
- `agents/classifier.py`
- `agents/investigation.py`
- `eval/runner.py`
- `main.py`
- `processing/admin_handoff.py`
- `streaming/adapter.py`
- `streaming/investigation_adapter.py`
- `tools/investigation.py`
- `warmup.py`

Each file produces ~3 offenders (the `from agent_framework.azure import` pattern, the named import `AzureAIAgentClient`, and the identifier reference where it's used) — consistent with the migration plan's F-01 finding count.

## Acknowledged Consequences (per CONTEXT D-13 relaxation)

- **Local `main` is intentionally not buildable** between this commit and the migration plan that strips a given file's RC import. Verified: `cd backend && uv run python -c "from second_brain.main import app"` fails (the trace continues past the agent_framework wall to the AppInsights instrumentation key check because env vars aren't set locally; in any environment with env vars set, the RC import wall on `main.py:33` is the failure point).
- **Push guard from plan 24-01 (sentinel + pre-push hook) protects against accidental push** during this window. Sentinel verified present at `.planning/phases/24-foundry-ga-migration/PUSH-GUARD-ACTIVE`.
- **Bisect across the migration window is compromised.** Bisect within a task group's terminal state (after 24-08, after 24-13, after 24-19) still works.

## Decisions Made During Execution

- **Verbatim drop-in via `cp`, not Write.** Per the plan's explicit instruction (line 217-223), used `cp .planning/phases/23-foundry-ga-prep/CANDIDATE-pyproject.toml backend/pyproject.toml` and the same for uv.lock. Avoids partial state on a 2352-line lock file.
- **Test verification via `--noconftest` + direct python import**, not the plan's grep pattern alone. The plan's `grep -qE "FAILED|RC SDK imports/references found"` would match either, but the conftest issue (see Deferred Issues below) prevents the plan's exact pytest invocation from reaching test collection. The `--noconftest` invocation matches the plan's grep pattern, and a direct python invocation of the test function confirms the assertion fails with 30 offender lines — both demonstrate red state.
- **Did NOT modify the plan file's verification command** even though it has a comment-line vs dep-line ambiguity for the strict `! grep -q "agent-framework-azure-ai"` check. The CANDIDATE drop-in (which the plan tells us to apply verbatim) contains an explanatory comment in `pyproject.toml` line 9 that mentions the placeholder package name. This is intentional context for future readers. The load-bearing acceptance — no `agent-framework-azure-ai*` dep LINE — is satisfied (verified via `grep -E '^\s*"agent-framework-azure-ai' backend/pyproject.toml` returning empty).

## Deviations from Plan

### Auto-fixed Issues

None. Tasks 1, 2, 3 executed exactly as written. The test infrastructure surfacing in Task 3 is documented as a deferred issue, not auto-fixed (out of scope per the SCOPE BOUNDARY rule).

### Verification Quirks (documented, not auto-fixed)

**1. [Documentation only] Plan Task 1 verify command uses `! grep -q "agent-framework-azure-ai" backend/pyproject.toml`**
- The CANDIDATE-pyproject.toml drop-in contains the substring in a comment line explaining P1-4b's direct-pin rationale (line 9: `# The meta-package's [all] extra transitively pulls agent-framework-azure-ai-search==0.0.0a1`).
- Strict interpretation: grep would return 0 (substring found in comment), so the negation in the plan's verify command would fail.
- Practical interpretation: no DEPENDENCY LINE pins `agent-framework-azure-ai*`. Verified via `grep -E '^\s*"agent-framework-azure-ai' backend/pyproject.toml` returning empty.
- Resolution: kept CANDIDATE drop-in verbatim (it is the source of truth per P1-4b retraction). Future plans may want to tighten the verification regex to anchor on the dependency-line shape rather than the bare substring.

**2. [Documentation only] Plan Task 3 verify command uses `pytest ... 2>&1 | grep -qE "FAILED|RC SDK imports/references found"`**
- The default pytest invocation hits a conftest ImportError on `mcp` BEFORE collecting tests (see Deferred Issues below).
- Workaround: `--noconftest` makes the test run and fail as intended. The plan's grep pattern matches.
- Resolution: verified red state via two paths — (a) `pytest --noconftest` matches the plan's grep, and (b) direct python invocation of the test function shows AssertionError with 30 offender lines.

## Deferred Issues

**1. backend/tests/conftest.py imports `mcp` (transitive RC dep dropped by CANDIDATE drop-in)**
- **Found during:** Task 3 verification — running `cd backend && uv run pytest tests/test_no_rc_imports_after_cleanup.py -x` failed with `ModuleNotFoundError: No module named 'mcp'` from `backend/tests/conftest.py:51` (`importlib.import_module(sub)` for `mcp.server.fastmcp`).
- **Root cause:** `mcp` (the open MCP protocol Python package on PyPI) was a transitive dep of `agent-framework-azure-ai` → `agent-framework-ag-ui` chain in the RC dep tree. Verified by inspecting `git show HEAD~3:backend/uv.lock` which contained `name = "mcp"`. The CANDIDATE drop-in (correctly, per its design) dropped the entire RC tree, which removed `mcp` from the lock.
- **Effect:** Any default `pytest` invocation in `backend/` fails at conftest load — the entire backend test suite becomes uncollectable.
- **Why deferred (Rule scope):** This is test-infrastructure surgery on a file unrelated to the plan's `<files_modified>` frontmatter. The CANDIDATE drop-in is the canonical source per P1-4b retraction; modifying it inline to add `mcp` to `[project.optional-dependencies] test` would diverge from the verbatim drop-in directive. Adding `mcp` to test extras and regenerating the lock is its own concern that warrants a separate housekeeping plan or a small fix-up commit at the orchestrator's discretion.
- **Workaround used during this plan:** `pytest --noconftest` for the AST scan red test verification. Confirmed the plan's verify pattern (`grep -qE "FAILED|RC SDK imports/references found"`) matches via this path. Also confirmed via a direct `python -c "from test_no_rc_imports_after_cleanup import test_no_rc_imports_under_src; test_no_rc_imports_under_src()"` invocation — AssertionError with 30 offender lines.
- **Recommended follow-up:** add `"mcp"` to `[project.optional-dependencies] test` in `backend/pyproject.toml` and regenerate `backend/uv.lock`. Alternatively: defensive conftest that no-ops the local MCP server registration when `mcp` is absent (lower risk, smaller diff). Either restores the entire backend test suite to runnable state. This is required before any plan that wants to run pytest against the backend suite normally (most plans 24-04 onward).
- **Severity:** medium — does not block plan 24-02 itself (the AST scan red test is verified via two alternate paths) but blocks routine pytest workflow until resolved.

## P1-4 / P1-4b Retraction Notes (for downstream plans)

- **P1-4 RETRACTED 2026-05-10** (commit `5dbfa60`): the original additive-deps approach is packaging-infeasible because both versions of `agent-framework-core` install to the same `agent_framework/` directory. Strict cutover (this plan) is the canonical approach.
- **P1-4b RETRACTED 2026-05-10** (commit `08a2277`): the meta-package `agent-framework`'s `[all]` extra transitively pulls `agent-framework-azure-ai-search==0.0.0a1` whose 0-byte `agent_framework/__init__.py` corrupts the real one from `agent-framework-core`. Direct-pin to `agent-framework-core>=1.3.0,<2` + `agent-framework-foundry` is the canonical approach.
- **24-PLAN-DEFECTS.md status updated:** P1-4 row in summary table reads "closed" but the resolution-summary text now reads RETRACTED with both retraction notes. The `tests/test_no_rc_imports_after_cleanup.py` red test (originally landed in 24-19.5) is now landed in plan 24-02 (this plan). Plan 24-19.5 has been deleted from the corpus.
- **Note for future GA upgrades:** if Microsoft fixes the placeholder package upstream (likely; this is a clear bug in `agent-framework-azure-ai-search==0.0.0a1`), the `agent-framework` meta-package may become safe to use. Until then, the direct-pin pattern is required. Add a Phase 25+ cleanup item to re-evaluate.

## Reminder for Plan 24-21

The three `azure_ai_*_agent_id` settings (classifier, admin, investigation) are RETAINED in this plan with `# KEEP — deleted in plan 24-21` comments. Per CONFIG-DELTAS Section "Phase 24 task group 23.3 — config.py orphan cleanup":

- The deployed RC image's `main.py` reads these settings at lifespan startup (lines 514, 596, 687).
- Removing them BEFORE the GA image deploys would cause the running RC revision to fall through to creating BLANK portal agents (per `agents/classifier.py:40` and symmetric paths for admin/investigation), causing live agent drift.
- Plan 24-21 must remove these fields in the same commit as the corresponding lifespan-read removals in `main.py`, and only after the GA image is healthy in production.

## Self-Check: PASSED

- File `backend/pyproject.toml`: FOUND, modified at commit `acec255`
- File `backend/uv.lock`: FOUND, modified at commit `acec255`
- File `backend/src/second_brain/config.py`: FOUND, modified at commit `4e2fec9`
- File `backend/tests/test_no_rc_imports_after_cleanup.py`: FOUND, created at commit `f3b1fa5`
- Commit `acec255`: FOUND in `git log --oneline --all`
- Commit `4e2fec9`: FOUND in `git log --oneline --all`
- Commit `f3b1fa5`: FOUND in `git log --oneline --all`
- All success criteria from prompt: PASSED (see "Verified Behaviour" section above)
- No modifications to `.planning/STATE.md` or `.planning/ROADMAP.md`: VERIFIED via `git diff --name-only HEAD~3..HEAD | grep -E "STATE\.md|ROADMAP\.md"` returning empty
