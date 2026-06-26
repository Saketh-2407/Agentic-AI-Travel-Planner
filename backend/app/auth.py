"""Verifies the Supabase-issued JWT on incoming backend requests.

Newer Supabase projects sign tokens asymmetrically (ES256) with rotating
keys published at the project's JWKS endpoint, rather than the legacy
shared HS256 secret. We verify via JWKS first (the modern + recommended
path) and fall back to the static secret for older HS256-only projects.
"""

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from app.config import get_settings

_jwk_client: PyJWKClient | None = None


def _get_jwk_client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        settings = get_settings()
        _jwk_client = PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
    return _jwk_client


def verify_jwt(token: str) -> str:
    """Returns the verified user_id (the JWT's `sub` claim). Raises HTTPException(401)."""
    settings = get_settings()
    try:
        signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(token, signing_key.key, algorithms=["ES256", "RS256"], audience="authenticated")
        return payload["sub"]
    except Exception as jwks_exc:
        if settings.supabase_jwt_secret:
            try:
                payload = jwt.decode(
                    token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated"
                )
                return payload["sub"]
            except jwt.PyJWTError as exc:
                raise HTTPException(status_code=401, detail=f"Invalid or expired token: {exc}") from exc
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {jwks_exc}") from jwks_exc


def get_current_user_id(authorization: str = Header(...)) -> str:
    """FastAPI dependency: extracts + verifies the Bearer token, returns the user_id."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return verify_jwt(authorization.removeprefix("Bearer "))
