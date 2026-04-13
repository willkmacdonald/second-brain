# Second Brain Code Review

You are reviewing a pull request for the Second Brain project -- a personal AI-powered capture and organization system.

## Stack
- Backend: Python 3.12, FastAPI, Azure AI Foundry (Agent Framework), Cosmos DB, App Insights
- Mobile: React Native / Expo, TypeScript
- CI/CD: GitHub Actions, Azure Container Apps

## Scope

Review ONLY the files changed in this PR. The diff is available at `/tmp/pr-diff.patch` and the list of changed files is at `/tmp/pr-context.md`. Do NOT comment on existing code that was not modified by this PR.

## Review Focus

### High Priority
1. **Type safety**: TypeScript strict mode compliance (mobile), Python type hints (backend)
2. **Test health**: Run `backend/.venv/bin/pytest -q` and `cd mobile && npx tsc --noEmit --pretty false`. Report any failures.
3. **Async correctness**: Unawaited coroutines, missing await, leaked tasks
4. **Security**: SSRF protection, API key exposure, SQL/NoSQL injection, hardcoded secrets

### Medium Priority
5. **Error handling**: All external operations (API calls, DB, file I/O) wrapped in try/except with logging
6. **Observability**: New code paths emit appropriate OTel spans or log messages
7. **Consistency**: New patterns match existing codebase conventions (check middleware.py, tools/*.py patterns)

### Low Priority
8. **Documentation**: Stale references in planning docs, missing docstrings on public functions
9. **Dead code**: Unused imports, unreachable branches, commented-out code

## Output Format
- Categorize findings as Critical, High, Medium, or Minor
- Include file path and line number for each finding
- Provide specific fix recommendations
- If no issues found, say "No issues found" (don't pad with noise)

## What NOT to Flag
- Style preferences (ruff handles formatting)
- Import ordering (ruff handles this)
- Line length (ruff config in pyproject.toml)
- Planning doc formatting
