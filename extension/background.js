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
// The record only changes when a session resolves, so it can be cached longer.
const RECORD_TTL_MS = 60 * 60 * 1000;
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

/**
 * Re-register the content script on every host the user has enabled.
 *
 * Called on install and on browser start: dynamic content-script registrations
 * do NOT survive a browser restart, but the granted permissions DO. Without
 * this replay, a user who enabled Schwab last week would silently get nothing
 * today, with the permission still showing as granted — the worst kind of bug
 * to diagnose from a review.
 */
async function syncEnabledSites() {
  try {
    const granted = await chrome.permissions.getAll();
    const origins = (granted.origins || []).filter((o) => !o.includes("api.tapeline.io"));
    const existing = await chrome.scripting.getRegisteredContentScripts();
    const ids = existing.map((s) => s.id);
    if (ids.length) await chrome.scripting.unregisterContentScripts({ ids });
    if (!origins.length) return;
    await chrome.scripting.registerContentScripts([
      {
        id: "tapeline-enabled-sites",
        matches: origins,
        js: ["sites.js", "content.js"],
        runAt: "document_idle",
      },
    ]);
  } catch (err) {
    console.warn("tapeline: could not sync enabled sites", err);
  }
}

/**
 * First run: show what the extension reads before it reads anything.
 *
 * Chrome Web Store policy (from 1 Aug 2026) requires data-use disclosure in the
 * PRODUCT UI — store-listing text explicitly does not satisfy it. This also
 * happens to be the right thing to do: a finance overlay that silently starts
 * touching pages is exactly what makes people distrust the category.
 * Only on a genuine install, never on update or Chrome refresh.
 */
chrome.runtime.onInstalled.addListener((details) => {
  syncEnabledSites();
  registerContextMenu();
  if (details && details.reason === "install") {
    chrome.tabs.create({ url: chrome.runtime.getURL("welcome.html") });
  }
});
chrome.runtime.onStartup.addListener(() => {
  syncEnabledSites();
  // Context menus do not survive a browser restart either.
  registerContextMenu();
});

/**
 * This ticker's history in the published record.
 *
 * Fetched LAZILY — only when the user expands the panel — for two reasons.
 * Most page views never expand, so eager-fetching would double origin load for
 * data nobody looks at; and the pill needs to appear instantly, which it can't
 * if it waits on a second request. Cached longer than the score because the
 * record only changes once a session resolves.
 */
async function fetchRecord(symbol) {
  const key = `r:${symbol}`;
  try {
    const got = await chrome.storage.session.get(key);
    const hit = got[key];
    if (hit && Date.now() - hit.at < RECORD_TTL_MS) return { ok: true, data: hit.data };
  } catch (_) {}

  try {
    const res = await fetch(
      `${API_BASE}/api/scorecard/symbol/${encodeURIComponent(symbol)}`,
      { signal: AbortSignal.timeout(TIMEOUT_MS), headers: { Accept: "application/json" } }
    );
    if (!res.ok) return { ok: false };
    const raw = await res.json();
    const s = (raw && raw.summary) || {};
    const rows = (raw && raw.rows) || [];
    const data = {
      // appearances === 0 is a real, publishable answer ("never picked"), not a
      // failure — the UI says so rather than hiding the block.
      appearances: s.appearances_scored || 0,
      hitRate: typeof s.hit_rate_beat_spy === "number" ? s.hit_rate_beat_spy : null,
      medianAlpha: typeof s.median_alpha_vs_spy === "number" ? s.median_alpha_vs_spy : null,
      best: typeof s.best_alpha === "number" ? s.best_alpha : null,
      worst: typeof s.worst_alpha === "number" ? s.worst_alpha : null,
      lastSeen: rows.length ? rows[0].as_of : null,
      inUniverse: s.in_universe !== false,
    };
    try {
      await chrome.storage.session.set({ [key]: { at: Date.now(), data } });
    } catch (_) {}
    return { ok: true, data };
  } catch (_) {
    return { ok: false };
  }
}

/**
 * Consent gate.
 *
 * Chrome's 1 Aug 2026 policy change removed the "closely related to the single
 * purpose" exemption, so a prominent in-product disclosure with an affirmative
 * accept is required BEFORE the first network call — store-listing text does
 * not satisfy it. The content script asks here rather than reading storage
 * itself so there is exactly one definition of "has consented".
 */
async function hasConsent() {
  try {
    const got = await chrome.storage.local.get("consentAt");
    return Boolean(got.consentAt);
  } catch (_) {
    return false;   // fail closed: no consent record, no network call
  }
}

/**
 * Right-click a highlighted ticker anywhere on the web → look it up.
 *
 * The best value-per-hour idea in the teardown: it delivers the "works
 * anywhere" promise with ZERO host permissions, zero DOM reading and zero
 * maintenance tax, because the selection is handed to us by the browser rather
 * than scraped. Nothing here can rot when a host site redesigns.
 */
function registerContextMenu() {
  try {
    chrome.contextMenus.removeAll(() => {
      chrome.contextMenus.create({
        id: "tapeline-lookup",
        title: 'Look up "%s" in Tapeline',
        contexts: ["selection"],
      });
    });
  } catch (_) {}
}

chrome.contextMenus?.onClicked.addListener((info) => {
  if (info.menuItemId !== "tapeline-lookup") return;
  const raw = (info.selectionText || "").trim().toUpperCase();
  // Accept a bare symbol or a $CASHTAG; anything else is a mis-click, and
  // opening a junk page would be worse than doing nothing.
  const m = raw.match(/^\$?([A-Z][A-Z0-9.\-]{0,9})$/);
  if (!m) return;
  chrome.tabs.create({ url: link(`/t/${encodeURIComponent(m[1])}`) });
});

/**
 * Score in the toolbar badge — answers "is there anything here for me?" for
 * zero pixels of page real estate, which is the discovery problem overlays die
 * of. Per-tab so it never leaks one tab's ticker into another.
 */
function setBadge(tabId, text) {
  if (!tabId) return;
  try {
    chrome.action.setBadgeText({ tabId, text: text || "" });
    if (text) {
      chrome.action.setBadgeBackgroundColor({ tabId, color: "#3b82f6" });
      chrome.action.setBadgeTextColor?.({ tabId, color: "#ffffff" });
    }
  } catch (_) {}
}

// Grants made from Chrome's own "Site access" UI never touch our popup, so
// without these the user (or a reviewer testing that path) grants access and
// nothing happens.
chrome.permissions.onAdded.addListener(syncEnabledSites);
chrome.permissions.onRemoved.addListener(syncEnabledSites);

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "TAPELINE_CONSENT") {
    hasConsent().then((ok) => sendResponse({ ok }));
    return true;
  }
  if (msg && msg.type === "TAPELINE_BADGE") {
    setBadge(sender && sender.tab && sender.tab.id, msg.text);
    return false;
  }
  if (msg && msg.type === "TAPELINE_RECORD" && msg.symbol) {
    fetchRecord(String(msg.symbol).toUpperCase()).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "TAPELINE_SYNC_SITES") {
    syncEnabledSites().then(() => sendResponse({ ok: true }));
    return true;
  }
  if (msg && msg.type === "TAPELINE_LOOKUP" && msg.symbol) {
    fetchTicker(String(msg.symbol).toUpperCase()).then(sendResponse);
    return true; // async response
  }
  if (msg && msg.type === "TAPELINE_LINKS") {
    sendResponse({ site: link("/"), scorecard: link("/scorecard") });
  }
  return false;
});
