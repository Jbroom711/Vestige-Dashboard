"""/fees — per-user monthly fees (auto-calc + manual override)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, require_approved
from app.db import user_client
from app.schemas import MonthlyFeeOut, MonthlyFeeOverride
from app.state import recompute_user_fees

router = APIRouter(prefix="/fees", tags=["fees"])


@router.get("", response_model=list[MonthlyFeeOut])
def list_fees(
    user: Annotated[CurrentUser, Depends(require_approved)],
) -> list[MonthlyFeeOut]:
    """Caller's own monthly fee rows, oldest first (RLS scopes the query)."""
    rows = (
        user_client(user.access_token)
        .table("monthly_fees")
        .select("*")
        .order("year")
        .order("month")
        .execute()
    ).data or []
    return [MonthlyFeeOut(**row) for row in rows]


@router.patch("/{year}/{month}", response_model=MonthlyFeeOut)
def override_fee(
    year: int,
    month: int,
    body: MonthlyFeeOverride,
    user: Annotated[CurrentUser, Depends(require_approved)],
) -> MonthlyFeeOut:
    """Set or clear the manual override for one month.

    Pydantic semantics: omitted fields are *not* touched; fields explicitly
    set to `null` clear the override (re-defaulting to auto values).
    """
    if not (1 <= month <= 12):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "month must be 1-12")

    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Empty body: pass manual_amount and/or manual_deducted_on (use null to clear)",
        )
    if "manual_amount" in patch and patch["manual_amount"] is not None:
        patch["manual_amount"] = str(patch["manual_amount"])
    if "manual_deducted_on" in patch and patch["manual_deducted_on"] is not None:
        patch["manual_deducted_on"] = patch["manual_deducted_on"].isoformat()

    result = (
        user_client(user.access_token)
        .table("monthly_fees")
        .update(patch)
        .eq("user_id", user.id)
        .eq("year", year)
        .eq("month", month)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No fee row for {year}-{month:02d}. Run POST /fees/recompute first to seed auto values.",
        )
    return MonthlyFeeOut(**result.data[0])


@router.post("/recompute", status_code=status.HTTP_200_OK)
def recompute_fees(
    user: Annotated[CurrentUser, Depends(require_approved)],
) -> dict:
    """Regenerate auto_amount + auto_deducted_on + carryforward_* for all
    months from join_date forward. Manual override fields are left intact
    (the upsert only touches the auto/carryforward columns).
    """
    return recompute_user_fees(user.id)
