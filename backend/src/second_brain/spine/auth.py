"""Spine API authentication dependency.

The codebase's primary auth is a Starlette middleware (APIKeyMiddleware in
second_brain.auth). The spine router is built with an injectable auth
dependency for testability, so we wrap the same semantics - read the API
key lazily from app.state, validate the Authorization: Bearer header with
hmac.compare_digest - as an async FastAPI dependency.
"""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request


async def spine_auth(request: Request) -> None:
    """Validate API key on spine routes. Matches APIKeyMiddleware semantics."""
    api_key = getattr(request.app.state, "api_key", None)
    auth_header = request.headers.get("authorization", "")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    provided_key = auth_header[7:]
    if api_key is None or not hmac.compare_digest(provided_key, api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


__all__ = ["spine_auth"]
