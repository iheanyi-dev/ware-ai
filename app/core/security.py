# app/core/security.py
"""
Internal service-to-service authentication.

This service is only meant to be called by the main backend, never
directly by end users/browsers — so instead of per-user auth (JWTs,
sessions, etc.), we use a single shared secret (INTERNAL_API_KEY) that
both sides know. The main backend sends it as:

    Authorization: Bearer <INTERNAL_API_KEY>

Used as a FastAPI dependency on any route that should be protected —
see app/api/routes/recommendations.py for how it's applied.
"""

import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

# auto_error=False so we can raise our own 401 with a consistent error
# body, instead of FastAPI's default (which varies slightly depending on
# whether the header is missing vs malformed).
bearer_scheme = HTTPBearer(auto_error=False)


def verify_internal_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    """
    FastAPI dependency — raises 401 if the request isn't authenticated as
    the main backend. Add `Depends(verify_internal_api_key)` to any route
    (or an entire router) that should require this.
    """
    settings = get_settings()

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Expected: Bearer <INTERNAL_API_KEY>",
        )

    # hmac.compare_digest instead of `==` — plain string comparison exits
    # early on the first mismatched character, which leaks (via response
    # timing) how many characters of the key were guessed correctly.
    # compare_digest runs in constant time regardless of where the
    # mismatch is, closing that timing side-channel.
    is_valid = hmac.compare_digest(credentials.credentials, settings.INTERNAL_API_KEY)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )