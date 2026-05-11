"""EvalAgentInvoker -- temporary facade hiding RC/GA call shape during migration.

Introduced in Phase 24 task group 23.2 (plan 24-12) when the Admin agent
migrates to GA. The RC implementation is deleted at end of 23.3 (plan 24-18)
when no caller remains.

D-07 EXPLICIT JUSTIFICATION (per EVAL-INVENTORY.md round-15):

1. Framework primitive considered: Agent.run(messages) direct.
2. What custom code provides: translation between eval cases
   (input + expected label) and agent.run() call shape, AND adapting
   the response back to the eval runner's existing per-case dict format.
3. Why not middleware/context provider/tool/configuration: it CAN be
   solved by either, but during the migration window we have BOTH RC and
   GA call shapes alive (classifier on RC until plans 24-13..24-17,
   admin on GA after plans 24-09..24-11). The facade hides that split
   for one migration window.
4. Permanent or temporary: temporary. Deletion trigger: end of plan 24-18,
   when no RCEvalAgentInvoker caller remains.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from agent_framework import ChatOptions

if TYPE_CHECKING:
    from agent_framework import Agent
    from agent_framework.azure import AzureAIAgentClient

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


class RCEvalAgentInvoker:
    """RC implementation -- temporary, deleted in plan 24-18.

    Body lifted from eval/runner.py:133-149 (classifier) and 278-294 (admin)
    verbatim. Used while the corresponding agent has not yet migrated to GA.
    After 24-18, the classifier is GA and this class has no callers.

    Imports of RC-only types (Message, ChatOptions with tool_choice dict)
    happen inside the methods so this module does not place a top-level
    dependency on RC types at import time.
    """

    def __init__(
        self,
        classifier_client: AzureAIAgentClient,
        admin_client: AzureAIAgentClient,
    ) -> None:
        self._classifier_client = classifier_client
        self._admin_client = admin_client

    async def invoke_classifier(
        self,
        input_text: str,
        tools_instance: EvalClassifierTools,
    ) -> None:
        from agent_framework import ChatOptions as RCChatOptions
        from agent_framework import Message

        messages = [Message(role="user", text=input_text)]
        options = RCChatOptions(
            tools=[tools_instance.file_capture],
            tool_choice={
                "mode": "required",
                "required_function_name": "file_capture",
            },
        )
        await self._classifier_client.get_response(messages=messages, options=options)

    async def invoke_admin(
        self,
        input_text: str,
        tools_instance: DryRunAdminTools,
        routing_context: str,
    ) -> None:
        from agent_framework import ChatOptions as RCChatOptions
        from agent_framework import Message

        prompt = f"{routing_context}\n\n---\n{input_text}"
        messages = [Message(role="user", text=prompt)]
        options = RCChatOptions(
            tools=[
                tools_instance.add_errand_items,
                tools_instance.add_task_items,
                tools_instance.get_routing_context,
            ],
        )
        await self._admin_client.get_response(messages=messages, options=options)


class _MigrationHybridInvoker:
    """Hybrid composition for the 23.2-23.3 migration window.

    Routes invoke_classifier -> RC implementation (classifier still RC until
    plans 24-13..24-17) and invoke_admin -> GA implementation (admin migrated
    in plans 24-09..24-11).

    Deletion trigger: end of plan 24-18 (cleanup commit), once both agents
    are GA and the call-site can construct a single GAEvalAgentInvoker. The
    leading underscore signals deletion-trigger-aligned private API, matching
    the RC/GA siblings.
    """

    def __init__(
        self,
        rc_invoker: RCEvalAgentInvoker,
        ga_invoker: GAEvalAgentInvoker,
    ) -> None:
        self._rc = rc_invoker
        self._ga = ga_invoker

    async def invoke_classifier(
        self,
        input_text: str,
        tools_instance: EvalClassifierTools,
    ) -> None:
        await self._rc.invoke_classifier(input_text, tools_instance)

    async def invoke_admin(
        self,
        input_text: str,
        tools_instance: DryRunAdminTools,
        routing_context: str,
    ) -> None:
        await self._ga.invoke_admin(input_text, tools_instance, routing_context)
