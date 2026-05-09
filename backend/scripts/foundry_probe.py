"""Foundry probe harness — substitutes for staged production.

Standalone GA SDK exerciser. Lives outside backend/src/ and is NOT imported
by the running app. Probe runs hit the real Foundry endpoint using the
laptop's az login credentials (AzureCliCredential) and capture raw SDK
output to backend/tests/fixtures/foundry-probe/<probe>.json.

Usage:
    uv run python -m scripts.foundry_probe <probe_name>

Probes (per docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md
Section "Foundry probe harness"):
    streaming_shape       — AgentResponseUpdate field/type/order
    tool_call_extraction  — AgentResponse tool-call extraction path
    tool_choice_required  — Whether tool_choice='required' enforces single-tool selection
    session_rehydration   — AgentSession / session round-trip
    auth_probe            — FoundryChatClient + AzureCliCredential RBAC verification

Trace pollution containment:
    - Every span emitted by a probe carries probe.run_id and probe.name attributes.
    - No probe sets capture.trace_id — production KQL queries filter on that
      attribute and naturally exclude probe traffic.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# GA SDK imports — resolved against the candidate dependency set.
# If any of these fail at runtime, the candidate dep set is wrong; rerun
# PLAN-01 task 1 against the real CANDIDATE-pyproject.toml.
#
# NOTE: GA SDK (agent-framework 1.3.0) uses AgentResponse/AgentResponseUpdate/
# AgentSession — NOT the pre-GA names AgentRunResponse/AgentRunResponseUpdate/
# AgentThread that appeared in early documentation. See DEP-RESOLUTION-NOTES.md.
from agent_framework_foundry import FoundryChatClient
from azure.identity import AzureCliCredential

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "foundry-probe"
)


def _new_run_id() -> str:
    return str(uuid.uuid4())


def _write_fixture(probe_name: str, payload: dict[str, Any]) -> Path:
    """Persist probe output as JSON. Always tags payload with probe.run_id + probe.name."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURE_DIR / f"{probe_name}.json"
    payload.setdefault("probe", {})
    payload["probe"]["name"] = probe_name
    payload["probe"]["run_id"] = payload["probe"].get("run_id") or _new_run_id()
    payload["probe"]["captured_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def _build_client() -> FoundryChatClient:
    """Construct a FoundryChatClient for laptop-side probe runs.

    Reads FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL from env. AzureCliCredential
    is the credential class — Phase 24 will use ManagedIdentityCredential in
    Container Apps; the auth_probe documents the credential-shape difference.
    """
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT") or os.environ.get(
        "AZURE_AI_PROJECT_ENDPOINT"
    )
    if not endpoint:
        raise RuntimeError(
            "FOUNDRY_PROJECT_ENDPOINT not set. Source the laptop env before running probes."
        )
    model = os.environ.get("FOUNDRY_MODEL", "gpt-4o")
    return FoundryChatClient(
        endpoint=endpoint,
        model_deployment_name=model,
        credential=AzureCliCredential(),
    )


async def streaming_shape() -> Path:
    """Probe 1: AgentResponseUpdate field/type/order.

    Filled by PLAN-02 task 1. Should:
      - Construct a 1-tool stub agent (single tool: an echo function with @tool).
      - Run agent.run_stream(messages=[...]) with input that forces 1 tool call.
      - Collect every AgentResponseUpdate yielded into a JSON-serializable list.
      - Tag every emitted span with probe.run_id + probe.name (no capture.trace_id).
      - Optionally delete the agent's thread/session at end-of-run if SDK exposes deletion.
      - Write fixture via _write_fixture('streaming_shape', {...}).
    """
    raise NotImplementedError("streaming_shape probe body filled by PLAN-02 task 1")


async def tool_call_extraction() -> Path:
    """Probe 2: AgentResponse tool-call extraction path.

    Filled by PLAN-02 task 2. Should:
      - Same 1-tool stub agent as streaming_shape.
      - Run agent.run(messages=[...]) (NON-streaming).
      - Capture the raw AgentResponse object structure (messages, content blocks,
        metadata, tool_calls top-level if present).
      - Document via fixture which path inside AgentResponse contains the tool call.
      - Write fixture via _write_fixture('tool_call_extraction', {...}).
    """
    raise NotImplementedError(
        "tool_call_extraction probe body filled by PLAN-02 task 2"
    )


async def tool_choice_required() -> Path:
    """Probe 3: tool_choice='required' enforcement on Foundry Responses endpoint.

    Filled by PLAN-02 task 3. Should:
      - Single-tool agent so the result is unambiguous.
      - Run with tool_choice='required'. Record whether the model called the tool.
      - Re-run with tool_choice={'type': 'function', 'function': {'name': '<tool>'}}
        (provider-dict fallback) and record same.
      - Compare to a baseline tool_choice='auto' run with input that does NOT
        naturally invite the tool, to prove 'required' actually changed behavior.
      - Tag every emitted span with probe.run_id + probe.name (no capture.trace_id).
      - Write fixture via _write_fixture('tool_choice_required', {...}).
    """
    raise NotImplementedError(
        "tool_choice_required probe body filled by PLAN-02 task 3"
    )


async def session_rehydration() -> Path:
    """Probe 4: Round-trip an AgentSession / session across two run_stream calls.

    Filled by PLAN-02 task 4. Should:
      - Run turn 1: agent.run_stream(messages=['initial turn'], session=AgentSession()).
      - Capture the stored identifier shape (whatever the SDK exposes:
        AgentSession.id, service_session_id, conversation_id).
      - Run turn 2: agent.run_stream(messages=['follow up'], session=<rehydrated identifier>).
      - Verify continuity by asking turn 2 to reference content from turn 1.
      - Tag every emitted span with probe.run_id + probe.name (no capture.trace_id).
      - Write fixture via _write_fixture('session_rehydration', {...}).
    """
    raise NotImplementedError("session_rehydration probe body filled by PLAN-02 task 4")


async def auth_probe() -> Path:
    """Probe 5: AzureCliCredential + FoundryChatClient + minimal agent invocation.

    Filled by PLAN-02 task 5. Should:
      - Construct FoundryChatClient(credential=AzureCliCredential()).
      - Call AzureCliCredential().get_token('https://cognitiveservices.azure.com/.default')
        (or whichever scope the GA path needs) and record token-acquisition outcome.
      - Run a minimal agent (no tools, single user message) and assert the response
        comes back without auth errors.
      - Document RBAC role names that succeeded — query
        `az role assignment list --assignee <upn> --scope <foundry-resource-id>`
        and capture the role names.
      - Does NOT simulate ManagedIdentityCredential (only the deployed Container App
        can verify that). Documents the credential-class shape difference.
      - Tag every emitted span with probe.run_id + probe.name (no capture.trace_id).
      - Write fixture via _write_fixture('auth_probe', {...}).
    """
    raise NotImplementedError("auth_probe probe body filled by PLAN-02 task 5")


PROBES = {
    "streaming_shape": streaming_shape,
    "tool_call_extraction": tool_call_extraction,
    "tool_choice_required": tool_choice_required,
    "session_rehydration": session_rehydration,
    "auth_probe": auth_probe,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="foundry_probe",
        description="Run a Foundry GA SDK probe against the real endpoint.",
    )
    parser.add_argument(
        "probe_name",
        choices=sorted(PROBES.keys()) + ["all"],
        help="Probe to run, or 'all' to run every probe sequentially.",
    )
    args = parser.parse_args()

    async def _run_one(name: str) -> Path:
        print(f"[probe] running {name} ...", file=sys.stderr)
        path = await PROBES[name]()
        print(f"[probe] {name} -> {path}", file=sys.stderr)
        return path

    async def _run_all() -> list[Path]:
        paths: list[Path] = []
        for name in PROBES:
            paths.append(await _run_one(name))
        return paths

    try:
        if args.probe_name == "all":
            asyncio.run(_run_all())
        else:
            asyncio.run(_run_one(args.probe_name))
    except NotImplementedError as exc:
        print(f"[probe] STUB: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
