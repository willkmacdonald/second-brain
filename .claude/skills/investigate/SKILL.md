---
name: investigate
description: Use when the user asks about the deployed Second Brain system's telemetry -- captures, errors, traces, system health, latency, usage patterns, classifier behavior, admin agent activity -- or asks follow-up questions referring to a recent investigation's output. This is the primary operational support interface for the system.
---

# Investigate Skill

When the user asks a question about the deployed Second Brain system,
invoke `backend/scripts/investigate.py` to get an answer from the live
Investigation Agent. This is the operational support system for the
Second Brain app.

## When to invoke (Rule B)

**Invoke AUTOMATICALLY** when the user's message contains explicit
telemetry vocabulary:

- "errors", "exceptions", "failures", "crashes", "broken"
- "captures", "last capture", "most recent capture", "my last ..."
- "traces", "trace lifecycle", "trace ID"
- "system health", "latency", "p95", "p99", "success rate", "error rate"
- "classifier" (with behavior context), "admin agent" (with behavior
  context), "inbox", "bucket"
- "how many X this week/day/hour"
- "what happened with/to Y"
- "is the system healthy/broken/slow/degraded"

**ALSO invoke AUTOMATICALLY** when the user's message is a follow-up
to a recent investigation in this conversation AND uses pronouns or
references to the previous answer:

- "tell me more about that"
- "why did that happen"
- "step 4" / "the first error" / "that trace"
- "go deeper on ..."
- "what about yesterday instead"
- "show me the component breakdown"

## When to ASK first

If the user's question has partial telemetry vocabulary but could
plausibly be about local code, tests, or development:

> "Do you want me to check the deployed system for this, or look at
> the code/tests?"

Examples of ambiguous questions:
- "why is it slow?" (local tests? deployed backend?)
- "is this working?" (code? deployed?)
- "why did it fail?" (tests? production?)

## When NOT to invoke

Do NOT invoke when the user is clearly asking about:
- The codebase itself ("read file X", "how does function Y work")
- Local tests ("run the tests", "why did pytest fail")
- Git state ("show recent commits", "what's on main")
- Planning, designs, specs, documentation
- Anything outside the deployed Second Brain backend

## How to invoke

Build and run this Bash command:

    cd backend && uv run python scripts/investigate.py "<question>" [flags]

**Thread management:**
- If you remember a thread_id from an earlier investigation in this
  session, add `--thread <thread_id>` to the command
- If the user says "new investigation", "start over", "fresh thread",
  "forget that", or "different topic", add `--new` instead
- If this is the first investigation in the session, omit both flags

**After running:**
1. Extract `[THREAD_ID: <id>]` from the last line of stdout. Remember
   the thread_id value for follow-up calls in this session.
2. Strip the `[THREAD_ID: ...]` line from the output.
3. If you are continuing a previous thread, print one line before the
   agent's answer: `[continuing previous thread]`
4. Show the remaining stdout VERBATIM — the agent's text followed by
   the status line. Do NOT summarize or paraphrase.
5. Show stderr if present (error conditions).

**Error handling:**
- Exit code 1: show stderr. If "az login" is mentioned, suggest
  `! az login`. If "timed out", suggest re-running or simpler question.
- Do NOT retry automatically. The user decides whether to re-run.

## Examples

User: "show me errors from the last 24 hours"
→ Invoke: `scripts/investigate.py "show me errors from the last 24 hours"`

User: "tell me more about the first one"  (after a recent investigation)
→ Invoke: `scripts/investigate.py "tell me more about the first one" --thread <remembered_id>`

User: "new investigation: how many captures this week?"
→ Invoke: `scripts/investigate.py "how many captures this week?" --new`

User: "read the investigation_client.py file"
→ Do NOT invoke. This is a code-reading request, not a system query.

User: "is the backend healthy?"
→ ASK first: "Do you want me to check the deployed system for this,
  or look at the code/tests?"
