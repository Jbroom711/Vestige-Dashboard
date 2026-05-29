"""Playwright-driven vhg.app scraper. Drives a real headless Chromium so
Cloudflare's bot-check serves us a real `cf_clearance` cookie, then logs
into WordPress and fires the trading_reporting AJAX call from inside the
browser context (so it inherits the cookies the browser just acquired).

Use this when running from a hosted IP that Cloudflare doesn't trust
(Railway, AWS, etc.) — the simpler httpx-based fetch in vhg.py is blocked.

Local prerequisite: `pip install playwright && playwright install chromium`.
Container prerequisite: use the Microsoft Playwright Python base image
(see backend/Dockerfile.cron) which ships Chromium + system libs.
"""

from __future__ import annotations

import logging

from playwright.sync_api import Page, TimeoutError as PWTimeoutError, sync_playwright

from app.scrapers.vhg import VHGScrapeError

log = logging.getLogger(__name__)

_HOMEPAGE = "https://vhg.app/"
_LOGIN_URL = "https://vhg.app/wp-login.php"

# Hides the most common headless-Chrome tells from Cloudflare's bot detection.
# This isn't bulletproof — `playwright-stealth` adds more patches — but
# covers the basics for free.
_STEALTH_INIT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
"""

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def fetch_html_via_browser(
    email: str,
    password: str,
    accnum: str,
    userid: str,
    *,
    headless: bool = True,
    cf_settle_ms: int = 4000,
) -> str:
    """Return the trading_reporting HTML payload, scraped via a real browser.

    Raises VHGScrapeError on login failure or Cloudflare challenge that
    Playwright can't auto-solve.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        context.add_init_script(_STEALTH_INIT)
        page = context.new_page()
        try:
            # 1) Hit the homepage so Cloudflare can serve cf_clearance.
            # wait_until="networkidle" waits for CF's challenge JS to redirect
            # and the real page to finish loading; otherwise page.title()
            # races with navigation and throws "execution context destroyed".
            page.goto(_HOMEPAGE, wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(cf_settle_ms)
            _wait_for_settle(page)
            _ensure_not_blocked(page, where="homepage")

            # 2) Navigate to the WP login form and submit credentials.
            page.goto(_LOGIN_URL, wait_until="networkidle", timeout=60_000)
            _wait_for_settle(page)
            _ensure_not_blocked(page, where="login")
            try:
                page.wait_for_selector("#user_login", timeout=15_000)
            except PWTimeoutError as e:
                raise VHGScrapeError(
                    f"Login form (#user_login) didn't appear within 15s. URL={page.url}"
                ) from e
            page.fill("#user_login", email)
            page.fill("#user_pass", password)
            page.click("#wp-submit")
            page.wait_for_load_state("networkidle", timeout=30_000)

            if "wp-login" in page.url.lower():
                body_snippet = (page.text_content("body") or "")[:300]
                raise VHGScrapeError(
                    f"Login appeared to fail — still on wp-login. Page text: {body_snippet!r}"
                )

            # 3) Fire the AJAX call from inside the browser context so it
            # uses the cookies the browser just acquired (cf_clearance +
            # wordpress_logged_in + wordpress_sec).
            html = page.evaluate(
                """
                async ([accnum, userid]) => {
                    const body = new URLSearchParams({
                        action: 'trading_reporting',
                        period: 'alltime',
                        accnum,
                        userid,
                    });
                    const r = await fetch('/wp-admin/admin-ajax.php', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        credentials: 'include',
                        body: body.toString(),
                    });
                    return await r.text();
                }
                """,
                [accnum, userid],
            )
            if not isinstance(html, str):
                raise VHGScrapeError(f"AJAX response was not a string: {type(html).__name__}")
            if len(html) < 5_000:
                raise VHGScrapeError(
                    f"AJAX response unexpectedly short ({len(html)} bytes). "
                    f"First 200 chars: {html[:200]!r}"
                )
            return html
        finally:
            context.close()
            browser.close()


def _wait_for_settle(page: Page) -> None:
    """Best-effort wait until the page stops navigating. Useful right after
    a Cloudflare challenge because CF chains DOMContentLoaded → JS challenge
    → token submission → final navigation; calling page.title() during any
    of those re-navigations throws 'execution context destroyed'."""
    for _ in range(3):
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
            return
        except PWTimeoutError:
            continue
        except Exception:
            page.wait_for_timeout(1500)


def _safe_title(page: Page) -> str:
    """Retry page.title() across navigation races."""
    for _ in range(3):
        try:
            return page.title() or ""
        except Exception:
            page.wait_for_timeout(1500)
    return ""


def _ensure_not_blocked(page: Page, *, where: str) -> None:
    """Detect Cloudflare's hard-block / challenge pages so we fail loudly
    rather than silently submitting login credentials to an error page."""
    title = _safe_title(page).lower()
    if "just a moment" in title or "checking your browser" in title:
        # Challenge still in progress; give it another beat.
        page.wait_for_timeout(8000)
        _wait_for_settle(page)
        title = _safe_title(page).lower()
        if "just a moment" in title or "checking your browser" in title:
            raise VHGScrapeError(
                f"Cloudflare challenge at {where} didn't auto-resolve. "
                "May need an updated stealth patch."
            )
    if "forbidden" in title or "access denied" in title:
        raise VHGScrapeError(
            f"Cloudflare hard-block at {where} (page title: {title!r}). "
            "Railway IP likely flagged."
        )
