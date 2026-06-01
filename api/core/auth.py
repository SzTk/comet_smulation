import time
from typing import Any, Optional

import httpx
from fastapi import Header, HTTPException
from jose import JWTError, jwt

from api.core.config import settings

_GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUER = "https://accounts.google.com"
_JWKS_TTL = 3600

_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0


async def _fetch_jwks() -> dict[str, Any]:
    global _jwks_cache, _jwks_fetched_at
    async with httpx.AsyncClient() as client:
        resp = await client.get(_GOOGLE_JWKS_URI, timeout=10.0)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = time.monotonic()
    return _jwks_cache


async def _get_jwks() -> dict[str, Any]:
    if _jwks_cache and time.monotonic() - _jwks_fetched_at < _JWKS_TTL:
        return _jwks_cache
    return await _fetch_jwks()


async def _decode_google_jwt(token: str) -> dict[str, Any]:
    """Verify a Google ID token against JWKS, retrying once on key rotation."""
    jwks = await _get_jwks()
    try:
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=_GOOGLE_ISSUER,
        )
    except JWTError:
        global _jwks_fetched_at
        _jwks_fetched_at = 0.0
        jwks = await _fetch_jwks()
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=_GOOGLE_ISSUER,
        )


async def require_authorized_user(
    authorization: Optional[str] = Header(None),
    x_ms_token_google_id_token: Optional[str] = Header(None),
    x_ms_client_principal_name: Optional[str] = Header(None),
) -> Optional[str]:
    """FastAPI dependency. Returns verified email, or None when auth is disabled."""
    if not settings.auth_enabled:
        return None

    token: Optional[str] = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif x_ms_token_google_id_token:
        token = x_ms_token_google_id_token

    if token:
        try:
            claims = await _decode_google_jwt(token)
        except JWTError:
            raise HTTPException(
                status_code=401,
                detail={"error": "Unauthorized", "message": "Invalid or expired token"},
            )

        if not claims.get("email_verified", False):
            raise HTTPException(
                status_code=401,
                detail={"error": "Unauthorized", "message": "Email not verified"},
            )

        email: str = claims.get("email", "")
        if email not in settings.allowed_emails:
            raise HTTPException(
                status_code=403,
                detail={"error": "Forbidden", "message": "Email not authorized"},
            )

        return email

    # Fallback: trust X-MS-CLIENT-PRINCIPAL-NAME injected by Easy Auth.
    # Azure sanitizes this header (client-supplied value is stripped before reaching the app).
    if x_ms_client_principal_name and x_ms_client_principal_name in settings.allowed_emails:
        return x_ms_client_principal_name

    raise HTTPException(
        status_code=401,
        detail={"error": "Unauthorized", "message": "Authentication required"},
    )
