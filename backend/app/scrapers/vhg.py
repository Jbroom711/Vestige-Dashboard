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

    Uses `curl_cffi` (libcurl + Chrome TLS fingerprint impersonation) rather
    than plain httpx, because Cloudflare fingerprints the TLS handshake —
    Python's `ssl` module produces a recognizable JA3 hash that vhg.app's
    CF rejects, even from a trusted residential proxy. libcurl + impersonate
    "chrome131" reproduces Chrome's TLS handshake, so the request is
    indistinguishable from a real browser at the transport layer.

    When `proxy_url` is set (typical in production), traffic is tunneled
    through it. Login flow: warm-up GET → login-page GET → credentials POST
    → trading_reporting AJAX, all on a single cookie-sharing session.

    Raises VHGScrapeError on auth failure or non-2xx response.
    """
    from curl_cffi import requests as cc_requests

    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    # chrome124 is supported across curl_cffi 0.6+; bump as we upgrade.
    with cc_requests.Session(impersonate="chrome124", proxies=proxies) as s:
        # Step 1: warm-up GET to vhg.app/ — Cloudflare issues cf_clearance
        # on a successful first hit; subsequent requests reuse it via the
        # session cookie jar.
        warm = s.get(
            "https://vhg.app/",
            headers={"Sec-Fetch-Site": "none", "Sec-Fetch-Mode": "navigate"},
            timeout=30,
        )
        print(
            f"[vhg-scrape] warm-up GET vhg.app: {warm.status_code}, "
            f"{len(warm.text):,} bytes, cookies: {list(s.cookies.keys())}"
        )
        if warm.status_code >= 400:
            raise VHGScrapeError(
                f"Warm-up GET to vhg.app/ returned {warm.status_code}. "
                f"Body: {warm.text[:300]!r}"
            )

        # Step 2: GET wp-login.php — sets WP-specific cookies and gives us
        # a real Referer for the subsequent POST.
        login_get = s.get(
            LOGIN_URL,
            headers={
                "Referer": "https://vhg.app/",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
            },
            timeout=30,
        )
        print(f"[vhg-scrape] GET wp-login.php: {login_get.status_code}, {len(login_get.text):,} bytes")
        if login_get.status_code >= 400:
            raise VHGScrapeError(
                f"GET wp-login.php returned {login_get.status_code}. "
                f"Body: {login_get.text[:300]!r}"
            )

        # WordPress requires the test cookie to be set before login POST.
        s.cookies.set("wordpress_test_cookie", "WP Cookie check", domain="vhg.app")

        # Step 3: POST credentials with browser-flavored headers.
        r = s.post(
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
            timeout=30,
        )
        if r.status_code >= 400:
            raise VHGScrapeError(f"Login HTTP {r.status_code} — body: {r.text[:300]!r}")
        if not any(name.startswith("wordpress_logged_in") for name in s.cookies.keys()):
            raise VHGScrapeError(
                "Login did not produce a logged_in cookie — wrong credentials, "
                "or vhg.app changed its WP login flow"
            )

        # Step 4: trading_reporting AJAX call.
        r = s.post(
            AJAX_URL,
            data={
                "action": "trading_reporting",
                "period": "alltime",
                "accnum": accnum,
                "userid": userid,
            },
            headers={
                "Referer": "https://vhg.app/",
                "Origin": "https://vhg.app",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=30,
        )
        if r.status_code >= 400:
            raise VHGScrapeError(f"trading_reporting HTTP {r.status_code} — body: {r.text[:300]!r}")
        return r.text


def parse_html(html: str) -> list[VHGRow]:
    """Extract the daily-growth chart series into VHGRow tuples, oldest first.

    Skips entries that don't parse as a date or as a Decimal.
    """
    labels = _find_array(html, r"labels\s*:\s*\[([^\]]+)\]")
    balance = _find_named_array(html, "BALANCE")
    gross = _find_named_array(html, "GROSS PROFIT")

    # vhg.app's Chart.js config sometimes pairs each label with multiple
    # data points (e.g. open/close or stacked datasets). When data arrays
    # are an integer multiple of labels, take a stride that preserves
    # day-to-day alignment. Otherwise truncate to match.
    if len(balance) == 2 * len(labels):
        # Daily charts often emit [point, point, point, point, ...] where
        # adjacent pairs are the same day. Take every other entry, starting
        # from the second (which is typically the closing value).
        balance = balance[1::2]
        print(f"[vhg-parse] balance had 2x labels; took every other (closing values), now {len(balance)}")
    elif len(balance) > len(labels):
        balance = balance[: len(labels)]
        print(f"[vhg-parse] balance longer than labels; truncated to first {len(labels)}")

    if len(gross) == 2 * len(labels):
        gross = gross[1::2]
        print(f"[vhg-parse] gross had 2x labels; took every other (closing values), now {len(gross)}")
    elif len(gross) > len(labels):
        gross = gross[: len(labels)]
        print(f"[vhg-parse] gross longer than labels; truncated to first {len(labels)}")

    if not (len(labels) == len(balance) == len(gross)):
        raise VHGScrapeError(
            f"Array length mismatch after normalization: labels={len(labels)} "
            f"balance={len(balance)} gross={len(gross)}. "
            f"First label: {labels[0] if labels else None!r}, "
            f"first balance: {balance[0] if balance else None!r}, "
            f"first gross: {gross[0] if gross else None!r}"
        )

    rows: list[VHGRow] = []
    skipped_samples: list[str] = []
    for label, bal, g in zip(labels, balance, gross):
        try:
            d = _parse_date(label)
            bal_dec = Decimal(bal.replace(",", "").replace("$", ""))
            g_dec = Decimal(g.replace(",", "").replace("$", ""))
        except (ValueError, ArithmeticError) as e:
            if len(skipped_samples) < 3:
                skipped_samples.append(
                    f"label={label!r}, bal={bal!r}, gross={g!r}, err={e!s}"
                )
            continue
        rows.append(VHGRow(date=d, closing_balance=bal_dec, gross_profit=g_dec))

    # Diagnostic: if we got nothing, surface what we tried to parse so the
    # cron logs make the format mismatch obvious.
    if not rows and labels:
        for sample in skipped_samples:
            print(f"[vhg-parse] skipped: {sample}")
        print(
            f"[vhg-parse] NO ROWS produced. First label={labels[0]!r}, "
            f"first balance={balance[0]!r}, first gross={gross[0]!r}"
        )
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
    raw = m.group(1)
    # One-time diagnostic: when the response shape changes, print the raw
    # array contents so we can see what we're parsing.
    print(f"[vhg-parse] {label_name} raw[:200]={raw[:200]!r}")
    # Numbers may be plain, quoted, or floats; split on commas, trim quotes
    # and whitespace, and drop empty/non-numeric entries.
    out: list[str] = []
    for piece in raw.split(","):
        cleaned = piece.strip().strip("'\"").strip()
        if not cleaned:
            continue
        # Accept things that look like a (possibly signed, possibly decimal) number
        if re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
            out.append(cleaned)
    return out


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
