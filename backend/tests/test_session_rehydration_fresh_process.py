"""Phase 24 P0-1 OUTCOME regression guard: cross-process AgentSession
rehydration is PROVEN BROKEN on GA Foundry SDK 1.3.0.

This test was originally authored as a RED gate for plans 24-07, 24-16,
24-17 — asserting that a SEPARATE Python process could reconstruct
conversation continuity from a persisted ``session_id`` alone. The
probe ran live TWICE during 24-06.5 (both runs returned
``recalled_pineapple=False``) and a 3rd time during 24-08's auditor
re-pin. The operator locked **Option A** (persist full conversation
history on the Inbox doc) as a result.

Per the P0-1 OUTCOME closure in 24-PLAN-DEFECTS.md the assertion is
INVERTED in TG 23.3 cleanup (target was 24-18; landed in 24-20 Gate 3
auto-fix): the locked invariant is ``recalled_pineapple is False``.
If this test ever flips to True (i.e. cross-process recall starts
working), the conversationHistory design becomes OPTIONAL not
mandatory — revisit the design before continuing.

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
    """Run the fresh-process session rehydration probe and assert the
    P0-1 OUTCOME locked invariant: cross-process recall FAILS.

    The probe spawns two SEPARATE Python subprocesses:
      - Phase A creates an AgentSession, sends turn 1 with magic word
        PINEAPPLE, persists session.session_id to a temp file, exits.
      - Phase B (fresh interpreter, no shared Python state) loads the
        session_id from disk, reconstructs AgentSession(session_id=...),
        sends turn 2 asking for the magic word, captures the response.

    The probe writes a fixture with phase_a_exit_code, phase_b_exit_code,
    persisted_session_id, turn_two_text, and recalled_pineapple.

    P0-1 OUTCOME: 3+ independent live runs all produced
    recalled_pineapple=False. Operator locked Option A. This test asserts
    the locked invariant — if it flips to True, the design changes.
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
    assert payload.get("recalled_pineapple") is False, (
        f"P0-1 OUTCOME REGRESSION: cross-process recall flipped to True.\n"
        f"The conversationHistory design (Option A, locked 2026-05-10) was "
        f"built on the assumption that cross-process AgentSession rehydration "
        f"FAILS on GA Foundry SDK 1.3.0. If this assertion fires, the design "
        f"becomes optional, not mandatory — revisit before continuing.\n"
        f"persisted_session_id={payload.get('persisted_session_id')}\n"
        f"turn_two_text={payload.get('turn_two_text')!r}"
    )
