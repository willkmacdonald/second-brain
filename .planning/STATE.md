---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Admin Agent & Shopping Lists
status: in-progress
last_updated: "2026-03-19T04:48:23Z"
progress:
  total_phases: 19
  completed_phases: 14
  total_plans: 54
  completed_plans: 51
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** One-tap capture from a phone instantly routes through an agent that classifies, files, and clarifies -- with zero organizational effort.
**Current focus:** v3.0 -- Phase 12.5 On-Device Voice Transcription in progress

## Current Position

Phase: 12.5 of 13 (On-Device Voice Transcription)
Plan: 1 of 3
Status: Plan 01 complete -- expo-speech-recognition installed, speech helper created, sendCapture extended
Last activity: 2026-03-19 -- Completed 12.5-01 (Install & configure on-device speech recognition)

Progress: [█████████░] 94% (v3.0)

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 28
- Average duration: 3.2 min
- Total execution time: 1.5 hours

**Velocity (v2.0):**
- Total plans completed: 16
- Average duration: 3.3 min
- Timeline: 2026-02-26 to 2026-03-01 (4 days)

**Velocity (v3.0):**
- Total plans completed: 13
- Average duration: 2.9 min

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 10 | 01 | 2 min | 3 | 4 |
| 10 | 02 | 2 min | 3 | 4 |
| 11 | 01 | 3 min | 2 | 4 |
| 11 | 02 | 5 min | 3 | 3 |
| 11.1 | 01 | 3 min | 2 | 5 |
| 11.1 | 02 | 4 min | 2 | 2 |
| 11.1 | 03 | 2 min | 2 | 2 |
| 11.1 | 04 | 3 min | 2 | 0 |
| 12 | 01 | 2 min | 2 | 3 |
| 12 | 02 | 2 min | 2 | 4 |
| 12.1 | 01 | 5 min | 3 | 9 |
| 12.1 | 02 | 2 min | 2 | 2 |
| 12.2 | 01 | 2 min | 2 | 6 |
| 12.2 | 03 | 2 min | 2 | 4 |
| Phase 12.2 P02 | 3 min | 2 tasks | 4 files |
| Phase 12.3 P01 | 3 min | 2 tasks | 3 files |
| Phase 12.3 P02 | 5 min | 2 tasks | 3 files |
| Phase 12.3 P03 | 6 min | 2 tasks | 4 files |
| Phase 12.3 P04 | 1 min | 2 tasks | 2 files |
| Phase 12.3 P05 | 3 min | 2 tasks | 3 files |
| Phase 12.3.1 P01 | 3 min | 2 tasks | 8 files |
| Phase 12.3.1 P02 | 3 min | 2 tasks | 10 files |
| Phase 12.3.1 P03 | 3 min | 2 tasks | 5 files |
| Phase 12.5 P01 | 2 min | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
v2.0 decisions archived to .planning/milestones/v2.0-ROADMAP.md

**v3.0 decisions:**
- [10-01] ShoppingListItem does not inherit BaseDocument -- no userId, timestamps, or classificationMeta needed
- [10-01] Tool parameter is list[dict] not list[ShoppingListItem] to avoid agent schema generation issues
- [10-01] Unknown stores silently fall back to "other" without error
- [10-02] Admin Agent registration is non-fatal -- app continues if Foundry registration fails
- [10-02] Separate AzureAIAgentClient instance for Admin Agent (own agent_id, own middleware)
- [11-01] autouse fixture pattern for Cosmos read_item mock -- returns mutable dicts to match real Cosmos behavior
- [11-02] getattr with safe defaults for admin refs -- graceful degradation when Admin Agent registration fails
- [11-02] Admin Agent only on initial captures, not follow-ups -- follow-ups are reclassification, not new captures
- [11-02] Admin Agent instructions already correct in Foundry portal -- no manual update needed
- [11.1-01] Extend classified_event with optional params (not new event type) -- backward-compatible
- [11.1-01] Conditional dict: buckets/itemIds absent (not null) for single-item events
- [11.1-01] process_admin_captures_batch delegates to existing process_admin_capture -- code reuse
- [11.1-01] Safety net triggers on empty file_capture_results list, not detected_tool check
- [11.1-02] Check buckets.length > 1 (not just existence) for multi-split vs single toast branching
- [11.1-02] Multi-split toast omits confidence -- multiple confidences would be confusing
- [11.1-02] Classifier multi-intent instructions favor keeping as single item when split is ambiguous
- [11.1-03] Store all function_calls in pending_calls dict -- future-proof for new tools
- [11.1-03] Pop from pending_calls on function_result -- prevents stale entries
- [11.1-03] stream_follow_up_capture intentionally unchanged -- single-tool pattern correct for reclassification
- [11.1-04] Instruction rewrite: "After determining the primary bucket" replaces "Before classifying" to prevent over-analysis
- [11.1-04] Explicit conjunction markers (and also, plus, oh and) as sole trigger for multi-intent splitting
- [11.1-04] Rule 6 added: conversational phrasing treated identically to imperative phrasing
- [12-01] Store display name mapping as constant dict with title-case fallback for unknown stores
- [12-01] Per-partition query loop over KNOWN_STORES (not cross-partition fan-out) for Cosmos best practice
- [12-02] StatusSectionRenderer renders header only -- SectionList handles item rendering via renderItem prop
- [12-02] Optimistic delete uses refetch instead of snapshot rollback to avoid stale closure issues with rapid deletes
- [12-02] Lightning bolt icon for Status tab to convey action/working
- [12.1-01] Processing triggers as side effect of GET /api/shopping-lists (not a separate endpoint)
- [12.1-01] Delete-on-success replaces processed upsert -- shopping list items are the durable output
- [12.1-01] CosmosResourceNotFoundError on delete is non-fatal (user may have swipe-deleted)
- [12.1-01] 3-second polling interval for auto-refresh while processing is active
- [12.1-01] processingCount field added to ShoppingListResponse for mobile banner control
- [12.1-02] Include ALL pending items in retry (not just stale ones) -- idempotent agent safer than permanently stuck items
- [12.1-02] admin_handoff.py NOT modified -- delete failure handler keeps log-only behavior per user decision
- [12.2-01] Field rename store->destination mirrors the broader errands concept (destinations can be physical or online)
- [12.2-03] Migration script uses upsert_item for idempotency -- safe to re-run if interrupted
- [12.2-03] Verification count check blocks old container deletion on mismatch -- prevents data loss
- [Phase 12.2]: DELETE endpoint path simplified from /api/errands/items/{id} to /api/errands/{id} per CONTEXT.md
- [Phase 12.3]: Azure CLI management plane for Cosmos container creation (data plane gets 403 with AAD)
- [Phase 12.3]: Destination slug used as document id for idempotent upserts in seed script
- [Phase 12.3]: KNOWN_DESTINATIONS kept for backward compatibility until Plan 03 replaces with dynamic routing
- [Phase 12.3]: Admin tools accept any destination slug dynamically, default fallback is 'unrouted' not 'other'
- [Phase 12.3]: needsRouting=True set automatically when destination is 'unrouted'
- [Phase 12.3]: Affinity rule conflict detection is case-insensitive on itemPattern
- [Phase 12.3]: manage_destination remove checks for existing errand items before deletion
- [Phase 12.3]: Response delivery heuristic uses keyword indicators (?, conflict, rule, created, deleted, destination) to classify agent responses
- [Phase 12.3]: Routing context injection wrapped in try/except with graceful fallback to raw text
- [Phase 12.3]: DELETE /api/errands/{id} accepts any destination string (no hardcoded validation)
- [Phase 12.3]: Notification dismiss deletes inbox item (response has been delivered)
- [Phase 12.3]: Migration script retains local KNOWN_DESTINATIONS (self-contained, not imported from documents.py)
- [Phase 12.3]: Horizontal scrollable chips for destination picker (not dropdown) -- better UX for quick tapping
- [Phase 12.3]: Admin notifications render above processing banner -- notifications are higher priority
- [Phase 12.3]: Route request always sets saveRule: true -- system auto-learns user preferences by default
- [Phase 12.3.1]: PUBLIC_PATHS reduced to /health only -- /docs and /openapi.json now conditional on environment
- [Phase 12.3.1]: Upload validation uses dual check: file.size header first, then len(bytes) as fallback
- [Phase 12.3.1]: VALID_BUCKETS uses frozenset for immutability (prevents accidental mutation of shared constant)
- [Phase 12.3.1]: Routing context format uses admin.py tool version as canonical (Agent trained on DESTINATIONS: / ROUTING RULES: headers)
- [Phase 12.5]: expo-speech-recognition ^3.1.1 wraps Apple SpeechAnalyzer for Expo compatibility
- [Phase 12.5]: speech.ts is stateless functions only -- component uses useSpeechRecognitionEvent hooks directly
- [Phase 12.5]: X-Capture-Source header is observability-only, does not affect classification

### Research Findings (Critical for v3.0)

- Admin Agent processes silently in background -- no SSE streaming of Admin work to user
- Individual item documents in Cosmos (not embedded arrays) for atomicity
- youtube-transcript-api blocked on Azure IPs -- use YouTube Data API v3 for production
- Agent-driven store routing via Foundry portal instructions, not code
- Separate AzureAIAgentClient instance for Admin Agent (no thread/tool cross-contamination)

### Pending Todos

None.

### Roadmap Evolution

- Phase 11.1 inserted after Phase 11: Classifier Multi-Bucket Splitting (URGENT)
- Phase 12.1 inserted after Phase 12: Admin agent deletes processed inbox items (URGENT)
- Phase 12.2 inserted after Phase 12.1: Rename Admin infrastructure from shopping lists to generic errands system (URGENT)
- Phase 12.3 inserted after Phase 12: Destination affinity and knowledge system for errand routing (URGENT)
- Phase 14 added: App Insights Operational Audit
- Phase 12.3.1 inserted after Phase 12.3: Implement fixes for security issues and from output of dead code analysis (URGENT)
- Phase 12.5 added: On-Device Voice Transcription (replace cloud Whisper with iOS SpeechAnalyzer)

### Blockers/Concerns

- [Open]: YouTube Data API v3 setup needs research before Phase 13 starts
- [Resolved]: Admin Agent instruction quality for store routing -- validated: "need milk" correctly routed to jewel store

## Session Continuity

Last session: 2026-03-19
Stopped at: Completed 12.5-01-PLAN.md
Resume action: Continue with 12.5-02-PLAN.md (index.tsx rewrite for on-device voice capture)
