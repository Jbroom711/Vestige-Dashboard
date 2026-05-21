"""/dashboard — derived KPIs and time series for the caller."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, require_approved
from app.calc import (
    CapitalChange,
    compute_monthly_fees,
    deployed_capital,
    forecast_year_end,
)
from app.db import service_client
from app.holidays import prev_trading_day, trading_days_between
from app.schemas import (
    BalancePoint,
    DailyBarPoint,
    DailyTile,
    DashboardSnapshot,
    DashboardSummary,
    DayStateOut,
    MonthTile,
    YearTile,
)
from app.state import evolve_user_balance, evolve_user_balance_with_inputs

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ZERO = Decimal("0")


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


def _load_capital_changes(user_id: str) -> list[CapitalChange]:
    rows = (
        service_client()
        .table("capital_changes")
        .select("date, amount, type")
        .eq("user_id", user_id)
        .order("date")
        .execute()
    ).data or []
    return [
        CapitalChange(
            date=date.fromisoformat(r["date"]),
            amount=Decimal(str(r["amount"])),
            type=r["type"],
        )
        for r in rows
    ]


def _safe_pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return ZERO
    return numerator / denominator


@router.get("/summary", response_model=DashboardSummary)
def summary(
    user: Annotated[CurrentUser, Depends(require_approved)],
    as_of: date | None = None,
) -> DashboardSummary:
    as_of = as_of or date.today()
    starting, join_date, commission_rate = _load_profile_essentials(user.id)
    states = evolve_user_balance_with_inputs(starting, join_date, user.id)

    if not states:
        return DashboardSummary(
            as_of=as_of,
            current_balance=starting,
            deployed_capital=starting,
            mtd_gross_pl=ZERO,
            mtd_accrued_fee=ZERO,
            net_balance=starting,
            ytd_gain=ZERO,
            avg_daily_gain_rate=ZERO,
            projected_year_end_balance=starting,
        )

    latest = states[-1]
    current_balance = latest.closing_balance

    cap_changes = _load_capital_changes(user.id)
    deployed = deployed_capital(starting, cap_changes, as_of)

    mtd_states = [s for s in states if s.date.year == as_of.year and s.date.month == as_of.month]
    mtd_gross_pl = sum((s.gross_pl for s in mtd_states), ZERO)

    month_start = date(as_of.year, as_of.month, 1)
    prior_states = [s for s in states if s.date < month_start]
    prior_fee_results = compute_monthly_fees(prior_states, commission_rate)
    carryforward = (
        prior_fee_results[-1].carryforward_remaining if prior_fee_results else ZERO
    )
    if mtd_gross_pl > 0:
        offset = min(carryforward, mtd_gross_pl)
        accrued_fee = (mtd_gross_pl - offset) * commission_rate
    else:
        accrued_fee = ZERO

    net_balance = current_balance - accrued_fee

    year_start = date(as_of.year, 1, 1)
    states_before_year = [s for s in states if s.date < year_start]
    balance_at_year_start = (
        states_before_year[-1].closing_balance if states_before_year else starting
    )
    ytd_gain = current_balance - balance_at_year_start

    forecast = forecast_year_end(states, as_of, commission_rate)

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


@router.get("/snapshot", response_model=DashboardSnapshot)
def snapshot(
    user: Annotated[CurrentUser, Depends(require_approved)],
    as_of: date | None = None,
) -> DashboardSnapshot:
    """Composite payload backing the dashboard view: yesterday tile, MTD tile,
    YTD tile, daily bar chart points, balance-over-time series."""
    as_of = as_of or date.today()
    starting, join_date, commission_rate = _load_profile_essentials(user.id)
    states = evolve_user_balance_with_inputs(starting, join_date, user.id)

    def daily_net(gross: Decimal) -> Decimal:
        # Per-day rule: keep 60% on winners, eat the full loss on losers.
        return gross * (Decimal("1") - commission_rate) if gross > 0 else gross

    # ---- empty case ------------------------------------------------------
    if not states:
        empty_daily = DailyTile(
            label="Last day",
            trading_date=None,
            gross_pl=ZERO, gross_pct=ZERO, net_pl=ZERO, net_pct=ZERO,
            avg_gross_pct_to_date=None, avg_net_pct_to_date=None,
        )
        return DashboardSnapshot(
            as_of=as_of,
            current_balance=starting,
            deployed_capital=starting,
            yesterday=empty_daily,
            month=MonthTile(
                year=as_of.year, month=as_of.month,
                gross_pl=ZERO, gross_pct=ZERO, net_pl=ZERO, net_pct=ZERO,
                avg_daily_gross_rate=ZERO, avg_daily_net_rate=ZERO,
                remaining_trading_days=0, total_trading_days=0,
                projected_gross_pl=ZERO, projected_net_pl=ZERO,
                projected_gross_pct=ZERO, projected_net_pct=ZERO,
            ),
            year=YearTile(
                year=as_of.year,
                gross_pl=ZERO, gross_pct=ZERO, net_pl=ZERO, net_pct=ZERO,
                avg_daily_gross_rate=ZERO, avg_daily_net_rate=ZERO,
                remaining_trading_days=0, total_trading_days=0,
                projected_gross_pl=ZERO, projected_net_pl=ZERO,
                projected_gross_pct=ZERO, projected_net_pct=ZERO,
                projected_year_end_balance=starting,
            ),
            monthly_bars=[],
            monthly_avg_gross_pl=ZERO,
            monthly_avg_net_pl=ZERO,
            all_time_avg_gross_pl=ZERO,
            all_time_avg_net_pl=ZERO,
            balance_series=[],
        )

    cap_changes = _load_capital_changes(user.id)

    # ---- yesterday tile --------------------------------------------------
    latest = states[-1]
    if latest.date == as_of:
        label = "Today"
    elif latest.date == prev_trading_day(as_of):
        label = "Yesterday"
    else:
        label = "Last day"

    gross_pct_latest = _safe_pct(latest.gross_pl, latest.prior_balance)
    net_pl_latest = daily_net(latest.gross_pl)
    net_pct_latest = _safe_pct(net_pl_latest, latest.prior_balance)

    if len(states) >= 4:
        prior = states[:-1]
        gross_pcts = [_safe_pct(s.gross_pl, s.prior_balance) for s in prior]
        net_pcts = [_safe_pct(daily_net(s.gross_pl), s.prior_balance) for s in prior]
        avg_gross_pct = sum(gross_pcts, ZERO) / Decimal(len(gross_pcts))
        avg_net_pct = sum(net_pcts, ZERO) / Decimal(len(net_pcts))
    else:
        avg_gross_pct = None
        avg_net_pct = None

    yesterday_tile = DailyTile(
        label=label,
        trading_date=latest.date,
        gross_pl=latest.gross_pl,
        gross_pct=gross_pct_latest,
        net_pl=net_pl_latest,
        net_pct=net_pct_latest,
        avg_gross_pct_to_date=avg_gross_pct,
        avg_net_pct_to_date=avg_net_pct,
    )

    # ---- month tile ------------------------------------------------------
    month_start = date(as_of.year, as_of.month, 1)
    states_before_month = [s for s in states if s.date < month_start]
    mtd_states = [s for s in states if s.date >= month_start]
    mtd_gross = sum((s.gross_pl for s in mtd_states), ZERO)

    prior_fee_results = compute_monthly_fees(states_before_month, commission_rate)
    cf_at_month_start = (
        prior_fee_results[-1].carryforward_remaining if prior_fee_results else ZERO
    )
    if mtd_gross > 0:
        offset = min(cf_at_month_start, mtd_gross)
        accrued_fee = (mtd_gross - offset) * commission_rate
    else:
        accrued_fee = ZERO
    mtd_net = mtd_gross - accrued_fee

    balance_at_month_start = (
        states_before_month[-1].closing_balance if states_before_month else starting
    )

    # ---- Month projection ----
    # Geo-mean MTD daily gross and net rates (used for the SIMPLE bar %).
    mtd_active = [s for s in mtd_states if s.prior_balance > 0 and s.gross_pl != 0]
    if mtd_active:
        fg = Decimal("1")
        fn = Decimal("1")
        for s in mtd_active:
            fg *= (Decimal("1") + s.gross_pl / s.prior_balance)
            fn *= (Decimal("1") + daily_net(s.gross_pl) / s.prior_balance)
        n = Decimal(len(mtd_active))
        month_avg_gross_rate = fg ** (Decimal("1") / n) - Decimal("1")
        month_avg_net_rate = fn ** (Decimal("1") / n) - Decimal("1")
    else:
        month_avg_gross_rate = ZERO
        month_avg_net_rate = ZERO

    # Trading-day counts (NYSE, no active-rate adjustment now).
    if as_of.month == 12:
        month_last_day = date(as_of.year, 12, 31)
    else:
        month_last_day = date(as_of.year, as_of.month + 1, 1) - timedelta(days=1)
    month_first_day = date(as_of.year, as_of.month, 1)
    total_month_nyse = len(trading_days_between(month_first_day, month_last_day))
    nyse_remaining_month = len(trading_days_between(as_of + timedelta(days=1), month_last_day))

    # Compound $ projection: geo-rate compounded over remaining NYSE days,
    # then 40% fee on the resulting full month gross.
    if month_avg_gross_rate > 0 and nyse_remaining_month > 0:
        proj_remainder_factor = (Decimal("1") + month_avg_gross_rate) ** Decimal(nyse_remaining_month)
        proj_remainder_gross = latest.closing_balance * (proj_remainder_factor - Decimal("1"))
    else:
        proj_remainder_gross = ZERO
    month_proj_gross = mtd_gross + proj_remainder_gross
    if month_proj_gross > 0:
        month_proj_net = month_proj_gross * (Decimal("1") - commission_rate)
    else:
        month_proj_net = month_proj_gross

    # SIMPLE projected % (what shows inside the bar): avg_daily × total_days
    month_simple_proj_gross_pct = month_avg_gross_rate * Decimal(total_month_nyse)
    month_simple_proj_net_pct = month_avg_net_rate * Decimal(total_month_nyse)

    month_tile = MonthTile(
        year=as_of.year,
        month=as_of.month,
        gross_pl=mtd_gross,
        gross_pct=_safe_pct(mtd_gross, balance_at_month_start),
        net_pl=mtd_net,
        net_pct=_safe_pct(mtd_net, balance_at_month_start),
        avg_daily_gross_rate=month_avg_gross_rate,
        avg_daily_net_rate=month_avg_net_rate,
        remaining_trading_days=nyse_remaining_month,
        total_trading_days=total_month_nyse,
        projected_gross_pl=month_proj_gross,
        projected_net_pl=month_proj_net,
        projected_gross_pct=month_simple_proj_gross_pct,
        projected_net_pct=month_simple_proj_net_pct,
    )

    # ---- year tile -------------------------------------------------------
    year_start = date(as_of.year, 1, 1)
    states_before_year = [s for s in states if s.date < year_start]
    ytd_states = [s for s in states if s.date >= year_start]
    ytd_gross = sum((s.gross_pl for s in ytd_states), ZERO)

    # Effective fees for closed months come from the monthly_fees table —
    # manual override wins, falling back to the auto value. This honors any
    # out-of-band fees the user knows about (e.g., the broker lumped two
    # months together) instead of re-deriving from the gross.
    fee_rows = (
        service_client()
        .table("monthly_fees")
        .select("year, month, auto_amount, manual_amount")
        .eq("user_id", user.id)
        .execute()
    ).data or []
    effective_fee_by_ym: dict[tuple[int, int], Decimal] = {}
    for r in fee_rows:
        eff = (
            Decimal(str(r["manual_amount"]))
            if r["manual_amount"] is not None
            else Decimal(str(r["auto_amount"]))
        )
        effective_fee_by_ym[(r["year"], r["month"])] = eff

    ytd_total_fee = ZERO
    months_in_ytd = sorted({(s.date.year, s.date.month) for s in ytd_states})
    current_ym = (as_of.year, as_of.month)
    for ym in months_in_ytd:
        if ym == current_ym:
            # Current month — use the running accrual computed for MTD.
            ytd_total_fee += accrued_fee
        elif ym in effective_fee_by_ym:
            # Closed month with a stored fee row — use the effective value.
            ytd_total_fee += effective_fee_by_ym[ym]
        else:
            # Closed month with no row yet — fall back to a simple calc on
            # the month's gross (carryforward not modeled here; once
            # /fees/recompute is run, the row will exist with the proper
            # value and this branch becomes unreachable).
            month_states = [s for s in ytd_states if (s.date.year, s.date.month) == ym]
            month_gross = sum((s.gross_pl for s in month_states), ZERO)
            if month_gross > 0:
                ytd_total_fee += month_gross * commission_rate
    ytd_net = ytd_gross - ytd_total_fee

    balance_at_year_start = (
        states_before_year[-1].closing_balance if states_before_year else starting
    )
    # ---- Year projection ----
    # Geo-mean YTD daily gross and net rates.
    ytd_active = [s for s in ytd_states if s.prior_balance > 0 and s.gross_pl != 0]
    if ytd_active:
        fg = Decimal("1")
        fn = Decimal("1")
        for s in ytd_active:
            fg *= (Decimal("1") + s.gross_pl / s.prior_balance)
            fn *= (Decimal("1") + daily_net(s.gross_pl) / s.prior_balance)
        n = Decimal(len(ytd_active))
        year_avg_gross_rate = fg ** (Decimal("1") / n) - Decimal("1")
        year_avg_net_rate = fn ** (Decimal("1") / n) - Decimal("1")
    else:
        year_avg_gross_rate = ZERO
        year_avg_net_rate = ZERO

    # NYSE trading-day counts.
    year_start_calendar = date(as_of.year, 1, 1)
    year_end_calendar = date(as_of.year, 12, 31)
    total_year_nyse = len(trading_days_between(year_start_calendar, year_end_calendar))
    nyse_remaining_year = len(trading_days_between(as_of + timedelta(days=1), year_end_calendar))

    # Compound $ projection — keep using forecast_year_end (monthly-fee model).
    forecast = forecast_year_end(
        states, as_of, commission_rate, rate_override=year_avg_gross_rate
    )
    projected_remainder_net = forecast.projected_closing_balance - latest.closing_balance
    if projected_remainder_net > 0:
        projected_remainder_gross = projected_remainder_net / (Decimal("1") - commission_rate)
    else:
        projected_remainder_gross = projected_remainder_net
    year_proj_gross = ytd_gross + projected_remainder_gross
    year_proj_net = ytd_net + projected_remainder_net

    # SIMPLE projected % (bar display): avg_daily × total_trading_days
    year_simple_proj_gross_pct = year_avg_gross_rate * Decimal(total_year_nyse)
    year_simple_proj_net_pct = year_avg_net_rate * Decimal(total_year_nyse)

    year_tile = YearTile(
        year=as_of.year,
        gross_pl=ytd_gross,
        gross_pct=_safe_pct(ytd_gross, balance_at_year_start),
        net_pl=ytd_net,
        net_pct=_safe_pct(ytd_net, balance_at_year_start),
        avg_daily_gross_rate=year_avg_gross_rate,
        avg_daily_net_rate=year_avg_net_rate,
        remaining_trading_days=nyse_remaining_year,
        total_trading_days=total_year_nyse,
        projected_gross_pl=year_proj_gross,
        projected_net_pl=year_proj_net,
        projected_gross_pct=year_simple_proj_gross_pct,
        projected_net_pct=year_simple_proj_net_pct,
        projected_year_end_balance=forecast.projected_closing_balance,
    )

    # ---- monthly bars ----------------------------------------------------
    monthly_bars: list[DailyBarPoint] = []
    for s in mtd_states:
        net = daily_net(s.gross_pl)
        monthly_bars.append(
            DailyBarPoint(
                date=s.date,
                gross_pl=s.gross_pl,
                fee_portion=s.gross_pl - net,
                net_pl=net,
            )
        )

    if mtd_states:
        avg_gross_pl_dollar = sum((s.gross_pl for s in mtd_states), ZERO) / Decimal(len(mtd_states))
        avg_net_pl_dollar = sum((daily_net(s.gross_pl) for s in mtd_states), ZERO) / Decimal(
            len(mtd_states)
        )
    else:
        avg_gross_pl_dollar = ZERO
        avg_net_pl_dollar = ZERO

    # All-time averages over active trading days (matches the platform's
    # "Avg profit per day" stat).
    trading_states = [s for s in states if s.gross_pl != 0]
    if trading_states:
        all_time_avg_gross = sum((s.gross_pl for s in trading_states), ZERO) / Decimal(
            len(trading_states)
        )
        all_time_avg_net = sum((daily_net(s.gross_pl) for s in trading_states), ZERO) / Decimal(
            len(trading_states)
        )
    else:
        all_time_avg_gross = ZERO
        all_time_avg_net = ZERO

    # ---- balance series --------------------------------------------------
    balance_series: list[BalancePoint] = []
    sorted_caps = sorted(cap_changes, key=lambda c: c.date)
    cap_idx = 0
    cap_running = starting
    for s in states:
        while cap_idx < len(sorted_caps) and sorted_caps[cap_idx].date <= s.date:
            cap_running += sorted_caps[cap_idx].signed_amount
            cap_idx += 1
        balance_series.append(
            BalancePoint(
                date=s.date,
                closing_balance=s.closing_balance,
                deployed_capital=cap_running,
            )
        )

    return DashboardSnapshot(
        as_of=as_of,
        current_balance=latest.closing_balance,
        deployed_capital=cap_running,
        yesterday=yesterday_tile,
        month=month_tile,
        year=year_tile,
        monthly_bars=monthly_bars,
        monthly_avg_gross_pl=avg_gross_pl_dollar,
        monthly_avg_net_pl=avg_net_pl_dollar,
        all_time_avg_gross_pl=all_time_avg_gross,
        all_time_avg_net_pl=all_time_avg_net,
        balance_series=balance_series,
    )


@router.get("/history", response_model=list[DayStateOut])
def history(
    user: Annotated[CurrentUser, Depends(require_approved)],
    start: date | None = None,
    end: date | None = None,
) -> list[DayStateOut]:
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
