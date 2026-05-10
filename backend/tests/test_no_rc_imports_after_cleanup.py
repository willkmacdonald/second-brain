"""Phase 24 P1-4 regression guard.

Walks backend/src/second_brain/ and asserts zero references to the RC SDK
namespace. Fails if any future commit re-introduces an import like:
    from agent_framework.azure import AzureAIAgentClient
    import agent_framework_azure_ai
    from agent_framework_azure_ai import ...

NOTE: This test starts RED at plan 24-02 (10 source files still import RC).
It turns GREEN incrementally as plans 24-04 → 24-19 strip RC imports.
After 24-19, it stays GREEN as a permanent regression guard.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "second_brain"

FORBIDDEN_PREFIXES = (
    "agent_framework.azure",
    "agent_framework_azure_ai",
)
FORBIDDEN_NAMES = ("AzureAIAgentClient",)


def _iter_py_files() -> list[Path]:
    return [p for p in SRC_ROOT.rglob("*.py") if p.is_file()]


def _imports_in(tree: ast.AST) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                pairs.append((alias.name, ""))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                pairs.append((module, alias.name))
    return pairs


def _name_references(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.attr, str):
                names.add(node.attr)
    return names


def test_no_rc_imports_under_src() -> None:
    files = _iter_py_files()
    assert files, f"No source files found under {SRC_ROOT} — test setup wrong."

    offenders: list[str] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            pytest.fail(f"Syntax error parsing {path}: {exc}")

        for module, name in _imports_in(tree):
            for prefix in FORBIDDEN_PREFIXES:
                if module == prefix or module.startswith(prefix + "."):
                    offenders.append(
                        f"{path.relative_to(SRC_ROOT.parent)}: imports {module!r} (name={name!r})"
                    )
            if name in FORBIDDEN_NAMES:
                offenders.append(
                    f"{path.relative_to(SRC_ROOT.parent)}: imports name {name!r} from {module!r}"
                )

        for ref in _name_references(tree):
            if ref in FORBIDDEN_NAMES:
                offenders.append(
                    f"{path.relative_to(SRC_ROOT.parent)}: references identifier {ref!r}"
                )

    assert not offenders, (
        "RC SDK imports/references found under backend/src/second_brain/. "
        "Phase 24 P1-4 mandates ZERO references after Wave 2-4 ships.\n"
        + "\n".join(f"  - {o}" for o in sorted(set(offenders)))
    )
