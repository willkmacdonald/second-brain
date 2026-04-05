# Technology Stack

**Project:** Second Brain v3.1 -- Observability & Evals
**Researched:** 2026-04-04
**Scope:** NEW capabilities only (observability investigation agent, eval framework, self-monitoring)

## Recommended Stack Additions

### Programmatic App Insights Queries (Investigation Agent Backend)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `azure-monitor-query` | `>=2.0.0` | KQL queries from Python via `LogsQueryClient` | Official Azure SDK for programmatic Log Analytics / App Insights queries. v2.0.0 is GA (released 2025-07-30). Provides both sync and async clients (`azure.monitor.query.aio.LogsQueryClient`). Integrates with `DefaultAzureCredential` already in use. |

**Confidence:** HIGH -- Official Microsoft SDK, GA, verified via [official docs](https://learn.microsoft.com/en-us/python/api/overview/azure/monitor-query-readme?view=azure-python) and [PyPI](https://pypi.org/project/azure-monitor-query/).

**Key integration details:**
- Use `query_workspace(workspace_id, query, timespan)` with the Log Analytics workspace ID backing the existing App Insights resource (`second-brain-insights`)
- Async variant: `from azure.monitor.query.aio import LogsQueryClient` -- use this in FastAPI routes
- Existing KQL queries use `AppTraces`/`AppRequests` (portal table names) -- these work when querying via the workspace-based SDK too
- Authentication: reuse existing `DefaultAzureCredential` from `azure-identity` (already a dependency)
- New config value needed: `log_analytics_workspace_id` in Settings (find via Azure Portal > App Insights > Properties > Workspace ID)
- **No** `pandas` dependency needed -- iterate `LogsTable.rows` and `LogsTable.columns` directly, return JSON

**Breaking change note:** v2.0.0 removed `MetricsClient`/`MetricsQueryClient` (moved to `azure-monitor-querymetrics`). We do not need metrics queries, only logs queries, so this is a non-issue.

### Eval Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `azure-ai-evaluation` | `>=1.16.0` | Classifier and Admin Agent quality evals | Official Azure AI Foundry evaluation SDK. Provides `IntentResolutionEvaluator`, `ToolCallAccuracyEvaluator`, `TaskAdherenceEvaluator` for agent evaluation + `evaluate()` batch API + custom evaluator support. v1.16.4 is latest (2026-04-03). |
| `azure-ai-projects` | `>=2.0.0` | `AIAgentConverter` for Foundry Agent thread-to-eval conversion | Required by eval SDK's `AIAgentConverter` to convert Foundry Agent Service threads/runs to evaluation format. Already a transitive dependency via `agent-framework-azure-ai`. Pin `>=2.0.0` explicitly. |

**Confidence:** HIGH -- Official Microsoft SDK, verified via [official docs](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-evaluation-readme?view=azure-python), [agent eval docs](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/agent-evaluate-sdk?view=foundry-classic), and [PyPI](https://pypi.org/project/azure-ai-evaluation/).

**Key integration details:**
- `AIAgentConverter(project_client)` initializes with `AIProjectClient` -- need to create one alongside existing `AzureAIAgentClient`
- `converter.convert(thread_id, run_id)` transforms agent threads into eval-ready dicts
- `converter.prepare_evaluation_data(thread_ids, filename)` exports to JSONL for batch eval
- Built-in agent evaluators: `IntentResolutionEvaluator`, `TaskAdherenceEvaluator`, `ToolCallAccuracyEvaluator` (public preview, but functional)
- Custom evaluators via simple functions: `def classifier_accuracy(response, ground_truth, **kwargs) -> dict`
- `evaluate()` batch API runs multiple evaluators over JSONL datasets
- Results optionally logged to Foundry portal for visualization (pass `azure_ai_project` param)
- AI-assisted evaluators need a model config (reuse existing `gpt-4o` deployment)

**Two evaluation paths discovered:**

1. **Local SDK evaluation** (`azure-ai-evaluation` `evaluate()` API) -- run evaluators locally against exported JSONL datasets. Best for: golden dataset regression tests, CI/CD gates, custom evaluators.
2. **Cloud evaluation via Foundry portal** (`azure-ai-projects` `client.evals.create()` API) -- run evaluations server-side via the Foundry Evals API. Best for: agent-targeted evals where the service calls the agent and captures responses automatically.

**Recommendation:** Start with local SDK evaluation (path 1) because it works with custom evaluators and golden datasets without requiring the newer Foundry Evals API. Add cloud evaluation later if needed for continuous monitoring.

### MCP Server for Claude Code

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `mcp` | `>=1.27.0` | MCP server exposing App Insights query tools to Claude Code | Official MCP Python SDK. Includes FastMCP as built-in (`from mcp.server.fastmcp import FastMCP`). Supports stdio transport for Claude Code integration. v1.27.0 is latest (2026-04-02). |

**Confidence:** HIGH -- Official SDK, verified via [GitHub](https://github.com/modelcontextprotocol/python-sdk), [PyPI](https://pypi.org/project/mcp/), and [Claude Code docs](https://code.claude.com/docs/en/mcp).

**Key integration details:**
- Build as a **separate Python module** (`tools/mcp-server/`), NOT inside the FastAPI backend
- Use `from mcp.server.fastmcp import FastMCP` (built into the `mcp` package, NOT the standalone `fastmcp` package)
- Transport: **stdio** for Claude Code local tool (Claude Code spawns the server as a child process)
- Register with Claude Code: `claude mcp add --transport stdio second-brain-insights -- uv run --with "mcp[cli]" --with azure-monitor-query --with azure-identity python /path/to/mcp_server.py`
- Tools to expose: `query_system_health`, `query_capture_trace`, `query_recent_failures`, `query_admin_audit`, `run_custom_kql`
- Reuse `azure-monitor-query` `LogsQueryClient` (sync variant, since stdio server is not async)
- Auth: `DefaultAzureCredential` (Will is already logged in via `az login`)
- Python requirement: `>=3.10` (project already requires `>=3.12`)

**Why NOT the standalone `fastmcp` package (v3.2.0):**
The standalone `fastmcp` on PyPI is a larger framework that includes client/app features we do not need. The official `mcp` SDK has `FastMCP` built in since FastMCP 1.0 was incorporated in 2024. Using `mcp` avoids an extra dependency and aligns with the official SDK.

### Mobile Chat UI (Investigation Agent Frontend)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Custom FlatList chat | N/A (React Native built-in) | Chat bubbles for investigation agent conversation | The app already uses FlatList patterns throughout. A custom chat component (chat bubbles + input) is ~100 lines of TSX. Avoids adding `react-native-gifted-chat` (heavy dependency, known Expo SDK compatibility issues with `react-native-keyboard-controller`). Matches existing app styling. |

**Confidence:** HIGH -- FlatList is core React Native, no new dependency needed.

**Key integration details:**
- Reuse existing AG-UI SSE streaming pattern (`react-native-sse` already a dependency)
- New tab or screen: `/app/(tabs)/investigate.tsx` or a modal from status screen
- Chat messages model: `{ id, role: 'user' | 'assistant', content, timestamp }`
- Bubble styling: match existing app theme
- Input: `TextInput` with send button (voice capture is overkill for investigation queries)
- SSE endpoint: new `/api/investigate` route on backend, reuse `FoundrySSEAdapter` pattern

### Mobile Dashboard (Observability Metrics)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `victory-native` | `>=41.0.0` | Charts for capture volume, error rates, agent metrics | Well-maintained, works with Expo managed workflow (no native linking required). SVG-based (via `react-native-svg`, already compatible with Expo). Composable API (`VictoryChart`, `VictoryBar`, `VictoryLine`, `VictoryAxis`). |
| `react-native-svg` | (Expo-compatible) | Required peer dep for victory-native | Install via `npx expo install react-native-svg` to get the Expo SDK 54 compatible version. |

**Confidence:** MEDIUM -- Victory Native is well-documented and Expo-compatible per [multiple sources](https://kushabhi5.medium.com/using-victory-native-for-charts-in-an-expo-react-native-project-bd57d805cb8c), but exact version compatibility with Expo SDK 54 / React Native 0.81 needs validation at install time. Alternative: `react-native-gifted-charts` if Victory has issues.

**Key integration details:**
- Dashboard screen: part of the investigate tab or a sub-screen
- Data source: new backend API endpoint (`GET /api/metrics/summary`) that runs pre-defined KQL queries and returns JSON
- Charts to display: capture volume trend (line), success rate (gauge or text), error count (bar), admin agent activity (line)
- Keep it simple: 2-4 charts max, not a full monitoring dashboard (App Insights portal exists for deep dives)

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| KQL queries | `azure-monitor-query` | Direct REST API calls to Log Analytics | SDK handles auth, pagination, error handling, response parsing. No reason to go lower-level. |
| KQL queries | `azure-monitor-query` | `azure-ai-projects` inference | `azure-ai-projects` does not provide KQL query capabilities. |
| Eval framework | `azure-ai-evaluation` | Custom eval scripts (pure Python) | The SDK provides battle-tested evaluators, batch API, Foundry portal integration. Building from scratch wastes time. |
| Eval framework | `azure-ai-evaluation` local | `client.evals.create()` cloud API | Cloud API is newer, requires Foundry Evals API which is in preview. Local SDK evaluation is more mature and supports custom evaluators natively. Start local, add cloud later. |
| MCP server | `mcp` (official SDK) | Standalone `fastmcp` v3.x | `mcp` includes FastMCP built-in. Standalone `fastmcp` adds unnecessary features (client, apps) we don't need. |
| MCP server | `mcp` (official SDK) | Custom JSON-RPC over stdio | Reinventing the protocol is pointless when the SDK exists. |
| Chat UI | Custom FlatList | `react-native-gifted-chat` | Heavy dependency (~200KB), has had [Expo compatibility issues](https://github.com/FaridSafi/react-native-gifted-chat/issues/2595) with keyboard controller. Our chat is simple (text in, streaming text out) -- not a full chat app. |
| Chat UI | Custom FlatList | Stream Chat SDK | Commercial product, massive dependency, overkill for single-user investigation chat. |
| Charts | `victory-native` | `react-native-chart-kit` | Less composable, fewer chart types, less active maintenance. |
| Charts | `victory-native` | Web-based dashboard (separate app) | Adds deployment complexity. Mobile-native charts keep everything in one app. |
| Charts | `victory-native` | Skip charts, text-only metrics | Poor UX for trend data. Simple charts add significant value for quick health checks. |

## What NOT to Add

| Technology | Why Skip |
|------------|----------|
| `pandas` | Often paired with `azure-monitor-query` for data analysis, but we just need JSON responses. Adding pandas bloats the Docker image by ~60MB. |
| `plotly` | Server-side charting -- we render charts on mobile with Victory Native. |
| `azure-monitor-querymetrics` | We query logs, not Azure Monitor metrics. |
| `streamlit` / `gradio` | Web dashboard alternatives -- we want mobile-native, not a separate web app. |
| `langchain` / `semantic-kernel` | Investigation agent is a Foundry Agent Service agent with @tools, same pattern as Classifier and Admin Agent. No orchestration framework needed. |
| `fastmcp` (standalone, v3.x) | Redundant with `mcp` package which includes FastMCP built-in. |
| `pytest-benchmark` | Eval framework handles quality measurement. Benchmarking is not the goal. |
| `react-native-gifted-chat` | See alternatives section -- custom FlatList is simpler and more compatible. |
| `@ag-ui/client` | Mobile app already has `@ag-ui/core` for SSE event types. No additional AG-UI packages needed. |
| `promptflow` | Was the previous eval framework before `azure-ai-evaluation`. The newer SDK supersedes it. |
| Any state management library (Zustand, Redux) | Investigation chat is a single screen with local state. React `useState` is sufficient. |

## Installation

### Backend (Python)

```bash
cd /Users/willmacdonald/Documents/Code/claude/second-brain/backend

# New dependencies for v3.1
uv pip install azure-monitor-query azure-ai-evaluation "azure-ai-projects>=2.0.0" --prerelease=allow
```

Add to `pyproject.toml` `[project.dependencies]`:

```toml
dependencies = [
    # ... existing deps ...
    # Programmatic App Insights / Log Analytics queries
    "azure-monitor-query>=2.0.0",
    # Eval framework for agent quality measurement
    "azure-ai-evaluation>=1.16.0",
    # AIProjectClient + AIAgentConverter for eval data export
    "azure-ai-projects>=2.0.0",
]
```

Then: `uv lock` to update the lock file.

### MCP Server (separate from backend, not in Docker)

```bash
# Option A: Register with Claude Code using uv run (no permanent install)
claude mcp add --transport stdio \
  --scope project \
  second-brain-insights -- \
  uv run \
  --with "mcp[cli]" \
  --with azure-monitor-query \
  --with azure-identity \
  python /Users/willmacdonald/Documents/Code/claude/second-brain/tools/mcp-server/server.py

# Option B: Create a dedicated venv
cd /Users/willmacdonald/Documents/Code/claude/second-brain/tools/mcp-server
uv venv && uv pip install "mcp[cli]" azure-monitor-query azure-identity
```

### Mobile (TypeScript)

```bash
cd /Users/willmacdonald/Documents/Code/claude/second-brain/mobile

# Charts (use npx expo install for SDK-compatible versions)
npx expo install victory-native react-native-svg

# No other new mobile dependencies needed
# Chat UI: custom component using existing FlatList + react-native-sse
```

## New Configuration Values

| Setting | Source | Where | Notes |
|---------|--------|-------|-------|
| `log_analytics_workspace_id` | Azure Portal > App Insights > Properties > Workspace ID | `config.py` Settings + Container App env var | Required for `LogsQueryClient.query_workspace()` |
| `azure_ai_project_endpoint` | Already exists in config | Reuse for `AIProjectClient` in eval framework | No change needed |
| Investigation Agent ID | Create in Foundry portal | `config.py` + Container App env var | New persistent agent, same pattern as Classifier/Admin |

## Architecture Impact Summary

### Backend Changes
- New module: `second_brain/observability/` -- `LogsQueryClient` wrapper, pre-built KQL templates, investigation agent @tools
- New module: `second_brain/evals/` -- custom evaluators, golden dataset management, eval runner
- New API routes: `POST /api/investigate` (SSE), `GET /api/metrics/summary`
- New agent: Investigation Agent (third persistent Foundry agent, mirrors Classifier/Admin pattern)

### MCP Server (Separate Process)
- New directory: `tools/mcp-server/`
- Standalone Python script, NOT part of the FastAPI backend or Docker image
- Claude Code spawns it via stdio transport
- Shares `azure-monitor-query` and `azure-identity` deps but runs independently on Will's machine

### Mobile Changes
- New tab or screen: investigation chat with FlatList-based chat bubbles
- New component: metrics dashboard with Victory Native charts
- Reuse: SSE streaming pattern, AG-UI event handling from `react-native-sse`

## Dependency Compatibility Notes

| New Package | Potential Conflict | Mitigation |
|-------------|-------------------|------------|
| `azure-monitor-query>=2.0.0` | None -- separate from existing Azure packages | Clean addition |
| `azure-ai-evaluation>=1.16.0` | Pulls in `openai`, `azure-identity` (already deps), plus `promptflow-core` and other eval internals | May increase Docker image size by ~50-100MB. Monitor image size after adding. Consider adding to `[project.optional-dependencies]` under `eval` extra if image size is a concern, and run evals locally only. |
| `azure-ai-projects>=2.0.0` | Already a transitive dep via `agent-framework-azure-ai`. Pinning explicitly may cause version conflicts if agent-framework pins a different version. | Check `uv.lock` after install. If conflict, let agent-framework control the version and import from its transitive dep instead of pinning directly. |
| `mcp>=1.27.0` | Requires Python `>=3.10` (project uses `>=3.12`, fine). Pulls in `pydantic`, `httpx`. | Install in MCP server context only, NOT in backend pyproject.toml, to avoid bloating the Docker image. |
| `victory-native` | Requires `react-native-svg`. May have peer dep version constraints with Expo SDK 54. | Use `npx expo install` which resolves compatible versions automatically. |

## Sources

- [azure-monitor-query SDK docs](https://learn.microsoft.com/en-us/python/api/overview/azure/monitor-query-readme?view=azure-python) -- HIGH confidence
- [azure-monitor-query PyPI](https://pypi.org/project/azure-monitor-query/) -- v2.0.0, released 2025-07-30
- [azure-ai-evaluation SDK docs](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-evaluation-readme?view=azure-python) -- HIGH confidence
- [azure-ai-evaluation PyPI](https://pypi.org/project/azure-ai-evaluation/) -- v1.16.4, released 2026-04-03
- [Agent Evaluation with Foundry SDK](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/agent-evaluate-sdk?view=foundry-classic) -- HIGH confidence, detailed converter examples
- [Foundry portal agent evaluation](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/evaluate-agent) -- HIGH confidence, newer cloud eval API
- [MCP Python SDK GitHub](https://github.com/modelcontextprotocol/python-sdk) -- v1.27.0, HIGH confidence
- [MCP Python SDK PyPI](https://pypi.org/project/mcp/) -- v1.27.0, released 2026-04-02
- [FastMCP + Claude Code integration](https://gofastmcp.com/integrations/claude-code) -- HIGH confidence
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) -- HIGH confidence
- [Victory Native for Expo](https://kushabhi5.medium.com/using-victory-native-for-charts-in-an-expo-react-native-project-bd57d805cb8c) -- MEDIUM confidence
- [react-native-gifted-chat issues](https://github.com/FaridSafi/react-native-gifted-chat/issues/2595) -- Expo compatibility concerns
