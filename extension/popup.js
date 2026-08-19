/** Manual lookup — works on any page, including sites with no content script. */
const FACTOR_LABEL = {
  trend: "Trend", rs: "Rel. strength", fundamentals: "Fundamentals",
  smart_money: "Smart money", macro: "Macro", momentum: "Momentum",
};
const TONE = {
  "STRONG SETUP": "pos", "HIGH CONVICTION": "pos", CONSTRUCTIVE: "pos",
  NEUTRAL: "mid", WATCH: "mid", CAUTION: "neg", AVOID: "neg",
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
    show(`<p class="msg">${res && res.reason === "not_covered"
      ? esc(symbol) + " isn't in Tapeline's covered universe."
      : "Couldn't reach Tapeline just now."}</p>`);
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
    <p class="fine">Descriptive six-factor scoring — not investment advice. Every daily top-10 pick is logged publicly, including the ones that lose.</p>`);
}

/* ── Enable on this site ───────────────────────────────────────────────────
   The built-in list covers public research sites. Brokers and the long tail
   are reached here instead: the user grants access to THIS origin only. That
   is both the honest ask — we read the ticker out of the URL and nothing else
   — and the one Chrome Web Store review accepts, since requesting every site
   up front is the single most common rejection reason. */

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

/* Pre-fill from the active tab, and offer to enable the site when it's new. */
chrome.tabs.query({ active: true, currentWindow: true }).then(async ([tab]) => {
  if (!tab || !tab.url) return;
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

  const sym = detectSymbol(
    { hostname: u.hostname, pathname: u.pathname, search: u.search, hash: u.hash },
    !known && granted
  );
  if (sym) { document.getElementById("q").value = sym; lookup(sym); }
}).catch(() => {});
