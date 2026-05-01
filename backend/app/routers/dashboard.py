"""/dashboard — derived KPIs and time series for the caller."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, require_approved
from app.calc import compute_monthly_fees, deployed_capital, forecast_year_end
from app.db import service_client
from app.schemas import DashboardSummary, DayStateOut
from app.state import evolve_user_balance

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _load_profile_essentials(user_id: str) -> tuple[Decimal, date, Decimal]:
    p = (
        service_client()
        .table("profiles")
        .select("starting_balance, join_date, commission_rate")
        .eq("id", user_id)
        .single()
        .execute()
    ).data
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return (
        Decimal(str(p["starting_balance"])),
        date.fromisoformat(p["join_date"]),
        Decimal(str(p["commission_rate"])),
    )


@router.get("/summary", response_model=DashboardSummary)
def summary(
    user: Annotated[CurrentUser, Depends(require_approved)],
    as_of: date | None = None,
) -> DashboardSummary:
    as_of = as_of or date.today()
    starting, join_date, commission_rate = _load_profile_essentials(user.id)
    states = evolve_user_balance(user.id)

    # Empty case: no returns yet.
    if not states:
        return DashboardSummary(
            as_of=as_of,
            current_balance=starting,
            deployed_capital=starting,
            mtd_gross_pl=Decimal("0"),
            mtd_accrued_fee=Decimal("0"),
            net_balance=starting,
            ytd_gain=Decimal("0"),
            avg_daily_gain_rate=Decimal("0"),
            projected_year_end_balance=starting,
        )

    latest = states[-1]
    current_balance = latest.closing_balance

    # Deployed capital: starting + signed capital_changes through as_of
    cap_rows = (
        service_client()
        .table("capital_changes")
        .select("date, amount, type")
        .eq("user_id", user.id)
        .execute()
    ).data or []
    from app.calc import CapitalChange  # local import keeps the module surface tidy
    cap_changes = [
        CapitalChange(
            date=date.fromisoformat(r["date"]),
            amount=Decimal(str(r["amount"])),
            type=r["type"],
        )
        for r in cap_rows
    ]
    deployed = deployed_capital(starting, cap_changes, as_of)

    # Month-to-date breakdown
    mtd_states = [s for s in states if s.date.year == as_of.year and s.date.month == as_of.month]
    mtd_gross_pl = sum((s.gross_pl for s in mtd_states), Decimal("0"))

    # MTD accrued fee = pending commission for the current month, factoring in
    # carryforward from prior months.
    month_start = date(as_of.year, as_of.month, 1)
    prior_states = [s for s in states if s.date < month_start]
    prior_fee_results = compute_monthly_fees(prior_states, commission_rate)
    carryforward = (
        prior_fee_results[-1].carryforward_remaining if prior_fee_results else Decimal("0")
    )
    if mtd_gross_pl > 0:
        offset = min(carryforward, mtd_gross_pl)
        accrued_fee = (mtd_gross_pl - offset) * commission_rate
    else:
        accrued_fee = Decimal("0")

    # Net balance: take the inflated current balance and subtract the unpaid
    # MTD accrual so the user sees the take-home figure.
    net_balance = current_balance - accrued_fee

    # YTD gain
    year_start = date(as_of.year, 1, 1)
    states_before_year = [s for s in states if s.date < year_start]
    balance_at_year_start = (
        states_before_year[-1].closing_balance if states_before_year else starting
    )
    ytd_gain = current_balance - balance_at_year_start

    # Forecast
    forecast = forecast_year_end(states, as_of)

    return DashboardSummary(
        as_of=as_of,
        current_balance=current_balance,
        deployed_capital=deployed,
        mtd_gross_pl=mtd_gross_pl,
        mtd_accrued_fee=accrued_fee,
        net_balance=net_balance,
        ytd_gain=ytd_gain,
        avg_daily_gain_rate=forecast.avg_daily_gain_rate,
        projected_year_end_balance=forecast.projected_closing_balance,
    )


@router.get("/history", response_model=list[DayStateOut])
def history(
    user: Annotated[CurrentUser, Depends(require_approved)],
    start: date | None = None,
    end: date | None = None,
) -> list[DayStateOut]:
    """Per-day evolved state for the caller. Optional date-range filter."""
    states = evolve_user_balance(user.id)
    if start is not None:
        states = [s for s in states if s.date >= start]
    if end is not None:
        states = [s for s in states if s.date <= end]
    return [
        DayStateOut(
            date=s.date,
            prior_balance=s.prior_balance,
            gross_pl=s.gross_pl,
            capital_net=s.capital_net,
            fee_deducted=s.fee_deducted,
            closing_balance=s.closing_balance,
        )
        for s in states
    ]
