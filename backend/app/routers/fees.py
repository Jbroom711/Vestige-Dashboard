"""/fees — per-user monthly fees (auto-calc + manual override)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, require_approved
from app.schemas import MonthlyFeeOut, MonthlyFeeOverride

router = APIRouter(prefix="/fees", tags=["fees"])


@router.get("", response_model=list[MonthlyFeeOut])
def list_fees(user: Annotated[CurrentUser, Depends(require_approved)]) -> list[MonthlyFeeOut]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.patch("/{year}/{month}", response_model=MonthlyFeeOut)
def override_fee(
    year: int,
    month: int,
    body: MonthlyFeeOverride,
    user: Annotated[CurrentUser, Depends(require_approved)],
) -> MonthlyFeeOut:
    """Set or clear the manual override amount/date for a given month.
    Passing nulls clears the override and re-defaults to the auto value."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.post("/recompute", status_code=status.HTTP_202_ACCEPTED)
def recompute_fees(user: Annotated[CurrentUser, Depends(require_approved)]) -> dict[str, str]:
    """Force a recomputation of auto_amount for all the user's months from
    their join_date forward. Useful after editing older data."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)
