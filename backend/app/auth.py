"""Auth dependencies: JWT verification + role checks.

Every protected route takes `CurrentUser` as a dependency. Admin-only
routes additionally depend on `require_admin`.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError

from app.config import get_settings
from app.db import service_client

bearer_scheme = HTTPBearer(auto_error=True)


@dataclass
class CurrentUser:
    id: str
    email: str
    role: str
    status: str
    access_token: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin" and self.status == "approved"

    @property
    def is_approved(self) -> bool:
        return self.status == "approved"


@lru_cache
def _jwks_client() -> PyJWKClient:
    """Cached JWKS fetcher for verifying asymmetric Supabase tokens."""
    settings = get_settings()
    return PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


def _decode_token(token: str) -> dict:
    """Verify a Supabase access token.

    Supabase projects can issue tokens signed either with the legacy shared
    HS256 secret or with newer asymmetric keys (ES256 / RS256). We honor both
    by inspecting the token header and dispatching to the matching key.
    """
    settings = get_settings()

    try:
        header = jwt.get_unverified_header(token)
    except jwt.DecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token format: {e}",
        ) from e

    alg = header.get("alg", "")
    try:
        if alg == "HS256":
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        if alg in ("ES256", "RS256"):
            try:
                signing_key = _jwks_client().get_signing_key_from_jwt(token)
            except PyJWKClientError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Could not resolve signing key from JWKS: {e}",
                ) from e
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unsupported token alg: {alg}",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> CurrentUser:
    payload = _decode_token(credentials.credentials)
    user_id = payload.get("sub")
    email = payload.get("email", "")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing sub claim")

    # Service-role lookup: JWT doesn't carry role/status, those live in profiles
    result = (
        service_client()
        .table("profiles")
        .select("role, status")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No profile for authenticated user")

    return CurrentUser(
        id=user_id,
        email=email,
        role=result.data["role"],
        status=result.data["status"],
        access_token=credentials.credentials,
    )


def require_approved(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if not user.is_approved:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Account is pending admin approval",
        )
    return user


def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
