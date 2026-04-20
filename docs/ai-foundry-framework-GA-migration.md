# AI Foundry / Agent Framework GA Migration

Last updated: 2026-04-13

## Purpose

This document captures the current architectural conclusions about migrating this project from the Microsoft Agent Framework beta/RC packages to the GA model.

It focuses on the question that matters most for this repo:

- not just "how do we update the package?"
- but "what should own each agent definition and where should each agent run?"

## Current Situation

The backend currently uses the pre-GA Foundry integration:

- `agent-framework-azure-ai`
- `agent-framework-core`
- `AzureAIAgentClient`

The codebase uses three existing Foundry-defined agents:

- `Classifier`
- `AdminAgent`
- `InvestigationAgent`

Planned next:

- `Connections Agent`

## GA Model: How To Think About It

The GA Python model separates concepts that were previously blurred together.

### Ownership axis

- `Prompt agent`
  A service-managed agent definition. Foundry owns the prompt/configuration shape.
- `Code agent`
  An application-owned agent definition. The repo owns instructions, tool contracts, orchestration behavior, and tests.

### Hosting axis

- `App-hosted`
  Runs inside this backend/container.
- `Foundry-hosted`
  Runs in Foundry as a Hosted Agent, but still follows a code-first model.

### Practical GA SDK shapes

- `FoundryAgent(...)`
  Best fit when the agent definition is service-managed in Foundry.
- `Agent(client=FoundryChatClient(...))`
  Best fit when the application owns the agent definition, instructions, tools, and conversation loop.

## Why Microsoft Made This Split

The change appears to make ownership boundaries explicit.

Instead of one client covering multiple architectural modes, GA now distinguishes between:

- service-managed agents
- app-owned code agents
- code that can be hosted by Foundry

This does **not** imply that "everything should move into Foundry prompt agents."

The better interpretation is:

- use prompt agents when the behavior is mostly configuration, prompt, and service-managed tooling
- use code agents when the behavior depends on schema, side effects, retries, orchestration, custom tooling, or tight application coupling

## Why The Current Agents Do Not Look Like Prompt Agents

The important point is not prompt quality. The important point is where the real behavior lives.

If removing the backend code would destroy the agent's real behavior, that agent is not really a prompt agent.

In this repo, that appears true for all current agents.

### Classifier

The classifier is not just "a prompt that classifies."

It is a code-owned workflow component that:

- forces tool usage through request-time options
- parses streaming tool calls/results
- writes application state into Cosmos
- preserves follow-up context
- preserves trace propagation
- emits app-specific SSE events
- falls back to safety-net behavior if the model fails to call the expected tool

Classifier-local tools currently run in the backend container:

- `file_capture`
- `transcribe_audio`

Those tools are tightly coupled to:

- this repo's Cosmos schema
- trace/context propagation
- Blob Storage
- Azure OpenAI transcription

That makes the classifier a much better fit for a code-agent model than a prompt-agent model.

### AdminAgent

The admin agent is also not just prompt-defined behavior.

It performs domain side effects and depends on local routing/data tools and backend retry logic around whether output tools were actually called.

### InvestigationAgent

The investigation agent is tool-driven and domain-aware. It operates on observability queries and custom backend formatting/streaming logic.

### Connections Agent

The planned Connections Agent is explicitly:

- scheduled
- autonomous
- cross-system
- tool-heavy
- read-heavy
- integrated into digest orchestration

That is a code agent by design, not a prompt artifact.

## Core Recommendation

Think about each agent using two separate decisions:

1. Who owns the definition?
2. Where should it run?

For this repo, the current recommendation is:

- most or all agents should be treated as `code agents`
- then choose `app-hosted` vs `Foundry-hosted` per agent

## Agent 2x2

| Agent | Prompt vs Code | App-hosted vs Foundry-hosted | Why |
|---|---|---|---|
| `Classifier` | Code | App-hosted now | Tightly coupled to capture streaming, Cosmos writes, trace propagation, follow-up handling, and required local tools. |
| `AdminAgent` | Code | App-hosted now | Performs domain side effects and depends on local routing/data tools plus backend orchestration logic. |
| `InvestigationAgent` | Code | App-hosted now, Hosted later is plausible | Tool-driven and domain-aware, but less tightly bound to the live capture request path than the classifier. |
| `Connections Agent` | Code | Strong Foundry-hosted candidate | Scheduled, autonomous, cross-system, read-heavy, and not latency-critical for an interactive request. |

## Recommended Mental Model Per Agent

### Classifier

Treat as:

- code agent
- app-hosted
- latency-sensitive
- tightly coupled to the mobile capture API path

This is the weakest candidate for a prompt-agent model.

### AdminAgent

Treat as:

- code agent
- app-hosted
- side-effecting workflow component

This is also a weak candidate for a prompt-agent model unless its tooling and persistence responsibilities are redesigned.

### InvestigationAgent

Treat as:

- code agent
- app-hosted for now
- possible future Hosted Agent candidate

### Connections Agent

Treat as:

- code agent
- strongest Hosted Agent candidate

Reasons:

- not on the interactive mobile request path
- runs on a schedule
- reads from multiple systems
- naturally fits autonomous background execution

## What This Means For GA Migration

There are two realistic near-term paths.

### Path A: Keep agents app-hosted and move to the GA code-agent model

Use:

- `Agent(client=FoundryChatClient(...))`

This path means:

- the repo owns agent definitions
- the repo owns prompts/instructions
- local Python tools remain local
- Foundry is the model/provider layer

This is the cleanest migration path for the current `Classifier`, `AdminAgent`, and likely `InvestigationAgent`.

### Path B: Move selected agents to Foundry Hosted Agents

Use this when:

- the agent is autonomous or scheduled
- the runtime is code-first
- the agent has meaningful custom tools and orchestration
- Foundry hosting is desirable, but prompt-agent constraints are not

This is the strongest architectural fit for the future `Connections Agent`.

## What Not To Assume

Do not assume:

- GA means everything should become a Foundry prompt agent
- Foundry-hosted and prompt-agent are the same thing
- local tools are a problem by themselves

The actual problem is the old hybrid pattern:

- service-managed Foundry agent identity
- backend-injected local runtime tools

GA pushes toward a cleaner separation:

- either Foundry owns the agent definition
- or the app/code owns the agent definition

## Current Working Conclusion

The likely target architecture is:

- `Classifier`: code agent, app-hosted
- `AdminAgent`: code agent, app-hosted
- `InvestigationAgent`: code agent, app-hosted for now
- `Connections Agent`: code agent, strong Hosted Agent candidate

So the main strategic question is not:

- "Should these be prompt agents?"

It is:

- "Which code agents should remain in this backend?"
- "Which code agents should eventually become Hosted Agents?"

## Suggested Next Planning Step

Create a migration plan in two waves:

### Wave 1

- Move the existing app-hosted agents to the GA code-agent model
- Replace old beta/RC Foundry client usage with the GA code-agent pattern
- Keep deployment topology the same

### Wave 2

- Evaluate the `Connections Agent` as the first Hosted Agent pilot
- Reassess whether `InvestigationAgent` should also move later

## Official References

- [Microsoft Agent Framework Foundry provider docs](https://learn.microsoft.com/en-us/agent-framework/agents/providers/microsoft-foundry)
- [Microsoft Agent Framework Python significant changes](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes)
- [Azure AI Foundry Agent Service overview](https://learn.microsoft.com/en-us/azure/foundry/agents/overview)
- [Azure AI Foundry Hosted Agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Python 1.0.0 release](https://github.com/microsoft/agent-framework/releases/tag/python-1.0.0)
- [Python 1.0.1 release](https://github.com/microsoft/agent-framework/releases/tag/python-1.0.1)
