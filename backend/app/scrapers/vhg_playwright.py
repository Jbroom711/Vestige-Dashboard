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
    proxy_url: str | None = None,
) -> str:
    """Return the trading_reporting HTML payload, scraped via a real browser.

    `proxy_url`, when provided, routes all browser traffic through a residential
    proxy so Cloudflare sees a real-ISP IP instead of the Railway/cloud range.
    Accepts the standard `http://user:pass@host:port` form.

    Raises VHGScrapeError on login failure or Cloudflare challenge that
    Playwright can't auto-solve.
    """
    proxy_config = _parse_proxy(proxy_url)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
            proxy=proxy_config,
        )
        context = browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        context.add_init_script(_STEALTH_INIT)
        page = context.new_page()
        try:
            # 0) Sanity check — print the apparent exit IP so we can confirm
            # the proxy is actually routing traffic (vs. silently bypassed).
            try:
                page.goto("https://api.ipify.org?format=text", timeout=20_000)
                _wait_for_settle(page)
                ip_text = (page.text_content("body") or "").strip()[:60]
                print(f"[vhg-playwright] outbound IP via browser: {ip_text!r}")
            except Exception as e:
                print(f"[vhg-playwright] IP check failed (continuing): {e!r}")

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


def _parse_proxy(url: str | None) -> dict[str, str] | None:
    """Translate `http://user:pass@host:port` into Playwright's proxy dict."""
    if not url:
        return None
    from urllib.parse import urlparse

    p = urlparse(url)
    if not p.hostname:
        return None
    server = f"{p.scheme or 'http'}://{p.hostname}"
    if p.port:
        server = f"{server}:{p.port}"
    cfg: dict[str, str] = {"server": server}
    if p.username:
        cfg["username"] = p.username
    if p.password:
        cfg["password"] = p.password
    return cfg


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
