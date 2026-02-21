# Phase 1: Backend Foundation - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

FastAPI server with AG-UI endpoint, Cosmos DB with 5 containers, API key authentication via Azure Key Vault, and OpenTelemetry tracing. This is the infrastructure foundation — no agents classify or route yet, but the plumbing accepts requests, persists data, and produces observable traces.

</domain>

<decisions>
## Implementation Decisions

### Cosmos DB schema design
- Partition key: `/userId` only (single-user app, no need for hierarchical keys)
- 5 separate containers as spec'd: Inbox, People, Projects, Ideas, Admin
- Shared base schema across all containers (id, userId, createdAt, rawText, classificationMeta) with bucket-specific extensions (e.g., People adds birthday/contacts, Projects adds nextAction)
- Inbox documents kept permanently — full audit trail, no TTL

### AG-UI endpoint shape
- Single POST `/api/ag-ui` endpoint — thread ID and message type determine internal routing (standard AG-UI pattern)
- Minimal SSE event subset for Phase 1: only events needed for text capture and confirmation (message start/end, state updates, run lifecycle). Add more event types as later phases need them
- Long-lived SSE connection — stays open from request to completion. No reconnect/polling pattern (user has solid connectivity)
- Agent framework: Microsoft Agent Framework v1.0.0 (https://github.com/microsoft/agent-framework)

### Auth approach
- API key stored in Azure Key Vault, server fetches at startup
- Key passed via standard `Authorization: Bearer <key>` header
- Failed auth attempts logged with IP/timestamp for security auditing
- Push notification alert on repeated failures deferred to Phase 8 (when push infra exists) — logging foundation built now

### Project structure
- Monorepo: `/backend` and `/mobile` directories in this repo
- Domain-based packages inside backend: `backend/api/`, `backend/agents/`, `backend/db/`, `backend/models/`
- pyproject.toml with uv for dependency management (dependency groups for dev/test/prod)
- Direct uvicorn for local development (`uvicorn main:app --reload`), containerize only for deployment
- pytest tests from the start — API route tests, DB integration tests alongside implementation

### Claude's Discretion
- Exact Cosmos DB indexing policies per container
- OpenTelemetry configuration details (exporters, sampling)
- SSE event payload shapes within AG-UI spec
- FastAPI middleware ordering and dependency injection patterns
- Specific pyproject.toml dependency versions
- Docker/containerization setup for deployment (not Phase 1 local dev)

</decisions>

<specifics>
## Specific Ideas

- Microsoft Agent Framework v1.0.0 specifically — not Semantic Kernel, AutoGen, or Azure AI Agent Service
- AG-UI protocol for the streaming contract between backend and mobile app
- Azure Key Vault for secrets — not .env files on the server

</specifics>

<deferred>
## Deferred Ideas

- Push notification on repeated auth failures — wire up once push infra exists (Phase 8)
- Full AG-UI event spec — expand from minimal subset as later phases need more event types

</deferred>

---

*Phase: 01-backend-foundation*
*Context gathered: 2026-02-21*
