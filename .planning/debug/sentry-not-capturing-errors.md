---
status: investigating
trigger: "Sentry not capturing client-side errors - console.error fires but nothing in Sentry"
created: 2026-04-11T00:00:00Z
updated: 2026-04-11T00:00:00Z
---

## Current Focus

hypothesis: Two independent root causes preventing Sentry from capturing console.error calls
test: Code review of sentry.ts config and index.tsx error handling
expecting: Confirm (1) no CaptureConsole integration and (2) enabled:!__DEV__ disables in dev
next_action: Document root cause and recommend fix

## Symptoms

expected: console.error("Voice capture fallback error:", error) at index.tsx:208 should appear in Sentry
actual: Error shows in device error overlay but not in Sentry dashboard
errors: N/A (no Sentry errors -- that IS the problem)
reproduction: Trigger a voice capture error on the mobile device
started: Since Phase 17.3 added Sentry (never worked for this case)

## Eliminated

(none -- root cause identified on first pass)

## Evidence

- timestamp: 2026-04-11
  checked: mobile/lib/sentry.ts - Sentry init configuration
  found: |
    Line 15: `enabled: !__DEV__` -- Sentry is DISABLED in dev builds.
    No CaptureConsole integration configured.
    Only integrations: [navigationIntegration]
  implication: Two root causes identified

- timestamp: 2026-04-11
  checked: mobile/app/(tabs)/index.tsx lines 207-208 and 615-616
  found: |
    Both error handlers use `console.error(msg, error)` where `error` is a string.
    No `Sentry.captureException()` or `Sentry.captureMessage()` calls anywhere in the codebase.
  implication: Even if Sentry were enabled, it would not capture console.error calls without explicit integration

- timestamp: 2026-04-11
  checked: Sentry SDK for CaptureConsole integration
  found: |
    `@sentry/react-native` does NOT ship a captureConsoleIntegration.
    This integration lives in `@sentry/core` / `@sentry/integrations` (browser SDK).
    It is NOT available in the React Native bundle.
  implication: Cannot rely on CaptureConsole even if desired; must use explicit captureException/captureMessage

- timestamp: 2026-04-11
  checked: eas.json and Sentry DSN configuration
  found: |
    DSN is set in both "development" and "production" EAS build profiles.
    DSN value looks valid (o4511203611574272.ingest.us.sentry.io).
  implication: DSN config is correct -- not a configuration issue

- timestamp: 2026-04-11
  checked: Sentry.ErrorBoundary in _layout.tsx
  found: |
    ErrorBoundary wraps the app tree -- catches unhandled React render errors.
    But the voice capture error is a CAUGHT error in a callback, not a render throw.
    ErrorBoundary cannot intercept it.
  implication: ErrorBoundary is correctly configured but irrelevant to this error path

## Resolution

root_cause: |
  TWO independent issues prevent Sentry from capturing the voice capture error:

  1. **Primary: No explicit Sentry.captureException() call** (mobile/app/(tabs)/index.tsx:208, :616)
     The error handlers call `console.error()` only. Sentry does NOT automatically
     capture console.error() calls. The `@sentry/react-native` SDK captures:
     - Unhandled JS exceptions (global error handler)
     - Unhandled promise rejections
     - React render errors (via ErrorBoundary)
     It does NOT intercept `console.error()` unless a CaptureConsole integration
     is explicitly added -- and that integration isn't available in the React Native SDK.

  2. **Secondary: Sentry disabled in dev** (mobile/lib/sentry.ts:15)
     `enabled: !__DEV__` means Sentry is completely disabled during development.
     Even if captureException were called, nothing would be sent while testing
     via `npx expo start --dev-client`.

  The error at line 208 is a string passed through a callback (`onError: (error: string) => {...}`).
  It is a CAUGHT error being logged, not an unhandled exception. Sentry's automatic
  capture mechanisms (global error handler, ErrorBoundary) cannot see it.

fix: |
  Add explicit Sentry.captureException() or Sentry.captureMessage() calls at each
  console.error site. Since the error value is a string (not an Error object),
  use Sentry.captureMessage() or wrap in new Error().

verification: (pending)
files_changed: []
