"""/capital — per-user capital additions and withdrawals."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import CurrentUser, require_approved
from app.db import user_client
from app.holidays import is_trading_day
from app.schemas import CapitalChangeCreate, CapitalChangeOut

router = APIRouter(prefix="/capital", tags=["capital"])


@router.get("", response_model=list[CapitalChangeOut])
def list_capital_changes(
    user: Annotated[CurrentUser, Depends(require_approved)],
    start: date | None = None,
    end: date | None = None,
) -> list[CapitalChangeOut]:
    """Caller's own capital changes (RLS scopes the query)."""
    q = (
        user_client(user.access_token)
        .table("capital_changes")
        .select("*")
        .order("date", desc=True)
    )
    if start is not None:
        q = q.gte("date", start.isoformat())
    if end is not None:
        q = q.lte("date", end.isoformat())
    return [CapitalChangeOut(**row) for row in (q.execute().data or [])]


@router.post("", response_model=CapitalChangeOut, status_code=status.HTTP_201_CREATED)
def create_capital_change(
    body: CapitalChangeCreate,
    user: Annotated[CurrentUser, Depends(require_approved)],
) -> CapitalChangeOut:
    """Create one capital change for the caller. Additions must fall on a
    Monday that is also an NYSE trading day; withdrawals may fall on any
    trading day. Amount is positive in both cases — `type` carries the sign."""
    if not is_trading_day(body.date):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{body.date} is not an NYSE trading day",
        )
    if body.type == "addition" and body.date.weekday() != 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Capital additions must fall on a Monday",
        )

    payload = {
        "user_id": user.id,
        "date": body.date.isoformat(),
        "amount": str(body.amount),
        "type": body.type,
        "note": body.note,
    }
    result = user_client(user.access_token).table("capital_changes").insert(payload).execute()
    if not result.data:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Insert returned no row")
    return CapitalChangeOut(**result.data[0])


@router.delete(
    "/{change_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_capital_change(
    change_id: UUID,
    user: Annotated[CurrentUser, Depends(require_approved)],
):
    """Delete one of the caller's own capital changes. RLS prevents deleting
    rows that don't belong to the caller (silent no-op rather than 404)."""
    user_client(user.access_token).table("capital_changes").delete().eq(
        "id", str(change_id)
    ).execute()
