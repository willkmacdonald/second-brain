---
phase: 20-feedback-collection
type: code-review
depth: standard
status: issues_found
files_reviewed: 8
findings: 5
critical: 0
high: 1
medium: 2
low: 2
files_reviewed_list:
  - backend/src/second_brain/api/errands.py
  - backend/src/second_brain/api/feedback.py
  - backend/src/second_brain/api/inbox.py
  - backend/src/second_brain/main.py
  - backend/src/second_brain/tools/investigation.py
  - backend/tests/test_feedback.py
  - mobile/app/(tabs)/inbox.tsx
  - mobile/components/InboxItem.tsx
---

# Phase 20: Code Review Report

**Reviewed:** 2026-04-22T14:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 20 adds feedback signal collection infrastructure across three layers: a backend POST /api/feedback endpoint for explicit thumbs up/down, inline fire-and-forget FeedbackDocument writes in the recategorize and errand re-route handlers, two new investigation agent tools (query_feedback_signals and promote_to_golden_dataset), and thumbs up/down UI buttons in the mobile inbox detail modal.

The implementation is well-structured and follows existing project patterns consistently. Fire-and-forget signal writes are correctly wrapped in try/except to avoid blocking primary user actions. The investigation tools follow the established class-based tool pattern with proper error handling. Test coverage is thorough with 16 test cases covering happy paths, error paths, and the non-fatal guarantee.

No critical issues found. One high-severity warning about the feedback endpoint not handling Cosmos write failures gracefully (returns a 500 instead of a meaningful error). Two medium-severity items on minor logic/UX concerns. Two low-severity info items.

## Warnings

### WR-01: Unhandled Cosmos exception in POST /api/feedback returns raw 500

**File:** `backend/src/second_brain/api/feedback.py:49-50`
**Issue:** The `submit_feedback` endpoint validates inputs and checks for `cosmos_manager`, but the `container.create_item()` call on line 50 is not wrapped in a try/except. If Cosmos DB returns a transient error (throttling, timeout, network error), the unhandled exception propagates to FastAPI's default handler, returning a generic 500 with no meaningful detail. This contrasts with the inline signal writes in inbox.py and errands.py, which are wrapped in try/except because they are fire-and-forget. Here, the POST /api/feedback endpoint IS the primary action, so a failure should return a proper error response (e.g., 503 with a retry-friendly message), not a raw traceback in non-debug mode.
**Fix:**
```python
try:
    container = cosmos_manager.get_container("Feedback")
    await container.create_item(body=feedback_doc.model_dump(mode="json"))
except Exception:
    logger.warning(
        "Failed to write feedback document for item %s",
        body.inboxItemId,
        exc_info=True,
    )
    raise HTTPException(
        status_code=503,
        detail="Failed to record feedback. Please try again.",
    )
```

### WR-02: Cosmos datetime string comparison may miss signals near cutoff boundary

**File:** `backend/src/second_brain/tools/investigation.py:413-414`
**Issue:** The query `c.createdAt >= @cutoff` compares against `cutoff_str = cutoff.isoformat()`. The `isoformat()` output for a UTC datetime includes `+00:00` suffix (e.g., `2026-04-15T14:00:00+00:00`). However, FeedbackDocument's `createdAt` field is serialized via Pydantic's `model_dump(mode="json")`, which serializes datetime objects as ISO strings. If Cosmos stores these as strings, the string comparison is lexicographic and the `+00:00` suffix vs `Z` suffix inconsistency could cause incorrect filtering. FeedbackDocuments created via the API will have `datetime.now(UTC)` serialized by Pydantic, while the query cutoff uses Python's `isoformat()`. These may produce different suffix formats (`+00:00` vs potentially no suffix if UTC is stripped).
**Fix:** Normalize the cutoff format to match what Pydantic produces, or use a consistent suffix:
```python
cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
```
Alternatively, store `createdAt` as an epoch number in Cosmos for reliable numeric comparison. This is a design-level consideration for a future phase; for now, verify that both sides produce the same format.

### WR-03: handleFeedback not awaited -- race condition with toast display on toggle-off

**File:** `mobile/app/(tabs)/inbox.tsx:235-271`
**Issue:** The `handleFeedback` callback is an async function called via `onPress={() => handleFeedback("thumbs_up")}`. React Native's `Pressable.onPress` does not await the returned promise. This is fine for the fire-and-forget POST call. However, there is a subtle logic issue: when the user toggles OFF (taps an already-selected button), `newState` becomes `"none"` and the function returns early at line 239 without showing a toast or making an API call. This is correct behavior. But when the user toggles ON, the toast is shown immediately (line 241) before the await on fetch (line 245). If the user quickly toggles off and then on, the feedbackState could be stale due to the closure capturing the previous value. The `useCallback` dependency array includes `[feedbackState, selectedItem]`, which means the closure will be recreated on state change, but rapid double-taps could still race. This is unlikely to cause user-visible bugs in practice given the single-user nature, but is worth noting.
**Fix:** Consider using a ref to track the latest feedback state, or debounce the button press. Given this is low-risk in a single-user app, this is informational.

## Info

### IN-01: Feedback buttons shown for items without classificationMeta

**File:** `mobile/app/(tabs)/inbox.tsx:381-424`
**Issue:** The feedback buttons are rendered unconditionally in the detail modal, regardless of whether the item has `classificationMeta`. For items with status "unresolved" or "misunderstood" that have no classification to rate, showing thumbs up/down on the classification is semantically meaningless. The POST will send `originalBucket: "Unknown"` (from the `?? "Unknown"` fallback on line 256). While this does not cause a crash, it may confuse the feedback signal data.
**Fix:** Wrap the feedback section in a conditional:
```tsx
{selectedItem?.classificationMeta && (
  <>
    <Text style={styles.detailLabel}>Feedback</Text>
    <View style={styles.feedbackRow}>
      {/* ... buttons ... */}
    </View>
  </>
)}
```

### IN-02: Unused `FeedbackDocument` import in investigation.py

**File:** `backend/src/second_brain/tools/investigation.py:26`
**Issue:** The file imports `GoldenDatasetDocument` from `second_brain.models.documents` (line 26) but does not import `FeedbackDocument`. The code constructs feedback documents in `inbox.py` and `errands.py`, not here. However, the `from __future__ import annotations` at the top (line 13) and the `TYPE_CHECKING` block (lines 35-36) import `CosmosManager` only for type checking. This is all correct. The observation is that `FeedbackDocument` is mentioned in the plan but not actually needed in this file since the tool reads raw dicts from Cosmos rather than constructing typed documents. This is fine -- just noting the plan vs. implementation delta is intentional and correct.
**Fix:** No action needed. The implementation correctly reads raw dicts from Cosmos and only needs `GoldenDatasetDocument` for the promotion write path.

---

_Reviewed: 2026-04-22T14:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
