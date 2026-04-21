// Kite login redirect handler.
//
// GET /kite/callback?request_token=...&status=success
//   -> POST https://api.kite.trade/session/token  (generate_session)
//   -> write access_token to Neon (both DBs)
//   -> Telegram confirmation
//   -> return "✅ Logged in" HTML

import { neon } from "@neondatabase/serverless";

const OK_HTML = `<!doctype html><html><body style="font-family:system-ui;padding:2rem">
<h1>✅ Logged in</h1><p>You can close this tab. Insight-Alpha will pick up the session.</p>
</body></html>`;

async function sha256Hex(input) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function generateSession(env, requestToken) {
  const checksum = await sha256Hex(env.KITE_API_KEY + requestToken + env.KITE_API_SECRET);
  const body = new URLSearchParams({
    api_key: env.KITE_API_KEY,
    request_token: requestToken,
    checksum,
  });
  const res = await fetch("https://api.kite.trade/session/token", {
    method: "POST",
    headers: {
      "X-Kite-Version": "3",
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });
  if (!res.ok) throw new Error(`kite generate_session failed: ${res.status} ${await res.text()}`);
  const payload = await res.json();
  if (payload.status !== "success") throw new Error(`kite response: ${JSON.stringify(payload)}`);
  return payload.data.access_token;
}

// End of trading day in IST — Kite invalidates tokens at 15:30 IST
// (= 10:00 UTC). We store a few minutes earlier to be safe.
function expiresAtIso() {
  const now = new Date();
  const expiry = new Date(now);
  expiry.setUTCHours(9, 55, 0, 0);
  if (expiry <= now) expiry.setUTCDate(expiry.getUTCDate() + 1);
  return expiry.toISOString();
}

async function writeToken(dbUrl, accessToken, expiresAtIsoStr) {
  const sql = neon(dbUrl);
  // app_state has a UNIQUE index on key — ON CONFLICT upserts cleanly.
  await sql`
    INSERT INTO app_state (key, value, updated_at)
    VALUES ('kite_access_token', ${accessToken}, now())
    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
  `;
  await sql`
    INSERT INTO app_state (key, value, updated_at)
    VALUES ('kite_session_expires_at', ${expiresAtIsoStr}, now())
    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
  `;
}

async function sendTelegram(env, text) {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text }),
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== "GET" || url.pathname !== "/kite/callback") {
      return new Response("Not found", { status: 404 });
    }
    const requestToken = url.searchParams.get("request_token");
    const status = url.searchParams.get("status");
    if (status !== "success" || !requestToken) {
      return new Response("Login failed", { status: 400 });
    }

    try {
      const accessToken = await generateSession(env, requestToken);
      const exp = expiresAtIso();
      await writeToken(env.DATABASE_URL_PAPER, accessToken, exp);
      await writeToken(env.DATABASE_URL_LIVE, accessToken, exp);
      await sendTelegram(env, `✅ Kite session active until 15:30 IST.`);
      return new Response(OK_HTML, { headers: { "Content-Type": "text/html" } });
    } catch (err) {
      await sendTelegram(env, `❌ Kite login failed: ${err.message}`);
      return new Response(`Error: ${err.message}`, { status: 500 });
    }
  },
};
