# Project Research Summary

**Project:** Active Second Brain — v2.0 Foundry Migration + Proactive Specialist Agents
**Domain:** Multi-agent proactive personal knowledge management (FastAPI + Expo + Azure AI Foundry)
**Researched:** 2026-02-25
**Confidence:** MEDIUM-HIGH overall. Stack and features are grounded in official sources. Architecture has one confirmed design element that requires empirical validation (FoundrySSEAdapter event surface). Pitfalls are thoroughly documented with recovery strategies and phase mappings.

---

## Executive Summary

The Active Second Brain v2.0 encompasses two milestones in one research cycle: (1) migrating the existing capture pipeline from `HandoffBuilder` + `AGUIWorkflowAdapter` to Azure AI Foundry Agent Service with persistent specialist agents, and (2) adding a proactive notification layer driven by APScheduler-triggered specialist agents. The single most critical finding across all four research files is unanimous: **HandoffBuilder and AzureAIAgentClient are fundamentally incompatible and cannot coexist**. The Orchestrator agent is eliminated entirely. FastAPI becomes the code-based orchestrator via `if/elif` routing after classification — this replaces `HandoffBuilder` with approximately 20 lines of Python.

The proactive notification layer is architecturally straightforward once the Foundry migration stabilizes, but carries one irreversible UX risk: notification fatigue. If Will disables iOS notifications for the app, the permission cannot be re-granted programmatically. This means throttling and quiet hours must be built into the notification dispatcher before any agent scheduler is connected to push delivery — not added as a polish step. Beyond that constraint, the proactive layer follows standard patterns: APScheduler in-process (not Container App Jobs, which cannot share initialized agent connections), Expo Push Service for APNs/FCM delivery, and agent-generated copy that reads current Cosmos DB state at nudge time. Geofencing is explicitly deferred to v3.0 in favor of a weekend-morning time-window heuristic that delivers 80% of the value with 5% of the complexity.

The recommended implementation sequence has a hard dependency chain: Foundry infrastructure and credentials first, then single-agent Classifier baseline, then FoundrySSEAdapter rewrite, then HITL validation, then the four specialist agents, then push notification infrastructure, then proactive scheduling. Each phase validates independently before the next adds complexity. The v2.0 MVP delivers people nudges, Friday digest, ideas check-ins, and errand timing — all backed by agent-generated copy referencing the user's actual captured content.

---

## Key Findings

### Recommended Stack

See `.planning/research/STACK.md` for full details.

The existing validated stack (FastAPI, Expo/React Native 0.81.5 SDK 54, Cosmos DB, Azure Container Apps, uv, Ruff) is unchanged. Six new capability areas add targeted packages.

**Core technologies added:**
- `agent-framework-azure-ai 1.0.0rc1`: `AzureAIAgentClient` connector to Foundry Agent Service — required for persistent server-side agents. Install with `--prerelease=allow`. RC1 promoted February 19, 2026; stable enough for production.
- `azure-ai-projects 1.0.0` + `azure-ai-agents 1.1.0`: Agent lifecycle management (CRUD for persistent agents). Both GA as of July-August 2025. Pin both together to avoid version drift.
- `APScheduler 3.11.2`: `AsyncIOScheduler` with cron triggers for Friday digests, weekly nudges, daily People scans. Use v3 only — v4 is still alpha (4.0.0a6). Starts in FastAPI lifespan; shares initialized agent connections.
- `azure-monitor-opentelemetry 1.6.0`: One-call Application Insights setup via `configure_azure_monitor()`. Do not pin `opentelemetry-sdk` directly — let the distro manage it.
- `exponent-server-sdk 2.2.0`: Expo Push Service Python SDK (sync). Called from APScheduler jobs, not async FastAPI routes.
- `expo-notifications ~0.32.x` + `expo-device ~7.0.x`: Expo SDK 54 push notification packages. Require development build — Expo Go insufficient for production push tokens.
- `gpt-4o-transcribe`: Drop-in replacement for Whisper via same `audio.transcriptions.create()` API. Requires `api_version="2025-03-01-preview"`. Currently East US2 global standard only.

**Critical version constraint:** `agent-framework-azure-ai` RC1 requires `azure.identity.aio.DefaultAzureCredential` (async), not the sync variant from `azure.identity`. This is a silent breaking change from the existing codebase and must be addressed before any Foundry SDK code runs.

**What NOT to add:** `APScheduler 4.x` (alpha), `HandoffBuilder` or `AGUIWorkflowAdapter` (dead code after migration), `ConnectedAgentTool` for specialist routing (local `@tool` functions unsupported), `expo-background-fetch` (removed in SDK 53+), Hub-based AI Foundry projects (deprecated May 2025).

### Expected Features

See `.planning/research/FEATURES.md` for full details.

**Must have for v2.0 (P1 — table stakes for the "proactive" promise):**
- Push token registration on app startup — nothing proactive works without the device token stored server-side
- APScheduler in FastAPI lifespan — trigger mechanism for all scheduled agent runs
- People Agent relationship nudge — daily 8am scan; fire if `last_interaction` > 4 weeks; highest-value agent for personal system
- Admin Agent Friday evening digest — one notification/week summarizing pending Admin captures; proves the digest pattern
- Admin Agent errand timing — surface errand captures Saturday 9am (time-window heuristic, not geofencing)
- Ideas Agent weekly check-in — "any new thoughts on X?" for the stalest idea; prevents Ideas from becoming a graveyard
- Notification frequency budget — max 3 nudges/day total, max 2/week per agent; must be built before any scheduler connects to push delivery
- Quiet hours enforcement — no notifications 9pm-8am (UTC-adjusted); server-side check in scheduler

**Should have (P2 — add after core proactive loop is validated):**
- Projects Agent action item extraction — real-time trigger on Projects classification; new `action_item` Cosmos DB document type
- Projects Agent weekly progress check-in — "2 open items on [project]. On track?" — requires action item extraction first
- `last_interaction` field on People documents — written by `classify_and_file` when bucket=People; currently uses capture date as proxy
- Notification action buttons — Expo `setNotificationCategoryAsync` with "Done" + "Snooze 1 week"; backend `/api/nudge/respond` endpoint
- Notification deep links — tap notification lands in relevant capture, not app home screen

**Defer to v3.0+ (P3):**
- Background geofencing — Android terminated-app limitation makes it unreliable for errand reminders; weekend morning time-window covers the value
- Per-person nudge frequency settings — settings creep; add only when explicitly requested
- Calendar integration — OAuth scope complexity; out of bounds for v2.0
- Digest as conversation — complex AG-UI threading redesign not justified for one-way weekly summary

**Key anti-feature to avoid:** Independent per-agent notification scheduling without a shared budget. Four agents firing independently create notification storms that cause iOS notification opt-out — an action that cannot be reversed programmatically.

### Architecture Approach

See `.planning/research/ARCHITECTURE.md` for full details.

The v2.0 architecture centers on five persistent Foundry-backed agents (Classifier + Admin, Projects, People, Ideas specialists) all invoked directly by the FastAPI process. Connected Agents are explicitly ruled out for v2.0 because they cannot call local Python `@tool` functions, and every specialist agent needs Cosmos DB write access via `@tool`. FastAPI acts as the code-based orchestrator: after Classifier determines the bucket, `if/elif` logic selects which specialist to invoke for enrichment.

**Major components:**
1. `AzureAIAgentClient` (in FastAPI lifespan): Single shared client, all five agents created at startup with `should_cleanup_agent=False`. Agent IDs stored in environment variables and reused on restart.
2. `FoundrySSEAdapter` (~150 lines, replaces 340-line `AGUIWorkflowAdapter`): Wraps `classifier_agent.run(stream=True)`, processes `AgentResponseUpdate` events (not `WorkflowEvent`), emits AG-UI events. Complete rewrite of surrounding plumbing; outcome-detection logic and custom event emission are preserved in concept.
3. `APScheduler AsyncIOScheduler` (in FastAPI lifespan): Cron-based triggers for Friday digest, weekly nudges, daily People scans. Shares initialized Cosmos connections and agent objects — this is why Container App Jobs are not used.
4. `PushNotificationService` (`services/push_notifications.py`): Async `httpx` wrapper around Expo Push HTTP API. Fetches stored token from Cosmos Admin container on first call, caches it. Called by scheduler jobs.
5. Specialist agents (`agents/people.py`, `agents/projects.py`, `agents/ideas.py`, `agents/admin.py`): Foundry-backed agents with domain-specific `@tool` functions registered at `as_agent()` creation time.
6. New API endpoints: `POST /api/push-token` (device registration), `POST /api/geofence` (deferred), `POST /api/nudge/respond` (v2.x).

**Confirmed architectural patterns:**
- Tool registration happens at `as_agent(tools=[...])` creation time, not at `run()` time — this is a documented breaking change from `AzureOpenAIChatClient`
- HITL follow-up always creates a fresh Foundry thread to avoid conversation history contamination from the first failed classification pass
- `should_cleanup_agent=False` is mandatory for all persistent agents; agent IDs stored as env vars from day one
- FastAPI is the orchestrator via `if/elif`, not Foundry Connected Agents

**Deleted components:** `agents/orchestrator.py` (Orchestrator eliminated), `agents/workflow.py` (AGUIWorkflowAdapter replaced by FoundrySSEAdapter).

### Critical Pitfalls

See `.planning/research/PITFALLS.md` for full details. 13 pitfalls documented; top 7 are critical.

1. **HandoffBuilder + AzureAIAgentClient incompatibility** — Delete `HandoffBuilder` and `AGUIWorkflowAdapter` before writing any migration code. They cannot coexist. HTTP 400 "invalid payload" on multi-agent runs is the symptom (confirmed GitHub issue #3097). Replacement is code-based FastAPI routing to sequential `agent.run()` calls.

2. **Connected Agents cannot call local @tool functions** — Confirmed in official docs. Sub-agent `requires_action` events are handled server-side; the FastAPI process never receives the callback. The Classifier's Cosmos DB writes silently never execute. Do not use Connected Agents in v2.0. Reserve for v3.0 with Azure Functions.

3. **`should_cleanup_agent=True` (default) destroys persistent agents** — Default deletes the server-side agent resource on `close()`. Container App scale-to-zero triggers cleanup, accumulating hundreds of stale agents and invalidating stored IDs. Use `should_cleanup_agent=False` for all agents.

4. **AGUIWorkflowAdapter is a complete rewrite, not a migration** — The existing adapter checks `WorkflowEvent` types that do not exist in the `AzureAIAgentClient` stream. The new `FoundrySSEAdapter` must handle `AgentResponseUpdate` objects. The outcome-detection logic is reusable in concept but all event-type handling is a replacement. Budget ~150 lines and a full test cycle against the mobile client.

5. **Notification fatigue is irreversible** — iOS notification permission, once revoked, cannot be re-granted programmatically. Build frequency throttling (max 1/agent/day, 3/day total) and quiet hours (9pm-8am) into the notification dispatcher before connecting any scheduler to push delivery. CHI 2025 research confirms: even a modest increase in suggestion frequency can cut user preference for a proactive assistant by half.

6. **Async credential mismatch** — `AzureAIAgentClient` requires `azure.identity.aio.DefaultAzureCredential`. The existing codebase uses the sync version. Update all credential imports before writing any Foundry client code. Do not share credential objects between the Foundry client and other sync Azure clients.

7. **Three RBAC assignments required** — Developer Entra ID + Container App managed identity need "Azure AI User" on Foundry project; Foundry project managed identity needs "Cognitive Services User" on the Azure OpenAI resource. Missing any one causes 403/401 errors that surface only in specific deployment contexts.

---

## Implications for Roadmap

The research establishes a clear dependency chain that determines phase ordering. Foundry infrastructure prerequisites block all SDK work. The Classifier baseline validates the tool execution model before building the adapter. The FoundrySSEAdapter must be proven before HITL validation adds complexity. Push notification infrastructure must be proven before scheduler logic is connected. Throttling must exist before any agent fires a push.

### Phase 1: Foundry Infrastructure and Prerequisites
**Rationale:** Before any code, Azure resources and RBAC must be correct. Three separate RBAC assignments, async credential type, and agent persistence strategy have all caused silent failures that are expensive to diagnose mid-implementation. This phase also includes deleting `HandoffBuilder` and `AGUIWorkflowAdapter` before they can cause confusion — they are dead code from the first line of Foundry migration code.
**Delivers:** AI Foundry Account + Project provisioned; gpt-4o-transcribe deployed in East US2; Application Insights instance wired; all three RBAC assignments verified independently; async credentials in codebase (`azure.identity.aio`); `HandoffBuilder` and `AGUIWorkflowAdapter` deleted; new env vars in `.env` and `config.py`; `agent-framework-azure-ai` installed and import verified.
**Avoids:** Pitfalls 6 (credential mismatch), 7 (RBAC — three assignments), 3 (agent persistence strategy locked in before first agent is created).

### Phase 2: Single-Agent Classifier Baseline
**Rationale:** Validate `AzureAIAgentClient` with the existing Classifier before introducing any new agents. This is the lowest-risk entry point — the Classifier is already functionally proven; only the client type changes. Critically: confirm that `classify_and_file` writes to Cosmos DB when called by the Foundry service. If tool execution fails here, the architecture changes before any adapter or specialist agent work is done.
**Delivers:** Classifier agent visible in Foundry portal with stable ID across restarts; `classify_and_file` confirmed writing to Cosmos DB during a Foundry-managed run; agent ID captured for `AZURE_AI_CLASSIFIER_AGENT_ID` env var; `classifier.py` updated with `AzureAIAgentClient`; `should_cleanup_agent=False` verified working.
**Avoids:** Pitfalls 1 (HandoffBuilder already gone), 2 (tool execution confirmed before building multi-agent layer), 4 (tools registered at creation time, not run time).
**Uses:** `agent-framework-azure-ai`, `azure-ai-projects`, `azure.identity.aio`.

### Phase 3: FoundrySSEAdapter and FastAPI Integration
**Rationale:** With the Classifier baseline confirmed, replace the AG-UI streaming layer. The `FoundrySSEAdapter` (~150 lines) is the riskiest migration component — silent SSE failures are hard to debug once specialist agents add noise to the picture. Validating against the mobile client at this stage means any streaming problems are attributable to the adapter alone.
**Delivers:** `FoundrySSEAdapter` replacing `AGUIWorkflowAdapter`; `main.py` lifespan migrated to `AzureAIAgentClient`; Orchestrator deleted; text and voice capture pipelines working end-to-end; `CLASSIFIED`/`MISUNDERSTOOD`/`UNRESOLVED` custom events verified against mobile app; HITL follow-up confirmed using fresh Foundry threads.
**Avoids:** Pitfall 4 (AGUIWorkflowAdapter rewrite correctly scoped as complete replacement), Pitfall 13 (HITL thread contamination — fresh thread strategy validated here).
**Implements:** `FoundrySSEAdapter` architecture component.

### Phase 4: HITL Validation and Observability
**Rationale:** HITL flows are the highest functional risk because they depend on the adapter's custom event emission and thread management. Validate all three HITL paths explicitly before declaring migration complete. Wire Application Insights and confirm traces, token usage, and cost metrics appear in the Foundry portal.
**Delivers:** All three HITL flows verified end-to-end (low-confidence bucket buttons; misunderstood follow-up with fresh thread; recategorize); Application Insights traces in portal for a classification run; token usage and cost metrics confirmed; v2.0 Foundry migration declared complete.
**Uses:** `configure_azure_monitor()` with `APPLICATIONINSIGHTS_CONNECTION_STRING`; fresh `thread_id` per follow-up endpoint call.

### Phase 5: Specialist Agents (People, Projects, Ideas, Admin)
**Rationale:** With infrastructure, Classifier baseline, and streaming layer proven, the four specialist agents can be added using the same creation pattern. Each agent follows the tool-at-creation-time rule. FastAPI routing code (`if/elif` on classified bucket) is straightforward. Adding agents one at a time and verifying Cosmos DB writes after each reduces debugging surface.
**Delivers:** Four persistent Foundry-backed specialist agents created with IDs stored in env vars; domain tools wired at creation time (`log_interaction`, `add_action_item`, `enrich_idea`, `schedule_reminder`); post-classification enrichment routing in FastAPI endpoint handler; Cosmos DB writes verified for each specialist.
**Avoids:** Pitfall 2 (explicit decision: code-based routing, not Connected Agents), Pitfall 4 (tool registration at creation time).
**Implements:** `agents/people.py`, `agents/projects.py`, `agents/ideas.py`, `agents/admin.py` and corresponding `tools/` files.

### Phase 6: Push Notification Infrastructure
**Rationale:** The entire proactive feature depends on push delivery. This infrastructure phase proves the full cycle (token registration → Expo Push API → APNs/FCM → device) before any agent scheduling is connected. Push receipt polling for `DeviceNotRegistered` detection must be implemented here — not as a later polish step — because silent delivery failures are the second biggest proactive feature risk after notification fatigue.
**Delivers:** `POST /api/push-token` endpoint; `PushNotificationService` with token storage in Cosmos Admin container; Expo push token registration on app startup; receipt polling for `DeviceNotRegistered` detection; notification frequency budget utility (max 3/day total, max 2/week per agent); quiet hours enforcement (9pm-8am); end-to-end push delivery verified with development build (not Expo Go).
**Avoids:** Pitfalls 6 (permission sequence before `getExpoPushTokenAsync()`), 7 (two-stage receipt system implemented), 9 (notification budget built before any scheduler connects).
**Uses:** `exponent-server-sdk 2.2.0`, `expo-notifications`, `expo-device`.

### Phase 7: Proactive Agent Scheduling (APScheduler + Nudge Logic)
**Rationale:** Only after push infrastructure is proven and the notification budget is in place should the scheduler be connected. All specialist agents and the push pipeline are independently proven; this phase composes them into the proactive loop. `gpt-4o-transcribe` replaces Whisper in this phase as well (drop-in, same API call).
**Delivers:** `AsyncIOScheduler` in FastAPI lifespan; Friday digest (Admin Agent, 5pm UTC Friday); People nudge (daily 8am scan, 4-week threshold); Ideas check-in (weekly, stalest idea, Tue-Thu rotation); errand timing (Saturday 9am); quiet hours enforced in all job functions; gpt-4o-transcribe deployed and wired.
**Avoids:** Pitfall 9 (notification fatigue — budget utility from Phase 6 gates all sends), Pitfall 10 (APScheduler timezone configuration with `timezone="Europe/London"` for DST handling).
**Uses:** `APScheduler 3.11.2`, `PushNotificationService`, all specialist agents from Phase 5.
**Implements:** `services/scheduler.py` with all job functions.

### Phase Ordering Rationale

- **Infrastructure before code:** Foundry RBAC, credential type, and resource provisioning are preconditions for all Foundry SDK work. Wrong credential type causes silent failures that obscure real bugs in subsequent phases.
- **One agent before many:** Validating the Classifier in isolation proves the `AzureAIAgentClient` + `@tool` pattern cheaply. Adding four specialist agents to a broken baseline multiplies debugging surface.
- **Streaming adapter early:** The FoundrySSEAdapter is the riskiest migration component and the most mobile-app-visible. Validating it before specialist agents means streaming problems are attributable to the adapter, not to agent interactions.
- **HITL validation before specialist agents:** HITL flows depend on the adapter. Confirming them before Phase 5 means specialist agent work starts from a fully validated foundation.
- **Push infrastructure before scheduling:** Proving delivery independently means scheduling failures are attributable to scheduler code, not to push infrastructure.
- **Throttling before scheduling:** The notification budget utility is built in Phase 6 (push infrastructure) and gates all sends in Phase 7. The order of operations prevents notification fatigue at launch.

### Research Flags

Phases likely needing `/gsd:research-phase` during planning:
- **Phase 3 (FoundrySSEAdapter):** The exact structure of `AgentResponseUpdate` events from a live Foundry agent stream needs empirical validation during Phase 2 standalone testing before writing the Phase 3 event handler. This is a 5-minute smoke test, not a full research phase — but the finding should be documented before Phase 3 planning begins.
- **Phase 7 (APScheduler timezone):** Whether `timezone="Europe/London"` in `AsyncIOScheduler` handles DST correctly in the Azure Container Apps environment is a configuration decision. APScheduler's DST handling is the better default (avoids manual cron updates twice a year), but needs a decision documented before scheduler implementation begins.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Entirely documented via official Azure portal flows and `az cli` commands, plus the official 2026 Significant Changes migration guide.
- **Phase 2:** `AzureAIAgentClient` + local `@tool` pattern documented in official Agent Framework samples with code.
- **Phase 4:** Application Insights is `configure_azure_monitor()` with one env var. HITL thread strategy is an explicit architectural decision, not a research question.
- **Phase 5:** Same creation pattern as Phase 2, repeated four times with domain-specific tools.
- **Phase 6:** Expo push setup extensively documented; receipt polling pattern is well-known from Expo official docs.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official PyPI versions, official Expo SDK 54 docs, official Microsoft Learn docs. The only LOW-confidence item is gpt-4o-transcribe East US2 availability — validate at deployment time. `agent-framework-azure-ai` RC2 status (vs. RC1) is minor version-tracking, not architectural risk. |
| Features | HIGH | Notification UX patterns backed by CHI 2025 research and industry benchmarks (OneSignal, CleverTap). Geofencing limitations confirmed via official Expo docs and open GitHub issues. Agent behavior specifications are prompt engineering decisions, not technical unknowns. |
| Architecture | MEDIUM-HIGH | Foundry integration patterns confirmed via official docs (updated Feb 2026). FoundrySSEAdapter design is sound but `AgentResponseUpdate` event surface needs empirical confirmation during Phase 2. Agent ID persistence, RBAC, and code-based orchestration patterns are high confidence. |
| Pitfalls | HIGH | 13 pitfalls documented with confirmed causes, warning signs, recovery strategies, and phase mappings. HandoffBuilder incompatibility confirmed via GitHub issue #3097. Connected Agents @tool limitation confirmed in official docs. Notification fatigue backed by CHI 2025 research. All four research files independently reach the same conclusions on the top pitfalls. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **FoundrySSEAdapter event surface:** Confirm that `classifier_agent.run(stream=True)` produces `AgentResponseUpdate` objects (not `WorkflowEvent` types) during Phase 2 standalone testing. This takes 5 minutes and removes ambiguity from the Phase 3 implementation. Document the exact content types found in `update.contents` before writing the Phase 3 event handler.

- **APScheduler timezone handling:** `AsyncIOScheduler` supports `timezone="Europe/London"` (via `pytz` or `zoneinfo`) which handles DST automatically. Validate that this works correctly in the Azure Container Apps environment before committing to it in Phase 7. The alternative (UTC offset hardcoded) requires manual cron updates twice a year — documenting this decision explicitly prevents future confusion.

- **gpt-4o-transcribe region availability:** Currently East US2 global standard only. If the Foundry project is in a different region, validate availability at Phase 7 deployment time. Region expansion is ongoing but not guaranteed for all target regions.

- **4 specialist agents + APScheduler memory stability:** Running 5 persistent Foundry agent connections + APScheduler in the same FastAPI lifespan has not been validated in production. Monitor Application Insights for memory growth and thread contention during Phase 7 testing.

- **Android geofencing after force-quit:** Confirmed platform limitation (deferred to v3.0). If v3.0 pursues geofencing, Android OEM behavior (Samsung, Xiaomi, OnePlus treat force-quit as hard kill) must be surfaced in UX design as "best effort" not reliable trigger.

---

## Sources

### Primary (HIGH confidence — official docs, PyPI releases)

- [Microsoft Learn — Azure AI Foundry Provider (Agent Framework)](https://learn.microsoft.com/en-us/agent-framework/agents/providers/azure-ai-foundry) — `AzureAIAgentClient`, `should_cleanup_agent`, credential pattern; updated 2026-02-23
- [Microsoft Learn — Python 2026 Significant Changes Guide](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes) — RC1 breaking changes: unified credential param, `AgentSession` API
- [Microsoft Learn — Connected Agents How-To](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) — max depth 2, no local @tool support; updated 2026-02-25
- [Microsoft Learn — Container Apps Jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs) — scheduled jobs, UTC-only cron limitation; updated 2026-01-28
- [azure-ai-projects on PyPI](https://pypi.org/project/azure-ai-projects/) — v1.0.0 GA, July 31, 2025
- [azure-ai-agents on PyPI](https://pypi.org/project/azure-ai-agents/) — v1.1.0, August 5, 2025
- [APScheduler on PyPI](https://pypi.org/project/APScheduler/) — v3.11.2 stable; v4.0.0a6 alpha only
- [exponent-server-sdk on PyPI](https://pypi.org/project/exponent-server-sdk/) — v2.2.0, July 3, 2025
- [Expo Notifications SDK docs](https://docs.expo.dev/versions/latest/sdk/notifications/) — push token, SDK 54 requirements, dev build required
- [Expo Push Notifications setup](https://docs.expo.dev/push-notifications/push-notifications-setup/) — FCM for Android, APNs for iOS
- [Expo Location SDK docs](https://docs.expo.dev/versions/latest/sdk/location/) — geofencing limitations, iOS 20-region limit, Android force-quit behavior
- [Azure OpenAI Audio Models blog](https://devblogs.microsoft.com/foundry/get-started-azure-openai-advanced-audio-models/) — `gpt-4o-transcribe`, API version, East US2
- [azure-monitor-opentelemetry on PyPI](https://pypi.org/project/azure-monitor-opentelemetry/) — latest stable

### Secondary (MEDIUM confidence — multiple sources agree)

- Agent Framework GitHub issue #3097 — HandoffBuilder + AzureAIAgentClient incompatibility confirmed via PR #4083
- APScheduler + FastAPI lifespan integration — consistent across multiple tutorials; `AsyncIOScheduler` with `CronTrigger` is established pattern
- Expo SDK 54 + expo-notifications dev build requirement — confirmed by SDK 53 and 54 changelogs
- CHI 2025 — "Need Help? Designing Proactive AI Assistants" — notification frequency preference research (frequency increase halves user preference)
- OneSignal — frequency capping research (2-5 notifications/week optimal ceiling)
- [Clarify — Top Personal CRM Apps 2025](https://www.getclarify.ai/blog/top-personal-crm-apps) — Clay, Dex, Covve reconnect nudge patterns
- [Expo Geofencing issue #25875](https://github.com/expo/expo/issues/25875) — Android geofencing not working as expected (open issue)

### Tertiary (LOW confidence — needs validation in implementation)

- 4 specialist agents + APScheduler memory stability in production: not validated; monitor during Phase 7
- FoundrySSEAdapter `AgentResponseUpdate` exact event surface: designed from documentation but needs empirical confirmation during Phase 2 standalone testing
- gpt-4o-transcribe availability outside East US2: regions expand regularly; validate at deployment time
- APScheduler `timezone="Europe/London"` behavior in Azure Container Apps: standard Python behavior but validate in target environment

---
*Research completed: 2026-02-25*
*Ready for roadmap: yes*
