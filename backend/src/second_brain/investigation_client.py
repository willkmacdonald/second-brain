"""Terminal client for the deployed Investigation Agent SSE endpoint.

Used by backend/scripts/investigate.py and the Claude Code skill at
.claude/skills/investigate/SKILL.md. This is the primary operational
support interface for Second Brain -- a natural-language tool for
investigating captures, errors, system health, and usage patterns.

NOT imported by backend runtime code (main.py, API routes, etc.).
Only imported by scripts/investigate.py and tests.

CLI contract:
  cd backend && uv run python scripts/investigate.py "<question>" \
  [--thread <id>] [--new]

Environment prerequisites:
  - az login (DefaultAzureCredential for Key Vault access)
  - uv sync (httpx, azure-identity, azure-keyvault-secrets installed)

Constants:
  - INVESTIGATE_URL: https://brain.willmacdonald.com/api/investigate
  - KEY_VAULT_URL: https://wkm-shared-kv.vault.azure.net/
  - SECRET_NAME: second-brain-api-key
  - TIMEOUT_SECONDS: 60.0
"""

import json
import logging
import time
from dataclasses import dataclass, field

import httpx
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)

INVESTIGATE_URL = "https://brain.willmacdonald.com/api/investigate"
KEY_VAULT_URL = "https://wkm-shared-kv.vault.azure.net/"
SECRET_NAME = "second-brain-api-key"
TIMEOUT_SECONDS = 60.0


@dataclass
class InvestigationResult:
    """Accumulated result from parsing the Investigation Agent's SSE stream."""

    text: str = ""
    tools_called: list[str] = field(default_factory=list)
    thread_id: str | None = None
    elapsed_seconds: float = 0.0
    error: str | None = None
    tool_errors: list[dict] = field(default_factory=list)
    was_continued: bool = False


def _handle_event(event: dict, result: InvestigationResult) -> None:
    """Dispatch one SSE event into the accumulating result.

    Event types handled:
      text       -> append content to result.text
      tool_call  -> add tool name to result.tools_called (deduped)
      tool_error -> append {tool, error} to result.tool_errors
      done       -> set result.thread_id
      error      -> set result.error
      thinking, rate_warning -> ignored (not meaningful for CLI)
    """
    event_type = event.get("type")

    if event_type == "text":
        result.text += event.get("content", "")

    elif event_type == "tool_call":
        tool_name = event.get("tool", "unknown")
        if tool_name not in result.tools_called:
            result.tools_called.append(tool_name)

    elif event_type == "tool_error":
        result.tool_errors.append(
            {
                "tool": event.get("tool", "unknown"),
                "error": event.get("error", ""),
            }
        )

    elif event_type == "done":
        result.thread_id = event.get("thread_id") or None

    elif event_type == "error":
        result.error = event.get("message", "Unknown error")


def format_response(result: InvestigationResult) -> tuple[str, str]:
    """Build the (stdout, stderr) pair for printing.

    stdout layout:
      <agent answer text>
      <blank line>
      [status line]
      <blank line>
      [THREAD_ID: <id>]     <- machine-readable, Claude strips before display

    stderr layout (only if errors present):
      ERROR: <message>
      TOOL ERROR (<tool>): <message>
    """
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    # Agent's answer text
    if result.text:
        stdout_parts.append(result.text.rstrip())

    # Status line
    tools_part = (
        f"tools: {', '.join(result.tools_called)}"
        if result.tools_called
        else "no tools"
    )

    thread_suffix = ""
    if result.thread_id:
        thread_state = "continued" if result.was_continued else "new"
        thread_short = (
            result.thread_id[:16] + "..."
            if len(result.thread_id) > 16
            else result.thread_id
        )
        thread_suffix = f" | thread: {thread_short} ({thread_state})"

    tool_errors_suffix = ""
    if result.tool_errors:
        tool_errors_suffix = f" | {len(result.tool_errors)} tool error(s)"

    status = (
        f"[{tools_part}{thread_suffix}"
        f" | {result.elapsed_seconds:.1f}s{tool_errors_suffix}]"
    )
    stdout_parts.append(status)

    # Machine-readable thread_id marker (last line)
    if result.thread_id:
        stdout_parts.append(f"[THREAD_ID: {result.thread_id}]")

    # Errors to stderr
    if result.error:
        stderr_parts.append(f"ERROR: {result.error}")

    for tool_err in result.tool_errors:
        stderr_parts.append(f"TOOL ERROR ({tool_err['tool']}): {tool_err['error']}")

    stdout_text = "\n\n".join(stdout_parts) + "\n" if stdout_parts else ""
    stderr_text = "\n".join(stderr_parts) + "\n" if stderr_parts else ""
    return stdout_text, stderr_text


def fetch_api_key() -> str:
    """Fetch the deployed backend's API key from Azure Key Vault.

    Uses DefaultAzureCredential which picks up az login, managed identity,
    or environment credentials automatically.

    Raises RuntimeError with actionable message if auth is missing.
    """
    try:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
        secret = client.get_secret(SECRET_NAME)
        return secret.value
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch API key from Key Vault ({SECRET_NAME}). "
            f"Check that you are logged in with 'az login'. Original: {exc}"
        ) from exc


def stream_investigation(
    question: str,
    thread_id: str | None,
    api_key: str,
    *,
    url: str = INVESTIGATE_URL,
    timeout: float = TIMEOUT_SECONDS,
) -> InvestigationResult:
    """POST the question to the Investigation Agent, parse the SSE stream.

    This function is pure: no stdout, no stderr, no global state. Callers
    get back a structured InvestigationResult and decide what to print.

    Args:
        question: Natural-language question to ask the agent.
        thread_id: Existing thread ID for multi-turn continuation, or None.
        api_key: Bearer token for Authorization header.
        url: Override the endpoint URL (useful for testing).
        timeout: Request timeout in seconds (default 60, matches backend).

    Returns:
        InvestigationResult with accumulated text, tools, thread_id, etc.
    """
    result = InvestigationResult(was_continued=thread_id is not None)
    body: dict = {"question": question}
    if thread_id:
        body["thread_id"] = thread_id

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    start = time.monotonic()
    try:
        with (
            httpx.Client(timeout=timeout) as client,
            client.stream("POST", url, headers=headers, json=body) as response,
        ):
            if response.status_code != 200:
                result.error = (
                    f"HTTP {response.status_code}: "
                    f"{response.read().decode('utf-8', errors='replace')[:500]}"
                )
                result.elapsed_seconds = time.monotonic() - start
                return result

            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload_str = line[6:]  # strip "data: " prefix
                try:
                    event = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue
                _handle_event(event, result)

    except httpx.TimeoutException:
        result.error = f"Request timed out after {timeout}s."
    except httpx.HTTPError as exc:
        result.error = f"HTTP error: {exc}"

    result.elapsed_seconds = time.monotonic() - start
    return result


def run_investigation(
    question: str,
    thread_id: str | None = None,
) -> tuple[str, str, int]:
    """End-to-end: fetch key, stream, format.

    Returns:
        (stdout_text, stderr_text, exit_code)
        exit_code is 0 on success, 1 on any error.
    """
    try:
        api_key = fetch_api_key()
    except RuntimeError as exc:
        return ("", f"ERROR: {exc}\n", 1)

    result = stream_investigation(question, thread_id, api_key)
    stdout, stderr = format_response(result)
    exit_code = 1 if result.error or result.tool_errors else 0
    return stdout, stderr, exit_code
