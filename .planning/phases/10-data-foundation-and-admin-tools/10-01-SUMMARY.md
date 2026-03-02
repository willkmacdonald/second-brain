---
phase: 10-data-foundation-and-admin-tools
plan: 01
subsystem: database
tags: [cosmos-db, pydantic, shopping-list, admin-agent, tools]

# Dependency graph
requires: []
provides:
  - ShoppingListItem Pydantic model with id, store, name fields
  - KNOWN_STORES constant for store validation
  - ShoppingLists container reference in CosmosManager
  - AdminTools.add_shopping_list_items @tool for writing shopping items
  - Unit tests for AdminTools with mocked CosmosManager
affects: [10-02, 11-admin-agent-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AdminTools class follows ClassifierTools pattern for tool binding"
    - "ShoppingListItem uses plain BaseModel (not BaseDocument) for non-classified data"
    - "Partition key /store instead of /userId for shopping list items"

key-files:
  created:
    - backend/src/second_brain/tools/admin.py
    - backend/tests/test_admin_tools.py
  modified:
    - backend/src/second_brain/models/documents.py
    - backend/src/second_brain/db/cosmos.py

key-decisions:
  - "ShoppingListItem does not inherit BaseDocument -- no userId, timestamps, or classificationMeta needed"
  - "Tool parameter is list[dict] not list[ShoppingListItem] to avoid agent schema generation issues"
  - "Unknown stores silently fall back to 'other' without error"

patterns-established:
  - "AdminTools pattern: class-based tool binding with CosmosManager for admin operations"
  - "Non-classified data models use plain BaseModel, not BaseDocument"

requirements-completed: [SHOP-01, SHOP-02]

# Metrics
duration: 2min
completed: 2026-03-02
---

# Phase 10 Plan 01: Data Foundation Summary

**ShoppingListItem Pydantic model, KNOWN_STORES constant, CosmosManager ShoppingLists container, and AdminTools.add_shopping_list_items @tool with 6 unit tests**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-02T00:45:14Z
- **Completed:** 2026-03-02T00:47:18Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- ShoppingListItem model with id, store, name fields (no BaseDocument inheritance)
- KNOWN_STORES constant with jewel, cvs, pet_store, other
- AdminTools.add_shopping_list_items @tool writes individual documents to ShoppingLists container
- 6 unit tests covering happy path, unknown store fallback, empty names, case normalization

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ShoppingListItem model and extend CosmosManager** - `3f50c80` (feat)
2. **Task 2: Create AdminTools class with add_shopping_list_items @tool** - `53ac26a` (feat)
3. **Task 3: Unit tests for AdminTools and updated conftest** - `3c87948` (test)

## Files Created/Modified
- `backend/src/second_brain/models/documents.py` - Added KNOWN_STORES constant and ShoppingListItem model
- `backend/src/second_brain/db/cosmos.py` - Added "ShoppingLists" to CONTAINER_NAMES
- `backend/src/second_brain/tools/admin.py` - New AdminTools class with add_shopping_list_items @tool
- `backend/tests/test_admin_tools.py` - 6 unit tests for AdminTools

## Decisions Made
- ShoppingListItem does not inherit BaseDocument -- shopping items have no userId, timestamps, rawText, or classificationMeta
- Tool parameter is list[dict] (not list[ShoppingListItem]) to avoid agent schema generation issues with complex Pydantic models
- Unknown stores silently fall back to "other" without raising errors -- defensive for agent-generated inputs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required

The physical ShoppingLists container must be created in Azure Cosmos DB before deployment. Use `az cosmosdb sql container create` with partition key `/store`. This is the same pattern as the existing 5 containers.

## Next Phase Readiness
- ShoppingListItem model, KNOWN_STORES, and AdminTools are ready for Admin Agent wiring (Phase 10-02 and Phase 11)
- CosmosManager will automatically initialize the ShoppingLists container reference on startup
- No blockers

## Self-Check: PASSED

All 4 files verified present. All 3 task commits verified in git log.

---
*Phase: 10-data-foundation-and-admin-tools*
*Completed: 2026-03-02*
