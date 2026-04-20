from datetime import date
from decimal import Decimal

from app.calc import (
    CapitalChange,
    DailyReturn,
    compute_monthly_fees,
    deployed_capital,
    derive_pct_from_balance,
    evolve_balance,
    forecast_year_end,
)


D = Decimal


# ---------------------------------------------------------------------------
# derive_pct_from_balance
# ---------------------------------------------------------------------------
def test_derive_pct_simple_gain():
    # Prior 100,000; new 101,000; no capital/fee → +1.0%
    pct = derive_pct_from_balance(D("100000"), D("101000"))
    assert pct == D("0.010000")


def test_derive_pct_backs_out_capital_change():
    # Prior 100k, new 102k, but 1k was a same-day deposit — true gain = 1%
    pct = derive_pct_from_balance(D("100000"), D("102000"), capital_net_today=D("1000"))
    assert pct == D("0.010000")


def test_derive_pct_adds_back_fee():
    # Fee of 500 was deducted today; actual trading produced +1%
    # new = prior + gross - fee → 100500 = 100000 + gross - 500 → gross=1000 → 1.0%
    pct = derive_pct_from_balance(D("100000"), D("100500"), fee_today=D("500"))
    assert pct == D("0.010000")


def test_derive_pct_zero_prior_raises():
    import pytest

    with pytest.raises(ValueError):
        derive_pct_from_balance(D("0"), D("100"))


# ---------------------------------------------------------------------------
# evolve_balance
# ---------------------------------------------------------------------------
def test_evolve_balance_pure_compounding():
    returns = [
        DailyReturn(date(2024, 1, 2), D("0.01")),    # +1%
        DailyReturn(date(2024, 1, 3), D("0.01")),    # +1%
        DailyReturn(date(2024, 1, 4), D("-0.005")),  # -0.5%
    ]
    states = evolve_balance(D("100000"), date(2024, 1, 2), returns, [])
    assert len(states) == 3

    # 100000 * 1.01 = 101000
    assert states[0].closing_balance == D("101000.00")
    # 101000 * 1.01 = 102010
    assert states[1].closing_balance == D("102010.00")
    # 102010 * 0.995 = 101499.95
    assert states[2].closing_balance == D("101499.95")


def test_evolve_balance_ignores_returns_before_start_date():
    returns = [
        DailyReturn(date(2024, 1, 2), D("0.05")),  # ignored
        DailyReturn(date(2024, 1, 3), D("0.01")),
    ]
    states = evolve_balance(D("50000"), date(2024, 1, 3), returns, [])
    assert len(states) == 1
    assert states[0].prior_balance == D("50000.00")
    assert states[0].closing_balance == D("50500.00")


def test_evolve_balance_applies_capital_changes_on_day():
    returns = [DailyReturn(date(2024, 1, 2), D("0.01"))]
    capital = [CapitalChange(date(2024, 1, 2), D("10000"), "addition")]
    # Gross on prior 100k = 1000; plus 10k deposit → closing 111000
    states = evolve_balance(D("100000"), date(2024, 1, 2), returns, capital)
    assert states[0].closing_balance == D("111000.00")


def test_evolve_balance_deducts_fee_on_day():
    returns = [DailyReturn(date(2024, 2, 1), D("0.00"))]  # flat day, fee gets deducted
    fees = {date(2024, 2, 1): D("400")}
    states = evolve_balance(D("100000"), date(2024, 1, 1), returns, [], fees_by_date=fees)
    assert states[0].fee_deducted == D("400.00")
    assert states[0].closing_balance == D("99600.00")


# ---------------------------------------------------------------------------
# compute_monthly_fees
# ---------------------------------------------------------------------------
def _states_from_gains(month_gains: dict[tuple[int, int], Decimal]):
    """Helper: fabricate day_states where each month has a single day with the
    given gross_pl. Sufficient for testing the month aggregator + carryforward."""
    from app.calc import DayState

    out = []
    for (y, m), g in sorted(month_gains.items()):
        out.append(
            DayState(
                date=date(y, m, 15),
                prior_balance=D("100000"),
                gross_pl=g,
                capital_net=D("0"),
                fee_deducted=D("0"),
                closing_balance=D("100000") + g,
            )
        )
    return out


def test_monthly_fee_single_winning_month():
    states = _states_from_gains({(2024, 1): D("5000")})
    results = compute_monthly_fees(states, commission_rate=D("0.40"))
    assert len(results) == 1
    r = results[0]
    assert r.month_gain == D("5000.00")
    assert r.carryforward_used == D("0.00")
    assert r.taxable == D("5000.00")
    assert r.auto_amount == D("2000.00")
    assert r.carryforward_remaining == D("0.00")
    # Fee for Jan 2024 deducted on first trading day of Feb 2024 = Thu Feb 1
    assert r.auto_deducted_on == date(2024, 2, 1)


def test_monthly_fee_losing_month_builds_carryforward():
    states = _states_from_gains({(2024, 1): D("-3000")})
    results = compute_monthly_fees(states, commission_rate=D("0.40"))
    assert results[0].auto_amount == D("0.00")
    assert results[0].carryforward_remaining == D("3000.00")


def test_monthly_fee_carryforward_offsets_next_gain():
    states = _states_from_gains({
        (2024, 1): D("-3000"),  # loss → carry 3000
        (2024, 2): D("5000"),   # 5000 - 3000 offset = 2000 taxable → fee 800
    })
    results = compute_monthly_fees(states, commission_rate=D("0.40"))
    feb = results[1]
    assert feb.carryforward_used == D("3000.00")
    assert feb.taxable == D("2000.00")
    assert feb.auto_amount == D("800.00")
    assert feb.carryforward_remaining == D("0.00")


def test_monthly_fee_partial_carryforward_consumption():
    states = _states_from_gains({
        (2024, 1): D("-5000"),  # carry 5000
        (2024, 2): D("2000"),   # 2000 offset, 3000 still in carry, no fee
    })
    results = compute_monthly_fees(states, commission_rate=D("0.40"))
    feb = results[1]
    assert feb.carryforward_used == D("2000.00")
    assert feb.taxable == D("0.00")
    assert feb.auto_amount == D("0.00")
    assert feb.carryforward_remaining == D("3000.00")


def test_monthly_fee_december_deducts_first_trading_day_of_january():
    states = _states_from_gains({(2024, 12): D("1000")})
    results = compute_monthly_fees(states, commission_rate=D("0.40"))
    # Jan 1, 2025 is Wed (New Year holiday) → first trading day is Thu Jan 2
    assert results[0].auto_deducted_on == date(2025, 1, 2)


# ---------------------------------------------------------------------------
# deployed_capital
# ---------------------------------------------------------------------------
def test_deployed_capital_sums_signed_changes():
    changes = [
        CapitalChange(date(2024, 1, 1), D("10000"), "addition"),
        CapitalChange(date(2024, 2, 1), D("3000"), "withdrawal"),
        CapitalChange(date(2024, 3, 1), D("5000"), "addition"),  # after as_of
    ]
    assert deployed_capital(D("100000"), changes, date(2024, 2, 15)) == D("107000.00")


# ---------------------------------------------------------------------------
# forecast_year_end
# ---------------------------------------------------------------------------
def test_forecast_with_positive_history():
    returns = [
        DailyReturn(date(2024, 1, 2), D("0.01")),
        DailyReturn(date(2024, 1, 3), D("0.01")),
    ]
    states = evolve_balance(D("100000"), date(2024, 1, 2), returns, [])
    result = forecast_year_end(states, as_of=date(2024, 1, 3))
    assert result.avg_daily_gain_rate == D("0.010000")
    assert result.remaining_trading_days > 0
    assert result.projected_closing_balance > states[-1].closing_balance


def test_forecast_with_no_history_returns_zeros():
    result = forecast_year_end([], as_of=date(2024, 6, 15))
    assert result.projected_closing_balance == D("0")
    assert result.remaining_trading_days == 0
