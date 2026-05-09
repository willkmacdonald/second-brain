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
import threading
import uuid
from contextvars import ContextVar
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
# Streaming uses agent.run(stream=True) returning ResponseStream, NOT agent.run_stream().
# tool_choice is passed via options=ChatOptions(tool_choice=...), NOT as a direct kwarg.
from agent_framework import Agent, AgentResponse, AgentSession, ChatOptions, tool
from agent_framework.observability import enable_instrumentation
from agent_framework_foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.trace import Span

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "foundry-probe"
)

# Per-probe context for span tagging. ContextVars are async-safe — every
# span created on the probe's task tree will see these values.
_probe_run_id: ContextVar[str] = ContextVar("probe_run_id", default="")
_probe_name: ContextVar[str] = ContextVar("probe_name", default="")

_probe_processor_installed = threading.Event()
_probe_telemetry_configured = threading.Event()


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
        project_endpoint=endpoint,
        model=model,
        credential=AzureCliCredential(),
    )


def _setup_probe_telemetry() -> None:
    """Configure Azure Monitor + framework instrumentation BEFORE any SDK calls.

    Must be called at module entry, before any FoundryChatClient or Agent is
    constructed. Without this, get_tracer_provider() returns a ProxyTracerProvider
    where add_span_processor is missing — silent no-op for span tagging.

    Fails fast (sys.exit(2)) if APPLICATIONINSIGHTS_CONNECTION_STRING is not set
    or if the TracerProvider after configuration does not expose add_span_processor.
    """
    if _probe_telemetry_configured.is_set():
        return
    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not conn:
        print(
            "FATAL: APPLICATIONINSIGHTS_CONNECTION_STRING not set — probe spans "
            "cannot export to App Insights, tagging contract cannot be honored.",
            file=sys.stderr,
        )
        sys.exit(2)

    configure_azure_monitor(
        logger_name="second_brain.probe",
        connection_string=conn,
        enable_live_metrics=False,
    )
    enable_instrumentation()

    provider = otel_trace.get_tracer_provider()
    if not callable(getattr(provider, "add_span_processor", None)):
        print(
            f"FATAL: TracerProvider after configure_azure_monitor() does not "
            f"expose add_span_processor (got {type(provider).__name__}). "
            "Probe span tagging cannot be installed. Refusing to run probes — "
            "would produce untagged Foundry traces in production App Insights.",
            file=sys.stderr,
        )
        sys.exit(2)
    _probe_telemetry_configured.set()


class ProbeTagSpanProcessor(SpanProcessor):
    """Tag every span CREATED within a probe run with probe.run_id + probe.name.

    Mirrors the pattern of CaptureTraceSpanProcessor (backend/src/second_brain/
    observability/span_processor.py) — read ContextVars in on_start so the
    attribute lands on the span at creation time, regardless of who creates
    it (framework code, HTTP instrumentation, etc.).

    Importantly we do NOT set capture.trace_id — production KQL filters
    on Properties.['capture.trace_id'] (or capture_trace_id) and probes
    must remain naturally invisible to capture-correlated queries.
    """

    def on_start(self, span: Span, parent_context: object = None) -> None:
        run_id = _probe_run_id.get()
        name = _probe_name.get()
        if run_id:
            span.set_attribute("probe.run_id", run_id)
        if name:
            span.set_attribute("probe.name", name)

    def on_end(self, span: Span) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _ensure_probe_processor_installed() -> None:
    """Install the probe span processor on the current TracerProvider exactly once.

    Fails fast (sys.exit(2)) if add_span_processor is somehow missing at install
    time (race against telemetry setup). No silent no-op — would produce
    untagged Foundry traces in production App Insights.
    """
    if _probe_processor_installed.is_set():
        return
    provider = otel_trace.get_tracer_provider()
    add = getattr(provider, "add_span_processor", None)
    if not callable(add):
        print(
            f"FATAL: cannot install ProbeTagSpanProcessor — provider "
            f"{type(provider).__name__} has no add_span_processor. "
            "_setup_probe_telemetry() may not have been called, or telemetry "
            "was reset between calls.",
            file=sys.stderr,
        )
        sys.exit(2)
    add(ProbeTagSpanProcessor())
    _probe_processor_installed.set()


@tool
async def echo_back(message: str) -> str:
    """Probe stub tool: echo the input message back. Used by streaming_shape and tool_call_extraction probes."""
    return f"echo: {message}"


async def _maybe_delete_session(agent: Agent, session: AgentSession | None) -> bool:
    """Try to delete probe-created sessions if the SDK exposes deletion. Return True if deleted."""
    if session is None:
        return False
    # GA SDK API for session deletion is not documented — try multiple shapes
    for method_name in ("delete_session", "delete_thread", "delete"):
        method = getattr(agent, method_name, None)
        if callable(method):
            try:
                result = method(session)
                if asyncio.iscoroutine(result):
                    await result
                return True
            except Exception:
                continue
    return False


# ========================================================================
# Module-entry telemetry setup — MUST happen before any probe definition
# ========================================================================
_setup_probe_telemetry()


# ========================================================================
# Probe implementations
# ========================================================================


async def streaming_shape() -> Path:
    """Probe 1: AgentResponseUpdate field/type/order.

    Constructs a 1-tool stub agent (single tool: echo_back with @tool).
    Runs agent.run(stream=True) with input that forces 1 tool call.
    Collects every AgentResponseUpdate yielded into a JSON-serializable list.
    Tags every emitted span with probe.run_id + probe.name (no capture.trace_id).
    Optionally deletes the agent's session at end-of-run if SDK exposes deletion.
    Writes fixture via _write_fixture('streaming_shape', {...}).
    """
    # 1. Tagging FIRST — set ContextVars + install processor before any SDK construction
    run_id = _new_run_id()
    _probe_run_id.set(run_id)
    _probe_name.set("streaming_shape")
    _ensure_probe_processor_installed()

    # 2. Now construct client/agent — every span they create gets tagged
    client = _build_client()
    agent = Agent(
        client=client,
        instructions="You are a probe agent. When the user asks you to echo something, call echo_back.",
        tools=[echo_back],
    )

    updates: list[dict[str, Any]] = []
    session = AgentSession()
    # GA SDK: agent.run(stream=True) returns a ResponseStream (async iterable)
    async for update in agent.run(
        messages="Please echo back: probe one",
        session=session,
        stream=True,
    ):
        updates.append(
            {
                "type": type(update).__name__,
                "repr": repr(update),
                # Capture every public attribute on the update so Phase 24 can see field shape
                "fields": {
                    k: repr(getattr(update, k, None))
                    for k in dir(update)
                    if not k.startswith("_") and not callable(getattr(update, k, None))
                },
            }
        )

    deleted = await _maybe_delete_session(agent, session)
    return _write_fixture(
        "streaming_shape",
        {
            "probe": {"run_id": run_id},
            "update_count": len(updates),
            "updates": updates,
            "thread_deleted_after_run": deleted,
        },
    )


async def tool_call_extraction() -> Path:
    """Probe 2: AgentResponse tool-call extraction path.

    Uses same 1-tool stub agent as streaming_shape.
    Runs agent.run(messages=[...]) (NON-streaming).
    Captures the raw AgentResponse object structure (messages, content blocks,
    metadata, tool_calls top-level if present).
    Documents via fixture which path inside AgentResponse contains the tool call.
    Writes fixture via _write_fixture('tool_call_extraction', {...}).
    """
    # 1. Tagging FIRST
    run_id = _new_run_id()
    _probe_run_id.set(run_id)
    _probe_name.set("tool_call_extraction")
    _ensure_probe_processor_installed()

    # 2. Then construct client/agent
    client = _build_client()
    agent = Agent(
        client=client,
        instructions="You are a probe agent. When the user asks you to echo something, call echo_back.",
        tools=[echo_back],
    )

    session = AgentSession()
    response: AgentResponse = await agent.run(
        messages="Please echo back: probe two",
        session=session,
    )

    # Capture EVERY traversal path that might contain tool calls. Phase 24 reads
    # this fixture to learn the canonical extraction path.
    payload: dict[str, Any] = {
        "probe": {"run_id": run_id},
        "response_type": type(response).__name__,
        "response_repr": repr(response),
        "response_fields": {
            k: repr(getattr(response, k, None))
            for k in dir(response)
            if not k.startswith("_") and not callable(getattr(response, k, None))
        },
        # Try common locations
        "top_level_tool_calls": getattr(response, "tool_calls", None) is not None,
        "messages_present": getattr(response, "messages", None) is not None,
    }

    # Walk messages[].content[] looking for tool-call shaped blocks
    if hasattr(response, "messages") and response.messages:
        payload["messages_walk"] = []
        for i, msg in enumerate(response.messages):
            payload["messages_walk"].append(
                {
                    "index": i,
                    "type": type(msg).__name__,
                    "repr": repr(msg),
                    "fields": {
                        k: repr(getattr(msg, k, None))
                        for k in dir(msg)
                        if not k.startswith("_") and not callable(getattr(msg, k, None))
                    },
                }
            )

    await _maybe_delete_session(agent, session)
    return _write_fixture("tool_call_extraction", payload)


async def tool_choice_required() -> Path:
    """Probe 3: tool_choice='required' enforcement on Foundry Responses endpoint.

    Single-tool agent so the result is unambiguous.
    Runs with tool_choice='required'. Records whether the model called the tool.
    Re-runs with tool_choice={'type': 'function', 'function': {'name': '<tool>'}}
    (provider-dict fallback) and records same.
    Compares to a baseline tool_choice='auto' run with input that does NOT
    naturally invite the tool, to prove 'required' actually changed behavior.
    Tags every emitted span with probe.run_id + probe.name (no capture.trace_id).
    Writes fixture via _write_fixture('tool_choice_required', {...}).
    """
    # 1. Tagging FIRST
    run_id = _new_run_id()
    _probe_run_id.set(run_id)
    _probe_name.set("tool_choice_required")
    _ensure_probe_processor_installed()

    # 2. Then construct client/agent
    client = _build_client()
    agent = Agent(
        client=client,
        instructions="You are a probe agent. The user is testing forced tool calls. Do NOT call any tool unless tool_choice forces you to.",
        tools=[echo_back],
    )

    # Input deliberately worded so the model would NOT naturally call echo_back under tool_choice='auto'
    baseline_input = "Tell me a fact about the moon."

    observations: dict[str, Any] = {"probe": {"run_id": run_id}, "trials": {}}

    # Trial 1: tool_choice='auto' (baseline)
    # GA SDK: tool_choice passed via options=ChatOptions(tool_choice=...)
    try:
        s1 = AgentSession()
        r1 = await agent.run(
            messages=baseline_input,
            session=s1,
            options=ChatOptions(tool_choice="auto"),
        )
        observations["trials"]["auto"] = {
            "raised": False,
            "response_repr": repr(r1)[:2000],
            "fields_seen": sorted(k for k in dir(r1) if not k.startswith("_")),
        }
        await _maybe_delete_session(agent, s1)
    except Exception as exc:
        observations["trials"]["auto"] = {
            "raised": True,
            "exc_type": type(exc).__name__,
            "exc_str": str(exc),
        }

    # Trial 2: tool_choice='required'
    try:
        s2 = AgentSession()
        r2 = await agent.run(
            messages=baseline_input,
            session=s2,
            options=ChatOptions(tool_choice="required"),
        )
        observations["trials"]["required"] = {
            "raised": False,
            "response_repr": repr(r2)[:2000],
            "fields_seen": sorted(k for k in dir(r2) if not k.startswith("_")),
        }
        await _maybe_delete_session(agent, s2)
    except Exception as exc:
        observations["trials"]["required"] = {
            "raised": True,
            "exc_type": type(exc).__name__,
            "exc_str": str(exc),
        }

    # Trial 3: provider-dict pinning by name
    try:
        s3 = AgentSession()
        r3 = await agent.run(
            messages=baseline_input,
            session=s3,
            options=ChatOptions(
                tool_choice={"type": "function", "function": {"name": "echo_back"}}
            ),
        )
        observations["trials"]["provider_dict"] = {
            "raised": False,
            "response_repr": repr(r3)[:2000],
            "fields_seen": sorted(k for k in dir(r3) if not k.startswith("_")),
        }
        await _maybe_delete_session(agent, s3)
    except Exception as exc:
        observations["trials"]["provider_dict"] = {
            "raised": True,
            "exc_type": type(exc).__name__,
            "exc_str": str(exc),
        }

    return _write_fixture("tool_choice_required", observations)


async def session_rehydration() -> Path:
    """Probe 4: Round-trip an AgentSession across two streaming run calls.

    Runs turn 1: agent.run(stream=True, session=AgentSession()).
    Captures the stored identifier shape (whatever the SDK exposes:
    AgentSession.session_id, service_session_id).
    Runs turn 2: agent.run(stream=True, session=<same session>).
    Verifies continuity by asking turn 2 to reference content from turn 1.
    Tags every emitted span with probe.run_id + probe.name (no capture.trace_id).
    Writes fixture via _write_fixture('session_rehydration', {...}).
    """
    # 1. Tagging FIRST
    run_id = _new_run_id()
    _probe_run_id.set(run_id)
    _probe_name.set("session_rehydration")
    _ensure_probe_processor_installed()

    # 2. Then construct client/agent
    client = _build_client()
    agent = Agent(
        client=client,
        instructions="You are a probe agent. Remember details from prior turns and quote them back when asked.",
        tools=[],
    )

    # Turn 1
    session = AgentSession()
    turn_one_updates: list[str] = []
    async for upd in agent.run(
        messages="Remember the magic word PINEAPPLE for later.",
        session=session,
        stream=True,
    ):
        turn_one_updates.append(repr(upd)[:500])

    # Capture every plausible identifier shape on the session object
    identifier_shape = {
        "type": type(session).__name__,
        "fields": {
            k: repr(getattr(session, k, None))
            for k in dir(session)
            if not k.startswith("_") and not callable(getattr(session, k, None))
        },
    }

    # Turn 2 — round-trip the SAME session object
    turn_two_updates: list[str] = []
    async for upd in agent.run(
        messages="What was the magic word I told you to remember?",
        session=session,
        stream=True,
    ):
        turn_two_updates.append(repr(upd)[:500])

    deleted = await _maybe_delete_session(agent, session)

    return _write_fixture(
        "session_rehydration",
        {
            "probe": {"run_id": run_id},
            "turn_one_updates": turn_one_updates,
            "thread_identifier_shape": identifier_shape,
            "turn_two_updates": turn_two_updates,
            "thread_deleted_after_run": deleted,
        },
    )


async def auth_probe() -> Path:
    """Probe 5: AzureCliCredential + FoundryChatClient + minimal agent invocation.

    Constructs FoundryChatClient(credential=AzureCliCredential()).
    Calls AzureCliCredential().get_token('https://cognitiveservices.azure.com/.default')
    and records token-acquisition outcome.
    Runs a minimal agent (no tools, single user message) and asserts the response
    comes back without auth errors.
    Documents RBAC role names that succeeded.
    Does NOT simulate ManagedIdentityCredential (only the deployed Container App
    can verify that). Documents the credential-class shape difference.
    Tags every emitted span with probe.run_id + probe.name (no capture.trace_id).
    Writes fixture via _write_fixture('auth_probe', {...}).
    """
    import subprocess

    # 1. Tagging FIRST — even before token acquisition (which may emit spans)
    run_id = _new_run_id()
    _probe_run_id.set(run_id)
    _probe_name.set("auth_probe")
    _ensure_probe_processor_installed()

    cred = AzureCliCredential()

    # Token acquisition outcome (does NOT exercise managed identity — design note)
    scope = "https://cognitiveservices.azure.com/.default"
    token_outcome: dict[str, Any]
    try:
        token = cred.get_token(scope)
        token_outcome = {
            "scope": scope,
            "acquired": True,
            "expires_on": getattr(token, "expires_on", None),
            "token_length": len(token.token) if token and token.token else 0,
        }
    except Exception as exc:
        token_outcome = {
            "scope": scope,
            "acquired": False,
            "exc_type": type(exc).__name__,
            "exc_str": str(exc),
        }

    # RBAC role names — query az CLI; capture stdout
    rbac_outcome: dict[str, Any]
    try:
        cli_proc = subprocess.run(
            ["az", "ad", "signed-in-user", "show", "--query", "id", "-o", "tsv"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        user_id = cli_proc.stdout.strip()
        endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "") or os.environ.get(
            "AZURE_AI_PROJECT_ENDPOINT", ""
        )
        roles_proc = subprocess.run(
            [
                "az",
                "role",
                "assignment",
                "list",
                "--assignee",
                user_id,
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        rbac_outcome = {
            "user_id": user_id,
            "endpoint": endpoint,
            "role_assignments_raw": roles_proc.stdout[:8000],
        }
    except Exception as exc:
        rbac_outcome = {
            "raised": True,
            "exc_type": type(exc).__name__,
            "exc_str": str(exc),
        }

    # Minimal agent invocation — client/agent constructed AFTER tagging is active
    invocation_outcome: dict[str, Any]
    try:
        inv_endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT") or os.environ.get(
            "AZURE_AI_PROJECT_ENDPOINT", ""
        )
        client = FoundryChatClient(
            project_endpoint=inv_endpoint,
            model=os.environ.get("FOUNDRY_MODEL", "gpt-4o"),
            credential=cred,
        )
        agent = Agent(
            client=client,
            instructions="Reply with a single short sentence.",
            tools=[],
        )
        s = AgentSession()
        response = await agent.run(
            messages="Say hello.",
            session=s,
        )
        invocation_outcome = {
            "succeeded": True,
            "response_type": type(response).__name__,
            "response_repr": repr(response)[:2000],
        }
        await _maybe_delete_session(agent, s)
    except Exception as exc:
        invocation_outcome = {
            "succeeded": False,
            "exc_type": type(exc).__name__,
            "exc_str": str(exc),
        }

    return _write_fixture(
        "auth_probe",
        {
            "probe": {"run_id": run_id},
            "credential_class": "AzureCliCredential",
            "deployed_credential_class_note": (
                "Container Apps uses ManagedIdentityCredential — this probe does NOT "
                "exercise that path. Verified post-deploy in Phase 24 day-after UAT."
            ),
            "token_acquisition": token_outcome,
            "rbac": rbac_outcome,
            "invocation": invocation_outcome,
        },
    )


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

    if args.probe_name == "all":
        asyncio.run(_run_all())
    else:
        asyncio.run(_run_one(args.probe_name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
