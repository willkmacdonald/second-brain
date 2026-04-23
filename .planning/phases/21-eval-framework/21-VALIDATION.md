---
phase: 21
slug: eval-framework
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-23
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python3 -m pytest tests/test_eval.py -x -q` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/test_eval.py -x -q`
- **After every plan wave:** Run `cd backend && python3 -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | EVAL-01 | — | N/A | unit | `python3 -m pytest tests/test_eval.py -k golden_dataset` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | EVAL-02 | — | N/A | unit | `python3 -m pytest tests/test_eval.py -k classifier_eval` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | EVAL-03 | — | N/A | unit | `python3 -m pytest tests/test_eval.py -k admin_eval` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | EVAL-04 | — | N/A | unit | `python3 -m pytest tests/test_eval.py -k eval_storage` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | EVAL-05 | — | N/A | integration | `python3 -m pytest tests/test_eval.py -k eval_trigger` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_eval.py` — stubs for EVAL-01 through EVAL-05
- [ ] Test fixtures for golden dataset documents and eval results

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Mobile investigation chat triggers eval | EVAL-05 | Requires Expo dev client + deployed API | Open investigation chat, say "run classifier eval", verify results appear |
| Claude Code /investigate triggers eval | EVAL-05 | Requires MCP tool + deployed API | Run /investigate, ask "run classifier eval", verify results appear |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
