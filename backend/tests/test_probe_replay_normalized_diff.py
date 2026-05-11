"""Phase 24 P1-6 — live probe replay produces fixture matching committed shape
under the volatile-field normalization (foundry_probe_compare.normalize_fixture).
Marked live_endpoint — skipped if probe env is not sourced."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "foundry-probe"
)
PROBE_NAMES = (
    "streaming_shape",
    "tool_call_extraction",
    "tool_choice_required",
    "session_rehydration",
    "auth_probe",
    "session_rehydration_fresh_process",
)


@pytest.mark.live_endpoint
@pytest.mark.parametrize("probe_name", PROBE_NAMES)
def test_probe_replay_matches_normalized_fixture(probe_name: str) -> None:
    if not os.environ.get("FOUNDRY_PROJECT_ENDPOINT"):
        pytest.skip("FOUNDRY_PROJECT_ENDPOINT not set — probe env not sourced")

    proc = subprocess.run(
        [sys.executable, "-m", "scripts.foundry_probe_compare", probe_name],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=Path(__file__).resolve().parents[1],
    )
    output = proc.stdout
    assert proc.returncode == 0, (
        f"probe_compare failed for {probe_name}: {proc.stderr}\n{output}"
    )
    payload = (
        json.loads(output.split("\n")[-2] if "\n" in output else output)
        if output
        else {}
    )
    assert payload.get("matches") is True, (
        f"Probe {probe_name} replay did not match committed fixture under normalization.\n"
        f"diff:\n{payload.get('diff', '<missing>')}"
    )
