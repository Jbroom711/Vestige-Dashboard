"""/profiles — user self-management and admin approval."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, get_current_user, require_admin
from app.schemas import ProfileApprove, ProfileOut, ProfileUpdateSelf

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileOut)
def get_me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> ProfileOut:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.patch("/me", response_model=ProfileOut)
def update_me(
    body: ProfileUpdateSelf,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ProfileOut:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.get("", response_model=list[ProfileOut])
def list_profiles(admin: Annotated[CurrentUser, Depends(require_admin)]) -> list[ProfileOut]:
    """Admin-only: list all profiles (pending + approved)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.patch("/{user_id}/approval", response_model=ProfileOut)
def approve_profile(
    user_id: str,
    body: ProfileApprove,
    admin: Annotated[CurrentUser, Depends(require_admin)],
) -> ProfileOut:
    """Admin-only: set status (and optionally role) of a profile."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)
