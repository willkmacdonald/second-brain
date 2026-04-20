---
created: 2026-04-19T21:18:34.251Z
title: EAS rebuild and verify mobile_capture emits
area: general
files:
  - mobile/lib/ag-ui-client.ts:47
  - .planning/phases/19.2-transaction-first-spine/SPIKE-MEMO.md:§5.5
---

## Problem

Phase 19.2 Plan 02 shipped Option B mobile_capture emit — centralised in `attachCallbacks` at `mobile/lib/ag-ui-client.ts:47` with single-fire guard and 10-terminal-path outcome mapping (success/degraded/failure per SPIKE-MEMO §4c). The JS is committed and deployed in the git tree, BUT the phone still runs a pre-19.2 EAS bundle — so every capture made from the phone today produces a trace that shows "Missing required segments: mobile_capture" in the red banner at `/correlation/capture/<trace>`.

Verified 2026-04-19 against post-deploy trace `547941ac-bdf3-4ea7-85ac-87cd52217f1f` — only 2 events landed (backend_api + classifier), mobile_capture was flagged missing by the new ledger policy chain validator.

## Solution

1. `cd mobile && eas build --profile development --platform ios` (or preview/production per your usual flow)
2. Install on phone, restart Expo/dev client
3. Do one fresh capture (any text)
4. Run `/investigate "trace my last capture"` → grab new trace_id
5. Visit `https://second-brain-spine-web.purplefield-006b9c41.eastus2.azurecontainerapps.io/correlation/capture/<new-trace>`
6. Confirm the red banner is GONE and "Events (3)" lists mobile_capture + backend_api + classifier in chronological order

Closes the mobile side of Phase 19.2 in practice. Does not require a new phase.

Context: [project_deferred_19.2_spine_gaps.md](../../memory/project_deferred_19.2_spine_gaps.md)
