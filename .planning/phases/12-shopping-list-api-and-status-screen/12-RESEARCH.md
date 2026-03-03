# Phase 12: Shopping List API and Status Screen - Research

**Researched:** 2026-03-02
**Domain:** FastAPI REST endpoints + React Native mobile tab with grouped list UI
**Confidence:** HIGH

## Summary

Phase 12 bridges the data layer (Cosmos DB ShoppingLists container, already created in Phase 10) to the user via two deliverables: (1) a FastAPI REST API for reading and deleting shopping list items, and (2) a new "Status & Priorities" tab in the Expo mobile app that displays items grouped by store with expand/collapse and swipe-to-delete.

The backend work is straightforward: two new endpoints (`GET /api/shopping-lists` and `DELETE /api/shopping-lists/items/{id}`) following the exact same patterns established in `inbox.py`. The key nuance is that the ShoppingLists container uses `/store` as its partition key (not `/userId` like all other containers), which affects query patterns and delete calls.

The mobile work involves adding a third tab to the existing Expo Router tab layout, building a SectionList-based grouped view with collapsible store sections, and implementing swipe-to-delete with optimistic UI. All required libraries are already installed (`react-native-gesture-handler` for Swipeable, `expo-router` for tabs, `react-native-safe-area-context`). No new dependencies are needed for either backend or mobile.

**Primary recommendation:** Build the API first (Plan 01), then the mobile Status screen (Plan 02). Use per-store queries (not cross-partition) on the backend to return pre-grouped data. Use React Native's built-in SectionList with a `Set<string>` for expand/collapse state on the mobile side.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MOBL-01 | Status & Priorities screen exists as a new tab in the app | Expo Router file-based tabs: add `status.tsx` to `app/(tabs)/` and register a `Tabs.Screen` in the tab layout. Pattern verified from existing `_layout.tsx` and Expo Router docs. |
| MOBL-02 | Status screen displays shopping lists grouped by store with item counts | SectionList with `renderSectionHeader` showing store name + count. API returns pre-grouped `{ stores: [{ store, items }] }` shape. |
| MOBL-03 | User can expand a store to see its items and tap to check off / swipe to remove | SectionList collapsible sections via `Set<string>` state + `extraData` prop. Swipeable from `react-native-gesture-handler` (same pattern as InboxItem). |
| SHOP-05 | User can swipe-to-remove items from shopping lists | `DELETE /api/shopping-lists/items/{id}` endpoint with store partition key. Mobile: optimistic removal from state, rollback on API failure. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | (existing) | REST API endpoints | Already used for all backend routes |
| Pydantic | (existing) | Request/response models | Already used for all API schemas |
| azure-cosmos async | (existing) | Cosmos DB queries and deletes | Already used for Inbox, Admin, etc. |
| React Native SectionList | built-in | Grouped list with section headers | Built into React Native, no install needed. Designed exactly for "data grouped by section" use case. |
| react-native-gesture-handler Swipeable | ~2.28.0 (installed) | Swipe-to-delete gesture | Already installed and used in InboxItem component |
| expo-router Tabs | ~6.0.23 (installed) | Tab navigation | Already installed and used for Capture/Inbox tabs |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| expo-haptics | ~15.0.8 (installed) | Haptic feedback on delete | Same pattern as InboxItem delete action |
| react-native-safe-area-context | ~5.6.0 (installed) | Safe area wrapping | Already used in all screens |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SectionList | FlatList with manual grouping | SectionList has built-in section headers, sticky headers, and `renderSectionHeader` -- FlatList would require custom logic to render group headers inline with items |
| Set<string> for expand state | LayoutAnimation | LayoutAnimation adds smooth open/close transitions but is unreliable on Android and adds complexity. Simple show/hide with `extraData` is sufficient for MVP. |
| Per-store queries | Cross-partition query | Per-store queries are more efficient (4 targeted partition reads vs 1 fan-out). With only 4 known stores, the overhead of 4 queries is negligible and avoids cross-partition RU cost. |

**Installation:**
No new packages needed. All dependencies are already installed.

## Architecture Patterns

### Recommended Project Structure
```
backend/
  src/second_brain/
    api/
      shopping_lists.py    # NEW: GET /api/shopping-lists, DELETE /api/shopping-lists/items/{id}
    models/
      documents.py         # EXISTING: ShoppingListItem model already defined

mobile/
  app/(tabs)/
    _layout.tsx            # MODIFY: Add third Tabs.Screen for "Status"
    status.tsx             # NEW: Status & Priorities screen
  components/
    ShoppingListItem.tsx   # NEW: Swipeable shopping list item row
```

### Pattern 1: Pre-Grouped API Response
**What:** The API returns shopping list data already grouped by store, so the mobile app does not need to do client-side grouping.
**When to use:** When the grouping key (store) is also the Cosmos DB partition key, making per-partition queries natural.
**Example:**
```python
# Response shape from GET /api/shopping-lists
{
    "stores": [
        {
            "store": "jewel",
            "displayName": "Jewel",
            "items": [
                {"id": "abc-123", "name": "milk", "store": "jewel"},
                {"id": "def-456", "name": "eggs", "store": "jewel"}
            ],
            "count": 2
        },
        {
            "store": "cvs",
            "displayName": "CVS",
            "items": [
                {"id": "ghi-789", "name": "bandages", "store": "cvs"}
            ],
            "count": 1
        }
    ],
    "totalCount": 3
}
```

### Pattern 2: Per-Store Cosmos Queries (NOT Cross-Partition)
**What:** Query each known store partition individually rather than using a cross-partition query.
**When to use:** When you have a small, fixed number of known partition key values.
**Why:** The ShoppingLists container has `/store` as partition key with only 4 known values (`jewel`, `cvs`, `pet_store`, `other`). Querying each partition individually is cheaper in RUs than a cross-partition fan-out, and the async Python SDK makes it easy to do these in parallel with `asyncio.gather`.
**Example:**
```python
# Source: Azure Cosmos DB Python SDK docs (async client)
from second_brain.models.documents import KNOWN_STORES

async def get_all_shopping_items(container) -> dict[str, list[dict]]:
    """Query each store partition individually."""
    results: dict[str, list[dict]] = {}
    for store in KNOWN_STORES:
        items = []
        async for item in container.query_items(
            query="SELECT * FROM c",
            partition_key=store,
        ):
            items.append(item)
        if items:
            results[store] = items
    return results
```

### Pattern 3: SectionList with Collapsible Sections
**What:** Use React Native SectionList with a `Set<string>` tracking expanded sections. Render section headers as Pressable, return `null` from `renderItem` when section is collapsed.
**When to use:** When displaying grouped data with expand/collapse behavior.
**Example:**
```typescript
// Source: React Native SectionList docs + community pattern
const [expandedStores, setExpandedStores] = useState<Set<string>>(new Set());

const toggleStore = (store: string) => {
  setExpandedStores((prev) => {
    const next = new Set(prev);
    if (next.has(store)) {
      next.delete(store);
    } else {
      next.add(store);
    }
    return next;
  });
};

<SectionList
  sections={sections}
  extraData={expandedStores}  // REQUIRED: triggers re-render on toggle
  keyExtractor={(item) => item.id}
  renderSectionHeader={({ section }) => (
    <Pressable onPress={() => toggleStore(section.store)}>
      <Text>{section.displayName} ({section.data.length})</Text>
      <Text>{expandedStores.has(section.store) ? "v" : ">"}</Text>
    </Pressable>
  )}
  renderItem={({ item, section }) => {
    if (!expandedStores.has(section.store)) return null;
    return <ShoppingListItemRow item={item} onDelete={handleDelete} />;
  }}
/>
```

### Pattern 4: Optimistic Delete with Rollback
**What:** Remove the item from local state immediately, then call the API. If the API fails, restore the item.
**When to use:** For delete operations where instant feedback matters more than guaranteed server confirmation.
**Example:**
```typescript
// Same pattern as existing InboxItem delete
const handleDeleteItem = useCallback((itemId: string, store: string) => {
  // Snapshot for rollback
  const previousData = storeData;

  // Optimistic removal
  setStoreData((prev) =>
    prev.map((section) =>
      section.store === store
        ? { ...section, data: section.data.filter((i) => i.id !== itemId) }
        : section
    ).filter((section) => section.data.length > 0)
  );

  // API call
  fetch(`${API_BASE_URL}/api/shopping-lists/items/${itemId}?store=${store}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${API_KEY}` },
  }).then((res) => {
    if (!res.ok && res.status !== 404) {
      // Rollback on failure
      setStoreData(previousData);
    }
  }).catch(() => {
    setStoreData(previousData);
  });
}, [storeData]);
```

### Pattern 5: Focus-Based Data Refresh
**What:** Use `useFocusEffect` from expo-router to refetch data when the tab gains focus.
**When to use:** When data may have changed while the user was on another tab (e.g., new items added via capture flow).
**Example:**
```typescript
// Source: Expo Router docs, already used in inbox.tsx
import { useFocusEffect } from "expo-router";

useFocusEffect(
  useCallback(() => {
    void fetchShoppingLists();
  }, [fetchShoppingLists])
);
```

### Anti-Patterns to Avoid
- **Cross-partition query for ShoppingLists:** With only 4 known stores, querying per-partition is cheaper and more predictable. Cross-partition fan-out wastes RUs on empty partitions.
- **Client-side grouping:** The API should return pre-grouped data. Making the mobile app sort/group a flat list wastes CPU on the device and creates a more complex data transform.
- **Using `partition_key="will"` for ShoppingLists:** Unlike all other containers (which use `/userId`), ShoppingLists uses `/store`. Using `"will"` as partition key will return zero results.
- **Adding a new library for accordion/collapsible:** SectionList + state is sufficient. No need for `react-native-collapsible` or `react-native-elements`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Grouped list with section headers | Custom FlatList with group logic | React Native SectionList | Built-in, handles section headers, sticky headers, key extraction, and virtualization |
| Swipe-to-delete gesture | Custom PanResponder gesture handling | `Swipeable` from `react-native-gesture-handler` | Already used in InboxItem, handles gesture physics, animation, and threshold detection |
| Tab navigation | Custom tab bar component | `Tabs` from `expo-router` | Already in use, file-based routing, handles focus events |
| Focus-based refresh | Manual navigation event listeners | `useFocusEffect` from `expo-router` | Already used in inbox.tsx, wraps React Navigation's focus lifecycle |
| Partition key routing | Custom query router | Cosmos SDK `partition_key` parameter | SDK handles partition routing natively -- just pass the store name |

**Key insight:** Every piece of infrastructure needed for Phase 12 already exists in the project. The InboxItem pattern (Swipeable, delete, optimistic UI) is directly reusable. The inbox.tsx pattern (useFocusEffect, fetch, FlatList/SectionList) is directly reusable. The API pattern from inbox.py is directly reusable. No new dependencies, no new patterns -- just applying existing patterns to a new data source and screen.

## Common Pitfalls

### Pitfall 1: Wrong Partition Key for ShoppingLists
**What goes wrong:** Using `partition_key="will"` (the pattern everywhere else in the codebase) when querying or deleting from the ShoppingLists container. Queries return empty results; deletes throw 404.
**Why it happens:** Every other Cosmos operation in the codebase uses `"will"` as the partition key. Muscle memory / pattern-matching leads to copy-pasting the wrong value.
**How to avoid:** The partition key for ShoppingLists is the store name (e.g., `"jewel"`, `"cvs"`). The `DELETE` endpoint must receive the store name to construct the correct delete call. Pass store as a query parameter: `DELETE /api/shopping-lists/items/{id}?store=jewel`.
**Warning signs:** API returns empty shopping lists despite items being present in Cosmos. Delete operations return 404 for items that clearly exist.

### Pitfall 2: SectionList Not Re-Rendering on Expand/Collapse
**What goes wrong:** Tapping a section header toggles the state, but items don't appear or disappear.
**Why it happens:** SectionList is a PureComponent. It only re-renders when `props` change (shallow comparison). The `sections` prop doesn't change when you toggle expand state -- only the `expandedStores` Set changes.
**How to avoid:** Pass `extraData={expandedStores}` to SectionList. This prop exists specifically to trigger re-renders when external state changes. Every SectionList with dynamic visibility MUST use `extraData`.
**Warning signs:** Console logs show state changing, but UI doesn't update.

### Pitfall 3: Stale Closures in Optimistic Delete Rollback
**What goes wrong:** Rollback restores stale data because the snapshot was captured from an old render.
**Why it happens:** JavaScript closures capture variables at creation time. If multiple deletes happen rapidly, each closure has a different snapshot.
**How to avoid:** Use the functional form of setState for the snapshot: `setStoreData((prev) => { /* save prev for rollback */ })`. Or refetch from API on failure instead of restoring a snapshot.
**Warning signs:** Deleting two items quickly, then one fails -- the rollback brings back both items instead of just the failed one. Simplest fix: refetch on failure instead of snapshot rollback.

### Pitfall 4: Empty Sections Showing in SectionList
**What goes wrong:** Stores with zero items still show a section header.
**Why it happens:** The API returns all known stores, even empty ones. Or: after deleting the last item in a store, the section remains with an empty data array.
**How to avoid:** Filter out stores with empty item arrays both in the API response (only return stores that have items) and in the optimistic delete logic (remove sections where `data.length === 0` after filtering).
**Warning signs:** "CVS (0)" section headers with no items underneath.

### Pitfall 5: Tab Order and File Naming
**What goes wrong:** The new Status tab appears in the wrong position (first instead of third).
**Why it happens:** Expo Router orders tabs based on the order of `Tabs.Screen` components in `_layout.tsx`, NOT alphabetical file order. If the Status screen is added before the existing screens, it becomes the default tab.
**How to avoid:** Add the `Tabs.Screen` for status AFTER index and inbox in the `_layout.tsx` file. The file name can be anything (`status.tsx`), but the `Tabs.Screen` order determines tab position.
**Warning signs:** App opens to the Status tab instead of Capture.

## Code Examples

Verified patterns from official sources and existing codebase:

### Backend: Shopping List API Router
```python
# Follows exact same pattern as backend/src/second_brain/api/inbox.py
# Source: Existing codebase pattern

import logging
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel
from second_brain.models.documents import KNOWN_STORES

logger = logging.getLogger(__name__)
router = APIRouter()

STORE_DISPLAY_NAMES: dict[str, str] = {
    "jewel": "Jewel",
    "cvs": "CVS",
    "pet_store": "Pet Store",
    "other": "Other",
}

class ShoppingItemResponse(BaseModel):
    id: str
    name: str
    store: str

class StoreSection(BaseModel):
    store: str
    displayName: str
    items: list[ShoppingItemResponse]
    count: int

class ShoppingListResponse(BaseModel):
    stores: list[StoreSection]
    totalCount: int

@router.get("/api/shopping-lists", response_model=ShoppingListResponse)
async def get_shopping_lists(request: Request) -> ShoppingListResponse:
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(status_code=503, detail="Cosmos DB not configured")

    container = cosmos_manager.get_container("ShoppingLists")
    stores: list[StoreSection] = []

    for store in KNOWN_STORES:
        items: list[ShoppingItemResponse] = []
        async for item in container.query_items(
            query="SELECT * FROM c",
            partition_key=store,
        ):
            items.append(ShoppingItemResponse(
                id=item["id"],
                name=item.get("name", ""),
                store=store,
            ))
        if items:
            stores.append(StoreSection(
                store=store,
                displayName=STORE_DISPLAY_NAMES.get(store, store.title()),
                items=items,
                count=len(items),
            ))

    total = sum(s.count for s in stores)
    return ShoppingListResponse(stores=stores, totalCount=total)


@router.delete("/api/shopping-lists/items/{item_id}", status_code=204)
async def delete_shopping_item(
    request: Request,
    item_id: str,
    store: str = Query(..., description="Store name (partition key)"),
) -> Response:
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(status_code=503, detail="Cosmos DB not configured")

    if store not in KNOWN_STORES:
        raise HTTPException(status_code=400, detail=f"Unknown store: {store}")

    container = cosmos_manager.get_container("ShoppingLists")
    try:
        await container.delete_item(item=item_id, partition_key=store)
    except CosmosResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Item not found") from exc

    logger.info("Deleted shopping item %s from store %s", item_id, store)
    return Response(status_code=204)
```

### Backend: Router Registration in main.py
```python
# Add to imports in main.py
from second_brain.api.shopping_lists import router as shopping_lists_router

# Add to router includes
app.include_router(shopping_lists_router)
```

### Mobile: Tab Layout Addition
```typescript
// In app/(tabs)/_layout.tsx -- add AFTER existing Tabs.Screen entries
<Tabs.Screen
  name="status"
  options={{
    title: "Status",
    tabBarIcon: ({ color }) => (
      <TabIcon label={"\uD83D\uDED2"} color={color} />
    ),
  }}
/>
```

### Mobile: SectionList Data Transform
```typescript
// Transform API response to SectionList format
interface ShoppingItem {
  id: string;
  name: string;
  store: string;
}

interface StoreSection {
  store: string;
  displayName: string;
  data: ShoppingItem[];
  count: number;
}

// API response maps directly to SectionList sections
// sections={storeData} where storeData: StoreSection[]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `enable_cross_partition_query=True` (sync SDK) | Async SDK does cross-partition by default (no flag needed) | azure-cosmos 4.x async | Async client queries across partitions automatically. But we use per-partition queries anyway for efficiency. |
| FlatList + manual section headers | SectionList (built-in) | React Native 0.59+ | SectionList has been stable for years. No changes needed. |
| Custom gesture handling | Swipeable from react-native-gesture-handler | Stable for 3+ years | Already used in InboxItem. react-native-gesture-handler v3 exists but v2.28 is fine for Expo SDK 54. |

**Deprecated/outdated:**
- `enable_cross_partition_query` parameter: Not needed in the async Cosmos SDK client. The async client automatically does cross-partition queries when no `partition_key` is specified. However, we deliberately use `partition_key=store` for per-partition queries, so this is moot.

## Open Questions

1. **Store display name mapping**
   - What we know: Stores are stored as lowercase slugs (`jewel`, `cvs`, `pet_store`, `other`)
   - What's unclear: Whether the user wants different display names (e.g., "Jewel-Osco" vs "Jewel")
   - Recommendation: Use a simple `STORE_DISPLAY_NAMES` dict in the API module. Easy to change later.

2. **Initial expand state**
   - What we know: Sections can start expanded or collapsed
   - What's unclear: Whether all sections should start expanded (showing all items) or collapsed (showing only store name + count)
   - Recommendation: Start all sections expanded. With a small number of stores and items, showing everything immediately is more useful than requiring taps to see content.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `backend/src/second_brain/api/inbox.py` -- API endpoint patterns, Cosmos query patterns, Pydantic response models
- Existing codebase: `mobile/app/(tabs)/inbox.tsx` -- useFocusEffect, fetch pattern, FlatList usage
- Existing codebase: `mobile/components/InboxItem.tsx` -- Swipeable component, optimistic delete pattern
- Existing codebase: `backend/src/second_brain/models/documents.py` -- ShoppingListItem model, KNOWN_STORES list
- Existing codebase: `backend/tests/test_admin_integration.py` -- Confirms ShoppingLists uses `/store` partition key with `partition_key=store` calls
- React Native SectionList docs: https://reactnative.dev/docs/sectionlist -- Section type, renderSectionHeader, extraData, stickySectionHeadersEnabled
- Expo Router tabs docs: https://docs.expo.dev/router/advanced/tabs/ -- Adding tabs via file + Tabs.Screen in _layout.tsx
- Azure Cosmos DB Python async SDK: https://github.com/azure/azure-sdk-for-python/blob/main/sdk/cosmos/azure-cosmos/README.md -- Cross-partition query behavior in async client, delete_item with partition_key

### Secondary (MEDIUM confidence)
- React Navigation useFocusEffect: https://reactnavigation.org/docs/use-focus-effect/ -- Focus lifecycle hook (used via expo-router re-export)
- SectionList expand/collapse pattern: https://gist.github.com/peterpme/b818eca2b7faf0e06f2466ab3e84db62 -- Community pattern using Set + extraData + renderItem null check
- Phase 10 RESEARCH.md: `.planning/phases/10-data-foundation-and-admin-tools/10-RESEARCH.md` -- ShoppingLists container design decisions, partition key rationale

### Tertiary (LOW confidence)
- None. All findings verified against primary sources or existing codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed and in use in the project. No new dependencies.
- Architecture: HIGH - All patterns are direct extensions of existing codebase patterns (inbox.py for API, inbox.tsx for mobile screen, InboxItem.tsx for swipeable rows).
- Pitfalls: HIGH - Partition key issue verified via test code and Phase 10 research. SectionList extraData issue is well-documented in official React Native docs.

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (30 days -- all components are stable, no fast-moving dependencies)
