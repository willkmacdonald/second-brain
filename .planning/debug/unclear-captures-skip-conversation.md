---
status: diagnosed
trigger: "Investigate why some unclear captures go straight to unclassified without entering conversation mode"
created: 2026-02-24T00:00:00Z
updated: 2026-02-24T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — LLM non-determinism + ambiguous instruction boundary between "junk" and "misunderstood"
test: Traced all three code paths to confirm mark_as_junk produces "Capture logged as unclassified"
expecting: N/A — root cause found
next_action: Return diagnosis

## Symptoms

expected: Ambiguous single-word inputs like "Xyzzy" should trigger conversation mode (request_misunderstood tool)
actual: "Xyzzy" went straight to "Capture logged as unclassified" without asking for clarification
errors: None (not an error, wrong behavior path)
reproduction: Send "Xyzzy" as capture text — sometimes triggers conversation mode, sometimes goes to unclassified
started: Phase 04.3 UAT testing

## Eliminated

- hypothesis: Bug in the adapter/workflow code path
  evidence: workflow.py correctly detects all three tool names (classify_and_file, request_misunderstood, mark_as_junk) via function_call.name inspection. The adapter faithfully emits MISUNDERSTOOD custom event when request_misunderstood is detected. No code bug — the wrong tool is being called by the LLM.
  timestamp: 2026-02-24

- hypothesis: Missing tool registration (request_misunderstood not available to classifier)
  evidence: classifier.py line 138-142 registers all three tools: classify_and_file, request_misunderstood, mark_as_junk. The LLM has access to all three.
  timestamp: 2026-02-24

## Evidence

- timestamp: 2026-02-24
  checked: classification.py mark_as_junk tool (lines 239-259)
  found: mark_as_junk returns exactly "Capture logged as unclassified" (line 259). This is the only source of that exact string in the codebase.
  implication: When the user saw "Capture logged as unclassified", the LLM called mark_as_junk, NOT request_misunderstood.

- timestamp: 2026-02-24
  checked: classifier.py instructions — Junk Detection section (lines 87-89)
  found: Junk detection says "If the input is gibberish, accidental, or nonsensical (random characters, empty phrases, keyboard mashing), call mark_as_junk". "Xyzzy" is a real word (classic text adventure reference) but looks like nonsense to an LLM.
  implication: The LLM can reasonably interpret "Xyzzy" as either gibberish/nonsensical (junk path) OR a single ambiguous word with no context (misunderstood path).

- timestamp: 2026-02-24
  checked: classifier.py instructions — Classification Decision Flow (lines 91-100)
  found: Decision tree is ordered: (1) Junk/gibberish -> mark_as_junk, (2) High confidence -> classify_and_file, (3) Low confidence -> classify_and_file, (4) Misunderstood -> request_misunderstood. Junk check comes FIRST in the decision tree.
  implication: The instruction ordering creates a bias toward the junk path. The LLM encounters "is this junk?" before "is this misunderstood?" — and for ambiguous single words, both descriptions partially match.

- timestamp: 2026-02-24
  checked: classifier.py instructions — Misunderstood signals (lines 105-110)
  found: Misunderstood signals include "Text is a single ambiguous word or very short fragment with no context" — this EXACTLY describes "Xyzzy". But the junk description also includes "nonsensical" which an LLM could also apply to "Xyzzy".
  implication: There is an overlap zone where the junk and misunderstood definitions both apply. The LLM non-deterministically picks one or the other depending on its internal state.

- timestamp: 2026-02-24
  checked: UAT results — "Aardvark" vs "Xyzzy"
  found: "Aardvark" correctly triggered conversation mode but "Xyzzy" did not. "Aardvark" is a recognizable English word (an animal), while "Xyzzy" looks more like random characters to an LLM despite being a real word.
  implication: The boundary between "recognizable but ambiguous word" (misunderstood) and "looks like gibberish" (junk) is fuzzy and LLM-dependent. "Aardvark" is clearly a real word so the LLM doesn't consider it junk. "Xyzzy" looks like random characters so the LLM may categorize it as junk.

## Resolution

root_cause: The classifier instructions have an ambiguous boundary between "junk/gibberish" (mark_as_junk) and "misunderstood" (request_misunderstood) for inputs that are real words but look nonsensical to an LLM. The junk detection check comes FIRST in the decision flow (line 92), and its description ("gibberish, accidental, or nonsensical") overlaps with the misunderstood description ("single ambiguous word or very short fragment"). For inputs like "Xyzzy" that fall in this overlap zone, the LLM non-deterministically chooses mark_as_junk (producing "Capture logged as unclassified") instead of request_misunderstood (which would enter conversation mode).
fix:
verification:
files_changed: []
