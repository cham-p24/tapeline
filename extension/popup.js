/** Manual lookup — works on any page, including sites with no content script. */
const FACTOR_LABEL = {
  trend: "Trend", rs: "Rel. strength", fundamentals: "Fundamentals",
  smart_money: "Smart money", macro: "Macro", momentum: "Momentum",
};
const TONE = {
  "STRONG SETUP": "pos", "HIGH CONVICTION": "pos", CONSTRUCTIVE: "pos",
  NEUTRAL: "mid", CAUTION: "neg", WEAK: "neg",
};
const out = document.getElementById("out");
const siteEl = document.getElementById("site");
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function show(html) { out.innerHTML = html; }

async function lookup(symbol) {
  show('<p class="msg">Checking…</p>');
  let res;
  try { res = await chrome.runtime.sendMessage({ type: "TAPELINE_LOOKUP", symbol }); }
  catch (_) { res = { ok: false, reason: "unavailable" }; }

  if (!res || !res.ok) {
    const why =
      res && res.reason === "connect_required"
        ? "Connect your Tapeline account to look up tickers."
        : res && res.reason === "not_covered"
          ? esc(symbol) + " isn't in Tapeline's covered universe."
          : "Couldn't reach Tapeline just now.";
    show(`<p class="msg">${why}</p>`);
    return;
  }
  const d = res.data;
  const tone = TONE[(d.signal || "").toUpperCase()] || "mid";
  const factors = (d.factors || []).map((f) => {
    const v = Math.round(f.value);
    return `<div class="f"><span class="fl">${esc(FACTOR_LABEL[f.key] || f.key)}</span>
      <span class="bar"><i style="width:${Math.max(0, Math.min(100, v))}%"></i></span>
      <span class="fv">${v}</span></div>`;
  }).join("");
  show(`
    <div class="row">
      <div><div class="sym">${esc(d.symbol)}</div><div class="name">${esc(d.name || "")}</div>${d.confidence != null ? `<div class="conf">${esc(d.signal || "")} · ${Math.round(d.confidence)}% confidence</div>` : ""}</div>
      <div class="score ${tone}">${d.score == null ? "–" : Math.round(d.score)}<span>/100</span></div>
    </div>
    ${d.reason ? `<p class="why">${esc(d.reason)}</p>` : ""}
    ${factors}
    <div class="actions">
      <a class="btn" href="${esc(d.url)}" target="_blank" rel="noopener">Full breakdown</a>
      <a class="btn ghost" href="${esc(d.scorecardUrl)}" target="_blank" rel="noopener">Public record</a>
    </div>
    <div id="rec"></div>
    <p class="fine">Descriptive six-factor scoring — not investment advice. Every daily top-10 pick is logged publicly, including the ones that lose.</p>`);

  // Eager here, unlike the overlay: opening the popup is explicit intent, so
  // there is no wasted fetch to avoid.
  loadRecord(d.symbol);
}

/**
 * This ticker's own history in the published record — the thing no rival
 * overlay can show. "Never published" is a real answer and is stated plainly;
 * where there IS a history, the worst pick is shown next to the best, because
 * showing only the best is the selective memory this product argues against.
 */
async function loadRecord(symbol) {
  let res;
  try { res = await chrome.runtime.sendMessage({ type: "TAPELINE_RECORD", symbol }); }
  catch (_) { return; }
  const slot = document.getElementById("rec");
  if (!slot || !res || !res.ok) return;
  const r = res.data;

  if (!r.appearances) {
    slot.innerHTML =
      '<div class="rec"><div class="rec-h">Tapeline\'s record on this ticker</div>' +
      '<div class="rec-empty">Never published in the daily top 10.</div></div>';
    return;
  }
  const pct = (v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
  const rows = [];
  if (r.hitRate != null) {
    rows.push(`<div class="rec-row"><span>Beat SPY next session</span><b>${Math.round(r.hitRate)}%</b></div>`);
  }
  if (r.medianAlpha != null) {
    rows.push(`<div class="rec-row"><span>Median vs SPY</span><b class="${r.medianAlpha >= 0 ? "up" : "down"}">${pct(r.medianAlpha)}</b></div>`);
  }
  if (r.best != null && r.worst != null) {
    rows.push(`<div class="rec-row"><span>Best / worst</span><b><span class="up">${pct(r.best)}</span> · <span class="down">${pct(r.worst)}</span></b></div>`);
  }
  slot.innerHTML =
    '<div class="rec"><div class="rec-h">Tapeline\'s record on this ticker</div>' +
    `<div class="rec-n">Published ${r.appearances}× in the daily top 10${r.lastSeen ? ` · last ${esc(r.lastSeen)}` : ""}</div>` +
    rows.join("") +
    `<div class="rec-note">Descriptive measures of ${r.appearances} past published pick${r.appearances === 1 ? "" : "s"} — too small a sample to distinguish from chance.</div></div>`;
}

/* ── Enable on this site ───────────────────────────────────────────────────
   The built-in list covers public research sites. Brokers and the long tail
   are reached here instead: the user grants access to THIS origin only. That
   is both the honest ask — we read the ticker out of the URL and nothing else
   — and the one Chrome Web Store review accepts, since requesting every site
   up front is the single most common rejection reason. */

/**
 * Account state. The extension requires a Tapeline account, so this is the
 * first thing the popup resolves — everything else is meaningless without it.
 */
async function renderAccount() {
  let acct = null;
  try {
    const res = await chrome.runtime.sendMessage({ type: "TAPELINE_ACCOUNT" });
    acct = res && res.account;
  } catch (_) {}

  if (acct) {
    const row = document.createElement("div");
    row.className = "acct-row";
    row.innerHTML =
      `<span>Connected as <b>${esc(acct)}</b></span><button id="disconnect">Disconnect</button>`;
    siteEl.appendChild(row);
    document.getElementById("disconnect").addEventListener("click", async () => {
      try { await chrome.runtime.sendMessage({ type: "TAPELINE_DISCONNECT" }); } catch (_) {}
      location.reload();
    });
    return true;
  }

  siteEl.innerHTML =
    '<div class="site-card"><b>Connect your Tapeline account</b><br>' +
    'The extension works with a Tapeline account. Get your connect code, ' +
    'paste it below, and you are done.' +
    '<button id="getcode">Get my connect code</button>' +
    '<input id="code" placeholder="Paste your connect code" autocomplete="off" spellcheck="false">' +
    '<button id="doconnect">Connect</button>' +
    '<span id="cerr" class="cerr" hidden></span></div>';

  document.getElementById("getcode").addEventListener("click", () => {
    chrome.tabs.create({
      url: "https://tapeline.io/extension/connect?utm_source=extension&utm_medium=popup",
    });
  });

  const err = document.getElementById("cerr");
  document.getElementById("doconnect").addEventListener("click", async () => {
    const token = document.getElementById("code").value.trim();
    err.hidden = true;
    if (!token) {
      err.textContent = "Paste the code from tapeline.io first.";
      err.hidden = false;
      return;
    }
    let res;
    try { res = await chrome.runtime.sendMessage({ type: "TAPELINE_CONNECT", token }); }
    catch (_) { res = { ok: false, reason: "unavailable" }; }
    if (res && res.ok) { location.reload(); return; }
    err.textContent =
      res && res.reason === "invalid"
        ? "That code wasn't accepted. Get a fresh one and try again."
        : "Couldn't reach Tapeline. Check your connection.";
    err.hidden = false;
  });
  return false;
}

/**
 * Permanent per-site mute.
 *
 * The × on the pill only hides it for one page view. Every overlay eventually
 * shows up somewhere the user doesn't want it, and the ones that survive years
 * (Dark Reader) make "off here, permanently" a first-class control instead of
 * letting that moment become an uninstall.
 */
async function getMuted() {
  try {
    const got = await chrome.storage.local.get("mutedHosts");
    return Array.isArray(got.mutedHosts) ? got.mutedHosts : [];
  } catch (_) {
    return [];
  }
}

async function renderMute(host) {
  const list = await getMuted();
  const isMuted = list.includes(host);
  const el = document.createElement("div");
  el.className = "mute-row";
  el.innerHTML = isMuted
    ? `<span>Hidden on <b>${esc(host)}</b></span><button id="mute">Show again</button>`
    : `<button id="mute">Hide on ${esc(host)}</button>`;
  siteEl.appendChild(el);

  document.getElementById("mute").addEventListener("click", async () => {
    const cur = await getMuted();
    const next = isMuted ? cur.filter((h) => h !== host) : cur.concat([host]);
    try { await chrome.storage.local.set({ mutedHosts: next }); } catch (_) {}
    siteEl.querySelector(".mute-row")?.remove();
    await renderMute(host);
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab && tab.id) chrome.tabs.reload(tab.id);
    } catch (_) {}
  });
}

function renderSite(host, origin, granted) {
  if (granted) {
    siteEl.innerHTML =
      `<div class="site-card"><b>${esc(host)}</b><br>` +
      `<span class="ok">Enabled</span> — the score shows on ticker pages here.</div>`;
    return;
  }
  siteEl.innerHTML =
    `<div class="site-card"><b>${esc(host)}</b> isn't covered yet.<br>` +
    `Enable it and Tapeline reads the ticker from the page address — nothing else.` +
    `<button id="enable">Enable on this site</button></div>`;

  document.getElementById("enable").addEventListener("click", async () => {
    let ok = false;
    try {
      ok = await chrome.permissions.request({ origins: [origin] });
    } catch (_) {}
    if (!ok) return;   // user declined — leave the card as-is
    try {
      await chrome.runtime.sendMessage({ type: "TAPELINE_SYNC_SITES" });
    } catch (_) {}
    renderSite(host, origin, true);
    // The content script is registered from here on, but this tab predates it.
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab && tab.id) chrome.tabs.reload(tab.id);
    } catch (_) {}
  });
}

document.getElementById("f").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = document.getElementById("q").value.trim().toUpperCase();
  if (/^[A-Z][A-Z0-9.\-]{0,9}$/.test(v)) lookup(v);
  else show('<p class="msg">Enter a ticker symbol, e.g. NVDA.</p>');
});

/**
 * Calibration first run.
 *
 * Opening the popup on a non-finance page used to show an empty input, which
 * tells a stranger nothing about whether the product is any good. Showing a
 * live score for a company they already hold a private opinion about lets them
 * audit us in one glance — the single cheapest trust-building move available.
 */
const CALIBRATION = ["NVDA", "AAPL", "MSFT"];

async function showCalibration() {
  for (const sym of CALIBRATION) {
    let res;
    try { res = await chrome.runtime.sendMessage({ type: "TAPELINE_LOOKUP", symbol: sym }); }
    catch (_) { return; }
    if (res && res.ok) {
      document.getElementById("q").value = sym;
      await lookup(sym);
      return;
    }
  }
}

/* Pre-fill from the active tab, and offer to enable the site when it's new.
 *
 * `tab.url` is only populated because the manifest declares `activeTab`, which
 * Chrome grants the moment the user clicks the toolbar icon — i.e. exactly when
 * this runs — and which costs no extra install warning. Without it Chrome
 * redacts url/title on every host we lack permission for, this function
 * returned early, and the "Enable on this site" card never rendered on any
 * broker. The whole opt-in architecture was unreachable in production. */
chrome.tabs.query({ active: true, currentWindow: true }).then(async ([tab]) => {
  const connected = await renderAccount();
  if (!connected) {
    // Hide the lookup form too — it would 401 without a token.
    const form = document.getElementById("f");
    if (form) form.hidden = true;
    return;
  }
  if (!tab) return;
  if (!tab.url) {
    // Defensive: if a future manifest edit drops activeTab, fail loudly in the
    // UI rather than silently pretending no site is open.
    siteEl.innerHTML =
      '<div class="site-card">Can\'t read the current tab. Use the box above to look up a ticker.</div>';
    return;
  }
  let u;
  try { u = new URL(tab.url); } catch (_) { return; }
  if (!/^https?:$/.test(u.protocol)) return;   // chrome://, file://, extension pages

  const known = isKnownHost(u.hostname);
  const origin = `${u.protocol}//${u.hostname}/*`;
  let granted = known;
  if (!known) {
    try { granted = await chrome.permissions.contains({ origins: [origin] }); } catch (_) {}
    renderSite(u.hostname, origin, granted);
  }
  // Mute control shows on every http(s) site, covered or not — it is the
  // recovery path when the pill appears somewhere unwanted.
  await renderMute(u.hostname);

  const sym = detectSymbol(
    { hostname: u.hostname, pathname: u.pathname, search: u.search, hash: u.hash },
    !known && granted
  );
  if (sym) { document.getElementById("q").value = sym; lookup(sym); }
  else showCalibration();
}).catch(() => {});

/* Consent state, surfaced here too: someone who closed the welcome tab without
   accepting would otherwise find a silently inert extension and assume it's
   broken. The overlay genuinely does nothing until consent is recorded. */
chrome.runtime.sendMessage({ type: "TAPELINE_CONSENT" }).then((c) => {
  if (c && c.ok) return;
  siteEl.innerHTML =
    '<div class="site-card">Tapeline is installed but not switched on yet.' +
    '<button id="consent">Review and turn on</button></div>';
  document.getElementById("consent").addEventListener("click", () => {
    chrome.tabs.create({ url: chrome.runtime.getURL("welcome.html") });
  });
}).catch(() => {});
