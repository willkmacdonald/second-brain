# Stack Research

**Domain:** Multi-agent proactive personal knowledge management
**Project:** Active Second Brain — v2.0 Foundry Migration + Proactive Specialist Agents
**Researched:** 2026-02-25
**Confidence:** HIGH for packages/versions from official sources; MEDIUM for geofencing reliability (known open issues); LOW for Foundry specialist agent orchestration pattern (no direct precedent found)

---

## Context: What This Covers

This document covers all **new or changed** stack elements for the v2.0 milestone. The existing validated stack (FastAPI, Expo/React Native, Cosmos DB, Blob Storage, Azure Container Apps, Ruff, uv) is unchanged. Six new capability areas are addressed:

1. **Foundry Agent Service migration** — `AzureAIAgentClient` + specialist agents per bucket
2. **gpt-4o-transcribe** — replaces Whisper for voice transcription
3. **Expo push notifications** — backend-triggered proactive alerts to the mobile app
4. **Background geofencing** — location-triggered captures on the mobile side
5. **Scheduled agent execution** — cron-like Friday digests, weekly nudges, project follow-ups
6. **Enhanced observability** — Application Insights wired to Foundry agents

---

## New and Changed Packages

### Python Backend Additions

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `agent-framework-azure-ai` | `1.0.0rc1` (RC, install `--pre`) | `AzureAIAgentClient` for Foundry Agent Service | The Agent Framework connector to Foundry. Without this, agent runs are local in-memory; with it, agents are persistent server-side resources with Foundry-managed threads. |
| `azure-ai-projects` | `1.0.0` (GA) | `AIProjectClient` for agent CRUD — create, delete, list persistent agents | Required for managing agent lifecycle: creating the 4 specialist agents at startup, storing their IDs in env vars. Released July 31, 2025. |
| `azure-ai-agents` | `1.1.0` (GA) | `ConnectedAgentTool` model and lower-level agents SDK | Pulled in transitively by `azure-ai-projects` but pin explicitly for `ConnectedAgentTool` type imports. Released August 5, 2025. |
| `azure-monitor-opentelemetry` | `1.6.0` | Application Insights via OpenTelemetry distro (`configure_azure_monitor()`) | One-call setup routes all OTel spans, logs, and metrics to Application Insights. The `azure-monitor-opentelemetry-distro` package name is deprecated — use this one. |
| `APScheduler` | `3.11.2` (stable) | `AsyncIOScheduler` with cron triggers for scheduled agent execution | Production-stable Python job scheduler. v4 is still alpha (4.0.0a6 as of Apr 2025) — do not use. `AsyncIOScheduler` integrates with FastAPI's asyncio event loop and is started/stopped via lifespan context manager. |
| `exponent-server-sdk` | `2.2.0` (stable, sync) | Send Expo push notifications from Python backend | Official Python SDK for Expo Push Service. Use the sync version (`exponent-server-sdk`) because push notifications are fire-and-forget calls from scheduler jobs, not from async FastAPI routes. If called from a FastAPI route, use `asyncio.get_event_loop().run_in_executor()` or `httpx.AsyncClient` directly. |

### Python Backend — Keep Unchanged

| Package | Notes |
|---------|-------|
| `agent-framework-core` | Still required — provides `Agent`, `Message`, `@tool`, `AgentSession` |
| `agent-framework-orchestrations` | Required only if HandoffBuilder stays; may be removed after migration |
| `agent-framework-ag-ui` | AG-UI SSE endpoint unchanged |
| `azure-identity` | `DefaultAzureCredential` / `AzureCliCredential` — unified `credential=` param since RC1 |
| `azure-cosmos`, `azure-storage-blob`, `azure-keyvault-secrets` | All unchanged |
| `openai` | Still required for `AsyncAzureOpenAI` — now used for `gpt-4o-transcribe` instead of Whisper |
| `fastapi`, `uvicorn`, `aiohttp` | Unchanged |
| `pydantic-settings`, `python-dotenv` | Still in use for `Settings` class (AF internals dropped pydantic-settings in RC1 but your code still uses it) |

### Python Backend — Remove

| Package | Why Remove |
|---------|-----------|
| `agent-framework-orchestrations` | Remove once HandoffBuilder orchestration code is deleted (v2.0 replaces with code-based routing) |
| Nothing else | All other existing packages stay |

### Mobile (Expo/React Native) Additions

Current mobile: `expo ~54.0.33`, `react-native 0.81.5`

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `expo-notifications` | `~0.32.x` (SDK 54 compatible) | Receive push notification tokens, display notifications, handle notification tap events | Official Expo push notification library. Required for backend-triggered proactive alerts. As of SDK 54, does not work in Expo Go — requires a development build for testing. |
| `expo-device` | `~7.0.x` (SDK 54 compatible) | Check if running on a physical device before requesting push token | Required by `expo-notifications` — prevents push token requests on simulators/emulators where it always fails. |
| `expo-location` | `~19.0.8` (SDK 54 compatible) | `startGeofencingAsync` + `stopGeofencingAsync` for background region monitoring | Official Expo geofencing API. Works with `expo-task-manager` to trigger background tasks when device enters/exits a region. |
| `expo-task-manager` | `~1.1.x` (SDK 54 compatible) | Define background task handlers for geofencing events | Required companion to `expo-location` geofencing. Task definitions must be at the top-level module scope, not inside React components. |

### Mobile — Keep Unchanged

| Package | Notes |
|---------|-------|
| All existing packages | `expo-audio`, `expo-constants`, `expo-router`, `@ag-ui/core`, etc. — zero changes |

---

## pyproject.toml Changes (Backend)

```toml
[project]
dependencies = [
    # Agent Framework + AG-UI (RC - requires --prerelease=allow)
    "agent-framework-ag-ui",
    # Remove agent-framework-orchestrations after HandoffBuilder deletion
    # NEW: Foundry Agent Service integration
    "agent-framework-azure-ai",
    # Azure services (existing)
    "azure-cosmos",
    "azure-identity",
    "azure-keyvault-secrets",
    "azure-storage-blob",
    # NEW: Foundry Agent lifecycle management
    "azure-ai-projects>=1.0.0",
    "azure-ai-agents>=1.1.0",
    # NEW: Application Insights via OTel distro
    "azure-monitor-opentelemetry>=1.6.0",
    # NEW: Scheduled agent execution (proactive digests, nudges, follow-ups)
    "APScheduler>=3.11.2,<4.0",
    # NEW: Expo push notifications from backend
    "exponent-server-sdk>=2.2.0",
    # Unchanged
    "aiohttp",
    "openai",
    "python-multipart",
    "pydantic-settings",
    "python-dotenv",
]
```

Install commands:

```bash
# Foundry Agent Service
uv pip install agent-framework-azure-ai --prerelease=allow
uv pip install "azure-ai-projects>=1.0.0" "azure-ai-agents>=1.1.0"
# Observability
uv pip install "azure-monitor-opentelemetry>=1.6.0"
# Scheduler
uv pip install "APScheduler>=3.11.2,<4.0"
# Push notifications
uv pip install "exponent-server-sdk>=2.2.0"
```

## mobile/package.json Changes

```bash
# Push notifications
npx expo install expo-notifications expo-device
# Geofencing
npx expo install expo-location expo-task-manager
```

Resulting additions to `dependencies`:

```json
{
  "expo-notifications": "~0.32.0",
  "expo-device": "~7.0.0",
  "expo-location": "~19.0.0",
  "expo-task-manager": "~1.1.0"
}
```

Use `npx expo install` (not `npm install`) — it picks versions compatible with your exact SDK.

---

## Azure Resources: New Additions

| Resource | Type | Notes |
|----------|------|-------|
| AI Foundry Account | `Microsoft.CognitiveServices/accounts` | New resource type (NOT old Hub-based ML workspace). Created via Foundry portal. |
| Foundry Project | Child of AI Foundry Account | Provides `https://<account>.services.ai.azure.com/api/projects/<project>` endpoint. |
| gpt-4o-transcribe deployment | Model deployment in Foundry Project | Deploy `gpt-4o-transcribe` model; use East US2 region (currently the only region with global standard availability). |
| Application Insights | `Microsoft.Insights/components` | Connected to Container App and Foundry project for agent run traces, token usage, cost. |
| Container App Jobs (optional) | Scheduled Container App Jobs | Alternative to APScheduler for digest/nudge jobs. Runs on cron without occupying the always-on Container App. See "Scheduling Strategy" section below. |

---

## New Environment Variables

| Variable | Format | Source |
|----------|--------|--------|
| `AZURE_AI_PROJECT_ENDPOINT` | `https://<account>.services.ai.azure.com/api/projects/<project>` | Foundry portal → Project overview |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | `gpt-4o` | Foundry portal → Models + Endpoints |
| `AZURE_AI_TRANSCRIBE_DEPLOYMENT_NAME` | `gpt-4o-transcribe` | Foundry portal → Models + Endpoints |
| `AZURE_AI_ADMIN_AGENT_ID` | Foundry agent ID (stable after creation) | Output from agent creation script |
| `AZURE_AI_PROJECTS_AGENT_ID` | Foundry agent ID | Output from agent creation script |
| `AZURE_AI_PEOPLE_AGENT_ID` | Foundry agent ID | Output from agent creation script |
| `AZURE_AI_IDEAS_AGENT_ID` | Foundry agent ID | Output from agent creation script |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `InstrumentationKey=...;IngestionEndpoint=...` | Azure portal → Application Insights → Overview |
| `EXPO_PUSH_ACCESS_TOKEN` | String token | Expo EAS dashboard (optional; Expo Push API works without token for development) |

---

## SDK Integration Patterns

### 1. AzureAIAgentClient — Foundry-backed Specialist Agents

Four specialist agents (Admin, Projects, People, Ideas) replace the previous Orchestrator + Classifier. Each is a persistent Foundry agent with a stable ID:

```python
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential

# At FastAPI lifespan startup — create or reference persistent agents
async with DefaultAzureCredential() as credential:
    client = AzureAIAgentClient(credential=credential)

    # Register agent once; subsequent runs reference the stable ID
    admin_agent = await client.as_agent(
        name="AdminAgent",
        instructions="You are the Admin specialist...",
        tools=[classify_and_file, request_misunderstood],
        should_cleanup_agent=False,  # REQUIRED: persist across restarts
    )
```

Each agent is created once and its ID stored in an environment variable (`AZURE_AI_ADMIN_AGENT_ID`). The FastAPI lifespan loads by ID on subsequent starts:

```python
# config.py
azure_ai_admin_agent_id: str = ""  # populated from env or agent creation
```

### 2. gpt-4o-transcribe — Drop-in Whisper Replacement

Same API surface as Whisper — same `audio.transcriptions.create()` method, just different model name and API version:

```python
from openai import AsyncAzureOpenAI

async with AsyncAzureOpenAI(
    azure_endpoint=settings.azure_openai_endpoint,
    api_version="2025-03-01-preview",  # Required for gpt-4o-transcribe
    azure_ad_token_provider=token_provider,
) as client:
    transcript = await client.audio.transcriptions.create(
        model=settings.azure_ai_transcribe_deployment_name,  # "gpt-4o-transcribe"
        file=audio_file,
        response_format="text",
    )
```

No changes to the `@tool` decorator or the agent wiring — only the model name and API version change.

### 3. APScheduler — Scheduled Agent Execution

`AsyncIOScheduler` runs in the same event loop as FastAPI. Started/stopped via lifespan context manager:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager

scheduler = AsyncIOScheduler(timezone="UTC")

@scheduler.scheduled_job(CronTrigger(day_of_week="fri", hour=17, minute=0))
async def friday_digest():
    """Run the Digest agent every Friday at 5pm UTC."""
    session = digest_agent.create_session()
    await digest_agent.run("Generate this week's summary", session=session)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()
```

Jobs are in-memory only (lost on restart) which is acceptable for scheduled digests — the next scheduled run catches up. No persistent jobstore required for this use case.

**Alternative: Container App Jobs.** For digest/nudge jobs that should run even if the main Container App is scaled to zero, consider Azure Container App Scheduled Jobs (cron trigger, separate container, free when not running). This adds deployment complexity but decouples scheduling from the always-on service. Decision deferred to planning phase.

### 4. Expo Push Notifications — Backend to Mobile

**Mobile side (token registration):**

```typescript
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';

async function registerForPushNotificationsAsync(): Promise<string | null> {
    if (!Device.isDevice) return null;  // Simulators can't receive pushes

    const { status } = await Notifications.requestPermissionsAsync();
    if (status !== 'granted') return null;

    const token = await Notifications.getExpoPushTokenAsync({
        projectId: Constants.expoConfig?.extra?.eas?.projectId,
    });
    return token.data;  // "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]"
}
```

Token is stored on the backend (new `devices` or `admin` Cosmos DB document per user).

**Backend side (sending):**

```python
from exponent_server_sdk import PushClient, PushMessage

def send_push_notification(expo_token: str, title: str, body: str) -> None:
    response = PushClient().publish(
        PushMessage(to=expo_token, title=title, body=body)
    )
    response.validate_response()
```

`exponent-server-sdk` uses `requests` (sync) internally. Call from APScheduler jobs directly. For FastAPI async routes, wrap in `asyncio.get_event_loop().run_in_executor(None, send_push_notification, ...)` if needed.

### 5. Background Geofencing — Mobile Side

Geofencing requires `expo-location` + `expo-task-manager`. Task definition must be at the **top-level module scope**, not inside React components:

```typescript
// app/_layout.tsx (top-level, before any exports)
import * as TaskManager from 'expo-task-manager';
import * as Location from 'expo-location';

const GEOFENCE_TASK = 'LOCATION_GEOFENCE';

TaskManager.defineTask(GEOFENCE_TASK, ({ data, error }) => {
    if (error) { console.error(error); return; }
    const { eventType, region } = data as any;
    if (eventType === Location.GeofencingEventType.Enter) {
        // Trigger a capture prompt or send to backend
    }
});

// Start monitoring (after requesting background location permission)
await Location.startGeofencingAsync(GEOFENCE_TASK, [
    { latitude: 37.7749, longitude: -122.4194, radius: 100 }
]);
```

**Key limitations:**
- iOS: max 20 regions simultaneously
- Android: terminated app does NOT restart on geofence event (unlike iOS)
- Both platforms: requires "always" background location permission (triggers App Store review scrutiny)
- Requires development build — does not work in Expo Go
- Known open issues with event firing on app open (GitHub issue #33433) — validate in phase testing

### 6. Application Insights — Foundry Agent Observability

One call at FastAPI startup, before the app is created:

```python
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    connection_string=settings.applicationinsights_connection_string
)
```

Agent Framework's existing OpenTelemetry spans route automatically to Application Insights. No agent code changes. Specialist agent runs appear as separate traces with:
- Per-agent token usage
- Tool call duration (classify_and_file, transcribe_audio)
- Classification outcome as a span attribute
- Cost per run (computed from token counts)

---

## Scheduling Strategy: APScheduler vs Container App Jobs

| Approach | When to Use | Pros | Cons |
|----------|-------------|------|------|
| **APScheduler in-process** | Digest/nudge jobs that must access agent objects already in memory | Zero extra infra, co-located with agents, simple deployment | Scheduling state lost on restart; requires always-on Container App instance |
| **Azure Container App Jobs** | Jobs that run even when main app is scaled to zero; jobs that are long-running or CPU-intensive | Decoupled from main app, free when idle, proper retry/history tracking | Extra deployment artifact; can't directly share agent objects — must call via HTTP API |

**Recommendation for v2.0:** Start with APScheduler in-process. The Friday digest and weekly nudges are lightweight tasks that benefit from sharing the already-initialized Foundry agent connections. If the main app needs to scale to zero (not currently required), migrate digest jobs to Container App Jobs in v3.0.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `agent-framework-core 1.0.0rc1` | `agent-framework-azure-ai 1.0.0rc1` | Both promoted to RC1 together Feb 19, 2026. Use same RC tag. |
| `azure-ai-projects 1.0.0` | `azure-ai-agents 1.1.0` | `azure-ai-agents` is a dependency of `azure-ai-projects`. Pin both to avoid drift. |
| `azure-monitor-opentelemetry 1.6.0` | `opentelemetry-sdk` (managed) | Do NOT manually pin `opentelemetry-sdk` — let the distro control it to avoid conflicts. |
| `expo ~54.0.33` | `expo-notifications ~0.32.x` | Use `npx expo install` to get exact SDK-54-compatible version; do not manually pick versions. |
| `expo ~54.0.33` | `expo-location ~19.0.8` | Same — use `npx expo install`. |
| `APScheduler 3.11.x` | Python `>=3.8` | v3 stable; v4 is alpha (do not use in production). |
| `gpt-4o-transcribe` | `openai` Python SDK `>=1.0` + `api_version="2025-03-01-preview"` | Requires preview API version; standard `2024-xx-xx` versions return 404 for this model. |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `APScheduler 4.x` | Still in alpha (4.0.0a6 as of April 2025); breaking API changes from v3 | `APScheduler 3.11.x` — stable, well-documented, same AsyncIOScheduler pattern |
| `azure-monitor-opentelemetry-distro` | Deprecated package name | `azure-monitor-opentelemetry` |
| Direct `opentelemetry-sdk` pin | Version conflicts with distro's internal pins | Let `azure-monitor-opentelemetry` control OTel versions |
| Hub-based AI Foundry project | Deprecated since May 2025; incompatible with current SDK/REST API | New `Microsoft.CognitiveServices/accounts` Foundry resource |
| `expo-background-fetch` | Deprecated in SDK 52, removed in SDK 53+ | `expo-background-task` (if periodic background polling is needed) or geofencing via `expo-location` |
| `expo-background-task` for geofencing | This is for periodic background polling, not geofencing | `expo-location.startGeofencingAsync()` for location-triggered events |
| `exponent-server-sdk-async` | Last maintained version unclear; the sync SDK works for scheduled jobs | `exponent-server-sdk 2.2.0` (sync, actively maintained, released July 2025) |
| `HandoffBuilder` / `AGUIWorkflowAdapter` | Incompatible with multi-specialist-agent design; local-only orchestration with no portal visibility | Code-based routing in FastAPI: inspect the capture type, choose the specialist agent directly |
| `ConnectedAgentTool` for specialist routing | Connected Agents max depth is 2, and subagents CANNOT call local `@tool` functions (requires Azure Functions) | Code-based routing: FastAPI reads capture type and directly invokes the matching specialist agent |

---

## Alternatives Considered

| Recommended | Alternative | Why Not Alternative |
|-------------|-------------|---------------------|
| APScheduler in FastAPI lifespan | Azure Container App Jobs | APScheduler is simpler and shares initialized agent connections. Container App Jobs are better for zero-scale scenarios (not currently needed). |
| `exponent-server-sdk` (sync) | Direct `httpx.post` to Expo Push API | SDK handles token validation, chunking, receipt checking. httpx is fine but more boilerplate for the same outcome. |
| `expo-location` geofencing | Third-party geofencing libraries (react-native-geolocation) | `expo-location` is officially maintained and integrates with `expo-task-manager`. Third-party libraries require bare workflow (ejecting from managed Expo). |
| Code-based routing to specialist agents | Connected Agents (Foundry server-side) | Connected Agents cannot call local Python `@tool` functions — all tools would need to move to Azure Functions. v3.0 concern, not v2.0. |
| `gpt-4o-transcribe` | `whisper-1` (keep existing) | `gpt-4o-transcribe` is ~50% lower word error rate and is the forward-looking Azure audio model. Drop-in replacement for the `audio.transcriptions.create()` call — no refactoring needed. |

---

## Sources

### HIGH Confidence (Official docs, PyPI, official release notes)

- [Microsoft Agent Framework — Azure AI Foundry Provider (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/agents/providers/azure-ai-foundry) — `AzureAIAgentClient`, `should_cleanup_agent`, credential pattern; updated 2026-02-23
- [Python 2026 Significant Changes Guide (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes) — RC1 breaking changes: unified credential param, `AgentSession` API
- [Connected Agents How-To (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) — max depth 2 limitation, no local `@tool` support; updated 2026-02-25
- [Azure Container Apps Jobs (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/container-apps/jobs) — scheduled jobs with cron expressions, trigger types; updated 2026-01-28
- [Agent Background Responses (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-background-responses) — continuation token pattern, Python support "coming soon" for background responses
- [azure-ai-projects on PyPI](https://pypi.org/project/azure-ai-projects/) — Version 1.0.0 GA, July 31, 2025
- [azure-ai-agents on PyPI](https://pypi.org/project/azure-ai-agents/) — Version 1.1.0, August 5, 2025
- [azure-monitor-opentelemetry on PyPI](https://pypi.org/project/azure-monitor-opentelemetry/) — Latest stable
- [APScheduler on PyPI](https://pypi.org/project/APScheduler/) — v3.11.2 stable (Dec 22, 2025); v4.0.0a6 alpha only
- [exponent-server-sdk on PyPI](https://pypi.org/project/exponent-server-sdk/) — v2.2.0 (July 3, 2025)
- [expo-notifications (Expo Docs)](https://docs.expo.dev/versions/latest/sdk/notifications/) — Installation, `getExpoPushTokenAsync`, SDK 54 requirements (dev build required)
- [expo-notifications Push Setup (Expo Docs)](https://docs.expo.dev/push-notifications/push-notifications-setup/) — Setup steps, FCM for Android, APNs for iOS
- [expo-location (Expo Docs)](https://docs.expo.dev/versions/latest/sdk/location/) — `startGeofencingAsync`, permissions, iOS 20-region limit, Android termination behavior
- [expo-task-manager (Expo Docs)](https://docs.expo.dev/versions/latest/sdk/task-manager/) — Top-level `defineTask` requirement, platform support
- [Expo SDK 54 Changelog](https://expo.dev/changelog/sdk-54) — expo-notifications deprecated exports removed; React Native 0.81
- [Azure OpenAI Audio Models blog (Microsoft Foundry Blog)](https://devblogs.microsoft.com/foundry/get-started-azure-openai-advanced-audio-models/) — `gpt-4o-transcribe`, `api_version="2025-03-01-preview"`, East US2 availability
- [gpt-4o-transcribe on OpenAI platform](https://platform.openai.com/docs/models/gpt-4o-transcribe) — model name, response formats, comparison to whisper-1

### MEDIUM Confidence (Verified against secondary sources)

- APScheduler + FastAPI lifespan pattern — consistent across multiple tutorials/Stack Overflow; use of `AsyncIOScheduler` with `CronTrigger` is the established pattern
- `exponent-server-sdk` sync call from scheduler jobs — standard pattern; async variant (`exponent-server-sdk-async`) has unclear maintenance status
- Expo SDK 54 + expo-notifications requiring dev build — confirmed by SDK 53 and 54 changelogs; consistent with Expo's ongoing deprecation of Expo Go for advanced features

### LOW Confidence (Needs validation in implementation phase)

- **Geofencing on Android after app termination**: Official docs say terminated Android app does NOT restart on geofence event. iOS does restart. This means Android geofencing silently stops working after the user kills the app. If geofencing is a key feature, this limitation needs to be surfaced in UX (e.g., a status indicator showing geofencing is active).
- **4 specialist agents + APScheduler stability**: Running 4 persistent Foundry agents + a scheduler in the same FastAPI lifespan has not been validated. Monitor for memory growth and thread contention during testing.
- **gpt-4o-transcribe East US2 only**: Currently `global standard` deployment type only in East US2. If the Foundry project is in a different region, check current availability at deployment time — regions expand regularly but not guaranteed at time of writing.

---

*Stack research for: Active Second Brain v2.0 — Foundry migration + proactive specialist agents + push notifications + geofencing + scheduled execution*
*Researched: 2026-02-25*
