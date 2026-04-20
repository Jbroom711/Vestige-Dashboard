"""NYSE trading calendar.

Pure Python, no external market-data dependency. A trading day is a weekday
that is not an NYSE-observed holiday. Early closes are ignored (we only care
whether the market is open at all on a given date).

Sources: NYSE published holiday schedule. Rules encoded here:

- New Year's Day (Jan 1; if Sat → not observed, if Sun → observed Mon)
- Martin Luther King Jr. Day (3rd Monday of January)
- Presidents' Day / Washington's Birthday (3rd Monday of February)
- Good Friday (Friday before Easter Sunday)
- Memorial Day (last Monday of May)
- Juneteenth (Jun 19, observed since 2022; weekend-shift rules apply)
- Independence Day (Jul 4; weekend-shift rules apply)
- Labor Day (1st Monday of September)
- Thanksgiving Day (4th Thursday of November)
- Christmas Day (Dec 25; weekend-shift rules apply)

Weekend-shift rules for fixed-date holidays on the NYSE:
  Saturday → Friday before
  Sunday → Monday after
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache


def _easter_sunday(year: int) -> date:
    """Gregorian Easter Sunday via the Meeus/Jones/Butcher algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """N-th occurrence of `weekday` (Mon=0) in (year, month). 1-indexed."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Last occurrence of `weekday` in (year, month)."""
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last = next_month - timedelta(days=1)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def _observed(d: date) -> date:
    """NYSE weekend-shift: Sat → Fri before, Sun → Mon after."""
    if d.weekday() == 5:  # Saturday
        return d - timedelta(days=1)
    if d.weekday() == 6:  # Sunday
        return d + timedelta(days=1)
    return d


@lru_cache(maxsize=64)
def nyse_holidays(year: int) -> frozenset[date]:
    """All NYSE closure dates for a given year."""
    holidays: set[date] = set()

    holidays.add(_observed(date(year, 1, 1)))                   # New Year's
    holidays.add(_nth_weekday(year, 1, 0, 3))                   # MLK Day
    holidays.add(_nth_weekday(year, 2, 0, 3))                   # Presidents' Day
    holidays.add(_easter_sunday(year) - timedelta(days=2))      # Good Friday
    holidays.add(_last_weekday(year, 5, 0))                     # Memorial Day
    if year >= 2022:
        holidays.add(_observed(date(year, 6, 19)))              # Juneteenth
    holidays.add(_observed(date(year, 7, 4)))                   # Independence Day
    holidays.add(_nth_weekday(year, 9, 0, 1))                   # Labor Day
    holidays.add(_nth_weekday(year, 11, 3, 4))                  # Thanksgiving
    holidays.add(_observed(date(year, 12, 25)))                 # Christmas

    # NYE edge case: if Jan 1 of next year falls on Saturday, it's observed
    # as the Friday before — which is Dec 31 of the current year.
    if date(year + 1, 1, 1).weekday() == 5:
        holidays.add(date(year, 12, 31))

    return frozenset(holidays)


def is_trading_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    return d not in nyse_holidays(d.year)


def next_trading_day(d: date) -> date:
    nxt = d + timedelta(days=1)
    while not is_trading_day(nxt):
        nxt += timedelta(days=1)
    return nxt


def prev_trading_day(d: date) -> date:
    prv = d - timedelta(days=1)
    while not is_trading_day(prv):
        prv -= timedelta(days=1)
    return prv


def trading_days_between(start: date, end: date) -> list[date]:
    """Inclusive list of trading days in [start, end]."""
    if start > end:
        return []
    days: list[date] = []
    cur = start
    while cur <= end:
        if is_trading_day(cur):
            days.append(cur)
        cur += timedelta(days=1)
    return days


def first_trading_day_of_month(year: int, month: int) -> date:
    cur = date(year, month, 1)
    while not is_trading_day(cur):
        cur += timedelta(days=1)
    return cur
