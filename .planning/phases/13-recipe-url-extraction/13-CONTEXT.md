# Phase 13: Recipe URL Extraction - Context

**Gathered:** 2026-03-04
**Updated:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

User types "admin" + a recipe URL into the text capture field. Classifier routes to Admin. Admin Agent fetches the page, extracts ingredients via LLM, and writes them to the appropriate store shopping lists with source attribution. This phase adds a new Admin Agent @tool for URL fetching/extraction and extends the shopping list data model for source tracking.

</domain>

<decisions>
## Implementation Decisions

### Page fetching
- Backend-side fetch via a new Admin Agent @tool (not mobile client) — tool handles Playwright launch, page load, and content extraction all in one
- Use headless browser (Playwright) inside the backend Docker container for JS-rendered pages
- 30-second page load timeout
- Block non-essential resources (images, CSS, fonts, media) during page load — only load HTML/JS needed for content
- Set realistic browser user-agent headers to improve success rate on sites that block scrapers; fail gracefully if still blocked
- Playwright added to the existing container image — no separate service

### Ingredient extraction strategy
- **Always run LLM** — even when JSON-LD Recipe schema is found in the page, pass through LLM to normalize format and handle store assignment in one step. Structured data can inform the LLM but is not used as a bypass.
- LLM extracts **recipe name + ingredients** together (recipe name used for source attribution)
- **Shopper-friendly format** — LLM normalizes ingredient text to what you'd look for in-store (e.g., "Diced tomatoes (14 oz can)" not "1 can (14 oz) diced tomatoes")
- Include quantities in ingredient names
- **Include all items** — no filtering of pantry staples (salt, pepper, oil, water). User removes what they already have.
- Allow duplicate items — if "milk" already exists on the list and the recipe also needs milk, add another entry with the recipe quantity

### Store assignment
- LLM assigns each ingredient to the appropriate store based on Admin Agent instructions
- Admin Agent instructions (or knowledge) will include store preferences (e.g., "don't buy meat from Jewel", "fish from the fishmarket")
- This is consistent with how the Admin Agent already assigns stores for non-recipe captures

### Source attribution UX
- Shopping list items from recipes include optional `sourceName` and `sourceUrl` fields (null for regular items)
- Data model: add optional `sourceName: str | None` and `sourceUrl: str | None` to ShoppingListItem
- Recipe items are **interspersed normally** in the shopping list — no special grouping or sections
- **Always-visible subtitle** under recipe items: "from: Chicken Tikka Masala" in subtle secondary text (muted gray, smaller font)
- Tapping the subtitle opens the source URL in the device browser
- Recipe items behave **exactly like regular items** when checked off — no special tracking or recipe completion indicator

### URL routing and classifier behavior
- **No classifier changes needed** — user types "admin" prefix + URL, classifier routes to Admin as usual
- **Bucket hint preferred**: user is expected to type the bucket (e.g., "admin https://..."). Future phases may handle URLs in other buckets (Ideas, etc.) but that's out of scope here.
- **Admin Agent always fetches URLs** — if the Admin Agent sees a URL in the input text, it always invokes the fetch tool. No domain-checking or keyword-matching to decide whether to fetch.
- **Not a recipe?** Just extract what it can. If ingredients are found, add them. If no recipe content found, report "No recipe found on this page." Don't try to process non-recipe content differently.

### Error handling
- **Fetch failure** (timeout, 404, blocked): Inbox item stays visible with an error status/message visible directly on the item (red indicator or error text) — not hidden behind a tap
- **Not a recipe** (page loads but no recipe content): Same pattern — inbox item stays with error "No recipe found on this page"
- **Partial extraction**: If only some ingredients are extracted, add what was found. Note partial results in the inbox item.
- **Success feedback**: Status screen shows a summary like "8 items added to 2 stores from Chicken Tikka Masala"
- **Retry**: User re-pastes the URL to retry. No retry button UI. No duplicate URL detection — just process again. Failed inbox items can be swiped away.
- **30-second timeout** for Playwright page loads

### Claude's Discretion
- Playwright configuration details (browser flags, specific resource types to block)
- JSON-LD parsing implementation details
- Exact LLM prompt for ingredient extraction and store assignment
- How much page content to send to the LLM (truncation strategy)
- Error message wording
- User-agent string choice

</decisions>

<specifics>
## Specific Ideas

- User types "admin" + URL into the existing text input field on the main capture screen — no new UI for URL input
- The flow is: type "admin https://recipe.com/..." → Classifier → Admin inbox item → open Status → Admin Agent processes → success summary shown → ingredients appear on shopping lists
- Store preferences will be in Admin Agent instructions (e.g., "I don't typically buy meat from Jewel and I get fish from a fishmarket")
- Headless browser chosen partly because future phases may need browser automation for other purposes (e.g., online ordering)
- Source attribution subtitle should feel informational, not prominent — muted gray, smaller than the item name

</specifics>

<deferred>
## Deferred Ideas

- **Automated online ordering** — User mentioned wanting Admin Agent to "order cat food from Chewy" via browser automation. Future phase that would build on the Playwright infrastructure added here.
- **YouTube recipe extraction** — Extract ingredients from YouTube video captions. Moved to backlog; can be added as an enhancement to this phase's URL pipeline later.
- **URL routing for other buckets** — URLs could be pasted for Ideas, notes, etc. in the future. Each bucket would need its own URL handling. Out of scope for Phase 13 which only handles Admin bucket URLs.
- **Smart classifier URL routing** — Teach classifier to auto-detect recipe URLs by domain and route to Admin without user typing "admin" prefix. Deferred — keep it simple with explicit bucket hint for now.

</deferred>

---

*Phase: 13-recipe-url-extraction*
*Context gathered: 2026-03-04*
*Context updated: 2026-03-06*
