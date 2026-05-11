
## 24-10 — Pre-existing ruff E501 in tools/admin.py

**Discovered during:** 24-10 verification (Task 1).

**Issue:** `backend/src/second_brain/tools/admin.py:413` (was line 408 pre-strip) — `description="True if this rule was auto-saved from a HITL routing answer"` exceeds 88-char ruff limit by 1 character.

**Status:** Pre-existing on `main` before 24-10. Stash-verified: ruff was failing on the same line (different line number) before any 24-10 edit. The decorator strip didn't introduce the violation; it merely shifted the line number.

**Scope:** Out of scope for 24-10 per executor scope boundary (only auto-fix issues directly caused by the current task's changes). The plan invariant ("Annotated[..., Field(description=...)] parameter shape preserved") would be violated if we re-wrapped the string here, so leave verbatim.

**Recommended fix (separate task):** Wrap the description string into a multiline tuple, e.g. `description=("True if this rule was auto-saved " "from a HITL routing answer")`.
