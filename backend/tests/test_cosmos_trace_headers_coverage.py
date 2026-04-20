"""Static source scan: capture-correlated Cosmos writes must use trace_headers().

This test scans source files for Cosmos write operations (create_item, upsert_item,
replace_item) and verifies:

1. All capture-correlated files use trace_headers() on every Cosmos write.
2. Non-capture files (user-initiated endpoints) do NOT use trace_headers(),
   preventing over-instrumentation of user operations.

See SPIKE-MEMO.md section 4 (Cosmos audit table) for the authoritative list of
capture-correlated vs non-capture-correlated call sites.
"""

from __future__ import annotations

import pathlib
import re

# Root of the backend source tree
BACKEND_SRC = pathlib.Path(__file__).parent.parent / "src" / "second_brain"

# Files with capture-correlated Cosmos writes that MUST use trace_headers()
CAPTURE_CORRELATED_FILES = [
    "tools/classification.py",
    "processing/admin_handoff.py",
    "streaming/adapter.py",
    "api/capture.py",
]

# Files with user-initiated Cosmos writes that must NOT use trace_headers()
NON_CAPTURE_FILES = [
    "api/inbox.py",
    "api/tasks.py",
    "api/errands.py",
]

# Regex matching Cosmos write operations
COSMOS_WRITE_PATTERN = re.compile(r"\.(create_item|upsert_item|replace_item)\s*\(")

# Lines that are explicitly exempted from the trace_headers requirement.
# Add entries here with a comment explaining the exemption.
EXEMPTED_PATTERNS: list[str] = [
    # read_item is not a write -- sometimes appears in multi-line chains
]


def _extract_cosmos_write_lines(file_path: pathlib.Path) -> list[tuple[int, str]]:
    """Return (line_number, line_text) for each Cosmos write call in the file."""
    text = file_path.read_text()
    lines = text.splitlines()
    results: list[tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        if COSMOS_WRITE_PATTERN.search(line):
            results.append((i, line))
    return results


def _has_trace_headers_nearby(
    file_path: pathlib.Path, target_line_no: int, window: int = 5
) -> bool:
    """Check if trace_headers appears near the target line.

    For multi-line Cosmos calls, trace_headers may appear on a preceding line
    (e.g., `th = trace_headers(trace_id)` followed by `create_item(..., **th)`)
    OR on a subsequent line within the same multi-line call expression
    (e.g., `create_item(\n    body=doc, **trace_headers(...)\n)`).
    """
    text = file_path.read_text()
    lines = text.splitlines()

    # Check the target line and up to `window` lines before AND after it.
    # Multi-line calls may have trace_headers on continuation lines.
    start = max(0, target_line_no - 1 - window)
    end = min(len(lines), target_line_no + window)
    region = lines[start:end]

    for line in region:
        if "trace_headers" in line:
            return True

    # Also check if a variable containing trace_headers result is used
    # anywhere in the call's vicinity (before or after).
    # Pattern: `th = trace_headers(...)` defined earlier, then `**th` on
    # the write line or continuation lines.
    call_region_start = max(0, target_line_no - 1)
    call_region_end = min(len(lines), target_line_no + window)
    call_region = lines[call_region_start:call_region_end]

    th_var_pattern = re.compile(r"\*\*(\w+)")
    for call_line in call_region:
        for match in th_var_pattern.finditer(call_line):
            var_name = match.group(1)
            if var_name == "trace_headers":
                return True
            # Check if var_name was assigned from trace_headers earlier in the file
            assignment_pattern = re.compile(
                rf"^\s*{re.escape(var_name)}\s*=\s*trace_headers\("
            )
            for line in lines[: target_line_no + window]:
                if assignment_pattern.match(line):
                    return True

    return False


def test_capture_correlated_files_use_trace_headers() -> None:
    """Every Cosmos write in capture-correlated files must use trace_headers().

    Fails CI if a new Cosmos write is added to a capture-correlated file
    without trace_headers(), preventing correlation regression.
    """
    offenders: list[str] = []

    for rel_path in CAPTURE_CORRELATED_FILES:
        file_path = BACKEND_SRC / rel_path
        assert file_path.exists(), f"Expected source file missing: {rel_path}"

        cosmos_writes = _extract_cosmos_write_lines(file_path)
        for line_no, line_text in cosmos_writes:
            # Skip exempted patterns
            if any(exempt in line_text for exempt in EXEMPTED_PATTERNS):
                continue

            if not _has_trace_headers_nearby(file_path, line_no, window=10):
                offenders.append(f"{rel_path}:{line_no}: {line_text.strip()}")

    assert not offenders, (
        "Capture-correlated Cosmos writes missing trace_headers():\n"
        + "\n".join(f"  - {o}" for o in offenders)
        + "\n\nEvery capture-correlated Cosmos write must use "
        "trace_headers(capture_trace_id) for AzureDiagnostics correlation. "
        "See SPIKE-MEMO.md section 4."
    )


def test_non_capture_files_do_not_use_trace_headers() -> None:
    """Non-capture endpoints must NOT use trace_headers().

    Prevents over-instrumentation of user-initiated operations (inbox listing,
    task CRUD, errand management) which have no capture_trace_id context.
    """
    offenders: list[str] = []

    for rel_path in NON_CAPTURE_FILES:
        file_path = BACKEND_SRC / rel_path
        if not file_path.exists():
            # Some files may not exist yet (e.g., tasks.py if not implemented)
            continue

        text = file_path.read_text()
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            if "trace_headers" in line and not line.strip().startswith("#"):
                offenders.append(f"{rel_path}:{i}: {line.strip()}")

    assert not offenders, (
        "Non-capture files should NOT use trace_headers() "
        "(these are user-initiated operations without capture context):\n"
        + "\n".join(f"  - {o}" for o in offenders)
        + "\n\nIf this file now operates in a capture context, move it to "
        "CAPTURE_CORRELATED_FILES in this test."
    )


def test_trace_headers_import_present_in_capture_correlated_files() -> None:
    """Capture-correlated files that have Cosmos writes must import trace_headers.

    This is a quick sanity check -- if the file has Cosmos writes but no
    trace_headers import, something is wrong even if the variable-based
    check above passes (e.g., stale `th` variable from a deleted line).
    """
    offenders: list[str] = []

    for rel_path in CAPTURE_CORRELATED_FILES:
        file_path = BACKEND_SRC / rel_path
        if not file_path.exists():
            continue

        text = file_path.read_text()
        cosmos_writes = _extract_cosmos_write_lines(file_path)

        if cosmos_writes and "trace_headers" not in text:
            offenders.append(
                f"{rel_path}: has {len(cosmos_writes)} Cosmos writes "
                "but no trace_headers import/usage"
            )

    assert not offenders, (
        "Capture-correlated files with Cosmos writes must reference trace_headers:\n"
        + "\n".join(f"  - {o}" for o in offenders)
    )
