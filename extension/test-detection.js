/**
 * Detection tests — `node extension/test-detection.js`.
 *
 * These rules are the most likely thing to rot: every host can change its URL
 * shape, and the failure is silent (no pill, no error). Run this when adding a
 * site, and when a user reports the pill missing on one.
 *
 * The negative cases matter more than the positive ones. The generic patterns
 * are deliberately loose so they can cover brokers we've never seen, which
 * means the guard rails — route words, article slugs, known-host-no-fallthrough
 * — are what keep them from inventing tickers.
 */
const { detectSymbol, isKnownHost } = require("./sites.js");

const mk = (u) => {
  const x = new URL(u);
  return { hostname: x.hostname, pathname: x.pathname, search: x.search, hash: x.hash };
};

// [url, expected, allowGeneric]
const CASES = [
  // known hosts
  ["https://finance.yahoo.com/quote/NVDA", "NVDA", false],
  ["https://finance.yahoo.com/quote/BRK-B/news/", "BRK-B", false],
  ["https://www.tradingview.com/symbols/NASDAQ-NVDA/", "NVDA", false],
  ["https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL", "AAPL", false],
  ["https://www.google.com/finance/quote/MSFT:NASDAQ", "MSFT", false],
  ["https://www.marketwatch.com/investing/stock/tsla", "TSLA", false],
  ["https://seekingalpha.com/symbol/AMD", "AMD", false],
  ["https://stocktwits.com/symbol/GME", "GME", false],
  ["https://finviz.com/quote.ashx?t=META&p=d", "META", false],
  ["https://www.barchart.com/stocks/quotes/AMZN", "AMZN", false],
  ["https://www.cnbc.com/quotes/GOOGL", "GOOGL", false],
  ["https://robinhood.com/stocks/PLTR", "PLTR", false],
  ["https://www.nasdaq.com/market-activity/stocks/intc", "INTC", false],
  ["https://www.zacks.com/stock/quote/CRM", "CRM", false],
  ["https://stockanalysis.com/stocks/uber/", "UBER", false],
  ["https://www.tipranks.com/stocks/sofi", "SOFI", false],
  ["https://www.wsj.com/market-data/quotes/KO", "KO", false],
  ["https://www.benzinga.com/quote/NFLX", "NFLX", false],
  ["https://stockcharts.com/h-sc/ui?s=DIS", "DIS", false],

  // user-enabled hosts via the generic patterns — brokers and long tail
  ["https://www.webull.com/quote/nasdaq-nvda", "NVDA", true],
  ["https://digital.fidelity.com/prgw/digital/research/quote/dashboard?symbol=AAPL", "AAPL", true],
  ["https://client.schwab.com/app/research/#/stocks/TSLA", "TSLA", true],
  ["https://us.etrade.com/etx/mkt/quotes/AMD", "AMD", true],
  ["https://trade.tastyworks.com/symbol/SPY", "SPY", true],
  ["https://www.moomoo.com/stock/AAPL-US", "AAPL", true],
  ["https://public.com/stocks/hood", "HOOD", true],
  ["https://someneworder.example.com/trade/COIN", "COIN", true],

  // negatives — the guard rails
  ["https://finance.yahoo.com/news/some-article", null, false],
  ["https://www.tradingview.com/chart/", null, false],
  ["https://example.com/quote/NVDA", null, false],          // generic OFF by default
  ["https://randomblog.example.com/stocks/news", null, true], // route word
  ["https://randomblog.example.com/quote/search", null, true],
  ["https://shop.example.com/quote/watchlist", null, true],
  ["https://finance.yahoo.com/lookup/all", null, false],     // known host, no fallthrough
];

let pass = 0;
for (const [url, want, generic] of CASES) {
  const got = detectSymbol(mk(url), generic);
  const ok = got === want;
  if (ok) pass++;
  console.log(
    `${ok ? "PASS" : "FAIL"}  ${String(got).padEnd(7)}${ok ? "" : `(want ${want}) `}${url}`
  );
}

// isKnownHost drives whether the popup offers "enable on this site".
const HOST_CASES = [
  ["finance.yahoo.com", true],
  ["www.tradingview.com", true],
  ["client.schwab.com", false],
  ["example.com", false],
  // Robinhood has a parsing rule but is NOT in the manifest, so it must report
  // as unknown or the popup withholds "Enable on this site" and the extension
  // is a dead end there with no route in. Regression guard for that exact bug.
  ["robinhood.com", false],
];
for (const [host, want] of HOST_CASES) {
  const got = isKnownHost(host);
  const ok = got === want;
  if (ok) pass++;
  console.log(`${ok ? "PASS" : "FAIL"}  isKnownHost(${host}) = ${got}`);
}

const total = CASES.length + HOST_CASES.length;
console.log(`\n${pass}/${total} passed`);
if (pass !== total) process.exit(1);
