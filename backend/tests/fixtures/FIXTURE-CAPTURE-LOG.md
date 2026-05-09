# Golden-trace fixture capture log

**Captured:** 2026-05-09
**Captured against:** brain.willmacdonald.com (deployed RC, agent-framework-azure-ai==1.0.0rc2)
**Workspace queried:** Log Analytics `shared-services-logs` (572d91c2-3209-4b92-b431-5ffb7e8ce4ad)
**Operator:** Claude Code (automated capture via curl + App Insights KQL export)

## Investigation fixtures (5)

| Fixture | Trace ID | Thread ID Out | Captured at (UTC) | SSE event count | Span count | Notes |
|---|---|---|---|---|---|---|
| recent_errors | 58d60f86-8ce1-4232-bd74-c532042b6a38 | thread_PQLeQCE8hilSFxh2XT5h1qGZ | 2026-05-09 17:33 | 50 | 45 | Agent called recent_errors tool; no errors in last hour |
| system_health | af9628ec-c19a-4a2d-8ee7-618c969619d5 | thread_Q42dDcTGFPvFbKLHrEGUdRgM | 2026-05-09 17:34 | 100 | 39 | Agent called system_health tool with 24h window |
| usage_patterns | fc13fdb3-f0c5-4f0d-bd52-b8ad52455e5e | thread_nnjeASbYY7VOecE2Sm2For1o | 2026-05-09 17:35 | 70 | 65 | Agent called usage_patterns tool with 7-day bucket breakdown |
| trace_lifecycle | 4c415b01-c8e8-430d-a430-e5b08e9efbfe | thread_tawNr7cX1vXGZHQDiG2XIK3r | 2026-05-09 17:36 | 204 | 26 | Agent called trace_lifecycle tool for capture 08c31eb1-6815-452a-affb-1d290b7d5885 |
| audit_correlation | 6b5efa1d-2d1e-4a0f-924e-a108cfaaa6e6 | thread_ggJLIOswMGRbMmg2eLoteytc | 2026-05-09 17:37 | 239 | 18 | Agent called trace_lifecycle (not audit_correlation) for capture de875d59-1335-4143-b3ef-1564e06d8ea9; model chose tool autonomously |

## Admin fixtures (5)

| Fixture | Stage A trace_id | Stage A captured at (UTC) | Stage B fired at (UTC) | Tool called | Side effects | Cleanup needed? |
|---|---|---|---|---|---|---|
| errand_routing | 2a0819ba-2d2b-47f3-a47f-9c4f19146244 | 2026-05-09 17:55 | 2026-05-09 17:55 | add_errand_items (tool_invoked=True) | Errand items "apples and bread" filed to grocery destination | Left as-is (real errand items in live data) |
| task_creation | 640b17f1-0bc7-41b7-8f18-74f618cb7b9b | 2026-05-09 18:10 | 2026-05-09 18:10 | add_task_items (tool_invoked=True) | Task "Book the veterinarian appointment for the cats next Tuesday" created | Left as-is |
| recipe_extraction | 814ac3e1-43c3-407d-848d-8f78aa79ebea | 2026-05-09 17:45 | 2026-05-09 17:46 | recipe extraction tools (tool_invoked=True) | Recipe URL https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/ fetched and processed | Recipe stored in Cosmos |
| destination_management | 95f0bf52-2a11-46bd-8371-05da81b36d5e | 2026-05-09 17:46 | 2026-05-09 17:46 | No tool invoked (5 admin_agent_process attempts, all tool_invoked=False) | Admin processed item "Add a new destination called Home Depot" but agent did not call manage_destination | Item marked failed in inbox |
| affinity_rule_edit | b446e961-fe93-4001-8bc1-0a0639fec112 | 2026-05-09 17:46 | 2026-05-09 17:46 | No tool invoked (1 admin_agent_process attempt, tool_invoked absent) | Admin processed item "When I mention tools route to Home Depot" but agent did not call manage_affinity_rule | Item marked failed in inbox |

## Classifier fixtures (8)

| Fixture | Trace ID(s) | Captured at (UTC) | Bucket | Confidence | SSE final event | Notes |
|---|---|---|---|---|---|---|
| text_person | dc32cc85-5e89-48a3-be04-04e11b445edf | 2026-05-09 18:17 | People | 0.9 | CLASSIFIED | "Coffee with Sarah next Tuesday at the Blue Bottle" |
| text_project | 76ea0345-a367-4b2a-88e3-c3d64157f519 | 2026-05-09 18:17 | Projects | 0.9 | CLASSIFIED | "Backend refactor to migrate auth middleware to async" |
| text_idea | 9beb580d-ba2c-4bbf-985d-9f384cdd2d0a | 2026-05-09 18:17 | Ideas | 0.9 | CLASSIFIED | "What if errands could auto-suggest based on calendar context?" |
| text_admin_errand | 896fb189-2174-4173-a45f-c3d96e835ffa | 2026-05-09 18:17 | Admin | 0.9 | CLASSIFIED | "Pick up the dry cleaning Friday" |
| text_admin_task | 1649253d-f7d8-4103-92d3-aff940e4426d | 2026-05-09 18:19 | Admin | 0.95 | CLASSIFIED | "Pay the electric bill before it is due next Friday"; re-captured because initial "Submit expense report" classified as Projects |
| voice_person | 7fe92c3b-ca3f-4681-baf2-443bca26eef7 | 2026-05-09 18:20 | People | 0.9 | CLASSIFIED | Audio source: macOS TTS /tmp/voice_person_sample.m4a; transcript: "Birthday dinner with mom on Saturday at 7pm" |
| low_confidence_followup | d720349e-7022-4ee8-bdd0-516d345c129f | 2026-05-09 18:18 | Ideas | 0.4 | LOW_CONFIDENCE | Turn 1 only; turn 2 follow-up not captured because LOW_CONFIDENCE uses bucket-selection HITL, not follow-up text endpoint |
| deliberate_misunderstood | a40f8178-20b8-4d8a-8976-2ca05da3d2f4 | 2026-05-09 18:18 | N/A | N/A | MISUNDERSTOOD | "asdf zxcv qwerty deliberately incomprehensible test input"; model chose Misunderstood via safety net path (retired in GA per D-07b) |

## Capture environment

- Local API key source: Azure Key Vault (wkm-shared-kv, secret: second-brain-api-key)
- Auth header format: Authorization: Bearer (not X-API-Key as plan originally specified; corrected per actual auth.py middleware)
- Network conditions: local machine, direct internet
- App Insights ingestion lag observed: 2-4 minutes for AppRequests/AppDependencies
- Azure CLI identity: will@willmacdonald.com

## Re-capture protocol (for Phase 24 and beyond)

To re-capture fixtures (e.g. if they grow stale or if Phase 24 finds drift):

1. Confirm deployed RC version unchanged (commit SHA in /health response).
2. Re-run capture commands from PLAN-03 tasks 1-3.
3. Update this log with new trace IDs and timestamps.
4. Diff old vs new fixtures: SSE event order should be identical; span counts may vary; expected-deltas.md should rarely need editing.

## Side effects to clean up

Captures created real artifacts in the live system:

- **errand_routing**: Errand items "apples and bread" filed to grocery destination. Left as-is.
- **task_creation**: Task "Book the veterinarian appointment" created. Left as-is.
- **recipe_extraction**: Recipe from allrecipes.com stored in Cosmos. Left as-is.
- **destination_management**: Admin processing failed (agent did not invoke manage_destination). Item left as failed in inbox.
- **affinity_rule_edit**: Admin processing failed (agent did not invoke manage_affinity_rule). Item left as failed in inbox.
- **text_admin_errand**: "Pick up dry cleaning Friday" filed as Admin errand in inbox. Left as-is.
- **text_admin_task**: "Pay the electric bill" filed as Admin task in inbox. Left as-is.
- **deliberate_misunderstood**: No inbox item created (safety-net MISUNDERSTOOD path does not create items).
- **low_confidence_followup**: LOW_CONFIDENCE inbox item "remind me about the thing" created with Ideas bucket at 0.4 confidence. Left as-is.
- Additional test captures from re-capture attempts (errand_routing x2, task_creation x2) also left in inbox.
