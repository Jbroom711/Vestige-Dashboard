"""/voice — unauthenticated text-only endpoints for Siri Shortcuts.

Access is gated by a shared-secret `token` query parameter (the same approach
used by other personal-use Siri integrations). The shared secret lives in the
`VOICE_TOKEN` env var. Responses are plain text designed to be spoken aloud
by the iOS "Speak Text" Shortcut action.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.db import service_client
from app.state import evolve_user_balance_with_inputs

router = APIRouter(prefix="/voice", tags=["voice"])

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _require_token(token: str) -> None:
    expected = get_settings().voice_token
    if not token or token != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def _first_admin_user_id() -> str:
    """Single-user app: voice endpoint speaks for the (only) admin profile."""
    sb = service_client()
    row = (
        sb.table("profiles")
        .select("id, starting_balance, join_date, commission_rate")
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


def _format_dollars_abs(amount: Decimal) -> str:
    """Plain dollar amount, no sign — caller supplies up/down verb."""
    return f"${abs(int(round(amount))):,}"


def _format_percent_abs(pct: Decimal, digits: int = 2) -> str:
    return f"{abs(pct * 100):.{digits}f}%"


@router.get("/daily", response_class=PlainTextResponse)
def daily(token: str = Query(...)) -> str:
    """Spoken sentence summarizing the most recent trading day."""
    _require_token(token)
    user_id = _first_admin_user_id()
    starting, join_date, commission_rate = _load_profile(user_id)
    states = evolve_user_balance_with_inputs(starting, join_date, user_id)
    if not states:
        return "No trading data available yet."

    latest = states[-1]
    gross = latest.gross_pl
    net = gross * (Decimal("1") - commission_rate) if gross > 0 else gross
    pct_gross = gross / latest.prior_balance if latest.prior_balance > 0 else Decimal("0")

    when = f"{_MONTHS[latest.date.month - 1]} {latest.date.day}"
    pct_phrase = _format_percent_abs(pct_gross, 2)

    if gross > 0:
        return (
            f"On {when}, your account was up {_format_dollars_abs(gross)} gross "
            f"and {_format_dollars_abs(net)} net — a {pct_phrase} gain for the day."
        )
    if gross < 0:
        return (
            f"On {when}, your account was down {_format_dollars_abs(gross)} — "
            f"a {pct_phrase} loss for the day."
        )
    return f"On {when}, your account closed flat."
