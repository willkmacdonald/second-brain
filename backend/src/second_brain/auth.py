"""API key authentication middleware with security logging.

Uses Starlette BaseHTTPMiddleware (justified per CLAUDE.md -- framework pattern).
Key passed via Authorization: Bearer <key> header (per locked CONTEXT.md decision).
Failed auth attempts logged with IP/timestamp for security auditing.
"""

import logging
from datetime import UTC, datetime

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger("second_brain.auth")

# Paths that bypass authentication
PUBLIC_PATHS: frozenset[str] = frozenset({"/health", "/docs", "/openapi.json"})


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware that validates API key from Authorization: Bearer <key> header.

    Public paths (/health, /docs, /openapi.json) bypass authentication.
    Failed attempts are logged with client IP, timestamp, and AUTH_FAILED marker.

    The API key is read lazily from app.state.api_key at request time,
    allowing the middleware to be registered before the lifespan fetches
    the key from Azure Key Vault.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Validate the API key on each request.

        Allows public paths without auth. Extracts the key from the
        Authorization: Bearer <key> header format.
        """
        # Allow public paths without authentication
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Read API key lazily from app.state (set by lifespan after Key Vault fetch)
        api_key = getattr(request.app.state, "api_key", None)

        # Extract Authorization header
        auth_header = request.headers.get("authorization", "")

        # Validate Bearer format and key
        if not auth_header.startswith("Bearer "):
            self._log_auth_failure(request, "missing or malformed Authorization header")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        provided_key = auth_header[7:]  # Strip "Bearer " prefix

        if api_key is None or provided_key != api_key:
            self._log_auth_failure(request, "invalid API key")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)

    def _log_auth_failure(self, request: Request, reason: str) -> None:
        """Log a failed authentication attempt with security context."""
        client_ip = request.client.host if request.client else "unknown"
        timestamp = datetime.now(UTC).isoformat()

        logger.warning(
            "AUTH_FAILED ip=%s timestamp=%s path=%s reason=%s",
            client_ip,
            timestamp,
            request.url.path,
            reason,
        )
