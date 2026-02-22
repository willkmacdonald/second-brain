"""HandoffBuilder workflow wiring for the capture pipeline.

Includes an AG-UI adapter that wraps WorkflowAgent for AG-UI endpoint compatibility.
WorkflowAgent.run(stream=True) returns an AsyncIterable[AgentResponseUpdate] but
AG-UI expects a ResponseStream. This adapter wraps the output in a ResponseStream.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from collections.abc import AsyncIterable, Sequence
from typing import Any, Literal, overload

from agent_framework import (
    Agent,
    AgentResponse,
    AgentResponseUpdate,
    AgentThread,
    Message,
    WorkflowAgent,
    WorkflowEvent,
)
from agent_framework._types import ResponseStream
from agent_framework.orchestrations import HandoffBuilder

logger = logging.getLogger(__name__)


class AGUIWorkflowAdapter:
    """Adapter that wraps a workflow definition for AG-UI endpoint compatibility.

    Creates a fresh WorkflowAgent per request to avoid state leaking
    between requests (e.g., conversation_id accumulation).
    """

    def __init__(
        self,
        orchestrator: Agent,
        classifier: Agent,
        name: str,
    ) -> None:
        self._orchestrator = orchestrator
        self._classifier = classifier
        self.id = f"workflow-{name}"
        self.name = name
        self.description = "Capture pipeline workflow"

    def _create_workflow_agent(self) -> WorkflowAgent:
        """Create a fresh WorkflowAgent for each request."""
        workflow = (
            HandoffBuilder(
                name="capture_pipeline",
                participants=[self._orchestrator, self._classifier],
            )
            .with_start_agent(self._orchestrator)
            .add_handoff(self._orchestrator, [self._classifier])
            .with_autonomous_mode(
                agents=[self._orchestrator, self._classifier],
                prompts={
                    self._orchestrator.name: "Route this input to the Classifier.",
                    self._classifier.name: "Classify this text and file it.",
                },
            )
            .build()
        )
        return WorkflowAgent(workflow, name="SecondBrainPipeline")

    @overload
    def run(
        self,
        messages: str | Message | Sequence[str | Message] | None = None,
        *,
        stream: Literal[False] = ...,
        thread: AgentThread | None = None,
        **kwargs: Any,
    ) -> Any: ...

    @overload
    def run(
        self,
        messages: str | Message | Sequence[str | Message] | None = None,
        *,
        stream: Literal[True],
        thread: AgentThread | None = None,
        **kwargs: Any,
    ) -> ResponseStream[AgentResponseUpdate, AgentResponse[Any]]: ...

    async def _stream_updates(
        self,
        messages: str | Message | Sequence[str | Message] | None,
        thread: AgentThread | None,
        **kwargs: Any,
    ) -> AsyncIterable[AgentResponseUpdate]:
        """Stream updates from the workflow, converting WorkflowEvents.

        WorkflowAgent.run(stream=True) in this version (1.0.0b260210)
        yields raw WorkflowEvent objects instead of AgentResponseUpdate.

        For Phase 3 (fire-and-forget), both Orchestrator and Classifier
        run in autonomous mode.  The stream ends gracefully after
        classification completes.
        """
        workflow_agent = self._create_workflow_agent()
        source = workflow_agent.run(
            messages, stream=True, thread=thread, **kwargs
        )
        response_id = str(_uuid.uuid4())
        try:
            async for event in source:
                if isinstance(event, AgentResponseUpdate):
                    yield event
                elif isinstance(event, WorkflowEvent):
                    logger.info(
                        "WorkflowEvent: type=%s", event.type
                    )
                    if event.type == "request_info":
                        continue
                    converter = (
                        workflow_agent
                        ._convert_workflow_event_to_agent_response_updates
                    )
                    updates = converter(response_id, event)
                    for update in updates:
                        yield update
        except Exception as exc:
            # Workflow may error after classification is complete
            # (e.g., request_info timeout). Classification already
            # filed to Cosmos DB — let the stream end gracefully.
            logger.warning(
                "Workflow stream error: %s", exc
            )

    def run(
        self,
        messages: str | Message | Sequence[str | Message] | None = None,
        *,
        stream: bool = False,
        thread: AgentThread | None = None,
        **kwargs: Any,
    ) -> Any:
        """Run the workflow, wrapping streaming output in a ResponseStream."""
        if stream:
            return ResponseStream(self._stream_updates(messages, thread, **kwargs))
        workflow_agent = self._create_workflow_agent()
        return workflow_agent.run(
            messages, stream=False, thread=thread, **kwargs
        )

    def get_new_thread(self, **kwargs: Any) -> AgentThread:
        """Create a new conversation thread."""
        return AgentThread(**kwargs)


def create_capture_workflow(
    orchestrator: Agent,
    classifier: Agent,
) -> AGUIWorkflowAdapter:
    """Build the AG-UI compatible adapter for the capture pipeline.

    The workflow routes: Orchestrator -> Classifier.
    Both agents run in autonomous mode for Phase 3 (fire-and-forget).
    A fresh WorkflowAgent is created per request to avoid state leakage.
    """
    return AGUIWorkflowAdapter(orchestrator, classifier, name="SecondBrainPipeline")
