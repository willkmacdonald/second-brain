"""HandoffBuilder workflow wiring for the capture pipeline.

Includes an AG-UI adapter that wraps Workflow for AG-UI endpoint compatibility.
Phase 4 additions: HITL support (low-confidence detection + respond endpoint),
AG-UI step events (StepStarted/StepFinished on agent transitions), and
Orchestrator echo filtering.

Phase 04.3-05: Classifier text buffering (suppress chain-of-thought reasoning,
yield only tool result lines) and misunderstood detection via request_info data
and function_call/function_result content inspection.
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
    Content,
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

# Regex to extract (inbox_doc_id, question_text) from request_misunderstood output
_MISUNDERSTOOD_RE = re.compile(
    r"Misunderstood\s*→\s*([a-f0-9\-]+)\s*\|\s*(.+)", re.DOTALL
)

# Combined regex matching any known Classifier tool result line.
# Used to extract the clean tool result from the Classifier text buffer,
# suppressing all chain-of-thought reasoning tokens.
_TOOL_RESULT_RE = re.compile(
    r"("
    r"Filed\s*(?:\(needs review\)\s*)?→\s*\w+\s*\(\d+\.\d+\)"
    r"|Misunderstood\s*→\s*[a-f0-9\-]+\s*\|.+"
    r"|Clarification\s*→\s*[a-f0-9\-]+\s*\|.+"
    r")",
    re.DOTALL,
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

        Only the Orchestrator runs in autonomous mode. The Classifier is
        NOT autonomous so that when it calls request_clarification, the
        framework emits a request_info event and the workflow pauses for
        HITL. For high-confidence cases the Classifier calls classify_and_file,
        produces its response, and the workflow completes normally.
        """
        return (
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
    def _is_classifier_text(update: AgentResponseUpdate) -> bool:
        """Check if an update is text-only content from the Classifier.

        Returns True when the update's author_name matches 'Classifier'
        (case-insensitive) and ALL content items are of type 'text'.
        This is used to buffer Classifier chain-of-thought reasoning
        and suppress it from the SSE stream.
        """
        if (
            update.author_name
            and update.author_name.lower() == "classifier"
            and update.contents
        ):
            return all(getattr(c, "type", None) == "text" for c in update.contents)
        return False

    @staticmethod
    def _has_misunderstood_tool_call(update: AgentResponseUpdate) -> bool:
        """Check for request_misunderstood function_call/result.

        Returns True if any content item is a function_call or
        function_result with name 'request_misunderstood'. This is a
        reliable alternative to regex-based detection on streamed text,
        since tool return values are consumed internally by the LLM.
        """
        for content in update.contents or []:
            if getattr(content, "type", None) in (
                "function_call",
                "function_result",
            ) and getattr(content, "name", None) == "request_misunderstood":
                return True
        return False

    @staticmethod
    def _extract_misunderstood_from_content(
        update: AgentResponseUpdate,
    ) -> tuple[str, str] | None:
        """Extract misunderstood data from function_result content items.

        Looks for a function_result with name='request_misunderstood' and
        parses the result string using _MISUNDERSTOOD_RE.
        """
        for content in update.contents or []:
            if (
                getattr(content, "type", None) == "function_result"
                and getattr(content, "name", None) == "request_misunderstood"
            ):
                result_str = str(getattr(content, "result", "") or "")
                match = _MISUNDERSTOOD_RE.search(result_str)
                if match:
                    return (match.group(1), match.group(2))
        return None

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

    @staticmethod
    def _extract_misunderstood(text: str) -> tuple[str, str] | None:
        """Extract (inbox_item_id, question_text) from misunderstood output."""
        match = _MISUNDERSTOOD_RE.search(text)
        return (match.group(1), match.group(2)) if match else None

    def _run_detection_on_text(
        self,
        text: str,
        detected_misunderstood: tuple[str, str] | None,
        detected_clarification: tuple[str, str] | None,
        detected_confidence: float | None,
    ) -> tuple[
        tuple[str, str] | None,
        tuple[str, str] | None,
        float | None,
    ]:
        """Run misunderstood/clarification/confidence extraction on text.

        Returns updated (detected_misunderstood, detected_clarification,
        detected_confidence) tuple.
        """
        if detected_misunderstood is None:
            mis = self._extract_misunderstood(text)
            if mis is not None:
                detected_misunderstood = mis
        if detected_misunderstood is None and detected_clarification is None:
            clar = self._extract_clarification(text)
            if clar is not None:
                detected_clarification = clar
            elif detected_confidence is None:
                conf = self._extract_confidence(text)
                if conf is not None:
                    detected_confidence = conf
        return detected_misunderstood, detected_clarification, detected_confidence

    def _extract_request_info_text(self, request_data: Any) -> str:
        """Extract all text from a request_info event's data payload.

        Broadens extraction beyond just .response.text or .text to also
        iterate over response content items (which may contain tool results
        in .text or .result fields).
        """
        parts: list[str] = []

        # Try .response.text
        if hasattr(request_data, "response"):
            resp = request_data.response
            if hasattr(resp, "text") and resp.text:
                parts.append(resp.text)
            # Also iterate response content items for tool results
            if hasattr(resp, "content"):
                for content in resp.content or []:
                    if hasattr(content, "text") and content.text:
                        parts.append(content.text)
                    if hasattr(content, "result") and content.result:
                        parts.append(str(content.result))
        elif hasattr(request_data, "text") and request_data.text:
            parts.append(request_data.text)

        return "\n".join(parts)

    async def _stream_updates(
        self,
        messages: str | Message | Sequence[str | Message] | None,
        thread: AgentThread | None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamItem]:
        """Stream updates from the workflow with step events and HITL detection.

        Yields a mix of AgentResponseUpdate (text/tool content) and AG-UI
        BaseEvent (StepStarted, StepFinished, Custom HITL_REQUIRED/MISUNDERSTOOD).

        Phase 04.3: Detects both misunderstood (MISUNDERSTOOD event) and
        clarification (HITL_REQUIRED event) patterns. Low-confidence items
        are silently filed as pending -- no HITL interruption.

        Echo filtering: Orchestrator text is suppressed. Classifier text is
        BUFFERED (chain-of-thought reasoning suppressed); only the clean tool
        result line (e.g., "Filed -> Admin (0.90)") is yielded at stream end.

        Misunderstood detection: Uses multiple strategies -- regex on buffered
        text, function_call/function_result content inspection, and request_info
        data extraction -- because tool return values may not appear in text.
        """
        workflow = self._create_workflow()
        converter = self._get_converter()
        thread_id = kwargs.get("thread_id") or str(_uuid.uuid4())
        current_agent: str | None = None
        response_id = str(_uuid.uuid4())
        detected_confidence: float | None = None
        detected_clarification: tuple[str, str] | None = None
        detected_misunderstood: tuple[str, str] | None = None
        saw_request_info = False
        # Buffer for Classifier text content -- accumulates all text deltas
        # from the Classifier so chain-of-thought reasoning is suppressed.
        # Only the clean tool result line is yielded after the stream ends.
        classifier_buffer: str = ""

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

                            # Check for misunderstood tool call/result in content
                            if self._has_misunderstood_tool_call(update):
                                logger.info(
                                    "Detected request_misunderstood tool call in update"
                                )
                            if detected_misunderstood is None:
                                mis = self._extract_misunderstood_from_content(update)
                                if mis is not None:
                                    detected_misunderstood = mis
                                    logger.info(
                                        "Extracted misunderstood from function_result"
                                    )

                            # Buffer Classifier text-only updates
                            if self._is_classifier_text(update):
                                classifier_buffer += update.text or ""
                                # Run detection on accumulated buffer
                                (
                                    detected_misunderstood,
                                    detected_clarification,
                                    detected_confidence,
                                ) = self._run_detection_on_text(
                                    classifier_buffer,
                                    detected_misunderstood,
                                    detected_clarification,
                                    detected_confidence,
                                )
                                logger.debug(
                                    "Buffering Classifier text (%d chars total)",
                                    len(classifier_buffer),
                                )
                                continue  # Do NOT yield -- buffered

                            # Non-Classifier, non-Orchestrator updates: detect and yield
                            if update.text:
                                (
                                    detected_misunderstood,
                                    detected_clarification,
                                    detected_confidence,
                                ) = self._run_detection_on_text(
                                    update.text,
                                    detected_misunderstood,
                                    detected_clarification,
                                    detected_confidence,
                                )
                            yield update

                    if event.type == "request_info":
                        logger.info("request_info received — workflow paused for HITL")
                        saw_request_info = True
                        # Extract text from the HandoffAgentUserRequest which
                        # wraps the agent's AgentResponse containing tool results
                        request_data = event.data
                        logger.info(
                            "request_info data type=%s",
                            type(request_data).__name__,
                        )
                        request_text = self._extract_request_info_text(request_data)

                        if request_text:
                            # Check misunderstood FIRST (higher priority)
                            if detected_misunderstood is None:
                                mis = self._extract_misunderstood(request_text)
                                if mis is not None:
                                    detected_misunderstood = mis
                                    logger.info(
                                        "Extracted misunderstood from request_info data"
                                    )

                            # Then check clarification
                            if (
                                detected_misunderstood is None
                                and detected_clarification is None
                            ):
                                clar = self._extract_clarification(request_text)
                                if clar is not None:
                                    detected_clarification = clar
                                    logger.info(
                                        "Extracted clarification from request_info data"
                                    )
                        continue

                    # Skip other workflow events (status, superstep, etc.)

                elif isinstance(event, AgentResponseUpdate):
                    if self._is_orchestrator_text(event):
                        logger.debug(
                            "Filtering direct Orchestrator echo: %s",
                            event.text[:80] if event.text else "",
                        )
                        continue

                    # Check for misunderstood tool call/result in content
                    if self._has_misunderstood_tool_call(event):
                        logger.info(
                            "Detected request_misunderstood tool call in direct update"
                        )
                    if detected_misunderstood is None:
                        mis = self._extract_misunderstood_from_content(event)
                        if mis is not None:
                            detected_misunderstood = mis
                            logger.info(
                                "Extracted misunderstood from direct function_result"
                            )

                    # Buffer Classifier text-only updates
                    if self._is_classifier_text(event):
                        classifier_buffer += event.text or ""
                        (
                            detected_misunderstood,
                            detected_clarification,
                            detected_confidence,
                        ) = self._run_detection_on_text(
                            classifier_buffer,
                            detected_misunderstood,
                            detected_clarification,
                            detected_confidence,
                        )
                        logger.debug(
                            "Buffering direct Classifier text (%d chars total)",
                            len(classifier_buffer),
                        )
                        continue  # Do NOT yield -- buffered

                    # Non-Classifier, non-Orchestrator updates: detect and yield
                    if event.text:
                        (
                            detected_misunderstood,
                            detected_clarification,
                            detected_confidence,
                        ) = self._run_detection_on_text(
                            event.text,
                            detected_misunderstood,
                            detected_clarification,
                            detected_confidence,
                        )
                    yield event

        except Exception as exc:
            logger.warning("Workflow stream error: %s", exc)

        # Final step finished for any open step
        if current_agent:
            yield StepFinishedEvent(step_name=current_agent)

        # Flush Classifier buffer: extract and yield only the clean tool result
        if classifier_buffer:
            # Run final detection on the complete buffer
            detected_misunderstood, detected_clarification, detected_confidence = (
                self._run_detection_on_text(
                    classifier_buffer,
                    detected_misunderstood,
                    detected_clarification,
                    detected_confidence,
                )
            )
            # Extract tool result line from buffer
            tool_match = _TOOL_RESULT_RE.search(classifier_buffer)
            if tool_match:
                clean_result = tool_match.group(1).strip()
                logger.info(
                    "Yielding clean Classifier tool result: %s", clean_result[:80]
                )
                yield AgentResponseUpdate(
                    contents=[Content.from_text(clean_result)],
                    author_name="Classifier",
                    response_id=response_id,
                )
            else:
                logger.debug(
                    "Classifier buffer (%d chars) contained no tool result pattern",
                    len(classifier_buffer),
                )

        # After workflow completes: emit custom events based on detection
        if detected_misunderstood is not None:
            inbox_item_id, question_text = detected_misunderstood
            logger.info(
                "Misunderstood detected for inbox item %s, emitting MISUNDERSTOOD",
                inbox_item_id,
            )
            yield CustomEvent(
                name="MISUNDERSTOOD",
                value={
                    "threadId": thread_id,
                    "inboxItemId": inbox_item_id,
                    "questionText": question_text,
                },
            )
        elif detected_clarification is not None:
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
        elif saw_request_info:
            # request_info fired but neither misunderstood nor clarification
            # regex matched — emit HITL_REQUIRED with threadId only.
            logger.info(
                "request_info without known pattern — emitting generic HITL_REQUIRED"
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
    Only the Orchestrator runs in autonomous mode; the Classifier pauses
    on request_clarification for HITL. HITL detection happens by inspecting
    clarification text in tool results. A fresh Workflow is created per
    request to avoid state leakage.
    """
    return AGUIWorkflowAdapter(
        orchestrator,
        classifier,
        name="SecondBrainPipeline",
        classification_threshold=classification_threshold,
    )
