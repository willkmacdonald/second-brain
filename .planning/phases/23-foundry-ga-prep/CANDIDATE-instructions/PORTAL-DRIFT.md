# Portal vs canonicalized-doc drift report

**Investigation agent** (`asst_5feSWWTMA8rBSUyQo6aSCsEJ`): canonicalized doc exists at `docs/foundry/investigation-agent-instructions.md` since Phase 17.1 (2026-04-09). Portal text exported 2026-05-09.

## Diff summary

Total hunks: 3
Drift class: regressive (portal lost content from canonicalized)

The portal text is semantically identical to the canonicalized doc for the base 6 tools and all formatting/behavioral rules, BUT:

1. **All markdown formatting stripped.** Portal text has no `##` headings, no numbered lists, no bullet points, no backtick code formatting, no fenced code blocks. The Foundry portal Instructions field appears to strip markdown structure when the text is pasted in, flattening it to plain text paragraphs.
2. **Entire "Evaluation Tools" section missing.** The canonicalized doc was updated in Phase 21.1 (2026-04-25) to add 3 evaluation tools (run_classifier_eval, run_admin_eval, get_eval_results) with full documentation, examples, and formatting rules. The portal still says "six tools" (the original 4 telemetry + 2 feedback). The portal was never updated with the Phase 21.1 additions.
3. **Entire "Tracing Configuration" section missing.** The canonicalized doc includes a section about `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true`. Portal lacks it.
4. **Signal type naming discrepancy.** Portal uses `hitlbucket`, `errandreroute`, `thumbsup`, `thumbsdown` (no underscores). Canonicalized doc uses `hitl_bucket`, `errand_reroute`, `thumbs_up`, `thumbs_down` (with underscores). The underscored form matches the Python enum values in the backend code.

## Per-hunk reconciliation

### Hunk 1 (formatting throughout)

**Canonicalized text:**
```
## Tone & Style

- Clinical, precise, data-focused. No casual filler ("Great question!", "Let
  me check!", emojis). Lead with the answer.
- Default to concise narrative summaries. Offer detail on follow-up, don't
  dump everything at once.
```

**Portal text:**
```
Tone & Style
Clinical, precise, data-focused. No casual filler ("Great question!", "Let me check!", emojis). Lead with the answer.
Default to concise narrative summaries. Offer detail on follow-up, don't dump everything at once.
```

**Decision:** canonicalized wins

**Reasoning:** Markdown formatting (`##` headings, `-` bullets, numbered lists, backtick code, fenced blocks) provides structure that aids agent comprehension and is standard in the repo's instruction files; the portal stripped it on paste.

### Hunk 2 (missing Evaluation Tools section -- lines 192-287 in canonicalized)

**Canonicalized text:**
```
## Evaluation Tools

You have three tools for managing evaluation runs. Eval scoring, run records, and result storage are handled by Azure AI Foundry's native evaluation service. ...

### run_classifier_eval
...
### run_admin_eval
...
### get_eval_results
...
### Formatting eval results
...
### Eval usage flow
...
```

**Portal text:**
(section entirely absent; portal says "six tools" instead of "nine tools")

**Decision:** canonicalized wins

**Reasoning:** Phase 21.1 (2026-04-25) added 3 evaluation tools to the Investigation agent with full documentation. The canonicalized doc was updated; the portal was not. The eval tools are live in the deployed backend and the agent needs their documentation to use them correctly. The reconciled file includes the full Evaluation Tools section from the canonicalized doc.

### Hunk 3 (missing Tracing Configuration section -- lines 289-291 in canonicalized)

**Canonicalized text:**
```
## Tracing Configuration

The Container App must have `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true` set as an environment variable for the Foundry Tracing page to show Input/Output columns with full prompt and response content. Without this, the Tracing page shows agent runs but with empty content columns.
```

**Portal text:**
(section entirely absent)

**Decision:** canonicalized wins

**Reasoning:** This operational note was added as part of Phase 21.1's tracing work. It documents a required env var for full Foundry Tracing visibility. Portal was not updated.

### Signal type naming (minor, within Hunk 1 scope)

**Canonicalized text:**
```
Signal type (recategorize, hitl_bucket, errand_reroute, thumbs_up, thumbs_down)
```

**Portal text:**
```
Signal type (recategorize, hitlbucket, errandreroute, thumbsup, thumbsdown)
```

**Decision:** canonicalized wins

**Reasoning:** The underscored form (`hitl_bucket`, `errand_reroute`, `thumbs_up`, `thumbs_down`) matches the Python signal type enum values in `backend/src/second_brain/models/documents.py`. The portal text dropped the underscores, likely during manual editing.

## Investigation reconciled file

The reconciled file at `./investigation.md` reflects all "canonicalized wins" decisions. It is the canonicalized doc verbatim (with HTML comment header replaced by the reconciliation frontmatter). No portal-only additions were found worth merging. Phase 24 task group 23.1 promotes that file as `backend/src/second_brain/agents/instructions/investigation.md` and the portal instructions field becomes display-only.

## Classifier and Admin

**Classifier** (`asst_Fnjkq5RVrvdFIOSqbreAwxuq`): no canonicalized doc exists. Portal text IS the source, exported verbatim to `./classifier.md`. Phase 24 task group 23.3 promotes that file.

**Admin** (`asst_17oFXNHNq7kzmspQGMUrgERM`): no canonicalized doc exists. Portal text IS the source, exported verbatim to `./admin.md`. Phase 24 task group 23.2 promotes that file.

## Phase 24 implication (D-02)

After Phase 24 task groups 23.1/23.2/23.3 promote these three files, repo markdown is the SOLE source of truth for agent instructions (per D-02). Portal instruction fields become display-only. No more portal hot-edits.

## Verbatim angle-bracket allow-list

The following angle-bracket patterns in `investigation.md` are verbatim runtime template references used by the agent when rendering output, NOT unfilled plan placeholders:

| File | Line | Snippet | Reason |
|------|------|---------|--------|
| investigation.md | 62 | `<time_range>` | Runtime variable in agent output template |
| investigation.md | 63 | `<total_count>`, `<time_range>` | Runtime variable in agent output template |
| investigation.md | 64 | `<total_count>`, `<time_range>`, `<returned_count>` | Runtime variable in agent output template |
| investigation.md | 76 | `<capture_trace_id_short>` | Runtime variable in agent output template |
| investigation.md | 79 | `<id1>`, `<id2>` | Runtime variable in agent output template |
