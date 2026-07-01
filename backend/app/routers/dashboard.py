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
    project_year_with_plans,
)
from app.db import service_client
from app.holidays import is_trading_day, prev_trading_day, trading_days_between
from app.schemas import (
    AnnualBarPoint,
    AnnualProjectionTile,
    BalancePoint,
    CapitalChangePoint,
    DailyBarPoint,
    DailyTile,
    DashboardSnapshot,
    DashboardSummary,
    DayStateOut,
    MonthTile,
    PlannedCapitalChangeOut,
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
            annual_projection=AnnualProjectionTile(
                starting_balance=starting,
                current_balance=starting,
                projected_year_end_balance=starting,
                projected_gross_pl=ZERO,
                projected_net_pl=ZERO,
                projected_gross_pct=ZERO,
                projected_net_pct=ZERO,
            ),
            planned_changes=[],
            monthly_bars=[],
            monthly_avg_gross_pl=ZERO,
            monthly_avg_net_pl=ZERO,
            all_time_avg_gross_pl=ZERO,
            all_time_avg_net_pl=ZERO,
            balance_series=[],
        )

    cap_changes = _load_capital_changes(user.id)

    # ---- yesterday tile --------------------------------------------------
    # Pick the most recent state that reflects actual trading (non-zero
    # gross_pl). evolve_balance creates fee-only states on fee-deduction
    # dates (e.g. 2026-07-01 when June's fee is auto-deducted), and those
    # states have gross_pl = 0. Showing them in the Daily tile is misleading
    # — the tile is for "yesterday's trading performance," not for fee
    # bookkeeping days. Fall back to states[-1] only if no state has any
    # trading activity yet (very early in a fresh account's history).
    latest = next(
        (s for s in reversed(states) if s.gross_pl != ZERO),
        states[-1],
    )
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
    # When today's calendar month has no trading activity yet (e.g. it's the
    # 1st of the month and this morning's cron hasn't run), fall back to the
    # last month that DOES have trading — mirrors how the Daily tile shows
    # yesterday's trading rather than today's zero-data day.
    if latest.date.year != as_of.year or latest.date.month != as_of.month:
        month_as_of = latest.date
    else:
        month_as_of = as_of

    month_start = date(month_as_of.year, month_as_of.month, 1)
    states_before_month = [s for s in states if s.date < month_start]
    # Cap at month_as_of so past-month views (?as_of=YYYY-MM-{last_day}) don't
    # accidentally include subsequent months' states in the MTD totals.
    mtd_states = [s for s in states if month_start <= s.date <= month_as_of]
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

    # If viewing a fully-elapsed past month (via ?as_of=...), prefer the
    # effective fee from monthly_fees (manual override or auto stored value)
    # over the running auto-accrual above. That matches what the dashboard's
    # YTD net uses for the same month and keeps MTD-vs-E columns honest.
    today_real = date.today()
    is_past_month = (month_as_of.year, month_as_of.month) < (today_real.year, today_real.month)
    if is_past_month:
        past_fee = (
            service_client()
            .table("monthly_fees")
            .select("auto_amount, manual_amount")
            .eq("user_id", user.id)
            .eq("year", month_as_of.year)
            .eq("month", month_as_of.month)
            .limit(1)
            .execute()
        ).data
        if past_fee:
            r = past_fee[0]
            accrued_fee = (
                Decimal(str(r["manual_amount"]))
                if r["manual_amount"] is not None
                else Decimal(str(r["auto_amount"]))
            )

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
    if month_as_of.month == 12:
        month_last_day = date(month_as_of.year, 12, 31)
    else:
        month_last_day = date(month_as_of.year, month_as_of.month + 1, 1) - timedelta(days=1)
    month_first_day = date(month_as_of.year, month_as_of.month, 1)
    total_month_nyse = len(trading_days_between(month_first_day, month_last_day))
    nyse_remaining_month = len(trading_days_between(month_as_of + timedelta(days=1), month_last_day))

    # Compound $ projection: geo-rate compounded over remaining NYSE days,
    # then 40% fee on the resulting full month gross.
    if month_avg_gross_rate > 0 and nyse_remaining_month > 0:
        proj_remainder_factor = (Decimal("1") + month_avg_gross_rate) ** Decimal(nyse_remaining_month)
        proj_remainder_gross = latest.closing_balance * (proj_remainder_factor - Decimal("1"))
    else:
        proj_remainder_gross = ZERO
    month_proj_gross = mtd_gross + proj_remainder_gross
    if is_past_month:
        # Past month: projection equals actual. MTD and E columns match,
        # and the bar % reflects the realized month return.
        month_proj_net = mtd_net
        month_simple_proj_gross_pct = _safe_pct(mtd_gross, balance_at_month_start)
        month_simple_proj_net_pct = _safe_pct(mtd_net, balance_at_month_start)
    else:
        if month_proj_gross > 0:
            month_proj_net = month_proj_gross * (Decimal("1") - commission_rate)
        else:
            month_proj_net = month_proj_gross
        # SIMPLE projected % (bar display): avg_daily × total_trading_days
        month_simple_proj_gross_pct = month_avg_gross_rate * Decimal(total_month_nyse)
        month_simple_proj_net_pct = month_avg_net_rate * Decimal(total_month_nyse)

    month_tile = MonthTile(
        year=month_as_of.year,
        month=month_as_of.month,
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

    # Active rate: how often the user actually traded NYSE sessions historically.
    # Used for both the Yearly tile and the Annual Projection tile so they
    # agree on the projection methodology when no plans are active.
    hist_nyse_total = len(trading_days_between(min(s.date for s in states), as_of))
    active_count_total = sum(1 for s in states if s.gross_pl != 0)
    active_rate_for_proj = (
        Decimal(active_count_total) / Decimal(hist_nyse_total)
        if hist_nyse_total > 0
        else Decimal("1")
    )

    # SIMPLE projected % (bar display): avg_daily × total_trading_days × active_rate.
    # The active_rate factor brings the displayed % into line with the $
    # projection (which uses project_year_with_plans w/ active_rate).
    year_simple_proj_gross_pct = (
        year_avg_gross_rate * Decimal(total_year_nyse) * active_rate_for_proj
    )
    year_simple_proj_net_pct = (
        year_avg_net_rate * Decimal(total_year_nyse) * active_rate_for_proj
    )

    # Yearly tile $ projection: project_year_with_plans with NO plans. This
    # is the "what the strategy would produce if I made no further capital
    # moves" number. The Annual Projection tile uses the same function with
    # the user's actual planned changes — so when no plans are active, the
    # two tiles show identical $ amounts.
    yearly_proj = project_year_with_plans(
        current_balance=latest.closing_balance,
        as_of=as_of,
        commission_rate=commission_rate,
        daily_rate=year_avg_gross_rate,
        active_rate=active_rate_for_proj,
        planned_changes=[],
    )
    year_proj_gross = ytd_gross + yearly_proj.projected_gross_pl
    year_proj_net = ytd_net + yearly_proj.projected_net_pl

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
        projected_year_end_balance=yearly_proj.projected_balance,
    )

    # ---- annual projection (incorporates planned future capital changes) ----
    planned_rows = (
        service_client()
        .table("planned_capital_changes")
        .select("*")
        .eq("user_id", user.id)
        .order("date")
        .execute()
    ).data or []
    planned_changes = [
        CapitalChange(
            date=date.fromisoformat(r["date"]),
            amount=Decimal(str(r["amount"])),
            type=r["type"],
        )
        for r in planned_rows
    ]

    annual_proj = project_year_with_plans(
        current_balance=latest.closing_balance,
        as_of=as_of,
        commission_rate=commission_rate,
        daily_rate=year_avg_gross_rate,
        active_rate=active_rate_for_proj,
        planned_changes=planned_changes,
    )
    # Full-year totals = YTD (already realized) + projected remainder. The $
    # amounts ARE expected to grow with planned deposits (more capital → more
    # earnings). The %s on the other hand are RATE-based: they represent
    # "what return rate the strategy is producing", which is independent of
    # how much capital is currently working. So we use the same simple
    # avg_daily × total_trading_days figure as the Yearly tile's bar — it
    # doesn't move when the user adds planned capital changes.
    full_year_gross = ytd_gross + annual_proj.projected_gross_pl
    full_year_net = ytd_net + annual_proj.projected_net_pl
    annual_projection_tile = AnnualProjectionTile(
        starting_balance=starting,
        current_balance=latest.closing_balance,
        projected_year_end_balance=annual_proj.projected_balance,
        projected_gross_pl=full_year_gross,
        projected_net_pl=full_year_net,
        projected_gross_pct=year_simple_proj_gross_pct,
        projected_net_pct=year_simple_proj_net_pct,
    )
    planned_changes_out = [PlannedCapitalChangeOut(**r) for r in planned_rows]

    # ---- monthly bars ----------------------------------------------------
    # Build a full skeleton of every trading day in the current month so the
    # chart's x-axis shows all 20-ish ticks. Elapsed days carry real data;
    # non-elapsed days carry zeros (rendered as no-bar but the tick remains).
    # Uses month_as_of (computed above) so on the 1st of a new month the
    # chart shows the just-closed month's full bar set — same fallback as
    # the Month tile.
    state_by_date = {s.date: s for s in mtd_states}
    last_dom = (date(month_as_of.year, month_as_of.month, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    monthly_bars: list[DailyBarPoint] = []
    cur = date(month_as_of.year, month_as_of.month, 1)
    while cur <= last_dom:
        if is_trading_day(cur):
            if cur in state_by_date:
                s = state_by_date[cur]
                net = daily_net(s.gross_pl)
                gross_pct = s.gross_pl / s.prior_balance if s.prior_balance > 0 else ZERO
                net_pct = net / s.prior_balance if s.prior_balance > 0 else ZERO
                monthly_bars.append(
                    DailyBarPoint(
                        date=s.date,
                        gross_pl=s.gross_pl,
                        fee_portion=s.gross_pl - net,
                        net_pl=net,
                        gross_pct=gross_pct,
                        net_pct=net_pct,
                    )
                )
            else:
                monthly_bars.append(
                    DailyBarPoint(
                        date=cur,
                        gross_pl=ZERO,
                        fee_portion=ZERO,
                        net_pl=ZERO,
                        gross_pct=ZERO,
                        net_pct=ZERO,
                    )
                )
        cur += timedelta(days=1)

    if mtd_states:
        avg_gross_pl_dollar = sum((s.gross_pl for s in mtd_states), ZERO) / Decimal(len(mtd_states))
        avg_net_pl_dollar = sum((daily_net(s.gross_pl) for s in mtd_states), ZERO) / Decimal(
            len(mtd_states)
        )
    else:
        avg_gross_pl_dollar = ZERO
        avg_net_pl_dollar = ZERO

    # ---- annual bars (Jan-Dec aggregate by month) ------------------------
    monthly_gross_totals: dict[int, Decimal] = {}
    monthly_net_totals: dict[int, Decimal] = {}
    for s in states:
        if s.date.year != as_of.year:
            continue
        m_key = s.date.month
        monthly_gross_totals[m_key] = monthly_gross_totals.get(m_key, ZERO) + s.gross_pl
        monthly_net_totals[m_key] = monthly_net_totals.get(m_key, ZERO) + daily_net(s.gross_pl)

    # Balance at the start of each month in the current year (for per-month %).
    def balance_at_month_start(month: int) -> Decimal:
        first_of_month = date(as_of.year, month, 1)
        before = [s for s in states if s.date < first_of_month]
        if before:
            return before[-1].closing_balance
        return starting

    annual_bars: list[AnnualBarPoint] = []
    for m in range(1, 13):
        base = balance_at_month_start(m)
        if m == as_of.month and m in monthly_gross_totals:
            gross = month_proj_gross
            net = month_proj_net
            gpct = gross / base if base > 0 else ZERO
            npct = net / base if base > 0 else ZERO
            annual_bars.append(
                AnnualBarPoint(
                    month=m, gross_pl=gross, fee_portion=gross - net, net_pl=net,
                    gross_pct=gpct, net_pct=npct,
                )
            )
        elif m in monthly_gross_totals:
            gross = monthly_gross_totals[m]
            net = monthly_net_totals[m]
            gpct = gross / base if base > 0 else ZERO
            npct = net / base if base > 0 else ZERO
            annual_bars.append(
                AnnualBarPoint(
                    month=m, gross_pl=gross, fee_portion=gross - net, net_pl=net,
                    gross_pct=gpct, net_pct=npct,
                )
            )
        else:
            annual_bars.append(
                AnnualBarPoint(
                    month=m, gross_pl=ZERO, fee_portion=ZERO, net_pl=ZERO,
                    gross_pct=ZERO, net_pct=ZERO,
                )
            )

    # Averages derive from the bars actually drawn (so the projected E for the
    # current month contributes to the dashed reference line too).
    populated = [b for b in annual_bars if b.gross_pl != ZERO or b.net_pl != ZERO]
    if populated:
        n_elapsed = Decimal(len(populated))
        annual_avg_gross_pl = sum((b.gross_pl for b in populated), ZERO) / n_elapsed
        annual_avg_net_pl = sum((b.net_pl for b in populated), ZERO) / n_elapsed
    else:
        annual_avg_gross_pl = ZERO
        annual_avg_net_pl = ZERO

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
        annual_projection=annual_projection_tile,
        planned_changes=planned_changes_out,
        monthly_bars=monthly_bars,
        monthly_avg_gross_pl=avg_gross_pl_dollar,
        monthly_avg_net_pl=avg_net_pl_dollar,
        annual_bars=annual_bars,
        annual_avg_gross_pl=annual_avg_gross_pl,
        annual_avg_net_pl=annual_avg_net_pl,
        all_time_avg_gross_pl=all_time_avg_gross,
        all_time_avg_net_pl=all_time_avg_net,
        balance_series=balance_series,
        capital_changes=[
            CapitalChangePoint(date=c.date, amount=c.amount, type=c.type)
            for c in sorted_caps
        ],
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
