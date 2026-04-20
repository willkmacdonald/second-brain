---
created: 2026-04-19T00:00:00.000Z
title: Delete duplicate Key Vault secret for API key
area: infra
files: []
---

## Problem

Two Key Vault secrets in `wkm-shared-kv` point at the same API key (noted in `memory/project_followup_duplicate_api_key_secrets.md`).

## Solution

1. Identify the duplicate (likely `sb-api-key` vs `second-brain-api-key`)
2. Confirm neither is actively referenced twice via `az containerapp show -g shared-services-rg -n second-brain-api`
3. Delete the unused one

Zero downstream blocker -- purely housekeeping. Trigger: whenever convenient.

Reference: `memory/project_followup_duplicate_api_key_secrets.md`
