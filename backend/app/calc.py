"""Pure calculation engine for Vestige Dashboard.

No DB, no FastAPI, no I/O. Takes in-memory data, returns in-memory data.
Every function here should have a corresponding test in tests/test_calc.py.

All money values use Decimal. Percentages are stored as Decimal fractions
(e.g. 0.01 for 1%, not 1.0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
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
) -> ForecastResult:
    """Project year-end balance by compounding the historical avg daily gain
    rate across remaining trading days of the current year.

    avg rate is computed from gross_pl / prior_balance per day (so it's
    independent of the size of the book). If there are no observations or
    no remaining trading days, returns zeros.
    """
    if not day_states:
        return ForecastResult(
            avg_daily_gain_rate=Decimal("0"),
            remaining_trading_days=0,
            projected_closing_balance=Decimal("0"),
            projected_gain=Decimal("0"),
        )

    rates: list[Decimal] = []
    for s in day_states:
        if s.prior_balance > 0:
            rates.append(s.gross_pl / s.prior_balance)
    avg = sum(rates, Decimal("0")) / Decimal(len(rates)) if rates else Decimal("0")

    last_entry_date = max(s.date for s in day_states)
    year_end = date(as_of.year, 12, 31)
    remaining_days = len(
        trading_days_between(max(last_entry_date, as_of), year_end)
    )
    # exclude the starting anchor day itself
    if remaining_days > 0:
        remaining_days -= 1

    current_balance = max(day_states, key=lambda s: s.date).closing_balance
    projected = current_balance * (Decimal("1") + avg) ** remaining_days

    return ForecastResult(
        avg_daily_gain_rate=_qpct(avg),
        remaining_trading_days=remaining_days,
        projected_closing_balance=_qmoney(projected),
        projected_gain=_qmoney(projected - current_balance),
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
