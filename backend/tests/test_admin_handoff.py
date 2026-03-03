"""Unit tests for Admin Agent background processing.

Tests the process_admin_capture function with mocked Azure services.
Validates status transitions, delete-on-success, error handling,
and timeout behavior.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from second_brain.processing.admin_handoff import (
    process_admin_capture,
    process_admin_captures_batch,
)


@pytest.fixture
def mock_admin_client():
    """Mock AzureAIAgentClient for non-streaming calls."""
    client = AsyncMock()
    response = MagicMock()
    response.text = "Added 2 items: 1 to jewel, 1 to pet_store"
    client.get_response.return_value = response
    return client


@pytest.fixture
def mock_admin_tools():
    """Mock tool list for Admin Agent."""
    tool_fn = AsyncMock()
    return [tool_fn]


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
        self, mock_admin_client, mock_cosmos_manager, mock_admin_tools
    ):
        """Status transitions: None -> pending, then delete on success."""
        await process_admin_capture(
            admin_client=mock_admin_client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter and milk",
        )

        container = mock_cosmos_manager.get_container("Inbox")

        # Only ONE upsert: the "pending" status
        upsert_calls = container.upsert_item.call_args_list
        assert len(upsert_calls) == 1
        first_body = (
            upsert_calls[0].kwargs.get("body")
            or upsert_calls[0][1].get("body")
        )
        assert first_body["adminProcessingStatus"] == "pending"

        # delete_item called once for the processed inbox item
        container.delete_item.assert_called_once_with(
            item="test-inbox-id", partition_key="will"
        )

    async def test_delete_not_found_is_non_fatal(
        self, mock_admin_client, mock_cosmos_manager, mock_admin_tools
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
            admin_client=mock_admin_client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter and milk",
        )

    async def test_delete_failure_is_non_fatal(
        self, mock_admin_client, mock_cosmos_manager, mock_admin_tools
    ):
        """Generic Exception on delete does not raise."""
        container = mock_cosmos_manager.get_container("Inbox")
        container.delete_item = AsyncMock(
            side_effect=Exception("Cosmos timeout")
        )

        # Should NOT raise
        await process_admin_capture(
            admin_client=mock_admin_client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter and milk",
        )

    async def test_calls_admin_agent_with_raw_text(
        self, mock_admin_client, mock_cosmos_manager, mock_admin_tools
    ):
        """Admin Agent receives the user's capture text."""
        await process_admin_capture(
            admin_client=mock_admin_client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter and milk",
        )

        mock_admin_client.get_response.assert_called_once()
        call_kwargs = mock_admin_client.get_response.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        assert len(messages) == 1
        assert messages[0].text == "need cat litter and milk"

    async def test_passes_tools_to_agent(
        self, mock_admin_client, mock_cosmos_manager, mock_admin_tools
    ):
        """Admin Agent receives the tool list."""
        await process_admin_capture(
            admin_client=mock_admin_client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need milk",
        )

        call_kwargs = mock_admin_client.get_response.call_args
        options = call_kwargs.kwargs.get("options") or call_kwargs[1].get("options")
        assert options["tools"] == mock_admin_tools


# ---------------------------------------------------------------------------
# Tests: failure path
# ---------------------------------------------------------------------------


class TestProcessAdminCaptureFailure:
    """Tests for error handling paths."""

    async def test_agent_error_sets_status_to_failed(
        self, mock_admin_client, mock_cosmos_manager, mock_admin_tools
    ):
        """When Admin Agent raises, status transitions to 'failed'."""
        mock_admin_client.get_response.side_effect = RuntimeError("Foundry timeout")

        await process_admin_capture(
            admin_client=mock_admin_client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter",
        )

        container = mock_cosmos_manager.get_container("Inbox")
        upsert_calls = container.upsert_item.call_args_list
        # Should have pending upsert and failed upsert
        assert len(upsert_calls) >= 2
        last_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get("body")
        assert last_body["adminProcessingStatus"] == "failed"

    async def test_agent_error_does_not_raise(
        self, mock_admin_client, mock_cosmos_manager, mock_admin_tools
    ):
        """process_admin_capture never raises -- safe for fire-and-forget."""
        mock_admin_client.get_response.side_effect = RuntimeError("Foundry timeout")

        # Should NOT raise
        await process_admin_capture(
            admin_client=mock_admin_client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-inbox-id",
            raw_text="need cat litter",
        )

    async def test_cosmos_read_failure_returns_early(
        self, mock_admin_client, mock_cosmos_manager, mock_admin_tools
    ):
        """If initial read fails, function returns without calling Admin Agent."""
        container = mock_cosmos_manager.get_container("Inbox")
        container.read_item.side_effect = Exception("Cosmos 404")

        await process_admin_capture(
            admin_client=mock_admin_client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="nonexistent-id",
            raw_text="need cat litter",
        )

        # Admin Agent should NOT be called
        mock_admin_client.get_response.assert_not_called()

    async def test_failed_status_update_does_not_raise(
        self, mock_admin_client, mock_cosmos_manager, mock_admin_tools
    ):
        """If updating status to 'failed' itself fails, no exception propagates."""
        mock_admin_client.get_response.side_effect = RuntimeError("Agent error")
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
            admin_client=mock_admin_client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            inbox_item_id="test-id",
            raw_text="need cat litter",
        )


# ---------------------------------------------------------------------------
# Tests: timeout
# ---------------------------------------------------------------------------


class TestProcessAdminCaptureTimeout:
    """Tests for timeout behavior."""

    async def test_timeout_sets_status_to_failed(
        self, mock_cosmos_manager, mock_admin_tools
    ):
        """60-second timeout triggers failed status."""
        slow_client = AsyncMock()

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(120)  # Simulate very slow response

        slow_client.get_response = slow_response

        # Patch asyncio.timeout to use a very short timeout for testing
        with patch(
            "second_brain.processing.admin_handoff.asyncio.timeout",
            return_value=asyncio.timeout(0.01),
        ):
            await process_admin_capture(
                admin_client=slow_client,
                admin_tools=mock_admin_tools,
                cosmos_manager=mock_cosmos_manager,
                inbox_item_id="test-inbox-id",
                raw_text="need cat litter",
            )

        container = mock_cosmos_manager.get_container("Inbox")
        upsert_calls = container.upsert_item.call_args_list
        last_body = upsert_calls[-1].kwargs.get("body") or upsert_calls[-1][1].get("body")
        assert last_body["adminProcessingStatus"] == "failed"


# ---------------------------------------------------------------------------
# Tests: batch processing
# ---------------------------------------------------------------------------


class TestProcessAdminCapturesBatch:
    """Tests for process_admin_captures_batch."""

    async def test_batch_calls_process_for_each_item(
        self, mock_admin_client, mock_cosmos_manager, mock_admin_tools
    ):
        """Given 2 admin items, admin_client.get_response is called twice."""
        admin_items = [
            {"inbox_item_id": "item-1", "raw_text": "need milk"},
            {"inbox_item_id": "item-2", "raw_text": "buy eggs"},
        ]

        await process_admin_captures_batch(
            admin_client=mock_admin_client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            admin_items=admin_items,
        )

        assert mock_admin_client.get_response.call_count == 2

    async def test_batch_one_failure_does_not_block_second(
        self, mock_cosmos_manager, mock_admin_tools
    ):
        """First item fails, second still processes successfully."""
        client = AsyncMock()
        response_ok = MagicMock()
        response_ok.text = "Processed items"

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Foundry timeout")
            return response_ok

        client.get_response = AsyncMock(side_effect=side_effect)

        # Need separate docs per item -- set up read_item to return fresh docs
        container = mock_cosmos_manager.get_container("Inbox")
        container.read_item.side_effect = lambda **kwargs: _inbox_doc()

        admin_items = [
            {"inbox_item_id": "item-fail", "raw_text": "fail this"},
            {"inbox_item_id": "item-ok", "raw_text": "this works"},
        ]

        await process_admin_captures_batch(
            admin_client=client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            admin_items=admin_items,
        )

        # Both items were attempted
        assert client.get_response.call_count == 2

        # Failed item gets "failed" upsert; successful item gets delete
        upsert_calls = container.upsert_item.call_args_list
        statuses = [
            (c.kwargs.get("body") or c[1].get("body"))[
                "adminProcessingStatus"
            ]
            for c in upsert_calls
        ]
        assert "failed" in statuses
        # "processed" should NOT be in upserts -- success path deletes
        assert "processed" not in statuses

        # delete_item called at least once (for the successful item)
        assert container.delete_item.call_count >= 1

    async def test_batch_empty_list_is_noop(
        self, mock_admin_client, mock_cosmos_manager, mock_admin_tools
    ):
        """Empty admin_items list returns without calling admin_client."""
        await process_admin_captures_batch(
            admin_client=mock_admin_client,
            admin_tools=mock_admin_tools,
            cosmos_manager=mock_cosmos_manager,
            admin_items=[],
        )

        mock_admin_client.get_response.assert_not_called()
