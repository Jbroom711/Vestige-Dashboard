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
