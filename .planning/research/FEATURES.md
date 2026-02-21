# Feature Research

**Domain:** Personal Knowledge Management / Second Brain / AI-Powered Capture-and-Intelligence System
**Researched:** 2026-02-21
**Confidence:** MEDIUM-HIGH (multiple competitor products analyzed; feature patterns consistent across sources; some AI-agentic features are emergent and less battle-tested)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Quick text capture** | Every PKM/capture app has one-tap text entry. Users will not tolerate friction at the moment of thought. Braintoss, Drafts, Apple Notes all set this bar. | LOW | Expo text input + POST to AG-UI. Already in PRD. Must feel instant (<200ms to "captured" confirmation). |
| **Voice capture with transcription** | Otter, Whisper Notes, Tana, Mem 2.0, Reflect, Apple Journal all offer voice-to-text. This is table stakes in 2026 for any capture app. | MEDIUM | Azure OpenAI Whisper via Perception Agent. Already in PRD. Accuracy must be high for proper nouns (Will's contacts, project names). |
| **Photo capture with understanding** | Apple Journal, Tana, and multimodal AI tools all process images. Users expect OCR + scene description at minimum. | MEDIUM | GPT-5.2 Vision via Perception Agent. Already in PRD. Key: extracting text from whiteboards, business cards, receipts. |
| **Automatic classification/routing** | Mem pioneered "zero-organization" with AI auto-tagging. Tana supertags auto-classify. Notion AI agents auto-organize. Users of AI-first tools expect the system to file things without manual effort. | HIGH | Classifier Agent with confidence scoring. Core value prop of the system. The 4-bucket model (People/Projects/Ideas/Admin) is simpler than most competitors — this is a strength, not a weakness. |
| **Cross-device sync** | Every modern app (Notion, Obsidian Sync, Reflect, Apple Journal) syncs across devices. Data must be available wherever you are. | LOW | Cosmos DB is the single source of truth; Expo app is a thin client. Already architected this way. |
| **Search across all captures** | Notion, Obsidian, Mem, Capacities, and every PKM tool has search. Users need to find things they captured previously. | MEDIUM | Cosmos DB queries + optional full-text index. PRD defers to Phase 4 — consider moving basic search earlier (keyword match on rawText + title fields). |
| **Push notifications for important events** | Standard mobile app expectation. Users need to know when the system needs their input or has a digest ready. | LOW | Expo Push Notifications. Already in PRD (HITL clarification + digests only). Restrained approach is correct. |
| **Data export / portability** | Obsidian (Markdown files), Logseq (plain text), Monica (REST API) all emphasize data ownership. Users fear lock-in — especially power users. | LOW | Cosmos DB JSON export. Not in PRD but trivial to add. Include a "download my data" function early. |
| **Confirmation feedback** | Users need to know their capture was received and processed. Every capture app provides immediate visual/haptic feedback. | LOW | AG-UI SSE stream already provides real-time agent chain visibility. Already in PRD. |
| **Daily digest / briefing** | Apple Journal has daily prompts, Notion AI summarizes, Limitless generates daily summaries. Users expect the system to surface what matters without asking. | HIGH | Digest Agent with morning briefing. Already in PRD. The <150 word constraint is a strong differentiator vs verbose competitors. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Zero-organization capture philosophy** | Most PKM tools still require the user to choose folders, tags, or categories at capture time. Even Mem (the closest competitor in philosophy) requires opening the right note type. The Active Second Brain removes ALL organizational decisions — you capture, agents handle the rest. This is the core differentiator. | Already architected | The 4-bucket model with AI classification is simpler than Tana's supertags, Notion's databases, or Obsidian's folder/tag systems. Simplicity IS the feature. |
| **Agent chain transparency (AG-UI)** | No competitor exposes the AI decision-making pipeline to the user in real-time. Mem, Notion AI, and Tana process in the background. Showing "Orchestrator -> Perception -> Classifier (0.85) -> Action Agent" builds trust through visibility. | MEDIUM | AG-UI SSE event streaming. Already in PRD. This is a genuine differentiator — users see WHY their note was filed where it was. |
| **Human-in-the-loop clarification** | When confidence is low, the Classifier asks a focused question rather than guessing. Most AI tools silently misclassify. Tana and Notion AI have no HITL loop. This prevents database pollution and builds trust over time. | MEDIUM | Classifier Agent owns the clarification conversation. Already in PRD. Key UX challenge: make clarification feel conversational, not like an error state. |
| **Action sharpening (vague -> executable)** | GTD's "next action" principle is well-established but no capture tool automatically transforms "deal with car registration" into "Go to ilsos.gov and renew registration online — due March 15." This bridges the gap between capture and execution. | MEDIUM | Dedicated Action Agent for Projects/Admin. Already in PRD. Unique separation from classification — no competitor has a dedicated action-sharpening agent. |
| **Personal CRM built into capture** | Monica, Dex, Clay are standalone personal CRMs. But nobody integrates CRM into the capture loop — you mention "had coffee with Sarah" and it automatically updates Sarah's record, last interaction date, and surfaces relationship insights in digests. | HIGH | People bucket + Entity Resolution Agent. Already in PRD. The automatic relationship tracking from natural captures is genuinely novel. |
| **Entity resolution (fuzzy name matching)** | "Don" and "Don Cheeseman" should resolve to the same person. Clay does this for LinkedIn contacts; no capture tool does it for freeform voice notes. Prevents duplicate records accumulating over time. | MEDIUM | Entity Resolution Agent running nightly. Already in PRD. Conservative merge strategy (flag ambiguous rather than auto-merge) is correct. |
| **Weekly review automation** | GTD's weekly review is powerful but nobody does it because it requires effort. Automated system health + stalled projects + neglected relationships review removes the friction. | MEDIUM | Digest Agent (weekly) + Evaluation Agent (Phase 4). Already in PRD. Competitors offer manual review templates (Notion, Todoist); none automate the review itself. |
| **Cross-reference extraction** | When you capture "talk to Sarah about the MedTech project," the system links both the Sarah person record AND the MedTech project record. No competitor does bidirectional cross-referencing from unstructured voice input. | HIGH | Classifier Agent extracts cross-refs. Already in PRD. Depends on existing People/Projects records for matching. |
| **System self-evaluation** | No PKM tool evaluates its own performance. The Evaluation Agent tracking classification accuracy, action completion rates, stale content, and system health is a meta-intelligence layer that no competitor offers. | HIGH | Evaluation Agent (Phase 4). Already in PRD. Requires weeks of data before useful — correct to defer. |
| **Concise output constraint** | Daily digests under 150 words. Most AI tools generate verbose summaries. The constraint that output must fit on a phone screen while making breakfast is a design decision that prevents information overload — the very problem the system solves. | LOW | Prompt engineering constraint on Digest Agent. Already in PRD. This is an anti-bloat feature disguised as a formatting rule. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems. Deliberately NOT building these.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Folder/tag taxonomy** | Power users expect customizable organization. Obsidian and Notion train users to think in folders and tags. | Forces organizational decisions at capture time — the exact friction this system eliminates. Users become "Tweakers" (anti-pattern #7) endlessly reorganizing instead of capturing. The 12 PKM mistakes research shows this is the #1 adoption killer. | 4 stable buckets (People/Projects/Ideas/Admin) with AI classification. Users never see or manage a taxonomy. |
| **Full rich-text editor** | Note-taking apps (Notion, Obsidian, Logseq) are built around long-form writing with formatting, headings, code blocks, embeds. | This is a note-taking app, not a capture app. Adding a rich editor shifts mental model from "dump thought quickly" to "compose something nice." Capture speed degrades. The system becomes a worse Notion clone. | Raw text capture + optional voice/photo. If Will needs to write long-form, he uses a dedicated tool (Notion, VS Code). This system captures the seed, not the tree. |
| **Bi-directional links / knowledge graph** | Obsidian, Logseq, Roam, and Tana all have graph views showing note connections. It looks impressive in demos. | Graph views are eye candy that rarely provide insight for personal capture data. They require critical mass (thousands of notes) to be useful, and maintaining link integrity adds complexity. The 4-bucket model with cross-references is simpler and more actionable. | Cross-reference fields on records (People mentioned in Projects, Projects mentioned with People). Flat, queryable, no graph rendering needed. |
| **Offline capture** | Mobile apps are expected to work offline. Obsidian is local-first. Apple Notes syncs later. | Voice transcription requires Whisper API (cloud). Classification requires LLM (cloud). The core value — AI processing — cannot work offline. Building offline-first with sync-later adds enormous complexity for a single-user system. PRD already decided this. | Require connectivity. Will's capture contexts (phone while walking, at desk, at home) all have connectivity. If truly needed later, queue raw captures locally and process on reconnect. |
| **Custom bucket types** | Users may want to add "Recipes," "Books," "Workouts" beyond the 4 buckets. Capacities and Tana let you define custom object types. | Scope creep. Every new bucket needs classifier training, new tools, schema changes, and digest integration. The 4-bucket model was chosen to be "painfully small" (Principle 9). Adding buckets is the PKM equivalent of adding folders. | Ideas bucket is the catch-all. If a pattern emerges (e.g., lots of book captures), consider a sub-classification within Ideas later. But start with 4. |
| **Real-time collaboration** | Notion, Supernotes, and many tools support multi-user editing. | Single-user system. Will is the only user. Collaboration adds auth complexity, conflict resolution, permissions, and shared state management for zero benefit. | N/A. This is a personal system. If sharing is needed, export data. |
| **Calendar integration** | Reflect, Clay, and Dex sync with Google Calendar. Notion integrates calendar views. Seems useful for "what meetings are coming up." | Adds a sync dependency, OAuth flows, and calendar API maintenance. The system is about capturing thoughts, not managing a schedule. Calendar data would pollute the 4-bucket model. | If Will captures "meeting with Sarah Tuesday at 3pm," the Admin bucket stores the task. The system doesn't need to read or write his actual calendar. |
| **Web clipper / browser extension** | Saner.ai, Notion, and many PKM tools let you clip web content. Seems like a natural capture input. | Web clipping captures OTHER people's content, not Will's thoughts. The system's core loop is "capture YOUR fleeting thought." Clipping articles creates a "Hoarder" pattern (anti-pattern #10) — more inputs than outputs. | If Will finds a useful article, he captures a text note: "Interesting article about X — idea Y for Z project." The thought is what matters, not the article. |
| **Template system** | Tana has template stores. Notion has template galleries. Capacities has object templates. | Templates are pre-structured forms — the opposite of frictionless capture. Requiring Will to pick a template before capturing defeats the "one-tap, zero-decision" principle. | The Classifier Agent applies structure AFTER capture. The user never sees a template — the agent knows what fields to populate based on the bucket. |
| **Plugin / extension ecosystem** | Obsidian has 1,500+ plugins. Notion has integrations marketplace. | Plugin ecosystems create "Complexity Monster" and "Integrator" anti-patterns. A single-user hobby project doesn't need third-party extensibility. Plugins fragment the experience and create maintenance burden. | Build the features you need directly. If the system needs a new capability, add an agent or tool — not a plugin marketplace. |
| **Gamification (streaks, points, badges)** | Apple Journal has streaks. Many productivity apps use gamification to drive engagement. | Gamification creates anxiety and guilt (Principle 10: "Design for Restart"). If Will stops capturing for a week, a broken streak makes restart harder. The system should welcome him back, not shame him. | No streaks, no scores. The daily digest naturally surfaces what needs attention. The system works for Will, not the other way around. |

## Feature Dependencies

```
[Text/Voice/Photo Capture]
    └──requires──> [AG-UI Endpoint + Orchestrator Agent]
                       └──requires──> [Cosmos DB Containers + Tool Library]

[Automatic Classification]
    └──requires──> [Classifier Agent + Cosmos DB]
    └──enhances──> [Action Sharpening]

[Action Sharpening]
    └──requires──> [Classifier Agent] (must know bucket before sharpening)
    └──requires──> [Cosmos DB] (to read/update project records)

[HITL Clarification]
    └──requires──> [Classifier Agent + AG-UI bidirectional messaging]
    └──enhances──> [Automatic Classification] (improves over time)

[Daily Digest]
    └──requires──> [Cosmos DB populated with captures]
    └──requires──> [Push Notifications]
    └──enhances──> [Entity Resolution] (surfaces ambiguous flags)

[Entity Resolution]
    └──requires──> [People records in Cosmos DB]
    └──enhances──> [Personal CRM / People bucket]

[Cross-Reference Extraction]
    └──requires──> [Existing People + Projects records]
    └──enhances──> [Daily Digest] (richer context)
    └──enhances──> [Personal CRM] (automatic relationship tracking)

[Weekly Review]
    └──requires──> [Daily Digest infrastructure]
    └──requires──> [Sufficient data history (2+ weeks)]

[System Self-Evaluation]
    └──requires──> [OpenTelemetry traces]
    └──requires──> [Sufficient data history (4+ weeks)]
    └──requires──> [All other agents operational]

[Search]
    └──requires──> [Cosmos DB with indexed fields]
    └──enhances──> [All buckets] (findability)

[Agent Chain Transparency]
    └──requires──> [AG-UI SSE event stream]
    └──enhances──> [Trust] (users see why decisions were made)
```

### Dependency Notes

- **Capture requires AG-UI + Orchestrator:** Nothing works without the pipeline entry point. This must be Phase 1.
- **Classification requires Cosmos DB:** The Classifier needs existing records to match against (people names, project names). Bootstrap with empty DB, but accuracy improves with data.
- **Action Sharpening requires Classification:** Must know the bucket before deciding whether to sharpen. Sequential dependency.
- **Daily Digest requires populated data:** An empty digest is demoralizing. Don't enable until there are 1-2 weeks of captures.
- **Entity Resolution requires People records:** Nightly merge is pointless without People records to reconcile. Defer until People bucket has 10+ records.
- **System Self-Evaluation requires everything:** Meta-agent needs all other agents running + weeks of data. Correctly deferred to Phase 4.
- **Search is independently valuable:** Does not depend on digests or evaluation. Could be added any time after Cosmos DB is populated.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept: "capture a thought on your phone, see it filed correctly."

- [ ] **Text capture via Expo app** — The simplest input. Validates the full pipeline end-to-end.
- [ ] **Orchestrator + Classifier Agent** — Core routing and classification. The intelligence that makes this more than a note app.
- [ ] **Cosmos DB with 4 buckets + Inbox** — Persistent storage. Records must survive across sessions.
- [ ] **AG-UI endpoint with SSE streaming** — Real-time feedback. User must see "Filed -> Projects (0.85)" to trust the system.
- [ ] **Capture confirmation UX** — Visual confirmation that the thought was captured and processed.
- [ ] **Basic HITL clarification** — When the Classifier is uncertain, ask the user. Prevents misclassification from poisoning early data.

### Add After Validation (v1.x)

Features to add once core capture-classify loop is working and trusted.

- [ ] **Voice capture + Perception Agent** — Add when text pipeline is solid. Whisper transcription + Orchestrator routing.
- [ ] **Photo capture + Vision processing** — Add after voice works. Same Perception Agent, different input modality.
- [ ] **Action Agent (sharpening)** — Add when Projects/Admin captures exist. Requires classified records to sharpen.
- [ ] **Cross-reference extraction** — Add when People + Projects buckets have records to cross-reference.
- [ ] **Basic search** — Keyword search across rawText and titles. Don't wait for Phase 4; basic search is table stakes.
- [ ] **Data export** — JSON export of all records. Prevents lock-in anxiety. Low effort, high trust.

### Future Consideration (v2+)

Features to defer until product-market fit is established (i.e., Will is actually using the system daily).

- [ ] **Daily/weekly digest** — Needs 2+ weeks of data. Digest of 3 captures is not useful.
- [ ] **Entity Resolution Agent** — Needs 10+ People records. Nightly merge of 2 records is not useful.
- [ ] **Push notifications** — Needs digest and HITL to be production-ready before pushing to the phone.
- [ ] **Evaluation Agent** — Needs 4+ weeks of data across all agents. Meta-evaluation of a nascent system produces noise.
- [ ] **Full-text search** — Semantic search beyond keyword matching. Requires enough data for embeddings to be useful.
- [ ] **Share sheet extension** — Convenient but not core. Adds Expo native module complexity.
- [ ] **Video capture + keyframe extraction** — Most complex input modality. Defer until voice+photo are reliable.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Text capture + classification | HIGH | MEDIUM | P1 |
| AG-UI real-time feedback | HIGH | MEDIUM | P1 |
| HITL clarification | HIGH | MEDIUM | P1 |
| Capture confirmation UX | HIGH | LOW | P1 |
| Voice capture + transcription | HIGH | MEDIUM | P1 |
| Photo capture + vision | MEDIUM | MEDIUM | P2 |
| Action sharpening | HIGH | MEDIUM | P2 |
| Cross-reference extraction | MEDIUM | HIGH | P2 |
| Basic keyword search | MEDIUM | LOW | P2 |
| Data export (JSON) | LOW | LOW | P2 |
| Daily digest | HIGH | MEDIUM | P2 |
| Push notifications | MEDIUM | LOW | P2 |
| Entity Resolution | MEDIUM | MEDIUM | P3 |
| Weekly review | MEDIUM | LOW | P3 |
| Evaluation Agent | LOW (initially) | HIGH | P3 |
| Full-text / semantic search | MEDIUM | HIGH | P3 |
| Share sheet extension | LOW | MEDIUM | P3 |
| Video capture + keyframes | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch (validates core hypothesis)
- P2: Should have, add when core loop is trusted
- P3: Nice to have, future consideration after daily usage established

## Competitor Feature Analysis

| Feature | Mem 2.0 | Tana | Notion AI | Capacities | Reflect | Our Approach |
|---------|---------|------|-----------|------------|---------|--------------|
| **Text capture** | Yes (app) | Yes (app + web) | Yes (app + web) | Yes (app + web) | Yes (app, sub-second launch) | Yes (Expo app, one-tap) |
| **Voice capture** | Yes (voice mode, Oct 2025) | Yes (voice chat, AI transcription) | Yes (transcription in 3.2) | No native voice | Yes (with transcription) | Yes (Whisper via Perception Agent) |
| **Photo/image capture** | No | No | Limited | No | No | Yes (GPT-5.2 Vision via Perception Agent) |
| **Auto-classification** | AI auto-tagging | Supertag AI auto-fill | AI agent auto-organize | Object type inference | No (manual) | 4-bucket AI classification with confidence scores |
| **Organization model** | AI-driven, no folders | Supertags (user-defined schema) | Databases + folders + AI | Object types + relations | Backlinks + daily notes | 4 fixed buckets, zero user decisions |
| **HITL when uncertain** | No | No | No | No | No | Yes (Classifier asks focused questions) |
| **Action sharpening** | No | No | No | No | No | Yes (dedicated Action Agent) |
| **Personal CRM** | No | Via supertag | Via database | Object types for people | No | Built-in People bucket with auto-tracking |
| **Daily digest** | No | No | No | No | No | Yes (< 150 words, 6:30 AM) |
| **Agent transparency** | Hidden AI | Hidden AI | Some visibility | Hidden AI | Hidden AI | Full AG-UI chain visibility |
| **Offline** | Yes (Mem 2.0) | Yes (2025 update) | Yes | Yes | Yes | No (requires cloud AI) |
| **Graph view** | No | Knowledge graph | No | Timeline + relations | Graph view | No (cross-references instead) |
| **Data export** | Limited | Export available | Markdown export | Export available | End-to-end encrypted export | JSON export (planned) |
| **Weekly review** | No | Manual templates | Manual | No | No | Automated (Digest + Evaluation Agent) |

**Key takeaway:** No competitor combines multimodal capture + auto-classification + HITL clarification + action sharpening + personal CRM + daily digest in a single system. Each competitor excels at 2-3 of these; the Active Second Brain integrates all of them into one capture loop. The tradeoff is no offline mode and no rich editing — deliberate choices that maintain focus.

## Sources

- [Buildin.AI: Best 15 Second Brain Apps in 2026](https://buildin.ai/blog/best-second-brain-apps) — Comprehensive feature comparison across 15 PKM tools
- [ToolFinder: Best Second Brain Apps in 2026](https://toolfinder.co/best/second-brain-apps) — Evaluation framework for second brain app selection criteria
- [12 Common PKM Mistakes](https://www.dsebastien.net/12-common-personal-knowledge-management-mistakes-and-how-to-avoid-them/) — Anti-patterns that informed anti-features section
- [Forte Labs: Test-Driving Second Brain Apps](https://fortelabs.com/blog/test-driving-a-new-generation-of-second-brain-apps-obsidian-tana-and-mem/) — Obsidian, Tana, Mem comparison from BASB originator
- [Tana 2025 Product Updates](https://tana.inc/articles/whats-new-in-tana-2025-product-updates) — Voice chat, mobile, supertag AI features
- [Notion 3.2 Release (Jan 2026)](https://www.notion.com/releases/2026-01-20) — Mobile AI agents, multi-model support
- [Monica CRM Features](https://www.monicahq.com/features) — Open-source personal CRM feature set
- [Wave Connect: 6 Best Personal CRM Tools](https://wavecnct.com/blogs/news/the-6-best-personal-crm-tools-in-2025) — Clay, Dex, Monica feature comparison
- [Braintoss](https://braintoss.com/) — Benchmark for zero-friction capture UX
- [Limitless AI / Rewind](https://www.limitless.ai/) — AI wearable capture with auto-summarization (acquired by Meta Dec 2025)
- [GTD Methodology (Todoist guide)](https://www.todoist.com/productivity-methods/getting-things-done) — Next action and inbox processing patterns
- [Capacities](https://capacities.io/) — Object-based PKM with people/meeting/project types
- [thesecondbrain.io: Notion vs Obsidian vs NotebookLM](https://www.thesecondbrain.io/blog/notion-vs-obsidian-vs-notebooklm-vs-second-brain-comparison-2025) — Feature comparison matrix

---
*Feature research for: Personal Knowledge Management / Second Brain / AI-Powered Capture-and-Intelligence System*
*Researched: 2026-02-21*
