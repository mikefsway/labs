"""Clerk JWT verification via JWKS (RS256)."""

import time
from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from app.config import get_settings


class ClerkAuthError(Exception):
    pass


_JWKS_TTL_SECONDS = 3600
_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0.0}


def _fetch_jwks(force: bool = False) -> list[dict]:
    now = time.time()
    if (
        not force
        and _jwks_cache["keys"] is not None
        and now - _jwks_cache["fetched_at"] < _JWKS_TTL_SECONDS
    ):
        return _jwks_cache["keys"]
    issuer = get_settings().clerk_jwt_issuer_url.rstrip("/")
    if not issuer:
        raise ClerkAuthError("CLERK_JWT_ISSUER_URL not configured")
    resp = httpx.get(f"{issuer}/.well-known/jwks.json", timeout=10)
    resp.raise_for_status()
    keys = resp.json().get("keys", [])
    _jwks_cache["keys"] = keys
    _jwks_cache["fetched_at"] = now
    return keys


def _get_signing_key(kid: str):
    for key in _fetch_jwks():
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(key)
    # Key rotation — force-refresh once before giving up.
    for key in _fetch_jwks(force=True):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(key)
    raise ClerkAuthError(f"No JWKS key for kid={kid}")


def verify_clerk_token(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise ClerkAuthError(f"malformed token: {exc}") from exc
    kid = header.get("kid")
    if not kid:
        raise ClerkAuthError("token missing kid")
    signing_key = _get_signing_key(kid)
    issuer = get_settings().clerk_jwt_issuer_url.rstrip("/")
    try:
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["exp", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise ClerkAuthError(f"token verification failed: {exc}") from exc
