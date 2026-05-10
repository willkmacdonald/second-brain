"""Phase 24 P0-1 red test: cross-process AgentSession rehydration.

Spawns the fresh-process session-rehydration probe end-to-end against the
deployed Foundry endpoint. Asserts that a SEPARATE Python process can
reconstruct conversation continuity from a persisted `session_id` alone.

This test gates plans 24-07, 24-16, 24-17. If it fails, the singleton-agent
+ session_id rehydration design is invalid and Phase 24 must fall back to
full message-history persistence on the Inbox doc.

Skips cleanly if the probe env vars (APPLICATIONINSIGHTS_CONNECTION_STRING
or FOUNDRY_PROJECT_ENDPOINT / AZURE_AI_PROJECT_ENDPOINT) are not set --
e.g. local dev without the laptop env sourced.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "foundry-probe"
    / "session_rehydration_fresh_process.json"
)


@pytest.mark.live_endpoint
def test_session_rehydration_fresh_process_recalls_prior_turn() -> None:
    """Run the fresh-process session rehydration probe and assert recall.

    The probe spawns two SEPARATE Python subprocesses:
      - Phase A creates an AgentSession, sends turn 1 with magic word
        PINEAPPLE, persists session.session_id to a temp file, exits.
      - Phase B (fresh interpreter, no shared Python state) loads the
        session_id from disk, reconstructs AgentSession(session_id=...),
        sends turn 2 asking for the magic word, captures the response.

    The probe writes a fixture with phase_a_exit_code, phase_b_exit_code,
    persisted_session_id, turn_two_text, and recalled_pineapple.

    This test asserts recalled_pineapple is True.
    """
    if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING") or not (
        os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        or os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    ):
        pytest.skip(
            "Probe env not sourced -- APPLICATIONINSIGHTS_CONNECTION_STRING "
            "or FOUNDRY_PROJECT_ENDPOINT/AZURE_AI_PROJECT_ENDPOINT missing"
        )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.foundry_probe",
            "session_rehydration_fresh_process",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0, f"Probe failed: stderr={result.stderr[-2000:]}"

    assert FIXTURE_PATH.exists(), f"Fixture not written: {FIXTURE_PATH}"
    payload = json.loads(FIXTURE_PATH.read_text())

    assert payload.get("phase_a_exit_code") == 0, (
        f"Phase A failed: {payload.get('phase_a_stderr_tail')}"
    )
    assert payload.get("phase_b_exit_code") == 0, (
        f"Phase B failed: {payload.get('phase_b_stderr_tail')}"
    )
    assert payload.get("recalled_pineapple") is True, (
        f"Cross-process recall FAILED. Turn 2 did not recall the magic word.\n"
        f"persisted_session_id={payload.get('persisted_session_id')}\n"
        f"turn_two_text={payload.get('turn_two_text')!r}"
    )
