/**
 * Injects the Tapeline pill for whichever ticker the page is showing.
 *
 * DESIGN CONSTRAINTS
 * ------------------
 * 1. Shadow DOM. Finance sites ship broad, aggressive CSS; an open div would be
 *    restyled by the host within a release or two. The whole UI lives in a
 *    closed-ish shadow root with its own styles.
 * 2. Collapsed by default. The pill states the score and nothing else until the
 *    user asks for more. An overlay that covers a chart is an uninstall.
 * 3. Read-only on the host. We take the SYMBOL from the URL and nothing else —
 *    no scraping of the host's data, no DOM mutation outside our own container.
 *    That keeps us clear of both the sites' terms and the store's single-purpose
 *    policy.
 * 4. Dismissible, and it stays dismissed for the tab session.
 */

(function () {
  if (window.__tapelineInjected) return;
  window.__tapelineInjected = true;

  const HOST_ID = "tapeline-overlay-root";

  /* Inlined, not a manifest CSS file: styles must live INSIDE the shadow root,
     and a content_scripts stylesheet cannot pierce it. Dark-first with a light
     override, since finance sites run both. */
  const CSS = `
  :host { all: initial; }
  .tl-wrap { position: fixed; right: 18px; bottom: 18px; z-index: 2147483000;
    font-family: ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
    display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
  .tl-pill { display: inline-flex; align-items: center; gap: 8px; cursor: pointer;
    background: #16181d; color: #e9e7e1; border: 1px solid #333740; border-radius: 999px;
    padding: 7px 10px 7px 9px; box-shadow: 0 6px 22px rgba(0,0,0,.28); font-size: 13px;
    line-height: 1; user-select: none; }
  .tl-pill:hover { border-color: #4a505c; }
  /* The brand mark itself — same geometry as frontend/public/favicon.svg, so the
     pill carries the real logo rather than a lookalike badge. */
  .tl-mark { width: 16px; height: 16px; border-radius: 3px; background: #0a0a0a; flex: none;
    display: inline-flex; align-items: center; justify-content: center; }
  .tl-mark i { display: block; width: 10px; height: 2.5px; border-radius: 999px; background: #3b82f6; }
  .tl-score { font-weight: 700; font-variant-numeric: tabular-nums; font-size: 15px; }
  .tl-sig { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: #9a978e; }
  .tl-sym { font-weight: 700; font-variant-numeric: tabular-nums; }
  .tl-muted { color: #9a978e; font-size: 12px; }
  .tl-pos .tl-score { color: #4ec98a; } .tl-neg .tl-score { color: #e0796f; }
  .tl-mid .tl-score { color: #e0ad4f; }
  .tl-x { all: unset; cursor: pointer; color: #6e6b64; font-size: 15px; padding: 0 2px; }
  .tl-x:hover { color: #e9e7e1; }
  .tl-dot { width: 7px; height: 7px; border-radius: 50%; background: #3b82f6;
    animation: tl-p 1s ease-in-out infinite; }
  @keyframes tl-p { 0%,100% { opacity: .35 } 50% { opacity: 1 } }
  .tl-panel { width: 292px; background: #16181d; color: #e9e7e1; border: 1px solid #333740;
    border-radius: 12px; padding: 14px; box-shadow: 0 18px 48px rgba(0,0,0,.4); font-size: 13px; }
  .tl-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
  .tl-h-sym { font-weight: 700; font-size: 15px; font-variant-numeric: tabular-nums; }
  .tl-h-name { color: #9a978e; font-size: 12px; margin-top: 1px; }
  .tl-h-score { font-size: 26px; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1; }
  .tl-h-score span { font-size: 11px; color: #9a978e; font-weight: 500; }
  .tl-h-score.tl-pos { color: #4ec98a; } .tl-h-score.tl-neg { color: #e0796f; }
  .tl-h-score.tl-mid { color: #e0ad4f; }
  .tl-why { margin: 10px 0 12px; color: #c9c6bf; line-height: 1.5; font-size: 12.5px; }
  .tl-factors { display: flex; flex-direction: column; gap: 5px; }
  .tl-f { display: grid; grid-template-columns: 82px 1fr 24px; align-items: center; gap: 8px; }
  .tl-fl { color: #9a978e; font-size: 11px; }
  .tl-bar { background: #262a32; height: 5px; border-radius: 3px; overflow: hidden; }
  .tl-bar i { display: block; height: 100%; background: #3b82f6; border-radius: 3px; }
  .tl-fv { text-align: right; font-size: 11px; font-variant-numeric: tabular-nums; color: #c9c6bf; }
  .tl-actions { display: flex; gap: 8px; margin-top: 13px; }
  .tl-btn { flex: 1; text-align: center; text-decoration: none; font-size: 12px; font-weight: 600;
    padding: 7px 9px; border-radius: 7px; background: #3b82f6; color: #fff; }
  .tl-btn-ghost { background: transparent; color: #c9c6bf; border: 1px solid #333740; }
  .tl-btn:hover { opacity: .9; }
  .tl-fine { margin: 11px 0 0; color: #7c7a72; font-size: 10.5px; line-height: 1.45; }
  @media (prefers-color-scheme: light) {
    .tl-pill, .tl-panel { background: #fff; color: #1a1a1a; border-color: #dcd8cf; }
    .tl-muted, .tl-fl, .tl-h-name, .tl-h-score span { color: #6b665d; }
    .tl-why, .tl-fv, .tl-btn-ghost { color: #333; }
    .tl-bar { background: #eceae5; }
    .tl-btn-ghost { border-color: #dcd8cf; }
    .tl-fine { color: #8a857c; }
  }
  @media (prefers-reduced-motion: reduce) { .tl-dot { animation: none } }
  `;
  let current = null;   // symbol currently rendered
  let dismissed = false;
  let host, root;

  const SIGNAL_TONE = {
    "STRONG SETUP": "pos",
    "HIGH CONVICTION": "pos",
    CONSTRUCTIVE: "pos",
    NEUTRAL: "mid",
    "WATCH": "mid",
    CAUTION: "neg",
    AVOID: "neg",
  };

  const FACTOR_LABEL = {
    trend: "Trend",
    rs: "Rel. strength",
    fundamentals: "Fundamentals",
    smart_money: "Smart money",
    macro: "Macro",
    momentum: "Momentum",
  };

  function ensureHost() {
    if (host && document.documentElement.contains(host)) return;
    host = document.createElement("div");
    host.id = HOST_ID;
    root = host.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = CSS;
    root.appendChild(style);
    document.documentElement.appendChild(host);
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function render(state, data, symbol) {
    ensureHost();
    const prev = root.querySelector(".tl-wrap");
    if (prev) prev.remove();

    const wrap = document.createElement("div");
    wrap.className = "tl-wrap";

    if (state === "loading") {
      wrap.innerHTML = `<div class="tl-pill tl-loading"><span class="tl-dot"></span><span class="tl-sym">${esc(symbol)}</span><span class="tl-muted">checking…</span></div>`;
    } else if (state === "missing") {
      wrap.innerHTML = `<div class="tl-pill"><span class="tl-sym">${esc(symbol)}</span><span class="tl-muted">not in Tapeline's universe</span><button class="tl-x" title="Hide">×</button></div>`;
    } else if (state === "error") {
      wrap.innerHTML = `<div class="tl-pill"><span class="tl-sym">${esc(symbol)}</span><span class="tl-muted">score unavailable</span><button class="tl-x" title="Hide">×</button></div>`;
    } else {
      const tone = SIGNAL_TONE[(data.signal || "").toUpperCase()] || "mid";
      const score = data.score == null ? "–" : Math.round(data.score);
      const factors = (data.factors || [])
        .map((f) => {
          const v = Math.round(f.value);
          return `<div class="tl-f"><span class="tl-fl">${esc(FACTOR_LABEL[f.key] || f.key)}</span><span class="tl-bar"><i style="width:${Math.max(0, Math.min(100, v))}%"></i></span><span class="tl-fv">${v}</span></div>`;
        })
        .join("");

      wrap.innerHTML = `
        <div class="tl-pill tl-${tone}" role="button" tabindex="0" aria-expanded="false">
          <span class="tl-mark" aria-hidden="true"><i></i></span>
          <span class="tl-score">${score}</span>
          <span class="tl-sig">${esc(data.signal || "")}</span>
          <button class="tl-x" title="Hide">×</button>
        </div>
        <div class="tl-panel" hidden>
          <div class="tl-head">
            <div>
              <div class="tl-h-sym">${esc(data.symbol)}</div>
              <div class="tl-h-name">${esc(data.name || "")}</div>
            </div>
            <div class="tl-h-score tl-${tone}">${score}<span>/100</span></div>
          </div>
          ${data.reason ? `<p class="tl-why">${esc(data.reason)}</p>` : ""}
          <div class="tl-factors">${factors}</div>
          <div class="tl-actions">
            <a class="tl-btn" href="${esc(data.url)}" target="_blank" rel="noopener">Full breakdown</a>
            <a class="tl-btn tl-btn-ghost" href="${esc(data.scorecardUrl)}" target="_blank" rel="noopener">Public record</a>
          </div>
          <p class="tl-fine">Descriptive six-factor scoring — not investment advice. Every daily top-10 pick is logged publicly, including the ones that lose.</p>
        </div>`;
    }

    root.appendChild(wrap);

    const x = wrap.querySelector(".tl-x");
    if (x) {
      x.addEventListener("click", (e) => {
        e.stopPropagation();
        dismissed = true;
        wrap.remove();
      });
    }
    const pill = wrap.querySelector(".tl-pill");
    const panel = wrap.querySelector(".tl-panel");
    if (pill && panel) {
      const toggle = () => {
        const open = !panel.hasAttribute("hidden");
        if (open) panel.setAttribute("hidden", "");
        else panel.removeAttribute("hidden");
        pill.setAttribute("aria-expanded", String(!open));
      };
      pill.addEventListener("click", toggle);
      pill.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      });
    }
  }

  function clear() {
    if (root) {
      const w = root.querySelector(".tl-wrap");
      if (w) w.remove();
    }
    current = null;
  }

  async function sync() {
    if (dismissed) return;
    const symbol = detectSymbol();
    if (!symbol) { clear(); return; }
    if (symbol === current) return;
    current = symbol;

    render("loading", null, symbol);
    let res;
    try {
      res = await chrome.runtime.sendMessage({ type: "TAPELINE_LOOKUP", symbol });
    } catch (_) {
      res = { ok: false, reason: "unavailable" };
    }
    if (current !== symbol) return;           // navigated away mid-flight
    if (res && res.ok) render("ok", res.data, symbol);
    else render(res && res.reason === "not_covered" ? "missing" : "error", null, symbol);
  }

  // Soft navigation: SPA hosts change the URL without a reload.
  let lastHref = location.href;
  function watch() {
    if (location.href !== lastHref) {
      lastHref = location.href;
      dismissed = false;
      sync();
    }
  }
  if (isSpaHost()) {
    setInterval(watch, 700);
    window.addEventListener("popstate", watch);
  }

  sync();

})();
