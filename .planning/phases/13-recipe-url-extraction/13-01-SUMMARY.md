---
phase: 13-recipe-url-extraction
plan: 01
subsystem: api, infra
tags: [playwright, beautifulsoup4, lxml, headless-browser, recipe-extraction, json-ld]

# Dependency graph
requires:
  - phase: 12.3-destination-affinity-and-knowledge-system
    provides: ErrandItem model, AdminTools class, admin agent tool registration pattern
provides:
  - RecipeTools class with fetch_recipe_url Admin Agent tool
  - Playwright + Chromium in Docker image for headless browsing
  - ErrandItem sourceName/sourceUrl fields for recipe attribution
  - add_errand_items passthrough for source attribution fields
affects: [13-02-PLAN, 13-03-PLAN, mobile ErrandRow source attribution display]

# Tech tracking
tech-stack:
  added: [playwright, beautifulsoup4, lxml]
  patterns: [Playwright browser lifecycle in FastAPI lifespan, browser context per-request isolation, JSON-LD structured data extraction]

key-files:
  created:
    - backend/src/second_brain/tools/recipe.py
    - backend/tests/test_recipe_tools.py
  modified:
    - backend/src/second_brain/models/documents.py
    - backend/src/second_brain/tools/admin.py
    - backend/src/second_brain/main.py
    - backend/Dockerfile
    - backend/pyproject.toml

key-decisions:
  - "Playwright browser launched once in lifespan, new context per fetch (cheap isolation)"
  - "JSON-LD extraction as supplementary context alongside visible text for LLM"
  - "Visible text truncated to 12000 chars (~3000 tokens) to fit LLM context"
  - "Playwright block nested inside admin try block -- recipe tools only useful with admin agent"
  - "Resource blocking targets image/media/font/stylesheet only (preserving XHR/fetch for SPA content)"

patterns-established:
  - "Playwright browser lifecycle: start in lifespan, store on app.state, close in cleanup"
  - "Tool class bound to shared browser instance (RecipeTools pattern)"
  - "Source attribution fields as optional model extensions (sourceName/sourceUrl)"

requirements-completed: [RCPE-01, RCPE-02, RCPE-03]

# Metrics
duration: 6min
completed: 2026-03-20
---

# Phase 13 Plan 01: Recipe URL Extraction Infrastructure Summary

**Playwright-based fetch_recipe_url Admin Agent tool with JSON-LD extraction, ErrandItem source attribution fields, and Docker Chromium support**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-20T14:37:21Z
- **Completed:** 2026-03-20T14:43:55Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Created RecipeTools class with fetch_recipe_url tool that fetches web pages via headless Chromium, blocks non-essential resources, extracts visible text and JSON-LD Recipe structured data
- Extended ErrandItem model with optional sourceName and sourceUrl fields for recipe source attribution
- Updated Dockerfile with Playwright system dependencies (libnss3, libgbm1, etc.), Chromium browser binary install, and PLAYWRIGHT_BROWSERS_PATH env var
- Wired Playwright browser lifecycle into FastAPI lifespan with graceful degradation and proper cleanup
- Added 14 unit tests covering JSON-LD extraction (7 tests) and mocked page fetching (7 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend ErrandItem model, add_errand_items tool, Dockerfile, and pyproject.toml** - `3110896` (feat)
2. **Task 2: Create RecipeTools with fetch_recipe_url, wire into main.py lifespan, add unit tests** - `a2631d9` (feat)

## Files Created/Modified
- `backend/src/second_brain/tools/recipe.py` - RecipeTools class with fetch_recipe_url tool and _extract_json_ld_recipe helper
- `backend/tests/test_recipe_tools.py` - 14 unit tests for recipe tools
- `backend/src/second_brain/models/documents.py` - ErrandItem extended with sourceName/sourceUrl
- `backend/src/second_brain/tools/admin.py` - add_errand_items passes through source attribution fields
- `backend/src/second_brain/main.py` - Playwright lifecycle + RecipeTools registration in admin agent
- `backend/Dockerfile` - Chromium system deps, browser install, PLAYWRIGHT_BROWSERS_PATH
- `backend/pyproject.toml` - playwright, beautifulsoup4, lxml dependencies added

## Decisions Made
- Playwright browser launched once in lifespan, each fetch creates a new browser context (cheap, isolated) rather than a new browser
- JSON-LD Recipe data extracted as supplementary structured context alongside truncated visible text
- Visible text truncated to 12000 characters to stay within reasonable LLM token limits
- Playwright startup block nested inside admin agent try block since recipe tools are only useful when admin agent is available
- Resource blocking targets only image/media/font/stylesheet -- XHR and fetch are preserved for SPA recipe sites

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed @tool decorator invocation in tests**
- **Found during:** Task 2
- **Issue:** Plan code used `__wrapped__` to access the underlying method, but agent_framework's @tool decorator does not expose `__wrapped__`. The tool is directly callable.
- **Fix:** Changed test calls from `tools.fetch_recipe_url.__wrapped__(tools, url=...)` to `tools.fetch_recipe_url(url=...)`
- **Files modified:** backend/tests/test_recipe_tools.py
- **Verification:** All 14 tests pass
- **Committed in:** a2631d9 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test invocation fix. No scope creep.

## Issues Encountered
- Two pre-existing test failures found (test_admin_handoff and test_transcription) unrelated to this plan's changes. Not addressed per scope boundary rules.

## User Setup Required

None - no external service configuration required. Playwright and Chromium are installed in the Docker image at build time.

## Next Phase Readiness
- fetch_recipe_url tool is registered and available for the Admin Agent
- ErrandItem source attribution fields ready for API response model extension (Plan 02)
- Admin Agent instructions in Foundry portal need updating to mention the new tool (Plan 02 or separate task)
- Mobile ErrandRow source attribution display needed (Plan 03)

---
*Phase: 13-recipe-url-extraction*
*Completed: 2026-03-20*
