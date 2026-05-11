"""Phase 24 P0-1 OUTCOME conversation-history resolver (Option A).

Background: cross-process AgentSession rehydration via session_id alone fails
on GA Foundry SDK 1.3.0 (probe fixture session_rehydration_fresh_process.json,
recalled_pineapple=false). Operator locked Option A — persist explicit
conversation history on the Inbox doc and pass it to agent.run(messages=[...])
on each follow-up.

During the migration window, an Inbox doc may have:
  (a) only foundryThreadId (legacy RC doc — no conversationHistory)
  (b) both foundryThreadId AND conversationHistory (post-24-17 new captures
      during the rollback-safety window)
  (c) only conversationHistory (post-24-24 cleanup of foundryThreadId)

resolve_inbox_conversation_history() returns the conversationHistory list as-is
if present, or an empty list with a logged warning if absent. Case (a) gracefully
loses continuity — the classifier treats the follow-up as a new conversation.
This is the accepted Option A trade-off: in-flight RC follow-ups during deploy
are few; zero migration effort.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ConversationTurn(BaseModel):
    """One turn in a persisted Inbox conversation history.

    Stored on InboxDocument.conversationHistory (list[ConversationTurn]).
    Reconstructed into agent_framework.Message objects in
    streaming/adapter.py (24-16).
    """

    role: Literal["user", "assistant"]
    content: str


def resolve_inbox_conversation_history(inbox_doc: Any) -> list[ConversationTurn]:
    """Return the conversation history stored on this Inbox doc.

    If ``conversationHistory`` is set: return the list (parsed into
    ConversationTurn models if raw dicts).

    If absent but ``foundryThreadId`` is set (legacy RC doc): return []
    and log a warning. The classifier treats this as a fresh conversation;
    continuity is lost gracefully for legacy docs.

    If both absent: return [] (brand-new capture, no warning).

    Accepts any object with attribute access (Pydantic model) or
    subscriptable access (dict from Cosmos).
    """
    raw_history = _read(inbox_doc, "conversationHistory")
    if raw_history:
        return _coerce_to_turns(raw_history)

    legacy_thread = _read(inbox_doc, "foundryThreadId")
    if legacy_thread:
        doc_id = _read(inbox_doc, "id") or "<unknown>"
        logger.warning(
            "inbox doc %s has legacy foundryThreadId=%s but no conversationHistory "
            "— follow-up will be treated as new conversation (continuity lost). "
            "P0-1 OUTCOME Option A graceful-loss path.",
            doc_id,
            legacy_thread,
        )
        return []

    return []


def _read(doc: Any, key: str) -> Any:
    """Read ``key`` from a Pydantic-attr object or a dict body, truthy only."""
    if hasattr(doc, key):
        value = getattr(doc, key, None)
        if value:
            return value
    if isinstance(doc, dict) and key in doc:
        value = doc.get(key)
        if value:
            return value
    return None


def _coerce_to_turns(raw: Any) -> list[ConversationTurn]:
    """Accept either list[dict] (raw from Cosmos) or list[ConversationTurn]."""
    if not isinstance(raw, list):
        return []
    turns: list[ConversationTurn] = []
    for item in raw:
        if isinstance(item, ConversationTurn):
            turns.append(item)
        elif isinstance(item, dict):
            try:
                turns.append(ConversationTurn(**item))
            except Exception:
                # Skip malformed entries rather than crash the follow-up
                logger.warning("Skipping malformed ConversationTurn: %r", item)
    return turns
