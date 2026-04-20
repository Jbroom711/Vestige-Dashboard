"""/returns — shared daily reference series. Admin writes, everyone reads."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import CurrentUser, require_admin, require_approved
from app.schemas import DailyReturnCreate, DailyReturnOut

router = APIRouter(prefix="/returns", tags=["returns"])


@router.get("", response_model=list[DailyReturnOut])
def list_returns(
    user: Annotated[CurrentUser, Depends(require_approved)],
    start: date | None = None,
    end: date | None = None,
) -> list[DailyReturnOut]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.post("", response_model=DailyReturnOut, status_code=status.HTTP_201_CREATED)
def upsert_return(
    body: DailyReturnCreate,
    admin: Annotated[CurrentUser, Depends(require_admin)],
) -> DailyReturnOut:
    """Create or update a daily return. Admin-only. In balance mode, derives
    the percentage from the supplied new balance."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


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
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)
