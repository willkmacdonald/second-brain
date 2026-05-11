"""Phase 24 P0-1 OUTCOME red test for conversation-history resolution (Option A).

Asserts resolve_inbox_conversation_history() resolves correctly for the three
Inbox doc states observed during the migration window:
  (a) foundryThreadId-only (legacy RC doc — returns [] with warning)
  (b) both foundryThreadId AND conversationHistory (returns history)
  (c) conversationHistory-only (returns history)

Plus negative tests: empty list, malformed entries, no fields at all.
"""

from __future__ import annotations

import logging

import pytest

from second_brain.cosmos.inbox_conversation_history import (
    ConversationTurn,
    resolve_inbox_conversation_history,
)


def test_legacy_doc_with_only_foundry_thread_id_returns_empty_list_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Case (a): legacy RC doc. Helper returns [] and logs a warning."""
    doc = {"id": "legacy-1", "foundryThreadId": "thread_legacy"}
    with caplog.at_level(logging.WARNING):
        result = resolve_inbox_conversation_history(doc)
    assert result == []
    assert any(
        "legacy foundryThreadId" in rec.message and "legacy-1" in rec.message
        for rec in caplog.records
    ), "Expected a warning mentioning the doc id and legacy foundryThreadId"


def test_doc_with_both_fields_returns_history_ignoring_foundry_thread_id() -> None:
    """Case (b): post-24-17 transitional state. conversationHistory is authoritative."""
    doc = {
        "id": "transitional-1",
        "foundryThreadId": "thread_legacy",
        "conversationHistory": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ],
    }
    result = resolve_inbox_conversation_history(doc)
    assert len(result) == 2
    assert result[0].role == "user"
    assert result[0].content == "Hello"
    assert result[1].role == "assistant"
    assert result[1].content == "Hi there"


def test_doc_with_only_conversation_history_returns_history() -> None:
    """Case (c): post-24-24 cleanup state. Only conversationHistory present."""
    doc = {
        "id": "new-1",
        "conversationHistory": [
            {"role": "user", "content": "What's the weather?"},
            {"role": "assistant", "content": "I don't have weather data."},
        ],
    }
    result = resolve_inbox_conversation_history(doc)
    assert len(result) == 2
    assert result[0].content == "What's the weather?"


def test_brand_new_doc_with_no_fields_returns_empty_list() -> None:
    """No prior conversation — fresh capture."""
    doc = {"id": "fresh-1"}
    result = resolve_inbox_conversation_history(doc)
    assert result == []


def test_empty_conversation_history_returns_empty_list() -> None:
    doc = {"id": "x", "conversationHistory": []}
    result = resolve_inbox_conversation_history(doc)
    assert result == []


def test_malformed_turns_are_skipped(caplog: pytest.LogCaptureFixture) -> None:
    """A malformed entry doesn't crash the follow-up."""
    doc = {
        "id": "malformed-1",
        "conversationHistory": [
            {"role": "user", "content": "OK"},
            {"role": "invalid_role", "content": "Bad"},  # invalid role
            {"role": "assistant"},  # missing content
            {"role": "assistant", "content": "Also OK"},
        ],
    }
    with caplog.at_level(logging.WARNING):
        result = resolve_inbox_conversation_history(doc)
    # The two well-formed turns survive
    assert len(result) == 2
    assert result[0].content == "OK"
    assert result[1].content == "Also OK"


def test_works_with_attribute_access_object() -> None:
    """Pydantic-style attribute access works as well as dict access."""

    class FakeInbox:
        id = "attr-1"
        conversationHistory = [
            ConversationTurn(role="user", content="From attrs"),
        ]

    result = resolve_inbox_conversation_history(FakeInbox())
    assert len(result) == 1
    assert result[0].content == "From attrs"
