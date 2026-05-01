"""/returns — shared daily reference series. Admin writes, everyone reads."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import CurrentUser, require_admin, require_approved
from app.calc import derive_pct_from_balance
from app.db import service_client
from app.holidays import is_trading_day
from app.schemas import DailyReturnCreate, DailyReturnOut
from app.state import prior_balance

router = APIRouter(prefix="/returns", tags=["returns"])


@router.get("", response_model=list[DailyReturnOut])
def list_returns(
    user: Annotated[CurrentUser, Depends(require_approved)],
    start: date | None = None,
    end: date | None = None,
) -> list[DailyReturnOut]:
    q = service_client().table("daily_returns").select("*").order("date")
    if start is not None:
        q = q.gte("date", start.isoformat())
    if end is not None:
        q = q.lte("date", end.isoformat())
    return [DailyReturnOut(**row) for row in (q.execute().data or [])]


@router.post("", response_model=DailyReturnOut, status_code=status.HTTP_201_CREATED)
def upsert_return(
    body: DailyReturnCreate,
    admin: Annotated[CurrentUser, Depends(require_admin)],
) -> DailyReturnOut:
    """Create or replace a daily return row for `body.date`. Admin-only.

    `entry_mode='percent'` consumes `gross_pl_pct` directly. `entry_mode='balance'`
    consumes `raw_balance` and back-solves the percentage from the calling
    admin's prior closing balance.
    """
    if not is_trading_day(body.date):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{body.date} is not an NYSE trading day",
        )
    if body.date > date.today():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot enter a return for a future date",
        )

    if body.entry_mode == "percent":
        if body.gross_pl_pct is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "gross_pl_pct is required when entry_mode='percent'",
            )
        gross_pct = body.gross_pl_pct
        raw_balance: Decimal | None = None
    else:  # balance mode
        if body.raw_balance is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "raw_balance is required when entry_mode='balance'",
            )
        prior = prior_balance(admin.id, body.date)
        if prior <= 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Cannot use balance mode without a positive prior balance — "
                "set starting_balance on your profile first or use percent mode",
            )
        gross_pct = derive_pct_from_balance(prior, body.raw_balance)
        raw_balance = body.raw_balance

    payload = {
        "date": body.date.isoformat(),
        "gross_pl_pct": str(gross_pct),
        "entry_mode": body.entry_mode,
        "raw_balance": str(raw_balance) if raw_balance is not None else None,
        "entered_by": admin.id,
    }
    result = (
        service_client()
        .table("daily_returns")
        .upsert(payload, on_conflict="date")
        .execute()
    )
    if not result.data:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Upsert returned no row")
    return DailyReturnOut(**result.data[0])


@router.delete(
    "/{d}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_return(
    d: date,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    service_client().table("daily_returns").delete().eq("date", d.isoformat()).execute()
