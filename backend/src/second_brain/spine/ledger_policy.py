"""Operator-facing ledger policy for the transaction-first spine UI.

This module codifies the **approved operator contract** for how the ledger-first
UI reports chain gaps and empty states. It is deliberately separate from the
raw audit registry (`spine/audit/chains.py::EXPECTED_CHAINS`) because the
operator-facing ledger incorporates decisions from the Phase 19.2 spike memo
(e.g. mobile push-path scope) that differ from the raw emit-site audit.

Do NOT read `SPIKE-MEMO.md` at runtime — the memo's approved decision is
encoded as code below.

Approved decisions folded in (from `SPIKE-MEMO.md` round 3):
- `mobile_capture` has a push-path emitter (Option B — post-capture
  fire-and-forget) and therefore IS a transactional segment for operator
  diagnostics. It remains required in the capture chain.
- `mobile_ui` remains native-only for the capture chain — it fires only on
  crud-kind events, not captures.
- `cosmos` and `container_app` are native-only by design (pulled from
  `AzureDiagnostics` / App Insights roll-up respectively).
"""

from __future__ import annotations

from typing import Literal, TypedDict

from second_brain.spine.audit.chains import EXPECTED_CHAINS, ExpectedSegment
from second_brain.spine.models import CorrelationKind


class _SegmentLedgerMetadata(TypedDict):
    """Per-segment runtime metadata for the ledger UI empty state."""

    mode: Literal["transactional", "native_only"]
    empty_state_reason: str | None


# ---------------------------------------------------------------------------
# LEDGER_EXPECTED_CHAINS — operator-facing chain expectations
# ---------------------------------------------------------------------------
# Starts from the raw audit registry, then overlays the SPIKE-MEMO decisions.
# The memo approved Option B (post-capture emit) for `mobile_capture`, so the
# capture chain expectation remains unchanged from EXPECTED_CHAINS. If a future
# memo revision downgrades `mobile_capture` to native-only, adjust the override
# below and `SEGMENT_LEDGER_METADATA["mobile_capture"]` in tandem.

LEDGER_EXPECTED_CHAINS: dict[CorrelationKind, list[ExpectedSegment]] = {
    kind: list(chain) for kind, chain in EXPECTED_CHAINS.items()
}


# ---------------------------------------------------------------------------
# SEGMENT_LEDGER_METADATA — per-segment ledger mode + empty-state text
# ---------------------------------------------------------------------------
# Every segment not listed here defaults to `{"mode": "transactional",
# "empty_state_reason": None}` — callers MUST handle that fallback.

SEGMENT_LEDGER_METADATA: dict[str, _SegmentLedgerMetadata] = {
    "cosmos": {
        "mode": "native_only",
        "empty_state_reason": (
            "Cosmos emits no workload events by design — diagnostics for this "
            "segment come from Azure Diagnostics logs rendered below."
        ),
    },
    "container_app": {
        "mode": "native_only",
        "empty_state_reason": (
            "Container App is a rollup segment — it pulls telemetry from the "
            "backend_api App Insights stream and emits no workload events of "
            "its own. See the diagnostics section below."
        ),
    },
    "mobile_ui": {
        "mode": "native_only",
        "empty_state_reason": (
            "mobile_ui emits spine events only for CRUD failures. Routine "
            "capture activity does not touch this segment — see Sentry for "
            "client-side telemetry."
        ),
    },
}


def ledger_metadata_for(segment_id: str) -> _SegmentLedgerMetadata:
    """Return the ledger metadata for a segment, defaulting to transactional."""
    return SEGMENT_LEDGER_METADATA.get(
        segment_id,
        {"mode": "transactional", "empty_state_reason": None},
    )
