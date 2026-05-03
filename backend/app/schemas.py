"""Pydantic schemas for API request/response bodies.

Keep these separate from any DB/ORM representation. Money uses Decimal;
dates use date. camelCase conversion happens on the frontend side — API
uses snake_case consistently.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
UserRole = Literal["admin", "viewer"]
UserStatus = Literal["pending", "approved", "rejected"]


class ProfileOut(ORMModel):
    id: UUID
    email: str
    role: UserRole
    status: UserStatus
    starting_balance: Decimal
    join_date: date
    commission_rate: Decimal
    created_at: datetime
    updated_at: datetime


class ProfileUpdateSelf(BaseModel):
    starting_balance: Decimal | None = None
    join_date: date | None = None


class ProfileApprove(BaseModel):
    status: UserStatus
    role: UserRole | None = None


# ---------------------------------------------------------------------------
# Daily returns (admin-authored, shared)
# ---------------------------------------------------------------------------
ReturnEntryMode = Literal["percent", "balance"]


class DailyReturnOut(ORMModel):
    date: date
    gross_pl_pct: Decimal
    entry_mode: ReturnEntryMode
    raw_balance: Decimal | None
    entered_by: UUID


class DailyReturnCreate(BaseModel):
    """One of gross_pl_pct (percent mode) OR raw_balance (balance mode) is
    required. Backend validates."""
    date: date
    entry_mode: ReturnEntryMode
    gross_pl_pct: Decimal | None = None
    raw_balance: Decimal | None = None


# ---------------------------------------------------------------------------
# Capital changes
# ---------------------------------------------------------------------------
CapitalChangeType = Literal["addition", "withdrawal"]


class CapitalChangeOut(ORMModel):
    id: UUID
    user_id: UUID
    date: date
    amount: Decimal
    type: CapitalChangeType
    note: str | None


class CapitalChangeCreate(BaseModel):
    date: date
    amount: Decimal = Field(gt=0)
    type: CapitalChangeType
    note: str | None = None


# ---------------------------------------------------------------------------
# Monthly fees
# ---------------------------------------------------------------------------
class MonthlyFeeOut(ORMModel):
    id: UUID
    user_id: UUID
    year: int
    month: int
    auto_amount: Decimal
    auto_deducted_on: date
    manual_amount: Decimal | None
    manual_deducted_on: date | None
    carryforward_used: Decimal
    carryforward_remaining: Decimal


class MonthlyFeeOverride(BaseModel):
    """Clients send either field null to clear a prior override."""
    manual_amount: Decimal | None = None
    manual_deducted_on: date | None = None


# ---------------------------------------------------------------------------
# Dashboard (computed)
# ---------------------------------------------------------------------------
class DayStateOut(BaseModel):
    date: date
    prior_balance: Decimal
    gross_pl: Decimal
    capital_net: Decimal
    fee_deducted: Decimal
    closing_balance: Decimal


class DashboardSummary(BaseModel):
    as_of: date
    current_balance: Decimal
    deployed_capital: Decimal
    mtd_gross_pl: Decimal
    mtd_accrued_fee: Decimal
    net_balance: Decimal                     # current - accrued
    ytd_gain: Decimal
    avg_daily_gain_rate: Decimal
    projected_year_end_balance: Decimal


# ---------------------------------------------------------------------------
# /dashboard/snapshot — composite payload for the dashboard view
# ---------------------------------------------------------------------------
class DailyTile(BaseModel):
    """Yesterday (or last trading day) summary."""
    label: str                                # "Yesterday" or "Last trading day"
    trading_date: date | None                 # None if no history yet
    gross_pl: Decimal
    gross_pct: Decimal
    net_pl: Decimal                           # daily net = gross * 0.6 on wins, gross on losses
    net_pct: Decimal
    avg_gross_pct_to_date: Decimal | None     # null when fewer than 3 prior days
    avg_net_pct_to_date: Decimal | None


class MonthTile(BaseModel):
    """Month-to-date aggregate using accrued fee with carryforward."""
    year: int
    month: int
    gross_pl: Decimal
    gross_pct: Decimal                        # vs balance at start of month
    net_pl: Decimal                           # gross - accrued fee (with carryforward)
    net_pct: Decimal


class YearTile(BaseModel):
    year: int
    gross_pl: Decimal
    gross_pct: Decimal                        # vs balance at start of year
    net_pl: Decimal
    net_pct: Decimal
    projected_year_end_balance: Decimal
    avg_daily_gain_rate: Decimal


class DailyBarPoint(BaseModel):
    """One bar in the month-of-day chart."""
    date: date
    gross_pl: Decimal
    fee_portion: Decimal                      # gross - net (0 on losing days)
    net_pl: Decimal


class BalancePoint(BaseModel):
    date: date
    closing_balance: Decimal
    deployed_capital: Decimal


class DashboardSnapshot(BaseModel):
    as_of: date
    current_balance: Decimal
    deployed_capital: Decimal
    yesterday: DailyTile
    month: MonthTile
    year: YearTile
    monthly_bars: list[DailyBarPoint]         # current-month days, oldest first
    monthly_avg_gross_pl: Decimal             # for the bar-chart trendline ($ avg)
    monthly_avg_net_pl: Decimal
    all_time_avg_gross_pl: Decimal            # for the daily-tile reference line
    all_time_avg_net_pl: Decimal
    balance_series: list[BalancePoint]        # all-time, oldest first
