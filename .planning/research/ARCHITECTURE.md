# Architecture Patterns: Proactive Multi-Agent Second Brain on Foundry Agent Service

**Domain:** Proactive AI agents + FastAPI + Cosmos DB + Expo push notifications + geofencing
**Researched:** 2026-02-25
**Confidence:** HIGH for core Foundry integration, MEDIUM for scheduling patterns, HIGH for push/geofencing (official Expo docs), MEDIUM for agent state patterns (newer Cosmos BYO thread storage)

---

## Critical Constraint Recap (From Prior Research)

This document builds on the confirmed constraints from the Foundry Agent Service migration research:

- **Connected Agents cannot call local @tool functions** — confirmed in official docs: "Connected agents cannot call local functions using the function calling tool. We recommend using the OpenAPI tool or Azure Functions instead." (Source: Microsoft Learn, updated 2026-02-25)
- **Connected Agents are deprecated in the new Foundry portal** — replaced by Workflows (`2025-11-15-preview` API). The classic Connected Agents pattern uses `2025-05-15-preview`.
- **`should_cleanup_agent=False` is required** for persistent agents across Container App restarts.
- **`AzureAIAgentClient` requires `azure.identity.aio.DefaultAzureCredential`** (async credential).
- **`AGUIWorkflowAdapter`** must be replaced with a new `FoundrySSEAdapter` (~150 lines).

The new architecture for proactive specialist agents must navigate the @tool constraint: any specialist agent that writes to Cosmos DB **cannot** use Connected Agents. It must run as an independent persistent Foundry agent invoked directly by the FastAPI process, not server-side by another agent.

---

## System Overview: After Proactive Agents Added

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Mobile App (Expo)                                  │
│   Push Notifications   AG-UI SSE Client    Expo Location (Geofencing)      │
│         ▲                    │  ▲                     │                    │
└─────────┼────────────────────┼──┼─────────────────────┼────────────────────┘
          │ Push               │  │ SSE events           │ Enter/Exit events
          │                    ▼  │                      ▼
     ┌─────────┐    ┌────────────────────────────────────────────────────────┐
     │  Expo   │    │               FastAPI (Azure Container Apps)           │
     │  Push   │◄───│                                                        │
     │ Service │    │  ┌── Lifespan ─────────────────────────────────────┐   │
     └─────────┘    │  │  AzureAIAgentClient (async credential)          │   │
                    │  │  ClassificationTools (→ Cosmos DB)               │   │
                    │  │  PeopleTools / ProjectTools / etc. (→ Cosmos DB) │   │
                    │  │  Persistent agents: Classifier, People,          │   │
                    │  │    Projects, Ideas, Admin (IDs from env vars)    │   │
                    │  │  APScheduler (cron: digests, nudges, follow-ups) │   │
                    │  │  PushNotificationService (httpx → Expo API)      │   │
                    │  └──────────────────────────────────────────────────┘   │
                    │                                                          │
                    │  POST /api/ag-ui         → FoundrySSEAdapter            │
                    │  POST /api/voice-capture → Blob + Whisper + Classifier  │
                    │  POST /api/ag-ui/respond → Direct Cosmos write          │
                    │  POST /api/ag-ui/follow-up → Classifier re-run         │
                    │  POST /api/push-token    → Store Expo token in Cosmos   │
                    │  POST /api/geofence      → Trigger location-based agent │
                    │  GET  /api/inbox         → Inbox CRUD (unchanged)       │
                    └────────────────┬─────────────────────────────────────────┘
                                     │
               ┌─────────────────────┴──────────────────────┐
               ▼                                            ▼
   ┌───────────────────────┐              ┌────────────────────────────────────┐
   │       Cosmos DB       │              │       Azure AI Foundry              │
   │  - Inbox (captures)   │              │                                    │
   │  - People             │◄─────────────│  Classifier Agent (persistent)     │
   │  - Projects           │  @tool calls │  People Agent (persistent)         │
   │  - Ideas              │  from FastAPI│  Projects Agent (persistent)       │
   │  - Admin              │  process     │  Ideas Agent (persistent)          │
   │  - Admin (push tokens)│              │  Admin Agent (persistent)          │
   └───────────────────────┘              └────────────────────────────────────┘
```

---

## Component Boundaries

### Existing Components (v2.0 Migration — Unchanged or Modified)

| Component | Responsibility | Change vs Current |
|-----------|---------------|-------------------|
| `main.py` | FastAPI app, lifespan, SSE endpoints | MODIFIED: AzureAIAgentClient, APScheduler, PushNotificationService |
| `config.py` | Settings via pydantic-settings | MODIFIED: push token env vars, scheduler config |
| `agents/classifier.py` | Classifier Agent creation | MODIFIED: AzureAIAgentClient |
| `agents/workflow.py` | SSE streaming adapter | REPLACED: AGUIWorkflowAdapter → FoundrySSEAdapter |
| `agents/orchestrator.py` | Orchestrator agent | DELETED |
| `tools/classification.py` | classify_and_file, request_misunderstood, mark_as_junk | UNCHANGED |
| `tools/transcription.py` | Whisper transcription | UNCHANGED |
| `db/cosmos.py` | CosmosManager singleton | UNCHANGED |
| `db/blob_storage.py` | BlobStorageManager singleton | UNCHANGED |
| `auth.py` | APIKeyMiddleware | UNCHANGED |
| `api/inbox.py` | Inbox CRUD REST endpoints | UNCHANGED |
| `api/health.py` | Health check | UNCHANGED |
| `models/documents.py` | Cosmos document models | UNCHANGED |

### New Components (Proactive Agents Milestone)

| Component | Responsibility | Where It Lives |
|-----------|---------------|----------------|
| `agents/people.py` | People Agent creation (Foundry-backed) | NEW file |
| `agents/projects.py` | Projects Agent creation (Foundry-backed) | NEW file |
| `agents/ideas.py` | Ideas Agent creation (Foundry-backed) | NEW file |
| `agents/admin.py` | Admin Agent creation (Foundry-backed) | NEW file |
| `tools/people_tools.py` | @tool functions: log_interaction, add_follow_up | NEW file |
| `tools/projects_tools.py` | @tool functions: update_project_status, add_action_item | NEW file |
| `tools/ideas_tools.py` | @tool functions: enrich_idea, link_related | NEW file |
| `tools/admin_tools.py` | @tool functions: schedule_reminder, create_task | NEW file |
| `services/push_notifications.py` | PushNotificationService: store token, send notification | NEW file |
| `services/scheduler.py` | APScheduler setup, job registration | NEW file |
| `api/push_token.py` | POST /api/push-token (register device) | NEW file |
| `api/geofence.py` | POST /api/geofence (geofence enter/exit) | NEW file |

---

## Question 1: How Does the Orchestrator Invoke Specialist Agents?

**Short answer:** The FastAPI process invokes each specialist agent directly via `specialist_agent.run()`. There is no server-side orchestration — the FastAPI endpoint is the orchestrator.

### Why Not Connected Agents?

Connected Agents in Foundry cannot call local @tool functions. Every specialist agent (People, Projects, Ideas, Admin) needs to write results to Cosmos DB via local @tool functions. Connected Agents would require moving all tools to Azure Functions — that is explicitly deferred to v3.0 (see `REQUIREMENTS.md` CONN-01).

### Pattern: FastAPI as Code-Based Orchestrator

```python
# main.py lifespan — all agents created once at startup
app.state.classifier_agent = create_classifier_agent(ai_client, classification_tools)
app.state.people_agent = create_people_agent(ai_client, people_tools)
app.state.projects_agent = create_projects_agent(ai_client, projects_tools)
# ... etc.

# In the /api/ag-ui endpoint — route to correct specialist based on classification result
# The Classifier writes to Cosmos DB via classify_and_file.
# For proactive enrichment: after classification, FastAPI decides whether to invoke a specialist.

# Example: post-classification enrichment
if classified_bucket == "People":
    # Run People Agent to extract entities and log the interaction
    await app.state.people_agent.run(
        [Message(role="user", text=f"Enrich and log: {capture_text}")],
        stream=False,
    )
```

**Key constraint:** Each specialist agent invocation is a separate `.run()` call from the FastAPI process. There is no Foundry-level agent-to-agent routing. The "orchestration" is Python `if/elif` in the endpoint handler, not a Foundry Connected Agent.

### How Specialist Agents Call Local @tool Functions

This is identical to how the Classifier works with `classify_and_file`:

1. FastAPI calls `specialist_agent.run(messages, stream=True)`.
2. Foundry service sends a `requires_action` event back to the client.
3. `agent-framework-azure-ai` runtime intercepts the event, executes the registered `@tool` function locally in the FastAPI process (with full access to CosmosManager, etc.).
4. Result is returned to Foundry service; the agent continues.
5. Output streams back through `AgentResponseUpdate` events.

**Tools must be registered at agent creation time:**

```python
# agents/people.py
def create_people_agent(ai_client: AzureAIAgentClient, people_tools: PeopleTools) -> Agent:
    return ai_client.as_agent(
        name="People",
        instructions="Extract people, relationships, and interactions from captures...",
        tools=[
            people_tools.log_interaction,       # writes to Cosmos People container
            people_tools.add_follow_up,         # schedules a follow-up reminder
        ],
        should_cleanup_agent=False,
    )
```

---

## Question 2: How Do Specialist Agents Call Local @tool Functions?

Answered above — same mechanism as Classifier. The constraint is that this only works when agents are invoked by the **FastAPI process** (not by other agents via Connected Agents).

### Agent ID Persistence Pattern (Extended to All Specialists)

Each specialist agent needs a stable ID stored as an environment variable, same pattern as the Classifier:

```python
# config.py additions for specialist agents
class Settings(BaseSettings):
    # Classifier (v2.0)
    azure_ai_classifier_agent_id: str = ""

    # Specialists (proactive agents milestone)
    azure_ai_people_agent_id: str = ""
    azure_ai_projects_agent_id: str = ""
    azure_ai_ideas_agent_id: str = ""
    azure_ai_admin_agent_id: str = ""
```

On first deploy: leave empty. Lifespan creates agents, logs their IDs. Operator sets env vars. Container App restarts reuse existing agents.

---

## Question 3: AG-UI Adapter Redesign for Foundry (FoundrySSEAdapter)

The `AGUIWorkflowAdapter` (340 lines, workflow.py) is replaced by `FoundrySSEAdapter` (~150 lines). The replacement is already designed in the prior research file. Key architecture points:

**What stays the same:**
- `_convert_update_to_events()` in `main.py` — converts `AgentResponseUpdate` → AG-UI events
- `_stream_sse()` in `main.py` — wraps any stream in RUN_STARTED/RUN_FINISHED
- All AG-UI event types (CLASSIFIED, MISUNDERSTOOD, UNRESOLVED, STEP_STARTED, STEP_FINISHED)
- Outcome detection via `function_call.name` inspection
- Classifier text buffering / chain-of-thought suppression

**What changes:**
- Source of the stream: `workflow.run()` → `classifier_agent.run()`
- No HandoffBuilder, no `WorkflowEvent` handling, no Orchestrator echo filtering
- Thread management: `get_new_thread()` → `thread_id` parameter on `run()`

**Skeleton:**

```python
class FoundrySSEAdapter:
    """Adapter that wraps classifier_agent.run() for AG-UI compatibility.

    Replaces AGUIWorkflowAdapter. No HandoffBuilder. No Workflow.
    Same outcome detection, text buffering, and step event logic.
    """
    def __init__(self, classifier: Agent, classification_threshold: float = 0.6):
        self._classifier = classifier
        self._threshold = classification_threshold

    async def _stream_updates(self, messages, thread_id: str) -> AsyncIterable[StreamItem]:
        detected_tool: str | None = None
        detected_tool_args: dict = {}
        classified_inbox_id: str | None = None
        misunderstood_inbox_id: str | None = None
        classify_result_str: str | None = None
        classifier_buffer: str = ""

        yield StepStartedEvent(step_name="Classifier")
        async for update in self._classifier.run(messages, stream=True):
            # Same _process_update() logic as AGUIWorkflowAdapter
            # Same _is_classifier_text() buffering
            # Same _extract_function_call_info() detection
            yield update
        yield StepFinishedEvent(step_name="Classifier")
        # Flush buffer, emit CLASSIFIED/MISUNDERSTOOD/UNRESOLVED
```

---

## Question 4: Scheduled Execution — Friday Digests, Weekly Nudges, Project Follow-Ups

### Architecture Decision: In-Process APScheduler (Not Container Apps Jobs)

**Verdict: Use APScheduler running inside the FastAPI process.**

**Why not Container Apps Jobs:**
- Jobs require a separate container and the same image would be used as both HTTP server and batch runner, which is awkward.
- Jobs cannot share `app.state` (Cosmos connections, AI clients) — they start fresh.
- For a single-user system at this scale, the overhead of a separate Job resource is not justified.
- APScheduler starts with the FastAPI lifespan and shares all initialized resources.

**Why not Azure Functions timer trigger:**
- Adds another service to manage and deploy.
- Cannot share CosmosManager singleton or AzureAIAgentClient from the FastAPI process.
- Overkill for single-user scheduled tasks.

**APScheduler with AsyncIOScheduler:**

```python
# services/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

def create_scheduler(
    cosmos_manager: CosmosManager,
    push_service: PushNotificationService,
    ai_client: AzureAIAgentClient,
    agents: dict[str, Agent],
) -> AsyncIOScheduler:
    """Create and configure the APScheduler AsyncIOScheduler.

    Jobs:
    - Friday digest: Fridays 17:00 UTC (noon EST)
    - Weekly nudge: Sundays 09:00 UTC (for pending action items)
    - Project follow-up: Daily 08:00 UTC (check for stale projects)
    """
    scheduler = AsyncIOScheduler()

    # Friday digest — weekly summary of what was captured
    scheduler.add_job(
        send_friday_digest,
        CronTrigger(day_of_week="fri", hour=17, minute=0),
        args=[cosmos_manager, push_service, agents["admin"]],
        id="friday_digest",
        replace_existing=True,
    )

    # Weekly nudge — incomplete action items
    scheduler.add_job(
        send_weekly_nudge,
        CronTrigger(day_of_week="sun", hour=9, minute=0),
        args=[cosmos_manager, push_service, agents["projects"]],
        id="weekly_nudge",
        replace_existing=True,
    )

    return scheduler
```

**Lifespan integration:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing init ...

    # Start scheduler
    scheduler = create_scheduler(cosmos_manager, push_service, ai_client, agents)
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    # Shutdown scheduler
    scheduler.shutdown(wait=False)
    # ... existing cleanup ...
```

**Scheduler job pattern — Friday digest:**

```python
async def send_friday_digest(
    cosmos_manager: CosmosManager,
    push_service: PushNotificationService,
    admin_agent: Agent,
) -> None:
    """Generate and send Friday digest via Admin Agent."""
    # 1. Query Cosmos DB for captures from the past week
    inbox_container = cosmos_manager.get_container("Inbox")
    # ... query for week's items ...

    # 2. Ask Admin Agent to summarize (Admin Agent has access to Cosmos via @tool)
    response = await admin_agent.run(
        [Message(role="user", text=f"Generate Friday digest for: {captures_summary}")],
        stream=False,
    )
    digest_text = response.text

    # 3. Send push notification
    await push_service.send(
        title="Your Week in Review",
        body=digest_text[:100],  # Preview in notification
        data={"type": "digest", "fullText": digest_text},
    )
```

---

## Question 5: Push Notification Flow

### Architecture: Backend → Expo Push Service → Device

Expo Push Service acts as a managed intermediary — no direct APNs/FCM credentials needed in development or for a single-user system.

**Flow:**

```
1. Device registers token on app launch:
   Mobile app → POST /api/push-token { token: "ExponentPushToken[xxx]" }
   FastAPI stores token in Cosmos DB Admin container (or dedicated field in Admin config doc)

2. Backend sends notification (from scheduler job or agent action):
   FastAPI → POST https://exp.host/--/api/v2/push/send
   Body: { "to": "ExponentPushToken[xxx]", "title": "...", "body": "...", "data": {...} }

3. Expo Push Service → APNs/FCM → Device
```

**PushNotificationService (services/push_notifications.py):**

```python
import httpx

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

class PushNotificationService:
    """Thin wrapper around the Expo Push HTTP API.

    Single-user system: one push token stored in Cosmos Admin container.
    """

    def __init__(self, cosmos_manager: CosmosManager) -> None:
        self._cosmos = cosmos_manager
        self._cached_token: str | None = None

    async def register_token(self, token: str) -> None:
        """Store the Expo push token for the user."""
        admin_container = self._cosmos.get_container("Admin")
        # Upsert the config document with the push token
        await admin_container.upsert_item({
            "id": "push-token-config",
            "userId": "will",
            "expoPushToken": token,
            "updatedAt": datetime.now(UTC).isoformat(),
        })
        self._cached_token = token

    async def get_token(self) -> str | None:
        """Get the stored Expo push token."""
        if self._cached_token:
            return self._cached_token
        try:
            admin_container = self._cosmos.get_container("Admin")
            doc = await admin_container.read_item("push-token-config", partition_key="will")
            self._cached_token = doc.get("expoPushToken")
            return self._cached_token
        except Exception:
            return None

    async def send(
        self, title: str, body: str, data: dict | None = None
    ) -> bool:
        """Send a push notification to the registered device."""
        token = await self.get_token()
        if not token:
            logger.warning("No push token registered, skipping notification")
            return False

        payload = {"to": token, "title": title, "body": body}
        if data:
            payload["data"] = data

        async with httpx.AsyncClient() as client:
            response = await client.post(
                EXPO_PUSH_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )

        if response.status_code != 200:
            logger.error("Push notification failed: %s", response.text)
            return False

        return True
```

**Push token registration endpoint (api/push_token.py):**

```python
@router.post("/api/push-token")
async def register_push_token(request: Request, body: PushTokenRequest) -> dict:
    """Register the device's Expo push token for notifications."""
    push_service: PushNotificationService = request.app.state.push_service
    await push_service.register_token(body.token)
    return {"status": "registered"}
```

**Confidence: HIGH** — Expo Push Service HTTP API is stable and well-documented. `expo-server-sdk-python` (`exponent-server-sdk` on PyPI) is an option for additional features (batching, error handling), but direct `httpx` is simpler for single-user.

---

## Question 6: Geofencing — Where Does the Logic Live?

### Architecture Decision: Mobile-Side Geofencing, Backend Receives Events

**Geofencing runs entirely on the mobile device.** The Expo Location SDK (`expo-location` + `expo-task-manager`) monitors regions. When the device enters or exits a region, the mobile app calls a backend endpoint. The backend then decides what to do (trigger an agent, send reminders, etc.).

**Why mobile-side:**
- iOS and Android OS handle geofence monitoring at the system level — works even when app is terminated (iOS restarts the app on geofence event)
- Backend has no access to device location in real-time
- Mobile → Backend HTTP call is the only integration point

**Mobile implementation (Expo):**

```typescript
// Defined at top-level of app (not inside component):
TaskManager.defineTask(GEOFENCE_TASK, async ({ data, error }) => {
  const { eventType, region } = data;

  // POST to backend
  await fetch(`${API_URL}/api/geofence`, {
    method: "POST",
    headers: { "x-api-key": API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({
      eventType: eventType === GeofencingEventType.Enter ? "enter" : "exit",
      regionId: region.identifier,
      latitude: region.latitude,
      longitude: region.longitude,
    }),
  });
});

// Start monitoring (call at app startup after permission grant):
await Location.startGeofencingAsync(GEOFENCE_TASK, [
  { identifier: "home", latitude: HOME_LAT, longitude: HOME_LON, radius: 200 },
  { identifier: "office", latitude: OFFICE_LAT, longitude: OFFICE_LON, radius: 300 },
]);
```

**Backend geofence endpoint (api/geofence.py):**

```python
@router.post("/api/geofence")
async def handle_geofence_event(request: Request, body: GeofenceEvent) -> dict:
    """Handle a geofence enter/exit event from the mobile app.

    Triggers context-appropriate agent actions:
    - Entering home: trigger "end of day" capture prompt notification
    - Leaving office: remind about open action items
    """
    push_service: PushNotificationService = request.app.state.push_service
    cosmos_manager: CosmosManager = request.app.state.cosmos_manager

    if body.eventType == "enter" and body.regionId == "home":
        # Query for any pending action items
        # ... check Cosmos Projects ...
        await push_service.send(
            title="Back home",
            body="3 open action items — capture anything from today?",
            data={"type": "geofence_prompt"},
        )

    elif body.eventType == "exit" and body.regionId == "office":
        await push_service.send(
            title="Leaving office",
            body="Quick: anything to capture before you head out?",
            data={"type": "geofence_prompt"},
        )

    return {"status": "handled"}
```

**Expo Location limitations (HIGH confidence — from official docs):**
- iOS: max 20 simultaneously monitored regions
- Android: max 100 simultaneously monitored regions
- iOS: requires `"location"` background mode in `Info.plist`
- Android: requires `ACCESS_FINE_LOCATION` + `FOREGROUND_SERVICE_LOCATION` permissions
- Does NOT work in Expo Go — requires a development build
- On iOS, the system restarts a terminated app when a geofence event fires

**For a single-user system:** 2-5 locations (home, office, gym) is well within both platform limits.

---

## Question 7: Agent State — "Last Interaction with Person X" / "Action Items for Project Y"

### Architecture Decision: Cosmos DB as the Authoritative State Store

**Foundry server-managed threads are for conversation history within a single session.** They are not the right tool for cross-session semantic state like "last interaction" or "outstanding action items." Cosmos DB is the correct store.

**State pattern for specialists:**

The People Agent reads and writes "interaction records" in the People Cosmos container. The Projects Agent reads and writes "action item" fields in the Projects container. The agent's @tool functions are the write path; Cosmos queries are the read path.

**People Agent state (Cosmos People container document):**

```json
{
  "id": "person-uuid",
  "userId": "will",
  "name": "Sarah Chen",
  "lastInteractionDate": "2026-02-20T14:00:00Z",
  "lastInteractionNote": "Discussed Q2 roadmap priorities",
  "followUpDue": "2026-02-27",
  "followUpNote": "Send meeting notes",
  "captureHistory": ["inbox-uuid-1", "inbox-uuid-3"],
  "tags": ["work", "product"]
}
```

**Projects Agent state (Cosmos Projects container document):**

```json
{
  "id": "project-uuid",
  "userId": "will",
  "title": "Second Brain v2.0",
  "status": "active",
  "lastActivityDate": "2026-02-25T10:00:00Z",
  "actionItems": [
    { "id": "ai-1", "text": "Write ARCHITECTURE.md", "due": "2026-02-26", "done": false },
    { "id": "ai-2", "text": "Deploy to Container Apps", "due": "2026-03-01", "done": false }
  ],
  "captureHistory": ["inbox-uuid-2", "inbox-uuid-5"]
}
```

**How the People Agent reads state before acting:**

The People Agent's @tool functions receive the person's current state as part of their arguments (injected by the agent based on context). The tool then reads from Cosmos, updates, and writes back. Alternatively, the FastAPI process queries Cosmos before calling the agent and injects the state as context into the message.

**Recommended pattern: inject current state into agent message, not into tool:**

```python
# In the endpoint or scheduler job:
person_doc = await cosmos_manager.get_container("People").read_item(
    item=person_id, partition_key="will"
)
context_msg = f"""
Current state for {person_doc['name']}:
- Last interaction: {person_doc['lastInteractionDate']}
- Follow-up due: {person_doc.get('followUpDue', 'none')}

New capture: {capture_text}

Please update the interaction record and determine if a follow-up is warranted.
"""
response = await people_agent.run(
    [Message(role="user", text=context_msg)],
    stream=False,
)
```

This avoids having the agent make a Cosmos read call — the FastAPI process reads, the agent reasons and decides, the @tool function writes.

**BYO Thread Storage (Cosmos DB for Foundry threads) — SKIP for this milestone:**

Cosmos DB can store Foundry's server-managed threads via the Foundry connector (BYO Thread Storage — three containers: `thread-message-store`, `system-thread-message-store`, `agent-entity-store`). This is useful for conversation continuity across sessions but adds significant setup complexity. For the proactive agents milestone: use server-managed threads per session (existing approach) and Cosmos for domain state. BYO Thread Storage is a v3.0+ consideration.

---

## Complete Data Flow: Proactive Enrichment After Classification

```
1. User submits text capture via POST /api/ag-ui

2. FastAPI ag_ui_endpoint:
   - Creates new thread_id (fresh Foundry thread)
   - Calls FoundrySSEAdapter.run(messages, stream=True)

3. FoundrySSEAdapter streams:
   - StepStartedEvent("Classifier")
   - Classifier Agent runs on Foundry (server-side LLM call)
   - LLM decides to call classify_and_file(bucket="People", confidence=0.92, ...)
   - Foundry sends requires_action → agent-framework executes classify_and_file locally
   - classify_and_file writes to Cosmos Inbox + People containers
   - Returns "Filed → People (0.92) | inbox-uuid"
   - StepFinishedEvent("Classifier")
   - CLASSIFIED custom event { inboxItemId, bucket: "People", confidence: 0.92 }

4. Mobile app receives CLASSIFIED event — shows toast, done for interactive capture.

5. FastAPI endpoint (after stream completes) triggers proactive enrichment
   as a background task (FastAPI BackgroundTasks):
   - Reads new inbox item from Cosmos to get full text
   - Queries People container for existing person record (by name extracted from text)
   - Calls people_agent.run([Message(context + capture_text)], stream=False)
   - People Agent calls log_interaction(@tool) → updates People document in Cosmos
   - If follow-up warranted: push_service.send("Follow up with Sarah", "...")

6. Mobile app receives push notification (seconds to minutes later)
```

---

## Data Flow: Scheduled Friday Digest

```
1. APScheduler fires friday_digest job at 17:00 UTC on Friday

2. Job function:
   - Queries Cosmos Inbox for captures from Mon-Fri (this week)
   - Aggregates by bucket and status
   - Formats summary dict: { "projects": 5, "people": 3, "ideas": 2, "admin": 8 }

3. Calls Admin Agent:
   admin_agent.run(
     [Message("Generate a Friday digest from: {summary}")],
     stream=False
   )
   Admin Agent calls generate_digest(@tool) → formats human-readable summary

4. push_service.send("Your Week in Review", digest_preview, data={"full": full_text})

5. Mobile app receives push notification
   - Taps notification → opens digest view (new screen)
   - GET /api/digest returns full digest text from Cosmos or computed on demand
```

---

## New File Structure After Proactive Agents

```
backend/src/second_brain/
├── agents/
│   ├── classifier.py      # MODIFIED: AzureAIAgentClient
│   ├── workflow.py        # REPLACED: FoundrySSEAdapter
│   ├── orchestrator.py    # DELETED
│   ├── people.py          # NEW: People Agent creation
│   ├── projects.py        # NEW: Projects Agent creation
│   ├── ideas.py           # NEW: Ideas Agent creation
│   └── admin.py           # NEW: Admin Agent creation
├── tools/
│   ├── classification.py  # UNCHANGED
│   ├── transcription.py   # UNCHANGED (modified for gpt-4o-transcribe in v2.0)
│   ├── people_tools.py    # NEW: log_interaction, add_follow_up
│   ├── projects_tools.py  # NEW: update_status, add_action_item
│   ├── ideas_tools.py     # NEW: enrich_idea, link_related
│   └── admin_tools.py     # NEW: generate_digest, schedule_reminder
├── services/
│   ├── push_notifications.py  # NEW: PushNotificationService
│   └── scheduler.py           # NEW: APScheduler setup + job functions
├── api/
│   ├── inbox.py           # UNCHANGED
│   ├── health.py          # UNCHANGED
│   ├── push_token.py      # NEW: POST /api/push-token
│   └── geofence.py        # NEW: POST /api/geofence
├── db/
│   ├── cosmos.py          # UNCHANGED
│   └── blob_storage.py    # UNCHANGED
├── main.py                # MODIFIED: add scheduler, push_service, new routers
├── config.py              # MODIFIED: push token config, specialist agent IDs
├── auth.py                # UNCHANGED
└── models/
    └── documents.py       # UNCHANGED (may add action_items field to Projects model)
```

---

## Build Order (Dependency-Ordered)

The build order must respect:
1. Infrastructure prerequisites before any code changes
2. Classifier migration before specialist agents (they share AzureAIAgentClient)
3. Push notification service before scheduler (scheduler calls push service)
4. Geofence endpoint after push service (geofence triggers push)

```
Phase 6: Infrastructure + Prerequisites
  ├── 6-01: Azure AI Foundry project, App Insights, RBAC
  ├── 6-02: config.py new env vars, package install, Orchestrator deletion
  └── 6-03: Breaking change migration (AgentThread → AgentSession RC changes)

Phase 7: Single-Agent Classifier Baseline
  ├── 7-01: classifier.py → AzureAIAgentClient, standalone smoke test
  ├── 7-02: transcribe_audio as @tool (gpt-4o-transcribe)
  └── 7-03: AgentMiddleware, FunctionMiddleware wiring

Phase 8: FoundrySSEAdapter + FastAPI Integration
  ├── 8-01: FoundrySSEAdapter implementation (replaces AGUIWorkflowAdapter)
  ├── 8-02: main.py lifespan migration, text capture E2E test
  └── 8-03: Voice capture E2E test

Phase 9: HITL + Observability + Deployment
  ├── 9-01: HITL flows (respond, follow-up endpoints)
  ├── 9-02: Application Insights traces
  └── 9-03: Container App deployment, CI/CD update

[NEW MILESTONE] Proactive Agents
  ├── P-01: PushNotificationService + /api/push-token endpoint
  │         DEPENDS ON: Cosmos DB (already done), httpx (already in deps)
  │
  ├── P-02: People Agent + PeopleTools (@tool functions for Cosmos People)
  │         DEPENDS ON: AzureAIAgentClient (Phase 7), CosmosManager (Phase 1)
  │
  ├── P-03: Projects Agent + ProjectsTools
  │         DEPENDS ON: AzureAIAgentClient (Phase 7)
  │
  ├── P-04: Ideas Agent + IdeasTools
  │         DEPENDS ON: AzureAIAgentClient (Phase 7)
  │
  ├── P-05: Admin Agent + AdminTools (digest generation)
  │         DEPENDS ON: AzureAIAgentClient (Phase 7)
  │
  ├── P-06: APScheduler integration in lifespan + Friday digest job
  │         DEPENDS ON: PushNotificationService (P-01), Admin Agent (P-05)
  │
  ├── P-07: Weekly nudge job (Projects) + project follow-up job
  │         DEPENDS ON: APScheduler (P-06), Projects Agent (P-03)
  │
  ├── P-08: Post-classification enrichment (BackgroundTasks injection)
  │         DEPENDS ON: All specialist agents (P-02..P-05)
  │
  └── P-09: Geofence endpoint + mobile geofencing setup
            DEPENDS ON: PushNotificationService (P-01)
            MOBILE: expo-location + expo-task-manager setup
```

**Critical build dependencies:**
- PushNotificationService must exist before scheduler and geofence (P-01 first)
- Specialist agents must exist before post-classification enrichment (P-02..05 before P-08)
- APScheduler must start in lifespan after all services are initialized

---

## Patterns to Follow

### Pattern 1: FastAPI BackgroundTasks for Post-Classification Enrichment

After the SSE stream to the mobile app completes, trigger specialist agents without blocking the response:

```python
@app.post("/api/ag-ui")
async def ag_ui_endpoint(
    request: Request,
    body: AGUIRunRequest,
    background_tasks: BackgroundTasks,
) -> StreamingResponse:
    sse_adapter = request.app.state.sse_adapter
    stream = sse_adapter.run(body.messages, stream=True)

    # Outcome captured during streaming (via shared mutable state or post-stream hook)
    classification_result: dict = {}

    async def generate():
        async for chunk in _stream_sse(stream, thread_id, run_id):
            yield chunk
        # After stream ends, schedule enrichment
        if classification_result.get("bucket"):
            background_tasks.add_task(
                enrich_classification,
                classification_result,
                request.app.state,
            )

    return StreamingResponse(generate(), media_type="text/event-stream", ...)
```

**Alternative:** Emit the CLASSIFIED custom event first, then the enrichment runs while the mobile app processes the result. The mobile app does not wait for enrichment.

### Pattern 2: Shared AzureAIAgentClient for All Specialist Agents

All agents share one `AzureAIAgentClient` instance. The client manages the connection pool and authentication. Do not create per-agent clients:

```python
# In lifespan — one client, multiple agents
ai_client = AzureAIAgentClient(
    credential=async_credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    model_deployment_name=settings.azure_ai_model_deployment_name,
    should_cleanup_agent=False,
)
app.state.ai_client = ai_client  # Keep alive for duration

# Each agent is a persistent Foundry agent registered against this client
app.state.classifier_agent = create_classifier_agent(ai_client, classification_tools)
app.state.people_agent = create_people_agent(ai_client, people_tools)
app.state.projects_agent = create_projects_agent(ai_client, projects_tools)
```

### Pattern 3: Cosmos State Injection Before Agent Run

Read domain state (person record, project record) from Cosmos before calling the specialist agent. Inject as context in the user message. This avoids a Cosmos read @tool and makes the agent's reasoning transparent:

```python
# Better: FastAPI reads state, injects as context
person = await cosmos_manager.get_container("People").read_item(id, partition_key="will")
context = f"Current record: {json.dumps(person)}\nNew capture: {capture_text}"
await people_agent.run([Message(role="user", text=context)], stream=False)

# Worse: Agent has a read_person @tool (extra LLM call to retrieve state)
```

### Pattern 4: APScheduler in FastAPI Lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... all initialization first ...

    # Scheduler must start AFTER all services it depends on are initialized
    scheduler = create_scheduler(
        cosmos_manager=app.state.cosmos_manager,
        push_service=app.state.push_service,
        agents={
            "admin": app.state.admin_agent,
            "projects": app.state.projects_agent,
        }
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("APScheduler started")

    yield

    # Cleanup: scheduler before other resources
    app.state.scheduler.shutdown(wait=False)
    # ... other cleanup ...
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Using Connected Agents for Specialists with Cosmos Tools

**What:** Register People Agent as a Connected Agent on the Classifier, with `log_interaction` as a server-side tool.
**Why wrong:** Connected Agents cannot call local @tool functions. `log_interaction` writes to Cosmos DB via the local `CosmosManager` singleton. Moving it to Azure Functions requires a separate deployment, authentication, and significantly more infrastructure.
**Instead:** FastAPI invokes specialist agents directly via `specialist_agent.run()` after classification.

### Anti-Pattern 2: APScheduler with ThreadPoolScheduler in an Async App

**What:** Using `BackgroundScheduler` (thread-based) instead of `AsyncIOScheduler` in an asyncio FastAPI app.
**Why wrong:** Thread-based scheduler cannot await async functions. All Cosmos DB calls, AI agent calls, and push notification calls are async.
**Instead:** Use `AsyncIOScheduler` which runs jobs in the asyncio event loop.

### Anti-Pattern 3: Storing Push Tokens in Environment Variables

**What:** `EXPO_PUSH_TOKEN=ExponentPushToken[xxx]` in `.env`.
**Why wrong:** Push tokens change when the app reinstalls or the device OS updates. The token must be refreshed by the mobile app and stored in a database (Cosmos Admin container).
**Instead:** Mobile app calls `POST /api/push-token` on every launch with the current token. Backend upserts into Cosmos.

### Anti-Pattern 4: Blocking Geofence Events in Mobile App

**What:** Performing synchronous or long-running operations in the TaskManager geofence task.
**Why wrong:** TaskManager background tasks have strict time limits on iOS/Android. Long operations will be killed by the OS.
**Instead:** The geofence task fires a single HTTP POST to the backend and returns. All agent logic runs server-side.

### Anti-Pattern 5: Creating New AzureAIAgentClient Per Scheduler Job

**What:** Each APScheduler job creates its own `AzureAIAgentClient`.
**Why wrong:** Creates new HTTP sessions, potentially creates new agent registrations in Foundry, wastes connections, and does not share the lifespan-managed credential.
**Instead:** Pass the lifespan-initialized agents (and their shared client) as arguments to the scheduler job functions.

### Anti-Pattern 6: Using Foundry Server-Managed Threads for Agent State

**What:** Storing "last interaction with person X" in Foundry's conversation threads.
**Why wrong:** Foundry threads are per-conversation session. Cross-session state ("when did I last contact Sarah?") is not accessible from thread history without querying Foundry's thread storage.
**Instead:** Cosmos DB is the authoritative state store. Foundry threads are for within-session conversation continuity only.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Azure AI Foundry Agent Service | `AzureAIAgentClient` with async credential | Shared client, all specialists use same client |
| Cosmos DB | `CosmosManager` singleton, initialized in lifespan | 5 containers: Inbox, People, Projects, Ideas, Admin |
| Expo Push Service | HTTP POST to `exp.host/--/api/v2/push/send` via httpx | No SDK needed for single-user; push token stored in Cosmos Admin |
| Azure Blob Storage | `BlobStorageManager` singleton | Voice recordings, deleted after transcription |
| Azure OpenAI Whisper | `AsyncAzureOpenAI` via @tool function | `gpt-4o-transcribe` deployment for voice captures |
| Expo Location (geofencing) | Mobile-side; backend receives events via POST /api/geofence | iOS: max 20 regions, Android: max 100 |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| APScheduler ↔ Push Service | Direct function call (shared reference) | Both initialized in lifespan, scheduler holds reference |
| APScheduler ↔ Specialist Agents | Direct async `agent.run()` call | Agents initialized in lifespan, passed as args to jobs |
| FoundrySSEAdapter ↔ Classifier Agent | `agent.run(stream=True)` | Same `AgentResponseUpdate` stream as before |
| Classifier ↔ CosmosManager | @tool function execution via agent-framework-azure-ai | `classify_and_file` writes to Inbox + bucket container |
| Specialist Agents ↔ CosmosManager | @tool function execution | Each specialist has its own domain @tool functions |
| FastAPI endpoint ↔ BackgroundTasks | `background_tasks.add_task(fn, args)` | Enrichment triggered after SSE stream completes |
| Mobile App ↔ Push Service | Expo Push Service (managed intermediary) | No direct APNs/FCM; Expo handles platform differences |
| Mobile App ↔ Backend (geofence) | HTTP POST from TaskManager background task | Mobile fires-and-forgets; backend handles all logic |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Connected Agents @tool limitation | HIGH | Explicitly stated in official docs (2026-02-25) |
| FastAPI as code-based orchestrator | HIGH | Known pattern from v1.0; confirmed approach for v2.0+ |
| AzureAIAgentClient shared instance | HIGH | Confirmed from SDK source and docs |
| APScheduler AsyncIOScheduler in FastAPI | HIGH | Well-documented pattern, multiple sources |
| Expo Push HTTP API | HIGH | Official Expo docs, stable API |
| Expo Location geofencing capabilities | HIGH | Official Expo docs, confirmed limitations |
| Cosmos DB as cross-session state store | HIGH | Domain data already in Cosmos; correct layer for this |
| BackgroundTasks for post-classification enrichment | HIGH | FastAPI native feature, no new dependencies |
| BYO Cosmos thread storage (deferred) | MEDIUM | Documented but complex setup, not needed for proactive agents |
| Mobile geofence → backend HTTP latency | LOW | Background tasks on iOS may be delayed by OS; acceptable for non-critical prompts |

---

## Open Questions for Phase-Specific Research

1. **APScheduler persistence across Container App restarts:** By default APScheduler uses in-memory job store. If the Container App restarts mid-week, the scheduled jobs are re-registered at startup (since `replace_existing=True`). However, jobs that fired while the app was down are missed. For Friday digest, this is acceptable. Verify whether a persistent job store (Redis or Cosmos-backed) is needed.

2. **Agent response routing after classification:** The FoundrySSEAdapter must capture the CLASSIFIED event data (bucket, inboxItemId) so the endpoint handler can trigger the right specialist agent. The current outcome detection reads `function_call.name` and args from the stream — this state must be propagated back to the endpoint handler, not just logged inside the adapter.

3. **Concurrent agent runs:** If APScheduler fires while a user is actively capturing, multiple specialist agent runs may execute concurrently against the same Cosmos containers. Cosmos DB handles concurrent writes via optimistic concurrency (ETag) — verify whether the domain data patterns need conflict resolution (e.g., two concurrent `log_interaction` calls for the same person document).

4. **Expo geofencing in development build vs TestFlight:** Geofencing does not work in Expo Go. For testing, a development build or TestFlight distribution is required. Confirm this is acceptable before implementing.

5. **Push notification background delivery on iOS:** iOS may delay or batch push notifications. For time-sensitive nudges (geofence prompts, follow-up reminders), this is acceptable. For Friday digests, delivery within an hour of the scheduled time is sufficient.

---

## Sources

- [How to use connected agents — Connected Agents cannot call local functions](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) — HIGH confidence, updated 2026-02-25
- [Azure AI Foundry Agents: agent-framework integration](https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-types/azure-ai-foundry-agent) — HIGH confidence, official docs
- [Jobs in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/jobs) — HIGH confidence, updated 2026-01-28; confirmed Jobs are separate from apps
- [Expo Send Notifications — Push Service HTTP API](https://docs.expo.dev/push-notifications/sending-notifications/) — HIGH confidence, official Expo docs
- [Expo Location SDK — Geofencing](https://docs.expo.dev/versions/latest/sdk/location/) — HIGH confidence, official Expo docs (20 region limit on iOS, 100 on Android)
- [Integration with Foundry Agent Service — Cosmos DB BYO Thread Storage](https://learn.microsoft.com/en-us/azure/cosmos-db/gen-ai/azure-agent-service) — HIGH confidence, updated 2026-02-23
- [Agent Middleware — Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-middleware) — HIGH confidence, official docs
- Local SDK inspection: `_sessions.py` (AgentSession replacing AgentThread), `_middleware.py` (AgentMiddleware, FunctionMiddleware) — HIGH confidence from installed SDK

---

*Architecture research for: The Active Second Brain — Proactive Multi-Agent Integration*
*Researched: 2026-02-25*
