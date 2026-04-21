# Cloudflare Worker — Kite Login Callback

Receives Zerodha's redirect after the user logs in on their phone, exchanges
the `request_token` for an `access_token` via Kite's `generate_session`, and
writes it to Neon `app_state`. Free tier (100k req/day) — plenty for one
login per trading day.

## Setup

```bash
cd cloudflare-worker
npm install
npx wrangler login
npx wrangler secret put KITE_API_KEY
npx wrangler secret put KITE_API_SECRET
npx wrangler secret put DATABASE_URL_PAPER
npx wrangler secret put DATABASE_URL_LIVE
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_CHAT_ID
npx wrangler deploy
```

After `wrangler deploy`, note the `*.workers.dev` URL. Register it in the
Zerodha Developer Console as the redirect URL for your app:
`https://insight-alpha.<your-subdomain>.workers.dev/kite/callback`.

## Flow

1. User taps Telegram link → Zerodha login page on phone.
2. Zerodha redirects to the Worker with `?request_token=X&status=success`.
3. Worker calls Kite `generate_session(request_token, api_secret)` →
   receives `{access_token, ...}`.
4. Worker writes token + `expires_at = next 15:30 IST` into both `paper` and
   `live` Neon DBs (key: `kite_access_token`, `kite_session_expires_at` in
   `app_state`).
5. Worker sends Telegram confirmation, returns a plain "✅ Logged in" HTML
   page.

## Security

- All secrets are Cloudflare Worker secrets — never in git.
- The worker only accepts `GET /kite/callback`; all other paths 404.
- `request_token` is one-time-use; Zerodha rejects replays.
- `DATABASE_URL_PAPER` / `LIVE` use Neon's pooled connection string so the
  edge function stays under the 30s CPU limit.

## Fallback

If you'd rather not deploy a worker, the plan's paste-URL flow still works:
users reply to the login Telegram message with the full redirect URL, and
the `telegram-poll` routine regex-extracts the token.
