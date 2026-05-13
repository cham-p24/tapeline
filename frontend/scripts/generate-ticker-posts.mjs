#!/usr/bin/env node
/**
 * Generates frontend/app/blog/ticker/tickers.ts — the manifest of 50
 * per-ticker SEO posts at /blog/ticker/{symbol}. Each post targets queries
 * like "{TICKER} stock score 2026" and "is {TICKER} a buy" — long-tail
 * commercial-investigation traffic that compounds passively over months.
 *
 * Run:  node scripts/generate-ticker-posts.mjs
 *
 * Edit the TICKERS array below to add/remove/reorder posts. Reruns
 * overwrite tickers.ts in place; commit the result.
 *
 * The single page template lives at app/blog/ticker/[symbol]/page.tsx and
 * pulls live score + factor breakdown from /api/ticker/{symbol} at request
 * time (with Next.js revalidate caching). The framing, intro, and risks
 * paragraph are shared across all 50 posts and live in the template — only
 * the per-ticker name + sector context lives in tickers.ts.
 */
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

// Top 50 most-searched US tickers as of 2026. Mix of mega-cap tech, mega-cap
// non-tech, retail-favourite mid-caps, ETFs, crypto-adjacent, and meme-residual.
// Re-sort by Google Trends search volume in 2026-H2 if posts underperform.
const TICKERS = [
  // Mega-cap tech (10)
  { symbol: "AAPL",  name: "Apple Inc.",                       sector: "Technology", context: "consumer electronics, services, and silicon design" },
  { symbol: "NVDA",  name: "NVIDIA Corp.",                     sector: "Technology", context: "GPUs, AI accelerators, and data-center silicon" },
  { symbol: "MSFT",  name: "Microsoft Corp.",                  sector: "Technology", context: "cloud (Azure), enterprise software, and AI infrastructure" },
  { symbol: "GOOGL", name: "Alphabet Inc.",                    sector: "Communication Services", context: "search, advertising, cloud, and AI" },
  { symbol: "AMZN",  name: "Amazon.com Inc.",                  sector: "Consumer Discretionary", context: "e-commerce, AWS cloud, and advertising" },
  { symbol: "META",  name: "Meta Platforms Inc.",              sector: "Communication Services", context: "social platforms, advertising, and AI/AR R&D" },
  { symbol: "TSLA",  name: "Tesla, Inc.",                      sector: "Consumer Discretionary", context: "EVs, energy storage, and autonomy software" },
  { symbol: "AVGO",  name: "Broadcom Inc.",                    sector: "Technology", context: "custom AI silicon and networking semis" },
  { symbol: "ORCL",  name: "Oracle Corp.",                     sector: "Technology", context: "database, ERP, and cloud infrastructure" },
  { symbol: "AMD",   name: "Advanced Micro Devices, Inc.",     sector: "Technology", context: "CPUs, GPUs, and accelerators for data-center and consumer" },

  // Mega-cap non-tech (10)
  { symbol: "BRK.B", name: "Berkshire Hathaway Inc. Class B",  sector: "Financials", context: "Warren Buffett's diversified holding company" },
  { symbol: "JPM",   name: "JPMorgan Chase & Co.",             sector: "Financials", context: "the largest US bank by assets" },
  { symbol: "V",     name: "Visa Inc.",                        sector: "Financials", context: "global payment-network operator" },
  { symbol: "JNJ",   name: "Johnson & Johnson",                sector: "Health Care", context: "pharmaceuticals and medical devices" },
  { symbol: "WMT",   name: "Walmart Inc.",                     sector: "Consumer Staples", context: "the largest US retailer by revenue" },
  { symbol: "UNH",   name: "UnitedHealth Group Inc.",          sector: "Health Care", context: "managed care and health-services operator" },
  { symbol: "LLY",   name: "Eli Lilly and Company",            sector: "Health Care", context: "diabetes, obesity (GLP-1), and oncology drugs" },
  { symbol: "PG",    name: "The Procter & Gamble Company",     sector: "Consumer Staples", context: "consumer-staples brand portfolio" },
  { symbol: "MA",    name: "Mastercard Inc.",                  sector: "Financials", context: "global payment-network operator" },
  { symbol: "HD",    name: "The Home Depot, Inc.",             sector: "Consumer Discretionary", context: "the largest US home-improvement retailer" },

  // High-search blue chips (10)
  { symbol: "BAC",   name: "Bank of America Corp.",            sector: "Financials", context: "consumer banking, wealth management, and capital markets" },
  { symbol: "XOM",   name: "Exxon Mobil Corp.",                sector: "Energy", context: "integrated oil-and-gas major" },
  { symbol: "CVX",   name: "Chevron Corp.",                    sector: "Energy", context: "integrated oil-and-gas major" },
  { symbol: "KO",    name: "The Coca-Cola Company",            sector: "Consumer Staples", context: "global beverage brand portfolio" },
  { symbol: "PEP",   name: "PepsiCo, Inc.",                    sector: "Consumer Staples", context: "beverages and snacks (Frito-Lay, Quaker)" },
  { symbol: "PFE",   name: "Pfizer Inc.",                      sector: "Health Care", context: "pharmaceuticals and post-pandemic pipeline" },
  { symbol: "NFLX",  name: "Netflix, Inc.",                    sector: "Communication Services", context: "streaming video and original content" },
  { symbol: "DIS",   name: "The Walt Disney Company",          sector: "Communication Services", context: "media, theme parks, and streaming (Disney+)" },
  { symbol: "CRM",   name: "Salesforce, Inc.",                 sector: "Technology", context: "enterprise CRM and adjacent SaaS" },
  { symbol: "ADBE",  name: "Adobe Inc.",                       sector: "Technology", context: "creative software and digital-experience platforms" },

  // Mid-cap high-search (10)
  { symbol: "PLTR",  name: "Palantir Technologies Inc.",       sector: "Technology", context: "government and enterprise data-analytics software" },
  { symbol: "COIN",  name: "Coinbase Global, Inc.",            sector: "Financials", context: "US-listed crypto exchange and custody" },
  { symbol: "SOFI",  name: "SoFi Technologies, Inc.",          sector: "Financials", context: "digital-first personal finance and banking" },
  { symbol: "NET",   name: "Cloudflare, Inc.",                 sector: "Technology", context: "edge network, CDN, and zero-trust security" },
  { symbol: "F",     name: "Ford Motor Company",               sector: "Consumer Discretionary", context: "legacy auto OEM with an EV transition" },
  { symbol: "GM",    name: "General Motors Company",           sector: "Consumer Discretionary", context: "legacy auto OEM with an EV and autonomy ambition" },
  { symbol: "BA",    name: "The Boeing Company",               sector: "Industrials", context: "commercial aerospace and defense" },
  { symbol: "T",     name: "AT&T Inc.",                        sector: "Communication Services", context: "wireless and broadband telecom" },
  { symbol: "INTC",  name: "Intel Corp.",                      sector: "Technology", context: "x86 CPUs and a foundry-business turnaround" },
  { symbol: "GE",    name: "GE Aerospace",                     sector: "Industrials", context: "commercial and defense aerospace engines" },

  // Crypto-adjacent + meme-residual (5)
  { symbol: "MSTR",  name: "Strategy Inc. (MicroStrategy)",    sector: "Technology", context: "enterprise software issuer leveraged to Bitcoin treasury" },
  { symbol: "MARA",  name: "Marathon Digital Holdings, Inc.",  sector: "Financials", context: "publicly-traded Bitcoin miner" },
  { symbol: "RIOT",  name: "Riot Platforms, Inc.",             sector: "Financials", context: "publicly-traded Bitcoin miner" },
  { symbol: "GME",   name: "GameStop Corp.",                   sector: "Consumer Discretionary", context: "video-game retailer with a meme-stock history" },
  { symbol: "AMC",   name: "AMC Entertainment Holdings, Inc.", sector: "Communication Services", context: "movie-theater chain with a meme-stock history" },

  // ETFs (5)
  { symbol: "SPY",   name: "SPDR S&P 500 ETF Trust",           sector: "ETF", context: "the canonical S&P 500 index tracker" },
  { symbol: "QQQ",   name: "Invesco QQQ Trust",                sector: "ETF", context: "Nasdaq-100 index tracker, tech-heavy" },
  { symbol: "VTI",   name: "Vanguard Total Stock Market ETF",  sector: "ETF", context: "total-US-market index tracker" },
  { symbol: "GLD",   name: "SPDR Gold Shares",                 sector: "Commodities", context: "physical-gold ETF" },
  { symbol: "XLE",   name: "Energy Select Sector SPDR Fund",   sector: "Energy", context: "S&P 500 energy-sector ETF" },
];

// Sanity check — bail loudly if the list drifts off 50.
if (TICKERS.length !== 50) {
  console.error(`Expected 50 tickers, got ${TICKERS.length}. Edit and re-run.`);
  process.exit(1);
}

// Validate unique symbols — catches typos that would land two posts on one URL.
const seen = new Set();
for (const t of TICKERS) {
  if (seen.has(t.symbol)) {
    console.error(`Duplicate symbol in TICKERS: ${t.symbol}`);
    process.exit(1);
  }
  seen.add(t.symbol);
}

// Emit a TS file. We keep the symbol as a URL-segment-safe ID (uppercase,
// dot kept verbatim — Next.js handles dots in dynamic segments fine and
// it keeps the canonical URL aligned with /t/BRK.B style elsewhere).
const header = `/**
 * Generated by scripts/generate-ticker-posts.mjs — DO NOT EDIT MANUALLY.
 *
 * Manifest of per-ticker SEO posts at /blog/ticker/{symbol}. The actual
 * post template (intro, score block, factor breakdown, risks, CTA) is one
 * shared file at app/blog/ticker/[symbol]/page.tsx — only the per-ticker
 * name + sector context lives here so we don't duplicate framing 50 times.
 *
 * To add a post: edit scripts/generate-ticker-posts.mjs and re-run.
 */

export type TickerPost = {
  symbol: string;
  name: string;
  sector: string;
  /** One-line context used in the H1 area; do not exceed ~80 chars. */
  context: string;
};

export const TICKERS: TickerPost[] = ${JSON.stringify(TICKERS, null, 2)};

export function findTicker(symbol: string): TickerPost | null {
  const target = symbol.toUpperCase();
  return TICKERS.find((t) => t.symbol === target) ?? null;
}
`;

const here = dirname(fileURLToPath(import.meta.url));
const out = resolve(here, "..", "app", "blog", "ticker", "tickers.ts");
writeFileSync(out, header);
console.log(`Wrote ${TICKERS.length} tickers to ${out}`);
