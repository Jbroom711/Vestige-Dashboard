"""Nightly job: pull the latest daily-trading data from vhg.app and insert
any new rows into daily_returns. Designed to be invoked by a Railway
scheduled task.

Auth path priority (highest wins):

  1. VHG_EMAIL + VHG_PASSWORD → Playwright (headless Chromium) drives the
     WordPress login form and solves Cloudflare in-browser. Survives the
     Railway-IP Cloudflare block that breaks plain httpx calls. Required
     for fully unattended operation from a hosted environment.
  2. VHG_COOKIE → reuse a manually-extracted browser cookie. Skips login
     but bound to the IP that issued the cookie; usually breaks on hosted
     environments behind Cloudflare. Kept as a low-cost fallback.

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

try:
    from app.scrapers.vhg_playwright import fetch_html_via_browser  # noqa: E402
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False


def main() -> int:
    cookie = os.environ.get("VHG_COOKIE")
    email = os.environ.get("VHG_EMAIL")
    password = os.environ.get("VHG_PASSWORD")
    accnum = os.environ.get("VHG_ACCNUM", "1011389")
    userid = os.environ.get("VHG_USERID", "23")

    sb_early = service_client()

    # --- Auth path selection ---------------------------------------------
    # Path 1 (preferred): plain httpx through a residential/ISP proxy.
    # Verified 2026-05-30 against BrightData ISP — curl-equivalent requests
    # pass Cloudflare cleanly because the IP is trusted; Playwright fails on
    # the same proxy because Chromium's TLS/canvas fingerprint trips CF's
    # bot detection. So when both PROXY_URL and credentials are present, we
    # skip the browser entirely.
    proxy_url = os.environ.get("PROXY_URL")
    if email and password and proxy_url:
        print(f"[vhg-refresh] auth mode = httpx via proxy ({email})")
        try:
            html = fetch_html(email, password, accnum, userid, proxy_url=proxy_url)
        except VHGScrapeError as e:
            print(f"[vhg-refresh] httpx fetch failed: {e}", file=sys.stderr)
            return 2

    # Path 2 (legacy): Playwright + proxy. Heavier; kept in case some future
    # proxy provider needs JavaScript execution (e.g. CF JS challenges).
    elif email and password and _PLAYWRIGHT_AVAILABLE:
        proxy_note = " (via residential proxy)" if proxy_url else ""
        print(f"[vhg-refresh] auth mode = Playwright browser ({email}){proxy_note}")
        try:
            html = fetch_html_via_browser(
                email, password, accnum, userid, proxy_url=proxy_url
            )
        except VHGScrapeError as e:
            print(f"[vhg-refresh] Playwright fetch failed: {e}", file=sys.stderr)
            return 2
    else:
        # Path 2 (fallback): reuse a manually extracted browser cookie.
        # Usually fails from hosted environments because Cloudflare binds
        # cf_clearance to the issuing IP.
        db_row = (
            sb_early.table("scraper_cookies")
            .select("cookie, refreshed_at")
            .eq("name", "vhg")
            .limit(1)
            .execute()
            .data
        )
        db_cookie = db_row[0]["cookie"] if db_row else None
        if db_cookie:
            cookie_source = "db"
            cookie = db_cookie
            print(f"[vhg-refresh] using cookie from DB (refreshed_at={db_row[0]['refreshed_at']})")
        elif cookie:
            cookie_source = "env"
            print(f"[vhg-refresh] using cookie from env (length {len(cookie)} chars)")
        else:
            print(
                "ERROR: set VHG_EMAIL+VHG_PASSWORD (Playwright path) or VHG_COOKIE",
                file=sys.stderr,
            )
            return 1

        try:
            html, refreshed_cookie = fetch_html_with_cookie(cookie, accnum, userid)
        except VHGScrapeError as e:
            print(f"[vhg-refresh] cookie fetch failed: {e}", file=sys.stderr)
            return 2

        if refreshed_cookie:
            sb_early.table("scraper_cookies").upsert(
                {"name": "vhg", "cookie": refreshed_cookie}
            ).execute()
            print("[vhg-refresh] cookie auto-renewed via Set-Cookie (saved to DB)")
        elif cookie_source == "env":
            sb_early.table("scraper_cookies").upsert(
                {"name": "vhg", "cookie": cookie}
            ).execute()
            print("[vhg-refresh] seeded DB with env-var cookie")

    print(f"[vhg-refresh] fetched {len(html):,} bytes of HTML")

    try:
        rows = parse_html(html)
    except VHGScrapeError as e:
        print(f"[vhg-refresh] parse failed: {e}", file=sys.stderr)
        # Diagnostic dump for short/unexpected responses
        snippet = html[:1000] if len(html) <= 1000 else html[:500] + " ... " + html[-500:]
        print(f"[vhg-refresh] response body ({len(html)} bytes): {snippet!r}", file=sys.stderr)
        return 3
    print(f"[vhg-refresh] parsed {len(rows)} daily rows from vhg.app")

    sb = sb_early
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
        if row.gross_profit == 0:
            # vhg.app emits zero-gross rows for non-trading days (holidays
            # like Christmas, Good Friday, days Vestige paused). daily_returns
            # only stores active trading days; the dashboard treats missing
            # dates as "no activity" automatically.
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
