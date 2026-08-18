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
      <div><div class="sym">${esc(d.symbol)}</div><div class="name">${esc(d.name || "")}</div></div>
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

document.getElementById("f").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = document.getElementById("q").value.trim().toUpperCase();
  if (/^[A-Z][A-Z0-9.\-]{0,9}$/.test(v)) lookup(v);
  else show('<p class="msg">Enter a ticker symbol, e.g. NVDA.</p>');
});

/* If the active tab is a supported quote page, pre-fill and look it up. */
chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => {
  if (!tab || !tab.url) return;
  try {
    const u = new URL(tab.url);
    const sym = detectSymbol({ hostname: u.hostname, pathname: u.pathname, search: u.search });
    if (sym) { document.getElementById("q").value = sym; lookup(sym); }
  } catch (_) {}
}).catch(() => {});
