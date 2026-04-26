---
phase: 20
slug: feedback-collection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-22
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + httpx (async) |
| **Config file** | `backend/pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `cd backend && python3 -m pytest tests/test_feedback.py -x` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/test_feedback.py -x`
- **After every plan wave:** Run `cd backend && python3 -m pytest tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15s

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | FEED-01 | T-20-01 / — | Signal write failure non-fatal | unit | `python3 -m pytest tests/test_feedback.py::test_recategorize_emits_feedback -x` | ❌ W0 | ⬜ pending |
| 20-01-02 | 01 | 1 | FEED-01 | — | HITL bucket pick emits correct type | unit | `python3 -m pytest tests/test_feedback.py::test_hitl_bucket_emits_feedback -x` | ❌ W0 | ⬜ pending |
| 20-01-03 | 01 | 1 | FEED-01 | — | Errand re-route emits signal | unit | `python3 -m pytest tests/test_feedback.py::test_errand_reroute_emits_feedback -x` | ❌ W0 | ⬜ pending |
| 20-01-04 | 01 | 1 | FEED-01 | T-20-02 / — | Failure does not block primary action | unit | `python3 -m pytest tests/test_feedback.py::test_signal_failure_nonfatal -x` | ❌ W0 | ⬜ pending |
| 20-02-01 | 02 | 1 | FEED-02 | T-20-03 / V5 | Input validation on signalType | unit | `python3 -m pytest tests/test_feedback.py::test_explicit_feedback_endpoint -x` | ❌ W0 | ⬜ pending |
| 20-03-01 | 03 | 2 | FEED-04 | — | Query returns aggregated data | unit | `python3 -m pytest tests/test_feedback.py::test_query_feedback_signals -x` | ❌ W0 | ⬜ pending |
| 20-03-02 | 03 | 2 | FEED-03 | — | Promote writes GoldenDatasetDocument | unit | `python3 -m pytest tests/test_feedback.py::test_promote_to_golden_dataset -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_feedback.py` — stubs for FEED-01 through FEED-04
- [ ] No new framework install needed (pytest + httpx already configured)
- [ ] Shared fixtures in `conftest.py` already provide `mock_cosmos_manager` with all containers

*Existing infrastructure covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Thumbs up/down UI renders correctly in detail modal | FEED-02 | Mobile UI rendering not testable via pytest | Open inbox detail modal on device, verify buttons appear between timestamp and bucket sections |
| Investigation agent uses query_feedback_signals naturally | FEED-04 | Agent tool selection requires live Foundry session | Ask agent "what are the most common misclassifications?" in investigation chat |
| Conversational promote flow completes end-to-end | FEED-03 | Multi-turn agent conversation | Ask agent to show signals, then promote one; verify GoldenDataset doc created |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
