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


def _function_call(name: str, call_id: str) -> MagicMock:
    """function_call content (lives on role='assistant' messages).

    GA framework shape verified 2026-05-17 by local probe against deployed
    Foundry endpoint: the tool name is on the function_call Content (which
    appears on the prior assistant message). The function_result Content
    (which appears on the follow-up role='tool' message) has name=None and
    only carries the matching call_id + result/exception.
    """
    content = MagicMock()
    content.type = "function_call"
    content.name = name
    content.call_id = call_id
    content.arguments = "{}"
    return content


def _function_result(call_id: str, exception: str | None = None) -> MagicMock:
    """function_result content (lives on role='tool' messages).

    name is intentionally None to match the real GA shape — the name lives
    on the matching function_call in the prior assistant message.
    """
    content = MagicMock()
    content.type = "function_result"
    content.name = None
    content.call_id = call_id
    content.result = "" if exception is None else f"Error: {exception}"
    content.exception = exception
    return content


def _assistant_message(
    text: str = "",
    calls: list[tuple[str, str]] | None = None,
) -> MagicMock:
    """role='assistant' message. `calls` is a list of (name, call_id)
    tuples for function_call content blocks attached to this message.
    """
    msg = MagicMock()
    msg.role = "assistant"
    msg.text = text
    contents: list[MagicMock] = []
    if text:
        text_content = MagicMock()
        text_content.type = "text"
        text_content.name = None
        text_content.call_id = None
        contents.append(text_content)
    for name, call_id in calls or []:
        contents.append(_function_call(name, call_id))
    msg.contents = contents
    return msg


def _tool_message(
    call_ids: list[str], exceptions: list[str | None] | None = None
) -> MagicMock:
    """role='tool' message carrying one or more function_result blocks.

    `call_ids` must match function_calls emitted by a prior assistant
    message. `exceptions` is parallel to call_ids: None for success, a
    string for a validation-failure exception payload.
    """
    msg = MagicMock()
    msg.role = "tool"
    msg.text = ""
    excs = exceptions if exceptions is not None else [None] * len(call_ids)
    msg.contents = [
        _function_result(cid, exc) for cid, exc in zip(call_ids, excs, strict=False)
    ]
    return msg


def _agent_response(
    text: str,
    tool_names: list[str] | None = None,
    tool_exceptions: list[str | None] | None = None,
) -> MagicMock:
    """Construct an AgentResponse-shaped mock matching the real GA shape.

    For each tool in `tool_names`, generates an assistant message carrying a
    function_call with that name, followed by a tool message carrying the
    matching function_result. `tool_exceptions` (parallel list) lets a test
    simulate a tool whose result raised (e.g. validation failure) — those
    don't count as fired in _output_tool_called.

    GA shape verified 2026-05-17 against the deployed Foundry endpoint:
      [assistant function_call(name='X', call_id='c1')]
      [tool      function_result(name=None, call_id='c1', result/exception)]
      [assistant text]
    """
    response = MagicMock()
    response.text = text
    messages: list[MagicMock] = []
    excs = (
        tool_exceptions
        if tool_exceptions is not None
        else [None] * len(tool_names or [])
    )
    for i, name in enumerate(tool_names or []):
        call_id = f"call-{i}-{name}"
        messages.append(_assistant_message("", calls=[(name, call_id)]))
        exc = excs[i] if i < len(excs) else None
        messages.append(_tool_message([call_id], [exc]))
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

    async def test_simple_confirmation_files_inbox_item(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """Branch B: status="filed" + ttl + adminProcessingStatus="completed" via upsert (no delete).

        Phase 25 swap: previously the success path called delete_item; now it
        soft-deletes via upsert with status='filed' + ttl + completed marker.
        All three fields must land in the SAME upsert body (Landmine #4 in
        RESEARCH.md — partial writes would re-fire the agent on filed docs).
        """
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter and milk",
        )

        container = mock_cosmos_manager.get_container("Inbox")

        # TWO upserts: pending (line ~247) + filing (Phase 25 swap)
        upsert_calls = container.upsert_item.call_args_list
        assert len(upsert_calls) == 2

        first_body = upsert_calls[0].kwargs.get("body") or upsert_calls[0][1].get(
            "body"
        )
        assert first_body["adminProcessingStatus"] == "pending"

        filing_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get(
            "body"
        )
        assert filing_body["status"] == "filed"
        assert filing_body["adminProcessingStatus"] == "completed"
        assert filing_body["ttl"] > 0
        assert isinstance(filing_body["ttl"], int)

        # delete_item should NOT have been called (replaced by upsert)
        container.delete_item.assert_not_called()

    async def test_filed_doc_ttl_matches_settings(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """Filed doc ttl = settings.inbox_filed_retention_days * 86400."""
        from second_brain.config import get_settings

        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need milk",
        )

        container = mock_cosmos_manager.get_container("Inbox")
        filing_body = container.upsert_item.call_args_list[-1].kwargs.get("body")

        expected_ttl = get_settings().inbox_filed_retention_days * 86400
        assert filing_body["ttl"] == expected_ttl
        assert expected_ttl == 30 * 86400  # 2592000 default

    async def test_filing_writes_all_fields_atomically(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """status, adminProcessingStatus, and ttl land in the SAME upsert body.

        Landmine #4: if filed-status and completed-marker were written in
        separate upserts, a partial write would leave the doc with
        adminProcessingStatus='pending' (which matches the api/errands.py:174
        re-fire query) AND status='filed' (which the listing query hides).
        Net result: invisible re-fire loop. The test asserts atomicity.
        """
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need milk",
        )

        container = mock_cosmos_manager.get_container("Inbox")
        filing_body = container.upsert_item.call_args_list[-1].kwargs.get("body")

        assert "status" in filing_body
        assert "adminProcessingStatus" in filing_body
        assert "ttl" in filing_body
        assert filing_body["status"] == "filed"
        assert filing_body["adminProcessingStatus"] == "completed"

    async def test_admin_handoff_sets_inbox_item_id_contextvar(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """process_admin_capture sets admin_inbox_item_id_var before agent.run.

        add_errand_items / add_task_items (Plan 04) read this ContextVar to
        stamp sourceInboxItemId backlinks on Errand/Task docs.
        """
        from second_brain.tools.admin import admin_inbox_item_id_var

        observed_id: list[str | None] = []

        async def _capture_var(*args, **kwargs):
            observed_id.append(admin_inbox_item_id_var.get())
            return _agent_response(
                text="Added items.",
                tool_names=["add_errand_items"],
            )

        mock_admin_agent.run = AsyncMock(side_effect=_capture_var)

        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="ctx-inbox-id",
            raw_text="need milk",
        )

        assert observed_id == ["ctx-inbox-id"]

    async def test_filing_not_found_is_non_fatal(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """CosmosResourceNotFoundError on filing read does not raise.

        Phase 25: the success path now reads the doc before upserting the
        filing fields. If the doc has been removed concurrently (e.g., user
        swipe-deleted), the read raises NotFound and we swallow it.
        """
        container = mock_cosmos_manager.get_container("Inbox")

        # Pending read succeeds; filing read raises NotFound.
        call_count = 0

        async def _read_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return _inbox_doc()
            raise CosmosResourceNotFoundError(status_code=404, message="Not found")

        container.read_item = AsyncMock(side_effect=_read_side_effect)

        # Should NOT raise
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter and milk",
        )

    async def test_filing_failure_is_non_fatal(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """Generic Exception during filing does not raise.

        Phase 25: errand items are the durable output; the filing upsert is
        best-effort. If Cosmos times out on the filing write, we log and move
        on rather than propagating the error.
        """
        container = mock_cosmos_manager.get_container("Inbox")

        # First upsert (pending) succeeds; second upsert (filing) raises.
        call_count = 0

        async def _upsert_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return None
            raise Exception("Cosmos timeout")

        container.upsert_item = AsyncMock(side_effect=_upsert_side_effect)

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
        # Phase 25 orthogonality: failed items MUST NOT be marked filed (Landmine #1).
        assert last_body.get("status") != "filed"

    async def test_agent_error_does_not_file_inbox_item(
        self, mock_admin_agent, mock_cosmos_manager
    ):
        """When Admin Agent raises, the soft-delete filing path MUST NOT run.

        Failed items get adminProcessingStatus="failed" only — not status="filed".
        This preserves orthogonality with Phase 24 backlog "Admin Retry Bound"
        (retry-exhausted items stay visible until manually deleted).
        """
        mock_admin_agent.run.side_effect = RuntimeError("Foundry timeout")

        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter",
        )

        container = mock_cosmos_manager.get_container("Inbox")
        # Every upsert body in the test must NOT have status="filed"
        upsert_calls = container.upsert_item.call_args_list
        for call in upsert_calls:
            body = call.kwargs.get("body") or call[1].get("body")
            assert body.get("status") != "filed", (
                f"Failed path wrote status='filed' to an upsert body: {body}"
            )

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

    async def test_output_tool_called_files_inbox_item(self, mock_cosmos_manager):
        """Output tool called -- inbox item is filed (Phase 25 soft-delete).

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

        # Phase 25: filing replaces delete
        upsert_calls = container.upsert_item.call_args_list
        assert len(upsert_calls) >= 2  # pending + filing
        filing_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get(
            "body"
        )
        assert filing_body["status"] == "filed"
        assert filing_body["adminProcessingStatus"] == "completed"
        assert filing_body["ttl"] > 0
        container.delete_item.assert_not_called()

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

        # Phase 25: filing replaces delete (retry succeeded)
        upsert_calls = container.upsert_item.call_args_list
        assert len(upsert_calls) >= 2  # pending + filing
        filing_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get(
            "body"
        )
        assert filing_body["status"] == "filed"
        assert filing_body["adminProcessingStatus"] == "completed"
        assert filing_body["ttl"] > 0
        container.delete_item.assert_not_called()

    async def test_tool_call_still_files(self, mock_admin_agent, mock_cosmos_manager):
        """When agent DOES call an output tool, inbox item is filed (Phase 25)."""
        await process_admin_capture(
            admin_agent=mock_admin_agent,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need milk and eggs",
        )

        container = mock_cosmos_manager.get_container("Inbox")

        # Phase 25: filing replaces delete
        upsert_calls = container.upsert_item.call_args_list
        assert len(upsert_calls) >= 2  # pending + filing
        filing_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get(
            "body"
        )
        assert filing_body["status"] == "filed"
        assert filing_body["adminProcessingStatus"] == "completed"
        assert filing_body["ttl"] > 0
        container.delete_item.assert_not_called()


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

        # Phase 25: failed item gets "failed" upsert; successful item gets a
        # filing upsert (status="filed" + adminProcessingStatus="completed" + ttl).
        upsert_calls = container.upsert_item.call_args_list
        bodies = [c.kwargs.get("body") or c[1].get("body") for c in upsert_calls]
        statuses = [b["adminProcessingStatus"] for b in bodies]
        assert "failed" in statuses
        # At least one filing upsert (success path) lands in the same batch.
        filing_bodies = [b for b in bodies if b.get("status") == "filed"]
        assert len(filing_bodies) >= 1
        assert filing_bodies[0]["adminProcessingStatus"] == "completed"
        assert filing_bodies[0]["ttl"] > 0

        # delete_item NEVER called (Phase 25 replaces hard-delete with file)
        container.delete_item.assert_not_called()

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
