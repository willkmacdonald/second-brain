---
phase: 07-classifier-agent-baseline
verified: 2026-02-27T07:00:00Z
status: human_needed
score: 4/4 automated must-haves verified
re_verification: false
human_verification:
  - test: "Start the backend and confirm the Classifier agent ID appears in the AI Foundry portal"
    expected: "An agent named 'Classifier' is visible in the AI Foundry portal with the ID matching AZURE_AI_CLASSIFIER_AGENT_ID; restarting the process reuses the same ID without creating a new agent"
    why_human: "AGNT-01 requires Foundry portal visibility and cross-restart persistence — both require a live Azure environment and cannot be verified from static code inspection"
  - test: "Run the integration test suite with live Azure credentials: pytest -m integration tests/test_classifier_integration.py -v"
    expected: "test_classifier_agent_classifies_text passes (agent invokes file_capture, Inbox container receives a write with status in classified/pending/misunderstood); test_classifier_agent_id_is_valid passes (agent.name == 'Classifier')"
    why_human: "End-to-end Foundry agent execution requires live AZURE_AI_PROJECT_ENDPOINT and AZURE_AI_CLASSIFIER_AGENT_ID — skipped in automated runs without credentials"
  - test: "Capture a voice note through the mobile app (or simulate via direct API call with a blob URL)"
    expected: "transcribe_audio is called by the Classifier, the transcript appears in a log entry, then file_capture is called with the transcribed text"
    why_human: "Voice capture path requires a real blob URL in Azure Storage and the gpt-4o-transcribe deployment — the tool chain cannot be exercised locally"
  - test: "Observe console output during a live classification run"
    expected: "[Agent] Run started, [Agent] Run completed in X.XXXs, [Tool] Calling file_capture, [Tool] file_capture completed with bucket/confidence/status/item_id fields all present"
    why_human: "Middleware audit logs only appear during actual Foundry agent runs — fire-and-observe requires live credentials"
---

# Phase 7: Classifier Agent Baseline Verification Report

**Phase Goal:** The Classifier is a persistent Foundry-registered agent that executes local @tool functions and writes to Cosmos DB, validated in isolation before touching the live streaming pipeline
**Verified:** 2026-02-27T07:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `file_capture` tool writes to Cosmos DB Inbox + bucket container and returns a structured dict | VERIFIED | `classification.py:51-196` — @tool decorator, dict returns `{bucket, confidence, item_id}` on success, `{error, detail}` on failure; 12 unit tests pass covering classified/pending/misunderstood/invalid-bucket/clamping/meta/links |
| 2 | `transcribe_audio` tool calls gpt-4o-transcribe via AsyncAzureOpenAI and returns transcript text | VERIFIED | `transcription.py:62-91` — @tool decorator, `self._openai.audio.transcriptions.create(model=self._deployment_name, file=...)`, returns `result.text`; 3 unit tests pass covering success/blob-failure/api-failure |
| 3 | `AuditAgentMiddleware` and `ToolTimingMiddleware` implement correct middleware interfaces and are wired to the agent client | VERIFIED | `middleware.py:22-93` — inherits `AgentMiddleware`/`FunctionMiddleware` from `agent_framework`; `main.py:185` passes `middleware=[AuditAgentMiddleware(), ToolTimingMiddleware()]` to `AzureAIAgentClient` constructor |
| 4 | `ensure_classifier_agent` checks stored ID and creates-if-missing via Foundry API; agent persists via `should_cleanup_agent=False` | VERIFIED | `classifier.py:115-163` — checks `stored_agent_id`, calls `foundry_client.agents_client.get_agent()`, falls through to `create_agent()` on failure; `main.py:184` sets `should_cleanup_agent=False` |
| 5 | `CLASSIFIER_INSTRUCTIONS` covers all three outcomes (classified, pending, misunderstood) with file_capture as the single tool | VERIFIED | `classifier.py:24-112` — multi-section instructions: Confidence Calibration, Classification Decision Flow, and Rules all address classified/pending/misunderstood; voice capture path documented; Rule 4: "ALWAYS call file_capture or transcribe_audio" |

**Score:** 5/5 truths verified (automated)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/second_brain/tools/classification.py` | ClassifierTools with file_capture @tool returning dict | VERIFIED | 197 lines; `ClassifierTools` class with `@tool(approval_mode="never_require") async def file_capture(...)`, returns `dict`; no `classify_and_file`, `mark_as_junk`, or `request_misunderstood` present |
| `backend/src/second_brain/tools/transcription.py` | TranscriptionTools with transcribe_audio @tool | VERIFIED | 92 lines; `TranscriptionTools` class with 4-param constructor; `@tool(approval_mode="never_require") async def transcribe_audio(...) -> str` |
| `backend/src/second_brain/agents/classifier.py` | ensure_classifier_agent function + CLASSIFIER_INSTRUCTIONS | VERIFIED | 164 lines; `CLASSIFIER_INSTRUCTIONS` constant (112-line prompt string); `async def ensure_classifier_agent(foundry_client, stored_agent_id) -> str`; no `AzureOpenAIChatClient` or v1 imports |
| `backend/src/second_brain/agents/middleware.py` | AuditAgentMiddleware + ToolTimingMiddleware | VERIFIED | 94 lines; both classes with correct `process(self, context, call_next)` signatures; structured logging for AppInsights queryability |
| `backend/src/second_brain/main.py` | Agent registration in lifespan + ClassifierTools and agent on app.state | VERIFIED | Full lifespan wiring at lines 125-200; `ensure_classifier_agent`, `ClassifierTools`, `TranscriptionTools`, `AzureAIAgentClient` with middleware, `app.state.classifier_agent_tools` list stored for request-time use |
| `backend/tests/test_classification.py` | Updated tests for file_capture dict returns and misunderstood status | VERIFIED | 341 lines; 12 tests: classified/pending/misunderstood/each-bucket/invalid-bucket/clamping/meta/links; all use `ClassifierTools` (not `ClassificationTools`); all 12 pass |
| `backend/tests/test_transcription.py` | Unit tests for TranscriptionTools.transcribe_audio | VERIFIED | 140 lines; 3 tests: success/blob-failure/api-failure; all pass |
| `backend/tests/test_classifier_integration.py` | Integration test for Classifier agent end-to-end | VERIFIED | 129 lines; `@pytest.mark.integration` + `@pytest.mark.skipif` on both tests; skips cleanly without credentials |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `classification.py` | `db/cosmos.py` | `self._manager.get_container()` for Inbox and bucket writes | WIRED | `_write_to_cosmos()` calls `self._manager.get_container("Inbox")` (line 137, 168) and `self._manager.get_container(bucket)` (line 186); container `create_item` called with full document body |
| `transcription.py` | `openai.AsyncAzureOpenAI` | `self._openai.audio.transcriptions.create()` with deployment name | WIRED | Line 84: `await self._openai.audio.transcriptions.create(model=self._deployment_name, file=(...))` — deployment name from 4-param constructor, `result.text` returned |
| `classifier.py` | `agent_framework.azure.AzureAIAgentClient` | `agents_client.get_agent()` and `agents_client.create_agent()` | WIRED | Lines 136, 153: `foundry_client.agents_client.get_agent(stored_agent_id)` and `foundry_client.agents_client.create_agent(model="gpt-4o", name="Classifier", instructions=CLASSIFIER_INSTRUCTIONS)` |
| `main.py` | `agents/classifier.py` | `ensure_classifier_agent()` called in lifespan | WIRED | Line 26 import, lines 125-129: `classifier_agent_id = await ensure_classifier_agent(foundry_client=foundry_client, stored_agent_id=settings.azure_ai_classifier_agent_id)` |
| `main.py` | `tools/classification.py` | `ClassifierTools` instantiated with cosmos_manager | WIRED | Line 37 import, lines 132-136: `ClassifierTools(cosmos_manager=cosmos_mgr, classification_threshold=settings.classification_threshold)` stored on `app.state.classifier_tools` |
| `main.py` | `agents/middleware.py` | `AuditAgentMiddleware` and `ToolTimingMiddleware` passed to `AzureAIAgentClient` | WIRED | Lines 28-30 import, line 185: `middleware=[AuditAgentMiddleware(), ToolTimingMiddleware()]` in constructor |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| AGNT-01 | 07-01, 07-02 | Classifier agent registered as a persistent Foundry agent with stable ID visible in AI Foundry portal | NEEDS HUMAN | `ensure_classifier_agent` exists and is wired; `should_cleanup_agent=False` set in main.py; persistence across restarts requires live Foundry verification |
| AGNT-02 | 07-01 | Classifier agent executes in-process Python @tool functions through Foundry callback mechanism with results written to Cosmos DB | SATISFIED | `file_capture` is a `@tool` bound to `CosmosManager`; writes to Inbox + bucket containers; returns structured dicts. NOTE: REQUIREMENTS.md text names old v1 tools (`classify_and_file`, `request_misunderstood`, `mark_as_junk`) — these were superseded by `file_capture` in this phase per CONTEXT.md locked decision. The requirement's intent (in-process @tool writing to Cosmos) is fully met. |
| AGNT-03 | 07-02 | `AzureAIAgentClient` with `should_cleanup_agent=False` manages agent lifecycle — agent persists across Container App restarts | SATISFIED (code) / NEEDS HUMAN (runtime) | `main.py:184` sets `should_cleanup_agent=False`; cross-restart persistence requires live environment validation |
| AGNT-05 | 07-01 | `transcribe_audio` is a `@tool` callable by the Classifier agent, using `gpt-4o-transcribe` via `AsyncAzureOpenAI` | SATISFIED | `TranscriptionTools.transcribe_audio` is `@tool`-decorated; calls `self._openai.audio.transcriptions.create(model=self._deployment_name)` where `deployment_name="gpt-4o-transcribe"` is passed from `settings.azure_openai_transcription_deployment`; 3 unit tests pass |
| AGNT-06 | 07-01, 07-02 | Agent middleware wired: `AgentMiddleware` for audit logging, `FunctionMiddleware` for tool validation/timing | SATISFIED | `AuditAgentMiddleware(AgentMiddleware)` and `ToolTimingMiddleware(FunctionMiddleware)` exist with correct `process()` signatures; wired to `AzureAIAgentClient` in `main.py:185`; structured logging implemented |

**Notes on AGNT-02 text drift:** The REQUIREMENTS.md description for AGNT-02 was written before this phase and references v1 tool names. This phase's PLAN and CONTEXT.md documents explicitly decided to replace those three tools with the unified `file_capture` tool (with `status="misunderstood"` replacing `request_misunderstood`, and junk unified into misunderstood). The requirement's semantic intent is satisfied; the description in REQUIREMENTS.md is now stale. It should be updated to reference `file_capture` but this is documentation debt, not a functional gap.

---

### Anti-Patterns Found

No anti-patterns found. Scans for TODO/FIXME/PLACEHOLDER, empty implementations, and stub return values all returned clean across all modified files.

---

### Human Verification Required

The four automated truth verifications pass cleanly. The following items require live Azure environment to confirm:

#### 1. Classifier Agent Portal Visibility (AGNT-01)

**Test:** Start the backend with valid Foundry credentials. Open the AI Foundry portal and navigate to the project's Agent Service.
**Expected:** An agent named "Classifier" is visible with the ID matching `AZURE_AI_CLASSIFIER_AGENT_ID`. Restart the process — the same agent ID is reused (logged: "Classifier agent loaded: id=... name=Classifier"). No new agent is created on restart.
**Why human:** Agent portal visibility and cross-restart ID stability require a live deployed environment. Static code analysis can confirm `should_cleanup_agent=False` and the `get_agent()` / `create_agent()` logic exists — but cannot verify the Foundry service honours it.

#### 2. Integration Test Suite (AGNT-01, AGNT-02)

**Test:** Run `pytest -m integration tests/test_classifier_integration.py -v` with `AZURE_AI_PROJECT_ENDPOINT` and `AZURE_AI_CLASSIFIER_AGENT_ID` set.
**Expected:** `test_classifier_agent_classifies_text` passes (Inbox container `create_item` called with `status` in `{classified, pending, misunderstood}`); `test_classifier_agent_id_is_valid` passes (`agent.name == "Classifier"`).
**Why human:** Live Foundry credentials and a deployed Classifier agent are required. Tests skip cleanly without credentials (verified: 2 skipped in automated run).

#### 3. Voice Capture Tool Chain (AGNT-05)

**Test:** Simulate a voice capture by calling the Classifier agent with a valid Azure Blob Storage URL for an audio file.
**Expected:** The agent calls `transcribe_audio(blob_url=...)` first, receives transcript text, then calls `file_capture(text=<transcript>, ...)`. Both tool calls appear in middleware timing logs.
**Why human:** Requires a real blob URL in Azure Storage and the `gpt-4o-transcribe` deployment. Unit tests mock the entire chain; end-to-end requires live Azure services.

#### 4. Middleware Console Output (AGNT-06)

**Test:** Run any live classification (text or voice) and observe stdout/Application Insights.
**Expected:** Log lines in sequence: `[Agent] Run started`, `[Tool] Calling file_capture`, `[Tool] file_capture completed in X.XXXs: bucket=... confidence=... status=... item_id=...`, `[Agent] Run completed in X.XXXs`. For `status="misunderstood"`, the ToolTimingMiddleware should fall through to the generic completion log (no `bucket` key in result for misunderstood — the code at line 66 checks `"bucket" in result`, which IS true for misunderstood since `file_capture` returns `{bucket, confidence, item_id}` regardless of status).
**Why human:** Middleware only fires during actual Foundry agent runs with real tool invocations.

---

### Summary

All automated verifications pass. The phase built exactly what the plans specified:

- `ClassifierTools.file_capture` is a substantive, wired `@tool` that writes to Cosmos DB (Inbox + bucket for classified/pending, Inbox-only for misunderstood) and returns structured dicts. 12 unit tests exercise every path.
- `TranscriptionTools.transcribe_audio` is a substantive, wired `@tool` calling `gpt-4o-transcribe` via `AsyncAzureOpenAI`. 3 unit tests cover success and both failure modes.
- `AuditAgentMiddleware` and `ToolTimingMiddleware` are substantive, wired to the `AzureAIAgentClient` constructor in `main.py`. Structured logging for AppInsights queryability is implemented.
- `ensure_classifier_agent` is substantive and wired in the FastAPI lifespan. Self-healing logic (check ID, create-if-missing, log new ID) is present and tested indirectly through import verification.
- `CLASSIFIER_INSTRUCTIONS` covers all three classification outcomes with detailed calibration guidance and the voice capture tool-chain ordering.
- `should_cleanup_agent=False` is set in `main.py:184` to prevent agent deletion on shutdown.

The 4 human verification items all require live Azure credentials. They are not gaps in the code — they are validations that can only be observed against a deployed system.

One documentation note: the REQUIREMENTS.md text for AGNT-02 still names v1 tool functions (`classify_and_file`, `request_misunderstood`, `mark_as_junk`). These were intentionally replaced by the unified `file_capture` tool in this phase. The requirement's intent is satisfied; the description text should be updated to reflect the v2 API surface.

---

_Verified: 2026-02-27T07:00:00Z_
_Verifier: Claude (gsd-verifier)_
