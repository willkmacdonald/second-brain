# The Active Second Brain

A personal capture-and-intelligence system that turns fleeting thoughts into organized, actionable records. Voice notes and text are classified by AI agents into four buckets (People, Projects, Ideas, Admin), with errands routed to dynamic destinations and recipes extracted from URLs — all with zero organizational effort from the user.

## How It Works

1. **Capture** — tap the phone, speak or type a thought
2. **Classify** — a Foundry Classifier agent routes the capture to the right bucket with confidence scoring
3. **Act** — an Admin Agent silently processes errands, routes items to destinations, and extracts recipe ingredients
4. **Observe** — an Investigation agent answers natural language questions about system health and capture history

## Architecture

```
Mobile (Expo/React Native)
    │
    ▼  SSE (AG-UI protocol)
FastAPI Backend (Azure Container Apps)
    │
    ├── Classifier Agent (Azure AI Foundry)
    ├── Admin Agent (Azure AI Foundry)
    ├── Investigation Agent (Azure AI Foundry)
    │
    ├── Cosmos DB (9 containers)
    └── Application Insights (OTel traces)

Web Dashboard (Next.js)          MCP Server (Claude Code)
    │                                │
    └── Spine observability ─────────┘
```

## Project Structure

```
backend/          Python backend (FastAPI + Azure AI Foundry Agent Service)
mobile/           iOS app (Expo/React Native)
web/              Observability dashboard (Next.js)
mcp/              MCP server for Claude Code telemetry queries
infra/            Infrastructure scripts
docs/             Architecture and operational docs
.github/          CI/CD workflows (deploy-backend, deploy-web, codex-review)
.planning/        GSD project management artifacts
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile | Expo 54, React Native 0.81, expo-speech-recognition |
| Backend | Python 3.12+, FastAPI, Azure AI Foundry Agent Service |
| AI | GPT-4o via Azure OpenAI, Microsoft Agent Framework |
| Database | Azure Cosmos DB (NoSQL) |
| Observability | Application Insights, OpenTelemetry, Sentry |
| Web | Next.js 14 |
| MCP | Python MCP server (stdio transport) |
| Infrastructure | Azure Container Apps, ACR, GitHub Actions (OIDC) |

## Key Features

- **Multi-bucket classification** with confidence scoring and HITL clarification flows
- **Voice capture** via on-device SFSpeechRecognizer (iOS) with cloud fallback
- **Dynamic destination routing** with voice-managed affinity rules
- **Recipe URL extraction** with three-tier fetch (Jina Reader, httpx, Playwright)
- **Investigation agent** accessible from mobile chat, web dashboard, and Claude Code MCP
- **Per-capture trace ID propagation** from mobile through backend to App Insights
- **Eval framework** with golden datasets and deterministic quality metrics
- **Feedback collection** with implicit signals and explicit thumbs up/down

## Development

### Backend

```bash
cd backend
uv venv && uv pip sync requirements.txt
```

The backend runs on Azure Container Apps. Push to `main` triggers CI/CD via GitHub Actions.

### Mobile

```bash
cd mobile
npm install
npx expo start --clear --dev-client
```

Requires an EAS development build on the device. The app connects to the deployed backend at `https://brain.willmacdonald.com`.

### Web Dashboard

```bash
cd web
npm install
npm run dev
```

### MCP Server

Configured in `.mcp.json` for Claude Code. Queries Application Insights telemetry directly.

## Deployment

- **Backend**: Push to `main` with changes in `backend/` triggers `deploy-backend.yml` — builds Docker image, pushes to ACR, deploys to Container Apps with health verification
- **Web**: Push to `main` with changes in `web/` triggers `deploy-web.yml`
- **Mobile**: EAS builds via `eas build`, OTA updates via `expo-updates`

## License

Private project. Not open source.
