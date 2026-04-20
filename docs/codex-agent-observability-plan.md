# Codex Agent Observability Plan

Last updated: 2026-04-19
Status: Draft

## Purpose

The current observability stack is good at answering infrastructure questions:

- Did the request arrive?
- Which segment failed?
- How long did it take?
- Did the tool call succeed?

It is weak at answering agent-behavior questions:

1. What prompt did the agent actually see?
2. What did the agent actually output?
3. How confident was it?
4. What rules or policies drove the behavior?

This document proposes a Foundry-first design that fills those gaps without recreating telemetry and trace features that Microsoft Foundry already provides.

## Design Rule: Foundry First, App Summary Second

Use Foundry as the primary system of record for raw agent execution artifacts wherever Foundry already supports them.

Do not build a second homegrown store for:

- raw prompt transcripts
- raw model outputs
- full tool-call transcripts
- span timelines

The app should only persist the pieces that Foundry does not give us as a stable business-audit record:

- correlation keys back to the capture and inbox item
- the decision summary that matters to the product
- rule provenance that lives in app data, not in Foundry
- a lightweight release/config reference so we know which agent definition was active

## What Foundry Should Own

Based on Microsoft Foundry documentation, we should explicitly lean on these native capabilities:

- Foundry tracing captures latency, exceptions, prompt content, retrieval operations, tool calls, and step-by-step traces when tracing is connected to Application Insights.
- Foundry Conversation results let operators inspect conversation history, response information, ordered actions, tool calls, and inputs/outputs for an agent run.
- Agent Service threads, runs, and messages already persist conversation state and messages.
- Prompt agents are configuration-managed in Foundry, including instructions, model selection, and tools.

Practical implication:

- For "what prompt did the agent see?" and "what did it output?", the default answer should be "open the Foundry trace/conversation for this run", not "query a custom Cosmos container full of copied transcripts."

## What The App Must Still Own

Foundry does not know our product semantics. The app still needs to own:

- capture-to-agent correlation using `capture_trace_id`
- inbox item, filed document, and errand/task side effects
- routing-rule provenance from Cosmos `AffinityRules`
- classifier threshold policy and safety-net path
- admin retry/nudge path
- a stable per-run business summary keyed to a capture

That is the right place for app-owned observability.

## Current Gaps

### 1. Prompt seen

Current state:

- The runtime creates user messages in `backend/src/second_brain/streaming/adapter.py` and `backend/src/second_brain/processing/admin_handoff.py`.
- The authoritative agent instructions live only in the Foundry portal for `Classifier`, `AdminAgent`, and `InvestigationAgent`.
- The app does not persist a stable reference to the exact agent configuration active for a given run.

Consequence:

- We cannot reliably answer "what exact prompt/configuration did the model see?" after the fact.

### 2. Agent output

Current state:

- Classifier text is suppressed from the mobile SSE stream and only tool outcomes are retained in structured form.
- Admin sometimes stores `adminAgentResponse` on the inbox document, but only for specific delivery cases.
- Investigation streams text to the client, but there is no first-class run audit record for it.

Consequence:

- We do not have a stable operator-facing answer to "what did the agent say/do?" across all agents.

### 3. Confidence

Current state:

- Classifier confidence is captured in `classificationMeta` and on spans.
- Admin and Investigation do not expose an explicit confidence contract.

Consequence:

- Confidence is partly available, but only for classification.
- We should not invent fake confidence for agents that do not actually emit one.

### 4. Rules that drove behavior

Current state:

- Admin routing context is assembled from destinations and affinity rules, but the system does not persist which exact rule matched.
- Classifier behavior depends on Foundry instructions, tool schema, threshold policy, and safety-net logic, but those are not surfaced as a coherent decision record.

Consequence:

- We cannot answer "why did this go to this bucket/destination?" without manually reconstructing code, logs, and data.

## Target Operator Experience

For any capture trace, the operator should be able to open one page and see:

- `Prompt`
  Foundry conversation/trace link plus the app-known context injected for that run.
- `Output`
  Final model answer, tool calls, tool results, and terminal state.
- `Confidence`
  Real confidence if emitted; otherwise explicitly `not available`.
- `Rule Basis`
  Threshold policy, matched routing rules, retry/safety-net path, and agent config reference.

The page should prefer Foundry-native drill-down for raw execution and show app-owned summaries for product semantics.

## Ownership Matrix

| Operator question | Primary owner | App-owned supplement |
|---|---|---|
| What prompt did the agent see? | Foundry Traces + Conversation results | `agent_release_id`, injected-context hash/reference, capture/inbox linkage |
| What did the agent output? | Foundry Traces + Conversation results | terminal state, tool-result summary, product side-effect summary |
| What was the confidence? | App decision record for classifier | `confidence_unavailable` for agents that do not emit it |
| What rules drove the behavior? | App decision record | matched rule IDs/text, threshold version, safety-net/retry markers |

## Proposed Architecture

### Phase 1: Make Foundry the raw execution source of truth

Ship this first. Without it, any app-side decision record will still feel incomplete.

#### 1.1 Connect and verify Foundry tracing

- Ensure the Foundry project is connected to Application Insights.
- Verify traces appear in Foundry for the existing agents after real traffic.
- Verify operators can open:
  - Foundry `Traces`
  - Foundry `Conversation results`
  - Azure Monitor for the connected Application Insights resource

#### 1.2 Prefer Foundry-native views over manual reasoning logs

Current classifier code logs "reasoning chunks" into App Insights. That should not become the long-term operator UX.

Plan:

- Keep the current logs only as a temporary fallback.
- Do not build product UI on top of `reasoning_text` log scraping.
- Once Foundry tracing is confirmed reliable, demote or remove manual reasoning-chunk logging because it duplicates sensitive content that Foundry already knows how to present.

#### 1.3 Persist Foundry identifiers everywhere we need correlation

For each run, persist the identifiers needed to jump into Foundry:

- `agent_id`
- `foundry_conversation_id` / thread ID
- Foundry run/response identifier if exposed by the SDK/runtime
- `capture_trace_id`
- inbox item ID / filed document ID

Priority:

- Classifier capture path
- Admin processing path
- Investigation path

The product should never require operators to manually search Foundry by timestamp alone.

### Phase 2: Add an app-owned `AgentDecisionRecord`

This is the core app-owned artifact. It is not a transcript store. It is a decision audit record.

Recommended storage:

- New Cosmos container: `AgentDecisionRecords`
- Partition key: `/captureTraceId` for capture-linked runs
- Secondary access path for investigation: `/threadId` or mirrored lookup record if needed

One document per meaningful agent execution.

Recommended shape:

```json
{
  "id": "uuid",
  "captureTraceId": "uuid-or-null",
  "threadId": "foundry-thread-or-null",
  "segmentId": "classifier | admin | investigation",
  "agent": {
    "agentId": "foundry-agent-id",
    "agentName": "Classifier",
    "agentType": "prompt_agent",
    "agentReleaseId": "classifier-2026-04-19-01"
  },
  "foundry": {
    "conversationId": "foundry-conversation-id",
    "runId": "foundry-run-id-or-null",
    "traceId": "foundry-trace-id-or-null"
  },
  "input": {
    "userMessagePreview": "first 200 chars",
    "userMessageRef": {
      "container": "Inbox",
      "id": "inbox-doc-id"
    },
    "injectedContext": {
      "kind": "routing_context | none",
      "hash": "sha256-or-null"
    }
  },
  "output": {
    "terminalState": "classified | pending | misunderstood | unresolved | failed",
    "finalTextPreview": "optional preview",
    "toolCalls": ["file_capture"],
    "toolSummary": {
      "bucket": "Admin",
      "itemId": "..."
    }
  },
  "decision": {
    "decisionType": "classification | routing | investigation_answer",
    "bucket": "Admin",
    "confidence": 0.9,
    "confidenceAvailable": true,
    "matchedRuleIds": [],
    "matchedRuleTexts": [],
    "thresholdPolicyVersion": "classifier-threshold-v1",
    "safetyNetUsed": false,
    "retryUsed": false
  },
  "createdAt": "2026-04-19T00:00:00Z"
}
```

Rules for this record:

- Do not copy the full prompt transcript into Cosmos if Foundry already has it.
- Do not copy the full model output into Cosmos if Foundry already has it.
- Store small previews and stable references only.
- Store the business decision fields that operators actually need for triage.

### Phase 3: Add a lightweight `AgentReleaseManifest`

This is the missing bridge between Foundry-managed prompt agents and incident auditability.

Problem:

- Prompt-agent instructions live in Foundry configuration.
- Foundry is the right authoring surface.
- But if instructions change later, we still need to know which agent definition was live when a bad decision occurred.

Plan:

- Keep Foundry as the source of truth for editing.
- Add a lightweight app-side release manifest that snapshots metadata for each promoted agent configuration:
  - `agent_release_id`
  - `agent_id`
  - `agent_name`
  - model deployment
  - tool list
  - instruction hash
  - optional human-readable release note
  - promotion timestamp

Recommended format:

- versioned JSON or YAML in repo or blob storage
- referenced by `agentReleaseId` from `AgentDecisionRecord`

Important boundary:

- This is not a second prompt-management system.
- It is release metadata so operators can answer "which configuration was active?" without scraping portal history.

### Phase 4: Record rule provenance where Foundry cannot

This is the most important app-specific addition.

#### 4.1 Classifier provenance

Record:

- selected bucket
- confidence
- `status` (`classified`, `pending`, `misunderstood`)
- whether safety net fired
- whether this was follow-up resolution
- threshold policy version
- split-count / multi-result summary if applicable

Do not attempt to infer hidden chain-of-thought.

For classifier, "rules that drove behavior" means:

- Foundry prompt-agent configuration reference
- tool schema used
- threshold policy applied by the app
- safety-net path if the tool was skipped

#### 4.2 Admin provenance

Record:

- routing-context hash
- matched `AffinityRuleDocument` IDs
- matched rule natural-language text
- destination chosen
- whether the agent only called intermediate tools
- whether retry/nudge was required
- whether response text was stored for user delivery

This is the gap Foundry cannot solve because the rules live in our Cosmos data model.

#### 4.3 Investigation provenance

Record:

- question text preview
- tools called
- final answer preview
- thread ID / conversation ID

Do not fabricate a confidence score unless the investigation workflow later emits one.

### Phase 5: Operator APIs and UI

Add a decision-observability view keyed to a capture trace.

Recommended API:

- `GET /api/agent-observability/capture/{trace_id}`
- `GET /api/agent-observability/thread/{thread_id}`

Response shape:

- `capture summary`
- `classifier decision`
- `admin decision`
- `investigation decision` if applicable
- `foundry links`
  - trace
  - conversation
  - agent

Recommended UI sections:

- `Prompt`
  Foundry link plus app-injected context summary/hash
- `Output`
  terminal state, output preview, tool summary
- `Confidence`
  real score or explicit `not available`
- `Rule Basis`
  matched rules, threshold version, safety-net/retry markers

The UI should make the split explicit:

- `Raw execution`: open in Foundry
- `Business decision`: show app summary inline

### Phase 6: Use Foundry evals and prompt tooling for prompt iteration

Do not build a custom prompt-management UI in this repo.

Use Foundry-native capabilities for:

- prompt-agent configuration
- prompt variants / comparison where available
- evaluations and trace review

App-owned responsibility:

- gate production changes through an `agentReleaseId`
- record which release was live for each run
- tie bad outcomes back to a specific release for rollback or evaluation

## Concrete Code Changes

### Classifier path

Files likely touched:

- `backend/src/second_brain/streaming/adapter.py`
- `backend/src/second_brain/tools/classification.py`
- `backend/src/second_brain/models/documents.py`

Work:

- persist `foundry_conversation_id` consistently on all classifier-created documents
- emit `AgentDecisionRecord` after terminal classification outcome
- record threshold/safety-net metadata
- stop treating `reasoning_text` logs as the operator artifact

### Admin path

Files likely touched:

- `backend/src/second_brain/processing/admin_handoff.py`
- `backend/src/second_brain/tools/admin.py`

Work:

- return or capture matched rule IDs and rule text as structured metadata
- emit `AgentDecisionRecord` for each admin run
- record retry/nudge path and final delivery decision

### Investigation path

Files likely touched:

- `backend/src/second_brain/streaming/investigation_adapter.py`
- `backend/src/second_brain/api/investigate.py`

Work:

- persist thread/conversation identifiers
- emit `AgentDecisionRecord` with tool usage and answer preview
- add Foundry deep links for the thread/run

### Operator surface

Files likely touched:

- spine detail APIs and/or a new observability API module
- mobile or web decision view

Work:

- add decision-observability endpoint(s)
- add Foundry deep links
- render prompt/output/confidence/rule-basis sections

## Non-Goals

These should remain out of scope:

- building a second transcript database when Foundry already stores messages and traces
- scraping or storing chain-of-thought as a product feature
- inventing confidence values for agents that do not emit them
- moving prompt-agent authoring out of Foundry into local code just for observability

## Policy and Retention

Foundry documentation explicitly warns that traces can capture sensitive information, including user inputs, outputs, tool arguments, and tool results.

Recommended policy:

- Restrict access to Foundry traces and Application Insights to operator roles only.
- Keep shorter retention for content-rich traces than for aggregate telemetry if cost/privacy becomes an issue.
- Treat `AgentDecisionRecord` as product telemetry, not as a replacement transcript store.
- If this system expands beyond a tightly-controlled single-user/internal setup, revisit whether full content recording should remain enabled in production.

## Recommended Delivery Order

1. Connect and verify Foundry tracing and conversation results.
2. Persist stable Foundry IDs and deep links.
3. Add `AgentReleaseManifest`.
4. Add `AgentDecisionRecord` for classifier.
5. Add rule provenance for admin.
6. Add the operator-facing decision page/API.
7. Add investigation decision records.
8. Remove or demote duplicated manual reasoning-text logging.

## Recommendation

The best near-term move is not "log more text."

The best near-term move is:

- use Foundry for raw execution truth
- use app-owned decision records for product semantics
- use release manifests to make Foundry-managed prompt agents auditable over time

That gives the missing debugging visibility without recreating a second observability platform inside the app.

## References

- [Set up tracing in Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup?view=foundry)
- [Configure tracing for AI agent frameworks](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-framework)
- [Threads, runs, and messages in Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry-classic/agents/concepts/threads-runs-messages)
- [What is Microsoft Foundry Agent Service?](https://learn.microsoft.com/en-us/azure/foundry/agents/overview)
