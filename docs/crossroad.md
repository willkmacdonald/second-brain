# Crossroad: Microsoft Agent Framework GA Migration

Assessed: 2026-05-01

## Executive Decision

We should migrate off the current pre-GA `agent-framework-azure-ai` / `AzureAIAgentClient` path. The current code is built on an RC compatibility surface, while current Microsoft Foundry Python guidance uses `agent-framework-foundry` with `agent_framework.foundry.FoundryChatClient` or `FoundryAgent`.

The recommended migration is **not** to move the existing agents wholesale into Foundry prompt agents. The safer target is:

| Agent | Near-term target | Reason |
|---|---|---|
| `Classifier` | App-hosted code agent with `Agent(client=FoundryChatClient(...))` | It owns capture streaming, required tool use, Cosmos writes, safety-net filing, trace propagation, and mobile SSE semantics. |
| `AdminAgent` | App-hosted code agent with `Agent(client=FoundryChatClient(...))` | It performs side effects, retries incomplete tool behavior, and depends on app-owned routing context. |
| `InvestigationAgent` | App-hosted code agent first; evaluate Hosted Agent later | It is tool-heavy and observability-aware, but less latency-critical than the classifier. |
| Future `Connections Agent` | First Hosted Agent candidate | It is scheduled, autonomous, cross-system, and not on the interactive capture path. |

This is a **medium effort / high leverage** migration. It is risky enough to do deliberately, but not a rewrite if we keep the deployment topology stable in wave 1.

## Why This Is A Real Crossroad

The repo is not merely behind on a package version. It depends on a Python API shape that current Microsoft docs say has been removed from the current Foundry namespace.

Current repo evidence:

- `backend/pyproject.toml` depends on `agent-framework-azure-ai`, explicitly commented as RC / prerelease.
- `backend/uv.lock` is pinned to `agent-framework-azure-ai==1.0.0rc2` and `agent-framework-core==1.0.0rc2`.
- `backend/src/second_brain/main.py` imports `AzureAIAgentClient` from `agent_framework.azure` and builds all three production agent clients from it.
- `backend/src/second_brain/streaming/adapter.py`, `streaming/investigation_adapter.py`, `processing/admin_handoff.py`, `eval/runner.py`, `eval/foundry.py`, and `warmup.py` depend on the old `Message` / `ChatOptions` / `get_response()` flow.
- `rg` finds 62 direct references to `AzureAIAgentClient`, `agent_framework.azure`, or `agent-framework-azure-ai`, and 218 broader Agent Framework import/use sites across backend source and tests.

Current Microsoft evidence:

- Microsoft announced Agent Framework 1.0 for Python as production-ready with stable APIs and long-term support: [Microsoft Agent Framework Version 1.0](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/).
- Current Foundry provider docs say Python Foundry clients now live under `agent_framework.foundry`, and recommend `FoundryChatClient` when the app owns instructions/tools and `FoundryAgent` when the agent definition lives in Foundry: [Microsoft Foundry provider docs](https://learn.microsoft.com/en-us/agent-framework/agents/providers/microsoft-foundry).
- The same docs warn that older Python `AzureAIClient`, `AzureAIProjectAgentProvider`, `AzureAIAgentClient`, and `AzureAIAgentsProvider` surfaces were removed from the current `agent_framework.azure` namespace.
- PyPI shows `agent-framework-foundry` as production/stable, while `agent-framework-azure-ai` remains an RC/beta-style package: [agent-framework-foundry](https://pypi.org/project/agent-framework-foundry/) and [agent-framework-azure-ai](https://pypi.org/project/agent-framework-azure-ai/).
- Foundry Hosted Agents remain preview, so using Hosted Agents for the live capture path would add platform risk: [Hosted agents in Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents).

## Strategic Recommendation

Do the migration in two waves.

### Wave 1: GA SDK, Same Hosting Topology

Move the current agents to GA app-hosted code agents:

- replace `agent-framework-azure-ai` with `agent-framework` plus `agent-framework-foundry`;
- replace `AzureAIAgentClient` construction with `FoundryChatClient(...).as_agent(...)` or `Agent(client=FoundryChatClient(...), ...)`;
- move agent instructions out of the portal and into versioned repo files;
- keep local Python tools local;
- keep FastAPI, Container Apps, Cosmos, App Insights, SSE, and mobile contracts unchanged.

This is the lowest-risk path because it changes the SDK/runtime boundary without also changing deployment topology.

### Wave 2: Hosted Agent Pilot

After wave 1 is stable, test Foundry Hosted Agents with a non-critical agent:

- first candidate: `Connections Agent`;
- second candidate: `InvestigationAgent`, only if hosted observability and auth behave well;
- avoid moving `Classifier` until Hosted Agents are out of preview and the custom AG-UI/SSE + required tool-call flow is proven.

## Effort Estimate

| Workstream | Effort | Notes |
|---|---:|---|
| SDK dependency migration | 0.5-1 day | Update `pyproject.toml`, lockfile, imports, local environment. |
| Agent construction refactor | 1-2 days | Build a small internal factory around `FoundryChatClient` / `Agent` so `main.py` does not own every detail. |
| Instructions migration | 1-2 days | Export/copy current portal instructions into repo-managed files for Classifier, Admin, and Investigation. This is required if they become code agents. |
| Streaming adapter migration | 2-3 days | Highest-risk code area. Must map GA stream events to existing SSE events and preserve tool-call/result parsing. |
| Admin background processing | 1 day | Replace non-streaming `get_response()` usage and preserve output-tool retry semantics. |
| Eval path migration | 1-2 days | `eval/runner.py` and app-mediated Foundry eval artifacts depend on the current response/tool-call shape. |
| Observability and middleware | 1-2 days | Validate `enable_instrumentation`, middleware hooks, token metrics, span attributes, and App Insights queries after GA migration. |
| Tests and deployed validation | 2-3 days | Unit tests, local integration fakes, deployed capture smoke test, admin processing smoke test, investigation smoke test. |

Overall wave 1 estimate: **7-12 engineering days** for a production-safe migration.

A thin proof-of-concept that only runs one classifier text capture could be done in **1-2 days**, but that would not retire the operational risk.

Wave 2 Hosted Agent pilot estimate: **3-6 days** for one non-critical agent after wave 1, more if private networking, identity, or protocol support blocks the desired design.

## Impact

### Architecture

This migration clarifies ownership. Today the app uses service-managed Foundry agent identities while injecting local runtime tools. The GA model pushes us to choose:

- **App-owned code agent:** repo owns instructions, tools, middleware, tests, and conversation flow; Foundry supplies model access.
- **Service-managed Foundry agent:** Foundry owns instructions and tools; the app should not try to modify those at runtime.

The current production agents behave like app-owned code agents, even though their instructions live in the portal. The migration should make that true in code and documentation.

### Backend Code

Main affected areas:

- startup wiring in `backend/src/second_brain/main.py`;
- agent registration modules under `backend/src/second_brain/agents/`;
- classifier streaming in `backend/src/second_brain/streaming/adapter.py`;
- investigation streaming in `backend/src/second_brain/streaming/investigation_adapter.py`;
- admin background processing in `backend/src/second_brain/processing/admin_handoff.py`;
- warm-up/self-healing in `backend/src/second_brain/warmup.py`;
- eval execution and artifact generation in `backend/src/second_brain/eval/`;
- tests that mock old response/content/tool-call shapes.

The local `@tool` functions probably survive mostly intact because current docs still support Python function tools and `@tool(approval_mode=...)`. The risky part is not tool definition; it is agent construction, session handling, required tool choice, streaming event shape, and response inspection.

### Product Behavior

The migration must preserve these user-visible contracts:

- every capture ends in `CLASSIFIED`, `LOW_CONFIDENCE`, `MISUNDERSTOOD`, `UNRESOLVED`, `ERROR`, and `COMPLETE` SSE events as expected by mobile;
- classifier safety net still files a misunderstood item when the model skips `file_capture`;
- follow-up classification keeps the right conversation/thread continuity;
- admin processing still marks inbox items pending/completed/failed and retries when only intermediate tools run;
- investigation still streams readable text, tool-call progress, and final thread IDs;
- evals still produce comparable accuracy/routing metrics.

### Operations

Expected operational changes:

- agent instruction changes become code changes instead of portal edits;
- environment variables likely shift from agent IDs toward model names and optional Foundry agent names/versions;
- existing Foundry prompt-agent IDs may no longer be the primary runtime identity for app-hosted code agents;
- App Insights dimensions and Foundry trace IDs may change and need query updates;
- warm-up logic may need to warm `Agent` sessions or client calls differently.

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|---|---:|---:|---|
| Streaming event shape differs from RC client | High | High | Build a narrow adapter layer and run golden SSE contract tests before deploying. |
| Required tool-call behavior changes | High | Medium | Prove `file_capture` can still be forced or implement a stricter app-side validation/retry loop. |
| Conversation/thread continuity changes | High | Medium | Add explicit tests for low-confidence follow-up using the same conversation/session. |
| Portal instructions are incomplete or drifted | High | High | Export current Classifier/Admin/Investigation instructions before changing runtime. Store in repo. |
| Observability regressions | Medium | High | Compare App Insights traces before/after for token metrics, span names, agent names, capture trace IDs, tool spans. |
| Eval comparability breaks | Medium | Medium | Run pre-migration baseline eval, then require post-migration scores within agreed tolerance. |
| Hosted Agent preview constraints block production use | Medium | Medium | Keep Hosted Agents out of the critical capture path until proven and no longer preview for required capabilities. |
| Identity/RBAC changes cause deployed-only failures | High | Medium | Deploy to staging first using managed identity, Key Vault, Cosmos, App Insights, and Foundry RBAC checks. |

## Recommended Migration Plan

### Phase 0: Freeze And Baseline

Before touching code:

1. Export current Foundry portal instructions for `Classifier`, `AdminAgent`, and `InvestigationAgent`.
2. Run the existing backend tests.
3. Run one deployed smoke capture for text, voice if configured, admin routing, and investigation.
4. Run current classifier/admin evals and save scores as migration baseline.
5. Capture one App Insights trace for each agent path.

Exit criteria:

- we have current instructions in repo;
- we know current eval scores;
- we have trace examples to compare after migration.

### Phase 1: Build A GA Agent Runtime Facade

Add a small internal wrapper so the rest of the app does not depend directly on `FoundryChatClient` or `Agent` details. The facade should expose only what the app needs:

- non-streaming run;
- streaming run;
- optional session/conversation continuity;
- tools;
- middleware/observability hooks;
- warm-up ping.

This limits future SDK churn to one module.

### Phase 2: Migrate Classifier First

Classifier is the highest-risk path, so it should move first in isolation.

Required checks:

- text capture files to Cosmos;
- safety net still fires when no tool result is observed;
- low-confidence follow-up reuses the right conversation/session;
- SSE event order matches mobile expectations;
- `captureTraceId` remains available on Cosmos records and App Insights spans.

### Phase 3: Migrate Admin

Required checks:

- routing context still gets injected;
- output-producing tool detection still works;
- intermediate-tool retry still works;
- inbox status transitions are unchanged;
- recipe tool remains optional and non-fatal.

### Phase 4: Migrate Investigation And Evals

Required checks:

- investigation text stream is still the primary response;
- tool-call progress events still render;
- eval dry-run tools capture expected predictions;
- Foundry eval app-mediated artifact generation still captures response/tool-call data or is redesigned around the GA response shape.

### Phase 5: Deployed Validation

Deploy to staging and require:

- health endpoint passes;
- text capture passes;
- admin capture passes;
- investigation query passes;
- eval smoke run passes;
- App Insights trace and Foundry trace are discoverable;
- no mobile client changes are required.

## Go / No-Go Criteria

Go if:

- GA classifier can preserve SSE and filing behavior;
- required tool-call or equivalent app-side enforcement works;
- instructions are safely versioned in repo;
- baseline evals do not materially regress;
- observability still provides enough traceability for RCA.

No-go / pause if:

- GA streaming does not expose enough tool-call/result detail to preserve current behavior;
- conversation/session continuation cannot support follow-up classification;
- Foundry project auth or deployed managed identity behavior is unstable;
- migration would require simultaneous mobile protocol changes.

## Recommendation

Proceed with wave 1 now: **GA SDK migration while keeping agents app-hosted**.

Do not spend engineering time trying to make the existing Classifier/Admin/Investigation agents pure Foundry prompt agents. That would fight the shape of the app. Their value comes from code-owned tools, app-owned state transitions, and backend-controlled streaming.

Use Hosted Agents only as a later pilot for a non-critical code agent. The future `Connections Agent` is the right proving ground because it is background, scheduled, and not coupled to the capture UX.

