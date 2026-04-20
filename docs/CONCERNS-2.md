# CONCERNS-2.md — Security Review & Dead Code Analysis

**Date:** 2026-03-18
**Scope:** All Python files in `backend/src/`, `backend/tests/`, `backend/scripts/`

---

## Part 1: Security Review

### Summary
- **Files scanned:** 34 Python source files + `.env` files + Dockerfile + config files
- **Issues found:** 12 (1 critical, 6 important, 5 medium)

---

### CRITICAL Issues

**C1. API key comparison is not timing-safe**
- **File:** `backend/src/second_brain/auth.py:61`
- **Code:** `if api_key is None or provided_key != api_key:`
- **Description:** The API key is compared using Python's `!=` operator, which short-circuits on the first mismatched character. An attacker with network proximity can perform a timing side-channel attack to determine the key one character at a time (CWE-208).
- **Fix:** Replace with `hmac.compare_digest()`:
  ```python
  import hmac
  if api_key is None or not hmac.compare_digest(provided_key, api_key):
  ```

---

### IMPORTANT Issues

**I1. Cosmos DB queries use f-string interpolation with LLM-sourced input (NoSQL injection)**
- **File:** `backend/src/second_brain/tools/admin.py:254,273,320`
- **Code:** `f"SELECT * FROM c WHERE c.slug = '{slug}' AND c.userId = 'will'"`
- **Description:** The `slug` parameter comes from the Admin LLM agent's tool call arguments. While the LLM provides this value rather than a direct user, prompt injection could cause the LLM to pass a crafted slug containing single quotes that break out of the Cosmos DB SQL query string. All other Cosmos queries in the project correctly use parameterized queries with `@parameters`.
- **Fix:** Use parameterized queries consistently:
  ```python
  query = "SELECT * FROM c WHERE c.slug = @slug AND c.userId = 'will'"
  parameters = [{"name": "@slug", "value": slug}]
  ```

**I2. Exception messages streamed to mobile client expose server internals**
- **File:** `backend/src/second_brain/streaming/adapter.py:312,494,631`
- **Code:** `yield encode_sse(error_event(str(exc)))`
- **Description:** Raw Python exception messages are serialized as SSE ERROR events and sent to the mobile client. This can leak connection strings, Cosmos DB endpoint URLs, Azure SDK error details, and credential-related error messages.
- **Fix:** Send a generic error message to the client and log the full exception server-side:
  ```python
  logger.error("Capture stream error: %s", exc, exc_info=True)
  yield encode_sse(error_event("An internal error occurred. Please try again."))
  ```

**I3. Tool error responses may leak internal Cosmos DB exception details**
- **File:** `backend/src/second_brain/tools/classification.py:126`
- **Code:** `return {"error": "cosmos_write_failed", "detail": str(exc)}`
- **File:** `backend/src/second_brain/tools/cosmos_crud.py:74,99,132`
- **Code:** `return f"Error creating document in {container_name}: {exc}"`
- **Description:** Raw exception messages flow back to the LLM agent (and could be echoed to the client). They may contain Azure SDK internal details, endpoint URLs, or authentication errors.
- **Fix:** Return generic error codes to the agent without raw exception text. Log the full exception server-side.

**I4. No file upload size validation on voice capture endpoints**
- **File:** `backend/src/second_brain/api/capture.py:201,314`
- **Code:** `audio_bytes = await file.read()`
- **Description:** Voice capture endpoints read the entire uploaded file into memory without any size check. An attacker with a valid API key could upload a multi-gigabyte file to exhaust server memory.
- **Fix:** Add a size check (25 MB cap for audio) before or during read.

**I5. No file type validation on voice capture uploads**
- **File:** `backend/src/second_brain/api/capture.py:184,296`
- **Description:** No validation of `content_type` header or file extension. Non-audio files uploaded to Blob Storage persist until cleanup.
- **Fix:** Validate content type against allowed audio MIME types.

**I6. OpenAPI docs and Swagger UI publicly exposed in production**
- **File:** `backend/src/second_brain/auth.py:19`
- **Code:** `PUBLIC_PATHS: frozenset[str] = frozenset({"/health", "/docs", "/openapi.json"})`
- **Description:** `/docs` and `/openapi.json` bypass API key auth in production, exposing the complete API schema to anyone.
- **Fix:** Conditionally disable docs in production via environment variable, or remove from `PUBLIC_PATHS`.

---

### MEDIUM Issues

**M1. No input length validation on text capture body**
- **File:** `backend/src/second_brain/api/capture.py:39-44`
- **Description:** `TextCaptureBody.text` has no `max_length` constraint. Could consume excessive memory and tokens.
- **Fix:** Add `Field(max_length=10000)` to the `text` field.

**M2. No pagination limit validation on inbox list endpoint**
- **File:** `backend/src/second_brain/api/inbox.py:55`
- **Description:** `limit` and `offset` query parameters have no maximum bounds. A client could pass `limit=1000000`.
- **Fix:** Use `Query(default=20, ge=1, le=100)` and `Query(default=0, ge=0)`.

**M3. No rate limiting on API endpoints**
- **Description:** No rate limiting middleware. A compromised key or misbehaving client could exhaust Azure AI Foundry quota and Cosmos DB RUs.
- **Fix:** Consider adding `slowapi` or custom rate-limiting middleware for capture endpoints.

**M4. Hardcoded user ID "will" throughout the codebase**
- **Files:** Nearly every Cosmos DB query uses `partition_key="will"`.
- **Description:** Not a vulnerability for single-user use, but worth documenting as a known design constraint. No multi-tenant isolation exists.

**M5. Transcription tool returns raw exception text to the LLM agent**
- **File:** `backend/src/second_brain/tools/transcription.py:91`
- **Code:** `return f"Transcription error: {exc}"`
- **Fix:** Return generic "Transcription failed" message; log the full exception.

---

### Security Recommendations (Prioritized)

1. **Fix timing-safe comparison (C1)** — one-line fix, textbook vulnerability
2. **Parameterize all Cosmos DB queries (I1)** — three f-string queries in `admin.py` are the only non-parameterized ones
3. **Sanitize all error messages sent to clients (I2, I3, M5)** — adopt consistent pattern: log full exception, return generic error
4. **Add upload guardrails (I4, I5)** — file size limits and content type validation
5. **Disable OpenAPI docs in production (I6)** — environment variable toggle
6. **Add input validation bounds (M1, M2)** — Pydantic `Field` and FastAPI `Query` constraints
7. **Consider rate limiting (M3)** — protect against quota exhaustion
8. **Add `pip-audit` to CI** — check for known CVEs in dependencies

---

## Part 2: Dead Code Analysis

### Summary
- **Files scanned:** 51 (30 source, 18 test, 3 scripts)
- **Issues found:** 12

---

### Unused Modules

**D1. `backend/src/second_brain/tools/cosmos_crud.py` — Entire module is dead runtime code**
- The `CosmosCrudTools` class (`create_document`, `read_document`, `list_documents`) is never imported or instantiated by any runtime code. Not registered in `main.py`, not used by any API router or agent.
- Only imported by `backend/tests/test_cosmos_crud.py` (tests exercising dead code).
- Likely a vestige of pre-Phase 7 architecture where a generic CRUD tool was used instead of specialized `ClassifierTools` and `AdminTools`.
- **Action:** Delete module and its test file.

---

### Unused Variables/Constants

**D2. `backend/src/second_brain/main.py:124` — `app.state.foundry_credential`**
- Assigned but never read anywhere. The credential is already stored as `app.state.credential` at line 70.
- **Action:** Remove the assignment.

**D3. `backend/src/second_brain/db/cosmos.py:28` — `PARTITION_KEY = "/userId"`**
- Defined at module level but never used in any source file. Scripts define their own local constants.
- **Action:** Remove the constant.

**D4. `backend/src/second_brain/streaming/adapter.py:175,351,538` — `reasoning_buffer` (3 instances)**
- Initialized as `""` and accumulated with `+=` in all three stream functions, but the accumulated string is **never read** after the loop completes. Individual chunks are already logged via `reasoning_logger.info()`.
- **Action:** Remove all `reasoning_buffer` assignments and accumulations.

**D5. `backend/src/second_brain/tools/transcription.py:46` — `self._blob_manager`**
- `blob_manager` parameter accepted in `__init__` and stored, but never accessed. The class downloads blobs directly using `BlobClient.from_blob_url` with `self._credential`.
- **Action:** Remove parameter and attribute; update call site in `main.py`.

**D6. `backend/src/second_brain/db/blob_storage.py:53` — `filename` parameter of `upload_audio`**
- Accepted but never referenced in the method body. Blob name is always `f"{user_id}/{uuid4()}.m4a"`.
- **Action:** Remove parameter; update callers in `capture.py`.

---

### Unused Test Fixtures

**D7. `backend/tests/conftest.py:17-26` — `settings` fixture**
- Defined but never used by any test function.
- **Action:** Remove the fixture.

---

### Redundant Code

**D8. `backend/src/second_brain/streaming/adapter.py:309,491,624` — `except (TimeoutError, Exception)` (3 instances)**
- `TimeoutError` is a subclass of `Exception`, so the explicit mention is redundant and misleading.
- **Action:** Simplify to `except Exception`.

**D9. Duplicate `VALID_BUCKETS` constant**
- `backend/src/second_brain/tools/classification.py:27` and `backend/src/second_brain/api/inbox.py:23`
- Identical `{"People", "Projects", "Ideas", "Admin"}` defined in two places; could drift out of sync.
- **Action:** Extract to a shared location (e.g., `models/documents.py`).

**D10. Duplicate routing context builders**
- `backend/src/second_brain/processing/admin_handoff.py:83-137` (`_build_routing_context`)
- `backend/src/second_brain/tools/admin.py:165-205` (`get_routing_context`)
- Same purpose with slightly different formatting.
- **Action:** Consolidate into a shared implementation.

---

### Deprecated/Legacy Scripts

**D11. `backend/scripts/migrate_shopping_to_errands.py` — Completed one-time migration**
- Migrates `ShoppingLists` → `Errands`. Current code only references `Errands`. Migration is done.
- **Action:** Delete or move to `scripts/archive/`.

**D12. `backend/scripts/create_tasks_container.py` — Completed one-time container creation**
- Creates the `Tasks` container, which already exists and is in use. Also has an unused `container` variable at line 42.
- **Action:** Delete or move to `scripts/archive/`.

---

### Dead Code Recommendations (Prioritized)

**High Priority (reduces confusion and maintenance burden):**
1. Delete `cosmos_crud.py` and `test_cosmos_crud.py` (D1)
2. Remove `app.state.foundry_credential` dead assignment (D2)
3. Remove unused `self._blob_manager` from `TranscriptionTools` (D5)

**Medium Priority (noise reduction):**
4. Remove `PARTITION_KEY` constant (D3)
5. Remove `reasoning_buffer` write-only variable (D4)
6. Remove unused `filename` parameter (D6)
7. Remove unused `settings` fixture (D7)

**Low Priority (code quality):**
8. Simplify redundant exception handling (D8)
9. Consolidate duplicate `VALID_BUCKETS` (D9)
10. Consolidate duplicate routing context builders (D10)
11. Archive completed scripts (D11, D12)
