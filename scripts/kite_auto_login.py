"""Automated daily Kite Connect login using External TOTP + headless browser.

Prerequisite: enable External 2FA TOTP in Kite profile and save the secret.
Set KITE_USER_ID, KITE_PASSWORD, KITE_TOTP_SECRET in .env (chmod 600).

Flow:
1. If today's access_token is already cached, exit 0 (no-op).
2. Otherwise, launch Chromium, submit user_id + password, then TOTP.
3. Intercept the redirect, extract request_token from the URL query string.
4. Exchange for access_token via KiteClient.authenticate() (cached to disk).

Usage:
    python scripts/kite_auto_login.py              # headless (default)
    python scripts/kite_auto_login.py --headed     # visible browser (debugging)

Caveat: automated Kite login violates Zerodha ToS. Use at your own risk.
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import parse_qs, urlparse

import structlog
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from src.data.kite_client import KiteClient  # noqa: E402

logger = structlog.get_logger(__name__)

MAX_RETRIES = 2
NAV_TIMEOUT_MS = 30_000
DEBUG_FAILURE_PAUSE_S = 30  # keep browser open on failure when --headed


def _normalize_totp_secret(raw: str) -> str:
    """Strip whitespace/dashes, uppercase, and pad to multiple of 8.

    Base32 decoding (pyotp) requires the input length to be a multiple of 8;
    some TOTP providers display secrets without the trailing `=` padding.
    """
    cleaned = "".join(raw.split()).replace("-", "").upper().rstrip("=")
    pad = (-len(cleaned)) % 8
    return cleaned + ("=" * pad)


def _get_request_token_via_browser(login_url: str, headless: bool) -> str:
    """Drive Chromium through the Kite login and return the request_token."""
    from playwright.sync_api import sync_playwright  # lazy import

    import pyotp

    user_id = os.environ["KITE_USER_ID"]
    password = os.environ["KITE_PASSWORD"]
    totp_secret = _normalize_totp_secret(os.environ["KITE_TOTP_SECRET"])

    # Validate the secret BEFORE launching the browser — fail fast with a clear error.
    pyotp.TOTP(totp_secret).now()

    import time

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(NAV_TIMEOUT_MS)

        # Capture the redirect URL containing request_token via a route handler.
        # Kite redirects to the app's configured callback URL (often localhost)
        # which may not be reachable; intercept the request and fulfill it with
        # a blank 200 so the URL sticks in the page and no error page appears.
        captured: dict[str, str] = {}

        def _capture_route(route):  # type: ignore[no-untyped-def]
            url = route.request.url
            if "request_token=" in url and "kite.zerodha.com" not in url:
                captured["url"] = url
                route.fulfill(
                    status=200,
                    content_type="text/html",
                    body="<html><body>captured</body></html>",
                )
            else:
                route.continue_()

        context.route("**/*", _capture_route)

        # Fallback capture: some redirects go through the browser's native
        # navigation path and may not surface as routable requests. Watch all
        # requests and responses on the context for a URL containing the token.
        def _on_request(request):  # type: ignore[no-untyped-def]
            if "request_token=" in request.url and "kite.zerodha.com" not in request.url:
                captured.setdefault("url", request.url)

        def _on_response(response):  # type: ignore[no-untyped-def]
            url = response.url
            loc = response.headers.get("location", "")
            if "request_token=" in url and "kite.zerodha.com" not in url:
                captured.setdefault("url", url)
            if "request_token=" in loc:
                captured.setdefault("url", loc)

        context.on("request", _on_request)
        context.on("response", _on_response)

        try:
            page.goto(login_url)

            # Page 1: user_id + password
            page.locator("input[type='text']").first.fill(user_id)
            page.locator("input[type='password']").first.fill(password)
            page.locator("button[type='submit']").first.click()

            # Page 2: TOTP (6-digit). Kite renders a single numeric input.
            page.wait_for_selector("input[type='number'], input[maxlength='6']")
            code = pyotp.TOTP(totp_secret).now()
            totp_input = page.locator(
                "input[type='number'], input[maxlength='6']"
            ).first
            totp_input.fill(code)

            # Kite's TOTP page auto-submits once 6 digits are entered. Wait up
            # to 10s for the redirect; if nothing, click submit as a fallback
            # and wait another 20s.
            def _wait_captured(seconds: float) -> bool:
                import time

                deadline = time.time() + seconds
                while time.time() < deadline:
                    if "url" in captured:
                        return True
                    page.wait_for_timeout(200)
                return "url" in captured

            if not _wait_captured(10):
                submit = page.locator("button[type='submit']").first
                if submit.count():
                    try:
                        submit.click()
                    except Exception:
                        pass
                _wait_captured(20)

            if "url" not in captured:
                raise RuntimeError(
                    "TOTP submitted but no redirect with request_token was captured"
                )
            final_url = captured["url"]
        except Exception:
            # Debug aid: when running --headed, keep the browser on screen briefly
            # so you can see what state it reached (error message, wrong page, etc).
            if not headless:
                logger.warning(
                    "kite_auto_login_debug_pause",
                    seconds=DEBUG_FAILURE_PAUSE_S,
                    url=page.url,
                )
                time.sleep(DEBUG_FAILURE_PAUSE_S)
            raise
        finally:
            context.close()
            browser.close()

    parsed = urlparse(final_url)
    params = parse_qs(parsed.query)
    token = params.get("request_token", [None])[0]
    if not token:
        raise RuntimeError("Login completed but request_token missing from redirect URL")
    return token


def main() -> int:
    parser = argparse.ArgumentParser(description="Automated Kite daily login")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    args = parser.parse_args()

    client = KiteClient()

    # Step 1: already authenticated today? No-op.
    try:
        client.authenticate()
        logger.info("kite_auto_login_skipped", reason="cached_token_valid")
        return 0
    except ValueError:
        pass

    # Step 2: validate secrets present
    missing = [
        name for name in ("KITE_USER_ID", "KITE_PASSWORD", "KITE_TOTP_SECRET")
        if not os.getenv(name)
    ]
    if missing:
        logger.error("kite_auto_login_missing_env", missing=missing)
        return 2

    # Step 3: drive browser, with limited retries
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            request_token = _get_request_token_via_browser(
                client.login_url, headless=not args.headed
            )
            client.authenticate(request_token=request_token)
            logger.info("kite_auto_login_success", attempt=attempt)
            return 0
        except Exception as e:
            last_err = e
            # Redact anything that might leak — log type + short message only.
            logger.warning(
                "kite_auto_login_attempt_failed",
                attempt=attempt,
                error_type=type(e).__name__,
                error=str(e)[:200],
            )

    logger.error(
        "kite_auto_login_failed",
        attempts=MAX_RETRIES,
        error_type=type(last_err).__name__ if last_err else None,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
