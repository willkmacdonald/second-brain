# Codex Code Review

Date: 2026-04-13

Scope:
- Current workspace state in `/Users/willmacdonald/Documents/Code/claude/second-brain`
- Current planning/spec documents under `.planning/`
- Backend and mobile code paths for investigation, observability, recipe extraction, and recent mobile error handling

Checks run:
- `backend/.venv/bin/pytest -q`
- `backend/.venv/bin/pytest backend/tests/test_recipe_tools.py -q`
- `backend/.venv/bin/pytest backend/tests/test_errands_api.py -q`
- `cd mobile && npx tsc --noEmit --pretty false`

Summary:
- No Critical issues confirmed in this pass.
- Highest confirmed severity is High.

## Critical

None confirmed.

## High

### 1. Mobile app does not typecheck because the Sentry error boundary fallback has the wrong prop type

Severity: High

Evidence:
- `mobile/app/_layout.tsx:22` passes `ErrorFallback` directly to `Sentry.ErrorBoundary`.
- `mobile/components/ErrorFallback.tsx:3-10` types `error` as `Error`.
- `npx tsc --noEmit --pretty false` currently fails with:
  - `app/_layout.tsx(22,38): error TS2322 ... Type 'unknown' is not assignable to type 'Error'.`

Impact:
- The mobile workspace is not in a clean, releasable state.
- Any CI/EAS step that enforces TypeScript correctness will fail before shipping.

Why this matters:
- The Phase 17.3 observability work added Sentry as a foundational crash-reporting path. Leaving the app red at typecheck means the instrumentation work is not actually in a deployable state.

Recommendation:
- Align `ErrorFallback` with Sentry's `FallbackRender` contract and narrow `unknown` inside the component before reading `message`.

### 2. Recipe URL extraction hard-fails on DNS lookup errors, which breaks the feature and keeps the backend test baseline red

Severity: High

Evidence:
- `backend/src/second_brain/tools/recipe.py:41-80` performs SSRF protection by resolving the hostname with `socket.getaddrinfo(...)`.
- `backend/src/second_brain/tools/recipe.py:72-73` returns `False` on any `socket.gaierror`.
- `backend/src/second_brain/tools/recipe.py:111-114` blocks the request entirely when `_is_safe_url(url)` returns `False`.
- `backend/tests/test_recipe_tools.py:146-245` expects `https://example.com/...` to proceed through mocked fetch tiers, but the tool rejects the URL before any mock is used.
- `backend/.venv/bin/pytest backend/tests/test_recipe_tools.py -q` currently reports `6 failed`.

Impact:
- The recipe-fetching feature becomes unavailable in environments where DNS resolution is restricted, flaky, or intentionally sandboxed.
- Unit tests are coupled to live DNS resolution even though the network/browser layers are mocked.
- The backend suite is not green (`176 passed, 6 failed, 5 skipped` in the full run).

Why this matters:
- This is not only a test problem. The current implementation treats "cannot resolve right now" as equivalent to "private/internal target", which is an incorrect security decision and creates avoidable false negatives in production-like restricted environments.

Recommendation:
- Decouple SSRF policy from live DNS availability. Either:
  - inject/mock the resolver in tests, or
  - treat resolution failure as "unable to verify" and let the actual fetch layer fail naturally, while still explicitly blocking known-private addresses and hostnames.

## Medium

None confirmed.

## Minor

### 3. Planning docs still describe the old "last error" dashboard behavior, but the intended feature has changed to "Errors (24 hours)"

Severity: Minor

Clarification:
- Product intent has changed since the original Phase 18 docs. The current intended behavior is `Errors (24 hours)`, not `Last error`.

Evidence:
- Current code implements the updated behavior:
  - `mobile/components/DashboardCards.tsx:53-69` renders `Errors (24h)`.
  - `backend/src/second_brain/api/health.py:66-70` returns aggregate `errorCount`.
- Multiple planning artifacts still describe the superseded behavior:
  - `.planning/phases/18-mobile-investigation-chat/18-CONTEXT.md:22-31`
  - `.planning/phases/18-mobile-investigation-chat/18-02-SUMMARY.md:57-76`
  - `.planning/phases/18-mobile-investigation-chat/18-04-SUMMARY.md:53-70`
  - `.planning/phases/18-mobile-investigation-chat/18-UAT.md:43-49`
  - `.planning/STATE.md:86-89`

Impact:
- Future reviews or implementation work can misclassify the current dashboard as broken when it is actually following the newer product decision.
- Verification docs and UAT notes are no longer reliable for this part of the app.

Recommendation:
- Update the affected planning, summary, and UAT documents so they describe `Errors (24 hours)` as the current intended behavior.

### 4. Errands API tests leak an unawaited coroutine when `asyncio.create_task` is mocked

Severity: Minor

Evidence:
- `backend/tests/test_errands_api.py:697-704` patches `second_brain.api.errands.asyncio.create_task` with a plain mock in `test_get_errands_triggers_processing`.
- `backend/tests/test_errands_api.py:741-748` does the same in `test_get_errands_no_processing_when_query_returns_empty`.
- `backend/src/second_brain/api/errands.py:222-249` constructs the real `process_admin_capture(...)` coroutine before passing it to `create_task(...)`.
- `backend/.venv/bin/pytest backend/tests/test_errands_api.py -q` passes but emits:
  - `RuntimeWarning: coroutine 'process_admin_capture' was never awaited`

Impact:
- The suite is noisy and no longer trustworthy as a clean async baseline.
- Real async lifecycle regressions can be easier to miss once warning output is normalized.

Recommendation:
- In the tests, either patch `process_admin_capture`/`process_admin_captures_batch` directly, or have the `create_task` mock close the coroutine it receives so the test does not leak it.

## Open Questions

1. `.planning/REQUIREMENTS.md:28-29` still says:
   - `MOBL-04` quick actions include `last eval results`
   - `MOBL-05` dashboard includes `eval scores`
   but the Phase 18 docs defer eval scores and define only 3 quick-action chips.
   If that product intent also changed, those docs should be reconciled for the same reason as the dashboard wording above.

2. This review was performed against the current workspace state, including uncommitted files already present before I started.
