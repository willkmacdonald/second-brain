# Product Requirements Document: The Active Second Brain (2026 Edition)
## v0.9 — Development Approach Added

---

## 1. Executive Summary & Vibe Check

**Vision:** To shift from a passive "storage unit" for notes (which fail because they require too much maintenance) to an **active agentic loop** that works while you sleep.

**Core Philosophy:** The brain is for thinking, not storage. Traditional systems fail because they force cognitive work (organizing, tagging) at the moment of capture. This system removes that friction entirely.

**Target Audience:** Will. A manufacturing industry advisor by day, AI hobbyist developer by night, who needs a reliable system to close open cognitive loops across two very different "modes" of life.

**What changed in v0.8:** The system uses a **multi-agent handoff pattern** built on Microsoft Agent Framework with **seven specialist agents**. An Orchestrator Agent receives all user input and hands off to specialists — perception (media→text), classification (text→bucket), action sharpening (vague→executable), digest composition, entity resolution, and system evaluation. A dedicated **Action Agent** enforces Principle 7 (Next Action is King). A dedicated **Evaluation Agent** (Phase 4) reviews the performance of all other agents across four dimensions: classification accuracy, stale content, action quality, and system performance — an agent that evaluates agents. This architecture is chosen deliberately to learn multi-agent orchestration patterns.

---

## 2. Core Principles (The "Vibe Code")

*These 12 principles govern the system's design to ensure trust and maintainability.*

1. **Single Reliable Behavior:** The user has only *one* job: Capture the thought. Everything else is automation.
2. **Decoupled Architecture:** Separate Capture (Expo app), Intelligence (Agent team), and Memory (Cosmos DB). Modular upgrades are easy.
3. **Prompts as APIs:** Each agent has strict instructions and typed tool contracts. Not creative writing exercises.
4. **Trust Mechanisms:** Visibility (OpenTelemetry tracing across all agents, audit logs in Cosmos DB) is more important than raw capability.
5. **Fail Safe:** When a specialist is uncertain, it owns the clarification conversation directly with the user — rather than guessing and polluting the database.
6. **Small, Actionable Output:** Daily digests must fit on a phone screen (<150 words). Huge reports get ignored.
7. **Next Action is King:** Projects must store executable next actions (e.g., "Email Sarah"), not vague intentions.
8. **Routing > Organizing:** Don't force the user to maintain a taxonomy. Agents route items into a few stable buckets.
9. **Minimalist Data Models:** Keep fields "painfully small" to ensure adoption. Complexity can be added later.
10. **Design for Restart:** If the user stops for a week, they should be able to restart without a "backlog monster" causing guilt.
11. **Core Loop First:** Build the basic Capture → Classify → Route → Digest loop before adding fancy features.
12. **Maintainability:** Optimize for easy fixes over elegant code. OpenTelemetry and Agent Framework DevUI help here.

---

## 3. Architecture Overview

```
┌──────────────────┐
│   CAPTURE LAYER  │
│  Expo/React      │
│  Native App      │       AG-UI Protocol
│                  │      (SSE event stream)
│  • Text input    │
│  • Voice record  │  Events: TEXT_MESSAGE_*
│  • Camera/photo  │          TOOL_CALL_*
│  • Video clip    │          STATE_DELTA
│  • Share sheet   │          INTERRUPT (HITL)
└────────┬─────────┘
         │
         │  HTTP POST + SSE
         ▼
┌──────────────────────────────────────────────────────┐
│                  AGENT TEAM                           │
│           Microsoft Agent Framework (Python)           │
│           Hosted on Azure Container Apps               │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │              ORCHESTRATOR AGENT                    │ │
│  │                                                    │ │
│  │  Receives all user input. Decides which            │ │
│  │  specialist handles it. Transfers control.         │ │
│  │  Gets control back when specialist is done.        │ │
│  │                                                    │ │
│  │  Handoff targets:                                  │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐           │ │
│  │  │Perception│ │Classifier│ │  Action   │           │ │
│  │  │  Agent   │ │  Agent   │ │  Agent    │           │ │
│  │  │          │ │          │ │           │           │ │
│  │  │voice→text│ │classifies│ │sharpens   │           │ │
│  │  │image→text│ │& files   │ │vague into │           │ │
│  │  │video→text│ │& clarify │ │next action│           │ │
│  │  └──────────┘ └──────────┘ └──────────┘           │ │
│  │                                                    │ │
│  │  ┌──────────────────┐  ┌──────────────────┐       │ │
│  │  │  Digest Agent     │  │Entity Resolution │       │ │
│  │  │                   │  │     Agent        │       │ │
│  │  │  Composes morning │  │  Nightly: merges │       │ │
│  │  │  briefing, weekly │  │  People records   │       │ │
│  │  │  review            │  │                  │       │ │
│  │  └──────────────────┘  └──────────────────┘       │ │
│  │                                                    │ │
│  │  ┌──────────────────────────────────────────────┐ │ │
│  │  │  Evaluation Agent (Phase 4)                   │ │ │
│  │  │  Reads audit logs + OpenTelemetry + Cosmos DB │ │ │
│  │  │  Weekly system health report + on-demand      │ │ │
│  │  └──────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  All agents share tools for Cosmos DB & Blob Storage   │
│  Built-in: OpenTelemetry tracing, DevUI                │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│                    MEMORY LAYER                       │
│                                                       │
│  ┌──────────────────┐  ┌───────────────────────────┐ │
│  │  Azure Cosmos DB  │  │  Azure Blob Storage       │ │
│  │  (NoSQL/JSON)     │  │  (media files)            │ │
│  │                   │  │                           │ │
│  │  • People         │  │  • Voice recordings       │ │
│  │  • Projects       │  │  • Photos                 │ │
│  │  • Ideas          │  │  • Videos                 │ │
│  │  • Admin          │  │  • Thumbnails             │ │
│  │  • Inbox Log      │  │                           │ │
│  └──────────────────┘  └───────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## 4. The Agent Team

### 4.1 Orchestrator Agent

**Role:** Front door. Receives all input from the Expo app via AG-UI. Decides which specialist should handle it and transfers control.

**LLM:** Azure OpenAI GPT-5.2

**Instructions:**
```
You are the Second Brain orchestrator. You are the front door for all user input.

Your ONLY job is to understand what the user has sent and hand off to the right
specialist. You do NOT classify, file, or compose anything yourself.

Rules:
1. If the input contains audio, image, or video → hand off to Perception Agent
2. If the input is text (or you just got text back from Perception) → hand off to Classifier Agent
3. If the Classifier filed to Projects or Admin → hand off to Action Agent to sharpen the next action
4. If the Classifier filed to People or Ideas → no further handoff needed, confirm to user
5. If the user asks "what's on my plate today" or requests a summary → hand off to Digest Agent
6. If the user asks "how is my system doing" or about system performance → hand off to Evaluation Agent
7. Keep your own messages extremely brief — you're a router, not a conversationalist

You always know who handled what, and you provide a short confirmation when the
chain completes.
```

**Handoff targets:** Perception Agent, Classifier Agent, Action Agent, Digest Agent, Evaluation Agent

**Tools:** None — the orchestrator delegates, it doesn't act on data directly.

---

### 4.2 Perception Agent

**Role:** Converts non-text input into text. Owns the multimodal processing conversation.

**LLM:** Azure OpenAI GPT-5.2 (with Vision)

**Instructions:**
```
You are the Perception Agent. You convert non-text captures into usable text.

For voice: Use the transcribe_audio tool to get a transcription.
For images: Describe what you see. Extract any text (OCR). Summarize the key information.
For video: Use transcribe_audio on the audio track and describe the keyframe.

If the transcription is garbled or the image is unclear, ask the user:
"I couldn't make this out clearly. Can you tell me what this was about?"

When done, return the processed text to the orchestrator so it can hand off to
the Classifier Agent.
```

**Tools:**
| Tool | Description |
|------|------------|
| `transcribe_audio(media_url)` | Calls Azure OpenAI Whisper. Returns transcription text. |
| `store_media(file, type)` | Uploads to Azure Blob Storage. Returns URL. |

**Handoff behavior:** Receives control from Orchestrator. Can have a multi-turn conversation with the user if input is unclear. When done, returns processed text and control flows back to Orchestrator → Classifier.

---

### 4.3 Classifier Agent

**Role:** The core brain. Classifies input, files it, handles cross-references, and owns the clarification conversation when confidence is low.

**LLM:** Azure OpenAI GPT-5.2

**Instructions:**
```
You are the Classifier Agent. You receive processed text and your job is to:

1. Classify it into ONE bucket: people, projects, ideas, or admin
2. Extract cross-references (people mentioned, projects referenced)
3. File it using your tools

Bucket definitions:
- "people": Mentions a specific person, relationship, or follow-up with someone
- "projects": Relates to an ongoing effort with multiple steps (work or hobby)
- "ideas": A standalone insight, concept, or "what if" thought
- "admin": A concrete task with a deadline or logistical action

Context about the user:
- Day job: Microsoft Manufacturing Industry Advisor (MedTech focus)
- Hobby: AI/Python development projects
- Personal: Child at Lane Tech, woodworking

When you are confident (>= 0.6):
- File the record using file_to_bucket
- Update any cross-referenced people or projects
- Return a brief confirmation: "Filed → Projects (0.85)"

When you are NOT confident (< 0.6):
- Tell the user your best guess and reasoning
- Ask a specific clarifying question
- Example: "This mentions 'Mike' and a deadline. Is this a follow-up with
  Mike (People) or a task you need to do (Admin)?"
- File after the user clarifies

Always check existing people and projects before creating new records.
```

**Tools:**
| Tool | Description |
|------|------------|
| `get_existing_people()` | Returns list of People records from Cosmos DB |
| `get_active_projects()` | Returns list of active Projects from Cosmos DB |
| `file_to_bucket(bucket, data)` | Creates a new record in the specified Cosmos DB container |
| `update_person(person_id, updates)` | Updates a People record (contact details, birthday, lastInteraction, interactionHistory, followUps) |
| `update_project(project_id, updates)` | Updates a Project record (e.g., notes, nextAction) |
| `log_to_inbox(capture_data)` | Writes the full capture record to the Inbox Log |

**Handoff behavior:** Receives control from Orchestrator. If confident, silently files and returns. If uncertain, has a focused clarification conversation with the user — potentially multiple turns — then files and returns control.

---

### 4.4 Action Agent

**Role:** Sharpens vague thoughts into concrete, executable next actions. Only handles items classified as Projects or Admin — People and Ideas skip this agent entirely.

**LLM:** Azure OpenAI GPT-5.2

**Instructions:**
```
You are the Action Agent. You receive items that have been classified as either
a Project or an Admin task. Your job is to sharpen the captured thought into a
specific, executable next action.

Rules:
- Turn vague intentions into concrete steps someone could do in one sitting
- BAD:  "Rethink the layout approach"
- GOOD: "Draft two alternative layout strategies and compare results in a test deck"
- BAD:  "Deal with car registration"
- GOOD: "Go to ilsos.gov and renew registration online — due March 15"

- If you need more context to sharpen the action, ask the user:
  "What's the first concrete step you'd take on this?"

- Once you have a sharp action, update the record using your tools

- For Projects: set the nextAction field
- For Admin: ensure the task description is specific and has a due date if possible

Context about the user:
- Day job: Microsoft Manufacturing Industry Advisor (MedTech focus)
- Hobby: AI/Python development projects
- Personal: Child at Lane Tech, woodworking
```

**Tools:**
| Tool | Description |
|------|------------|
| `update_project(project_id, updates)` | Set nextAction on a Project record |
| `update_admin(admin_id, updates)` | Update task description or dueDate on an Admin record |
| `get_active_projects()` | Context: see existing projects to connect related items |

**Handoff behavior:** Receives control from Orchestrator after Classifier files a Projects or Admin item. Reads the filed record, sharpens the action, updates the record, returns control. Can ask the user one clarifying question if the thought is too vague to actionize.

---

### 4.5 Digest Agent

**Role:** Composes the daily briefing and weekly review. Can answer ad-hoc "what's on my plate" questions.

**LLM:** Azure OpenAI GPT-5.2

**Instructions:**
```
You are the Digest Agent. You compose concise, actionable briefings for Will.

For daily digests (triggered at 6:30 AM CT):
- Use your tools to gather active projects, due items, and needs-review items
- Compose a briefing under 150 words in this format:

  ## Today's Focus
  1. [Most important action]
  2. [Second action]
  3. [Third action]

  ## Unblock This
  [One stuck/waiting item that needs attention]

  ## Small Win
  [One thing completed recently or progress to acknowledge]

For weekly reviews (triggered Sunday 9 AM CT):
- Summarize all activity from the past 7 days
- Identify recurring themes, stalled projects, forgotten people

For ad-hoc requests ("what's on my plate"):
- Pull the same data and compose a brief answer

Keep everything concise. Will reads this on his phone while making breakfast.
```

**Tools:**
| Tool | Description |
|------|------------|
| `get_active_projects()` | Projects with status `active` |
| `get_due_today()` | Admin items due today |
| `get_due_this_week()` | Admin items due this week |
| `get_needs_review()` | Items awaiting human review |
| `get_recent_captures(days)` | Captures from the last N days |
| `get_stalled_projects(days)` | Projects with no activity in N days |
| `get_neglected_people(days)` | People with no interaction in N days |
| `get_upcoming_birthdays(days)` | People with birthdays in the next N days |

**Handoff behavior:** Receives control from Orchestrator (either timer-triggered or user request). Composes briefing, delivers to user, returns control.

---

### 4.6 Entity Resolution Agent

**Role:** Nightly maintenance agent that reconciles person references across the day's captures.

**LLM:** Azure OpenAI GPT-5.2

**Instructions:**
```
You are the Entity Resolution Agent. You run nightly at 2:00 AM CT.

Review today's captures that mention people and reconcile them against
existing People records.

Rules:
- "Don" and "Don Cheeseman" → confident match → merge using merge_people
- "Mike" when there are two Mikes → ambiguous → flag using flag_ambiguous
- A completely new name with no match → create new People record
- Always explain your reasoning in the merge log

Be conservative: when in doubt, flag rather than merge incorrectly.
```

**Tools:**
| Tool | Description |
|------|------------|
| `get_all_people()` | Full People container contents |
| `get_todays_person_references()` | All personNames from today's captures |
| `merge_people(source_id, target_id)` | Merge two People records |
| `create_person(data)` | Create a new People record |
| `flag_ambiguous(name, candidate_ids)` | Flag for morning digest review |

**Handoff behavior:** Timer-triggered, no user interaction. Runs autonomously, logs actions.

---

### 4.7 Evaluation Agent (Phase 4 — Design Only)

**Role:** Meta-agent that reviews the performance of the entire Second Brain system. Reads audit logs, OpenTelemetry traces, and Cosmos DB state to generate an honest assessment of how well the system is serving Will. Runs weekly on auto-pilot and on-demand when asked "how is my system doing?"

**LLM:** Azure OpenAI GPT-5.2

**Instructions:**
```
You are the Evaluation Agent. You are the quality inspector for the Second Brain.
Your job is to honestly assess how well the other agents are performing and
whether the system is actually helping Will stay on top of his life.

You evaluate four dimensions:

1. CLASSIFICATION ACCURACY
   - How often did the Classifier need to ask for clarification? (HITL rate)
   - Were there patterns in what confused it? (e.g., Projects vs Ideas confusion)
   - Did the user ever correct a classification after filing? (reclassification rate)
   - Are confidence scores trending up or down over time?
   - Recommendation: Should bucket definitions be updated? Should the Classifier
     get additional context?

2. STALE CONTENT
   - Which Projects have had no new captures in 2+ weeks?
   - Which People haven't been contacted in 30+ days?
   - Are there Admin items past their due date?
   - How many Ideas have been sitting untouched since capture?
   - Recommendation: Suggest items to archive, complete, or resurface.

3. ACTION QUALITY
   - How many next actions did the Action Agent generate this period?
   - How many of those were completed (status changed to done)?
   - What's the completion rate? Is it improving or declining?
   - Are there patterns in uncompleted actions? (too ambitious, wrong domain, etc.)
   - Recommendation: Should the Action Agent sharpen differently? Are actions
     too granular or too vague?

4. SYSTEM PERFORMANCE
   - Average capture-to-filed latency (end to end)
   - Latency breakdown by agent (Perception, Classifier, Action)
   - Total LLM token usage and estimated cost this period
   - Error rate (failed tool calls, LLM timeouts, Cosmos DB errors)
   - Recommendation: Any agents that need optimization or are costing too much?

Output format for weekly report:

## Second Brain Health Report — Week of {date}

### 📊 By the Numbers
- Captures this week: {n}
- Classification accuracy: {n}% first-try (no HITL needed)
- Actions generated: {n} | Completed: {n} ({n}%)
- Avg capture-to-filed: {n}s

### 🎯 Classification
{analysis and recommendations}

### 🧊 Stale Content
{items that need attention}

### ⚡ Action Quality
{analysis of action completion patterns}

### 🔧 System Performance
{latency, cost, errors}

### 💡 Recommendations
1. {Most important systemic improvement}
2. {Second recommendation}
3. {Third recommendation}

Keep the report concise but specific. Use actual numbers, not vague assessments.
Name specific projects, people, and patterns.
```

**Tools:**
| Tool | Description |
|------|------------|
| `get_captures_for_period(start, end)` | All inbox records in a date range |
| `get_hitl_events(start, end)` | Captures where classifier confidence < 0.6 |
| `get_reclassifications(start, end)` | Captures where `correctedBy` is not null |
| `get_stalled_projects(days)` | Projects with no activity in N days |
| `get_neglected_people(days)` | People with no interaction in N days |
| `get_overdue_admin()` | Admin items past their due date |
| `get_idle_ideas(days)` | Ideas with no updates since capture |
| `get_action_completion_rate(start, end)` | Actions generated vs. completed |
| `get_uncompleted_actions(start, end)` | Actions that were generated but never done |
| `query_otel_traces(start, end)` | Agent latency, error rates, handoff timing from OpenTelemetry |
| `get_token_usage(start, end)` | LLM token counts and estimated cost by agent |
| `get_error_log(start, end)` | Failed tool calls, timeouts, exceptions |

**Triggers:**
- **Weekly auto-report:** Sunday at 7:00 PM CT. Report is stored and surfaced in Monday morning's digest as a "System Health" section.
- **On-demand:** User asks "how is my system doing?" → Orchestrator hands off to Evaluation Agent → agent runs analysis and returns report in the conversation.

**Handoff behavior:** Receives control from Orchestrator (on-demand) or runs via timer (weekly). Queries all data sources, composes report, returns to Orchestrator or stores for digest. No HITL needed — this agent is read-only, it never modifies data.

**Data dependencies:** This agent needs access to:
- Cosmos DB (all containers — for content analysis)
- OpenTelemetry backend (Azure Monitor / Application Insights — for performance data)
- Token usage tracking (needs a lightweight counter that each agent increments per LLM call)

**Why Phase 4:** The Evaluation Agent can only be useful once there's enough data to evaluate. It needs several weeks of captures, classifications, and action completions before patterns emerge. Building it early would produce empty reports.

---

## 5. Handoff Flow: Capture Pipeline

Here's what happens when Will grabs his phone and says "Maybe rethink the layout approach for pptx":

```
                         Will's phone
                             │
                      ┌──────┴──────┐
                      │  Voice note  │
                      │  captured    │
                      └──────┬──────┘
                             │  AG-UI POST
                             ▼
                    ┌─────────────────┐
                    │  ORCHESTRATOR   │
                    │                 │
                    │  "This is audio │
                    │   → Perception" │
                    └────────┬────────┘
                             │  handoff
                             ▼
                    ┌─────────────────┐
                    │  PERCEPTION     │
                    │  AGENT          │
                    │                 │
                    │  transcribe()   │──→ "Maybe rethink the layout approach for pptx"
                    │  store_media()  │──→ blob URL saved
                    │                 │
                    │  Returns text   │
                    └────────┬────────┘
                             │  control returns to orchestrator
                             ▼
                    ┌─────────────────┐
                    │  ORCHESTRATOR   │
                    │                 │
                    │  "Got text back │
                    │   → Classifier" │
                    └────────┬────────┘
                             │  handoff
                             ▼
                    ┌─────────────────┐
                    │  CLASSIFIER     │
                    │  AGENT          │
                    │                 │
                    │  Confidence 0.85│
                    │  Bucket:projects│
                    │                 │
                    │  file_to_bucket │──→ Project record created
                    │  ("projects",   │    (PPTX Automation)
                    │   {...})        │
                    │                 │
                    │  log_to_inbox() │──→ Audit record written
                    │                 │
                    │  Returns:       │
                    │  "Filed →       │
                    │   Projects"     │
                    └────────┬────────┘
                             │  control returns to orchestrator
                             ▼
                    ┌─────────────────┐
                    │  ORCHESTRATOR   │
                    │                 │
                    │  "Filed to      │
                    │   Projects →    │
                    │   Action Agent" │
                    └────────┬────────┘
                             │  handoff
                             ▼
                    ┌─────────────────┐
                    │  ACTION AGENT   │
                    │                 │
                    │  Reads filed    │
                    │  record:        │
                    │  "Maybe rethink │
                    │   the layout    │
                    │   approach"     │
                    │                 │
                    │  Sharpens to:   │
                    │  "Draft two     │
                    │   alternative   │
                    │   layout        │
                    │   strategies    │
                    │   and compare   │
                    │   in a test     │
                    │   deck"         │
                    │                 │
                    │  update_project │──→ nextAction updated
                    └────────┬────────┘
                             │  control returns to orchestrator
                             ▼
                    ┌─────────────────┐
                    │  ORCHESTRATOR   │
                    │                 │
                    │  AG-UI stream:  │
                    │  "✓ Filed →     │──→ Will's phone shows confirmation
                    │   Projects      │
                    │   (PPTX Auto.)  │
                    │   Next: Draft   │
                    │   two layout    │
                    │   strategies"   │
                    └─────────────────┘
```

### People/Ideas Flow (skips Action Agent):

```
  "Don mentioned a great fishing spot"

  Orchestrator → Perception → Classifier
                                  │
                          Bucket: People
                          Confidence: 0.91
                          file_to_bucket() ──→ People record updated
                                  │
                          Returns to Orchestrator
                                  │
                          "✓ Filed → People (Don Cheeseman)"
                          
  (No Action Agent — People don't need sharpened next actions)
```

### Low-Confidence Flow (Classifier owns the clarification):

```
                    ┌─────────────────┐
                    │  CLASSIFIER     │
                    │  AGENT          │
                    │                 │
                    │  Confidence 0.42│
                    │                 │
                    │  AG-UI stream:  │
                    │  "You mentioned │──→ Will sees question on phone
                    │   'Mike' and a  │
                    │   deadline. Is  │
                    │   this a follow-│
                    │   up with Mike  │
                    │   (People) or a │
                    │   task (Admin)?'│
                    └────────┬────────┘
                             │
                      Will taps "Admin"
                             │
                    ┌────────┴────────┐
                    │  CLASSIFIER     │
                    │  AGENT          │
                    │                 │
                    │  file_to_bucket │──→ Admin record created
                    │  ("admin", ...) │
                    │                 │
                    │  "Filed → Admin"│──→ Will sees confirmation
                    └────────┬────────┘
                             │  control returns to orchestrator
                             ▼
                    ┌─────────────────┐
                    │  ORCHESTRATOR   │
                    │  "✓ All done"   │
                    └─────────────────┘
```

---

## 6. Shared Tool Library

All agents share a common set of Cosmos DB and Blob Storage tools. Each agent only gets the tools relevant to its role (listed in Section 4).

### Cosmos DB Tools
```python
@tool
def file_to_bucket(bucket: str, data: dict) -> dict:
    """Create a new record in the specified container (people/projects/ideas/admin)."""

@tool
def log_to_inbox(capture_data: dict) -> dict:
    """Write a capture record to the Inbox Log with classification details."""

@tool
def get_existing_people() -> list[dict]:
    """Return all People records (name, id, context, lastInteraction, contact, birthday)."""

@tool
def get_active_projects() -> list[dict]:
    """Return Projects with status 'active' (name, id, nextAction, mode)."""

@tool
def update_person(person_id: str, updates: dict) -> dict:
    """Update a People record (contact, birthday, lastInteraction, interactionHistory, followUps)."""

@tool
def update_project(project_id: str, updates: dict) -> dict:
    """Update a Project record (notes, nextAction, status)."""

@tool
def update_admin(admin_id: str, updates: dict) -> dict:
    """Update an Admin record (task description, dueDate, status)."""

@tool
def get_due_today() -> list[dict]:
    """Return Admin items with dueDate = today."""

@tool
def get_due_this_week() -> list[dict]:
    """Return Admin items with dueDate within this week."""

@tool
def get_needs_review() -> list[dict]:
    """Return inbox items with status 'needs_review'."""

@tool
def get_recent_captures(days: int = 1) -> list[dict]:
    """Return captures from the last N days."""

@tool
def get_stalled_projects(days: int = 7) -> list[dict]:
    """Return Projects with no new sourceCaptures in N days."""

@tool
def get_neglected_people(days: int = 14) -> list[dict]:
    """Return People with lastInteraction.date older than N days."""

@tool
def get_upcoming_birthdays(days: int = 7) -> list[dict]:
    """Return People with birthdays in the next N days."""

@tool
def merge_people(source_id: str, target_id: str) -> dict:
    """Merge two People records. Source is absorbed into target."""

@tool
def create_person(data: dict) -> dict:
    """Create a new People record."""

@tool
def flag_ambiguous(name: str, candidate_ids: list[str]) -> dict:
    """Flag an ambiguous person reference for morning digest review."""
```

### Blob Storage Tools
```python
@tool
def store_media(file_bytes: bytes, file_type: str) -> str:
    """Upload media to Azure Blob Storage. Returns URL."""

@tool
def transcribe_audio(media_url: str) -> str:
    """Transcribe audio via Azure OpenAI Whisper. Returns text."""
```

---

## 7. Data Schema (Cosmos DB Containers)

**Partition Key for all containers:** `/userId`

### 7.1 Inbox Container
```json
{
  "id": "uuid",
  "userId": "will",
  "capturedAt": "2026-02-21T14:30:00Z",
  "inputType": "voice | text | image | video | share",
  "rawText": "Talk to Don about the MedTech research engine",
  "mediaUrl": "https://blob.../voice-abc123.m4a",
  "transcription": "Talk to Don about the MedTech research engine",
  "classification": {
    "bucket": "projects",
    "confidence": 0.82,
    "reasoning": "References an ongoing multi-step effort",
    "crossRefs": {
      "projects": ["MedTech Research Engine"],
      "people": ["Don Cheeseman"],
      "admin": []
    }
  },
  "handledBy": ["orchestrator", "perception", "classifier", "action"],
  "status": "filed | pending | needs_review",
  "filedTo": "projects/uuid-of-record",
  "correctedBy": null
}
```

### 7.2 People Container (Personal CRM)
```json
{
  "id": "uuid",
  "userId": "will",
  "name": "Don Cheeseman",
  "context": "Old friend from AGT/Telus days",
  "contact": {
    "email": null,
    "phone": null,
    "address": null
  },
  "birthday": null,
  "lastInteraction": {
    "date": "2026-02-15",
    "type": "call | text | email | in-person | mentioned",
    "note": "Talked about fishing trip"
  },
  "followUps": ["Call about fishing trip"],
  "interactionHistory": [
    {
      "date": "2026-02-15",
      "type": "call",
      "note": "Talked about fishing trip"
    },
    {
      "date": "2026-01-20",
      "type": "in-person",
      "note": "Lunch downtown"
    }
  ],
  "createdAt": "2026-02-21T14:30:00Z",
  "sourceCaptures": ["inbox/uuid"]
}
```

The Classifier Agent populates what it can extract from each capture. Contact details, birthday, and address accumulate over time as Will captures things like "Don's birthday is March 12" or "Mike's new email is mike@stryker.com." The `lastInteraction` field always reflects the most recent entry in `interactionHistory`, making it easy for the Digest Agent to surface neglected relationships.

### 7.3 Projects Container
```json
{
  "id": "uuid",
  "userId": "will",
  "name": "MedTech Research Engine",
  "status": "active | waiting | blocked | someday | done",
  "mode": "work | hobby | personal",
  "nextAction": "Test the competitor analysis prompt with Stryker data",
  "notes": [],
  "createdAt": "2026-02-21T14:30:00Z",
  "sourceCaptures": ["inbox/uuid"]
}
```

### 7.4 Ideas Container
```json
{
  "id": "uuid",
  "userId": "will",
  "title": "Use DSPy to learn slide layouts from examples",
  "oneLiner": "Instead of templates, train a model to replicate visual style",
  "notes": "",
  "createdAt": "2026-02-21T14:30:00Z",
  "sourceCaptures": ["inbox/uuid"]
}
```

### 7.5 Admin Container
```json
{
  "id": "uuid",
  "userId": "will",
  "task": "Renew car registration",
  "dueDate": "2026-03-15",
  "status": "pending | done",
  "createdAt": "2026-02-21T14:30:00Z",
  "sourceCaptures": ["inbox/uuid"]
}
```

---

## 8. Tech Stack Summary

| Layer | Technology | Why |
|-------|-----------|-----|
| **Capture** | Expo / React Native (iOS) | Real app, multimodal input, push notifications, share sheet |
| **Protocol** | AG-UI (SSE event stream) | Open standard for agent↔frontend. Real-time streaming, handoff visibility, state sync |
| **Agent Runtime** | Microsoft Agent Framework (Python) | Multi-agent handoff orchestration, function tools, OpenTelemetry, DevUI |
| **Hosting** | Azure Container Apps | Runs the Agent Framework server + AG-UI endpoint. Scales to zero |
| **LLM** | Azure OpenAI (GPT-5.2, Whisper) | Native framework support. Classification, vision, transcription, composition |
| **Memory** | Azure Cosmos DB (NoSQL) | JSON-document store, serverless pricing, free tier |
| **Media** | Azure Blob Storage | Voice, image, video files |
| **Notifications** | Expo Push Notifications | Free, built into Expo |
| **Observability** | OpenTelemetry (built into Agent Framework) | Distributed tracing across all agents in a handoff chain |
| **Dev Tools** | Agent Framework DevUI | Visual debugger — see handoff flow, tool calls, agent reasoning in real time |

---

## 9. The Expo App & AG-UI Integration

### 9.1 Capture UX

**Design Principle:** One thumb, one tap, one thought. No decisions at capture time.

**Main Screen:** Four large buttons — 🎤 Voice, 📷 Photo, 🎥 Video, ✏️ Text

**No settings. No folders. No tags. No decisions.**

### 9.2 AG-UI Connection

The Expo app connects to the Agent Framework backend via AG-UI:

1. **Capture POST** — App sends multipart data to the AG-UI endpoint
2. **SSE stream** — App receives real-time events as agents hand off:
   - Orchestrator: "Processing your voice note..."
   - Perception Agent: "Transcribed: 'Maybe rethink the layout approach for pptx'"
   - Classifier Agent: "Filed → Projects (PPTX Automation)"
   - Action Agent: "Next action: Draft two alternative layout strategies and compare in a test deck"
   - Or: Classifier Agent: "I'm not sure — is this about Mike from work or your neighbor Mike?"
3. **Clarification** — User responds inline, Classifier Agent continues and files
4. **Thread continuity** — AG-UI thread IDs track the full handoff chain

### 9.3 Notification Strategy

- **Silent badge updates** for successful captures
- **Push notification ONLY for:**
  - Clarification requests (agent needs user input)
  - Daily digest (6:30 AM CT)
  - Weekly review (Sunday 9 AM CT)

### 9.4 Screens

1. **Main Screen** — Four capture buttons
2. **Inbox View** — Recent captures with agent chain visible (e.g., Orchestrator → Perception → Classifier → Action)
3. **Digest View** — Morning briefing, opened via push notification
4. **Conversation View** — When a specialist needs clarification, opens a focused chat

---

## 10. Development Approach & Project Structure

### Development Tooling

This codebase is developed with **Claude Code** using the **GSD (Get Shit Done) methodology**. Local `Claude.md` files should reflect best practices for the solution components in this project — agent definitions, tool contracts, Cosmos DB access patterns, AG-UI integration, and Expo app conventions.

If GSD proves to be an impediment to the success of this project, the fallback approach is **spec-driven development**: defining specs, plans, and tasks based on feature cases stored under a `specs/` directory.

### Project Directory Conventions

```
second-brain/
├── Claude.md                  # Root-level Claude Code context
├── design-decisions/          # Architectural decision records
│   ├── 001-agent-framework.md
│   ├── 002-handoff-pattern.md
│   └── ...
├── docs/                      # Active project documentation
│   ├── archive/               # Superseded or historical docs
│   └── ...
├── specs/                     # (Fallback) Feature case specs if GSD is dropped
├── src/
│   ├── agents/                # Agent definitions + instructions
│   │   ├── Claude.md          # Agent-specific best practices
│   │   ├── orchestrator.py
│   │   ├── perception.py
│   │   ├── classifier.py
│   │   ├── action.py
│   │   ├── digest.py
│   │   ├── entity_resolution.py
│   │   └── evaluation.py
│   ├── tools/                 # Shared tool library
│   │   ├── Claude.md          # Tool implementation best practices
│   │   ├── cosmos.py
│   │   └── blob.py
│   ├── app/                   # Expo/React Native app
│   │   └── Claude.md          # Expo + AG-UI best practices
│   └── server/                # AG-UI endpoint + Agent Framework bootstrap
│       └── Claude.md          # Server configuration best practices
└── infrastructure/            # Azure Container Apps, Cosmos DB, Blob config
    └── Claude.md              # Infrastructure best practices
```

---

## 11. Build Phases

### Phase 1: Orchestrator + Classifier (Weeks 1-3)
- [ ] Set up Agent Framework project with AG-UI endpoint
- [ ] Orchestrator Agent (routing logic only)
- [ ] Classifier Agent with tools (classify, file, log)
- [ ] Cosmos DB containers + shared tool library
- [ ] Expo app with text capture + AG-UI SSE connection
- [ ] Deploy to Azure Container Apps
- [ ] Test handoff: Orchestrator → Classifier → file → confirm
- **Goal:** Type a thought → see the handoff chain in real time → record appears in Cosmos DB

### Phase 2: Perception + Action + HITL (Weeks 4-5)
- [ ] Perception Agent (Whisper transcription, GPT-5.2 Vision)
- [ ] Action Agent (sharpen vague thoughts into next actions for Projects/Admin)
- [ ] Full handoff chain: Orchestrator → Perception → Classifier → Action Agent → confirm
- [ ] Low-confidence clarification flow (Classifier ↔ user conversation)
- [ ] Action Agent clarification flow ("What's the first concrete step?")
- [ ] Add voice/photo buttons to Expo app
- [ ] Cross-reference updates (People/Projects backlinks)
- **Goal:** Multimodal capture with full agent chain, action sharpening, and clarification conversations

### Phase 3: Digest Agent (Weeks 6-7)
- [ ] Digest Agent with Cosmos DB query tools
- [ ] Timer-triggered daily digest (6:30 AM CT)
- [ ] Digest view in Expo app
- [ ] Push notifications (Expo Push)
- [ ] Ad-hoc "what's on my plate" via Orchestrator → Digest handoff
- [ ] OpenTelemetry integration for full agent chain tracing
- **Goal:** Morning briefing delivered automatically; ask for a summary anytime

### Phase 4: Meta-Intelligence & Polish (Week 8+)
- [ ] Entity Resolution Agent (nightly timer, fuzzy-match People)
- [ ] Evaluation Agent (weekly auto-report + on-demand)
- [ ] Token usage tracking across all agents
- [ ] OpenTelemetry → Azure Monitor pipeline for Evaluation Agent to query
- [ ] Weekly review digest (incorporating system health section from Evaluation Agent)
- [ ] Full-text search across all buckets
- [ ] Share sheet extension
- [ ] Video capture + keyframe extraction
- [ ] Correction feedback loop (clarification history as few-shot examples)

---

## 12. Resolved Design Decisions

### Round 1 — Core Design (v0.3)

| # | Decision |
|---|----------|
| 1 | **Auth:** API key in Expo Secure Store |
| 2 | **Entity Resolution:** Lazy nightly merge via LLM |
| 3 | **Mode Dimension:** `mode` field on Projects only |
| 4 | **Offline Capture:** Not required |
| 5 | **Cost Ceiling:** Optimize for capability, no hard cap |

### Round 2 — UX Details (v0.4)

| # | Decision |
|---|----------|
| 6 | **Digest timing:** Hardcode 6:30 AM CT |
| 7 | **Cross-bucket linking:** File to primary bucket + extract cross-references |
| 8 | **Capture search:** Deferred to Phase 4 |
| 9 | **Notifications:** Silent confirmations; push only for HITL + digests |

### Round 3 — Architecture (v0.5–v0.6)

| # | Decision |
|---|----------|
| 10 | **Compute:** Microsoft Agent Framework — multi-agent handoff pattern |
| 11 | **LLM:** Azure OpenAI (GPT-5.2, Whisper) |
| 12 | **Protocol:** AG-UI for agent↔frontend communication |
| 13 | **Delegation:** Handoff pattern — orchestrator transfers control to specialists |
| 14 | **Clarification:** Specialist agents own the clarification conversation directly with the user |
| 15 | **Learning goal:** Multi-agent orchestration is an explicit learning objective |
| 16 | **Action sharpening:** Dedicated Action Agent for Projects/Admin. People/Ideas skip it. |
| 17 | **Evaluation:** Dedicated Evaluation Agent. Weekly auto-report (Sunday 7 PM CT, feeds Monday digest) + on-demand. Evaluates classification accuracy, stale content, action quality, system performance. Phase 4 build. |
| 18 | **Development:** Claude Code + GSD methodology. Fallback to spec-driven development under `specs/` if GSD impedes progress. Design decisions in `design-decisions/`, docs in `docs/` with `docs/archive/` for superseded content. |

---

## 13. What Multi-Agent Handoff Teaches You

This architecture deliberately exercises these Agent Framework concepts:

1. **Handoff orchestration** — Orchestrator decides routing, transfers control, receives it back
2. **Conditional handoff** — Action Agent only gets involved for Projects/Admin, not People/Ideas
3. **Agent-specific tools** — Each specialist has tools scoped to its domain
4. **Shared tool library** — Common Cosmos DB/Blob tools reused across agents
5. **Multi-turn conversations** — Classifier and Action agents can have extended HITL dialogs
6. **Timer-triggered agents** — Digest, Entity Resolution, and Evaluation run on schedules
7. **AG-UI event streaming** — Real-time visibility into agent handoff chains
8. **OpenTelemetry** — Distributed tracing across agent boundaries
9. **DevUI** — Visual debugging of multi-agent workflows during development
10. **Meta-agent pattern** — Evaluation Agent reads the outputs and traces of other agents to assess system health. An agent that evaluates agents.

---

## 14. PRD Status

**This PRD is ready for build.** All agent specifications, tool contracts, data schemas, handoff flows, and build phases are defined.

**Next step:** Scaffold the Agent Framework project — Orchestrator + Classifier + AG-UI endpoint for Phase 1.
