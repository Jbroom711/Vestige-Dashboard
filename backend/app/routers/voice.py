"""/voice — unauthenticated text-only endpoints for Siri Shortcuts.

Access is gated by a shared-secret `token` query parameter (the same approach
used by other personal-use Siri integrations). The shared secret lives in the
`VOICE_TOKEN` env var. Responses are plain text designed to be spoken aloud
by the iOS "Speak Text" Shortcut action.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from app.calc import compute_monthly_fees, project_year_with_plans
from app.config import get_settings
from app.db import service_client
from app.holidays import trading_days_between
from app.state import evolve_user_balance_with_inputs

router = APIRouter(prefix="/voice", tags=["voice"])

ZERO = Decimal("0")
_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _require_token(token: str) -> None:
    expected = get_settings().voice_token
    if not token or token != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def _first_admin_user_id() -> str:
    sb = service_client()
    row = (
        sb.table("profiles")
        .select("id")
        .eq("role", "admin")
        .eq("status", "approved")
        .order("created_at")
        .limit(1)
        .execute()
        .data
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No admin profile")
    return row[0]["id"]


def _load_profile(user_id: str) -> tuple[Decimal, date, Decimal]:
    sb = service_client()
    p = (
        sb.table("profiles")
        .select("starting_balance, join_date, commission_rate")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    return (
        Decimal(str(p["starting_balance"])),
        date.fromisoformat(p["join_date"]),
        Decimal(str(p["commission_rate"])),
    )


def _fmt_dollars_abs(amount: Decimal) -> str:
    return f"${abs(int(round(amount))):,}"


def _fmt_pct_abs(pct: Decimal, digits: int = 2) -> str:
    return f"{abs(pct * 100):.{digits}f}%"


@router.get("/daily", response_class=PlainTextResponse)
def daily(token: str = Query(...)) -> str:
    """Spoken sentence summarizing the most recent trading day plus
    long-term monthly and annual net projections, using the same compute
    paths as the dashboard Monthly tile and Yearly tile so the numbers
    speak consistently with what the dashboard shows."""
    _require_token(token)
    user_id = _first_admin_user_id()
    starting, join_date, commission_rate = _load_profile(user_id)
    states = evolve_user_balance_with_inputs(starting, join_date, user_id)
    if not states:
        return "No trading data available yet."

    latest = states[-1]
    # `as_of` is today (matches dashboard); `latest.date` is the most recent
    # trading day with data, which may be the day before today.
    as_of = date.today()

    # --- Daily values -----------------------------------------------------
    gross = latest.gross_pl
    net = gross * (Decimal("1") - commission_rate) if gross > 0 else gross
    gross_pct = gross / latest.prior_balance if latest.prior_balance > 0 else ZERO
    net_pct = net / latest.prior_balance if latest.prior_balance > 0 else ZERO

    # --- Monthly projection (matches Monthly tile's Full Est. net) -------
    month_first = date(as_of.year, as_of.month, 1)
    mtd_states = [s for s in states if s.date >= month_first]
    mtd_gross = sum((s.gross_pl for s in mtd_states), ZERO)
    mtd_active = [s for s in mtd_states if s.prior_balance > 0 and s.gross_pl != 0]
    if mtd_active:
        f = Decimal("1")
        for s in mtd_active:
            f *= (Decimal("1") + s.gross_pl / s.prior_balance)
        month_avg_gross_rate = f ** (Decimal("1") / Decimal(len(mtd_active))) - Decimal("1")
    else:
        month_avg_gross_rate = ZERO

    if as_of.month == 12:
        month_last_day = date(as_of.year, 12, 31)
    else:
        month_last_day = date(as_of.year, as_of.month + 1, 1) - timedelta(days=1)
    remaining_month_days = len(
        trading_days_between(as_of + timedelta(days=1), month_last_day)
    )
    if month_avg_gross_rate > 0 and remaining_month_days > 0:
        proj_remainder_factor = (Decimal("1") + month_avg_gross_rate) ** Decimal(remaining_month_days)
        proj_remainder_gross = latest.closing_balance * (proj_remainder_factor - Decimal("1"))
    else:
        proj_remainder_gross = ZERO
    month_proj_gross = mtd_gross + proj_remainder_gross
    month_proj_net = (
        month_proj_gross * (Decimal("1") - commission_rate)
        if month_proj_gross > 0
        else month_proj_gross
    )

    # --- Annual projection (matches Yearly tile's Full Est. net) ---------
    year_start = date(as_of.year, 1, 1)
    ytd_states = [s for s in states if s.date >= year_start]
    ytd_gross = sum((s.gross_pl for s in ytd_states), ZERO)
    ytd_active = [s for s in ytd_states if s.prior_balance > 0 and s.gross_pl != 0]
    if ytd_active:
        fg = Decimal("1")
        fn = Decimal("1")
        for s in ytd_active:
            fg *= (Decimal("1") + s.gross_pl / s.prior_balance)
            net_s = (
                s.gross_pl * (Decimal("1") - commission_rate)
                if s.gross_pl > 0
                else s.gross_pl
            )
            fn *= (Decimal("1") + net_s / s.prior_balance)
        n_ytd = Decimal(len(ytd_active))
        year_avg_gross_rate = fg ** (Decimal("1") / n_ytd) - Decimal("1")
        year_avg_net_rate = fn ** (Decimal("1") / n_ytd) - Decimal("1")
    else:
        year_avg_gross_rate = year_avg_net_rate = ZERO

    # YTD net via the same fee model the dashboard uses (carryforward-aware).
    ytd_fee_results = compute_monthly_fees(ytd_states, commission_rate)
    ytd_fees = sum((f.auto_amount for f in ytd_fee_results), ZERO)
    ytd_net = ytd_gross - ytd_fees

    # Active-rate adjustment (same calc as dashboard).
    hist_nyse_total = len(trading_days_between(min(s.date for s in states), as_of))
    active_count_total = sum(1 for s in states if s.gross_pl != 0)
    active_rate_for_proj = (
        Decimal(active_count_total) / Decimal(hist_nyse_total)
        if hist_nyse_total > 0
        else Decimal("1")
    )
    annual_proj = project_year_with_plans(
        current_balance=latest.closing_balance,
        as_of=as_of,
        commission_rate=commission_rate,
        daily_rate=year_avg_gross_rate,
        active_rate=active_rate_for_proj,
        planned_changes=[],
    )
    full_year_net = ytd_net + annual_proj.projected_net_pl
    total_year_nyse = len(trading_days_between(year_start, date(as_of.year, 12, 31)))
    annual_net_pct = year_avg_net_rate * Decimal(total_year_nyse)

    # --- Sentence --------------------------------------------------------
    # The opening "On {date}" refers to the latest trading day with data,
    # which is what the listener actually cares about.
    when = f"{_MONTHS[latest.date.month - 1]} {latest.date.day}"
    monthly_tail = (
        f"Long term, you are on track for a monthly net gain of "
        f"{_fmt_dollars_abs(month_proj_net)}, and an annual net gain of "
        f"{_fmt_dollars_abs(full_year_net)}, or "
        f"{_fmt_pct_abs(annual_net_pct, 1)} Net gain for the year."
    )
    if gross > 0:
        return (
            f"On {when}, your account was up {_fmt_dollars_abs(gross)} gross, "
            f"a {_fmt_pct_abs(gross_pct, 2)} gross gain, and that's "
            f"{_fmt_dollars_abs(net)} net, a {_fmt_pct_abs(net_pct, 2)} Net gain "
            f"for the day. {monthly_tail}"
        )
    if gross < 0:
        return (
            f"On {when}, your account was down {_fmt_dollars_abs(gross)}, "
            f"a {_fmt_pct_abs(gross_pct, 2)} loss for the day. {monthly_tail}"
        )
    return f"On {when}, your account closed flat. {monthly_tail}"
