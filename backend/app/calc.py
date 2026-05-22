"""Pure calculation engine for Vestige Dashboard.

No DB, no FastAPI, no I/O. Takes in-memory data, returns in-memory data.
Every function here should have a corresponding test in tests/test_calc.py.

All money values use Decimal. Percentages are stored as Decimal fractions
(e.g. 0.01 for 1%, not 1.0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.holidays import first_trading_day_of_month, trading_days_between

MONEY_PLACES = Decimal("0.01")
PCT_PLACES = Decimal("0.000001")


def _qmoney(x: Decimal) -> Decimal:
    return x.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def _qpct(x: Decimal) -> Decimal:
    return x.quantize(PCT_PLACES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CapitalChange:
    date: date
    amount: Decimal  # always positive
    type: Literal["addition", "withdrawal"]

    @property
    def signed_amount(self) -> Decimal:
        return self.amount if self.type == "addition" else -self.amount


@dataclass(frozen=True)
class DailyReturn:
    date: date
    gross_pl_pct: Decimal  # fraction, e.g. Decimal("0.0123") for +1.23%


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DayState:
    date: date
    prior_balance: Decimal
    gross_pl: Decimal        # prior_balance * gross_pl_pct
    capital_net: Decimal     # sum of signed capital changes on this date
    fee_deducted: Decimal    # fee deducted today (usually 0)
    closing_balance: Decimal


@dataclass(frozen=True)
class MonthlyFeeResult:
    year: int
    month: int
    month_gain: Decimal             # sum of gross_pl for the month
    carryforward_used: Decimal      # amount of prior loss applied
    taxable: Decimal                # month_gain - carryforward_used (>=0)
    auto_amount: Decimal            # taxable * commission_rate
    auto_deducted_on: date          # first trading day of next month
    carryforward_remaining: Decimal # running balance after this month


@dataclass
class FeeCarryState:
    """Running carryforward state as we walk months in order."""
    carryforward: Decimal = Decimal("0")


# ---------------------------------------------------------------------------
# Derivations
# ---------------------------------------------------------------------------
def derive_pct_from_balance(
    prior_balance: Decimal,
    new_balance: Decimal,
    capital_net_today: Decimal = Decimal("0"),
    fee_today: Decimal = Decimal("0"),
) -> Decimal:
    """Back-solve gross_pl_pct when the admin enters a new total balance.

    Inverts: new_balance = prior_balance + gross_pl - fee + capital_net
    """
    if prior_balance <= 0:
        raise ValueError("prior_balance must be positive to derive a percentage")
    gross_pl = new_balance - prior_balance - capital_net_today + fee_today
    return _qpct(gross_pl / prior_balance)


# ---------------------------------------------------------------------------
# Daily compounding engine
# ---------------------------------------------------------------------------
def evolve_balance(
    starting_balance: Decimal,
    start_date: date,
    daily_returns: list[DailyReturn],
    capital_changes: list[CapitalChange],
    fees_by_date: dict[date, Decimal] | None = None,
) -> list[DayState]:
    """Walk forward through every date with a return, capital change, or fee
    deduction; for each, apply the shared daily % to the prior balance, then
    add the net capital, then subtract any fee. Dates appearing only in
    capital_changes or fees still produce a state (gross_pl will be 0 for
    that day). Events strictly before `start_date` are ignored — this lets
    viewers who join mid-stream start fresh from their own principal on
    `join_date`.
    """
    fees_by_date = fees_by_date or {}

    cap_by_date: dict[date, Decimal] = {}
    for c in capital_changes:
        cap_by_date[c.date] = cap_by_date.get(c.date, Decimal("0")) + c.signed_amount

    returns_by_date: dict[date, Decimal] = {dr.date: dr.gross_pl_pct for dr in daily_returns}

    active_dates = sorted(
        d for d in set(returns_by_date) | set(cap_by_date) | set(fees_by_date)
        if d >= start_date
    )

    states: list[DayState] = []
    balance = starting_balance
    for d in active_dates:
        prior = balance
        gross_pct = returns_by_date.get(d, Decimal("0"))
        gross = prior * gross_pct
        cap = cap_by_date.get(d, Decimal("0"))
        fee = fees_by_date.get(d, Decimal("0"))
        closing = prior + gross + cap - fee
        states.append(
            DayState(
                date=d,
                prior_balance=_qmoney(prior),
                gross_pl=_qmoney(gross),
                capital_net=_qmoney(cap),
                fee_deducted=_qmoney(fee),
                closing_balance=_qmoney(closing),
            )
        )
        balance = closing
    return states


# ---------------------------------------------------------------------------
# Monthly fee with loss carryforward
# ---------------------------------------------------------------------------
def compute_monthly_fees(
    day_states: list[DayState],
    commission_rate: Decimal,
) -> list[MonthlyFeeResult]:
    """Group day_states by (year, month) and compute the auto fee per month.

    Fee for month M is scheduled for the first trading day of month M+1,
    computed from the gross_pl column (already = prior_balance * pct).

    Loss months increase the running carryforward; gain months consume
    carryforward before the commission is applied.
    """
    if commission_rate < 0 or commission_rate > 1:
        raise ValueError("commission_rate must be in [0, 1]")

    # Bucket gross_pl per (year, month) in chronological order
    buckets: dict[tuple[int, int], Decimal] = {}
    for s in day_states:
        k = (s.date.year, s.date.month)
        buckets[k] = buckets.get(k, Decimal("0")) + s.gross_pl

    results: list[MonthlyFeeResult] = []
    state = FeeCarryState()
    for (year, month) in sorted(buckets.keys()):
        month_gain = buckets[(year, month)]
        if month_gain >= 0:
            used = min(state.carryforward, month_gain)
            taxable = month_gain - used
            auto = taxable * commission_rate
            state.carryforward -= used
        else:
            used = Decimal("0")
            taxable = Decimal("0")
            auto = Decimal("0")
            state.carryforward += -month_gain

        next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
        results.append(
            MonthlyFeeResult(
                year=year,
                month=month,
                month_gain=_qmoney(month_gain),
                carryforward_used=_qmoney(used),
                taxable=_qmoney(taxable),
                auto_amount=_qmoney(auto),
                auto_deducted_on=first_trading_day_of_month(next_y, next_m),
                carryforward_remaining=_qmoney(state.carryforward),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ForecastResult:
    avg_daily_gain_rate: Decimal          # mean of daily gain rates observed
    remaining_trading_days: int           # from day-after-last-entry to Dec 31
    projected_closing_balance: Decimal    # compounded forward
    projected_gain: Decimal               # projected - current


def forecast_year_end(
    day_states: list[DayState],
    as_of: date,
    commission_rate: Decimal,
    rate_override: Decimal | None = None,
) -> ForecastResult:
    """Project year-end balance using the monthly-fee model.

    Mechanic mirrors how the broker actually charges: within each month
    the gross gains compound at the daily rate; at month-end,
    `commission_rate` × that month's gross gain is deducted as the fee
    pulled at the start of the next month.

    `rate` is the geometric mean of historical daily gross %s (so it's
    consistent with compounding) unless `rate_override` is supplied for
    "what-if" projections. Active-rate adjustment scales the remaining
    NYSE trading-day count by the user's demonstrated trading frequency,
    so a user who skips 1 day in 30 won't be projected as if they trade
    every NYSE session.
    """
    current_balance = (
        max(day_states, key=lambda s: s.date).closing_balance if day_states else Decimal("0")
    )

    # Pick the daily rate
    if rate_override is not None:
        rate = rate_override
    else:
        gross_rates: list[Decimal] = [
            s.gross_pl / s.prior_balance
            for s in day_states
            if s.prior_balance > 0 and s.gross_pl != 0
        ]
        if not gross_rates:
            return ForecastResult(
                avg_daily_gain_rate=Decimal("0"),
                remaining_trading_days=0,
                projected_closing_balance=current_balance,
                projected_gain=Decimal("0"),
            )
        f = Decimal("1")
        for r in gross_rates:
            f *= (Decimal("1") + r)
        rate = f ** (Decimal("1") / Decimal(len(gross_rates))) - Decimal("1")

    if not day_states:
        return ForecastResult(
            avg_daily_gain_rate=_qpct(rate),
            remaining_trading_days=0,
            projected_closing_balance=current_balance,
            projected_gain=Decimal("0"),
        )

    # Active rate: how often the user actually trades on NYSE sessions
    first_date = min(s.date for s in day_states)
    historical_nyse = len(trading_days_between(first_date, as_of))
    active_count = sum(1 for s in day_states if s.gross_pl != 0)
    if historical_nyse > 0:
        active_rate = Decimal(active_count) / Decimal(historical_nyse)
    else:
        active_rate = Decimal("1")

    # Walk forward by month
    bal = current_balance
    total_active_days = 0
    cur_y, cur_m = as_of.year, as_of.month
    while cur_y == as_of.year:
        if cur_m == 12:
            month_end = date(cur_y, 12, 31)
            next_y, next_m = cur_y + 1, 1
        else:
            month_end = date(cur_y, cur_m + 1, 1) - timedelta(days=1)
            next_y, next_m = cur_y, cur_m + 1
        month_start = max(as_of, date(cur_y, cur_m, 1))

        nyse_days = len(trading_days_between(month_start, month_end))
        active_days = max(0, round(nyse_days * float(active_rate)))

        if active_days > 0:
            month_factor = (Decimal("1") + rate) ** Decimal(active_days)
            if rate >= 0:
                # Gross compounds intra-month; commission deducted at month-end
                net_factor = (Decimal("1") - commission_rate) * month_factor + commission_rate
            else:
                # Losing months don't trigger a fee
                net_factor = month_factor
            bal *= net_factor
            total_active_days += active_days

        cur_y, cur_m = next_y, next_m

    return ForecastResult(
        avg_daily_gain_rate=_qpct(rate),
        remaining_trading_days=total_active_days,
        projected_closing_balance=_qmoney(bal),
        projected_gain=_qmoney(bal - current_balance),
    )


# ---------------------------------------------------------------------------
# Annual projection that incorporates planned future capital changes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AnnualProjectionResult:
    projected_balance: Decimal
    projected_gross_pl: Decimal
    projected_net_pl: Decimal
    projected_fees: Decimal


def project_year_with_plans(
    current_balance: Decimal,
    as_of: date,
    commission_rate: Decimal,
    daily_rate: Decimal,
    active_rate: Decimal,
    planned_changes: list[CapitalChange],
) -> AnnualProjectionResult:
    """Walk month-by-month from as_of+1 to Dec 31 of as_of's year.

    Within each month, capital changes split the month into subperiods. Each
    subperiod compounds at `daily_rate` for its share of active NYSE trading
    days; at the end of each subperiod, the planned change is applied. At
    month-end, 40% of the month's trading gain is deducted as fee (skipped
    on losing months). When planned_changes is empty, this matches the
    Yearly tile's existing forecast_year_end output.
    """
    from app.holidays import trading_days_between

    year_end = date(as_of.year, 12, 31)
    caps_by_date: dict[date, Decimal] = {}
    for c in planned_changes:
        caps_by_date[c.date] = caps_by_date.get(c.date, Decimal("0")) + c.signed_amount

    bal = current_balance
    total_gross = Decimal("0")
    total_fees = Decimal("0")

    cur_y, cur_m = as_of.year, as_of.month
    while cur_y == as_of.year:
        if cur_m == 12:
            month_end = date(cur_y, 12, 31)
            next_y, next_m = cur_y + 1, 1
        else:
            month_end = date(cur_y, cur_m + 1, 1) - timedelta(days=1)
            next_y, next_m = cur_y, cur_m + 1
        month_start = max(as_of + timedelta(days=1), date(cur_y, cur_m, 1))

        bal_start_of_month = bal
        month_changes = sorted(
            (d, amt) for d, amt in caps_by_date.items() if month_start <= d <= month_end
        )

        # Walk subperiods between changes (inclusive of change_date for trading)
        chunk_start = month_start
        for change_date, change_amount in month_changes:
            chunk_nyse = len(trading_days_between(chunk_start, change_date))
            chunk_active = max(0, round(chunk_nyse * float(active_rate)))
            if chunk_active > 0:
                factor = (Decimal("1") + daily_rate) ** Decimal(chunk_active)
                gain = bal * (factor - Decimal("1"))
                bal += gain
                total_gross += gain
            bal += change_amount
            chunk_start = change_date + timedelta(days=1)

        # Final chunk to month-end
        if chunk_start <= month_end:
            chunk_nyse = len(trading_days_between(chunk_start, month_end))
            chunk_active = max(0, round(chunk_nyse * float(active_rate)))
            if chunk_active > 0:
                factor = (Decimal("1") + daily_rate) ** Decimal(chunk_active)
                gain = bal * (factor - Decimal("1"))
                bal += gain
                total_gross += gain

        # End-of-month fee
        change_total = sum((amt for _, amt in month_changes), Decimal("0"))
        month_gross = bal - bal_start_of_month - change_total
        if month_gross > 0:
            fee = month_gross * commission_rate
            bal -= fee
            total_fees += fee

        if next_y > as_of.year:
            break
        cur_y, cur_m = next_y, next_m

    return AnnualProjectionResult(
        projected_balance=_qmoney(bal),
        projected_gross_pl=_qmoney(total_gross),
        projected_net_pl=_qmoney(total_gross - total_fees),
        projected_fees=_qmoney(total_fees),
    )


# ---------------------------------------------------------------------------
# Deployed capital (informational)
# ---------------------------------------------------------------------------
def deployed_capital(
    starting_balance: Decimal,
    capital_changes: list[CapitalChange],
    as_of: date,
) -> Decimal:
    """Net capital invested to date: start + additions - withdrawals."""
    total = starting_balance
    for c in capital_changes:
        if c.date <= as_of:
            total += c.signed_amount
    return _qmoney(total)
