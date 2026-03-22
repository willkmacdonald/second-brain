---
phase: 13-recipe-url-extraction
verified: 2026-03-22T20:00:00Z
status: passed
score: 4/4 success criteria verified
---

# Phase 13: Recipe URL Extraction Verification Report

**Phase Goal:** Users can paste any recipe webpage URL, the Admin Agent fetches the page, the LLM extracts ingredients, and adds them to the shopping list with source attribution
**Verified:** 2026-03-22T20:00:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths (from Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User pastes a recipe URL, it gets classified as Admin, and the Admin Agent extracts ingredients from the page content | VERIFIED | `recipe.py` (285 lines) implements three-tier fetch (Jina Reader, httpx, Playwright). `main.py:269` appends `fetch_recipe_url` to `admin_agent_tools`. `admin_handoff.py:235-283` retries when agent calls intermediate tools without output tools. UAT in 13-03-SUMMARY confirmed end-to-end with 15 ingredients extracted from Chicken Tikka Masala. |
| 2 | Extracted ingredients appear on the appropriate store shopping lists as individual items | VERIFIED | `admin.py:168-174` creates `ErrandItem` with `sourceName`/`sourceUrl` from item dicts. `errands.py:111-120` and `141-148` pass `sourceName`/`sourceUrl` through from Cosmos docs to API response via `ErrandItemResponse`. UAT confirmed items routed to correct destinations (Agora for meat, Jewel-Osco for others). |
| 3 | Shopping list items from recipes show source attribution (recipe name and/or URL) | VERIFIED | `ErrandRow.tsx:60-65` renders "from: {item.sourceName}" in muted gray (fontSize 12, color #888888). `Pressable` wraps the text; `onPress` calls `Linking.openURL(item.sourceUrl)`. `status.tsx:23-24` includes `sourceName?`/`sourceUrl?` in `ErrandItem` interface. TypeScript compiles. |
| 4 | When URL cannot be fetched or contains no recognizable recipe, the system fails gracefully with a clear message | VERIFIED | `recipe.py:147-151` returns error strings on empty content. `admin_handoff.py:108-110` delivery heuristic surfaces "items added", "no recipe found", "error fetching" as admin notifications. `admin_handoff.py:235-283` retry mechanism prevents silent data loss. `_count_output_tool_invocations` (lines 51-64) ensures inbox items are not deleted when only intermediate tools run. UAT confirmed classifier gates non-recipe URLs via confidence scoring. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/second_brain/tools/recipe.py` | RecipeTools class with fetch_recipe_url tool | VERIFIED | 285 lines. Three-tier fetch (Jina, httpx, Playwright). SSRF protection via `_is_safe_url`. JSON-LD extraction via `_extract_json_ld_recipe`. URL normalization for Substack. |
| `backend/Dockerfile` | Playwright + Chromium system deps and browser binary | VERIFIED | System deps installed (lines 30-36), PLAYWRIGHT_BROWSERS_PATH set (line 48), `playwright install chromium` runs as app user (line 56). |
| `backend/tests/test_recipe_tools.py` | Unit tests for RecipeTools | VERIFIED | 235 lines. 7 tests for `_extract_json_ld_recipe` (direct, @graph, list, no scripts, non-Recipe, malformed, multiple scripts). 7 tests for `fetch_recipe_url` (success, JSON-LD, failure, context cleanup x2, empty page, truncation). |
| `backend/src/second_brain/models/documents.py` | ErrandItem with sourceName/sourceUrl fields | VERIFIED | Lines 104-105: `sourceName: str \| None = None` and `sourceUrl: str \| None = None`. |
| `backend/src/second_brain/tools/admin.py` | add_errand_items passes sourceName/sourceUrl | VERIFIED | Lines 166-174: extracts `source_name`/`source_url` from item_data, passes to ErrandItem constructor. Field description updated (lines 128-136). |
| `backend/src/second_brain/main.py` | Playwright lifecycle + RecipeTools registration | VERIFIED | Lines 253-283: Playwright started in lifespan, RecipeTools created, `fetch_recipe_url` appended to admin_agent_tools. Lines 333-336: cleanup closes browser and stops Playwright. |
| `backend/src/second_brain/api/errands.py` | ErrandItemResponse with sourceName/sourceUrl | VERIFIED | Lines 37-38: optional fields. Lines 117-118 and 146-147: both construction sites pass through from Cosmos docs. |
| `backend/src/second_brain/processing/admin_handoff.py` | Delivery heuristic + retry mechanism | VERIFIED | Lines 108-110: recipe indicators. Lines 42-64: output tool counting. Lines 235-283: retry with nudge prompt. |
| `mobile/components/ErrandRow.tsx` | Source attribution subtitle with tappable URL | VERIFIED | Lines 60-65: conditional Pressable with "from: {item.sourceName}". Line 2: Linking and Pressable imported. Lines 85-88: sourceText style (fontSize 12, color #888888). |
| `mobile/app/(tabs)/status.tsx` | ErrandItem interface with source fields | VERIFIED | Lines 23-24: `sourceName?: string` and `sourceUrl?: string`. |
| `backend/pyproject.toml` | playwright, beautifulsoup4, lxml dependencies | VERIFIED | Lines 30-32 contain all three. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `main.py` | `tools/recipe.py` | Playwright lifecycle + RecipeTools instantiation | WIRED | Line 49: `from playwright.async_api import async_playwright`. Line 53: `from second_brain.tools.recipe import RecipeTools`. Lines 254-268: browser launched, RecipeTools created. |
| `main.py` | `admin_agent_tools` | fetch_recipe_url appended | WIRED | Line 269: `app.state.admin_agent_tools.append(recipe_tools.fetch_recipe_url)` |
| `admin.py` | `documents.py` | ErrandItem with sourceName/sourceUrl | WIRED | Lines 166-174: `source_name = item_data.get("sourceName")`, passed to `ErrandItem(sourceName=source_name, sourceUrl=source_url)` |
| `errands.py` | `documents.py` | ErrandItemResponse maps source fields | WIRED | Lines 117-118 and 146-147: `sourceName=item.get("sourceName"), sourceUrl=item.get("sourceUrl")` |
| `ErrandRow.tsx` | `Linking.openURL` | Pressable onPress opens URL | WIRED | Line 62: `onPress={() => item.sourceUrl && Linking.openURL(item.sourceUrl)}` |
| `admin_handoff.py` | `recipe.py` | Retry when intermediate tool runs without output | WIRED | Lines 42-48: `_OUTPUT_TOOL_NAMES` excludes `fetch_recipe_url`. Lines 235-283: retry with nudge prompt when only intermediate tools called. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RCPE-01 | 13-01, 13-03 | User can paste any recipe webpage URL that gets classified as Admin, and Admin Agent extracts recipe ingredients from the page | SATISFIED | `fetch_recipe_url` tool with three-tier fetch, wired to admin agent tools, Foundry instructions updated (UAT confirmed). |
| RCPE-02 | 13-01, 13-02, 13-03 | Extracted ingredients are added to the appropriate grocery store shopping list | SATISFIED | `add_errand_items` passes sourceName/sourceUrl through. ErrandItemResponse returns fields. UAT confirmed 15 ingredients routed to correct destinations. |
| RCPE-03 | 13-01, 13-02, 13-03 | Shopping list items from recipes show source attribution (recipe name/URL) | SATISFIED | ErrandRow renders "from: Recipe Name" subtitle, Pressable opens URL in browser. API response includes source fields. |

No orphaned requirements found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | - | - | - | No anti-patterns detected across all 11 phase artifacts. No TODOs, FIXMEs, placeholders, empty implementations, or console.log-only handlers found. |

### Human Verification Required

### 1. Source Attribution Visual Appearance

**Test:** Open the Status screen with recipe-sourced errand items present.
**Expected:** "from: Recipe Name" appears below each recipe item in muted gray text (smaller than item name). Non-recipe items have no subtitle.
**Why human:** Visual styling (font size, color, spacing) cannot be verified programmatically.

### 2. Tap-to-Open Source URL

**Test:** Tap the "from: Recipe Name" subtitle on a recipe-sourced item.
**Expected:** The device browser opens with the recipe URL.
**Why human:** Device browser launch requires physical device interaction.

### 3. Recipe URL End-to-End Flow

**Test:** Paste a recipe URL as a capture, wait for processing, check Status screen.
**Expected:** Ingredients from the recipe appear on the correct destination shopping lists with source attribution.
**Why human:** Requires deployed backend, Foundry agent, and mobile app working together.

**Note:** 13-03-SUMMARY reports all three human verification items were tested during UAT (2026-03-20 to 2026-03-22) and passed. The results include successful extraction of 15 ingredients from Chicken Tikka Masala with correct routing and source attribution.

### Gaps Summary

No gaps found. All four success criteria are verified in the codebase:

1. **URL fetching infrastructure** is complete with a robust three-tier fetch strategy (Jina Reader, httpx, Playwright), SSRF protection, and URL normalization.
2. **Ingredient persistence** flows correctly from Admin Agent tool calls through ErrandItem model to Cosmos DB, with source attribution fields carried through the entire chain.
3. **Source attribution UI** is implemented in ErrandRow with conditional rendering, muted gray styling, and tappable URLs via Linking.openURL.
4. **Error handling** includes delivery heuristic detection of error messages, retry mechanism for intermediate-only tool invocations, and output tool counting to prevent silent data loss.

All six commits referenced in summaries are verified present in git history. All 11 artifacts pass three-level verification (exists, substantive, wired). No anti-patterns detected.

---

_Verified: 2026-03-22T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
