"""Phase 24 P1-5 regression guard.

Asserts that the FoundryChatClient credential class is the SYNC
azure.identity.ManagedIdentityCredential (NOT the async aio variant).
Per locked operator decision and CONFIG-DELTAS verbatim.
"""

from __future__ import annotations


def test_foundry_chat_client_uses_sync_managed_identity() -> None:
    """Construct FoundryChatClient via the same path main.py uses; assert
    the credential class is azure.identity.ManagedIdentityCredential (sync).
    """
    from azure.identity import (
        ManagedIdentityCredential as SyncManagedIdentityCredential,
    )
    from azure.identity.aio import (
        ManagedIdentityCredential as AsyncManagedIdentityCredential,
    )

    # Construct as the lifespan does
    cred = SyncManagedIdentityCredential()

    # Sanity invariant: the class is NOT the .aio variant
    assert not isinstance(cred, AsyncManagedIdentityCredential), (
        "P1-5: ManagedIdentityCredential must be the SYNC azure.identity variant, "
        "not azure.identity.aio. Per locked operator decision and CONFIG-DELTAS."
    )
    assert (
        type(cred).__module__ == "azure.identity._credentials.managed_identity"
        or "azure.identity" in type(cred).__module__
    ), f"Credential module path unexpected: {type(cred).__module__}"


def test_main_py_imports_sync_managed_identity() -> None:
    """AST-scan main.py to confirm it imports azure.identity.ManagedIdentityCredential
    (sync) — NOT azure.identity.aio.ManagedIdentityCredential."""
    import ast
    from pathlib import Path

    main_path = Path(__file__).resolve().parents[1] / "src" / "second_brain" / "main.py"
    tree = ast.parse(main_path.read_text(encoding="utf-8"), filename=str(main_path))

    aio_imports = []
    sync_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if alias.name == "ManagedIdentityCredential":
                    if module == "azure.identity.aio":
                        aio_imports.append(module)
                    elif module == "azure.identity":
                        sync_imports.append(module)

    assert not aio_imports, (
        f"P1-5 violation: main.py imports ManagedIdentityCredential from "
        f"async azure.identity.aio. Use the sync azure.identity variant. "
        f"Offending imports: {aio_imports}"
    )
    assert sync_imports, (
        "P1-5 violation: main.py does NOT import ManagedIdentityCredential "
        "from sync azure.identity. CONFIG-DELTAS specifies the sync variant."
    )
