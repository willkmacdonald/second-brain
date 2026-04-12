# Phase 18: Deferred Items

## Pre-existing TypeScript Error in _layout.tsx

- **File:** `mobile/app/_layout.tsx:22`
- **Error:** `ErrorFallback` component type incompatible with Sentry's `FallbackRender` type (`error: unknown` vs `error: Error`)
- **Origin:** Phase 17.3 Sentry integration
- **Impact:** TypeScript strict compilation fails, but runtime behavior is correct
- **Fix:** Cast error type or update `ErrorFallbackProps` to accept `unknown` instead of `Error`
