"""/dashboard — derived KPIs and time series for the caller."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, require_approved
from app.schemas import DashboardSummary, DayStateOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(
    user: Annotated[CurrentUser, Depends(require_approved)],
    as_of: date | None = None,
) -> DashboardSummary:
    """KPIs computed server-side so the frontend stays thin."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/history", response_model=list[DayStateOut])
def history(
    user: Annotated[CurrentUser, Depends(require_approved)],
    start: date | None = None,
    end: date | None = None,
) -> list[DayStateOut]:
    """Per-day evolved state for this user (prior balance, gross P&L, etc.)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)
