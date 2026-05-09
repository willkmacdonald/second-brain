# Eval module inventory + EvalAgentInvoker facade scope

**Scope source:** `docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md` Section "Eval invocation facade (REQUIRED scope for Phases 23.2 and 23.3)".
**Phase 24 consumer:** task group 23.2 introduces the facade; task group 23.3 deletes the RC implementation.

## Existing module surface (RC, pre-migration)

| File | Lines | Role |
|---|---|---|
| `backend/src/second_brain/eval/runner.py` | 375 | Orchestration: pulls test cases from Cosmos GoldenDataset, calls classifier/admin client, computes metrics, writes results to Cosmos EvalResults |
| `backend/src/second_brain/eval/metrics.py` | 176 | Pure functions: `compute_classifier_metrics`, `compute_confidence_calibration`, `compute_admin_metrics`. NO I/O. |
| `backend/src/second_brain/eval/dry_run_tools.py` | 151 | Stub @tool implementations for eval-only runs (don't actually write Cosmos). `EvalClassifierTools` and `DryRunAdminTools`. |
| `backend/src/second_brain/eval/foundry.py` | 1558 | Foundry-specific helpers: custom evaluator registration, dataset export/upload, canary target evaluation, app-mediated artifact generation, eval run creation/polling/results. (Per Phase 21.1-01 design). |
| `backend/src/second_brain/api/eval.py` | 179 | HTTP endpoint `/api/eval/run` triggering classifier or admin eval; `/api/eval/status/{run_id}` for polling; `/api/eval/results` for result retrieval. |
| `backend/scripts/seed_golden_dataset.py` | 236 | Seeds GoldenDataset container from exported Inbox items. Two subcommands: export + import. |

## RC-shaped call sites (the facade replaces these)

Two call sites in `eval/runner.py` directly invoke the agent client with RC types. These break when the underlying agent becomes a GA `Agent` (no `client.get_response` method, no `Message`/`ChatOptions` types).

### Call site 1 — Classifier (eval/runner.py:133-149, current commit)

Verbatim from current code:

```python
                messages = [Message(role="user", text=case["inputText"])]
                options = ChatOptions(
                    tools=[eval_tools.file_capture],
                    tool_choice={
                        "mode": "required",
                        "required_function_name": "file_capture",
                    },
                )

                await _call_with_retry(
                    lambda m=messages, o=options: classifier_client.get_response(
                        messages=m, options=o
                    ),
                    run_id=run_id,
                    case_index=i,
                    runs_dict=runs_dict,
                )
```

Behavior contract:
- Input: `case["inputText"]` (string)
- Tool registered: `eval_tools.file_capture` (a method on a per-case `EvalClassifierTools` instance)
- tool_choice: provider-dict with `mode=required, required_function_name='file_capture'`
- Side effect captured: `eval_tools.last_bucket` and `eval_tools.last_confidence` are set inside the tool stub when the model calls it
- Output read: `eval_tools.last_bucket`, `eval_tools.last_confidence` (NOT the response object)

### Call site 2 — Admin (eval/runner.py:278-294, current commit)

Verbatim from current code:

```python
                messages = [Message(role="user", text=case["inputText"])]
                options = ChatOptions(
                    tools=[
                        dry_run_tools.add_errand_items,
                        dry_run_tools.add_task_items,
                        dry_run_tools.get_routing_context,
                    ],
                )

                await _call_with_retry(
                    lambda m=messages, o=options: admin_client.get_response(
                        messages=m, options=o
                    ),
                    run_id=run_id,
                    case_index=i,
                    runs_dict=runs_dict,
                )
```

Behavior contract:
- Input: `case["inputText"]` (string)
- Tools registered: `dry_run_tools.add_errand_items`, `dry_run_tools.add_task_items`, `dry_run_tools.get_routing_context`
- tool_choice: not set (defaults to `auto` -- the admin agent decides which tools to call)
- Side effect captured: `dry_run_tools.captured_destinations` and `dry_run_tools.captured_tasks` are populated inside the tool stubs when the model calls them
- Output read: `dry_run_tools.captured_destinations[0]` (primary destination), `dry_run_tools.captured_tasks` (task items)

### Admin metric shape — flat per-destination accuracy, NOT separate precision/recall (round-15 P-01)

**Phase 24 task group 23.2 must preserve the runner's existing flat-accuracy contract for `per_destination`.** Do NOT add separate precision/recall keys to `per_destination` without first checking whether the design's L568 wording ("per-destination precision/recall") was strict.

`compute_admin_metrics` at `backend/src/second_brain/eval/metrics.py:137-176` writes:

```python
per_destination[dest] = sum(1 for c in correctness_list if c) / len(correctness_list)
```

That is a single accuracy float per destination (when grouped by `expected_destination`, this equals recall). The migration design at line 568 says "per-destination precision/recall" -- two metrics per class -- but the runner produces one. The asymmetry is internally consistent because the Phase 24 +/-5pp class-specific drop check operates on whatever the runner emits on BOTH sides of the migration. A pre-migration baseline of flat accuracy is compared against a post-migration value of flat accuracy; the drop check is well-defined.

**Action for Phase 24 task group 23.2 planner:** if you want true per-destination precision/recall, that is a metric-runner change in `eval/metrics.py` (and a corresponding baseline re-run via the Phase 23 baseline task), NOT a facade change. Track it as a separate follow-up item -- do not silently widen the runner's contract while introducing the facade.

## EvalAgentInvoker facade — Phase 24 task group 23.2 scope

Per design D-07's explicit-justification template, the facade is a temporary seam justified as:

1. **Which framework primitive was the candidate?** `Agent.run(messages)` direct.
2. **What capability does the custom code provide that the primitive does not?** Translation between eval cases (input string + expected label) and `agent.run()` call shape, AND adapting the response back to the eval runner's existing per-case dict format.
3. **Why can't this be solved by middleware / context provider / tool / configuration?** It can -- but during the migration window we have BOTH RC and GA call shapes alive (classifier on RC until 23.3 commits, admin on GA after 23.2 commits). The facade hides that split for one migration window.
4. **Permanent answer or temporary bridge with a deletion trigger?** Temporary. Deletion trigger: end of Phase 24 task group 23.3 (final cleanup commit), when no caller uses the RC implementation.

### Interface

```python
# eval/invoker.py (NEW in Phase 24 task group 23.2)
from typing import Protocol

class EvalAgentInvoker(Protocol):
    async def invoke_classifier(
        self,
        input_text: str,
        tools_instance: "EvalClassifierTools",
    ) -> None:
        """Run one classifier eval case. Side-effects on tools_instance.last_bucket / last_confidence."""
        ...

    async def invoke_admin(
        self,
        input_text: str,
        tools_instance: "DryRunAdminTools",
        routing_context: str,
    ) -> None:
        """Run one admin eval case. Side-effects captured inside dry-run tools."""
        ...
```

### Two implementations (during Phase 24 migration window)

- `RCEvalAgentInvoker` -- wraps current `client.get_response(messages, options=ChatOptions(...))`. Used for whichever agent has not yet been migrated. Deleted at end of Phase 24 task group 23.3.
- `GAEvalAgentInvoker` -- wraps `agent.run(messages=[...])`, parses `AgentRunResponse` to extract tool-call side effects per the path documented in `backend/tests/fixtures/foundry-probe/tool_call_extraction.json` (PLAN-02 output).

### Wire-up in eval/runner.py

The single change in runner.py is replacing the two RC-shaped call blocks with `await invoker.invoke_classifier(...)` / `await invoker.invoke_admin(...)`. Everything else (test-case iteration, metrics computation, Cosmos write, run status update) stays unchanged.

## Deletion trigger

At end of Phase 24 task group 23.3 final cleanup commit:
- All three agents on GA
- No caller of `RCEvalAgentInvoker` remains
- Delete `RCEvalAgentInvoker` class
- Optionally rename `GAEvalAgentInvoker` to plain `EvalAgentInvoker` (single concrete implementation)
- Or, more aggressively, inline the GA implementation back into `runner.py` and delete `eval/invoker.py` entirely

The framework-fidelity auditor (per design D-07) checks at task group 23.3 audit that `RCEvalAgentInvoker` is gone.

## Phase 21.1-01 noted earlier

Per `.planning/STATE.md` line 184-186 and the existing `backend/src/second_brain/eval/foundry.py`, Phase 21.1-01 introduced an AIProjectClient-based custom evaluator path. That path is preserved unchanged in Phase 24 (per design D-04 which scopes Foundry-native eval as a follow-up phase). The `eval/foundry.py` module continues to exist and is re-tested by Phase 24 task group 23.1 against the GA dep set as part of the investigation tools' eval surface.
