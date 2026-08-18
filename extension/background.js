/**
 * Service worker — the only place that talks to the Tapeline API.
 *
 * WHY NOT FETCH FROM THE CONTENT SCRIPT
 * -------------------------------------
 * Since Chrome 85 a content-script fetch is subject to the HOST page's CORS,
 * and api.tapeline.io only allows the app origin (backend `main.py`
 * CORSMiddleware allow_origins). A fetch from finance.yahoo.com would be
 * blocked. Extension service-worker fetches covered by `host_permissions` are
 * exempt, so all network access lives here and results are passed back over
 * runtime messaging. This also means the backend needs no CORS change.
 *
 * LOAD DISCIPLINE
 * ---------------
 * `/api/ticker/{symbol}` backs the public SSR pages, so an extension that
 * re-fetched on every navigation could add real origin load. Two guards:
 * a per-symbol cache in session storage (TTL below), and single-flight
 * de-duplication so N tabs opening the same symbol produce one request.
 * Scores move on a daily cadence, so a stale-by-minutes read is fine.
 */

const API_BASE = "https://api.tapeline.io";
const SITE = "https://tapeline.io";
const TTL_MS = 15 * 60 * 1000;
const TIMEOUT_MS = 8000;

/** In-flight requests, so concurrent tabs collapse to one fetch. */
const inflight = new Map();

/** Attribution — the weekly prod-pulse buckets signups by utm_source. */
function link(path) {
  return `${SITE}${path}?utm_source=extension&utm_medium=overlay`;
}

async function readCache(symbol) {
  try {
    const key = `t:${symbol}`;
    const got = await chrome.storage.session.get(key);
    const hit = got[key];
    if (hit && Date.now() - hit.at < TTL_MS) return hit.data;
  } catch (_) {}
  return null;
}

async function writeCache(symbol, data) {
  try {
    await chrome.storage.session.set({ [`t:${symbol}`]: { at: Date.now(), data } });
  } catch (_) {}
}

/** Keep only what the overlay renders — the full payload carries news + history. */
function trim(raw) {
  if (!raw || typeof raw !== "object") return null;
  const b = raw.breakdown || {};
  const factors = ["trend", "rs", "fundamentals", "smart_money", "macro", "momentum"]
    .filter((k) => b[k] && typeof b[k].value === "number")
    .map((k) => ({ key: k, value: b[k].value, label: b[k].label || null }));
  return {
    symbol: raw.symbol,
    name: raw.name || null,
    score: typeof raw.score === "number" ? raw.score : null,
    signal: raw.signal || null,
    confidence: typeof raw.confidence_pct === "number" ? raw.confidence_pct : null,
    reason: raw.reason || null,
    factors,
    url: link(`/t/${encodeURIComponent(raw.symbol || "")}`),
    scorecardUrl: link("/scorecard"),
  };
}

async function fetchTicker(symbol) {
  const cached = await readCache(symbol);
  if (cached) return { ok: true, data: cached, cached: true };

  if (inflight.has(symbol)) return inflight.get(symbol);

  const job = (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ticker/${encodeURIComponent(symbol)}`, {
        signal: AbortSignal.timeout(TIMEOUT_MS),
        headers: { Accept: "application/json" },
      });
      if (res.status === 404) return { ok: false, reason: "not_covered" };
      if (!res.ok) return { ok: false, reason: "unavailable" };
      const data = trim(await res.json());
      if (!data || data.score === null) return { ok: false, reason: "not_covered" };
      await writeCache(symbol, data);
      return { ok: true, data, cached: false };
    } catch (_) {
      return { ok: false, reason: "unavailable" };
    } finally {
      inflight.delete(symbol);
    }
  })();

  inflight.set(symbol, job);
  return job;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "TAPELINE_LOOKUP" && msg.symbol) {
    fetchTicker(String(msg.symbol).toUpperCase()).then(sendResponse);
    return true; // async response
  }
  if (msg && msg.type === "TAPELINE_LINKS") {
    sendResponse({ site: link("/"), scorecard: link("/scorecard") });
  }
  return false;
});
