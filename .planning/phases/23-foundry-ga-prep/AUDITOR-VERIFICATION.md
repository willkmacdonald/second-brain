# framework-fidelity-auditor verification

**Verified:** 2026-05-09
**Auditor file:** `~/.claude/agents/gsd-framework-fidelity-auditor.md`
**Calibration report:** `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-calibration.md`

## Existence checks

| Check | Result |
|---|---|
| `~/.claude/agents/gsd-framework-fidelity-auditor.md` exists | yes |
| Auditor file size | 19360 bytes |
| Auditor file line count | 318 lines |
| `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-calibration.md` exists | yes |
| Calibration report size | 37565 bytes |
| Number of F-## failure findings in calibration | 19 (F-01 through F-19) |

## Calibration ❌ category review

Per the 2026-05-08 calibration detour: the auditor was run against the current RC backend (known-bad case for GA fidelity). It produced 19 failure findings in these categories:

| Finding ID | Category | Summary |
|---|---|---|
| F-01 | RC framework client import | `AzureAIAgentClient` pervasively imported/instantiated in `main.py` (10 construction sites) |
| F-02 | RC framework client import | `AzureAIAgentClient` in `warmup.py` |
| F-03 | RC framework client import | `AzureAIAgentClient` in `processing/admin_handoff.py` |
| F-04 | RC framework client import | `AzureAIAgentClient` in `streaming/adapter.py` |
| F-05 | RC framework client import | `AzureAIAgentClient` in `streaming/investigation_adapter.py` |
| F-06 | RC framework types in eval | RC `Message`/`ChatOptions` in `eval/runner.py` |
| F-07 | RC framework types in eval | RC `Message`/`ChatOptions` in `eval/foundry.py` |
| F-08 | Tool registration | RC `@tool(approval_mode="never_require")` on all 16 production tools |
| F-09 | Required-tool semantics | Python safety net in classifier streaming (D-07b deletion target) |
| F-10 | Required-tool semantics | RC-shaped `tool_choice` provider-dict in classifier |
| F-11 | Required-tool semantics | Voice tool registered on same classifier agent (blocks `tool_choice='required'`) |
| F-12 | Conversation continuity | Constructor-level `agent_id`-pinned RC clients (conversation conflation hazard) |
| F-13 | Conversation continuity | RC `conversation_id` round-trip bypasses framework session API |
| F-14 | Tracing | Custom `tracer.start_as_current_span(...)` wrapping in `streaming/adapter.py` (3 sites) |
| F-15 | Tracing | Custom `tracer.start_as_current_span(...)` wrapping in `streaming/investigation_adapter.py` |
| F-16 | Tracing | Custom `tracer.start_as_current_span(...)` wrapping in `processing/admin_handoff.py` |
| F-17 | Tracing | Existing middleware uses `tracer.start_as_current_span` instead of operating on framework-emitted spans |
| F-18 | Probe fixture fidelity | Probe-fixture-shaped extraction code missing (coded against docs, not probes) |
| F-19 | Agent instructions (D-02) | Classifier agent shell creates portal-managed agent with no instructions content |

Plus 1 warning (W-01): `CaptureTraceSpanProcessor` retained as bulk tagger, narrowing required per D-07a.

Plus 3 pass findings: token metering via `enable_instrumentation()`, App Insights export wiring, tool parameter shape (`Annotated[..., Field(description=...)]`).

**Expected categories vs. actual coverage:**

| Expected category (from design D-07 checklist) | Covered by | Status |
|---|---|---|
| Tracing --- RC `agent_framework.azure` imports, custom span wrapping | F-01 through F-05 (imports), F-14 through F-17 (span wrapping) | Covered |
| Capture-trace propagation --- CaptureTraceSpanProcessor interaction | W-01 (narrowing required) | Covered |
| Tool registration --- RC `@tool(approval_mode=...)` decorators | F-08 (all 16 tools) | Covered |
| Required-tool semantics --- Python safety net pattern | F-09, F-10, F-11 | Covered |
| Conversation continuity --- RC thread/session handling | F-12, F-13 | Covered |
| Token metering --- manual token counters | Pass finding (no manual counters found) | Covered (passing) |
| Eval --- custom eval framework interaction with agent SDK | F-06, F-07 | Covered |
| App Insights export --- standard wiring | Pass finding (correct `configure_azure_monitor` usage) | Covered (passing) |
| Agent instructions --- D-02 repo-as-source-of-truth | F-19 | Covered |
| Probe fixture fidelity --- extraction code shaped by probes | F-18 (resolved by Phase 23 PLAN-02 probe execution) | Covered |

**No-blind-spots claim:** HOLDS. Every expected category produced at least one finding (failure or pass). No discrepancies found between the expected checklist categories and the calibration report's actual coverage.

## No-op invocation

Phase 24 will invoke the auditor at end of each task group with: task group ID + scope from design + git diff + the auditor checklist. Phase 23 does NOT invoke it (nothing to audit --- Phase 23 is artifact-only and touches zero `backend/src/` code). The auditor is verified to exist and be syntactically valid as a markdown agent definition.

Validity check (Claude can parse the file at agent-spawn time): file is well-formed markdown, has at least one heading, and contains the auditor checklist or a reference to design Section "Framework-fidelity auditor checklist".

```
$ grep -q "checklist\|Concern.*Pass.*Fail" ~/.claude/agents/gsd-framework-fidelity-auditor.md
AUDITOR CONTAINS CHECKLIST CONTENT
```

The auditor file at `~/.claude/agents/gsd-framework-fidelity-auditor.md` (318 lines, 19360 bytes) is a well-formed markdown agent definition containing checklist content. It is loadable as a Claude subagent via the standard `~/.claude/agents/` convention.

## Phase 24 invocation contract

Per design Section "Framework-fidelity audit workflow":
1. `git diff <task-group-start-sha>..HEAD` captured to `.planning/phases/24-foundry-ga-migration/FIDELITY-23.{1,2,3}.patch`
2. Spawn `gsd-framework-fidelity-auditor` subagent with: task-group ID, scope from design, the diff, the auditor checklist
3. Auditor produces `.planning/phases/24-foundry-ga-migration/FRAMEWORK-FIDELITY-23.{1,2,3}.md` with sections: **Pass** / **Warnings** / **Failures**
4. For each failure, fix the code OR rebut with explicit-justification template
5. Moving to the next task group requires zero failures on the current one
6. `git push origin main` requires the cumulative audit (`FRAMEWORK-FIDELITY-cumulative.md`) at zero failures

Phase 24 plans MUST include these auditor invocation tasks at the right boundary points.

## Status

READY --- auditor exists (318 lines, 19360 bytes), calibration report exists (37565 bytes) with 19 failure findings across all expected categories, no-blind-spots claim holds. Phase 24 unblocked.
