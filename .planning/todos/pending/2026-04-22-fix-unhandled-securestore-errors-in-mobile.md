---
created: "2026-04-22T01:46:38.433Z"
title: Fix unhandled SecureStore errors in mobile
area: mobile
files:
  - mobile/contexts/ApiKeyContext.tsx:35
  - mobile/app/settings.tsx:42
  - mobile/components/ApiKeyGate.tsx:22
---

## Problem

Phase 19.4.1 code review (19.4.1-REVIEW.md) found 5 warnings related to unhandled SecureStore errors:

- **WR-01** (`ApiKeyContext.tsx:35`): `SecureStore.getItemAsync` has no `.catch()` handler — an error leaves `isLoading` stuck at `true` forever, rendering the app blank.
- **WR-02** (`settings.tsx:42`): `handleSave` has no try/catch around `await setApiKey()` — SecureStore write failure gives no user feedback.
- **WR-03** (`ApiKeyGate.tsx:22`): `handleContinue` has same issue — unhandled SecureStore write failure leaves gate stuck with no error message.
- **WR-04** and **WR-05** are lower priority (require import cleanup and duplicate permissions).

## Solution

Add try/catch with user-facing error feedback to all three SecureStore call sites:
1. `ApiKeyContext.tsx` — catch on getItemAsync, set isLoading=false + fallback to empty key
2. `settings.tsx` — catch on setApiKey, show error toast instead of success toast
3. `ApiKeyGate.tsx` — catch on setApiKey, show Alert.alert with retry option
