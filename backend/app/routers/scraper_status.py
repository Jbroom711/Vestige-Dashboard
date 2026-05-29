"""/scraper/status — small read-only endpoint surfaced on the dashboard
header so the user can see if the vhg.app cookie is close to expiring or
if the nightly refresh job has stopped working.

Returns:
  last_data_date: ISO date of newest daily_returns row.
  data_age_business_days: how many weekdays old that row is (excludes
    weekends; doesn't subtract NYSE holidays — close enough).
  cookie_set_at: ISO date the user last refreshed VHG_COOKIE
    (sourced from VHG_COOKIE_SET_AT env var; null when unset).
  cookie_age_days: today - cookie_set_at, or null.
  is_stale: convenience flag the UI uses to decide whether to highlight
    the line. True when data is >=2 business days behind or cookie age
    is >=14 days.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import CurrentUser, require_approved
from app.db import service_client

router = APIRouter(prefix="/scraper", tags=["scraper"])


def _business_days_between(start: date, end: date) -> int:
    """Mon-Fri count, inclusive of `end` but exclusive of `start`.
    Approximation — ignores NYSE holidays."""
    if end <= start:
        return 0
    days = 0
    cur = start + timedelta(days=1)
    while cur <= end:
        if cur.weekday() < 5:
            days += 1
        cur += timedelta(days=1)
    return days


@router.get("/status")
def status(_: Annotated[CurrentUser, Depends(require_approved)]) -> dict[str, object]:
    today = date.today()
    sb = service_client()
    row = (
        sb.table("daily_returns")
        .select("date")
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    last_data_date = row[0]["date"] if row else None
    if last_data_date:
        data_age = _business_days_between(date.fromisoformat(last_data_date), today)
    else:
        data_age = None

    cookie_set_at_raw = os.environ.get("VHG_COOKIE_SET_AT")
    if cookie_set_at_raw:
        try:
            cookie_set = date.fromisoformat(cookie_set_at_raw)
            cookie_age = (today - cookie_set).days
        except ValueError:
            cookie_set, cookie_age = None, None
    else:
        cookie_set, cookie_age = None, None

    is_stale = (data_age is not None and data_age >= 2) or (
        cookie_age is not None and cookie_age >= 14
    )

    return {
        "last_data_date": last_data_date,
        "data_age_business_days": data_age,
        "cookie_set_at": cookie_set.isoformat() if cookie_set else None,
        "cookie_age_days": cookie_age,
        "is_stale": is_stale,
    }
