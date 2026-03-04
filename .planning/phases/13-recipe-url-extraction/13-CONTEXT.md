# Phase 13: Recipe URL Extraction - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

User pastes any recipe webpage URL into the text capture field. Classifier routes it as Admin. Admin Agent fetches the page, extracts ingredients, and writes them to the appropriate store shopping lists with source attribution. This phase adds a new Admin Agent @tool for URL fetching/parsing and extends the shopping list data model for source tracking.

</domain>

<decisions>
## Implementation Decisions

### Page fetching
- Backend-side fetch via a new Admin Agent @tool (not mobile client)
- Use headless browser (Playwright) inside the backend Docker container for JS-rendered pages
- Sensible defaults: ~30-second page load timeout, extract text content only (strip images/ads/scripts)
- Playwright added to the existing container image — no separate service

### Ingredient extraction strategy
- **Structured data first**: Check for JSON-LD Recipe schema (`@type: Recipe`) in the page. Most recipe sites include this. Parse ingredients directly from structured data.
- **LLM fallback**: If no structured data found, send page text content to the LLM for ingredient extraction
- Include quantities in ingredient names (e.g., "2 cups flour", "1 lb chicken breast")
- Allow duplicate items — if "milk" already exists on the list and the recipe also needs milk, add another entry with the recipe quantity

### Store assignment
- LLM assigns each ingredient to the appropriate store based on Admin Agent instructions
- Admin Agent instructions (or knowledge) will include store preferences (e.g., "don't buy meat from Jewel", "fish from the fishmarket")
- This is consistent with how the Admin Agent already assigns stores for non-recipe captures

### Source attribution
- Shopping list items from recipes include optional `sourceName` and `sourceUrl` fields (null for regular items)
- Mobile UI shows a subtitle under recipe items: "from: Chicken Tikka Masala"
- Tapping the subtitle opens the source URL in the device browser
- Data model: add optional `sourceName: str | None` and `sourceUrl: str | None` to ShoppingListItem

### Error handling
- **Fetch failure** (timeout, 404, blocked): Inbox item stays visible with an error status/message ("Could not fetch page"). User sees it when they open Status.
- **Not a recipe** (page loads but no recipe content): Same pattern — inbox item stays with error "No recipe found on this page"
- **Retry**: User re-pastes the URL to retry. No retry button UI. Failed inbox items can be swiped away.
- **URL detection**: Classifier handles it — no separate URL validation. If the Classifier classifies a URL as Admin, the Admin Agent processes it.

### Claude's Discretion
- Playwright configuration details (browser flags, resource blocking)
- JSON-LD parsing implementation
- Exact LLM prompt for ingredient extraction
- How much page content to send to the LLM (truncation strategy)
- Error message wording

</decisions>

<specifics>
## Specific Ideas

- User expects to paste URLs into the existing text input field on the main capture screen — no new UI for URL input
- The flow is: paste URL → Classifier → Admin inbox item → open Status → Admin Agent processes → ingredients appear on shopping lists
- Store preferences will be in Admin Agent instructions (e.g., "I don't typically buy meat from Jewel and I get fish from a fishmarket")
- Headless browser chosen partly because future phases may need browser automation for other purposes (e.g., online ordering)

</specifics>

<deferred>
## Deferred Ideas

- **Automated online ordering** — User mentioned wanting Admin Agent to "order cat food from Chewy" via browser automation. Future phase that would build on the Playwright infrastructure added here.
- **YouTube recipe extraction** — Extract ingredients from YouTube video captions. Moved to backlog; can be added as an enhancement to this phase's URL pipeline later.

</deferred>

---

*Phase: 13-recipe-url-extraction*
*Context gathered: 2026-03-04*
