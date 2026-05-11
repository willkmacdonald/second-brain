"""EvalAgentInvoker -- GA-only eval-side agent invocation facade.

Phase 24 plan 24-12 introduced this facade as a temporary RC/GA migration
seam. Plan 24-18 (this commit) DELETES the temporary parts now that the
classifier is on GA:

- RCEvalAgentInvoker (the RC implementation lifted verbatim from
  eval/runner.py:133-149 + 278-294)
- _MigrationHybridInvoker (the classifier->RC, admin->GA composition class)
- The TYPE_CHECKING import of the legacy RC client class that supported
  the RC implementation's type hints

What remains: the EvalAgentInvoker Protocol + the single GA implementation.
The Protocol stays because the eval runner types its parameter against it
and the test suite mocks it directly. The single concrete class is
GAEvalAgentInvoker; rename to a plain ``EvalAgentInvoker`` (drop the GA
prefix and the Protocol) is deferred -- diff stays small here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from agent_framework import ChatOptions

if TYPE_CHECKING:
    from agent_framework import Agent

    from second_brain.eval.dry_run_tools import (
        DryRunAdminTools,
        EvalClassifierTools,
    )


class EvalAgentInvoker(Protocol):
    """Protocol for eval-side agent invocation.

    Implementations capture predictions via side effects on the
    tools_instance (last_bucket / last_confidence for classifier;
    captured_destinations / captured_tasks for admin). The runner
    reads side effects, not the response.
    """

    async def invoke_classifier(
        self,
        input_text: str,
        tools_instance: EvalClassifierTools,
    ) -> None: ...

    async def invoke_admin(
        self,
        input_text: str,
        tools_instance: DryRunAdminTools,
        routing_context: str,
    ) -> None: ...


class GAEvalAgentInvoker:
    """GA implementation -- calls Agent.run(...).

    Per probe tool_call_extraction.json: tools registered via `tools=` kwarg
    on agent.run(). Side effects already captured on tools_instance attributes
    when the model invokes the stub tools.

    Per-case tools (EvalClassifierTools / DryRunAdminTools) are passed via
    Agent.run(tools=[...]) rather than registered at Agent construction time,
    because each eval case uses a fresh tool instance whose state captures
    that case's prediction (case-scoped, not lifespan-scoped).
    """

    def __init__(self, classifier_agent: Agent, admin_agent: Agent) -> None:
        self._classifier = classifier_agent
        self._admin = admin_agent

    async def invoke_classifier(
        self,
        input_text: str,
        tools_instance: EvalClassifierTools,
    ) -> None:
        await self._classifier.run(
            input_text,
            tools=[tools_instance.file_capture],
            options=ChatOptions(tool_choice="required"),
        )

    async def invoke_admin(
        self,
        input_text: str,
        tools_instance: DryRunAdminTools,
        routing_context: str,
    ) -> None:
        prompt = f"{routing_context}\n\n---\n{input_text}"
        await self._admin.run(
            prompt,
            tools=[
                tools_instance.add_errand_items,
                tools_instance.add_task_items,
                tools_instance.get_routing_context,
            ],
            # tool_choice not set -- admin eval contract uses default (auto)
            # per EVAL-INVENTORY.md call site 2 behavior contract.
        )
