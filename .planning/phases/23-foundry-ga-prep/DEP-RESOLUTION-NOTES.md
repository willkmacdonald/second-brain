# Dependency Resolution Notes — GA SDK Spike

## Spike project directory

`/tmp/foundry-ga-spike` (throwaway, deleted after candidate file extraction; venv at `.venv/` subdirectory).

## uv sync flag note

Explicit `--no-install-project` was used because the spike directory does not contain the `src/second_brain/` source tree. The production `pyproject.toml` declares `[tool.hatch.build.targets.wheel] packages = ["src/second_brain"]`, so without `--no-install-project`, `uv sync` would attempt to build the `second_brain` wheel and fail (source tree absent). The probe harness imports `agent_framework` / `agent_framework_foundry` (which DO get installed as dependencies); it does NOT import `second_brain`.

## Diff vs. backend/pyproject.toml

1. **REMOVED:** `"agent-framework-azure-ai",` (RC package, requires `--prerelease=allow`)
2. **ADDED:** `"agent-framework",` (GA core framework)
3. **ADDED:** `"agent-framework-foundry",` (GA Foundry integration)
4. **CHANGED comment:** `# Agent Framework -- Foundry integration (RC, requires --prerelease=allow for uv install)` replaced with `# Agent Framework -- GA (Microsoft Agent Framework + Foundry integration)`

All other dependencies left unchanged.

## Resolved versions

From CANDIDATE-uv.lock (verbatim):

| Package | Version |
|---------|---------|
| agent-framework | 1.3.0 |
| agent-framework-core | 1.3.0 |
| agent-framework-foundry | 1.3.0 |
| agent-framework-openai | 1.3.0 |
| azure-ai-projects | 2.1.0 |

Note: `agent-framework-core[all]` pulls in many optional integration packages as transitives (a2a, ag-ui, anthropic, azure-cosmos, bedrock, chatkit, claude, copilotstudio, declarative, devui, durabletask, foundry-local, github-copilot, lab, mem0, ollama, orchestrations, purview, redis). These are installed but not imported by the probe harness or the Second Brain backend. Total resolved packages: 194.

## GA SDK naming changes discovered during smoke test

The GA SDK (agent-framework 1.3.0) uses different class names than the plan anticipated:

| Plan assumed (from design doc) | GA SDK actual | Package |
|-------------------------------|---------------|---------|
| `AgentRunResponse` | `AgentResponse` | `agent_framework` |
| `AgentRunResponseUpdate` | `AgentResponseUpdate` | `agent_framework` |
| `AgentThread` | `AgentSession` | `agent_framework` |

The probe harness uses the actual GA names. The design doc's names were based on pre-GA documentation.

## Import smoke test

```bash
/tmp/foundry-ga-spike/.venv/bin/python -c "from agent_framework import Agent, AgentMiddleware, AgentSession, AgentResponse, AgentResponseUpdate; from agent_framework_foundry import FoundryChatClient; from azure.identity import AzureCliCredential; print('ALL IMPORTS OK')"
```

Output: `ALL IMPORTS OK`

## GA-imports-resolve check (BLOCKING)

```bash
/tmp/foundry-ga-spike/.venv/bin/python -c "from agent_framework_foundry import FoundryChatClient; from agent_framework import Agent; print('OK: GA imports resolve')"
```

Output: `OK: GA imports resolve`

## Secondary-path probe (informational only)

```bash
/tmp/foundry-ga-spike/.venv/bin/python -c "from agent_framework.foundry import FoundryChatClient; from agent_framework import Agent; print('OK: submodule path also resolves')"
```

Output: `OK: submodule path also resolves`

Both import paths work: the canonical top-level `agent_framework_foundry` and the submodule form `agent_framework.foundry`. The probe scaffold and PLAN-02 imports use `agent_framework_foundry` (top-level path) regardless. This subsection is informational ONLY; neither outcome blocks the spike or downstream files.

## Phase 24 consumption note

Phase 24 task group 23.1 promotes these candidate files into `backend/pyproject.toml` and `backend/uv.lock` as the first commit of that task group. Until then, the deployed image continues to use the RC `agent-framework-azure-ai` dependency.
