Ask a question to the deployed Investigation Agent about the Second Brain
system's captures, errors, system health, or usage patterns. This is the
primary operational support interface for the system.

## How to execute

Run this Bash command:

    cd backend && uv run python scripts/investigate.py "$ARGUMENTS" [flags]

Where:
- `$ARGUMENTS` is the user's question, quoted exactly as they wrote it
- Add `--thread <last_thread_id>` IF you remember a thread_id from a
  previous investigation in this Claude Code session
- Add `--new` IF the user passed `--new` in the slash command invocation,
  OR if the user said "new investigation", "start over", "fresh thread",
  or "different topic"
- Omit both flags if this is the first investigation in the session

## After running

1. Read stdout. The LAST line will match `[THREAD_ID: <id>]` — extract
   the thread ID value and remember it for the next investigation call
   in this session. Strip this line from the output before showing it to
   the user.
2. Show the remaining stdout to the user VERBATIM. Do NOT summarize,
   interpret, or rephrase the agent's answer. The agent's text IS the
   deliverable — your job is to relay it.
3. If stderr contains content, show it below the agent's answer, clearly
   separated. These are error conditions.

## Error handling

- Exit code 1 means something failed. Show stderr verbatim.
- If stderr mentions "az login", tell the user: "You need to refresh your
  Azure credentials. Run `! az login` in this terminal."
- If stderr mentions "timed out", suggest the user re-run with a simpler
  question or try again in a moment.
- If stderr mentions "HTTP 503", the Investigation Agent or App Insights
  is down. Suggest checking /health endpoint.

## Important

- NEVER modify the question before passing it to the script. Pass it
  exactly as the user wrote it — the Investigation Agent handles natural
  language interpretation.
- NEVER add your own analysis or commentary to the agent's response.
  Show the agent's text, then the status line, then stop.
- The status line at the bottom of stdout (e.g., `[tools: recent_errors
  | thread: ... | 2.3s]`) is useful context — always show it.
