# Phase 3: Text Classification Pipeline - Research

**Researched:** 2026-02-21
**Domain:** Multi-agent orchestration (Orchestrator + Classifier) with Microsoft Agent Framework, LLM-based text classification, Cosmos DB filing
**Confidence:** HIGH

## Summary

Phase 3 replaces the echo agent with a two-agent handoff workflow: an Orchestrator that receives all input and routes to a Classifier that classifies text into one of four buckets (People, Projects, Ideas, Admin) with a confidence score, then files the result to Cosmos DB. This is the first multi-agent phase and introduces the HandoffBuilder from `agent-framework-orchestrations`.

The critical architectural finding is that HandoffBuilder produces a `Workflow` object, which must be converted to an agent via `workflow.as_agent()` before passing to `add_agent_framework_fastapi_endpoint()`. The AG-UI endpoint only accepts agents (not raw workflows). The Classifier should use a `@tool` function that performs the actual classification and filing -- the LLM decides which tool to call and with what arguments, while the tool handles structured validation via Pydantic and Cosmos DB writes. Confidence scoring should be self-assessed by the LLM as part of the tool call arguments (the LLM reports its confidence as a float parameter), not extracted from token logprobs.

There are three known bugs at the boundary of HandoffBuilder + AG-UI + `as_agent()` that require awareness: the context_provider cloning bug (fixed in current RC), the JSON serialization crash on handoff user-input requests (fixed), and the echo bug where `as_agent()` echoes user input (open, issue #3206 -- has workaround). For Phase 3, the echo bug is the most relevant risk since we use `workflow.as_agent()` with `add_agent_framework_fastapi_endpoint`. The workaround is to filter the echoed prefix on the client side or accept it for now (Phase 4 adds richer event handling).

**Primary recommendation:** Install `agent-framework-orchestrations`, build a HandoffBuilder with Orchestrator (start agent) routing to Classifier, convert to WorkflowAgent via `as_agent()`, register with AG-UI endpoint. Classifier uses a `classify_and_file` tool that takes bucket + confidence as parameters, validates with Pydantic, writes to Cosmos DB Inbox + target container.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ORCH-01 | Orchestrator Agent receives all input and routes to the correct specialist agent based on input type and context | HandoffBuilder's `with_start_agent(orchestrator)` + `add_handoff(orchestrator, [classifier])` configures the Orchestrator as the entry point. For Phase 3, text-only routing is trivial (always hand off to Classifier). |
| ORCH-02 | Orchestrator routes text input directly to Classifier Agent | Single handoff rule: `add_handoff(orchestrator, [classifier])`. Orchestrator instructions say "Always hand off text input to the Classifier." |
| ORCH-06 | Orchestrator provides brief confirmation when the full agent chain completes | HandoffBuilder is interactive by default -- when Classifier finishes and doesn't handoff further, it generates a response to the user. The Classifier's final message serves as the confirmation (e.g., "Filed -> Projects (0.85)"). Autonomous mode can auto-continue if needed. |
| CLAS-01 | Classifier Agent classifies input into exactly one of four buckets: People, Projects, Ideas, or Admin | Classifier agent instructions + `classify_and_file` tool with `container_name` parameter restricted to the four buckets. Pydantic validation ensures only valid buckets. |
| CLAS-02 | Classifier assigns a confidence score (0.0-1.0) to each classification | `classify_and_file` tool takes a `confidence` float parameter (0.0-1.0). The LLM self-reports confidence based on the classification prompt. |
| CLAS-03 | When confidence >= 0.6, Classifier silently files the record and confirms | Tool logic: if confidence >= 0.6, write to target container + Inbox, return confirmation string. Classifier agent relays this as its response. |
| CLAS-07 | Every capture is logged to the Inbox container with full classification details and agent chain metadata | `classify_and_file` tool always writes to Inbox container with classificationMeta containing bucket, confidence, agentChain, and timestamps. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `agent-framework-orchestrations` | `--pre` (1.0.0b260210) | HandoffBuilder for multi-agent workflow | Required for HandoffBuilder, SequentialBuilder, etc. Separate package from `agent-framework-core`. Import: `from agent_framework.orchestrations import HandoffBuilder` |
| `agent-framework-core` | 1.0.0b260210 | Agent, tool, Message, WorkflowAgent | Already installed. Provides `Agent`, `@tool`, `Workflow.as_agent()` |
| `agent-framework-ag-ui` | 1.0.0b260210 | AG-UI FastAPI endpoint | Already installed. `add_agent_framework_fastapi_endpoint(app, workflow_agent, "/api/ag-ui")` |
| `azure-cosmos` | >=4.14.0 | Async Cosmos DB client | Already installed. Used by CRUD tools for Inbox + bucket writes |

### Supporting (already installed, no changes)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic` | >=2.11.2 | Classification result validation, document models | Validate tool arguments, document schemas |
| `azure-identity` | >=1.16.1 | Azure AD auth for OpenAI + Cosmos | DefaultAzureCredential for all services |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LLM self-reported confidence | Token logprobs from Azure OpenAI | Logprobs give calibrated probabilities but Agent Framework manages LLM calls internally -- no direct access to logprobs through `@tool` arguments. Self-reported confidence is simpler and sufficient for the 0.6 threshold. Calibration can be added in Phase 4 (Evaluation Agent). |
| `classify_and_file` as single tool | Separate `classify` + `file_document` tools | Single tool reduces LLM reasoning steps (one tool call instead of two). The classification and filing are tightly coupled -- there's no scenario where you classify but don't file (in Phase 3). |
| HandoffBuilder (interactive) | SequentialBuilder | Sequential forces a fixed order and doesn't support HITL. Handoff allows the Classifier to interact with the user for low-confidence cases (Phase 4). Building with HandoffBuilder now avoids refactoring later. |

### Installation

```bash
# New dependency for Phase 3
cd /Users/willmacdonald/Documents/Code/claude/second-brain/backend
uv pip install agent-framework-orchestrations --prerelease=allow
```

Add to `pyproject.toml` dependencies:
```toml
"agent-framework-orchestrations",
```

## Architecture Patterns

### Recommended Project Structure Changes

```
backend/src/second_brain/
├── agents/
│   ├── __init__.py
│   ├── echo.py              # KEEP for reference (Phase 1)
│   ├── orchestrator.py      # NEW: Orchestrator agent definition
│   ├── classifier.py        # NEW: Classifier agent definition
│   └── workflow.py          # NEW: HandoffBuilder wiring + as_agent()
├── tools/
│   ├── __init__.py
│   ├── cosmos_crud.py       # EXISTING: general CRUD tools
│   └── classification.py    # NEW: classify_and_file tool
├── models/
│   ├── __init__.py
│   └── documents.py         # UPDATE: add classificationMeta schema
└── main.py                  # UPDATE: replace echo agent with workflow agent
```

### Pattern 1: HandoffBuilder Workflow -> WorkflowAgent -> AG-UI

**What:** Build a HandoffBuilder workflow with Orchestrator as start agent, convert to WorkflowAgent via `as_agent()`, then register with `add_agent_framework_fastapi_endpoint()`. This is the standard pattern for exposing multi-agent workflows via AG-UI.

**When to use:** Whenever a HandoffBuilder workflow needs to be served via the AG-UI SSE endpoint.

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/as-agents
# + https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/handoff

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework.orchestrations import HandoffBuilder
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint
from azure.identity import DefaultAzureCredential
from fastapi import FastAPI

# Create chat client (shared across agents)
chat_client = AzureOpenAIChatClient(
    credential=DefaultAzureCredential(),
    endpoint=settings.azure_openai_endpoint,
    deployment_name=settings.azure_openai_chat_deployment_name,
)

# Create specialized agents
orchestrator = chat_client.as_agent(
    name="Orchestrator",
    instructions="You route all input to the appropriate specialist agent...",
    description="Routes user input to specialist agents",
)

classifier = chat_client.as_agent(
    name="Classifier",
    instructions="You classify text into People, Projects, Ideas, or Admin...",
    description="Classifies text and files to Cosmos DB",
    tools=[classify_and_file],
)

# Build the handoff workflow
workflow = (
    HandoffBuilder(
        name="capture_pipeline",
        participants=[orchestrator, classifier],
    )
    .with_start_agent(orchestrator)
    .add_handoff(orchestrator, [classifier])
    .build()
)

# Convert workflow to agent for AG-UI
workflow_agent = workflow.as_agent(name="SecondBrainPipeline")

# Register with FastAPI
app = FastAPI()
add_agent_framework_fastapi_endpoint(app, workflow_agent, "/api/ag-ui")
```

**Confidence:** HIGH -- verified from official Microsoft Learn docs (updated 2026-02-20) and confirmed `Workflow.as_agent()` exists in installed package.

### Pattern 2: Classification via Tool Calling

**What:** The Classifier agent uses a `@tool`-decorated function that takes bucket name, confidence, raw text, and optional title as parameters. The LLM decides which bucket and what confidence score based on its instructions, then calls the tool. The tool validates inputs with Pydantic and writes to Cosmos DB.

**When to use:** When the LLM needs to make a classification decision and immediately act on it (file to database). The tool pattern gives the LLM a structured way to express its decision while the tool handles validation and persistence.

**Why not structured output / response_format:** Agent Framework manages LLM calls internally. The `@tool` pattern is the idiomatic way to get structured data out of agents. The LLM's tool call arguments ARE the structured output -- Pydantic validates them automatically.

**Example:**
```python
# Source: Adapted from existing CosmosCrudTools pattern + Agent Framework @tool docs

from typing import Annotated, Literal
from agent_framework import tool

VALID_BUCKETS = Literal["People", "Projects", "Ideas", "Admin"]

@tool
async def classify_and_file(
    self,
    bucket: Annotated[VALID_BUCKETS, "Classification bucket: People, Projects, Ideas, or Admin"],
    confidence: Annotated[float, "Confidence score from 0.0 to 1.0"],
    raw_text: Annotated[str, "The original captured text"],
    title: Annotated[str, "Brief title for the record"] = "",
) -> str:
    """Classify the captured text and file it to the appropriate Cosmos DB container.

    Always call this tool after analyzing the text. Assign the most appropriate
    bucket and your confidence level in the classification.
    """
    # Validate confidence range
    confidence = max(0.0, min(1.0, confidence))

    if confidence < 0.6:
        return (
            f"Low confidence ({confidence:.2f}) for bucket '{bucket}'. "
            "Ask the user for clarification before filing."
        )

    # Build classification metadata
    classification_meta = {
        "bucket": bucket,
        "confidence": confidence,
        "classifiedBy": "Classifier",
        "agentChain": ["Orchestrator", "Classifier"],
    }

    # Write to Inbox (always)
    inbox_doc = InboxDocument(
        rawText=raw_text,
        classificationMeta=classification_meta,
        source="text",
    )
    inbox_container = self._manager.get_container("Inbox")
    await inbox_container.create_item(body=inbox_doc.model_dump(mode="json"))

    # Write to target bucket container
    model_class = CONTAINER_MODELS[bucket]
    kwargs = {"rawText": raw_text, "classificationMeta": classification_meta}
    if bucket == "People":
        kwargs["name"] = title or "Unnamed"
    elif bucket in ("Projects", "Ideas", "Admin"):
        kwargs["title"] = title or "Untitled"

    bucket_doc = model_class(**kwargs)
    bucket_container = self._manager.get_container(bucket)
    await bucket_container.create_item(body=bucket_doc.model_dump(mode="json"))

    return f"Filed -> {bucket} ({confidence:.2f})"
```

**Confidence:** HIGH -- follows the established `CosmosCrudTools` class-based tool pattern from Phase 1 and Microsoft's `@tool` documentation.

### Pattern 3: Autonomous Mode for Orchestrator

**What:** Enable autonomous mode on the Orchestrator agent so it always hands off without waiting for user input. The Orchestrator's only job is routing -- it should never pause to ask the user a question.

**When to use:** When an agent in a handoff workflow should always make a routing decision without human intervention.

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/handoff

workflow = (
    HandoffBuilder(
        name="capture_pipeline",
        participants=[orchestrator, classifier],
    )
    .with_start_agent(orchestrator)
    .add_handoff(orchestrator, [classifier])
    .with_autonomous_mode(
        agents=[orchestrator],
        prompts={orchestrator.name: "Route this to the Classifier agent."},
    )
    .build()
)
```

**Confidence:** HIGH -- autonomous mode is documented in official handoff docs with per-agent granularity.

### Pattern 4: classificationMeta Schema Extension

**What:** Extend the `classificationMeta` field on BaseDocument to include structured classification details: bucket, confidence, classifiedBy agent name, agentChain (list of agents that processed this capture), and timestamp.

**Example:**
```python
from pydantic import BaseModel

class ClassificationMeta(BaseModel):
    """Structured classification metadata attached to every filed document."""
    bucket: str                    # "People", "Projects", "Ideas", or "Admin"
    confidence: float              # 0.0-1.0
    classifiedBy: str              # Agent name, e.g., "Classifier"
    agentChain: list[str]          # e.g., ["Orchestrator", "Classifier"]
    classifiedAt: datetime         # Timestamp of classification
```

**Confidence:** HIGH -- extends the existing `classificationMeta: dict | None` field on BaseDocument (already defined in Phase 1).

### Anti-Patterns to Avoid

- **Putting the workflow (not WorkflowAgent) into AG-UI endpoint:** `add_agent_framework_fastapi_endpoint` expects an agent, not a Workflow. Must call `workflow.as_agent()` first.
- **Making both agents autonomous:** If the Classifier is autonomous, it will never pause for user input on low-confidence classifications (needed in Phase 4). Only make the Orchestrator autonomous.
- **Separate LLM call for classification then another for filing:** One tool call does both. The LLM's tool call IS the classification decision. Don't add a second LLM round-trip.
- **Using SequentialBuilder instead of HandoffBuilder:** Sequential doesn't support HITL. Phase 4 needs the Classifier to ask clarifying questions. Build with HandoffBuilder now.
- **Creating a new AzureOpenAIChatClient per agent:** Share one chat_client instance across all agents. The SDK manages connection pooling internally.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-agent orchestration | Custom agent-calling-agent logic | `HandoffBuilder` from `agent-framework-orchestrations` | Framework handles tool registration, context broadcasting, session management, and event emission automatically |
| Workflow -> AG-UI bridging | Custom SSE event translation | `workflow.as_agent()` + `add_agent_framework_fastapi_endpoint()` | The framework converts workflow events to AG-UI events automatically (RUN_STARTED, TEXT_MESSAGE_CONTENT, etc.) |
| Handoff tool generation | Custom "transfer_to_classifier" tool | HandoffBuilder auto-generates handoff tools | `add_handoff(orchestrator, [classifier])` creates `handoff_to_Classifier` tool automatically with proper descriptions |
| Classification validation | Custom if/elif bucket checking | Pydantic `Literal["People", "Projects", "Ideas", "Admin"]` | Type-safe at the tool call boundary; invalid buckets are rejected before code runs |
| Conversation history in handoff | Manual message passing between agents | HandoffBuilder context synchronization (automatic broadcasting) | All participants receive broadcasts of other agents' responses automatically |

**Key insight:** The HandoffBuilder does the heavy lifting of wiring agents together. The custom code you write is: (1) agent instructions (prompts), (2) tool functions, and (3) the glue in `main.py` lifespan. Do not build orchestration plumbing.

## Common Pitfalls

### Pitfall 1: Missing `agent-framework-orchestrations` Package

**What goes wrong:** `from agent_framework.orchestrations import HandoffBuilder` raises `ModuleNotFoundError: The 'agent-framework-orchestrations' package is not installed`.
**Why it happens:** The orchestrations package is separate from `agent-framework-core` and `agent-framework-ag-ui`. It must be explicitly installed.
**How to avoid:** Add `"agent-framework-orchestrations"` to `pyproject.toml` dependencies and run `uv pip install agent-framework-orchestrations --prerelease=allow`.
**Warning signs:** Import error on first run after adding orchestration code.

### Pitfall 2: Passing Workflow (not WorkflowAgent) to AG-UI Endpoint

**What goes wrong:** `add_agent_framework_fastapi_endpoint(app, workflow, "/api/ag-ui")` fails or behaves unexpectedly because `workflow` is a `Workflow` object, not an agent.
**Why it happens:** HandoffBuilder.build() returns a `Workflow`. The AG-UI endpoint expects something implementing the agent protocol.
**How to avoid:** Always call `workflow.as_agent(name="...")` and pass the result to the endpoint.
**Warning signs:** Type error or AG-UI endpoint returning empty/error events.

### Pitfall 3: Echo Bug with WorkflowAgent.as_agent() (Issue #3206)

**What goes wrong:** When using `workflow.as_agent()` with `add_agent_framework_fastapi_endpoint`, the user's input message is echoed as the first part of the assistant's streamed response.
**Why it happens:** Internal HandoffBuilder executors bypass the output_response filter in `_convert_workflow_event_to_agent_update()`.
**How to avoid:** For Phase 3, this is cosmetic -- the mobile app currently only uses RUN_FINISHED events (fire-and-forget pattern from Phase 2). The echoed text appears in the stream but the app ignores TEXT_MESSAGE_CONTENT events. When Phase 4 adds streaming display, implement the client-side filter workaround from the issue.
**Warning signs:** AG-UI Dojo or DevUI shows user message prepended to agent response.

### Pitfall 4: Orchestrator Not Handing Off (Generates Response Instead)

**What goes wrong:** The Orchestrator responds to the user directly instead of calling the handoff tool to transfer to the Classifier.
**Why it happens:** The LLM generates a text response instead of a tool call. In HandoffBuilder, if an agent doesn't call a handoff tool, the workflow pauses for user input (interactive mode).
**How to avoid:** (1) Make Orchestrator instructions explicit: "ALWAYS hand off to the Classifier. NEVER respond directly." (2) Enable autonomous mode on the Orchestrator with a prompt that forces handoff. (3) Give the Orchestrator a clear `description` so the auto-generated handoff tool has meaningful text.
**Warning signs:** AG-UI events show Orchestrator generating TEXT_MESSAGE_CONTENT instead of TOOL_CALL_START for the handoff.

### Pitfall 5: Classifier Confidence Always 0.9+ (Uncalibrated)

**What goes wrong:** The LLM always reports high confidence regardless of ambiguity. "Buy milk" gets confidence 0.95 for Admin, "Talked to Sarah about the deck project" gets 0.92 for People (could be Projects).
**Why it happens:** LLMs tend to be overconfident in self-assessed scores. Without calibration, the 0.6 threshold is meaningless because everything passes.
**How to avoid:** (1) Include classification examples in the prompt that demonstrate appropriate low-confidence scenarios. (2) Explicitly instruct: "Assign confidence below 0.6 when the text could reasonably belong to multiple buckets." (3) Test with 20+ real captures and verify the confidence distribution has meaningful variance. (4) Phase 4's Evaluation Agent can provide calibration data.
**Warning signs:** All classifications have confidence > 0.8. No captures ever trigger the low-confidence path.

### Pitfall 6: Context Broadcasting Bloats Token Usage

**What goes wrong:** Every agent response is broadcast to all participants in the handoff workflow. With two agents this is manageable, but adding more agents later means every response is duplicated N times in context windows.
**Why it happens:** HandoffBuilder uses context synchronization where all participants receive all messages. This is by design -- agents need context to make informed decisions.
**How to avoid:** For Phase 3 (2 agents), this is not a problem. For future phases: keep agent responses concise, don't include verbose tool output in responses, and monitor token usage per capture. The Orchestrator should produce minimal output (just the routing decision).
**Warning signs:** Token usage per capture exceeds 2,000 total across both agents.

## Code Examples

### Complete Orchestrator Agent Definition

```python
# Source: Adapted from official HandoffBuilder docs
# File: backend/src/second_brain/agents/orchestrator.py

"""Orchestrator agent that routes input to specialist agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIChatClient

if TYPE_CHECKING:
    pass


def create_orchestrator_agent(chat_client: AzureOpenAIChatClient) -> Agent:
    """Create the Orchestrator agent.

    The Orchestrator receives all user input and routes to the appropriate
    specialist. For Phase 3 (text only), it always routes to the Classifier.
    """
    return chat_client.as_agent(
        name="Orchestrator",
        instructions=(
            "You are the Orchestrator for a personal knowledge management system. "
            "Your ONLY job is to route user input to the correct specialist agent. "
            "NEVER answer questions directly. ALWAYS hand off to a specialist.\n\n"
            "For text input: hand off to the Classifier agent immediately.\n\n"
            "Do not add commentary. Just hand off."
        ),
        description="Routes user input to the appropriate specialist agent",
    )
```

### Complete Classifier Agent Definition

```python
# File: backend/src/second_brain/agents/classifier.py

"""Classifier agent that classifies text into buckets and files to Cosmos DB."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIChatClient

if TYPE_CHECKING:
    from second_brain.tools.classification import ClassificationTools


def create_classifier_agent(
    chat_client: AzureOpenAIChatClient,
    classification_tools: ClassificationTools,
) -> Agent:
    """Create the Classifier agent with classification tools."""
    return chat_client.as_agent(
        name="Classifier",
        instructions=(
            "You are the Classifier for a personal knowledge management system. "
            "You classify captured text into exactly ONE of four buckets:\n\n"
            "- **People**: Mentions of specific people, interactions, relationships, "
            "contact info, birthdays, personal notes about someone\n"
            "- **Projects**: Work tasks, project updates, deliverables, deadlines, "
            "professional goals, work-related actions\n"
            "- **Ideas**: Creative thoughts, hypotheses, 'what if' musings, "
            "inspiration, concepts to explore later\n"
            "- **Admin**: Personal errands, appointments, household tasks, bills, "
            "logistics, non-work obligations\n\n"
            "RULES:\n"
            "1. Always call the classify_and_file tool with your classification\n"
            "2. Assign confidence 0.8-1.0 when the text clearly fits one bucket\n"
            "3. Assign confidence 0.6-0.79 when the text mostly fits but has some ambiguity\n"
            "4. Assign confidence below 0.6 when the text could belong to 2+ buckets equally\n"
            "5. Extract a brief title (3-6 words) from the text\n"
            "6. After filing, respond with ONLY the confirmation (e.g., 'Filed -> Projects (0.85)')\n\n"
            "EXAMPLES:\n"
            "- 'Call Sarah about the deck quote' -> People (0.75) -- mentions a person but also a project\n"
            "- 'New ML paper on transformers looks promising' -> Ideas (0.90)\n"
            "- 'Sprint review slides due Friday' -> Projects (0.95)\n"
            "- 'Pick up prescription at Walgreens' -> Admin (0.92)\n"
            "- 'Interesting conversation with Mike about moving to Austin' -> People (0.55) -- "
            "could be People or Ideas, low confidence"
        ),
        description="Classifies text into People/Projects/Ideas/Admin and files to Cosmos DB",
        tools=[classification_tools.classify_and_file],
    )
```

### Complete Handoff Workflow Wiring

```python
# File: backend/src/second_brain/agents/workflow.py

"""HandoffBuilder workflow wiring for the capture pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_framework import Agent, WorkflowAgent
from agent_framework.orchestrations import HandoffBuilder

if TYPE_CHECKING:
    pass


def create_capture_workflow(
    orchestrator: Agent,
    classifier: Agent,
) -> WorkflowAgent:
    """Build the handoff workflow and return a WorkflowAgent for AG-UI.

    The workflow routes: Orchestrator -> Classifier.
    Orchestrator runs in autonomous mode (always hands off, never waits).
    Classifier is interactive (can pause for user input in Phase 4).
    """
    workflow = (
        HandoffBuilder(
            name="capture_pipeline",
            participants=[orchestrator, classifier],
        )
        .with_start_agent(orchestrator)
        .add_handoff(orchestrator, [classifier])
        .with_autonomous_mode(
            agents=[orchestrator],
            prompts={orchestrator.name: "Route this input to the Classifier."},
        )
        .build()
    )

    return workflow.as_agent(name="SecondBrainPipeline")
```

### Complete Classification Tool

```python
# File: backend/src/second_brain/tools/classification.py

"""Classification tool for the Classifier agent."""

import logging
from datetime import UTC, datetime
from typing import Annotated, Literal

from agent_framework import tool

from second_brain.db.cosmos import CosmosManager
from second_brain.models.documents import CONTAINER_MODELS, InboxDocument

logger = logging.getLogger(__name__)

VALID_BUCKETS = Literal["People", "Projects", "Ideas", "Admin"]


class ClassificationTools:
    """Classification tools bound to a CosmosManager instance."""

    def __init__(self, cosmos_manager: CosmosManager) -> None:
        self._manager = cosmos_manager

    @tool
    async def classify_and_file(
        self,
        bucket: Annotated[VALID_BUCKETS, "Classification bucket"],
        confidence: Annotated[float, "Confidence score 0.0-1.0"],
        raw_text: Annotated[str, "The original captured text"],
        title: Annotated[str, "Brief title (3-6 words)"] = "",
    ) -> str:
        """Classify captured text and file to Cosmos DB.

        Always call this after analyzing the text. Assigns the text to
        exactly one bucket with a confidence score.
        """
        confidence = max(0.0, min(1.0, confidence))

        classification_meta = {
            "bucket": bucket,
            "confidence": confidence,
            "classifiedBy": "Classifier",
            "agentChain": ["Orchestrator", "Classifier"],
            "classifiedAt": datetime.now(UTC).isoformat(),
        }

        # Always log to Inbox
        inbox_doc = InboxDocument(
            rawText=raw_text,
            classificationMeta=classification_meta,
            source="text",
        )
        inbox_container = self._manager.get_container("Inbox")
        await inbox_container.create_item(
            body=inbox_doc.model_dump(mode="json")
        )

        if confidence < 0.6:
            logger.info(
                "Low confidence %.2f for bucket %s: %s",
                confidence, bucket, raw_text[:80],
            )
            return (
                f"Low confidence ({confidence:.2f}) for '{bucket}'. "
                "I'm not sure about this classification. "
                "Could you clarify what this is about?"
            )

        # File to target bucket
        model_class = CONTAINER_MODELS[bucket]
        kwargs: dict = {
            "rawText": raw_text,
            "classificationMeta": classification_meta,
        }
        if bucket == "People":
            kwargs["name"] = title or "Unnamed"
        elif bucket in ("Projects", "Ideas", "Admin"):
            kwargs["title"] = title or "Untitled"

        doc = model_class(**kwargs)
        target_container = self._manager.get_container(bucket)
        await target_container.create_item(
            body=doc.model_dump(mode="json")
        )

        logger.info(
            "Filed to %s (%.2f): %s", bucket, confidence, raw_text[:80]
        )
        return f"Filed -> {bucket} ({confidence:.2f})"
```

### Updated main.py Lifespan (Key Changes)

```python
# In main.py lifespan -- replace echo agent with workflow agent

from second_brain.agents.orchestrator import create_orchestrator_agent
from second_brain.agents.classifier import create_classifier_agent
from second_brain.agents.workflow import create_capture_workflow
from second_brain.tools.classification import ClassificationTools

# Inside lifespan, after cosmos_manager initialization:

# Create shared chat client
chat_client = AzureOpenAIChatClient(
    credential=DefaultAzureCredential(),
    endpoint=settings.azure_openai_endpoint,
    deployment_name=settings.azure_openai_chat_deployment_name,
)

# Create tools
classification_tools = ClassificationTools(cosmos_manager)

# Create agents
orchestrator = create_orchestrator_agent(chat_client)
classifier = create_classifier_agent(chat_client, classification_tools)

# Build workflow and register with AG-UI
workflow_agent = create_capture_workflow(orchestrator, classifier)
add_agent_framework_fastapi_endpoint(app, workflow_agent, "/api/ag-ui")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ChatAgent` class name | `Agent` (renamed in RC) | 2026-02-10 (RC release) | All agent creation uses `Agent` or `chat_client.as_agent()` |
| `ChatMessage` | `Message` | 2026-02-10 (RC release) | Message types simplified |
| `context_provider` (singular) on Agent | `context_providers` (plural, list) | 2026-02-10 (RC release) | Agents accept multiple context providers |
| `AgentRunContext` | `AgentContext` | 2026-02-10 (RC release) | Context type renamed |
| HandoffBuilder in `agent_framework` | HandoffBuilder in `agent_framework.orchestrations` | 2026-02-10 (RC release) | Orchestrations moved to dedicated package |
| `get_response` method | `run` method | 2026-02-10 (RC release) | API method consolidated |
| Manual workflow event handling | `workflow.as_agent()` auto-converts events | 2026-02-17 (docs updated) | Workflows can be used as drop-in agent replacements |

**Deprecated/outdated:**
- `ChatAgent`: Use `Agent` (renamed in RC)
- `get_response()`: Use `run()` method
- Single-tier executor model in HandoffBuilder: Removed in favor of broadcasting model with `HandoffAgentExecutor`

## Open Questions

1. **Echo Bug (Issue #3206) -- Will it be fixed before Phase 4?**
   - What we know: Open issue, persists in 1.0.0b260210. Root cause identified.
   - What's unclear: No timeline for fix.
   - Recommendation: Accept for Phase 3 (mobile app ignores TEXT_MESSAGE_CONTENT). Implement client-side filter workaround in Phase 4 if not fixed by then.

2. **AG-UI `request_info` events for HITL in handoff workflows**
   - What we know: Issue #3239 notes that AG-UI doesn't treat `request_info` from workflows as first-class UI events in handoff-as-agent flows.
   - What's unclear: Whether the workaround is sufficient for Phase 4's clarification flow.
   - Recommendation: Not needed for Phase 3 (confidence >= 0.6 path only). Research deeper in Phase 4 research.

3. **Confidence calibration quality**
   - What we know: LLM self-reported confidence is often poorly calibrated. Research shows calibration errors of ~45% before calibration.
   - What's unclear: How GPT-4o performs specifically on the 4-bucket classification task with well-crafted examples.
   - Recommendation: Ship with self-reported confidence. Add 20+ real capture test after building. Adjust prompt examples based on observed distribution.

## Sources

### Primary (HIGH confidence)
- [Microsoft Agent Framework: Handoff Orchestration](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/handoff) -- HandoffBuilder API, Python code examples, autonomous mode, context synchronization, HITL patterns. Updated 2026-02-13.
- [Microsoft Agent Framework: Using Workflows as Agents](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/as-agents) -- `workflow.as_agent()` API, session management, streaming execution. Updated 2026-02-20.
- [AG-UI Getting Started](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/getting-started) -- `add_agent_framework_fastapi_endpoint()` API, server setup, SSE protocol. Updated 2026-02-13.
- [Agent Framework RC Release Notes (python-1.0.0b260210)](https://github.com/microsoft/agent-framework/releases/tag/python-1.0.0b260210) -- Breaking changes, bug fixes for context_provider cloning and AG-UI message handling.
- Local codebase verification: `Workflow.as_agent()` confirmed present, `HandoffBuilder` import path confirmed as `agent_framework.orchestrations`.

### Secondary (MEDIUM confidence)
- [HandoffBuilder context_provider bug #3709](https://github.com/microsoft/agent-framework/issues/3709) -- Closed/fixed in RC. Context providers now properly cloned.
- [AG-UI JSON serialization crash #3239](https://github.com/microsoft/agent-framework/issues/3239) -- Closed/fixed. Note: AG-UI still doesn't fully support request_info events from handoff-as-agent workflows.
- [WorkflowAgent echo bug #3206](https://github.com/microsoft/agent-framework/issues/3206) -- Open. User input echoed in streamed response. Workaround: client-side filter.
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs) -- JSON schema response_format, Pydantic integration (not directly used, but informs tool design).
- [LLM Classification Confidence Calibration](https://www.nyckel.com/blog/calibrating-gpt-classifications/) -- Self-assessed GPT confidences have ~45% calibration error before calibration.

### Tertiary (LOW confidence)
- [LLM Classifier Confidence Scores blog](https://aejaspan.github.io/posts/2025-09-01-LLM-Clasifier-Confidence-Scores) -- Logprob-based confidence vs self-reported. Useful context but not directly applicable (Agent Framework abstracts LLM calls).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- `agent-framework-orchestrations` import path verified locally; HandoffBuilder API verified from official docs
- Architecture: HIGH -- HandoffBuilder -> as_agent() -> AG-UI pattern verified from three official Microsoft Learn pages + local code verification
- Pitfalls: HIGH -- Three bugs verified via GitHub issues (2 fixed, 1 open with workaround); confidence calibration concern backed by multiple sources
- Classification approach: MEDIUM -- Tool-based classification is idiomatic for Agent Framework, but confidence calibration quality is unknown until tested with real data

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (framework is pre-GA; check for new RC releases before Phase 4)
