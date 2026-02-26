# Feature Research

**Domain:** Proactive multi-agent personal assistant — specialist agents with follow-up behaviors on mobile
**Researched:** 2026-02-25
**Confidence:** HIGH for behavioral patterns and UX norms (well-established domain); MEDIUM for geofencing (known Expo limitations); HIGH for notification infrastructure (official Expo docs verified)

---

## Context: What This Research Covers

This is the NEW feature layer for v2.0. The existing v1 features (text/voice capture, HITL classification, AG-UI streaming, inbox) already exist and are not being rebuilt. This research answers: what do proactive personal assistant agents actually do, what UX patterns do users expect from nudges and follow-ups in a mobile app, and what is the right feature set for the four specialist agents (Admin, Ideas, Projects, People)?

The downstream consumer is the roadmap. Features are mapped to agents. Complexity ratings inform phase sizing. Dependencies identify ordering constraints.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume will exist once an agent calls itself "proactive." Missing any of these = the product feels like a filing cabinet with badges, not an intelligent assistant.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Push notifications delivered to device | No nudge is real without device delivery. If the agent notices something, the user must learn about it. | LOW | Expo Push Service + APNs/FCM. Server sends to stored push token. `expo-server-sdk-python` or direct Expo Push API from FastAPI backend. |
| Notification content is specific, not generic | "You have a reminder" is ignored. "Haven't talked to Sarah in 3 weeks — her birthday is next month" gets opened. | LOW | Requires agent to read Cosmos DB records before generating message text. Content specificity is entirely in prompt engineering. |
| Notification taps deep-link into the relevant item | User taps notification → lands in the relevant capture/person/project, not the app home screen. | MEDIUM | Expo notifications support `data` payload with item ID. Expo Router handles deep links via notification handler. Requires notification handler setup in Expo app. |
| User can dismiss/snooze a nudge | 4/4 users in UX research wanted confirmation of snooze and granular control. Notification fatigue is real — 62% of users report annoyance at excessive notifications. | MEDIUM | Two options: (1) Expo notification action buttons ("Done", "Snooze 1 week") — works via `setNotificationCategoryAsync`. (2) Server-side: mark nudge as snoozed in Cosmos DB, skip on next agent run. Both are needed. |
| Push token stored server-side at app startup | Agent cannot send notifications without a device token. No token = silent failure. | LOW | App registers on startup with `getExpoPushTokenAsync()`, sends token to `/api/device/register` POST endpoint. Backend stores token in Cosmos DB user profile or simple KV. |
| Notifications respect quiet hours (no 2am nudges) | Basic hygiene. Users who get 2am "any thoughts on your idea?" will disable notifications. | LOW | Server-side: time-zone-aware scheduling. All scheduled jobs check current hour before firing. Default quiet window: 9pm–8am (configurable). |
| Notification frequency is bounded | U.S. users receive ~46 push messages/day across all apps. 2–5 agent-initiated nudges per week is the acceptable ceiling before opt-out spikes. | LOW | Per-agent rate limiting: each specialist agent can send at most N nudges per week. Enforced in scheduler logic, not per-notification. |

### Differentiators (Competitive Advantage)

Features that make this feel like a genuine thinking partner rather than a fancier reminder app.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Admin Agent: errand timing intelligence | "Buy milk" nudged on Saturday morning (near stores, not during a workday meeting). Context-aware scheduling beats dumb time-based reminders. | MEDIUM | Agent reads Admin bucket captures, extracts errand-type tasks, schedules nudge for weekend morning window. No geofencing required for v2.0 — time-window heuristic is simpler and reliable. Weekend = Sat 9am, Weekday = 6pm. |
| Admin Agent: Friday evening weekend planning digest | Single weekly digest notification at Friday 5–6pm summarizing pending Admin items. Enables intentional weekend planning without daily noise. | LOW | APScheduler cron job: Friday 5pm local time. Agent reads all Admin captures with status "pending_action", generates ranked summary. One notification per week. |
| Ideas Agent: weekly nudge per idea | Each captured idea gets a weekly "any new thoughts on X?" check-in. Prevents ideas from becoming a graveyard. Keeps creative thinking alive between captures. | LOW | APScheduler weekly job per-idea. Agent reads Ideas bucket, picks one idea per week (round-robin or stalest), generates contextual prompt. Max one nudge per week total across all ideas. |
| Projects Agent: action item extraction from captures | When a Project capture comes in, the agent identifies action items embedded in the text ("I need to call the accountant", "book the venue by March"). Files them as structured sub-tasks. | HIGH | Requires Projects Agent with Cosmos DB tools to write action items. Agent runs immediately after classification (triggered by CLASSIFIED event with bucket=Projects). Adds a new document type: `action_item` linked to parent capture. |
| Projects Agent: progress check-in ("are you on track?") | Weekly accountability check per active project. "Last week you captured 3 things about the website redesign. 2 action items are open. Are you on track?" | MEDIUM | APScheduler weekly job. Agent reads Projects bucket, groups by project/theme, summarizes open action items, generates check-in notification. Requires action item tracking (dependency on extraction feature). |
| People Agent: interaction tracking | Every People bucket capture is treated as an interaction log entry. Captures "talked to [person]" or "met [person]" update the last-interaction timestamp. Used for nudge timing. | LOW | Cosmos DB write on classification: update `last_interaction` field on People document. Classifier already creates People documents on classification. Add `last_interaction` timestamp update in `classify_and_file` tool. |
| People Agent: relationship nudge ("haven't talked to X in Y weeks") | Proactive nudge when interaction gap exceeds threshold. "It's been 5 weeks since you last mentioned Emma. Worth checking in?" | LOW | APScheduler daily job scans People documents. If `last_interaction` > threshold (default: 4 weeks, configurable per person), fire nudge. Clay and Covve — leading personal CRM apps — use this exact pattern. Users in the domain expect it. |
| Actionable notification buttons | Notification includes "Done ✓" and "Remind me later" buttons. One tap dismisses without opening app. | MEDIUM | Expo `setNotificationCategoryAsync` with action buttons. Backend `/api/nudge/respond` endpoint receives action. Simple to implement but requires backend endpoint + Expo category registration. |
| Agent-generated notification copy | Agent writes the notification text, not a template. "It's been 3 weeks since you talked to Marcus — you mentioned he was going through a job change" beats "Reminder: contact Marcus". | LOW | Pure prompt engineering. Agent has access to the capture history. The LLM generates natural copy. This is the core value of using an agent vs. a cron job with templates. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem like obvious additions but create real problems for this single-user personal use case.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Background geofencing for errand reminders | "Remind me when I'm near Tesco" sounds great. Location-triggered errands are genuinely useful. | Expo managed workflow does not support background geofencing; bare workflow or dev build required. iOS limits simultaneous monitored regions to 20. Android won't restart terminated apps on geofence events. Known open issue (#25875) with Expo geofencing. Adds significant infrastructure complexity (location permission flows, background task registration, testing). | Weekend morning time window heuristic covers 80% of the value with 5% of the complexity. Defer geofencing to v3.0 as an explicit enhancement once the agent layer is proven. |
| Per-person nudge frequency customization in-app | "Let me set Emma to every 2 weeks and John to every 3 months" | Adds a settings UI surface that doesn't exist yet. For a single user, the overhead of maintaining these settings is often higher than the value. Users in personal CRM research noted settings creep as a usability problem. | Use sensible defaults (4 weeks general, 2 weeks for frequently-mentioned contacts based on capture frequency). Add customization only when Will explicitly asks for it. |
| Real-time streaming SSE for nudge delivery | Consistent with existing AG-UI streaming pattern; seems architecturally clean. | Nudges are not interactive conversations. A push notification needs a device token and APNs/FCM, not an SSE stream to a browser tab. SSE requires an active HTTP connection; push notifications work when app is closed. | Push notifications via Expo Push Service for all proactive nudges. SSE stays exclusively for capture/classification flows. |
| AI-generated calendar integration | "Block time on my calendar to act on these action items." | Requires OAuth calendar access (Google/Apple/Outlook). Complex auth flow, token refresh, scope management — a completely different infrastructure concern from the current system. Scope creep. | Projects Agent surfacing action items via push notification is the right boundary. User acts on the notification. Calendar integration is a v4.0+ concern. |
| Digest as a chat/conversation | User receives digest → replies in conversational thread → agent responds → back-and-forth. | The existing HITL conversational follow-up already provides this for individual captures. A digest-as-conversation adds significant complexity to what is a one-way weekly summary. AG-UI threading would need to be redesigned for asynchronous digest flows. | Digest is a one-way push notification with deep link to inbox. If user wants to act on something in the digest, they tap through to the item. Conversation mode only for explicit capture follow-ups (already exists). |
| Multiple agents notifying independently | Admin Agent, People Agent, Projects Agent, Ideas Agent each fire independently. | Uncoordinated agents create notification storms. User sees 4 notifications in 10 minutes on Friday evening. Leads to opt-out. | Orchestrator coordinates notification scheduling: a single daily/weekly "budget" per agent. All agents compete for a shared slot. Max 3 nudges per day total across all agents. |

---

## Feature Dependencies

```
[Push token registration (device → backend)]
    └──required by──> [All proactive push notifications]
                          └──required by──> [Admin digest]
                          └──required by──> [Ideas nudge]
                          └──required by──> [Projects check-in]
                          └──required by──> [People nudge]

[APScheduler in FastAPI lifespan]
    └──required by──> [Scheduled proactive agent runs]
                          └──required by──> [All nudge types above]

[Specialist agents created in Foundry at startup]
    └──required by──> [Agent-generated notification copy]
                          └──built on──> [Foundry Agent Service (v1 migration)]

[People bucket captures with last_interaction tracking]
    └──required by──> [People Agent relationship nudges]

[Projects Agent action item extraction]
    └──required by──> [Projects Agent progress check-in]
    (check-in references open action items; extraction must exist first)

[Notification action buttons (Expo categories)]
    └──enhances──> [Snooze/dismiss behavior]
    └──requires──> [Backend /api/nudge/respond endpoint]

[Notification deep links]
    └──requires──> [Expo Router deep link configuration]
    └──requires──> [Notification data payload with item ID]

[Foundry Agent Service infrastructure (v1 migration output)]
    └──required by──> [All specialist agents]
    (specialist agents use AzureAIAgentClient, same as Classifier)

[Notification frequency budget / rate limiting]
    └──conflicts with──> [Independent per-agent scheduling]
    (agents must coordinate through shared budget, not fire independently)
```

### Dependency Notes

- **Push token registration is Day 1:** Nothing proactive works without the device token stored server-side. This is the first thing to build in the proactive layer, before any agent scheduler.
- **APScheduler is the trigger layer:** Foundry Agent Service has no built-in scheduled triggers. Azure Logic Apps connectors are the official path but add infrastructure overhead. APScheduler in FastAPI lifespan is the correct pattern — it is lightweight, integrates with async FastAPI, and requires zero additional Azure resources. Official documentation confirms Logic Apps as the trigger path for Foundry agents, but APScheduler with direct agent calls is simpler and appropriate for a single-user app.
- **Projects check-in requires action item extraction:** The check-in message "2 action items are open" requires that action items were extracted and stored. Build extraction first, check-in second.
- **People Agent requires last_interaction field:** The nudge fires based on interaction gap. This field must be written on every People classification. It is a small Cosmos DB schema addition to the existing `classify_and_file` tool.
- **Notification coordination required:** All agents must route through a shared notification budget before firing. This prevents notification storms. Implement as a simple `NotificationBudget` utility that checks per-day counts before sending.

---

## MVP Definition

### Launch With (v2.0 — Proactive Second Brain)

Minimum viable proactive layer. Validates the core shift from filing cabinet to thinking partner.

- [ ] **Push token registration** — App registers on startup, token stored in Cosmos DB. Without this, nothing works.
- [ ] **APScheduler in FastAPI lifespan** — Cron-based trigger for all scheduled agent runs.
- [ ] **People Agent: relationship nudge** — Scan People documents daily, fire nudge if last_interaction > 4 weeks. This is the highest-value agent for a personal system. Single user — Will gets nudged about specific people he's captured. Uses existing People captures from v1.
- [ ] **Admin Agent: Friday evening digest** — One notification per week summarizing pending Admin captures. Low complexity, high visible value. Proves the digest pattern.
- [ ] **Admin Agent: errand timing** — Classify errand-type Admin captures, surface on weekend morning vs weekday evening. Time-window heuristic only (no geofencing).
- [ ] **Ideas Agent: weekly nudge** — Pick one idea per week, generate "any new thoughts on X?" notification. Keeps the Ideas bucket alive.
- [ ] **Notification frequency budget** — Max 3 nudges/day total, max 2/week per agent. Prevents notification storms.
- [ ] **Quiet hours enforcement** — No notifications 9pm–8am. Server-side check in scheduler.

### Add After Validation (v2.x)

Features to add once the core proactive loop is proven working and Will is actually opening notifications.

- [ ] **Projects Agent: action item extraction** — Trigger: CLASSIFIED event with bucket=Projects. Adds structured action items. High value but requires new Cosmos DB document type.
- [ ] **Projects Agent: progress check-in** — Weekly "are you on track?" notification. Requires action item extraction to exist first.
- [ ] **Notification action buttons** — "Done" and "Snooze 1 week" buttons on push notifications. Requires Expo category setup + backend respond endpoint.
- [ ] **Notification deep links** — Tap notification → land in relevant item. Requires Expo Router configuration.
- [ ] **last_interaction field on People documents** — Written by `classify_and_file` tool when bucket=People. Required for accurate nudge timing (currently would use capture date as proxy).

### Future Consideration (v3.0+)

- [ ] **Background geofencing** — Location-triggered errand reminders. Requires Expo bare workflow or dev build. Defer until time-window approach proves insufficient.
- [ ] **Per-person nudge frequency settings** — Customizable thresholds. Defer until Will asks for it explicitly.
- [ ] **Calendar integration** — Block time for action items. Requires OAuth calendar scope.
- [ ] **Digest as conversation** — Reply to weekly digest and get agent response. Complex threading redesign.
- [ ] **People Agent: upcoming occasions awareness** — "Emma's birthday is in 3 weeks — you mentioned it in a capture last year." Requires date extraction from capture text.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Push token registration | HIGH (blocker) | LOW | P1 |
| APScheduler integration | HIGH (blocker) | LOW | P1 |
| People Agent: relationship nudge | HIGH | LOW | P1 |
| Admin Agent: Friday digest | HIGH | LOW | P1 |
| Admin Agent: errand timing | MEDIUM | LOW | P1 |
| Ideas Agent: weekly nudge | MEDIUM | LOW | P1 |
| Notification frequency budget | HIGH (prevents opt-out) | LOW | P1 |
| Quiet hours enforcement | HIGH (prevents opt-out) | LOW | P1 |
| Notification action buttons (snooze/done) | MEDIUM | MEDIUM | P2 |
| Notification deep links | MEDIUM | MEDIUM | P2 |
| last_interaction field on People | HIGH | LOW | P2 |
| Projects Agent: action item extraction | HIGH | HIGH | P2 |
| Projects Agent: progress check-in | HIGH | MEDIUM | P2 (after extraction) |
| Background geofencing | MEDIUM | HIGH | P3 |
| Per-person nudge frequency settings | LOW | MEDIUM | P3 |
| Calendar integration | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v2.0 to deliver on "proactive" promise
- P2: Add when core loop is validated and working
- P3: Defer — adds complexity before core is proven

---

## Agent Behavior Specifications

### Admin Agent

**Trigger 1: Friday evening digest**
- Schedule: Friday 5:00pm (user's local timezone, default UTC+0)
- Data: All Admin bucket Cosmos DB documents with `status != "archived"`
- Behavior: Agent reads Admin captures, ranks by urgency/type (errands > appointments > admin tasks), generates a 3–5 item digest summary
- Notification: Single push notification with title "Weekend planning" and body listing top items
- Rate: Once per week maximum

**Trigger 2: Errand timing nudge**
- Schedule: Saturday 9am (weekend), Friday 6pm (weekday alternative)
- Data: Admin captures classified as errand-type (e.g., "buy", "pick up", "drop off", "get")
- Behavior: Agent reads errand captures, generates contextual reminder
- Notification: "You have 3 errands captured — good time to knock them out" with item list
- Rate: Once per weekend maximum; skip if digest already covered them

### Ideas Agent

**Trigger: Weekly idea check-in**
- Schedule: Random day Tuesday–Thursday (avoids Monday cold start, avoids Friday digest noise), 10am
- Data: Ideas bucket captures, sorted by `last_nudged_at` ascending (oldest first)
- Behavior: Agent reads the stalest idea, generates a natural "any new thoughts?" prompt referencing the original capture text
- Notification: "Still thinking about [idea excerpt]? Any new angles?"
- Rate: One idea per week; mark `last_nudged_at` after send to rotate through all ideas

### Projects Agent

**Trigger: Weekly progress check-in**
- Schedule: Monday 9am (start of week framing is effective for accountability)
- Data: Projects captures grouped by inferred project name; open action items
- Behavior: Agent reads project captures from past 2 weeks, identifies open action items, generates accountability check-in
- Notification: "You have 2 open items on [project]. Are you on track this week?"
- Rate: Once per active project per week; skip projects with no activity in 30 days

**Trigger: Action item extraction (real-time)**
- Trigger: CLASSIFIED event with bucket=Projects (not a scheduled job — runs immediately after classification)
- Data: The newly classified Projects capture text
- Behavior: Agent reads the capture, extracts explicit action items ("I need to...", "have to...", "must..."), writes them as `action_item` documents to Cosmos DB
- Rate: Fires on every Projects classification

### People Agent

**Trigger: Relationship gap nudge**
- Schedule: Daily scan at 8am; only fires notification if someone exceeds gap threshold
- Data: All People bucket documents; `last_interaction` timestamp (or capture `created_at` as fallback)
- Behavior: Agent reads People documents, finds contacts where gap > threshold, generates personalized reconnect nudge referencing last capture content
- Notification: "It's been 6 weeks since you mentioned Marcus. Worth a check-in? Last you noted: [excerpt]"
- Default threshold: 4 weeks
- Rate: Maximum 1 People nudge per day total across all contacts

---

## Notification Infrastructure Requirements

### Backend (FastAPI)

| Component | Purpose | Implementation |
|-----------|---------|----------------|
| `POST /api/device/register` | Store Expo push token per user | Cosmos DB write; update on every app startup |
| `GET /api/nudge/pending` | List pending nudges | For app-side badge count |
| `POST /api/nudge/respond` | Mark nudge done/snoozed | Updates Cosmos DB nudge record; resets last_nudged_at |
| APScheduler setup in lifespan | Run scheduled agent jobs | `AsyncIOScheduler` started in FastAPI `lifespan()` context manager |
| `NotificationBudget` utility | Enforce per-agent and total frequency limits | Reads nudge history from Cosmos DB before each send |

### Expo App

| Component | Purpose | Implementation |
|-----------|---------|----------------|
| Push token registration | Register device on startup | `getExpoPushTokenAsync()` on app load, POST to backend |
| Notification handler | Process incoming notifications | `addNotificationResponseReceivedListener` |
| Deep link handler | Navigate to item on tap | Expo Router + notification `data.itemId` |
| Notification categories | Action buttons (snooze/done) | `setNotificationCategoryAsync` — P2 feature |

### Scheduling Infrastructure

APScheduler is the correct choice for this project (MEDIUM confidence, multiple sources confirm pattern):

- `AsyncIOScheduler` integrates with FastAPI's async event loop
- Started/stopped in `lifespan()` context manager alongside AI client
- Cron triggers for time-based jobs (Friday digest, weekly check-ins)
- Interval trigger for daily scans (People Agent gap check)
- Each scheduled job: authenticate to Cosmos DB → create Foundry agent session → run agent → send notification via Expo Push API

**Alternative considered:** Azure Logic Apps triggered Foundry agents (official Microsoft recommendation). Rejected for this project: adds Azure resource overhead, requires Logic Apps configuration management, and provides no advantage for a single-user app with simple scheduling needs. APScheduler keeps all scheduling logic in Python, visible in code, and requires zero additional infrastructure.

---

## Competitor Feature Analysis

| Feature | Clay (personal CRM) | Todoist AI | Our Approach |
|---------|---------------------|------------|--------------|
| Relationship nudges | Syncs contacts, timeline of interactions, smart reconnect reminders | N/A | Same pattern — capture-driven, not contact-import-driven. No OAuth required. |
| Idea tracking | N/A | N/A | Weekly check-in nudge is unique — no mainstream app does this well |
| Project accountability | N/A | Smart scheduling, AI task suggestions | Our agent reads Will's own captures — more personal context than Todoist |
| Digest / weekly summary | N/A | Weekly review feature | Friday evening framing is deliberate — matches planning mental model |
| Errand timing | N/A | Location reminders (requires GPS permission) | Time-window heuristic is simpler and avoids permission friction |
| Notification copy | Template-based | Template-based | Agent-generated copy referencing actual capture content is the differentiator |

---

## Sources

- [Expo Notifications SDK documentation](https://docs.expo.dev/versions/latest/sdk/notifications/) — push token, local scheduling, background handling, Android 12+ permissions
- [Expo Location SDK — geofencing capabilities and limitations](https://docs.expo.dev/versions/latest/sdk/location/) — 20-region iOS limit, Android terminated-app limitation, background task requirements
- [Expo Geofencing issue #25875](https://github.com/expo/expo/issues/25875) — Android geofencing not working as expected (open issue)
- [Shape of AI — Nudge UX Patterns](https://www.shapeof.ai/patterns/nudges) — contextual nudges, frequency restraint, "too many nudges crowd the surface"
- [Smashing Magazine — Designing for Agentic AI](https://www.smashingmagazine.com/2026/02/designing-agentic-ai-practical-ux-patterns/) — autonomy dial, intent preview, escalation pathway, action audit
- [OneSignal — Frequency Capping](https://onesignal.com/blog/prevent-overmessaging-frequency-capping/) — notification fatigue, 2–5 notifications/week optimal ceiling
- [Clarify — Top Personal CRM Apps 2025](https://www.getclarify.ai/blog/top-personal-crm-apps-to-boost-your-relationship-management-in-2025) — Clay, Dex, Covve reconnect nudge patterns
- [Personal CRM blog — relationship maintenance system](https://blog.annabyang.com/system-to-maintain-relationships/) — reconnect frequency configuration, monthly vs weekly cadences
- [Gravitec — Weekly Digest Automation](https://gravitec.net/blog/automation-features-daily-and-weekly-digests/) — Friday 9pm digest cadence evidence
- [MoEngage — Push Notification Best Practices 2025](https://www.moengage.com/learn/push-notification-best-practices/) — 2–5 per week limit, timing optimization, personalization impact
- [FastAPI APScheduler pattern](https://rajansahu713.medium.com/implementing-background-job-scheduling-in-fastapi-with-apscheduler-6f5fdabf3186) — AsyncIOScheduler with FastAPI lifespan
- [Azure AI Foundry triggers documentation](https://github.com/MicrosoftDocs/azure-ai-docs/blob/main/articles/ai-foundry/agents/how-to/triggers.md) — Logic Apps as official trigger path (APScheduler chosen as simpler alternative)
- [Proactive AI Agents Guide 2025](https://www.emilingemarkarlsson.com/blog/proactive-ai-agents-guide-2025/) — trigger-action-feedback loop, polling vs event-driven patterns
- [CleverTap — 62% notification annoyance statistic](https://clevertap.com/blog/push-notification-metrics-ctr-open-rate/) — notification fatigue data point

---
*Feature research for: The Active Second Brain — v2.0 Proactive Specialist Agents*
*Researched: 2026-02-25*
