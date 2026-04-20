"""Auth dependencies: JWT verification + role checks.

Every protected route takes `CurrentUser` as a dependency. Admin-only
routes additionally depend on `require_admin`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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


def _decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
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
