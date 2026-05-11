"""Unit tests for Admin Agent background processing.

Tests process_admin_capture against the GA Agent.run() shape introduced
in Phase 24 plan 24-11:
- Replaces RC AzureAIAgentClient.get_response with GA Agent.run
- Tool detection is post-hoc via response.messages (role='tool' walk)
- D-09 bounded retry with directive prompt preserved

Validates status transitions, delete-on-success, error handling,
timeout behavior, and the bounded retry semantics.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from second_brain.processing.admin_handoff import (
    process_admin_capture,
    process_admin_captures_batch,
)


def _tool_content(name: str) -> MagicMock:
    """Construct a Content block representing a tool call/result.

    Per FOUNDRY-PROBE-FINDINGS.md probe 2 (tool_call_extraction.json),
    tool-result message contents have a `name` (or `function_name`) field
    identifying the function that was called. _output_tool_called walks
    response.messages for role='tool' entries and reads this field.
    """
    content = MagicMock()
    content.name = name
    return content


def _tool_message(tool_name: str) -> MagicMock:
    """Construct a Message with role='tool' carrying one Content block."""
    msg = MagicMock()
    msg.role = "tool"
    msg.contents = [_tool_content(tool_name)]
    msg.text = ""
    return msg


def _assistant_message(text: str = "") -> MagicMock:
    """Construct a Message with role='assistant' and the given text."""
    msg = MagicMock()
    msg.role = "assistant"
    msg.contents = []
    msg.text = text
    return msg


def _agent_response(text: str, tool_names: list[str] | None = None) -> MagicMock:
    """Construct an AgentResponse-shaped mock.

    Per probe 2: response.text is the final assistant answer; response.messages
    is the full conversation walk including role='tool' entries for each tool
    invocation. We mirror that shape so _output_tool_called can detect calls.
    """
    response = MagicMock()
    response.text = text
    messages: list[MagicMock] = [_assistant_message("")]
    for name in tool_names or []:
        messages.append(_tool_message(name))
    messages.append(_assistant_message(text))
    response.messages = messages
    return response


@pytest.fixture
def mock_admin_agent():
    """Mock GA Agent for non-streaming calls.

    By default, returns a response indicating add_errand_items was called
    (an output tool). Individual tests override this to simulate different
    tool-call sequences (no-tool-call, intermediate-only, retry-succeeds).
    """
    agent = AsyncMock()

    async def _default_run(*args, **kwargs):
        return _agent_response(
            text="Added 2 items: 1 to jewel, 1 to pet_store",
            tool_names=["add_errand_items"],
        )

    agent.run = AsyncMock(side_effect=_default_run)
    return agent


def _inbox_doc(status: str | None = None) -> dict:
    """Return a fresh mutable inbox document dict."""
    return {
        "id": "test-inbox-id",
        "userId": "will",
        "rawText": "need cat litter and milk",
        "adminProcessingStatus": status,
    }


@pytest.fixture(autouse=True)
def _setup_inbox_read(mock_cosmos_manager):
    """Configure Inbox container read_item to return mutable dicts by default."""
    container = mock_cosmos_manager.get_container("Inbox")
    container.read_item.side_effect = lambda **kwargs: _inbox_doc()


# ---------------------------------------------------------------------------
# Tests: success path
# ---------------------------------------------------------------------------


class TestProcessAdminCaptureSuccess:
    """Tests for the happy path."""

    async def test_sets_pending_then_deletes_on_success(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """Status transitions: None -> pending, then delete on success."""
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter and milk",
        )

        container = mock_cosmos_manager.get_container("Inbox")

        # Only ONE upsert: the "pending" status
        upsert_calls = container.upsert_item.call_args_list
        assert len(upsert_calls) == 1
        first_body = upsert_calls[0].kwargs.get("body") or upsert_calls[0][1].get(
            "body"
        )
        assert first_body["adminProcessingStatus"] == "pending"

        # delete_item called once for the processed inbox item
        container.delete_item.assert_called_once_with(
            item="test-inbox-id", partition_key="will"
        )

    async def test_delete_not_found_is_non_fatal(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """CosmosResourceNotFoundError on delete does not raise."""
        container = mock_cosmos_manager.get_container("Inbox")
        container.delete_item = AsyncMock(
            side_effect=CosmosResourceNotFoundError(
                status_code=404, message="Not found"
            )
        )

        # Should NOT raise
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter and milk",
        )

    async def test_delete_failure_is_non_fatal(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """Generic Exception on delete does not raise."""
        container = mock_cosmos_manager.get_container("Inbox")
        container.delete_item = AsyncMock(side_effect=Exception("Cosmos timeout"))

        # Should NOT raise
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter and milk",
        )

    async def test_calls_admin_agent_with_enriched_text(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """Admin Agent receives routing context + user's capture text."""
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter and milk",
        )

        mock_admin_agent.run.assert_called_once()
        # First positional arg is the enriched_text string
        call_args = mock_admin_agent.run.call_args
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("input")
        # Enriched text includes routing context header and the raw text
        assert "DESTINATIONS:" in text
        assert "need cat litter and milk" in text

    async def test_passes_tool_choice_required(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """Admin Agent receives ChatOptions with tool_choice='required' per D-08."""
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need milk",
        )

        call_kwargs = mock_admin_agent.run.call_args.kwargs
        options = call_kwargs.get("options")
        assert options is not None
        # ChatOptions is a dict-subclass in agent_framework; access via key
        assert options["tool_choice"] == "required"


# ---------------------------------------------------------------------------
# Tests: failure path
# ---------------------------------------------------------------------------


class TestProcessAdminCaptureFailure:
    """Tests for error handling paths."""

    async def test_agent_error_sets_status_to_failed(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """When Admin Agent raises, status transitions to 'failed'."""
        mock_admin_agent.run.side_effect = RuntimeError("Foundry timeout")

        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter",
        )

        container = mock_cosmos_manager.get_container("Inbox")
        upsert_calls = container.upsert_item.call_args_list
        # Should have pending upsert and failed upsert
        assert len(upsert_calls) >= 2
        last_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get(
            "body"
        )
        assert last_body["adminProcessingStatus"] == "failed"

    async def test_agent_error_does_not_raise(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """process_admin_capture never raises -- safe for fire-and-forget."""
        mock_admin_agent.run.side_effect = RuntimeError("Foundry timeout")

        # Should NOT raise
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter",
        )

    async def test_cosmos_read_failure_returns_early(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """If initial read fails, function returns without calling Admin Agent."""
        container = mock_cosmos_manager.get_container("Inbox")
        container.read_item.side_effect = Exception("Cosmos 404")

        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="nonexistent-id",
            raw_text="need cat litter",
        )

        # Admin Agent should NOT be called
        mock_admin_agent.run.assert_not_called()

    async def test_failed_status_update_does_not_raise(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """If updating status to 'failed' itself fails, no exception propagates."""
        mock_admin_agent.run.side_effect = RuntimeError("Agent error")
        container = mock_cosmos_manager.get_container("Inbox")

        # First read succeeds (for pending), second read raises (for failed update)
        call_count = 0

        async def read_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return _inbox_doc()
            raise Exception("Cosmos write error")

        container.read_item = AsyncMock(side_effect=read_side_effect)

        # Should NOT raise even when failed-status update fails
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-id",
            raw_text="need cat litter",
        )


# ---------------------------------------------------------------------------
# Tests: no tool call (agent responds without invoking any tool)
# ---------------------------------------------------------------------------


class TestProcessAdminCaptureNoToolCall:
    """Tests for the scenario where the agent responds without calling any tool.

    With tool_choice='required' (D-08), the model is forced to call SOME tool,
    so this path is mostly defensive. Post-hoc detection per probe 2 means a
    response with zero role='tool' messages classifies as no_tool_call.
    """

    async def test_no_tool_call_marks_failed_not_deleted(self, mock_cosmos_manager):
        """When agent responds without calling tool, inbox item is NOT deleted."""
        agent = AsyncMock()
        agent.run = AsyncMock(
            side_effect=lambda *a, **kw: _agent_response(
                text="I've noted your request.", tool_names=[]
            )
        )

        await process_admin_capture(
            admin_agent=agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="pick up screws at the hardware store",
        )

        container = mock_cosmos_manager.get_container("Inbox")

        # Inbox item should NOT be deleted
        container.delete_item.assert_not_called()

        # Should have "pending" upsert then "failed" upsert
        upsert_calls = container.upsert_item.call_args_list
        assert len(upsert_calls) == 2
        first_body = upsert_calls[0].kwargs.get("body") or upsert_calls[0][1].get(
            "body"
        )
        assert first_body["adminProcessingStatus"] == "pending"
        last_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get(
            "body"
        )
        assert last_body["adminProcessingStatus"] == "failed"

    async def test_no_tool_call_does_not_raise(self, mock_cosmos_manager):
        """No-tool-call path never raises -- safe for fire-and-forget."""
        agent = AsyncMock()
        agent.run = AsyncMock(
            side_effect=lambda *a, **kw: _agent_response(
                text="I don't understand this request.", tool_names=[]
            )
        )

        # Should NOT raise
        await process_admin_capture(
            admin_agent=agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="random text",
        )

    async def test_output_tool_called_deletes_inbox_item(self, mock_cosmos_manager):
        """Output tool called -- inbox item is deleted.

        We trust that if the agent invoked an output tool (add_errand_items,
        add_task_items, etc.), it completed its job.
        """
        agent = AsyncMock()
        agent.run = AsyncMock(
            side_effect=lambda *a, **kw: _agent_response(
                text="Done processing your capture.",
                tool_names=["add_task_items"],
            )
        )

        await process_admin_capture(
            admin_agent=agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="book an appointment with an orthopedist",
        )

        container = mock_cosmos_manager.get_container("Inbox")

        # Inbox item SHOULD be deleted since output tool was called
        container.delete_item.assert_called_once()

    async def test_intermediate_tool_only_retries_then_marks_failed(
        self, mock_cosmos_manager
    ):
        """Agent calls fetch_recipe_url but not add_errand_items -- retries once.

        D-09 bounded retry: if neither add_errand_items nor add_task_items ran
        on the initial call, retry once with a directive prompt. If retry also
        fails to call an output tool, mark as failed.
        """
        agent = AsyncMock()

        async def _only_fetch(*args, **kwargs):
            # Both initial and retry only call fetch_recipe_url
            return _agent_response(
                text="Here's the recipe for Chicken Tikka Masala...",
                tool_names=["fetch_recipe_url"],
            )

        agent.run = AsyncMock(side_effect=_only_fetch)

        await process_admin_capture(
            admin_agent=agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="https://www.allrecipes.com/recipe/chicken-tikka-masala/",
        )

        container = mock_cosmos_manager.get_container("Inbox")

        # Agent called twice (initial + bounded retry per D-09)
        assert agent.run.call_count == 2

        # Retry prompt should contain the directive nudge
        retry_call = agent.run.call_args_list[1]
        retry_text = (
            retry_call.args[0] if retry_call.args else retry_call.kwargs.get("input")
        )
        assert "MUST call the appropriate tool" in retry_text

        # Inbox item should NOT be deleted -- retry also failed
        container.delete_item.assert_not_called()

        # Should be marked as failed
        upsert_calls = container.upsert_item.call_args_list
        last_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get(
            "body"
        )
        assert last_body["adminProcessingStatus"] == "failed"

    async def test_intermediate_tool_retry_succeeds(self, mock_cosmos_manager):
        """Agent calls fetch_recipe_url, retry succeeds with add_errand_items.

        First call: only fetch_recipe_url. Retry: add_errand_items called.
        Inbox item should be deleted (success).
        """
        agent = AsyncMock()
        call_count = 0

        async def _fetch_then_add(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: only intermediate tool
                return _agent_response(
                    text="Here's the recipe...",
                    tool_names=["fetch_recipe_url"],
                )
            # Retry: output tool called
            return _agent_response(
                text="Added 12 items: 8 to jewel, 4 to agora",
                tool_names=["add_errand_items"],
            )

        agent.run = AsyncMock(side_effect=_fetch_then_add)

        await process_admin_capture(
            admin_agent=agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="https://www.allrecipes.com/recipe/chicken-tikka-masala/",
        )

        container = mock_cosmos_manager.get_container("Inbox")

        # Inbox item SHOULD be deleted -- retry succeeded
        container.delete_item.assert_called_once()

    async def test_tool_call_still_deletes(self, mock_admin_agent, mock_cosmos_manager):
        """When agent DOES call an output tool, inbox item is deleted."""
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need milk and eggs",
        )

        container = mock_cosmos_manager.get_container("Inbox")
        container.delete_item.assert_called_once_with(
            item="test-inbox-id", partition_key="will"
        )


# ---------------------------------------------------------------------------
# Tests: timeout
# ---------------------------------------------------------------------------


class TestProcessAdminCaptureTimeout:
    """Tests for timeout behavior."""

    async def test_timeout_sets_status_to_failed(self, mock_cosmos_manager):
        """60-second timeout triggers failed status."""
        slow_agent = AsyncMock()

        async def slow_run(*args, **kwargs):
            await asyncio.sleep(120)  # Simulate very slow response

        slow_agent.run = slow_run

        # Patch asyncio.timeout to use a very short timeout for testing
        with patch(
            "second_brain.processing.admin_handoff.asyncio.timeout",
            return_value=asyncio.timeout(0.01),
        ):
            await process_admin_capture(
                admin_agent=slow_agent,
                cosmos_manager=mock_cosmos_manager,
                inbox_item_id="test-inbox-id",
                raw_text="need cat litter",
            )

        container = mock_cosmos_manager.get_container("Inbox")
        upsert_calls = container.upsert_item.call_args_list
        last_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get(
            "body"
        )
        assert last_body["adminProcessingStatus"] == "failed"


# ---------------------------------------------------------------------------
# Tests: batch processing
# ---------------------------------------------------------------------------


class TestProcessAdminCapturesBatch:
    """Tests for process_admin_captures_batch."""

    async def test_batch_calls_process_for_each_item(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """Given 2 admin items, admin_agent.run is called twice."""
        admin_items = [
            {"inbox_item_id": "item-1", "raw_text": "need milk"},
            {"inbox_item_id": "item-2", "raw_text": "buy eggs"},
        ]

        await process_admin_captures_batch(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            admin_items=admin_items,
        )

        assert mock_admin_agent.run.call_count == 2

    async def test_batch_one_failure_does_not_block_second(self, mock_cosmos_manager):
        """First item fails, second still processes successfully."""
        agent = AsyncMock()

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Foundry timeout")
            # Simulate output tool invocation for the successful call
            return _agent_response(
                text="Processed items",
                tool_names=["add_errand_items"],
            )

        agent.run = AsyncMock(side_effect=side_effect)

        # Need separate docs per item -- set up read_item to return fresh docs
        container = mock_cosmos_manager.get_container("Inbox")
        container.read_item.side_effect = lambda **kwargs: _inbox_doc()

        admin_items = [
            {"inbox_item_id": "item-fail", "raw_text": "fail this"},
            {"inbox_item_id": "item-ok", "raw_text": "this works"},
        ]

        await process_admin_captures_batch(
            admin_agent=agent,
            cosmos_manager=mock_cosmos_manager,
            admin_items=admin_items,
        )

        # Both items were attempted
        assert agent.run.call_count == 2

        # Failed item gets "failed" upsert; successful item gets delete
        upsert_calls = container.upsert_item.call_args_list
        statuses = [
            (c.kwargs.get("body") or c[1].get("body"))["adminProcessingStatus"]
            for c in upsert_calls
        ]
        assert "failed" in statuses
        # "processed" should NOT be in upserts -- success path deletes
        assert "processed" not in statuses

        # delete_item called at least once (for the successful item)
        assert container.delete_item.call_count >= 1

    async def test_batch_empty_list_is_noop(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """Empty admin_items list returns without calling admin_agent."""
        await process_admin_captures_batch(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            admin_items=[],
        )

        mock_admin_agent.run.assert_not_called()
