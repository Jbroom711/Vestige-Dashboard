"""vhg.app trading-data scraper.

Logs into the broker's WordPress site, hits the same `admin-ajax.php?action=
trading_reporting` endpoint the manual DevTools console scrape uses, and
parses the embedded Chart.js datasets into typed rows.

Returns one row per labeled date: (date, closing_balance, gross_profit).
GROSS PROFIT is the trading-only $ change (excludes capital flows); BALANCE
is the day's closing balance (includes capital flows).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import httpx

LOGIN_URL = "https://vhg.app/wp-login.php"
AJAX_URL = "https://vhg.app/wp-admin/admin-ajax.php"

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


class VHGScrapeError(Exception):
    pass


@dataclass(frozen=True)
class VHGRow:
    date: date
    closing_balance: Decimal
    gross_profit: Decimal


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://vhg.app/",
}


def fetch_html_with_cookie(
    cookie: str, accnum: str, userid: str
) -> tuple[str, str | None]:
    """Fetch trading_reporting using a stored session cookie.

    The cookie string is exactly what you'd paste into a browser's Cookie
    header — `name1=val1; name2=val2; ...`. This skips the WordPress login
    flow entirely, so it works even when Cloudflare blocks programmatic
    logins.

    Returns `(html, refreshed_cookie)`. The second tuple element is non-null
    when the server sent back a refreshed `wordpress_logged_in_*` cookie via
    Set-Cookie — WordPress's "sliding session" pattern. Callers should
    persist the refreshed cookie so the next run uses the extended one.

    Raises VHGScrapeError("cookie expired ...") with a clear, actionable
    message when the server tells us we're not logged in.
    """
    headers = {**_BROWSER_HEADERS, "Cookie": cookie}
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            AJAX_URL,
            data={
                "action": "trading_reporting",
                "period": "alltime",
                "accnum": accnum,
                "userid": userid,
            },
            headers=headers,
        )
        refreshed = _build_refreshed_cookie(cookie, client.cookies)
    if r.status_code == 403:
        raise VHGScrapeError(
            "HTTP 403 from vhg.app — cookie expired or Cloudflare block. "
            "Refresh VHG_COOKIE in Railway."
        )
    if r.status_code >= 400:
        raise VHGScrapeError(f"trading_reporting HTTP {r.status_code}")

    text = r.text
    # WP-AJAX returns "0" for unauthenticated callers on actions that require
    # login, or the full login HTML if the URL got redirected.
    stripped = text.strip()
    if stripped == "0" or stripped == "-1":
        raise VHGScrapeError(
            "vhg.app returned the not-logged-in sentinel. Cookie expired. "
            "Refresh VHG_COOKIE in Railway."
        )
    low = text.lower()
    if "wp-login.php" in low and "user_login" in low and len(text) < 50_000:
        raise VHGScrapeError(
            "Got the WP login page instead of chart data. Cookie expired. "
            "Refresh VHG_COOKIE in Railway."
        )
    return text, refreshed


def _build_refreshed_cookie(original: str, client_cookies: httpx.Cookies) -> str | None:
    """Merge any refreshed WordPress cookies from the response back into the
    original cookie string. WordPress's sliding-session pattern sends a
    `Set-Cookie: wordpress_logged_in_<hash>=...` with an extended expiration
    on authenticated requests when the session is past its halfway mark.

    Returns the rebuilt cookie string if anything changed, else None.
    """
    refreshed_names = {
        name
        for name in client_cookies.keys()
        if name.startswith("wordpress_logged_in_") or name.startswith("wordpress_sec_")
    }
    if not refreshed_names:
        return None

    # Parse the original cookie into (name, value) pairs preserving order.
    pairs: list[tuple[str, str]] = []
    for chunk in original.split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        pairs.append((name.strip(), value.strip()))

    changed = False
    for i, (name, value) in enumerate(pairs):
        if name in refreshed_names:
            new_value = client_cookies.get(name)
            if new_value and new_value != value:
                pairs[i] = (name, new_value)
                changed = True

    return "; ".join(f"{n}={v}" for n, v in pairs) if changed else None


def fetch_html(
    email: str,
    password: str,
    accnum: str,
    userid: str,
    *,
    proxy_url: str | None = None,
) -> str:
    """Log in to vhg.app with credentials and return the trading_reporting
    HTML payload.

    When `proxy_url` is set (typical in production), the entire flow is
    routed through that proxy. With a clean residential/ISP proxy that
    Cloudflare trusts (e.g. BrightData ISP), plain httpx works fine —
    we don't need Playwright's heavy browser fingerprint. Cloudflare's
    bot detection trips on Chromium's TLS/canvas tells; raw httpx with a
    real-browser User-Agent through a trusted exit IP slips past.

    Raises VHGScrapeError on auth failure or non-2xx response.
    """
    base_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
    client_kwargs: dict[str, object] = {
        "follow_redirects": True,
        "timeout": 30.0,
        "headers": base_headers,
    }
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    with httpx.Client(**client_kwargs) as client:  # type: ignore[arg-type]
        # Step 1: warm-up GET to vhg.app/ — picks up cf_clearance and any
        # other Cloudflare-issued cookies, so subsequent requests look like
        # they come from a session that already cleared the bot check.
        warm = client.get("https://vhg.app/", headers={"Sec-Fetch-Site": "none", "Sec-Fetch-Mode": "navigate"})
        print(
            f"[vhg-scrape] warm-up GET vhg.app: {warm.status_code}, "
            f"{len(warm.text):,} bytes, cookies after: {list(client.cookies.keys())}"
        )
        if warm.status_code >= 400:
            raise VHGScrapeError(
                f"Warm-up GET to vhg.app/ returned {warm.status_code}. "
                f"Body: {warm.text[:300]!r}"
            )

        # Step 2: GET the login page itself — sets WP-specific cookies and
        # gives us a real Referer for the subsequent POST.
        login_get = client.get(
            LOGIN_URL,
            headers={
                "Referer": "https://vhg.app/",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
            },
        )
        print(
            f"[vhg-scrape] GET wp-login.php: {login_get.status_code}, "
            f"{len(login_get.text):,} bytes"
        )
        if login_get.status_code >= 400:
            raise VHGScrapeError(
                f"GET wp-login.php returned {login_get.status_code}. "
                f"Body: {login_get.text[:300]!r}"
            )

        # WordPress requires the test cookie to be set before login POST.
        client.cookies.set("wordpress_test_cookie", "WP Cookie check", domain="vhg.app")

        # Step 3: POST credentials, now with full browser-flavored headers.
        r = client.post(
            LOGIN_URL,
            data={
                "log": email,
                "pwd": password,
                "wp-submit": "Log In",
                "testcookie": "1",
                "redirect_to": "https://vhg.app/",
            },
            headers={
                "Referer": LOGIN_URL,
                "Origin": "https://vhg.app",
                "Content-Type": "application/x-www-form-urlencoded",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
            },
        )
        if r.status_code >= 400:
            raise VHGScrapeError(f"Login HTTP {r.status_code} — body: {r.text[:300]!r}")
        if not any(name.startswith("wordpress_logged_in") for name in client.cookies.keys()):
            raise VHGScrapeError(
                "Login did not produce a logged_in cookie — wrong credentials, "
                "or vhg.app changed its WP login flow"
            )

        r = client.post(
            AJAX_URL,
            data={
                "action": "trading_reporting",
                "period": "alltime",
                "accnum": accnum,
                "userid": userid,
            },
        )
        if r.status_code >= 400:
            raise VHGScrapeError(f"trading_reporting HTTP {r.status_code}")
        return r.text


def parse_html(html: str) -> list[VHGRow]:
    """Extract the daily-growth chart series into VHGRow tuples, oldest first.

    Skips entries that don't parse as a date or as a Decimal.
    """
    labels = _find_array(html, r"labels\s*:\s*\[([^\]]+)\]")
    balance = _find_named_array(html, "BALANCE")
    gross = _find_named_array(html, "GROSS PROFIT")

    if not (len(labels) == len(balance) == len(gross)):
        raise VHGScrapeError(
            f"Array length mismatch: labels={len(labels)} "
            f"balance={len(balance)} gross={len(gross)}"
        )

    rows: list[VHGRow] = []
    for label, bal, g in zip(labels, balance, gross):
        try:
            d = _parse_date(label)
            bal_dec = Decimal(bal.replace(",", "").replace("$", ""))
            g_dec = Decimal(g.replace(",", "").replace("$", ""))
        except (ValueError, ArithmeticError):
            continue
        rows.append(VHGRow(date=d, closing_balance=bal_dec, gross_profit=g_dec))
    return rows


def _find_array(html: str, pattern: str) -> list[str]:
    m = re.search(pattern, html)
    if not m:
        raise VHGScrapeError(f"Pattern not found: {pattern}")
    return re.findall(r"'([^']*)'", m.group(1))


def _find_named_array(html: str, label_name: str) -> list[str]:
    """Find the `data: [...]` array for the Chart dataset whose label matches."""
    pat = (
        r"label\s*:\s*['\"]"
        + re.escape(label_name)
        + r"['\"][\s\S]*?data\s*:\s*\[([^\]]+)\]"
    )
    m = re.search(pat, html)
    if not m:
        raise VHGScrapeError(f"Dataset '{label_name}' not found in response")
    # Values may be single-quoted strings or bare numbers; capture either.
    return re.findall(r"['\"]?([\-\d.,]+)['\"]?", m.group(1))


def _parse_date(s: str) -> date:
    """Parse '15 DEC 2025' format."""
    parts = s.strip().split()
    if len(parts) != 3:
        raise ValueError(f"Bad date: {s}")
    day = int(parts[0])
    month = _MONTHS.get(parts[1].upper())
    if month is None:
        raise ValueError(f"Unknown month: {parts[1]}")
    year = int(parts[2])
    return date(year, month, day)
