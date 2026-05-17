---
phase: 25-admin-inbox-soft-delete-30-day-retention
type: discuss-context
discussed_at: 2026-05-17
status: locked
---

# Phase 25 — Discussion Context

## Domain

Replace the hard-delete-on-Admin-success path in `processing/admin_handoff.py` with `status="filed"` soft-delete + per-document Cosmos TTL (30 days). Preserves short-term audit trail for evals/observability without unbounded Cosmos growth. Phone inbox view and `/investigate` queries hide filed items.

Scope: **Admin-bucket** Inbox items processed by the Admin agent ONLY. People/Ideas/Projects/Admin (non-processed) inbox docs are unaffected — no agent processes them away, so they already persist as durable records.

## Canonical refs

- `.planning/ROADMAP.md` — Phase 25 section (success criteria, optional bundled scope)
- `backend/src/second_brain/processing/admin_handoff.py:396-405` — current `delete_item` site that becomes the soft-delete site
- `backend/src/second_brain/api/inbox.py:76-92` — inbox listing query that needs `status != "filed"` filter
- `backend/src/second_brain/tools/investigation.py:443,812` — investigation tool inbox queries that need the same filter
- `backend/src/second_brain/cosmos/inbox_conversation_history.py` — already touches Inbox doc lifecycle (Phase 24-15); reference for the filing pattern
- `backend/src/second_brain/tools/admin.py` — `add_errand_items` + `add_task_items` tool methods that get the new backlink fields
- `backend/src/second_brain/models/documents.py` — `ErrandItem` + `TaskItem` Pydantic models that get new optional fields
- `backend/src/second_brain/config.py` — gets new `inbox_filed_retention_days: int = 30` setting
- Phase 24 backlog items "Admin Retry Bound" + (obsolete after Phase 26) "Admin Recipe-Fetch Fallback" — these still apply to the filed-status loop concern raised during Phase 24 UAT 2026-05-17; Phase 25 must not regress them

## Decisions

### 1. TTL mechanism — Per-document Cosmos `ttl`

When `admin_handoff` marks an Inbox doc as `filed`, it sets `doc["ttl"] = settings.inbox_filed_retention_days * 86400` on the same upsert. Cosmos auto-deletes 30 days after the document's `_ts` (last write timestamp). Zero ongoing operational cost, no new scheduler infrastructure.

**Configuration:** New env var `INBOX_FILED_RETENTION_DAYS` (defaults to 30). Threads through `Settings.inbox_filed_retention_days: int = 30`. Container App env var settable per environment if we ever want to extend or shorten the window.

**Trade-off accepted:** Cosmos doesn't log per-document TTL deletions to spine_events. If we ever need to audit "which docs got purged when," we'd query App Insights for write-volume drops or rely on the 30-day window being long enough that we'd notice before purge.

**Alternatives considered:** Background sweep job (more moving parts, gives per-deletion logging; rejected because per-doc TTL is simpler and the audit trail in spine_events for processing events is what matters, not deletion events). Container-default TTL (same mechanism, just configured at container level instead of per-doc; rejected because per-doc gives flexibility if we ever want to file with different TTLs).

### 2. Container TTL prep — Plan invokes az CLI

Cosmos requires the container to have TTL machinery enabled (default TTL ≥ 0 or = -1) before per-doc `ttl` values take effect. Today the Inbox container has no TTL configuration.

**Lock:** The Phase 25 plan includes an `az cosmosdb sql container update --account-name shared-services-cosmosdb --database-name second-brain --name Inbox --ttl -1` step as part of execution. `ttl=-1` enables the machinery but doesn't expire anything by default; per-doc `ttl=N` overrides at filing time.

**Operator authorization required:** This is a write to production Cosmos infrastructure. Plan executes it explicitly under operator authorization (same pattern as Phase 24 Step C's `az containerapp update`).

**Verification:** Plan asserts via `az cosmosdb sql container show --query "resource.defaultTtl"` that the value is `-1` after the update.

### 3. Filed visibility — Fully out of sight

Phone inbox view filters out `status="filed"` items. `/investigate` Inbox queries default to excluding `filed` items. **No `include_filed=true` opt-in.** The 30-day window is purely internal (eval/debugging via direct Cosmos query if ever needed).

**ROADMAP amendment required:** ROADMAP success criterion #4 currently reads `/investigate Inbox queries default to excluding filed (with opt-in include_filed=true)`. The "with opt-in" clause is dropped. Plan amends ROADMAP wording during execution.

**Rationale:** "Filed = processed = done" mental model is clean. If we ever need to audit what got filed, Cosmos query + App Insights are available. Avoids UI complexity for a feature that's never been requested.

### 4. Bundled scope — Source backlinks on Errand/Task

Adds two optional fields to `ErrandItem` and `TaskItem` Pydantic models:
- `sourceInboxItemId: str | None = None`
- `sourceCaptureTraceId: str | None = None`

Populated at creation time in `tools/admin.py` when `add_errand_items` / `add_task_items` fires. The Admin agent's tool invocation already has the inbox_item_id in context (admin_handoff passes it through); the trace ID lives on `capture_trace_id_var` ContextVar.

**Field durability:**
- `sourceCaptureTraceId` — durable forever. Useful for spine_events correlation even after the 30-day Inbox TTL purges the source doc.
- `sourceInboxItemId` — durable for 30 days while the source Inbox doc exists; after TTL purge, the backlink points at a non-existent doc. Plan should document this as expected behavior; UI gracefully handles "source no longer available" (just doesn't render the affordance).

**Effect on phase plan count:** +1 plan compared to minimum scope. Total phase scope estimate: 2-3 plans.

**Pre-Phase-25 Errand/Task docs** keep their existing schema (no backlink fields). UI must gracefully handle absent backlinks.

### 5. Backfill — None

Existing Admin Inbox docs that already got hard-deleted are gone forever (irrecoverable). The Inbox container at Phase 25 start has 14 docs (post-cleanup from 2026-05-16), none of which have `status="filed"`. Phase 25 only changes behavior for **new** Admin captures going forward.

**Acceptance:**
- Pre-Phase-25 Errand/Task docs have no `sourceInboxItemId` / `sourceCaptureTraceId` fields. UI handles gracefully (no backlink affordance for those items).
- No spine_events-based backfill script. The historical Errand/Task ↔ Inbox correlation is lost; durable correlation only exists for Phase 25+ items.

## Specifics

- The 30-day retention is **configurable** via `INBOX_FILED_RETENTION_DAYS` env var. Default = 30 days. If we ever want to tune this (e.g., 14 days for faster privacy purge, 60 days for longer eval baseline window), it's an env var flip on the Container App — no code change.
- `status="filed"` is the soft-delete sentinel. **NOT** `status="completed"` or `status="processed"` — Plan 24-11 already uses `adminProcessingStatus` for tracking pending/completed/failed processing state. The two fields are orthogonal: `adminProcessingStatus="completed"` says the Admin agent finished work; `status="filed"` says the Inbox doc itself is done. Most filed docs will have both set.
- The current admin_handoff.py `delete_item` path at line 396-405 has TWO branches:
  - Branch A (line 396): "Simple confirmation — delete the inbox item." → THIS becomes the soft-delete (`status="filed"` + `ttl`).
  - Branch B (line 363 area): "Response contains info the user needs to see — keep the inbox item with response attached." → This path was already keeping the doc; Phase 25 doesn't change it.
- Only Admin-bucket items currently flow through admin_handoff.py. Classifier-side classification and HITL clarification paths do their own Inbox writes but never delete. Phase 25 doesn't touch those.

## Deferred ideas

- **Filed audit dashboard** — A `/investigate "what got filed this week"` capability via include_filed parameter. Considered and rejected for Phase 25 (no operator demand for this view); could be revisited if eval/debugging needs surface.
- **Per-bucket retention windows** — Different retention for different buckets (e.g., recipe captures purged faster than task captures). Out of scope; current design treats all Admin items identically. Configurable env var sets a single retention value.
- **Soft-delete for non-Admin buckets** — People/Projects/Ideas don't have a "processed" lifecycle today, so no soft-delete is needed. If a future phase adds an agent that processes People items (e.g., contact extraction), the same pattern would apply.
- **UI "history view" on the phone** — A settings toggle to show filed items in inbox with greyed visual treatment. Considered and rejected — clean "filed = done" mental model preferred. Trivial to add later if demand surfaces.

## Open Questions

None. All gray areas resolved.

## Constraints / Non-negotiables

- **Phone UX**: No regression. The mobile inbox view must look identical to today for non-filed items. Filed items vanish silently after the agent processes them (same UX as the current hard-delete behavior — user perspective unchanged).
- **Phase 24 stability**: This phase touches `admin_handoff.py` lifecycle code. Phase 24 must be fully stable (UAT done, 7-day soak tracking shows < 1% forced_tool_failure) before Phase 25 ships. As of 2026-05-17, Phase 24 is in 7-day soak window through 2026-05-24.
- **Phase 24 backlog awareness**: The backlogged "Admin Retry Bound" item (cap retries at N=3 via `adminRetryCount`) interacts with status=filed semantics — a failed item that hits the retry cap should NOT be marked `filed` (it's not "done"). The plan must keep these orthogonal: `adminRetryCount` + `adminProcessingStatus=failed` for cap exhaustion; `status=filed` only on successful Admin agent processing path.
- **Phase 26 awareness**: Recipe extraction is being retired (Phase 26). Phase 25's "recipe URL captures follow the same path: source Inbox → filed once, ingredients persist normally in Errands" success criterion still applies for whatever recipe-path captures exist before Phase 26 lands. If Phase 26 ships before Phase 25, the recipe-specific criterion becomes moot.
- **Container TTL update is a one-time infrastructure change.** Once enabled (`ttl=-1`), it stays enabled. Phase 25 plan should make this idempotent (check current value before updating).

## Next step

`/gsd-plan-phase 25` — researcher + planner spawn from this CONTEXT.md to produce the executable plan(s).
