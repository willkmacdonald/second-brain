"""HandoffBuilder workflow wiring for the capture pipeline.

Includes an AG-UI adapter that wraps Workflow for AG-UI endpoint compatibility.
Phase 4 additions: HITL support (request_info handling + respond), AG-UI step
events (StepStarted/StepFinished on agent transitions), Orchestrator echo
filtering, and in-memory pending session storage for HITL continuation.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from collections.abc import AsyncIterable, Sequence
from typing import Any, Literal, overload

from ag_ui.core import EventType
from ag_ui.core.events import (
    BaseEvent,
    CustomEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from agent_framework import (
    Agent,
    AgentResponse,
    AgentResponseUpdate,
    AgentThread,
    Content,
    Message,
    Workflow,
    WorkflowAgent,
    WorkflowEvent,
)
from agent_framework._types import ResponseStream
from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder

logger = logging.getLogger(__name__)

# Union type for the mixed stream produced by the adapter.
# AgentResponseUpdate comes from the workflow converter;
# BaseEvent is injected by the adapter for step/HITL events.
StreamItem = AgentResponseUpdate | BaseEvent


class AGUIWorkflowAdapter:
    """Adapter that wraps a workflow definition for AG-UI endpoint compatibility.

    Creates a fresh Workflow per request to avoid state leaking
    between requests (e.g., conversation_id accumulation).

    Phase 4: Supports HITL pause/resume via _pending_sessions, emits
    AG-UI StepStarted/StepFinished events, and filters Orchestrator echo.
    """

    # Store pending HITL sessions: thread_id -> (workflow, request_id)
    _pending_sessions: dict[str, tuple[Workflow, str]] = {}

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
        # Keep a dummy WorkflowAgent for its converter method reference
        self._converter_agent: WorkflowAgent | None = None

    def _create_workflow(self) -> Workflow:
        """Create a fresh Workflow for each request.

        Returns the raw Workflow (not WorkflowAgent) so that
        workflow.run(responses=...) is available for HITL resumption.
        Only the Orchestrator is autonomous; the Classifier is interactive
        so it emits request_info when it responds without handing off.
        """
        workflow = (
            HandoffBuilder(
                name="capture_pipeline",
                participants=[self._orchestrator, self._classifier],
            )
            .with_start_agent(self._orchestrator)
            .add_handoff(self._orchestrator, [self._classifier])
            .with_autonomous_mode(
                agents=[self._orchestrator],
                prompts={
                    self._orchestrator.name: "Route this input to the Classifier.",
                },
            )
            .build()
        )
        return workflow

    def _get_converter(self) -> WorkflowAgent:
        """Lazily create a WorkflowAgent for its event converter method."""
        if self._converter_agent is None:
            workflow = self._create_workflow()
            self._converter_agent = WorkflowAgent(
                workflow, name="ConverterHelper"
            )
        return self._converter_agent

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
    ) -> AsyncIterable[StreamItem]:
        """Stream updates from the workflow with step events and HITL support.

        Yields a mix of AgentResponseUpdate (text/tool content) and AG-UI
        BaseEvent (StepStarted, StepFinished, Custom HITL_REQUIRED).

        Echo filtering: Only yield text content from the Classifier agent.
        The Orchestrator's text (which echoes user input) is suppressed.
        """
        workflow = self._create_workflow()
        thread_id = kwargs.get("thread_id") or str(_uuid.uuid4())
        current_agent: str | None = None
        response_id = str(_uuid.uuid4())

        # Extract user input text for logging / debugging
        user_input_text = ""
        if isinstance(messages, str):
            user_input_text = messages
        elif isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, str):
                    user_input_text = msg
                    break
                if hasattr(msg, "text") and msg.text:
                    user_input_text = msg.text
                    break

        logger.info(
            "Starting workflow stream: thread_id=%s, user_input=%s",
            thread_id,
            user_input_text[:80] if user_input_text else "(empty)",
        )

        converter = self._get_converter()

        try:
            source = workflow.run(message=messages, stream=True)
            async for event in source:
                if isinstance(event, WorkflowEvent):
                    logger.info(
                        "WorkflowEvent: type=%s executor_id=%s",
                        event.type,
                        getattr(event, "executor_id", None),
                    )

                    # --- Step events ---
                    if event.type == "executor_invoked" and event.executor_id:
                        if current_agent and current_agent != event.executor_id:
                            yield StepFinishedEvent(step_name=current_agent)
                        current_agent = event.executor_id
                        yield StepStartedEvent(step_name=current_agent)
                        continue

                    if event.type == "executor_completed" and event.executor_id:
                        yield StepFinishedEvent(step_name=event.executor_id)
                        if current_agent == event.executor_id:
                            current_agent = None
                        continue

                    # --- HITL: request_info ---
                    if event.type == "request_info" and isinstance(
                        event.data, HandoffAgentUserRequest
                    ):
                        request_id = event.request_id
                        self._pending_sessions[thread_id] = (
                            workflow,
                            request_id,
                        )
                        logger.info(
                            "HITL pause: thread_id=%s request_id=%s",
                            thread_id,
                            request_id,
                        )

                        # Emit the agent's clarifying question as text events
                        msg_id = str(_uuid.uuid4())
                        agent_response = event.data.agent_response
                        question_text = ""
                        for msg in agent_response.messages:
                            for content in msg.contents:
                                if hasattr(content, "text") and content.text:
                                    question_text += content.text

                        if question_text:
                            yield TextMessageStartEvent(
                                message_id=msg_id, role="assistant"
                            )
                            yield TextMessageContentEvent(
                                message_id=msg_id, delta=question_text
                            )
                            yield TextMessageEndEvent(message_id=msg_id)

                        # Signal HITL needed
                        yield CustomEvent(
                            name="HITL_REQUIRED",
                            value={"threadId": thread_id},
                        )
                        return  # End stream; client calls /respond

                    # --- Convert output/data events to AgentResponseUpdate ---
                    if event.type in ("output", "data"):
                        updates = (
                            converter
                            ._convert_workflow_event_to_agent_response_updates(
                                response_id, event
                            )
                        )
                        for update in updates:
                            # Echo filter: skip text from Orchestrator
                            if (
                                update.author_name
                                and update.author_name.lower()
                                == self._orchestrator.name.lower()
                            ):
                                # Check if this update has only text content
                                has_only_text = all(
                                    getattr(c, "type", None) == "text"
                                    for c in (update.contents or [])
                                )
                                if has_only_text:
                                    logger.debug(
                                        "Filtering Orchestrator echo: %s",
                                        update.text[:80] if update.text else "",
                                    )
                                    continue
                            yield update

                    # Skip other workflow events (status, superstep, etc.)

                elif isinstance(event, AgentResponseUpdate):
                    # Direct AgentResponseUpdate from the stream
                    # Echo filter: skip text from Orchestrator
                    if (
                        event.author_name
                        and event.author_name.lower()
                        == self._orchestrator.name.lower()
                    ):
                        has_only_text = all(
                            getattr(c, "type", None) == "text"
                            for c in (event.contents or [])
                        )
                        if has_only_text:
                            logger.debug(
                                "Filtering direct Orchestrator echo: %s",
                                event.text[:80] if event.text else "",
                            )
                            continue
                    yield event

        except Exception as exc:
            # Workflow may error after classification is complete
            # (e.g., request_info timeout). Classification already
            # filed to Cosmos DB -- let the stream end gracefully.
            logger.warning("Workflow stream error: %s", exc)

        # Final step finished for any open step
        if current_agent:
            yield StepFinishedEvent(step_name=current_agent)

    async def _stream_resume(
        self,
        workflow: Workflow,
        responses: dict[str, Any],
    ) -> AsyncIterable[StreamItem]:
        """Stream events from a resumed HITL workflow.

        Same event processing as _stream_updates but for the
        continuation after user clarification.
        """
        current_agent: str | None = None
        response_id = str(_uuid.uuid4())
        converter = self._get_converter()

        try:
            source = workflow.run(responses=responses, stream=True)
            async for event in source:
                if isinstance(event, WorkflowEvent):
                    logger.info(
                        "Resume WorkflowEvent: type=%s executor_id=%s",
                        event.type,
                        getattr(event, "executor_id", None),
                    )

                    if event.type == "executor_invoked" and event.executor_id:
                        if (
                            current_agent
                            and current_agent != event.executor_id
                        ):
                            yield StepFinishedEvent(step_name=current_agent)
                        current_agent = event.executor_id
                        yield StepStartedEvent(step_name=current_agent)
                        continue

                    if (
                        event.type == "executor_completed"
                        and event.executor_id
                    ):
                        yield StepFinishedEvent(step_name=event.executor_id)
                        if current_agent == event.executor_id:
                            current_agent = None
                        continue

                    if event.type in ("output", "data"):
                        updates = (
                            converter
                            ._convert_workflow_event_to_agent_response_updates(
                                response_id, event
                            )
                        )
                        for update in updates:
                            # On resume, Orchestrator shouldn't produce text,
                            # but filter just in case
                            if (
                                update.author_name
                                and update.author_name.lower()
                                == self._orchestrator.name.lower()
                            ):
                                has_only_text = all(
                                    getattr(c, "type", None) == "text"
                                    for c in (update.contents or [])
                                )
                                if has_only_text:
                                    continue
                            yield update

                elif isinstance(event, AgentResponseUpdate):
                    yield event

        except Exception as exc:
            logger.warning("Resume stream error: %s", exc)

        if current_agent:
            yield StepFinishedEvent(step_name=current_agent)

    async def resume_with_response(
        self, thread_id: str, user_response: str
    ) -> AsyncIterable[StreamItem]:
        """Resume a paused HITL workflow with the user's clarification.

        Pops the pending session for thread_id, creates the response
        payload, and streams events from the resumed workflow.

        Raises:
            ValueError: If no pending session exists for thread_id.
        """
        if thread_id not in self._pending_sessions:
            raise ValueError(
                f"No pending HITL session for thread_id={thread_id}"
            )

        workflow, request_id = self._pending_sessions.pop(thread_id)
        logger.info(
            "Resuming HITL: thread_id=%s request_id=%s",
            thread_id,
            request_id,
        )

        responses = {
            request_id: HandoffAgentUserRequest.create_response(user_response)
        }
        async for item in self._stream_resume(workflow, responses):
            yield item

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
            # Extract thread_id from thread object if available
            thread_id = None
            if thread and hasattr(thread, "id"):
                thread_id = str(thread.id)
            return ResponseStream(
                self._stream_updates(
                    messages, thread, thread_id=thread_id, **kwargs
                )
            )
        # Non-streaming: create a workflow and run it
        workflow = self._create_workflow()
        return workflow.run(message=messages)

    def get_new_thread(self, **kwargs: Any) -> AgentThread:
        """Create a new conversation thread."""
        return AgentThread(**kwargs)


def create_capture_workflow(
    orchestrator: Agent,
    classifier: Agent,
) -> AGUIWorkflowAdapter:
    """Build the AG-UI compatible adapter for the capture pipeline.

    The workflow routes: Orchestrator -> Classifier.
    Only the Orchestrator runs in autonomous mode; the Classifier is
    interactive for Phase 4 HITL support.
    A fresh Workflow is created per request to avoid state leakage.
    """
    return AGUIWorkflowAdapter(orchestrator, classifier, name="SecondBrainPipeline")
