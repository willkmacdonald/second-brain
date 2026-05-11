# Deferred items discovered during Phase 24 execution

## From 24-19 execution (2026-05-11)

- **`tests/test_classifier_integration.py` + `tests/test_event_tracing.py` collection errors.** Both files import `stream_voice_capture` from `second_brain.streaming.adapter`, which was removed in 24-16 (see STATE decision "[24-16]: stream_voice_capture function removed"). Pre-existing breakage prior to 24-19; out-of-scope for the warmup + main.py GA migration. To fix: either update the imports to the current streaming/adapter.py surface, or delete the obsolete test bodies. Track for a follow-up.

- **`api/health.py` Foundry connectivity probe** still calls the legacy `foundry_client.agents_client.list_agents(...)` shape via `getattr(app.state.foundry_client, ...)`. After 24-19, `app.state.foundry_client` is permanently `None`, so the probe short-circuits to `not_configured`. Migrating this probe to a GA-shaped check (e.g. `app.state.classifier_agent.run("ping")` with a short timeout) restores the live `connected/degraded` signal. Track for a follow-up plan (likely 24-20 or 24-23).
