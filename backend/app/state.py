"""Per-user balance evolution: load the shared daily_returns series + the
user's own capital_changes + their effective monthly_fees, hand the lot to
calc.evolve_balance, return the per-day state.

Used by:
  - /returns POST (balance entry mode needs the admin's prior balance)
  - /dashboard summary + history (any user's day-by-day state)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.calc import (
    CapitalChange,
    DailyReturn,
    DayState,
    compute_monthly_fees,
    evolve_balance,
)
from app.db import service_client


def _load_profile(user_id: str) -> tuple[Decimal, date]:
    p = (
        service_client()
        .table("profiles")
        .select("starting_balance, join_date")
        .eq("id", user_id)
        .single()
        .execute()
    ).data
    return Decimal(str(p["starting_balance"])), date.fromisoformat(p["join_date"])


def evolve_user_balance_with_inputs(
    starting: Decimal,
    join_date: date,
    user_id: str,
    until_exclusive: date | None = None,
) -> list[DayState]:
    """Variant of evolve_user_balance that takes already-fetched profile data,
    so callers that have the profile in hand avoid a redundant query."""
    returns = _load_returns(until_exclusive)
    capital = _load_capital(user_id, until_exclusive)
    fees = _load_effective_fees(user_id, until_exclusive)
    return evolve_balance(starting, join_date, returns, capital, fees)


def _load_returns(until_exclusive: date | None) -> list[DailyReturn]:
    q = service_client().table("daily_returns").select("date, gross_pl_pct").order("date")
    if until_exclusive is not None:
        q = q.lt("date", until_exclusive.isoformat())
    rows = q.execute().data or []
    return [
        DailyReturn(date=date.fromisoformat(r["date"]), gross_pl_pct=Decimal(str(r["gross_pl_pct"])))
        for r in rows
    ]


def _load_capital(user_id: str, until_exclusive: date | None) -> list[CapitalChange]:
    q = (
        service_client()
        .table("capital_changes")
        .select("date, amount, type")
        .eq("user_id", user_id)
    )
    if until_exclusive is not None:
        q = q.lt("date", until_exclusive.isoformat())
    rows = q.execute().data or []
    return [
        CapitalChange(
            date=date.fromisoformat(r["date"]),
            amount=Decimal(str(r["amount"])),
            type=r["type"],
        )
        for r in rows
    ]


def _load_effective_fees(user_id: str, until_exclusive: date | None) -> dict[date, Decimal]:
    """Resolve manual override > auto value, key by effective deduction date."""
    rows = (
        service_client()
        .table("monthly_fees")
        .select("auto_amount, auto_deducted_on, manual_amount, manual_deducted_on")
        .eq("user_id", user_id)
        .execute()
    ).data or []

    fees: dict[date, Decimal] = {}
    for r in rows:
        eff_date_str = r["manual_deducted_on"] or r["auto_deducted_on"]
        if not eff_date_str:
            continue
        eff_date = date.fromisoformat(eff_date_str)
        if until_exclusive is not None and eff_date >= until_exclusive:
            continue
        amount_src = r["manual_amount"] if r["manual_amount"] is not None else r["auto_amount"]
        if amount_src is None:
            continue
        fees[eff_date] = fees.get(eff_date, Decimal("0")) + Decimal(str(amount_src))
    return fees


def evolve_user_balance(
    user_id: str,
    until_exclusive: date | None = None,
) -> list[DayState]:
    """Per-day state for `user_id` from their join_date up to (but not
    including) `until_exclusive`. Pass None to walk through all returns."""
    starting, join_date = _load_profile(user_id)
    returns = _load_returns(until_exclusive)
    capital = _load_capital(user_id, until_exclusive)
    fees = _load_effective_fees(user_id, until_exclusive)
    return evolve_balance(starting, join_date, returns, capital, fees)


def prior_balance(user_id: str, as_of: date) -> Decimal:
    """Closing balance from the most recent state strictly before `as_of`.
    Falls back to starting_balance if no prior returns have been entered."""
    states = evolve_user_balance(user_id, until_exclusive=as_of)
    if states:
        return states[-1].closing_balance
    starting, _ = _load_profile(user_id)
    return starting


def recompute_user_fees(user_id: str) -> dict:
    """Regenerate the auto/carryforward columns of monthly_fees for every
    closed month in `user_id`'s history. Idempotent: leaves manual override
    fields untouched, skips the current (still-accruing) month, and deletes
    any stale row for the current month from a prior recompute run.

    Returns a small summary dict suitable for logging. Used by:
      - POST /fees/recompute (HTTP handler)
      - scripts/refresh_daily.py (nightly cron — after daily insert)
    """
    sb = service_client()
    profile = (
        sb.table("profiles")
        .select("commission_rate")
        .eq("id", user_id)
        .single()
        .execute()
    ).data
    if not profile:
        return {"user_id": user_id, "computed": 0, "error": "profile_not_found"}
    commission_rate = Decimal(str(profile["commission_rate"]))

    states = evolve_user_balance(user_id)
    results = compute_monthly_fees(states, commission_rate)
    if not results:
        return {"user_id": user_id, "computed": 0, "carryforward_remaining": "0"}

    today = date.today()
    current_ym = (today.year, today.month)
    written = 0
    for r in results:
        if (r.year, r.month) == current_ym:
            continue  # current month still accruing
        payload = {
            "user_id": user_id,
            "year": r.year,
            "month": r.month,
            "auto_amount": str(r.auto_amount),
            "auto_deducted_on": r.auto_deducted_on.isoformat(),
            "carryforward_used": str(r.carryforward_used),
            "carryforward_remaining": str(r.carryforward_remaining),
        }
        sb.table("monthly_fees").upsert(payload, on_conflict="user_id,year,month").execute()
        written += 1

    sb.table("monthly_fees").delete().eq("user_id", user_id).eq(
        "year", today.year
    ).eq("month", today.month).execute()

    return {
        "user_id": user_id,
        "computed": written,
        "carryforward_remaining": str(results[-1].carryforward_remaining),
    }
