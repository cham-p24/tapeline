/**
 * Detection tests — `node extension/test-detection.js`.
 *
 * These are the rules most likely to rot: every host here can change its URL
 * shape, and the failure is silent (no badge, no error). Run this when adding a
 * site, and when a user reports the pill missing on one.
 */
const { detectSymbol } = require('./sites.js');
const mk = (u) => { const x = new URL(u); return { hostname: x.hostname, pathname: x.pathname, search: x.search }; };
const cases = [
  ["https://finance.yahoo.com/quote/NVDA", "NVDA"],
  ["https://finance.yahoo.com/quote/BRK-B/news/", "BRK.B|BRK-B"],
  ["https://www.tradingview.com/symbols/NASDAQ-NVDA/", "NVDA"],
  ["https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL", "AAPL"],
  ["https://www.google.com/finance/quote/MSFT:NASDAQ", "MSFT"],
  ["https://www.marketwatch.com/investing/stock/tsla", "TSLA"],
  ["https://seekingalpha.com/symbol/AMD", "AMD"],
  ["https://stocktwits.com/symbol/GME", "GME"],
  ["https://finviz.com/quote.ashx?t=META&p=d", "META"],
  ["https://www.barchart.com/stocks/quotes/AMZN", "AMZN"],
  ["https://www.cnbc.com/quotes/GOOGL", "GOOGL"],
  ["https://robinhood.com/stocks/PLTR", "PLTR"],
  ["https://www.nasdaq.com/market-activity/stocks/intc", "INTC"],
  ["https://finance.yahoo.com/news/some-article", "null"],
  ["https://www.tradingview.com/chart/", "null"],
  ["https://example.com/quote/NVDA", "null"],
];
let pass=0;
for (const [u, want] of cases) {
  const got = String(detectSymbol(mk(u)));
  const ok = want.split("|").includes(got);
  if (ok) pass++;
  console.log(`${ok?"PASS":"FAIL"}  ${got.padEnd(7)} ${ok?"":"(want "+want+") "}${u}`);
}
console.log(`\n${pass}/${cases.length} passed`);
