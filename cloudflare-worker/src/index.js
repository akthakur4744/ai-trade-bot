// Insight-Alpha Cloudflare Worker.
//
// GET /kite/callback?request_token=...&status=success
//   -> exchange request_token for access_token, write to Supabase, confirm via Telegram.
//
// GET /heartbeat/state?mode=paper|live
//   -> read watchdog keys from Supabase app_state, return JSON.
//      Header X-Heartbeat-Token must equal env.HEARTBEAT_TOKEN.
//      Exists because the cloud Routine sandbox cannot reach Supabase on port 6543
//      (HTTPS-only egress); this proxies the read over 443 via Supabase REST API.
//
// GET /memory/sweep?mode=paper|live
//   -> query expired pending_memory_updates rows (no mutation).
//      Returns { expired: [{id, telegram_message_id, title}] }.
//
// POST /memory/sweep?mode=paper|live  body: { "ids": [...] }
//   -> mark listed pending_memory_updates rows as status='expired'.
//      Returns { ok: true, count: N }.

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

async function supabaseUpsert(supabaseUrl, serviceKey, key, value) {
  const res = await fetch(
    `${supabaseUrl}/rest/v1/app_state?key=eq.${encodeURIComponent(key)}`,
    {
      method: "PATCH",
      headers: {
        "apikey": serviceKey,
        "Authorization": `Bearer ${serviceKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ key, value, updated_at: new Date().toISOString() }),
    }
  );
  if (!res.ok) {
    // If PATCH returns 0 rows updated (404-ish), do an INSERT instead
    if (res.status === 404 || res.headers.get("content-range") === "*/0") {
      const insertRes = await fetch(`${supabaseUrl}/rest/v1/app_state`, {
        method: "POST",
        headers: {
          "apikey": serviceKey,
          "Authorization": `Bearer ${serviceKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ key, value, updated_at: new Date().toISOString() }),
      });
      if (!insertRes.ok)
        throw new Error(`supabase insert failed: ${insertRes.status} ${await insertRes.text()}`);
    } else {
      throw new Error(`supabase upsert failed: ${res.status} ${await res.text()}`);
    }
  }
}

async function writeToken(supabaseUrl, serviceKey, accessToken, expiresAtIsoStr) {
  await supabaseUpsert(supabaseUrl, serviceKey, "kite_access_token", accessToken);
  await supabaseUpsert(supabaseUrl, serviceKey, "kite_session_expires_at", expiresAtIsoStr);
}

async function sendTelegram(env, text) {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text }),
  });
}

// Constant-time string compare so we don't leak token length via timing.
function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// Shared auth check — returns a Response on failure, null on success.
function authenticateRequest(request, env) {
  if (!env.HEARTBEAT_TOKEN) return new Response("Not configured", { status: 503 });
  const provided = request.headers.get("x-heartbeat-token") || "";
  if (!timingSafeEqual(provided, env.HEARTBEAT_TOKEN)) return new Response("Forbidden", { status: 403 });
  return null;
}

// Returns [supabaseUrl, serviceKey] based on ?mode=paper|live, or [null, null].
function getSupabaseCredentials(url, env) {
  const mode = url.searchParams.get("mode");
  if (mode === "live")  return [env.SUPABASE_URL_LIVE,  env.SUPABASE_KEY_LIVE];
  if (mode === "paper") return [env.SUPABASE_URL_PAPER, env.SUPABASE_KEY_PAPER];
  return [null, null];
}

const HEARTBEAT_KEYS = [
  "last_signal_scan_ts",
  "last_telegram_poll_ts",
  "last_autosell_tick_ts",
  "kite_access_token",
  "kite_session_expires_at",
];

async function readHeartbeatState(supabaseUrl, serviceKey) {
  const keyList = HEARTBEAT_KEYS.join(",");
  const res = await fetch(
    `${supabaseUrl}/rest/v1/app_state?key=in.(${keyList})&select=key,value`,
    {
      headers: {
        "apikey": serviceKey,
        "Authorization": `Bearer ${serviceKey}`,
      },
    }
  );
  if (!res.ok) throw new Error(`supabase read failed: ${res.status} ${await res.text()}`);
  const rows = await res.json();
  const out = Object.fromEntries(HEARTBEAT_KEYS.map((k) => [k, null]));
  for (const r of rows) out[r.key] = r.value;
  // Don't ship the raw token back — the caller only needs to know it's set.
  out.kite_access_token_present = out.kite_access_token != null;
  delete out.kite_access_token;
  return out;
}

async function handleKiteCallback(url, env) {
  const requestToken = url.searchParams.get("request_token");
  const status = url.searchParams.get("status");
  if (status !== "success" || !requestToken) {
    return new Response("Login failed", { status: 400 });
  }
  try {
    const accessToken = await generateSession(env, requestToken);
    const exp = expiresAtIso();
    await writeToken(env.SUPABASE_URL_PAPER, env.SUPABASE_KEY_PAPER, accessToken, exp);
    await writeToken(env.SUPABASE_URL_LIVE, env.SUPABASE_KEY_LIVE, accessToken, exp);
    await sendTelegram(env, `✅ Kite session active until 15:30 IST.`);
    return new Response(OK_HTML, { headers: { "Content-Type": "text/html" } });
  } catch (err) {
    await sendTelegram(env, `❌ Kite login failed: ${err.message}`);
    return new Response(`Error: ${err.message}`, { status: 500 });
  }
}

async function handleHeartbeatState(request, url, env) {
  const authErr = authenticateRequest(request, env);
  if (authErr) return authErr;
  const [supabaseUrl, serviceKey] = getSupabaseCredentials(url, env);
  if (!supabaseUrl) return new Response("mode must be paper|live", { status: 400 });
  try {
    const state = await readHeartbeatState(supabaseUrl, serviceKey);
    return new Response(JSON.stringify(state), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    });
  }
}

async function handleMemorySweepGet(request, url, env) {
  const authErr = authenticateRequest(request, env);
  if (authErr) return authErr;
  const [supabaseUrl, serviceKey] = getSupabaseCredentials(url, env);
  if (!supabaseUrl) return new Response("mode must be paper|live", { status: 400 });

  const now = new Date().toISOString();
  try {
    const res = await fetch(
      `${supabaseUrl}/rest/v1/pending_memory_updates` +
      `?status=eq.pending&expires_at=lt.${encodeURIComponent(now)}` +
      `&select=id,telegram_message_id,title`,
      { headers: { apikey: serviceKey, Authorization: `Bearer ${serviceKey}` } }
    );
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    const rows = await res.json();
    return new Response(JSON.stringify({ expired: rows }),
      { headers: { "Content-Type": "application/json" } });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }),
      { status: 502, headers: { "Content-Type": "application/json" } });
  }
}

async function handleMemorySweepPost(request, url, env) {
  const authErr = authenticateRequest(request, env);
  if (authErr) return authErr;
  const [supabaseUrl, serviceKey] = getSupabaseCredentials(url, env);
  if (!supabaseUrl) return new Response("mode must be paper|live", { status: 400 });

  const { ids } = await request.json();
  if (!Array.isArray(ids) || ids.length === 0)
    return new Response(JSON.stringify({ ok: true, count: 0 }),
      { headers: { "Content-Type": "application/json" } });

  try {
    const res = await fetch(
      `${supabaseUrl}/rest/v1/pending_memory_updates?id=in.(${ids.join(",")})`,
      {
        method: "PATCH",
        headers: {
          apikey: serviceKey, Authorization: `Bearer ${serviceKey}`,
          "Content-Type": "application/json", Prefer: "return=minimal",
        },
        body: JSON.stringify({ status: "expired" }),
      }
    );
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return new Response(JSON.stringify({ ok: true, count: ids.length }),
      { headers: { "Content-Type": "application/json" } });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }),
      { status: 502, headers: { "Content-Type": "application/json" } });
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/kite/callback") {
      return handleKiteCallback(url, env);
    }
    if (request.method === "GET" && url.pathname === "/heartbeat/state") {
      return handleHeartbeatState(request, url, env);
    }
    if (request.method === "GET"  && url.pathname === "/memory/sweep") return handleMemorySweepGet(request, url, env);
    if (request.method === "POST" && url.pathname === "/memory/sweep") return handleMemorySweepPost(request, url, env);
    return new Response("Not found", { status: 404 });
  },
};
