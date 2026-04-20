---
created: 2026-04-19T00:00:00.000Z
title: Mobile EAS rebuild to close 19.2 mobile_capture gap
area: mobile
files:
  - mobile/lib/ag-ui-client.ts
  - .planning/phases/19.2-transaction-first-spine/SPIKE-MEMO.md
---

## Problem

After Phase 19.2 the mobile JS was centralised to emit mobile_capture via Option B, but the phone runs a pre-19.2 EAS bundle. Need to rebuild and reinstall to close the 19.2 baseline.

## Solution

1. Run `eas build --profile development` (or preview)
2. Reinstall on phone
3. Perform one fresh capture
4. Confirm the web UI at `/correlation/capture/<trace>` shows mobile_capture + backend_api + classifier with no "Missing required segments" warning

Trigger: before Phase 19.4 executes (close 19.2 baseline first) OR immediately after 19.3 completes if it slipped.

Adoption check mechanism: see inventory Surface 9 / OTA update adoption row in `docs/superpowers/specs/native-observability-inventory.md`.

Reference: `memory/project_deferred_19.2_spine_gaps.md`
