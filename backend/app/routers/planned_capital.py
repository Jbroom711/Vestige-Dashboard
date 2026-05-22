"""/planned-capital — user's intended future deposits / withdrawals.

Distinct from /capital (which records actual past events). These rows feed
the Annual Projection tile so the user can model the year-end impact of
forward-looking deposits and withdrawals before they actually happen.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import CurrentUser, require_approved
from app.db import user_client
from app.holidays import is_trading_day
from app.schemas import PlannedCapitalChangeCreate, PlannedCapitalChangeOut

router = APIRouter(prefix="/planned-capital", tags=["planned-capital"])


@router.get("", response_model=list[PlannedCapitalChangeOut])
def list_plans(
    user: Annotated[CurrentUser, Depends(require_approved)],
) -> list[PlannedCapitalChangeOut]:
    rows = (
        user_client(user.access_token)
        .table("planned_capital_changes")
        .select("*")
        .order("date")
        .execute()
    ).data or []
    return [PlannedCapitalChangeOut(**row) for row in rows]


@router.post("", response_model=PlannedCapitalChangeOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    body: PlannedCapitalChangeCreate,
    user: Annotated[CurrentUser, Depends(require_approved)],
) -> PlannedCapitalChangeOut:
    today = date.today()
    year_end = date(today.year, 12, 31)

    if body.date <= today:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Planned date must be in the future",
        )
    if body.date > year_end:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Planned date must be within the current calendar year",
        )
    if not is_trading_day(body.date):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{body.date} is not an NYSE trading day",
        )
    if body.type == "addition" and body.date.weekday() != 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Planned deposits must fall on a Monday",
        )

    payload = {
        "user_id": user.id,
        "date": body.date.isoformat(),
        "amount": str(body.amount),
        "type": body.type,
        "note": body.note,
    }
    result = (
        user_client(user.access_token)
        .table("planned_capital_changes")
        .insert(payload)
        .execute()
    )
    if not result.data:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Insert returned no row")
    return PlannedCapitalChangeOut(**result.data[0])


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_plan(
    plan_id: UUID,
    user: Annotated[CurrentUser, Depends(require_approved)],
):
    user_client(user.access_token).table("planned_capital_changes").delete().eq(
        "id", str(plan_id)
    ).execute()
