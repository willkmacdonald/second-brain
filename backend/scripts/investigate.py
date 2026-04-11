"""CLI wrapper for the Investigation Agent.

Usage:
  cd backend && uv run python scripts/investigate.py "<question>"
  cd backend && uv run python scripts/investigate.py "<question>" --thread <id>
  cd backend && uv run python scripts/investigate.py "<question>" --new

Prerequisites:
  - az login (for Key Vault API key fetch)
  - Deployed backend at https://brain.willmacdonald.com (not local)

Exit code 0 on success, 1 on error. Errors go to stderr.
The last line of stdout is a machine-readable [THREAD_ID: <id>] marker
that Claude Code strips before display and uses for thread continuity.

See second_brain.investigation_client for the HTTP/SSE/formatting logic.
"""

import argparse
import sys

from second_brain.investigation_client import run_investigation


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ask a question to the deployed Investigation Agent.",
    )
    parser.add_argument("question", help="Natural-language question to ask")
    parser.add_argument(
        "--thread",
        default=None,
        help="Continue an existing conversation thread by ID",
    )
    parser.add_argument(
        "--new",
        action="store_true",
        help="Force a new thread (ignores --thread)",
    )
    args = parser.parse_args()

    thread_id = None if args.new else args.thread
    stdout, stderr, exit_code = run_investigation(args.question, thread_id)

    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
