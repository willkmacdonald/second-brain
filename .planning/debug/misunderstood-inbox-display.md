---
status: resolved
trigger: "Investigate why misunderstood inbox items (like 'Aardvark') show with broken display -- 'unknown' bucket, no confidence score, no agent chain"
created: 2026-02-23T12:00:00Z
updated: 2026-02-23T12:30:00Z
---

## Current Focus

hypothesis: confirmed -- 4 distinct issues identified
test: code trace through all 3 layers (backend tool, API, frontend components)
expecting: N/A -- investigation complete
next_action: none -- findings documented for fix planning

## Symptoms

expected: Misunderstood items should display meaningfully in the inbox list and detail card
actual: Items show "Unknown" bucket label, no confidence score, no agent chain, no bucket buttons in detail card, and badge count excludes them
errors: none (no crashes -- just incorrect/missing UI)
reproduction: Send "Aardvark" via capture -> agent calls request_misunderstood -> item appears in inbox with broken display
started: By design -- misunderstood status was added in Phase 04.3 but UI was not updated to handle it

## Eliminated

(none -- root causes confirmed on first pass)

## Evidence

- timestamp: 2026-02-23T12:05:00Z
  checked: backend/src/second_brain/tools/classification.py lines 145-187
  found: request_misunderstood creates InboxDocument with classificationMeta=None, status="misunderstood", title=None, filedRecordId=None, clarificationText=question_text. This is by design -- misunderstood items have no classification.
  implication: All downstream code must handle classificationMeta=None gracefully for misunderstood items

- timestamp: 2026-02-23T12:08:00Z
  checked: mobile/components/InboxItem.tsx lines 90-99 (bucket label logic)
  found: |
    The bucket label logic is:
    ```typescript
    const isPending = item.status === "pending" || item.status === "low_confidence" || item.status === "misunderstood";
    const isUnresolved = item.status === "unresolved";
    const bucketLabel = isPending
      ? "Pending"
      : isUnresolved
        ? "Unresolved"
        : item.classificationMeta?.bucket ?? "Unknown";
    ```
    The "misunderstood" status IS included in the isPending check, so the LIST VIEW actually shows "Pending" (not "Unknown") with an orange dot. The "Unknown" display is in the DETAIL CARD, not the list.
  implication: The list item display for misunderstood items is partially correct (shows "Pending" with orange dot) but misleading -- "Pending" is not the right label for a misunderstood item. It should say "Needs Clarification" or "Misunderstood".

- timestamp: 2026-02-23T12:10:00Z
  checked: mobile/app/(tabs)/inbox.tsx lines 286-302 (detail card bucket/confidence/agentChain)
  found: |
    Detail card always shows:
    - Bucket: `selectedItem?.classificationMeta?.bucket ?? "Unknown"` -> shows "Unknown" for misunderstood
    - Confidence: `selectedItem?.classificationMeta?.confidence != null ? ... : "N/A"` -> shows "N/A"
    - Agent Chain: `selectedItem?.classificationMeta?.agentChain?.join(" -> ") ?? "N/A"` -> shows "N/A"
    These are correct fallbacks but the detail card has no special handling for misunderstood items.
  implication: The detail card treats misunderstood items as if they're regular items with missing data, rather than showing contextually appropriate content (e.g., the clarification question, a "this item needs more context" message).

- timestamp: 2026-02-23T12:12:00Z
  checked: mobile/app/(tabs)/inbox.tsx lines 313-318 (bucket buttons visibility)
  found: |
    ```typescript
    const isPendingItem = selectedItem?.status === "pending" || selectedItem?.status === "low_confidence";
    const isClassifiedItem = selectedItem?.status === "classified";
    const showBucketButtons = isPendingItem || isClassifiedItem;
    ```
    "misunderstood" is NOT included in isPendingItem or isClassifiedItem, so showBucketButtons is false. No bucket buttons appear for misunderstood items.
  implication: Misunderstood items have NO resolution path from the detail card. User cannot file them to a bucket. They are "dangling" with no way to resolve.

- timestamp: 2026-02-23T12:15:00Z
  checked: mobile/app/(tabs)/inbox.tsx lines 79-86 (badge count logic)
  found: |
    ```typescript
    const isPendingStatus = (s: string) =>
      s === "pending" || s === "low_confidence" || s === "unresolved";
    const pendingCount = items.filter((i) => isPendingStatus(i.status)).length;
    ```
    "misunderstood" is NOT in isPendingStatus. Badge count does NOT include misunderstood items.
  implication: Misunderstood items needing attention are invisible in the badge count. User has no notification that they exist.

- timestamp: 2026-02-23T12:18:00Z
  checked: mobile/app/(tabs)/inbox.tsx lines 163-165 (recategorize optimistic update)
  found: |
    ```typescript
    classificationMeta: i.classificationMeta
      ? { ...i.classificationMeta, bucket: newBucket }
      : null,
    ```
    If classificationMeta is null (misunderstood items), recategorize keeps it null even after a bucket change. But this path is unreachable because bucket buttons don't appear for misunderstood items.
  implication: Even if bucket buttons were shown, the optimistic update would leave classificationMeta as null.

- timestamp: 2026-02-23T12:20:00Z
  checked: mobile/app/(tabs)/inbox.tsx lines 197-209 (handlePendingResolve)
  found: |
    handlePendingResolve creates classificationMeta when it was null:
    ```typescript
    : { bucket, confidence: 0.85, agentChain: ["User"] },
    ```
    This is the correct resolution path -- it calls sendClarification which goes to the backend. But since "misunderstood" is not in isPendingItem, the bucket buttons (and thus this handler) are never reachable.
  implication: The fix mechanism exists (handlePendingResolve creates classificationMeta from scratch) but the UI gate prevents it from being used for misunderstood items.

- timestamp: 2026-02-23T12:22:00Z
  checked: backend/src/second_brain/api/inbox.py lines 191-288 (recategorize endpoint)
  found: |
    recategorize_inbox_item builds fresh ClassificationMeta from old_meta fields. For misunderstood items where classificationMeta is None, old_meta will be {} so it would get: confidence=0.0, allScores={}, agentChain=["User"]. This would work but creates somewhat empty metadata.
  implication: Backend can handle recategorization of misunderstood items, just with minimal metadata. This is acceptable.

- timestamp: 2026-02-23T12:24:00Z
  checked: InboxDocument model (backend/src/second_brain/models/documents.py line 49)
  found: InboxDocument has clarificationText field that stores the agent's question. This field IS passed through the API (inbox.py line 40, line 93). The frontend InboxItemData type (InboxItem.tsx line 11) includes clarificationText as optional.
  implication: The clarification question text IS available on the frontend for misunderstood items. The detail card could display it but currently does not.

## Resolution

root_cause: |
  4 distinct issues, all stemming from the "misunderstood" status being added to the backend (Phase 04.3) without corresponding UI updates in the inbox components:

  **Issue 1: Badge count excludes misunderstood items**
  File: mobile/app/(tabs)/inbox.tsx line 80-81
  The isPendingStatus function checks for "pending", "low_confidence", and "unresolved" but NOT "misunderstood". Misunderstood items needing user attention are invisible in the badge.

  **Issue 2: Detail card shows "Unknown" bucket instead of meaningful content**
  File: mobile/app/(tabs)/inbox.tsx lines 286-302
  The detail card has no conditional rendering for misunderstood items. It shows generic fallbacks ("Unknown" bucket, "N/A" confidence/agent chain) instead of showing the clarification question text or a "needs more context" message.

  **Issue 3: No bucket buttons for misunderstood items (no resolution path)**
  File: mobile/app/(tabs)/inbox.tsx lines 314-316
  The showBucketButtons logic only includes "pending", "low_confidence", and "classified" statuses. "misunderstood" is excluded, so there are no bucket buttons and no way to manually resolve these items from the inbox.

  **Issue 4: List label says "Pending" instead of something misunderstood-specific**
  File: mobile/components/InboxItem.tsx line 93
  The isPending check includes "misunderstood" alongside "pending" and "low_confidence", so misunderstood items show "Pending" in the list. While this gives them an orange dot (correct), the label is misleading. A label like "Needs Clarification" would be more appropriate.

fix: not applied (diagnosis only mode)
verification: not applicable
files_changed: []

suggested_fixes:
  - file: mobile/app/(tabs)/inbox.tsx
    line: 80-81
    change: Add "misunderstood" to isPendingStatus function
    code: |
      const isPendingStatus = (s: string) =>
        s === "pending" || s === "low_confidence" || s === "unresolved" || s === "misunderstood";

  - file: mobile/app/(tabs)/inbox.tsx
    line: 314-316
    change: Add "misunderstood" to isPendingItem so bucket buttons appear
    code: |
      const isPendingItem =
        selectedItem?.status === "pending" ||
        selectedItem?.status === "low_confidence" ||
        selectedItem?.status === "misunderstood";

  - file: mobile/app/(tabs)/inbox.tsx
    line: 286-302
    change: Add conditional rendering for misunderstood items showing clarificationText and hiding meaningless bucket/confidence/agentChain fields
    description: |
      When selectedItem?.status === "misunderstood", show:
      - The clarificationText as an "Agent asked" section
      - Hide or replace the Bucket/Confidence/Agent Chain fields
      - Show bucket buttons labeled "File to bucket" (same as pending)

  - file: mobile/components/InboxItem.tsx
    line: 93-99
    change: Show a distinct label for misunderstood items instead of generic "Pending"
    code: |
      const isMisunderstood = item.status === "misunderstood";
      const isPending = item.status === "pending" || item.status === "low_confidence" || isMisunderstood;
      const bucketLabel = isMisunderstood
        ? "Needs Clarification"
        : isPending
          ? "Pending"
          : isUnresolved
            ? "Unresolved"
            : item.classificationMeta?.bucket ?? "Unknown";
