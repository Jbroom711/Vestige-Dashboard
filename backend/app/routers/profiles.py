"""/profiles — user self-management and admin approval."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, get_current_user, require_admin
from app.db import service_client, user_client
from app.schemas import ProfileApprove, ProfileOut, ProfileUpdateSelf

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _profile_or_404(user_id: str) -> dict:
    """Service-role lookup. Bypasses RLS — caller must have authorized access."""
    result = (
        service_client()
        .table("profiles")
        .select("*")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return result.data


@router.get("/me", response_model=ProfileOut)
def get_me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> ProfileOut:
    """Caller's own profile. Pending users CAN read this — we don't gate it
    behind require_approved so they can see their own status on /pending."""
    return ProfileOut(**_profile_or_404(user.id))


@router.patch("/me", response_model=ProfileOut)
def update_me(
    body: ProfileUpdateSelf,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ProfileOut:
    """Update fields the user is allowed to set on themselves. role and status
    are guarded by the prevent_self_role_change DB trigger."""
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return ProfileOut(**_profile_or_404(user.id))

    if "starting_balance" in patch:
        patch["starting_balance"] = str(patch["starting_balance"])

    result = (
        user_client(user.access_token)
        .table("profiles")
        .update(patch)
        .eq("id", user.id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return ProfileOut(**result.data[0])


@router.get("", response_model=list[ProfileOut])
def list_profiles(
    admin: Annotated[CurrentUser, Depends(require_admin)],
) -> list[ProfileOut]:
    """Admin-only: list every profile, ordered by status (pending first) then email."""
    result = (
        service_client()
        .table("profiles")
        .select("*")
        .order("status")
        .order("email")
        .execute()
    )
    return [ProfileOut(**row) for row in (result.data or [])]


@router.patch("/{user_id}/approval", response_model=ProfileOut)
def approve_profile(
    user_id: str,
    body: ProfileApprove,
    admin: Annotated[CurrentUser, Depends(require_admin)],
) -> ProfileOut:
    """Admin-only: change a profile's status (and optionally role)."""
    patch: dict = {"status": body.status}
    if body.role is not None:
        patch["role"] = body.role

    result = (
        service_client()
        .table("profiles")
        .update(patch)
        .eq("id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return ProfileOut(**result.data[0])
