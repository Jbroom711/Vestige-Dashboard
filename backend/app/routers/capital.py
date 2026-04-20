"""/capital — per-user capital additions and withdrawals."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import CurrentUser, require_approved
from app.schemas import CapitalChangeCreate, CapitalChangeOut

router = APIRouter(prefix="/capital", tags=["capital"])


@router.get("", response_model=list[CapitalChangeOut])
def list_capital_changes(
    user: Annotated[CurrentUser, Depends(require_approved)],
    start: date | None = None,
    end: date | None = None,
) -> list[CapitalChangeOut]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.post("", response_model=CapitalChangeOut, status_code=status.HTTP_201_CREATED)
def create_capital_change(
    body: CapitalChangeCreate,
    user: Annotated[CurrentUser, Depends(require_approved)],
) -> CapitalChangeOut:
    """Create a capital change. Additions must fall on a Monday that is also a
    trading day; withdrawals may fall on any trading day. Rule enforced here,
    not in the DB."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


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
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)
