/**
 * Ticker detection.
 *
 * Two layers, because "works on every trading platform" and "does not ask for
 * permission to read every website" pull in opposite directions.
 *
 *   1. KNOWN — a per-host rule for the public research sites we ship enabled.
 *      Precise, so we never guess a ticker out of an article slug.
 *   2. GENERIC — the URL shapes the whole industry converged on (/quote/NVDA,
 *      /symbol/NVDA, ?symbol=NVDA, /stocks/NVDA...). Only ever applied to a
 *      host the USER has explicitly enabled from the popup, which is what
 *      makes brokerage and long-tail coverage possible without demanding
 *      access to the entire web up front.
 *
 * Detection reads `location` only — never the host's DOM content. That means
 * we learn WHICH ticker is on screen and nothing else: no prices, no holdings,
 * no balances. It also survives the host redesigning its markup, which is the
 * usual reason finance extensions rot.
 */

const TAPELINE_SITES = [
  // ── aggregators / quote pages ───────────────────────────────────────────
  { host: /(^|\.)finance\.yahoo\.com$/, url: [/\/quote\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/] },
  {
    host: /(^|\.)tradingview\.com$/,
    url: [
      /\/symbols\/(?:[A-Z]{2,8}-)?([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/,
      /[?&]symbol=(?:[A-Z]{2,8}(?:%3A|:))?([A-Za-z0-9.\-]{1,12})/i,
    ],
    spa: true,
  },
  { host: /(^|\.)google\.com$/, url: [/\/finance\/quote\/([A-Za-z0-9.\-]{1,12})(?::|[/?#]|$)/], spa: true },
  { host: /(^|\.)marketwatch\.com$/, url: [/\/investing\/stock\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i] },
  { host: /(^|\.)seekingalpha\.com$/, url: [/\/symbol\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/], spa: true },
  { host: /(^|\.)stocktwits\.com$/, url: [/\/symbol\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/], spa: true },
  { host: /(^|\.)finviz\.com$/, url: [/\/quote\.ashx\?(?:.*&)?t=([A-Za-z0-9.\-]{1,12})/i] },
  { host: /(^|\.)barchart\.com$/, url: [/\/stocks\/quotes\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i] },
  { host: /(^|\.)cnbc\.com$/, url: [/\/quotes\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/] },
  { host: /(^|\.)nasdaq\.com$/, url: [/\/market-activity\/stocks\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i] },

  // ── research / data ─────────────────────────────────────────────────────
  { host: /(^|\.)investing\.com$/, url: [/\/equities\/([A-Za-z0-9.\-]{1,24})(?:[/?#]|$)/i] },
  { host: /(^|\.)zacks\.com$/, url: [/\/stock\/quote\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i] },
  { host: /(^|\.)morningstar\.com$/, url: [/\/stocks\/[a-z]{4}\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i] },
  { host: /(^|\.)tipranks\.com$/, url: [/\/stocks\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i], spa: true },
  { host: /(^|\.)stockanalysis\.com$/, url: [/\/stocks\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i] },
  { host: /(^|\.)simplywall\.st$/, url: [/\/stocks\/[^/]+\/[^/]+\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i], spa: true },
  { host: /(^|\.)stockcharts\.com$/, url: [/[?&](?:s|symbol)=([A-Za-z0-9.\-]{1,12})/i] },
  { host: /(^|\.)benzinga\.com$/, url: [/\/quote\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i] },
  { host: /(^|\.)fool\.com$/, url: [/\/quote\/[a-z]+\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i] },
  { host: /(^|\.)wsj\.com$/, url: [/\/market-data\/quotes\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i] },
  { host: /(^|\.)reuters\.com$/, url: [/\/markets\/companies\/([A-Za-z0-9.\-]{1,16})(?:[/?#]|$)/i] },

  // ── brokers: none ship enabled. robinhood.com was dropped from the manifest
  //    in PR #526, so this rule never runs at install time. The entry stays so
  //    that once a user DOES grant the origin, we parse their URLs with a rule
  //    written for Robinhood rather than the loose generic patterns.
  //
  //    `optIn` is what keeps the two ideas apart: "we have a rule for this
  //    host" and "this host works out of the box" are different questions, and
  //    conflating them cost us the Enable button here — isKnownHost was true,
  //    so popup.js never offered the grant, and the extension was a silent
  //    dead end on Robinhood with no way in from the UI. Every broker is
  //    opt-in rather than us asking for brokerage access at install. ────────
  {
    host: /(^|\.)robinhood\.com$/,
    url: [/\/stocks\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/],
    spa: true,
    optIn: true,
  },
];

/**
 * URL shapes shared across the industry. Applied ONLY to user-enabled hosts —
 * ordered most to least specific so an early match wins.
 */
const GENERIC_PATTERNS = [
  /\/(?:quote|quotes|symbol|symbols|ticker|tickers)\/(?:[A-Z]{2,8}[-:])?([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i,
  /\/(?:stock|stocks|equities|equity|shares|security)\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i,
  /\/(?:trade|trading|chart|charts|research|company)\/(?:[A-Z]{2,8}[-:])?([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i,
  /[?&](?:symbol|ticker|sym|s|t|q)=(?:[A-Z]{2,8}(?:%3A|:))?([A-Za-z0-9.\-]{1,12})(?:&|$)/i,
];

/**
 * Route words that occupy the symbol slot on some hosts. Without this the
 * generic patterns happily "detect" /quote/news as the ticker NEWS.
 */
const NOT_SYMBOLS = new Set([
  "NEWS", "CHART", "CHARTS", "QUOTE", "QUOTES", "MARKETS", "MARKET", "SEARCH",
  "HOME", "ABOUT", "LOGIN", "SIGNIN", "SETTINGS", "ACCOUNT", "PORTFOLIO",
  "WATCHLIST", "SUMMARY", "PROFILE", "HISTORY", "OPTIONS", "INDEX", "LISTS",
  "TRENDING", "MOVERS", "SCREENER", "EARNINGS", "DIVIDEND", "ANALYSIS", "ALL",
  "DASHBOARD", "OVERVIEW", "DETAIL", "DETAILS", "LIST", "VIEW", "MAIN",
  "NEW", "TOP", "US", "USD", "FAQ", "HELP", "TERMS", "LEGAL", "BLOG",
]);

/** Uppercase, strip an unambiguous exchange prefix, reject non-symbols. */
function normalizeSymbol(raw) {
  if (!raw) return null;
  let s = decodeURIComponent(raw).toUpperCase().trim();
  // Strip an exchange prefix only when the delimiter is unambiguous. ":" always
  // separates exchange from symbol ("NASDAQ:NVDA"); "-" does NOT — Yahoo writes
  // share classes as "BRK-B", and splitting on it turned Berkshire into "B".
  const colon = s.split(":");
  if (colon.length > 1 && /^[A-Z]{2,8}$/.test(colon[0])) {
    s = colon[colon.length - 1];
  }
  // Some platforms suffix a market code (moomoo's "AAPL-US", "9988-HK"). Strip a
  // TWO-letter trailing code, never a single letter — "BRK-B" is a share class
  // and must survive intact, which is why this is not a blanket split on "-".
  const dash = s.split("-");
  if (dash.length === 2 && /^[A-Z]{2}$/.test(dash[1]) && dash[0].length >= 2) {
    s = dash[0];
  }
  // The API accepts both "BRK.B" and "BRK-B", so pass the host's own form through.
  if (!/^[A-Z][A-Z0-9.\-]{0,9}$/.test(s)) return null;
  if (NOT_SYMBOLS.has(s)) return null;
  return s;
}

function _match(target, patterns) {
  for (const re of patterns) {
    const m = target.match(re);
    if (m && m[1]) {
      const sym = normalizeSymbol(m[1]);
      if (sym) return sym;
    }
  }
  return null;
}

function _rule(hostname) {
  return TAPELINE_SITES.find((r) => r.host.test(hostname));
}

/**
 * Current ticker for this page, or null.
 *
 * `allowGeneric` is passed true only for hosts the user enabled themselves —
 * the generic patterns are deliberately loose, so they must never run on a
 * site the user did not opt into.
 */
function detectSymbol(loc = window.location, allowGeneric = false) {
  // Include the hash: several brokers route entirely in the fragment
  // (Schwab's /app/research/#/stocks/TSLA), so pathname alone finds nothing.
  const target = loc.pathname + loc.search + (loc.hash || "");
  const rule = _rule(loc.hostname);
  if (rule) {
    const known = _match(target, rule.url);
    if (known) return known;
    // A known host that didn't match its own rule is an article or a listing
    // page, not a quote page. Don't fall through to guessing.
    return null;
  }
  return allowGeneric ? _match(target, GENERIC_PATTERNS) : null;
}

/** True if this host soft-navigates and needs a URL watcher. */
function isSpaHost(loc = window.location) {
  const rule = _rule(loc.hostname);
  // User-enabled hosts get the watcher too: most brokers and modern trading
  // platforms are single-page apps, and we can't know which in advance.
  return rule ? Boolean(rule.spa) : true;
}

/**
 * Is this host covered out of the box? Drives the popup's enable button.
 *
 * Deliberately NOT "do we have a rule for it" — an `optIn` rule exists to parse
 * URLs once the user grants the origin, and is not shipped in the manifest.
 * Reporting those as known suppresses the very button that grants them.
 */
function isKnownHost(hostname) {
  const rule = _rule(hostname);
  return Boolean(rule) && !rule.optIn;
}

if (typeof module !== "undefined") {
  module.exports = {
    detectSymbol,
    normalizeSymbol,
    isSpaHost,
    isKnownHost,
    TAPELINE_SITES,
    GENERIC_PATTERNS,
  };
}
