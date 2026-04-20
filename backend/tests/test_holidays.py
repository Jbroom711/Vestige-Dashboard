from datetime import date

from app.holidays import (
    first_trading_day_of_month,
    is_trading_day,
    next_trading_day,
    nyse_holidays,
    prev_trading_day,
    trading_days_between,
)


def test_weekend_is_not_trading_day():
    assert not is_trading_day(date(2024, 1, 6))   # Saturday
    assert not is_trading_day(date(2024, 1, 7))   # Sunday


def test_regular_weekday_is_trading_day():
    assert is_trading_day(date(2024, 1, 9))       # Tuesday


def test_fixed_holidays_observed():
    # 2024 MLK = Mon Jan 15
    assert not is_trading_day(date(2024, 1, 15))
    # 2024 Presidents' Day = Mon Feb 19
    assert not is_trading_day(date(2024, 2, 19))
    # 2024 Memorial Day = Mon May 27
    assert not is_trading_day(date(2024, 5, 27))
    # 2024 Labor Day = Mon Sep 2
    assert not is_trading_day(date(2024, 9, 2))
    # 2024 Thanksgiving = Thu Nov 28
    assert not is_trading_day(date(2024, 11, 28))


def test_good_friday_2024():
    # Easter 2024 = Mar 31; Good Friday = Mar 29
    assert not is_trading_day(date(2024, 3, 29))


def test_independence_day_weekend_shift():
    # Jul 4, 2026 is Saturday → observed Fri Jul 3
    assert not is_trading_day(date(2026, 7, 3))
    assert date(2026, 7, 4) not in nyse_holidays(2026)  # weekend itself not listed


def test_new_year_weekend_shift_forward():
    # Jan 1, 2023 was Sunday → observed Mon Jan 2
    assert not is_trading_day(date(2023, 1, 2))


def test_christmas_weekend_shift_backward():
    # Dec 25, 2027 is Saturday → observed Fri Dec 24
    assert not is_trading_day(date(2027, 12, 24))


def test_juneteenth_only_from_2022():
    assert date(2021, 6, 18) not in nyse_holidays(2021)  # not a market holiday yet
    # 2022 Jun 19 was Sunday → observed Mon Jun 20
    assert not is_trading_day(date(2022, 6, 20))


def test_next_and_prev_trading_day_skip_holidays():
    # Fri Jul 3, 2026 is observed Independence Day, Sat/Sun follow
    nxt = next_trading_day(date(2026, 7, 2))
    assert nxt == date(2026, 7, 6)
    prv = prev_trading_day(date(2026, 7, 6))
    assert prv == date(2026, 7, 2)


def test_trading_days_between_counts_correctly():
    # First week of Jan 2024: Mon 1 is New Year (holiday), Tue–Fri are trading
    days = trading_days_between(date(2024, 1, 1), date(2024, 1, 5))
    assert days == [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)]


def test_first_trading_day_of_month_jan_2024():
    # Mon Jan 1 is New Year; Tue Jan 2 is first trading day
    assert first_trading_day_of_month(2024, 1) == date(2024, 1, 2)
