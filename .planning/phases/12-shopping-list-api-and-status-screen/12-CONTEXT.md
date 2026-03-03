# Phase 12: Shopping List API and Status Screen - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can view their shopping lists grouped by store and remove items they've purchased. This is delivered via a new "Status" tab in the mobile app and REST API endpoints for fetching and deleting shopping list items. The Status tab will eventually host other categories (Ideas, Projects, People) in future phases — Phase 12 only builds shopping list sections but the screen structure must be extensible.

</domain>

<decisions>
## Implementation Decisions

### Store sections & item display
- Each item row shows the full name string (name and quantity are stored as a single field, not separate)
- Stores ordered by most items first (descending item count)
- All sections start **collapsed** by default — user taps to expand
- Section header shows: store display name + item count only (e.g., "Jewel-Osco (5)")
- Use friendly display names: "jewel" → "Jewel-Osco", etc.

### Delete interaction
- Swipe-to-delete with **no confirmation step** — tap delete button, item gone
- **No haptic feedback** on delete
- When last item in a store is deleted, the **section disappears** entirely
- On API failure: **silent rollback** — item reappears in the list, no error message shown

### Screen layout & navigation
- Tab label: **"Status"** with an icon representing action/working (not a shopping cart)
- **No screen header/title** — sections start at the top of the screen
- Empty state: **"No items yet"** — simple centered message
- Phase 12 shows shopping list sections only — no placeholders for future categories

### Data freshness
- Refresh **on tab focus only** (useFocusEffect pattern, same as Inbox)
- No pull-to-refresh, no background polling
- **Spinner** while loading (not skeleton placeholders)
- On fetch error: **show stale data** if available, silently retry next focus

### Screen extensibility
- **Flat hierarchy**: each store is a top-level section (not nested under a "Shopping" parent). Future categories (Ideas, Projects, People) will be peers at the same level
- Build as a **generic section renderer** from the start — not a focused shopping-list-only screen
- **Same row style** for all section types (uniform text rows)
- **Configurable actions per section type** — shopping sections get swipe-to-delete, future section types can define different swipe actions

### Claude's Discretion
- Exact icon choice for the Status tab (should convey "action" or "working")
- Section renderer abstraction design (interfaces, props shape)
- Item sorting within an expanded store section
- Spinner placement and style

</decisions>

<specifics>
## Specific Ideas

- The Status tab is the future home for Admin, Ideas, Projects, and People — not just shopping. The collapsed-by-default + flat hierarchy decisions are made with that future in mind.
- "Jewel-Osco" not "Jewel" for display names. Store display name mapping lives in a backend dict for now, eventually managed through Admin with location/URL metadata (future phase).
- ~20 stores expected (many online), not just the initial 4.

</specifics>

<deferred>
## Deferred Ideas

- Store metadata (physical location or URL per store) — managed through Admin in a future phase
- Ideas, Projects, People sections on the Status screen — future phases
- Store display name management through Admin UI — future phase

</deferred>

---

*Phase: 12-shopping-list-api-and-status-screen*
*Context gathered: 2026-03-02*
