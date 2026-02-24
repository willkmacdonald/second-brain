"""HandoffBuilder workflow wiring for the capture pipeline.

Includes an AG-UI adapter that wraps Workflow for AG-UI endpoint compatibility.

Outcome detection: The adapter detects which classification tool the Classifier
called by inspecting function_call.name in the event stream. This replaces the
previous regex-based approach that tried to parse opaque return strings.

Three outcomes:
  - classify_and_file → normal completion (onComplete on client)
  - request_misunderstood → MISUNDERSTOOD custom event (conversation mode)
  - mark_as_junk → normal completion

Classifier text buffering suppresses chain-of-thought reasoning; only a clean
result string (constructed from the tool's arguments) is yielded to the client.
"""

from __future__ import annotations

import json
import logging
import re
import uuid as _uuid
from collections.abc import AsyncIterable, Mapping, Sequence
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
StreamItem = AgentResponseUpdate | BaseEvent

# Known classification tool names.
_CLASSIFICATION_TOOLS = frozenset(
    {"classify_and_file", "request_misunderstood", "mark_as_junk"}
)

# Regex to extract the inbox_item_id UUID from a request_misunderstood
# function_result. The UUID is generated inside the tool and only appears
# in the return string — it's not in the function_call arguments.
_UUID_RE = re.compile(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})")


class AGUIWorkflowAdapter:
    """Adapter that wraps a workflow definition for AG-UI endpoint compatibility.

    Creates a fresh Workflow per request to avoid state leaking
    between requests (e.g., conversation_id accumulation).

    Emits AG-UI StepStarted/StepFinished events, filters Orchestrator echo,
    buffers Classifier chain-of-thought text, and detects classification
    outcomes via function_call.name inspection.
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
        self._converter_agent: WorkflowAgent | None = None

    def _create_workflow(self) -> Workflow:
        """Create a fresh Workflow for each request.

        Returns the raw Workflow (not WorkflowAgent) so that all event
        types are visible in the stream — including executor_invoked and
        executor_completed needed for step events.

        Only the Orchestrator runs in autonomous mode. The Classifier is
        NOT autonomous so the framework emits request_info after each
        Classifier response (we ignore this — outcome detection uses
        function_call.name instead).
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

        Used to buffer chain-of-thought reasoning and suppress it from
        the SSE stream.
        """
        if (
            update.author_name
            and update.author_name.lower() == "classifier"
            and update.contents
        ):
            return all(getattr(c, "type", None) == "text" for c in update.contents)
        return False

    @staticmethod
    def _extract_function_call_info(
        update: AgentResponseUpdate,
    ) -> tuple[str, dict[str, Any]] | None:
        """Extract classification tool name and parsed arguments.

        Scans update.contents for a function_call whose name is a known
        classification tool. Returns (tool_name, parsed_args) or None.
        """
        for content in update.contents or []:
            if getattr(content, "type", None) != "function_call":
                continue
            name = getattr(content, "name", None)
            if name not in _CLASSIFICATION_TOOLS:
                continue
            args_raw = getattr(content, "arguments", None)
            args: dict[str, Any] = {}
            if args_raw:
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse function_call arguments")
                elif isinstance(args_raw, Mapping):
                    args = dict(args_raw)
            return (name, args)
        return None

    @staticmethod
    def _extract_inbox_id_from_result(
        update: AgentResponseUpdate,
    ) -> str | None:
        """Extract UUID from a function_result content item.

        Used only after detecting request_misunderstood via function_call.name
        to retrieve the inbox_doc_id generated inside the tool.
        """
        for content in update.contents or []:
            if getattr(content, "type", None) == "function_result":
                result_str = str(getattr(content, "result", "") or "")
                match = _UUID_RE.search(result_str)
                if match:
                    return match.group(1)
        return None

    def _process_update(
        self,
        update: AgentResponseUpdate,
        detected_tool: str | None,
        detected_tool_args: dict[str, Any],
        misunderstood_inbox_id: str | None,
        classified_inbox_id: str | None,
    ) -> tuple[str | None, dict[str, Any], str | None, str | None]:
        """Run function_call detection on an update.

        Returns updated (detected_tool, detected_tool_args,
        misunderstood_inbox_id, classified_inbox_id).
        """
        if detected_tool is None:
            fc = self._extract_function_call_info(update)
            if fc is not None:
                detected_tool, detected_tool_args = fc
                logger.info("Detected classification tool: %s", detected_tool)

        if detected_tool == "request_misunderstood" and misunderstood_inbox_id is None:
            iid = self._extract_inbox_id_from_result(update)
            if iid is not None:
                misunderstood_inbox_id = iid
                logger.info("Extracted misunderstood inbox_id: %s", iid)

        if detected_tool == "classify_and_file" and classified_inbox_id is None:
            iid = self._extract_inbox_id_from_result(update)
            if iid is not None:
                classified_inbox_id = iid
                logger.info("Extracted classified inbox_id: %s", iid)

        return detected_tool, detected_tool_args, misunderstood_inbox_id, classified_inbox_id

    async def _stream_updates(
        self,
        messages: str | Message | Sequence[str | Message] | None,
        thread: AgentThread | None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamItem]:
        """Stream updates from the workflow with step events and outcome detection.

        Yields a mix of AgentResponseUpdate (text/tool content) and AG-UI
        BaseEvent (StepStarted, StepFinished, Custom MISUNDERSTOOD).

        Outcome detection: Inspects function_call.name to determine which
        classification tool the Classifier invoked. No regex on return strings.

        Echo filtering: Orchestrator text suppressed. Classifier text buffered
        (chain-of-thought suppressed); a clean result string constructed from
        the tool's arguments is yielded at stream end.
        """
        workflow = self._create_workflow()
        converter = self._get_converter()
        thread_id = kwargs.get("thread_id") or str(_uuid.uuid4())
        current_agent: str | None = None
        response_id = str(_uuid.uuid4())

        # Outcome tracking via function_call.name
        detected_tool: str | None = None
        detected_tool_args: dict[str, Any] = {}
        misunderstood_inbox_id: str | None = None
        classified_inbox_id: str | None = None

        # Classifier text buffer for chain-of-thought suppression
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
                                continue

                            # Detect classification tool
                            result = self._process_update(
                                update,
                                detected_tool,
                                detected_tool_args,
                                misunderstood_inbox_id,
                                classified_inbox_id,
                            )
                            detected_tool = result[0]
                            detected_tool_args = result[1]
                            misunderstood_inbox_id = result[2]
                            classified_inbox_id = result[3]

                            # Buffer Classifier text-only updates
                            if self._is_classifier_text(update):
                                classifier_buffer += update.text or ""
                                continue

                            yield update

                    if event.type == "request_info":
                        # Non-autonomous Classifier always fires request_info.
                        # Outcome detection uses function_call.name — ignore.
                        logger.debug("request_info received (non-autonomous pause)")
                        continue

                elif isinstance(event, AgentResponseUpdate):
                    if self._is_orchestrator_text(event):
                        continue

                    # Detect classification tool from function_call
                    detected_tool, detected_tool_args, misunderstood_inbox_id, classified_inbox_id = (
                        self._process_update(
                            event,
                            detected_tool,
                            detected_tool_args,
                            misunderstood_inbox_id,
                            classified_inbox_id,
                        )
                    )

                    # Buffer Classifier text-only updates
                    if self._is_classifier_text(event):
                        classifier_buffer += event.text or ""
                        continue

                    yield event

        except Exception as exc:
            logger.warning("Workflow stream error: %s", exc)

        # Final step finished for any open step
        if current_agent:
            yield StepFinishedEvent(step_name=current_agent)

        # Flush Classifier buffer: construct clean result from tool args
        if classifier_buffer:
            clean_result: str | None = None
            if detected_tool == "classify_and_file":
                bucket = detected_tool_args.get("bucket", "?")
                confidence = detected_tool_args.get("confidence", 0.0)
                if confidence < self._classification_threshold:
                    clean_result = f"Filed (needs review) → {bucket} ({confidence:.2f})"
                else:
                    clean_result = f"Filed → {bucket} ({confidence:.2f})"
            elif detected_tool == "request_misunderstood":
                clean_result = detected_tool_args.get("question_text", "")
            elif detected_tool == "mark_as_junk":
                clean_result = "Capture logged as unclassified"

            if clean_result:
                logger.info("Yielding constructed result: %s", clean_result[:80])
                yield AgentResponseUpdate(
                    contents=[Content.from_text(clean_result)],
                    author_name="Classifier",
                    response_id=response_id,
                )
            else:
                logger.debug(
                    "Classifier buffer (%d chars) — no tool detected",
                    len(classifier_buffer),
                )

        # Emit custom events based on detected tool
        if detected_tool == "request_misunderstood":
            question_text = detected_tool_args.get("question_text", "")
            inbox_item_id = misunderstood_inbox_id or ""
            if inbox_item_id:
                logger.info("Emitting MISUNDERSTOOD for inbox item %s", inbox_item_id)
                yield CustomEvent(
                    name="MISUNDERSTOOD",
                    value={
                        "threadId": thread_id,
                        "inboxItemId": inbox_item_id,
                        "questionText": question_text,
                    },
                )
            else:
                logger.warning(
                    "request_misunderstood detected but no inbox_item_id extracted"
                )
        elif detected_tool == "classify_and_file":
            logger.info("Classification completed via classify_and_file")
            if classified_inbox_id:
                yield CustomEvent(
                    name="CLASSIFIED",
                    value={
                        "inboxItemId": classified_inbox_id,
                        "bucket": detected_tool_args.get("bucket", ""),
                        "confidence": detected_tool_args.get("confidence", 0.0),
                    },
                )
        elif detected_tool == "mark_as_junk":
            logger.info("Classification completed via mark_as_junk")
        elif detected_tool is None:
            logger.warning(
                "Classifier stream ended without calling any classification tool"
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
            if "thread_id" not in kwargs and thread and hasattr(thread, "id"):
                kwargs["thread_id"] = str(thread.id)
            return ResponseStream(self._stream_updates(messages, thread, **kwargs))
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
    Only the Orchestrator runs in autonomous mode; the Classifier is
    non-autonomous. Classification outcomes are detected by inspecting
    function_call.name in the event stream.
    """
    return AGUIWorkflowAdapter(
        orchestrator,
        classifier,
        name="SecondBrainPipeline",
        classification_threshold=classification_threshold,
    )
