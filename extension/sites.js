/**
 * Ticker detection, one rule per host.
 *
 * Every supported site puts the symbol in the URL, so detection is a regex over
 * location rather than a DOM scrape. That matters for three reasons: it survives
 * the host's markup changing under us (the usual reason finance extensions rot),
 * it costs nothing on page load, and it means we never read the host's data —
 * we only learn WHICH ticker the user is looking at, then show our own numbers
 * for it. `dom` is a last-resort fallback for hosts that soft-navigate before
 * the URL settles.
 *
 * Symbols are normalised to Tapeline's convention: uppercase, exchange prefix
 * stripped (TradingView's "NASDAQ-NVDA"), class suffixes preserved (BRK.B).
 */

const TAPELINE_SITES = [
  {
    host: /(^|\.)finance\.yahoo\.com$/,
    url: [/\/quote\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/],
  },
  {
    host: /(^|\.)tradingview\.com$/,
    // /symbols/NASDAQ-NVDA/  ·  /chart/?symbol=NASDAQ%3ANVDA
    url: [
      /\/symbols\/(?:[A-Z]{2,8}-)?([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/,
      /[?&]symbol=(?:[A-Z]{2,8}(?:%3A|:))?([A-Za-z0-9.\-]{1,12})/i,
    ],
    spa: true,
  },
  {
    host: /(^|\.)google\.com$/,
    // /finance/quote/NVDA:NASDAQ
    url: [/\/finance\/quote\/([A-Za-z0-9.\-]{1,12})(?::|[/?#]|$)/],
    spa: true,
  },
  {
    host: /(^|\.)marketwatch\.com$/,
    url: [/\/investing\/stock\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i],
  },
  {
    host: /(^|\.)seekingalpha\.com$/,
    url: [/\/symbol\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/],
    spa: true,
  },
  {
    host: /(^|\.)stocktwits\.com$/,
    url: [/\/symbol\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/],
    spa: true,
  },
  {
    host: /(^|\.)finviz\.com$/,
    url: [/\/quote\.ashx\?(?:.*&)?t=([A-Za-z0-9.\-]{1,12})/i],
  },
  {
    host: /(^|\.)barchart\.com$/,
    url: [/\/stocks\/quotes\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i],
  },
  {
    host: /(^|\.)cnbc\.com$/,
    url: [/\/quotes\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/],
  },
  {
    host: /(^|\.)robinhood\.com$/,
    url: [/\/stocks\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/],
    spa: true,
  },
  {
    host: /(^|\.)nasdaq\.com$/,
    url: [/\/market-activity\/stocks\/([A-Za-z0-9.\-]{1,12})(?:[/?#]|$)/i],
  },
];

/** Uppercase, strip an exchange prefix, reject obvious non-symbols. */
function normalizeSymbol(raw) {
  if (!raw) return null;
  let s = decodeURIComponent(raw).toUpperCase().trim();
  // Strip an exchange prefix only when the delimiter is unambiguous. ":" always
  // separates exchange from symbol ("NASDAQ:NVDA"); "-" does NOT — Yahoo writes
  // share classes as "BRK-B", and splitting on it turned Berkshire into "B".
  // TradingView's "NASDAQ-NVDA" form is stripped by that host's url rule instead.
  const colon = s.split(":");
  if (colon.length > 1 && /^[A-Z]{2,8}$/.test(colon[0])) {
    s = colon[colon.length - 1];
  }
  // The API accepts both "BRK.B" and "BRK-B", so pass the host's own form through.
  if (!/^[A-Z][A-Z0-9.\-]{0,9}$/.test(s)) return null;
  // Route words that share the symbol slot on some hosts.
  if (["NEWS", "CHART", "QUOTE", "MARKETS", "SEARCH", "HOME"].includes(s)) return null;
  return s;
}

/** Current ticker for this page, or null. */
function detectSymbol(loc = window.location) {
  const rule = TAPELINE_SITES.find((r) => r.host.test(loc.hostname));
  if (!rule) return null;
  const target = loc.pathname + loc.search;
  for (const re of rule.url) {
    const m = target.match(re);
    if (m && m[1]) {
      const sym = normalizeSymbol(m[1]);
      if (sym) return sym;
    }
  }
  return null;
}

/** True if this host soft-navigates and needs a URL watcher. */
function isSpaHost(loc = window.location) {
  const rule = TAPELINE_SITES.find((r) => r.host.test(loc.hostname));
  return Boolean(rule && rule.spa);
}

if (typeof module !== "undefined") {
  module.exports = { detectSymbol, normalizeSymbol, isSpaHost, TAPELINE_SITES };
}
