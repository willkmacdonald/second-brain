---
status: diagnosed
trigger: "HITL resolution from conversation screen fails - item remains pending after filing. Duplicate key React error. Suspicion of still hitting localhost."
created: 2026-02-23T00:00:00Z
updated: 2026-02-23T00:01:00Z
symptoms_prefilled: true
goal: find_root_cause_only
---

## Current Focus

hypothesis: CONFIRMED -- useCallback closure bug causes inboxItemId to always be null
test: traced data flow from conversation screen through sendClarification to respond endpoint
expecting: respond endpoint skips DB update when inbox_item_id is None
next_action: return diagnosis

## Symptoms

expected: After selecting a bucket on conversation screen, item should be filed and no longer show as pending in inbox
actual: Item remains pending (orange dot) after filing. React error "encountered two children with the same key". Local items appearing in deployed environment.
errors: React error "encountered two children with the same key"
reproduction: Open inbox, tap pending item, select bucket, navigate back - item still pending
started: After Phase 04 deployment

## Eliminated

- hypothesis: Mobile app is hitting localhost:8003 instead of deployed backend
  evidence: mobile/.env has EXPO_PUBLIC_API_URL=https://brain.willmacdonald.com; curl to that URL returns 401 (reachable, auth-gated). The "local items in deployed env" observation is because backend/.env uses the SAME Cosmos DB endpoint (shared-services-cosmosdb.documents.azure.com) for both local and deployed -- they share one database.
  timestamp: 2026-02-23T00:00:30Z

- hypothesis: Respond endpoint Cosmos upsert operation fails silently
  evidence: While the exception handler (main.py:414-418) DOES swallow errors and emit a fake success response, the actual root cause is earlier -- the inbox_item_id is never sent in the first place, so the entire DB block is skipped by the guard condition on line 351.
  timestamp: 2026-02-23T00:00:45Z

## Evidence

- timestamp: 2026-02-23T00:00:10Z
  checked: mobile/.env and constants/config.ts
  found: EXPO_PUBLIC_API_URL=https://brain.willmacdonald.com, fallback is localhost:8003
  implication: Mobile IS pointing to deployed backend. Not an environment config issue.

- timestamp: 2026-02-23T00:00:15Z
  checked: backend/.env COSMOS_ENDPOINT vs deployed environment
  found: Both local and deployed use COSMOS_ENDPOINT=https://shared-services-cosmosdb.documents.azure.com:443/
  implication: Local items appearing in "deployed" env is expected -- same database. Not a bug.

- timestamp: 2026-02-23T00:00:20Z
  checked: conversation/[threadId].tsx handleBucketSelect useCallback (lines 61-99)
  found: useCallback dependency array is [threadId, isResolving] but the callback closure references `item?.id` (line 71). `item` is NOT in the dependency array.
  implication: When component mounts, item=null. useCallback memoizes the function. When item loads, isResolving hasn't changed (still false), so React returns the stale memoized function. item?.id evaluates to undefined.

- timestamp: 2026-02-23T00:00:25Z
  checked: ag-ui-client.ts sendClarification (lines 156-181)
  found: Sends JSON body with inbox_item_id: inboxItemId. When inboxItemId is undefined, JSON.stringify serializes it as missing/null.
  implication: Backend receives inbox_item_id=None in the RespondRequest.

- timestamp: 2026-02-23T00:00:30Z
  checked: main.py respond_to_hitl endpoint (lines 329-452)
  found: Line 351 has guard `if body.inbox_item_id and cosmos_manager:` -- when inbox_item_id is None, the ENTIRE Cosmos DB block (read existing, create bucket doc, upsert inbox) is SKIPPED. Lines 421-427 still emit "Filed -> Bucket (0.85)" success text. Line 442 emits RunFinishedEvent. Client receives success.
  implication: No DB write ever happens. Inbox document status stays "pending". Client navigates back thinking it succeeded.

- timestamp: 2026-02-23T00:00:35Z
  checked: main.py respond_to_hitl exception handling (lines 414-418)
  found: Bare `except Exception` catches all errors, logs a warning, and continues to emit success text. Even if inbox_item_id WERE provided, any Cosmos error would be swallowed.
  implication: Secondary issue -- error handling masks failures. The endpoint always claims success.

- timestamp: 2026-02-23T00:00:40Z
  checked: inbox.tsx FlatList keyExtractor (line 103) and handleLoadMore append logic (lines 46-48)
  found: keyExtractor uses item.id. Duplicate key error would require items with same id in the list. Most likely cause: offset pagination shift when new items are inserted between page fetches, causing overlapping items in appended results.
  implication: Duplicate key is a secondary issue from pagination, not related to the filing bug.

- timestamp: 2026-02-23T00:00:45Z
  checked: inbox.tsx -- no useFocusEffect or auto-refetch on navigation back
  found: fetchInbox only runs in useEffect([], []) on mount. No refetch on screen focus.
  implication: Even if filing DID work, the inbox list would show stale data until pull-to-refresh. Minor UX issue.

## Resolution

root_cause: |
  PRIMARY: useCallback closure bug in mobile/app/conversation/[threadId].tsx (line 61-99).

  The handleBucketSelect callback has dependency array [threadId, isResolving] but references
  `item?.id` from the component's state. Since `item` is NOT in the dependency array, the
  callback captures the initial value of item (null) and never updates when item loads.
  This means inboxItemId is always undefined/null when sent to the backend.

  The backend respond endpoint (main.py:351) guards the entire DB operation block with
  `if body.inbox_item_id and cosmos_manager:` -- when inbox_item_id is None, ALL Cosmos
  writes are skipped. But the endpoint still emits a "Filed -> Bucket (0.85)" success
  message, so the client thinks filing succeeded and navigates back.

  SECONDARY ISSUES:
  1. Backend respond endpoint swallows all exceptions (main.py:414-418) and always claims
     success, even if Cosmos operations fail.
  2. Inbox screen has no auto-refetch on focus/navigation-back, so even successful updates
     wouldn't be visible without pull-to-refresh.
  3. Duplicate key React error likely from pagination offset shift during load-more.
  4. "Local items in deployed env" is expected -- shared Cosmos DB instance.

fix:
verification:
files_changed: []
