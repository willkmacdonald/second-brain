"""HandoffBuilder workflow wiring for the capture pipeline.

Includes an AG-UI adapter that wraps Workflow for AG-UI endpoint compatibility.
Phase 4 additions: HITL support (low-confidence detection + respond endpoint),
AG-UI step events (StepStarted/StepFinished on agent transitions), and
Orchestrator echo filtering.
"""

from __future__ import annotations

import logging
import re
import uuid as _uuid
from collections.abc import AsyncIterable, Sequence
from typing import Any, Literal, overload

from ag_ui.core.events import (
    BaseEvent,
    CustomEvent,
    StepFinishedEvent,
    StepStartedEvent,
)
from agent_framework import (
    Agent,
    AgentResponse,
    AgentResponseUpdate,
    AgentThread,
    Message,
    Workflow,
    WorkflowAgent,
    WorkflowEvent,
)
from agent_framework._types import ResponseStream
from agent_framework.orchestrations import HandoffBuilder

logger = logging.getLogger(__name__)

# Union type for the mixed stream produced by the adapter.
# AgentResponseUpdate comes from the workflow converter;
# BaseEvent is injected by the adapter for step/HITL events.
StreamItem = AgentResponseUpdate | BaseEvent

# Regex to extract confidence from "Filed → Bucket (0.XX)" tool result
_FILED_CONFIDENCE_RE = re.compile(r"Filed\s*→\s*\w+\s*\((\d+\.\d+)\)")

# Regex to extract (inbox_doc_id, clarification_text) from request_clarification output
_CLARIFICATION_RE = re.compile(
    r"Clarification\s*→\s*([a-f0-9\-]+)\s*\|\s*(.+)", re.DOTALL
)


class AGUIWorkflowAdapter:
    """Adapter that wraps a workflow definition for AG-UI endpoint compatibility.

    Creates a fresh Workflow per request to avoid state leaking
    between requests (e.g., conversation_id accumulation).

    Phase 4: Emits AG-UI StepStarted/StepFinished events, filters
    Orchestrator echo, and detects low-confidence classifications
    to emit HITL_REQUIRED for client-side clarification.
    """

    def __init__(
        self,
        orchestrator: Agent,
        classifier: Agent,
        name: str,
        classification_threshold: float = 0.6,
    ) -> None:
        self._orchestrator = orchestrator
        self._classifier = classifier
        self.id = f"workflow-{name}"
        self.name = name
        self.description = "Capture pipeline workflow"
        self._classification_threshold = classification_threshold
        # Keep a dummy WorkflowAgent for its converter method reference
        self._converter_agent: WorkflowAgent | None = None

    def _create_workflow(self) -> Workflow:
        """Create a fresh Workflow for each request.

        Returns the raw Workflow (not WorkflowAgent) so that all event
        types are visible in the stream — including executor_invoked and
        executor_completed needed for step events. WorkflowAgent filters
        these out and only yields output/request_info events.

        Both agents run in autonomous mode so the workflow completes
        without blocking on request_info.
        """
        return (
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

    def _get_converter(self) -> WorkflowAgent:
        """Lazily create a WorkflowAgent for its event converter method."""
        if self._converter_agent is None:
            workflow = self._create_workflow()
            self._converter_agent = WorkflowAgent(workflow, name="ConverterHelper")
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

    def _is_orchestrator_text(self, update: AgentResponseUpdate) -> bool:
        """Check if an update is text-only content from the Orchestrator."""
        if (
            update.author_name
            and update.author_name.lower() == self._orchestrator.name.lower()
        ):
            return all(
                getattr(c, "type", None) == "text" for c in (update.contents or [])
            )
        return False

    @staticmethod
    def _extract_confidence(text: str) -> float | None:
        """Extract confidence from 'Filed → Bucket (0.XX)' text."""
        match = _FILED_CONFIDENCE_RE.search(text)
        return float(match.group(1)) if match else None

    @staticmethod
    def _extract_clarification(text: str) -> tuple[str, str] | None:
        """Extract (inbox_item_id, clarification_text) from output."""
        match = _CLARIFICATION_RE.search(text)
        return (match.group(1), match.group(2)) if match else None

    async def _stream_updates(
        self,
        messages: str | Message | Sequence[str | Message] | None,
        thread: AgentThread | None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamItem]:
        """Stream updates from the workflow with step events and HITL detection.

        Yields a mix of AgentResponseUpdate (text/tool content) and AG-UI
        BaseEvent (StepStarted, StepFinished, Custom HITL_REQUIRED).

        Both agents run in autonomous mode. The adapter detects low-confidence
        classifications from tool results and appends HITL_REQUIRED after
        the normal stream completes.

        Echo filtering: Only yield text content from the Classifier agent.
        The Orchestrator's text (which echoes user input) is suppressed.
        """
        workflow = self._create_workflow()
        converter = self._get_converter()
        thread_id = kwargs.get("thread_id") or str(_uuid.uuid4())
        current_agent: str | None = None
        response_id = str(_uuid.uuid4())
        detected_confidence: float | None = None
        detected_clarification: tuple[str, str] | None = None

        logger.info("Starting workflow stream: thread_id=%s", thread_id)

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

                    # --- Convert output/data events to AgentResponseUpdate ---
                    if event.type in ("output", "data"):
                        # The converter only handles type="output"; for "data"
                        # events we re-wrap as "output" since the payload is
                        # identical.
                        convert_event = event
                        if event.type == "data":
                            convert_event = WorkflowEvent.output(
                                executor_id=event.executor_id or "",
                                data=event.data,
                            )
                        updates = (
                            converter._convert_workflow_event_to_agent_response_updates(
                                response_id, convert_event
                            )
                        )
                        for update in updates:
                            if self._is_orchestrator_text(update):
                                logger.debug(
                                    "Filtering Orchestrator echo: %s",
                                    update.text[:80] if update.text else "",
                                )
                                continue
                            # Detect clarification or confidence in text
                            if update.text and detected_clarification is None:
                                clar = self._extract_clarification(update.text)
                                if clar is not None:
                                    detected_clarification = clar
                                elif detected_confidence is None:
                                    conf = self._extract_confidence(update.text)
                                    if conf is not None:
                                        detected_confidence = conf
                            yield update

                    if event.type == "request_info":
                        # Both agents are autonomous, so request_info
                        # shouldn't fire. Skip if it does.
                        logger.warning("Unexpected request_info event")
                        continue

                    # Skip other workflow events (status, superstep, etc.)

                elif isinstance(event, AgentResponseUpdate):
                    if self._is_orchestrator_text(event):
                        logger.debug(
                            "Filtering direct Orchestrator echo: %s",
                            event.text[:80] if event.text else "",
                        )
                        continue
                    # Detect clarification or confidence in text
                    if event.text and detected_clarification is None:
                        clar = self._extract_clarification(event.text)
                        if clar is not None:
                            detected_clarification = clar
                        elif detected_confidence is None:
                            conf = self._extract_confidence(event.text)
                            if conf is not None:
                                detected_confidence = conf
                    yield event

        except Exception as exc:
            logger.warning("Workflow stream error: %s", exc)

        # Final step finished for any open step
        if current_agent:
            yield StepFinishedEvent(step_name=current_agent)

        # After workflow completes: emit HITL if clarification was requested
        if detected_clarification is not None:
            inbox_item_id, clarification_text = detected_clarification
            logger.info(
                "Clarification requested for inbox item %s, emitting HITL_REQUIRED",
                inbox_item_id,
            )
            yield CustomEvent(
                name="HITL_REQUIRED",
                value={
                    "threadId": thread_id,
                    "inboxItemId": inbox_item_id,
                    "questionText": clarification_text,
                },
            )
        elif (
            detected_confidence is not None
            and detected_confidence < self._classification_threshold
        ):
            # Legacy fallback for edge case where classify_and_file
            # is called at low confidence
            logger.info(
                "Low-confidence detected (%.2f < %.2f), emitting HITL_REQUIRED",
                detected_confidence,
                self._classification_threshold,
            )
            yield CustomEvent(
                name="HITL_REQUIRED",
                value={"threadId": thread_id},
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
            # Prefer thread_id from kwargs (caller), fall back to thread.id
            if "thread_id" not in kwargs and thread and hasattr(thread, "id"):
                kwargs["thread_id"] = str(thread.id)
            return ResponseStream(self._stream_updates(messages, thread, **kwargs))
        # Non-streaming: create a workflow and run it
        workflow = self._create_workflow()
        return workflow.run(message=messages)

    def get_new_thread(self, **kwargs: Any) -> AgentThread:
        """Create a new conversation thread."""
        return AgentThread(**kwargs)


def create_capture_workflow(
    orchestrator: Agent,
    classifier: Agent,
    classification_threshold: float = 0.6,
) -> AGUIWorkflowAdapter:
    """Build the AG-UI compatible adapter for the capture pipeline.

    The workflow routes: Orchestrator -> Classifier.
    Both agents run in autonomous mode. HITL detection happens
    post-classification by inspecting confidence in tool results.
    A fresh WorkflowAgent is created per request to avoid state leakage.
    """
    return AGUIWorkflowAdapter(
        orchestrator,
        classifier,
        name="SecondBrainPipeline",
        classification_threshold=classification_threshold,
    )
