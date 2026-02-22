"""HandoffBuilder workflow wiring for the capture pipeline."""

from __future__ import annotations

from agent_framework import Agent, WorkflowAgent
from agent_framework.orchestrations import HandoffBuilder


def create_capture_workflow(
    orchestrator: Agent,
    classifier: Agent,
) -> WorkflowAgent:
    """Build the handoff workflow and return a WorkflowAgent for AG-UI.

    The workflow routes: Orchestrator -> Classifier.
    Orchestrator runs in autonomous mode (always hands off, never waits).
    Classifier is interactive (can pause for user input in Phase 4 HITL).
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
