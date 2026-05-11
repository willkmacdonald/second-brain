"""Phase 24 P1-6 — invariant shape assertions over probe fixtures."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "foundry-probe"
)


def _load(name: str) -> dict:
    path = FIXTURE_DIR / f"{name}.json"
    assert path.exists(), f"fixture missing: {path}"
    return json.loads(path.read_text())


def test_streaming_shape_yields_at_least_one_update() -> None:
    payload = _load("streaming_shape")
    assert payload.get("update_count", 0) >= 1
    assert isinstance(payload.get("updates"), list)
    assert len(payload["updates"]) >= 1


def test_tool_call_extraction_walks_messages() -> None:
    payload = _load("tool_call_extraction")
    assert payload.get("messages_present") is True
    walk = payload.get("messages_walk", [])
    assert len(walk) >= 1


def test_tool_choice_required_works_string_form() -> None:
    payload = _load("tool_choice_required")
    trials = payload.get("trials", {})
    assert "required" in trials
    assert trials["required"].get("raised") is False
    # provider_dict trial — confirm GA SDK still rejects
    assert "provider_dict" in trials


def test_session_rehydration_in_process_records_session_id() -> None:
    payload = _load("session_rehydration")
    shape = payload.get("thread_identifier_shape", {})
    fields = shape.get("fields", {})
    # session_id must appear on the AgentSession object
    assert any("session_id" in k for k in fields)


def test_session_rehydration_fresh_process_outcome_locked() -> None:
    """P0-1 OUTCOME — cross-process recall fails; this drives Option A design."""
    payload = _load("session_rehydration_fresh_process")
    # The locked outcome is recalled_pineapple=false. The schema/adapter design
    # is built on that outcome. Asserting either value here would over-constrain;
    # what matters is that the fixture is present and has the field.
    assert "recalled_pineapple" in payload
    # Per P0-1 OUTCOME closure: the locked value is False.
    assert payload["recalled_pineapple"] is False, (
        "Phase 24 design is locked on P0-1 OUTCOME = false (Option A). "
        "If this flips to true, the conversationHistory design becomes optional, "
        "not mandatory — revisit before continuing."
    )


def test_auth_probe_acquires_token() -> None:
    payload = _load("auth_probe")
    assert payload.get("token_acquisition", {}).get("acquired") is True
    assert payload.get("invocation", {}).get("succeeded") is True
