# Second Brain - Project CLAUDE.md

## Project Overview

Personal capture-and-intelligence system: voice/text captures classified by AI agents into People/Projects/Ideas/Admin buckets, with errands routing, recipe extraction, and an investigation agent for system observability.

## Architecture

- **backend/** — Python 3.12+, FastAPI, Azure AI Foundry Agent Service (3 persistent agents: Classifier, Admin, Investigation)
- **mobile/** — Expo 54 / React Native 0.81, iOS via EAS development builds
- **web/** — Next.js 14 observability dashboard (spine segments, transaction ledger)
- **mcp/** — Python MCP server for Claude Code telemetry queries (stdio transport)

## Code Search with qmd

This project is indexed in qmd for fast, token-efficient code search. **Use qmd search before falling back to grep/glob/Read** when exploring the codebase.

Collections:
- `second-brain-py` — Python backend (146 files)
- `second-brain-mobile` — Mobile TypeScript (32 files)
- `second-brain-web` — Web TypeScript (16 files)
- `second-brain` — Project markdown docs (6 files)

After making code changes, re-index with: `qmd update`

## Backend

- API runs on Azure Container Apps at `https://brain.willmacdonald.com`
- **Never run the backend locally** — testing happens against the deployed endpoint after CI/CD
- Deployment: push to main -> GitHub Actions (OIDC) -> ACR -> Container Apps
- Agent instructions live in the Foundry portal, not in the repo
- Cosmos DB: 9 containers, all partitioned by `/userId` or domain-specific keys
- Observability: Application Insights via OpenTelemetry, structured logging, KQL queries
- Use `uv` for all package management; Dockerfile pins uv 0.5.4

## Mobile

- Points to deployed Azure URL via `EXPO_PUBLIC_API_URL`, not localhost
- Use `npx expo install <package>` to ensure SDK-compatible versions
- Run with `npx expo start --clear --dev-client`
- If Metro cache clear doesn't pick up changes, suggest EAS rebuild immediately
- Custom fonts: Instrument Serif, Instrument Sans, JetBrains Mono (loaded via expo-font)
- Design tokens in `mobile/lib/theme.ts`

## Web

- Next.js 14 with App Router
- Spine observability: segment pages, transaction ledger, native telemetry drill-down
- Types mirror backend Pydantic models (Optional[T]=None -> T | null)

## Testing

- Backend: `pytest` from `backend/` directory
- Mobile: no test framework installed (coverage via end-to-end trace inspection)
- Web: `tsc` type checking + `next build` for build verification

## Key Patterns

- `@tool` functions on tool classes with `approval_mode="never_require"` and async
- Fire-and-forget for non-critical writes (feedback signals) — try/except wraps every write
- `ContextVar` for per-request state (capture_trace_id, follow-up context)
- SSE streaming via AG-UI protocol for agent-to-frontend communication
- Spine workload events via `IngestEvent` RootModel wrapper (not raw `_WorkloadEvent`)

## Important Files

- `backend/src/second_brain/main.py` — app lifespan, agent client init, router wiring
- `backend/src/second_brain/tools/investigation.py` — InvestigationTools (7 @tools)
- `backend/src/second_brain/tools/classification.py` — ClassifierTools (file_capture, transcribe_audio)
- `backend/src/second_brain/tools/admin.py` — AdminTools (6 @tools for errand routing)
- `backend/src/second_brain/models/documents.py` — all Cosmos document models
- `backend/src/second_brain/observability/queries.py` — KQL query execution
- `mobile/app/(tabs)/` — tab screens (capture, inbox, tasks, status)
- `mobile/lib/theme.ts` — design tokens
- `web/app/` — Next.js pages (segments, correlation, status)
