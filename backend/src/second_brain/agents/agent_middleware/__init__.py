"""Agent middleware package (Phase 24 GA SDK target home).

P1-3 amendment: this package is named `agent_middleware/` (NOT `middleware/`)
to avoid Python import-system shadowing of the legacy module
`backend/src/second_brain/agents/middleware.py`. The legacy module continues
to export AuditAgentMiddleware + ToolTimingMiddleware until plan 24-18
deletes it. After that deletion, plan 24-18 may optionally rename this
package to `middleware/` for tidiness -- no functional change.

Phase 24 task group 23.1 introduces capture_trace.py here.

During the 23.1..23.3 commit window, this package COEXISTS with the legacy
`agents/middleware.py` module-style file. Both are importable. Plans 24-04,
24-09, 24-14 import the new GA middleware from this package via FQN
(`from second_brain.agents.agent_middleware.capture_trace import ...`).
"""
