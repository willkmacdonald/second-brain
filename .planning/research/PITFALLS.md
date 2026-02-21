# Pitfalls Research

**Domain:** Multi-agent personal knowledge management / second brain system
**Researched:** 2026-02-21
**Confidence:** MEDIUM (framework is pre-1.0; AG-UI React Native support is in-progress; some findings rely on community reports rather than official docs)

---

## Critical Pitfalls

### Pitfall 1: The "Bag of Agents" Trap — 7 Agents Before 1 Works

**What goes wrong:**
You build all 7 specialist agents (Orchestrator, Perception, Classifier, Action, Digest, Entity Resolution, Evaluation) before proving the core capture loop works end-to-end. Each agent adds coordination overhead, and research shows that naive multi-agent systems experience up to 17x error amplification when agents operate without proven coordination topology. With 7 agents, you hit the threshold where "accuracy gains begin to saturate or fluctuate" (research shows degradation beyond 4 agents without structured topology).

**Why it happens:**
The architecture is the exciting part. Building the Orchestrator-to-Classifier-to-Action chain feels like making progress. But each handoff is a failure point: context loss, latency accumulation, and cost multiplication. Microsoft Agent Framework had a known bug where `HandoffBuilder` silently dropped `context_provider` during agent cloning (issue #3721, now fixed) — this is the kind of subtle failure that multiplies across 7 agents.

**How to avoid:**
Build one agent first. Literally one. The Classifier Agent receiving raw text input, classifying it, and writing to Cosmos DB. No Orchestrator handoff, no Perception pre-processing. Prove classification works, then add the Orchestrator in front of it. Then add Perception. Each agent must prove its value before the next is added. The project's own "Core Loop First" design principle already states this — the pitfall is ignoring it when the multi-agent architecture feels more interesting.

**Warning signs:**
- You're writing handoff logic before you've classified 50 real captures
- You have 3+ agents but no end-to-end test that goes from text input to Cosmos DB record
- Agent Framework DevUI shows handoff chains but no actual data in the database
- You're debugging orchestration routing before you know if the Classifier prompt works

**Phase to address:**
Phase 1 (Core Loop). The first working system should be: text in -> Classifier -> Cosmos DB. No Orchestrator. No handoffs. Just one agent doing one job.

---

### Pitfall 2: AG-UI React Native — Building on an Incomplete Bridge

**What goes wrong:**
AG-UI protocol has no first-party React Native client. Issue #510 in the ag-ui-protocol/ag-ui repo is "in progress" but has no completion timeline. The existing AG-UI clients target React (web), Angular, and Vue. A Kotlin SDK was recently released for native Android/iOS, but that doesn't help Expo/React Native. You build the backend emitting AG-UI events, then discover the frontend can't consume them properly, forcing a custom SSE integration layer that bypasses AG-UI's abstractions.

**Why it happens:**
AG-UI is a young protocol (CopilotKit origin, open-sourced 2025). Its adoption is growing but mobile-first is not its primary use case. The protocol itself is SSE-based, which is technically feasible in React Native, but the typed event handling, state management hooks, and human-in-the-loop patterns that AG-UI provides on web have no React Native equivalent.

**How to avoid:**
Accept that you'll need a custom AG-UI client adapter for React Native. Plan for it explicitly — don't assume the npm package will "just work." Options:
1. Use `react-native-sse` library to consume raw SSE events and manually map them to AG-UI event types
2. Monitor the Kotlin SDK progress — if it matures faster, consider using Expo's native module bridge
3. Build a thin translation layer: backend emits AG-UI events, a lightweight service (or the app itself) maps them to a simpler format the React Native app understands
4. Start with a web-based capture interface (React) where AG-UI works natively, and add the Expo app as a second client once the protocol matures

**Warning signs:**
- You're writing backend AG-UI event emitters with no client to test against
- The AG-UI npm packages you're importing have "web" in their peer dependencies
- Your SSE connection works in Expo Go but breaks in dev builds (see Expo SSE issue below)
- You're spending more time on protocol plumbing than on agent behavior

**Phase to address:**
Phase 1 should use a simple REST/SSE approach without AG-UI abstractions. AG-UI integration should be a Phase 2 or Phase 3 concern, by which time the React Native client situation will be clearer. The capture loop doesn't need real-time agent handoff visibility — it needs to work.

---

### Pitfall 3: Expo SSE Streaming Broken in Dev Builds

**What goes wrong:**
Expo's `ExpoRequestCdpInterceptor` and `ExpoNetworkInspectOkHttpNetworkInterceptor` block Server-Sent Events on Android debug builds. The interceptor calls `response.peekBody()` which cannot handle stream-type bodies (`text/event-stream`). In Expo 51 with `expo-dev-client`, a blocking `peeked.request()` call synchronously waits for 1MB of data, preventing the stream from ever being consumed. This is documented in Expo issue #27526.

**Why it happens:**
Expo's Chrome DevTools Protocol integration was not designed with streaming responses in mind. The network inspector intercepts all HTTP responses to display them in the debugger, but SSE responses are infinite streams — they never complete, so the inspector blocks forever.

**How to avoid:**
- Use `react-native-sse` library (not the browser's native `EventSource` API, which has known Android issues in React Native)
- In development: either remove `expo-dev-client` or apply the community patch that checks content-type before peeking the body
- Test SSE on physical devices, not just simulators — the issue manifests differently across platforms
- Build a simple SSE health-check endpoint early and verify it works in your exact Expo configuration before building agent streaming
- Set `pollingInterval: 0` to disable automatic reconnections when consuming OpenAI-style streaming endpoints

**Warning signs:**
- SSE works in iOS simulator but hangs on Android emulator
- Events arrive on web but not in the Expo app
- Network tab in Expo DevTools shows SSE requests as "pending" indefinitely
- You're adding timeouts to work around what is actually a blocked stream

**Phase to address:**
Phase 1 (Mobile App Setup). Validate SSE connectivity as the first thing you do in the Expo app — before writing any agent integration code.

---

### Pitfall 4: Cosmos DB Partition Key Lock-in with `/userId` on a Single-User System

**What goes wrong:**
You partition all 5 containers (Inbox, People, Projects, Ideas, Admin) by `/userId` as planned. Since there's only one user ("will"), every document in every container lands in a single logical partition. This means:
- Zero partition-level parallelism for writes
- The 20 GB logical partition size limit applies to your entire dataset per container
- Cross-partition queries are impossible (there's only one partition), but single-partition queries gain no routing benefit since there's nothing to route around
- If you ever add a second user, you're already set (this is the one upside)

For a single-user system, `/userId` is effectively a constant, not a partition key. It's like indexing a book with one chapter.

**Why it happens:**
Cosmos DB documentation emphasizes high-cardinality partition keys. When you design for "single user," the natural instinct is to use `userId` because it's the tenant discriminator. But with cardinality of 1, it provides no distribution benefit. The PRD already decided this, and it's not necessarily wrong for a hobby project at small scale — but it creates an invisible ceiling.

**How to avoid:**
For a single-user system at hobby scale, this is an acceptable tradeoff if you understand the limits. The 20 GB per logical partition is generous for personal knowledge management. But if you want a better design:
- Use hierarchical partition keys: `/userId` + `/type` (or `/category`) as a two-level key. This future-proofs for multi-user while giving partition distribution within a single user.
- Alternatively, use `/id` as partition key for containers with high write volume (Inbox). Point reads by ID are the cheapest operation in Cosmos DB (1 RU).
- For read-heavy containers (People, Projects), partition by the field you query most (e.g., `/category` or `/status`).

**Warning signs:**
- Cosmos DB metrics show a single "hot" partition consuming all RUs
- Write latency spikes during batch operations (e.g., nightly entity resolution updating many People records)
- You hit the 20 GB logical partition limit (unlikely for personal use, but possible with media metadata)

**Phase to address:**
Phase 1 (Data Layer Setup). Make the partition key decision before writing any data. Changing partition keys requires creating new containers and migrating data — there's no ALTER TABLE equivalent.

---

### Pitfall 5: Azure OpenAI Cost Spiral from Multi-Agent Prompt Chaining

**What goes wrong:**
Each agent in the chain consumes tokens independently. A single capture flowing through Orchestrator -> Perception -> Classifier -> Action makes 4 separate LLM calls, each with its own system prompt, context, and completion. With GPT-5.2 pricing, the system prompt alone (repeated in every call) can dominate costs. Enterprise deployments report running 15-40% above advertised token costs due to hidden overhead (system prompts, function calling schemas, retry logic). A 7-agent system where each agent processes the full conversation context creates multiplicative cost growth.

**Why it happens:**
Each handoff in Microsoft Agent Framework starts a new conversation with the receiving agent. The receiving agent needs context about what happened before — which means either passing the full conversation history (expensive) or summarizing it (lossy). The framework's context providers help, but they add tokens to every request. The PRD explicitly says "optimize for capability" and puts cost optimization out of scope, but "no cap" doesn't mean "no awareness."

**How to avoid:**
- **Use model tiering**: Not every agent needs GPT-5.2. The Classifier Agent might work fine with GPT-4o-mini (cheaper by ~33x for input tokens). Reserve GPT-5.2 for agents that need it (Action Agent for nuanced task sharpening, Perception for complex vision).
- **Minimize context passing**: Each agent should receive only what it needs, not the full conversation history. The Classifier doesn't need the Orchestrator's routing reasoning.
- **Cache system prompts**: Azure OpenAI's prompt caching feature (available for identical prompt prefixes) can reduce costs when the same system prompt is used repeatedly.
- **Implement token budgets per agent**: Log token usage per agent from day one. Set soft alerts at thresholds (e.g., >500 tokens per capture average).
- **Batch API for non-real-time agents**: Digest Agent (daily/weekly) and Entity Resolution Agent (nightly) don't need real-time inference. Batch API provides 50% cost reduction with 24-hour latency tolerance.

**Warning signs:**
- Monthly Azure OpenAI costs exceed $50 for a single-user hobby project
- Token usage per capture is >2,000 tokens across the agent chain
- System prompts are >500 tokens each and repeated in every call
- You're passing full conversation history through 4+ handoffs

**Phase to address:**
Phase 1 should establish per-agent token logging. Phase 2 should implement model tiering (not every agent needs the same model). Phase 3 should add Batch API for async agents.

---

### Pitfall 6: Building a System You Admire Instead of One You Use

**What goes wrong:**
The system becomes an engineering showcase — multi-agent orchestration, OpenTelemetry tracing, AG-UI streaming, hierarchical partition keys — but the daily capture experience has friction. You open the app, wait for the agent chain to process, get a classification you disagree with, don't bother correcting it, and stop opening the app. Within 3 weeks the system is shelfware. Research on knowledge management system failure consistently identifies the same root cause: if the new system creates more work than the previous way of doing things, adoption drops to zero.

**Why it happens:**
The learning goal (master multi-agent orchestration) competes with the usage goal (actually manage knowledge). When these conflict, the learning goal wins because it's more interesting. The 7-agent architecture is explicitly chosen for learning, not because it's the simplest solution. That's fine — but the system must still be usable, or there's nothing to learn from because there's no real-world feedback.

**How to avoid:**
The project's "Design for Restart" and "Core Loop First" principles directly address this. Enforce them ruthlessly:
- **Capture must take <3 seconds** from app open to "done." If the agent chain adds latency, process asynchronously — acknowledge the capture instantly, classify in the background.
- **Never block capture on classification**: Show "Captured!" immediately. Classification and action sharpening happen after the screen is dismissed.
- **The clarification flow (HITL) must be optional**: If the user ignores a low-confidence classification, the system should still file the capture with its best guess. Don't create a guilt backlog of "items needing review."
- **The daily digest must deliver value in week 1**: Even with minimal data, the 6:30 AM digest should surface something useful. An empty or generic digest kills the habit loop.
- **Measure usage, not features**: The real metric is "captures per day," not "agents deployed."

**Warning signs:**
- You haven't used the app for 3+ consecutive days and didn't notice
- The backlog of "pending clarification" items is growing
- You're adding agent features but the last real capture was a test
- The daily digest arrives but you delete it without reading
- You're more excited about the DevUI traces than the data in Cosmos DB

**Phase to address:**
Every phase. But Phase 1 must end with a system you actually use daily for real captures. If Phase 1 ends with "it works technically" but you're not using it, stop and fix the UX before moving to Phase 2.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoded `userId: "will"` everywhere | No auth system needed | Every query, every agent, every container has a magic string. Adding a second user requires find-and-replace across the codebase. | Acceptable for MVP. Extract to config constant immediately, but don't build auth. |
| API key auth instead of Azure AD | No token refresh, no MSAL, no redirect flows | No token expiry, no rotation mechanism, no audit trail. If the key leaks, full system access. | Acceptable for single-user hobby project. Store in Expo SecureStore + environment variable. Never acceptable if the system holds sensitive personal data about others. |
| Single GPT-5.2 model for all agents | Simpler deployment, one model to manage | 33x cost premium for agents that don't need reasoning power (Classifier could use GPT-4o-mini). | Acceptable in Phase 1 for simplicity. Must address in Phase 2 when cost patterns are visible. |
| Skipping OpenTelemetry initially | Faster development, fewer dependencies | Debugging multi-agent handoff failures without traces is near-impossible. "Every production agent system that has failed at scale had the same root cause: insufficient observability." | Never acceptable beyond Phase 1 prototype. Add tracing before adding the 3rd agent. |
| Processing captures synchronously | Simpler architecture, no queue needed | Capture UX blocks on slowest agent in the chain. GPT-5.2 with vision can take 5-10 seconds. User waits with spinner. | Never acceptable. Async-first from day one — acknowledge capture, process in background. |
| One Cosmos DB container for everything | Fewer resources, simpler setup | Mixed access patterns, no independent scaling, partition key compromises. | Never. The 5-container design in the PRD is correct. Cosmos DB charges per-container RUs, but serverless pricing is per-operation, so container count has minimal cost impact. |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Azure OpenAI + Agent Framework | Creating a new `AsyncAzureOpenAI` client per agent call instead of reusing a singleton | Create one client instance at startup, share across agents. The SDK manages connection pooling internally. |
| Cosmos DB Python SDK | Not using `async` client in FastAPI backend, causing event loop blocking | Use `aiohttp`-based `CosmosClient` from `azure.cosmos.aio`. The sync client blocks the event loop and kills FastAPI's concurrency. |
| Expo + Azure Blob Storage | Uploading media directly from the app to Blob Storage with the storage key embedded | Use SAS tokens generated by the backend with short expiry (1 hour). Never put storage keys in a mobile app — they're trivially extractable. |
| Agent Framework Handoff | Assuming receiving agent has full context from the sending agent | Handoff participants don't share the same session. Use `context_provider` explicitly and test that context survives the handoff. The framework had a bug (#3721) where context was silently dropped during agent cloning. |
| Whisper transcription | Sending full audio files when only the first 30 seconds matter | Whisper has a 25 MB file limit and charges per minute. Trim audio to actual speech duration before sending. Silence wastes tokens. |
| AG-UI SSE + Mobile | Using browser `EventSource` API in React Native | Use `react-native-sse` library. The native `EventSource` API has known issues on Android in React Native. Verify SSE works on both platforms before building agent streaming features. |
| Cosmos DB Serverless | Expecting consistent sub-10ms latency | Serverless Cosmos DB has no latency guarantees. Cold starts and dynamic scaling cause latency spikes (20ms+ for point reads reported). If you need predictable latency for capture UX, consider provisioned throughput (400 RU/s minimum) or accept that reads may occasionally be slow. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full conversation history in every handoff | Token costs growing linearly with capture count; agent responses slowing | Pass only relevant context per agent. Orchestrator sends the raw input + routing decision, not the full chat history. | After ~50 captures per day when context windows approach limits |
| Synchronous agent chain for captures | App freezes for 5-15 seconds during capture; user abandons app | Acknowledge capture instantly (write to Inbox), process agent chain asynchronously via background job or queue | Immediately — even the first capture will feel slow with 3+ agents in series |
| OpenTelemetry tracing every span at full fidelity | Backend CPU overhead of 18-49% (measured in research); memory growth from span buffering | Use sampling (tail-based recommended for agent systems). Trace 100% during development, 10-20% in production. Batch exports, don't export per-span. | At ~100 operations/hour the overhead becomes measurable |
| Nightly entity resolution scanning all People records | Entity Resolution Agent consumes high RUs reading entire People container; spikes Cosmos DB costs | Maintain a "dirty" flag or change feed — only process records modified since last run | After People container exceeds ~500 records |
| Media files stored as base64 in Cosmos DB | Document size explodes; 2 MB document limit hit quickly; RU costs proportional to document size | Store media in Blob Storage, store only the Blob URL in Cosmos DB. Always. | First photo capture (smartphone photos are 3-10 MB) |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing Azure OpenAI API key in Expo app bundle | Key extracted from APK/IPA in minutes using standard reverse engineering tools. Attacker gets unlimited access to your Azure OpenAI deployment. | Backend acts as proxy. Expo app authenticates to backend (API key in SecureStore), backend calls Azure OpenAI. Never put Azure service keys in mobile apps. |
| API key transmitted over HTTP (not HTTPS) | Key intercepted via network sniffing on any shared WiFi | Enforce HTTPS-only on Azure Container Apps (default behavior). Pin certificates if paranoid. |
| No rate limiting on capture endpoint | If API key leaks, attacker can flood the system with captures, running up Azure OpenAI costs | Add rate limiting at Azure Container Apps level (APIM or middleware). Even for single-user: 100 captures/hour is generous. |
| Cosmos DB connection string in environment variable without Key Vault | If container image or environment is compromised, full database access | For hobby project: environment variables in Azure Container Apps secrets are acceptable. For production: use Azure Key Vault references. |
| Push notification tokens stored in Cosmos DB without encryption | If database is breached, attacker can send push notifications to your device | Encrypt push tokens at rest or store them in a separate secure store. Low risk for single-user, but good hygiene. |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Requiring classification confirmation before capture is "done" | User must make a decision on every capture. Friction kills the habit. 10 captures/day with confirmations = 10 interruptions. | Capture is done the moment you tap "send." Classification happens silently. Only surface clarification requests in a non-blocking way (notification badge, not modal). |
| Showing agent handoff chain in real-time during capture | Cool technically, but the user doesn't care that the Orchestrator handed off to the Classifier. They care that their thought is saved. | Show a simple "Captured!" confirmation. Agent chain visibility should be opt-in (a "details" drawer), not the default UX. |
| Daily digest that's too long (>150 words) | User stops reading it. The PRD already caps this at 150 words, but the temptation to add "just one more section" is strong. | Enforce the 150-word cap in the Digest Agent's system prompt. Test by reading the digest while brushing your teeth — if it takes longer than the teeth, it's too long. |
| Making the HITL clarification flow feel like homework | Low-confidence captures pile up in a "needs review" queue. The queue grows. Guilt accumulates. The app becomes associated with unfinished tasks. | Auto-classify with best guess after 24 hours. No permanent "pending" state. "Design for Restart" means the system should work even if you never review anything. |
| Voice capture that requires holding a button | Awkward to use with one hand, while walking, while driving. The capture moment is lost. | Tap to start, tap to stop. Or even better: tap to start, auto-stop after 3 seconds of silence. Minimize motor interaction. |

## "Looks Done But Isn't" Checklist

- [ ] **Agent handoff**: The handoff works in DevUI but `context_provider` data isn't actually reaching the receiving agent — verify by logging received context in each agent, not just checking DevUI traces
- [ ] **Classification accuracy**: Classifier returns categories but accuracy on real-world captures is <70% — test with 50+ real captures (not synthetic test data) before considering classification "done"
- [ ] **Voice transcription**: Whisper transcribes but ambient noise, accents, and domain-specific terms (medical technology, woodworking) cause errors — test in real environments (car, workshop, walking outside)
- [ ] **Cosmos DB writes**: Data appears in Data Explorer but `userId` partition key isn't indexed for your query patterns — verify queries use the partition key and check RU charges per query
- [ ] **SSE streaming**: Events stream in the browser but the Expo app only receives the first event, then hangs — test on physical Android device, not just iOS simulator
- [ ] **Daily digest**: Digest Agent produces output but it arrives at 6:30 AM UTC, not 6:30 AM CT — verify timezone handling in the scheduling logic
- [ ] **Push notifications**: Expo push tokens are registered but notifications arrive 30 minutes late or not at all — test with the app in background, terminated, and on a locked device
- [ ] **Error handling**: The happy path works but a Cosmos DB timeout during classification silently drops the capture with no retry — verify every failure mode has a retry or dead-letter queue

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong partition key on Cosmos DB containers | HIGH | Must create new containers with correct partition keys, run container copy job, update all application code to use new containers. No in-place change possible. |
| Built all 7 agents, none work reliably | MEDIUM | Disable all agents except Classifier. Prove one works. Re-enable agents one at a time. The framework supports disabling handoff targets. |
| AG-UI integration doesn't work with Expo | LOW | Fall back to raw SSE with `react-native-sse`. Lose typed events but gain a working system. AG-UI is a nice-to-have, not a core requirement. |
| Azure OpenAI costs out of control | LOW | Switch expensive agents to GPT-4o-mini. Implement Batch API for async agents. Add token budget alerts. Can be done incrementally without architecture changes. |
| System works but you stopped using it | HIGH | Fundamental UX problem. Requires honest assessment of what's creating friction. May need to simplify the agent chain, reduce latency, or change the capture UX. The hardest recovery because the problem is behavioral, not technical. |
| SSE broken in Expo dev builds | LOW | Remove `expo-dev-client`, or use production builds for SSE testing. The issue is development-environment-specific. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Bag of Agents (building all 7 before 1 works) | Phase 1 | Phase 1 ends with exactly 1 agent (Classifier) processing real captures end-to-end |
| AG-UI React Native gap | Phase 2-3 | Phase 1 uses simple REST + SSE. AG-UI added only after React Native client stabilizes |
| Expo SSE blocking | Phase 1 | SSE health-check endpoint verified on physical Android device before any agent integration |
| Cosmos DB partition key lock-in | Phase 1 | Partition keys decided and documented before first `container.create()` call. Hierarchical keys evaluated. |
| Azure OpenAI cost spiral | Phase 1 (logging), Phase 2 (tiering) | Per-agent token usage logged from first LLM call. Model tiering implemented before 4th agent is added. |
| Shelfware / not using the system | Every phase | "Captures per day" tracked as the primary metric. If 0 for 3 days, stop feature work and fix UX. |
| Synchronous capture processing | Phase 1 | Capture endpoint returns <500ms. Agent processing is always asynchronous. |
| Context loss during handoffs | Phase 2 (when handoffs are introduced) | Integration test that verifies specific context fields survive Orchestrator -> Classifier handoff |
| OpenTelemetry overhead | Phase 2 | Tracing enabled before 3rd agent. Sampling configured before production deployment. |
| Media in Cosmos DB instead of Blob Storage | Phase 1 | Architecture decision documented: media -> Blob Storage, metadata -> Cosmos DB. No exceptions. |

## Sources

- [Microsoft Agent Framework Handoff Documentation](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/handoff) — HIGH confidence
- [AG-UI React Native Client Issue #510](https://github.com/ag-ui-protocol/ag-ui/issues/510) — HIGH confidence (primary source, in-progress)
- [AG-UI Kotlin SDK Announcement](https://www.copilotkit.ai/blog/ag-ui-goes-mobile-the-kotlin-sdk-unlocks-full-agent-connectivity-across-android-ios-and-jvm) — HIGH confidence
- [Expo SSE Blocking Issue #27526](https://github.com/expo/expo/issues/27526) — HIGH confidence (primary source, confirmed bug)
- [Cosmos DB Anti-Patterns](https://devblogs.microsoft.com/cosmosdb/antipatterns-on-azure-cosmos-db/) — HIGH confidence (official Microsoft blog)
- [Cosmos DB Hierarchical Partition Keys](https://learn.microsoft.com/en-us/azure/cosmos-db/hierarchical-partition-keys) — HIGH confidence (official docs)
- [Cosmos DB Serverless Performance](https://learn.microsoft.com/en-us/azure/cosmos-db/serverless-performance) — HIGH confidence (official docs)
- [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/azure-openai/) — HIGH confidence (official pricing)
- [Azure OpenAI Token Cost Management](https://oneuptime.com/blog/post/2026-02-16-how-to-manage-token-usage-and-cost-optimization-in-azure-openai-service/view) — MEDIUM confidence
- [17x Error Amplification in Multi-Agent Systems](https://towardsdatascience.com/why-your-multi-agent-system-is-failing-escaping-the-17x-error-trap-of-the-bag-of-agents/) — MEDIUM confidence (research article, not peer-reviewed)
- [Multi-Agent System Coordination Challenges](https://www.imaginexdigital.com/insights/why-your-multi-agent-ai-system-is-probably-making-things-worse) — MEDIUM confidence
- [OpenTelemetry Performance Impact](https://oneuptime.com/blog/post/2026-01-07-opentelemetry-performance-impact/view) — MEDIUM confidence
- [OpenTelemetry AI Agent Observability](https://opentelemetry.io/blog/2025/ai-agent-observability/) — HIGH confidence (official OpenTelemetry blog)
- [Agent Framework Release Notes (context_provider fix)](https://github.com/microsoft/agent-framework/releases) — HIGH confidence (primary source)
- [Knowledge Management System Failure Patterns](https://bloomfire.com/blog/why-knowledge-management-fails/) — MEDIUM confidence
- [Azure OpenAI Hidden Costs Analysis](https://azure-noob.com/blog/azure-openai-pricing-real-costs/) — LOW confidence (community blog)

---
*Pitfalls research for: Multi-agent personal knowledge management / second brain system*
*Researched: 2026-02-21*
