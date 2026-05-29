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


# Planned capital changes (future events for projection)
class PlannedCapitalChangeOut(ORMModel):
    id: UUID
    user_id: UUID
    date: date
    amount: Decimal
    type: CapitalChangeType
    note: str | None


class PlannedCapitalChangeCreate(BaseModel):
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
    label: str                                # "Today", "Yesterday", or "Last day"
    trading_date: date | None                 # None if no history yet
    gross_pl: Decimal
    gross_pct: Decimal
    net_pl: Decimal                           # daily net = gross * 0.6 on wins, gross on losses
    net_pct: Decimal
    avg_gross_pct_to_date: Decimal | None     # null when fewer than 3 prior days
    avg_net_pct_to_date: Decimal | None


class MonthTile(BaseModel):
    """Month-to-date aggregate plus full-month projection.

    Two projection styles are exposed:
      - projected_*_pct are SIMPLE (avg_daily_rate × total_trading_days),
        which is the user's "if every day looked like the average" view.
      - projected_*_pl ($) use the COMPOUND monthly-fee model (gross
        compounds intra-month, 40% pulled at month-end).
    """
    year: int
    month: int
    # Realized (MTD)
    gross_pl: Decimal
    gross_pct: Decimal                        # vs balance at start of month
    net_pl: Decimal
    net_pct: Decimal
    # Projection
    avg_daily_gross_rate: Decimal             # geo mean of MTD daily gross %s
    avg_daily_net_rate: Decimal               # geo mean of MTD daily net %s
    remaining_trading_days: int               # NYSE days from today to month-end
    total_trading_days: int                   # NYSE days in this month (full)
    projected_gross_pl: Decimal               # full-month gross $ (compound)
    projected_net_pl: Decimal                 # full-month net $ (compound, after fee)
    projected_gross_pct: Decimal              # SIMPLE: avg_daily_gross × total_days
    projected_net_pct: Decimal                # SIMPLE: avg_daily_net × total_days


class YearTile(BaseModel):
    """Year-to-date aggregate plus full-year projection (monthly-fee model).

    Same two-style projection as MonthTile: pct is SIMPLE
    (avg_daily × total_days_in_year); $ is COMPOUND with monthly fees.
    """
    year: int
    # Realized (YTD)
    gross_pl: Decimal
    gross_pct: Decimal                        # vs balance at start of year
    net_pl: Decimal
    net_pct: Decimal
    # Projection
    avg_daily_gross_rate: Decimal             # geo mean of YTD daily gross %s
    avg_daily_net_rate: Decimal               # geo mean of YTD daily net %s
    remaining_trading_days: int               # NYSE days from today to Dec 31
    total_trading_days: int                   # NYSE days in this year
    projected_gross_pl: Decimal               # full-year gross $ (compound)
    projected_net_pl: Decimal                 # full-year net $ (compound, after fees)
    projected_gross_pct: Decimal              # SIMPLE: avg_daily_gross × total_days
    projected_net_pct: Decimal                # SIMPLE: avg_daily_net × total_days
    projected_year_end_balance: Decimal       # kept for reference


class DailyBarPoint(BaseModel):
    """One bar in the month-of-day chart. For trading days that haven't
    elapsed yet, all fields are 0 (rendered as no-bar but the x-axis
    tick is still drawn)."""
    date: date
    gross_pl: Decimal
    fee_portion: Decimal                      # gross - net (0 on losing days)
    net_pl: Decimal
    gross_pct: Decimal                        # gross_pl / prior_balance
    net_pct: Decimal                          # net_pl / prior_balance


class AnnualBarPoint(BaseModel):
    """One bar in the year-by-month chart. For months that haven't started
    yet, all fields are 0."""
    month: int                                # 1-12
    gross_pl: Decimal
    fee_portion: Decimal
    net_pl: Decimal
    gross_pct: Decimal                        # month_gross / balance_at_month_start
    net_pct: Decimal                          # month_net / balance_at_month_start


class BalancePoint(BaseModel):
    date: date
    closing_balance: Decimal
    deployed_capital: Decimal


class CapitalChangePoint(BaseModel):
    """Capital deposit or withdrawal annotation for the Overview chart."""
    date: date
    amount: Decimal
    type: Literal["addition", "withdrawal"]


class AnnualProjectionTile(BaseModel):
    """Year-end projection that incorporates the user's planned future
    deposits/withdrawals. When the user has no plans, this equals the
    Yearly tile's Full Est. Same monthly-fee compounding model, but the
    walk applies each planned capital change on its date so subsequent
    days compound on the adjusted balance."""
    starting_balance: Decimal                 # user's profile starting_balance
    current_balance: Decimal                  # latest closing balance
    projected_year_end_balance: Decimal
    projected_gross_pl: Decimal               # full-year gross $ (incl. plans' compounding contribution)
    projected_net_pl: Decimal                 # full-year net $ (after monthly fees)
    projected_gross_pct: Decimal              # gross / current_balance (so "% from today")
    projected_net_pct: Decimal


class DashboardSnapshot(BaseModel):
    as_of: date
    current_balance: Decimal
    deployed_capital: Decimal
    yesterday: DailyTile
    month: MonthTile
    year: YearTile
    annual_projection: AnnualProjectionTile
    planned_changes: list[PlannedCapitalChangeOut]  # so the Annual tile can render the form
    monthly_bars: list[DailyBarPoint]         # current-month days, padded with zeros for non-elapsed trading days
    monthly_avg_gross_pl: Decimal             # for the bar-chart trendline ($ avg) — elapsed days only
    monthly_avg_net_pl: Decimal
    annual_bars: list[AnnualBarPoint]         # 12 entries (Jan-Dec); zeros for non-elapsed months
    annual_avg_gross_pl: Decimal              # avg monthly gross across elapsed months
    annual_avg_net_pl: Decimal
    all_time_avg_gross_pl: Decimal            # for the daily-tile reference line
    all_time_avg_net_pl: Decimal
    balance_series: list[BalancePoint]        # all-time, oldest first
    capital_changes: list[CapitalChangePoint] # historical deposits/withdrawals, oldest first
