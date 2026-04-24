# Cloudflare Worker — Kite Login Callback

Receives Zerodha's redirect after the user logs in on their phone, exchanges
the `request_token` for an `access_token` via Kite's `generate_session`, and
writes it to Supabase `app_state`. Free tier (100k req/day) — plenty for one
login per trading day.

## Setup

```bash
cd cloudflare-worker
npm install
npx wrangler login
npx wrangler secret put KITE_API_KEY
npx wrangler secret put KITE_API_SECRET
npx wrangler secret put SUPABASE_URL_PAPER   # https://mgarzpkoxgicdacujhny.supabase.co
npx wrangler secret put SUPABASE_URL_LIVE    # https://xagungelhyaqwokamayo.supabase.co
npx wrangler secret put SUPABASE_KEY_PAPER   # service_role key (Supabase dashboard → Project Settings → API)
npx wrangler secret put SUPABASE_KEY_LIVE    # service_role key for live project
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_CHAT_ID
npx wrangler secret put HEARTBEAT_TOKEN      # any long random string; mirror to Cloud Routine env
npx wrangler deploy
```

After `wrangler deploy`, note the `*.workers.dev` URL. Register it in the
Zerodha Developer Console as the redirect URL for your app:
`https://insight-alpha.<your-subdomain>.workers.dev/kite/callback`.

## Endpoints

All authenticated endpoints require `X-Heartbeat-Token: $HEARTBEAT_TOKEN` header.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/kite/callback` | Zerodha OAuth redirect handler (see Flow below). No auth token needed — called by Zerodha. |
| `GET` | `/heartbeat/state?mode=paper\|live` | Read-only view of watchdog keys in `app_state`. Returns `last_signal_scan_ts`, `last_telegram_poll_ts`, `last_autosell_tick_ts`, `kite_access_token_present`, `kite_session_expires_at`. |
| `GET` | `/memory/sweep?mode=paper\|live` | Query expired `pending_memory_updates` rows (no DB mutation). Returns `{ expired: [{id, telegram_message_id, title}] }`. |
| `POST` | `/memory/sweep?mode=paper\|live` | Body: `{ "ids": [1,2,3] }`. Marks listed rows as `status='expired'`. Returns `{ ok: true, count: N }`. |

These endpoints exist because the Cloud Routine sandbox blocks outbound Postgres (port 6543) — routines read/write state over HTTPS via this proxy instead of connecting to Supabase directly.

## Flow

1. User taps Telegram link → Zerodha login page on phone.
2. Zerodha redirects to the Worker with `?request_token=X&status=success`.
3. Worker calls Kite `generate_session(request_token, api_secret)` →
   receives `{access_token, ...}`.
4. Worker writes token + `expires_at = next 15:30 IST` into both `paper` and
   `live` Supabase DBs via REST API (key: `kite_access_token`,
   `kite_session_expires_at` in `app_state`).
5. Worker sends Telegram confirmation, returns a plain "✅ Logged in" HTML
   page.

## Security

- All secrets are Cloudflare Worker secrets — never in git.
- All `/heartbeat/*` and `/memory/*` endpoints require `X-Heartbeat-Token` with constant-time comparison (no timing oracle).
- `request_token` is one-time-use; Zerodha rejects replays.
- `SUPABASE_KEY_PAPER/LIVE` are `service_role` keys — they bypass Row Level Security. Never expose them client-side.

## Fallback

If you'd rather not deploy a worker, the plan's paste-URL flow still works:
users reply to the login Telegram message with the full redirect URL, and
the `telegram-poll` routine regex-extracts the token.
