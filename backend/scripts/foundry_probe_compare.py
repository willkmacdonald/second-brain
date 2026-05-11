"""Phase 24 P1-6 normalize-and-diff helper for Gate 4.

Strips volatile fields from probe output before diffing against committed
fixtures. The original Gate 4 spec used a /tmp stdout redirect that doesn't
work (probes write to fixture path, not stdout) and exact diff (unstable due
to UUIDs / timestamps / repr addresses).

This helper provides:
- normalize_fixture(payload: dict) -> dict — strips volatile fields recursively
- compare(live_payload, fixture_payload) -> tuple[bool, str] — returns (matches, diff_str)
- CLI entry: `uv run python -m scripts.foundry_probe_compare <probe_name>`
  reads the committed fixture, runs the live probe, normalizes both, diffs.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

VOLATILE_KEYS = {
    "run_id",
    "captured_at",
    "response_id",
    "service_session_id",
    "session_id",  # session ids change per run; keep shape only
    "phase_a_run_id",
    "phase_b_run_id",
    "expires_on",
    "token_length",
    "persisted_session_id",
    "user_id",
    # Additional GA SDK volatile fields surfaced during 24-20 Gate 4 live runs:
    "continuation_token",  # contains nested response_id like resp_0cc6dc2f...
    "created_at",  # ISO-8601 timestamps from the SDK
    "phase_a_stderr_tail",  # contains probe run_id + temp paths
    "phase_b_stderr_tail",
    "phase_b_service_session_id",
    "turn_two_text",  # model-generated free text (non-deterministic phrasing)
    "turn_two_response_repr",  # contains repr addresses + service ids
    "usage_details",  # dict key ordering varies; token counts may vary by 1-2
}

REPR_ADDRESS_RE = re.compile(r"at 0x[0-9a-fA-F]+")
# Volatile substrings inside otherwise-stable string values:
RESPONSE_ID_RE = re.compile(r"resp_[0-9a-fA-F]+")  # GA SDK Foundry response ids
ISO_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)
# Common model output variance: capitalisation of one-word echo responses
# (e.g. "echo" vs "Echo" — depends on temperature + recent model versioning).
# We could scrub this too but it's load-bearing semantic content; leave it
# alone and let the invariant tests catch shape regressions.


def _scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        # Strip Python repr addresses, response ids, and ISO timestamps
        # that may appear inside string values.
        scrubbed = REPR_ADDRESS_RE.sub("at 0x...", value)
        scrubbed = RESPONSE_ID_RE.sub("resp_<scrubbed>", scrubbed)
        scrubbed = ISO_TIMESTAMP_RE.sub("<scrubbed-timestamp>", scrubbed)
        return scrubbed
    if isinstance(value, dict):
        return {k: _scrub_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_value(v) for v in value]
    return value


def normalize_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip volatile fields recursively from probe payload."""
    cleaned = copy.deepcopy(payload)

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            new = {}
            for k, v in obj.items():
                if k in VOLATILE_KEYS:
                    new[k] = "<scrubbed>"
                else:
                    new[k] = _walk(v)
            return new
        if isinstance(obj, list):
            return [_walk(item) for item in obj]
        return _scrub_value(obj)

    return _walk(cleaned)


def compare(live: dict[str, Any], fixture: dict[str, Any]) -> tuple[bool, str]:
    n_live = normalize_fixture(live)
    n_fix = normalize_fixture(fixture)
    if n_live == n_fix:
        return True, ""
    # Cheap diff via JSON serialization
    live_str = json.dumps(n_live, indent=2, sort_keys=True, default=str)
    fix_str = json.dumps(n_fix, indent=2, sort_keys=True, default=str)
    import difflib

    diff = "\n".join(
        difflib.unified_diff(
            fix_str.splitlines(),
            live_str.splitlines(),
            lineterm="",
            fromfile="committed_fixture",
            tofile="live_replay",
        )
    )
    return False, diff


def main() -> int:
    parser = argparse.ArgumentParser(prog="foundry_probe_compare")
    parser.add_argument(
        "probe_name", help="Probe to run + diff (e.g. streaming_shape)."
    )
    args = parser.parse_args()

    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "foundry-probe"
        / f"{args.probe_name}.json"
    )
    if not fixture_path.exists():
        print(f"FATAL: fixture {fixture_path} missing", file=sys.stderr)
        return 1

    fixture = json.loads(fixture_path.read_text())

    # Run live probe — writes the fixture in place (foundry_probe writes to disk)
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.foundry_probe", args.probe_name],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        print(f"FATAL: probe failed:\n{proc.stderr}", file=sys.stderr)
        return 1

    live = json.loads(fixture_path.read_text())

    matches, diff = compare(live, fixture)
    if matches:
        print(json.dumps({"probe": args.probe_name, "matches": True}))
        return 0
    print(
        json.dumps({"probe": args.probe_name, "matches": False, "diff": diff}, indent=2)
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
