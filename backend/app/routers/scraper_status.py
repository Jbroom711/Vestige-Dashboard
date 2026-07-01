"""/scraper/status — small read-only endpoint surfaced on the dashboard
header so the user can see if the vhg.app cookie is close to expiring or
if the nightly refresh job has stopped working.

Returns:
  last_data_date: ISO date of newest daily_returns row.
  data_age_business_days: how many weekdays old that row is.
  cookie_set_at: when the active vhg cookie was last refreshed. Prefers
    `scraper_cookies.refreshed_at` (auto-updated when WordPress sends a
    sliding-session refresh) and falls back to VHG_COOKIE_SET_AT env var
    for the bootstrap case.
  cookie_age_days: today - cookie_set_at, or null.
  is_stale: True when data >=2 business days behind or cookie age >=14d.
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

    # Prefer the DB-tracked refreshed_at (auto-renewing path); fall back to
    # the bootstrap env var if there's no DB row yet.
    cookie_set: date | None = None
    db_row = (
        sb.table("scraper_cookies")
        .select("refreshed_at")
        .eq("name", "vhg")
        .limit(1)
        .execute()
        .data
    )
    if db_row:
        try:
            cookie_set = date.fromisoformat(db_row[0]["refreshed_at"][:10])
        except (ValueError, KeyError, TypeError):
            cookie_set = None
    if cookie_set is None:
        env_val = os.environ.get("VHG_COOKIE_SET_AT")
        if env_val:
            try:
                cookie_set = date.fromisoformat(env_val)
            except ValueError:
                cookie_set = None
    cookie_age = (today - cookie_set).days if cookie_set else None

    # Only data-age triggers the "stale" warning now. The cookie path is a
    # legacy fallback we haven't used since 2026-05-30 (active auth is
    # BrightData ISP proxy + credentials), so cookie age is not a real
    # signal — using it caused false-alarm amber warnings.
    is_stale = data_age is not None and data_age >= 2

    return {
        "last_data_date": last_data_date,
        "data_age_business_days": data_age,
        "cookie_set_at": cookie_set.isoformat() if cookie_set else None,
        "cookie_age_days": cookie_age,
        "is_stale": is_stale,
    }
