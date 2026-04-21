# Kite Token Health

Diagnose Kite session failures. Kite tokens expire daily at 15:30 IST (SEBI mandate).
Login is **manual on mobile** — no TOTP scripting. Token lives in Neon
`app_state` (keys: `kite_access_token`, `kite_session_expires_at`).

## Steps

0. **Env** — confirm the trigger env has `KITE_API_KEY`, `KITE_API_SECRET`,
   `DATABASE_URL_PAPER` / `DATABASE_URL_LIVE`. Do not print values.
1. **Session inspection** — read `app_state` rows for `kite_access_token` +
   `kite_session_expires_at`. Report expiry age.
2. **Live probe** — call Kite `profile` endpoint with the stored token; if
   `TokenException`, the session is dead.
3. **If dead:** fire the `morning-login-prompt` routine manually to re-post
   the login link to Telegram. User taps → phone login → Cloudflare Worker
   writes the new token. Re-probe to confirm.
4. **Cloudflare Worker health** — `curl https://insight-alpha.<sub>.workers.dev/kite/callback`
   should 400 (missing request_token), not 500. If 500, check Worker logs via
   `wrangler tail`.

## Output

Exact failure stage + one-line fix.

## Historical note

The old `scripts/kite_auto_login.py` automated login via Playwright + TOTP
— retained only as a manual debug tool. It violates Zerodha ToS; prefer
the mobile-login flow.
