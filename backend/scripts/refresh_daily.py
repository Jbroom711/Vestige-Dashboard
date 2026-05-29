"""Nightly job: pull the latest daily-trading data from vhg.app and insert
any new rows into daily_returns. Designed to be invoked by a Railway
scheduled task.

Auth env vars (one of these is required):

  VHG_COOKIE    Browser session cookie string (preferred — survives the
                Cloudflare/WAF block that breaks credential-based login).
                Format: "name1=val1; name2=val2; ...".
  VHG_EMAIL +   Credentials fallback. Usually blocked by Cloudflare on
  VHG_PASSWORD  hosted environments; kept for future or alternate access.

Optional:
  VHG_ACCNUM    default '1011389'  (Jonathan's Vestige account number)
  VHG_USERID    default '23'       (Jonathan's WordPress user id)

Idempotent: rows already in daily_returns are skipped. Exits 0 on success
(including no-new-data days), non-zero on auth or scrape failures so the
Railway dashboard surfaces the problem.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal

# Make `app.*` importable when invoked from anywhere.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..")))

from app.db import service_client  # noqa: E402
from app.scrapers.vhg import (  # noqa: E402
    VHGScrapeError,
    fetch_html,
    fetch_html_with_cookie,
    parse_html,
)


def main() -> int:
    cookie = os.environ.get("VHG_COOKIE")
    email = os.environ.get("VHG_EMAIL")
    password = os.environ.get("VHG_PASSWORD")
    accnum = os.environ.get("VHG_ACCNUM", "1011389")
    userid = os.environ.get("VHG_USERID", "23")

    if cookie:
        print(f"[vhg-refresh] auth mode = cookie (length {len(cookie)} chars)")
        try:
            html = fetch_html_with_cookie(cookie, accnum, userid)
        except VHGScrapeError as e:
            print(f"[vhg-refresh] cookie fetch failed: {e}", file=sys.stderr)
            return 2
    elif email and password:
        print(f"[vhg-refresh] auth mode = credentials ({email})")
        try:
            html = fetch_html(email, password, accnum, userid)
        except VHGScrapeError as e:
            print(f"[vhg-refresh] login/fetch failed: {e}", file=sys.stderr)
            return 2
    else:
        print(
            "ERROR: set VHG_COOKIE (preferred) or VHG_EMAIL + VHG_PASSWORD",
            file=sys.stderr,
        )
        return 1

    print(f"[vhg-refresh] fetched {len(html):,} bytes of HTML")

    try:
        rows = parse_html(html)
    except VHGScrapeError as e:
        print(f"[vhg-refresh] parse failed: {e}", file=sys.stderr)
        return 3
    print(f"[vhg-refresh] parsed {len(rows)} daily rows from vhg.app")

    sb = service_client()
    admin = (
        sb.table("profiles")
        .select("id, email")
        .eq("role", "admin")
        .eq("status", "approved")
        .order("created_at")
        .limit(1)
        .execute()
        .data
    )
    if not admin:
        print("[vhg-refresh] ERROR: no approved admin profile found", file=sys.stderr)
        return 4
    admin_id = admin[0]["id"]

    existing = sb.table("daily_returns").select("date").execute().data
    existing_dates = {row["date"] for row in existing}

    inserted = 0
    skipped = 0
    for i, row in enumerate(rows):
        date_str = row.date.isoformat()
        if date_str in existing_dates:
            skipped += 1
            continue
        if row.gross_profit == 0 and row.closing_balance == 0:
            # vhg.app sometimes emits zero filler rows; ignore them.
            skipped += 1
            continue
        if i == 0:
            print(
                f"[vhg-refresh] skipping first row {date_str}: no prior balance available",
                file=sys.stderr,
            )
            skipped += 1
            continue

        prior_close = rows[i - 1].closing_balance
        if prior_close <= 0:
            print(f"[vhg-refresh] skipping {date_str}: non-positive prior balance", file=sys.stderr)
            skipped += 1
            continue

        # gross_pl_pct = trading-only gross $ / prior closing balance.
        # vhg.app's GROSS PROFIT field already excludes capital flows.
        gross_pct = (row.gross_profit / prior_close).quantize(Decimal("0.00000001"))

        sb.table("daily_returns").insert(
            {
                "date": date_str,
                "gross_pl_pct": str(gross_pct),
                "entry_mode": "balance",
                "raw_balance": str(row.closing_balance),
                "entered_by": admin_id,
            }
        ).execute()
        inserted += 1
        print(
            f"[vhg-refresh] inserted {date_str}: "
            f"balance=${row.closing_balance:,.2f}, gross=${row.gross_profit:,.2f}, "
            f"pct={gross_pct * 100:.4f}%"
        )

    print(f"[vhg-refresh] done. inserted={inserted}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
