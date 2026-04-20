# Kite Token Health

Diagnose auth failures. Kite tokens expire daily (SEBI mandate).

## Steps

0. **Env** — confirm `.env` has `KITE_USER_ID`, `KITE_PASSWORD`, `KITE_TOTP_SECRET`, `KITE_API_KEY`, `KITE_API_SECRET`. Do not print values. Scripts load these via their own env loader — don't re-export in the shell.
1. **Cache inspection** — read `~/.insight_alpha/kite_token.json`. Report `generated_at`, age, `user_id`.
2. **Live probe** — call a cheap authenticated endpoint (profile); if 403, token is dead.
3. **Auto-login dry-run** — `launchctl start com.insightalpha.kiteauth`; tail `~/.insight_alpha/auto_login.log`.
4. **If it fails:**
   - TOTP secret padded to multiple of 8? (See commit `fac0b30`.)
   - Playwright chromium installed? (`playwright install chromium`)
   - External 2FA TOTP enabled in the Kite profile (not SMS/email)?
   - Request-token capture: route interception + context listeners (commits `8665580`, `621a7c9`); test with `--headed`.
5. **launchd schedule** — `launchctl list | grep insightalpha`; confirm Mon-Fri 08:55 local is active.
6. **ToS reminder** — automated Kite login violates Zerodha ToS. Confirm user still accepts the risk before re-arming.

## Output

Exact failure stage + one-line fix. Don't rewrite `scripts/kite_auto_login.py` unless a specific stage fails.
