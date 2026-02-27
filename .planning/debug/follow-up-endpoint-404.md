---
status: resolved
trigger: "POST /api/capture/follow-up returning 404 in production"
created: 2026-02-27T00:00:00Z
updated: 2026-02-27T00:00:00Z
---

## Current Focus

hypothesis: Phase 9 commits (including follow-up endpoint) were never pushed to remote
test: Compare origin/main vs local main
expecting: origin/main is behind local main, missing the follow-up endpoint commit
next_action: Report root cause -- code not deployed

## Symptoms

expected: POST /api/capture/follow-up returns SSE stream with classification events
actual: Returns 404 with 1ms response time (route not found)
errors: HTTP 404 on POST /api/capture/follow-up
reproduction: Any call to the follow-up endpoint on brain.willmacdonald.com
started: Since Phase 9 was "completed" -- the endpoint has never worked in production

## Eliminated

(none needed -- root cause found on first hypothesis)

## Evidence

- timestamp: 2026-02-27
  checked: backend/src/second_brain/api/capture.py
  found: Follow-up endpoint exists at line 318 as @router.post("/api/capture/follow-up")
  implication: Code is correct locally

- timestamp: 2026-02-27
  checked: backend/src/second_brain/main.py line 236
  found: capture_router is included via app.include_router(capture_router), no prefix
  implication: Router mounting is correct -- all routes in capture.py are registered

- timestamp: 2026-02-27
  checked: mobile/lib/ag-ui-client.ts sendFollowUp function (line 211)
  found: URL is `${API_BASE_URL}/api/capture/follow-up` -- matches backend route exactly
  implication: No URL mismatch between mobile and backend

- timestamp: 2026-02-27
  checked: git log origin/main..main
  found: 16 commits on local main NOT pushed to origin/main. origin/main is at a31c0af (phase 8 completion). The follow-up endpoint was added in e6870d1 (feat(09-01)), which is among the 16 unpushed commits.
  implication: The deployed code on Azure Container Apps does NOT have the follow-up endpoint. CI/CD deploys from origin/main, which is still at Phase 8.

## Resolution

root_cause: The 16 Phase 9 commits on local main were never pushed to origin/main. The CI/CD pipeline (GitHub Actions -> Azure Container Apps) deploys from the remote main branch, which is still at commit a31c0af (Phase 8 completion). The follow-up endpoint was added in commit e6870d1 but has never reached the remote repository or the deployed container.
fix: Push local main to origin/main (git push origin main)
verification: After push, wait for CI/CD to deploy, then POST /api/capture/follow-up should return a proper SSE response instead of 404
files_changed: []
