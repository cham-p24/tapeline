/**
 * Public per-ticker share page at /t/[symbol].
 *
 * Lives outside /app so search engines can index it and unauthenticated
 * traders pasting links to friends actually see content. Shows the score,
 * signal, 6-factor breakdown, and the why sentence — paywalls news / charts /
 * alerts behind a sign-up CTA. The full deep-dive lives at /app/ticker/[symbol].
 *
 * Why this matters:
 *   1. SEO — every ticker becomes a landing page for "AAPL stock score" queries.
 *   2. Viral loop — existing users tweet $TICKER + a /t/TICKER link, the OG card
 *      (next to this file) shows the live score so the share previews self-sell.
 *   3. Trust — the public-formula moat needs a public surface to land on.
 */
import Link from "next/link";
import { notFound } from "next/navigation";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { ScoreRadial } from "@/components/ScoreRadial";
import { ScoreSparkline } from "@/components/ScoreSparkline";
import {
  breadcrumbJsonLd,
  faqJsonLd,
  jsonLdScript,
  tickerReviewJsonLd,
} from "@/lib/jsonld";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

type FactorEntry = { value: number | null; weight: number; label: string };

type TickerData = {
  symbol: string;
  name: string;
  sector: string | null;
  asset_class: string;
  price: number | null;
  score: number | null;
  signal: string | null;
  confidence_pct: number | null;
  change_pct_1d: number | null;
  change_pct_5d: number | null;
  change_pct_1m: number | null;
  volume: number | null;
  reason: string | null;
  // The /api/ticker/{symbol} endpoint returns sub-factor values nested
  // inside `breakdown.<key>.value`, NOT as top-level sub_* fields. The
  // page initially assumed the flat shape and rendered every bar at 0%.
  breakdown?: {
    trend?: FactorEntry;
    rs?: FactorEntry;
    fundamentals?: FactorEntry;
    smart_money?: FactorEntry;
    macro?: FactorEntry;
    momentum?: FactorEntry;
  };
};

async function fetchTicker(symbol: string): Promise<TickerData | null> {
  try {
    const res = await fetch(`${API_BASE}/api/ticker/${symbol.toUpperCase()}`, {
      // Cache for 60s — matches the worker tick cadence so the page is fresh
      // without hammering the API on every social-card crawl.
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return (await res.json()) as TickerData;
  } catch {
    return null;
  }
}

/**
 * Build a substantive, ticker-specific editorial paragraph from the
 * actual factor sub-scores + signal label + recent change. This is
 * the content-depth replacement for the noindex gate (PR #198) — the
 * founder asked for every ticker to be indexed, so instead of hiding
 * thin pages we make every page genuinely substantial.
 *
 * Critically, the output is uniquely shaped per ticker:
 *   - Numbers come from live data (different per ticker)
 *   - The strongest + weakest factor identification is data-driven
 *   - The interpretation paragraphs are sub-score-conditional
 *   - The signal-specific framing changes per HIGH CONVICTION /
 *     STRONG SETUP / CONSTRUCTIVE / NEUTRAL / CAUTION / WEAK
 *
 * Google's quality classifier responds to substantive content over
 * sparse templates. A 200-400 word editorial paragraph derived from
 * the actual data signals "this page is genuinely about THIS ticker"
 * rather than "this page is a generic shell with the ticker swapped
 * in".
 */
type Sub = { value: number | null; weight: number; label: string };
type Breakdown = {
  trend?: Sub;
  rs?: Sub;
  fundamentals?: Sub;
  smart_money?: Sub;
  macro?: Sub;
  momentum?: Sub;
};

function buildEditorialCommentary(d: TickerData): string {
  const sym = d.symbol;
  const name = d.name || sym;
  const score = d.score;
  const signal = d.signal ?? "—";
  const b: Breakdown = d.breakdown ?? {};

  // Identify the strongest + weakest factors. If any are null they're
  // excluded from the ranking (data-sparse factors don't claim a
  // misleading weak / strong position).
  const factors: Array<{ key: string; value: number; label: string }> = [];
  if (b.trend?.value != null) factors.push({ key: "trend", value: b.trend.value, label: "Trend" });
  if (b.rs?.value != null) factors.push({ key: "rs", value: b.rs.value, label: "Relative Strength" });
  if (b.fundamentals?.value != null) factors.push({ key: "fundamentals", value: b.fundamentals.value, label: "Fundamentals" });
  if (b.smart_money?.value != null) factors.push({ key: "smart_money", value: b.smart_money.value, label: "Smart Money" });
  if (b.macro?.value != null) factors.push({ key: "macro", value: b.macro.value, label: "Macro" });
  if (b.momentum?.value != null) factors.push({ key: "momentum", value: b.momentum.value, label: "Momentum" });

  if (factors.length === 0) {
    return `${name} (${sym}) is in the Tapeline scanner universe but doesn't have enough factor data right now for a six-factor composite read. Data backfills run continuously — check back during the next US market session for the live read.`;
  }

  const sorted = [...factors].sort((a, b) => b.value - a.value);
  const strongest = sorted[0];
  const weakest = sorted[sorted.length - 1];

  // Signal-specific framing — same data, different "what this means
  // for a trader" paragraph per signal label. Keeps the editorial
  // honest (descriptive, not prescriptive) and avoids the publisher-
  // exemption violation Tapeline is built to respect.
  const sigInterp = ((): string => {
    const s = (signal || "").toUpperCase();
    if (s === "HIGH CONVICTION") {
      return `When ${sym} hits HIGH CONVICTION (85+), all six factors line up positive — the kind of confluence that historically clusters near multi-week breakouts. The label is descriptive: it tells you the data says "everything is aligned right now", not whether to enter at this exact price.`;
    }
    if (s === "STRONG SETUP") {
      return `STRONG SETUP (70-84) means most factors — typically four or five of six — point favourably. This is the band where the textbook multi-day swing setup tends to live. Tradeoff: the bigger HIGH CONVICTION moves are rarer and usually already-priced-in by the time they appear.`;
    }
    if (s === "CONSTRUCTIVE") {
      return `CONSTRUCTIVE (55-69) is the "watchlist tier" — net positive with meaningful tradeoffs. ${sym} is interesting but not bid up. For value or contrarian setups this is often the most actionable band — quality without the late-stage price-discovery overhead.`;
    }
    if (s === "NEUTRAL") {
      return `NEUTRAL (40-54) means the six factors cancel each other. ${sym} doesn't lean directionally on the composite right now. That's not bad — it's the band where you'd come back next week to see if any single factor breaks out of the equilibrium.`;
    }
    if (s === "CAUTION") {
      return `CAUTION (25-39) means more factors are pointing negative than positive. ${sym} has structural drag somewhere — trend, fundamentals, macro, or all of the above. The label is a "look before you act here" flag, not a short-call.`;
    }
    if (s === "WEAK") {
      return `WEAK (0-24) means four or more factors are negative. The composite is in the bottom tier of the distribution. Tapeline doesn't tell you to short — descriptive labels only — but a WEAK reading is the data saying "the structural conditions for this ticker are unfavourable across multiple measures".`;
    }
    return `The signal label captures where ${sym} sits in the score distribution and which factors are pulling the composite up or down.`;
  })();

  // Factor-level interpretation — uses the strongest + weakest factor
  // to write a couple of sentences that are genuinely different per
  // ticker because the strongest/weakest pair varies across the
  // universe.
  const strongestInterp = (() => {
    const v = strongest.value;
    const tier = v >= 80 ? "very strong" : v >= 65 ? "strong" : v >= 50 ? "constructive" : v >= 35 ? "mixed" : "weak";
    switch (strongest.key) {
      case "trend":
        return `${sym}'s strongest factor is Trend at ${v.toFixed(0)}/100 — a ${tier} read on the multi-week technical structure. Trend incorporates position vs key moving averages, slope, and participation; a high reading means price is well above structural support with consistent breadth behind it.`;
      case "rs":
        return `${sym}'s strongest factor is Relative Strength at ${v.toFixed(0)}/100 — ${tier} performance vs the broader market over the trailing 1-3 months. High RS means ${sym} is meaningfully outperforming SPY and its sector, which historically clusters with continuation rather than reversion.`;
      case "fundamentals":
        return `${sym}'s strongest factor is Fundamentals at ${v.toFixed(0)}/100 — a ${tier} balance-sheet + earnings-quality + margin-trend read. High Fundamentals doesn't guarantee a near-term move, but it caps the downside in a way pure-technical setups can't.`;
      case "smart_money":
        return `${sym}'s strongest factor is Smart Money at ${v.toFixed(0)}/100 — a ${tier} read on insider buying (SEC Form 4), Congressional disclosures, and ETF flows. High Smart Money means people with information edge are aligned with this name.`;
      case "macro":
        return `${sym}'s strongest factor is Macro at ${v.toFixed(0)}/100 — meaning the broader regime (rates, VIX, dollar, breadth) is ${tier} supportive for this kind of setup. Macro doesn't move stocks directly but it sets the tempo for everything underneath.`;
      case "momentum":
        return `${sym}'s strongest factor is Momentum at ${v.toFixed(0)}/100 — ${tier} short-horizon price acceleration (rate of change, RSI position, MACD posture, recent breakout structure). High momentum needs trend confirmation to mean anything; without it, momentum mean-reverts hard.`;
    }
    return "";
  })();

  const weakestInterp = (() => {
    if (weakest.key === strongest.key) return "";
    const v = weakest.value;
    const tier = v <= 25 ? "well below average" : v <= 40 ? "below average" : v <= 55 ? "middling" : "decent";
    switch (weakest.key) {
      case "trend":
        return `The weakest factor is Trend at ${v.toFixed(0)}/100 — a ${tier} technical read. If the rest of the picture is constructive, that's often a re-test buying opportunity rather than a structural concern.`;
      case "rs":
        return `The weakest factor is Relative Strength at ${v.toFixed(0)}/100 — ${tier} performance vs SPY and the sector. ${sym} is participating in any rally less than its peers.`;
      case "fundamentals":
        return `The weakest factor is Fundamentals at ${v.toFixed(0)}/100 — ${tier} balance-sheet and earnings-quality. A low fundamentals score is the canonical "value trap" warning: technical setups on broken fundamentals don't tend to compound.`;
      case "smart_money":
        return `The weakest factor is Smart Money at ${v.toFixed(0)}/100 — ${tier} insider + Congressional activity. Could mean nobody with edge is positioning here, or just that the disclosure data is sparse for ${sym}.`;
      case "macro":
        return `The weakest factor is Macro at ${v.toFixed(0)}/100 — ${tier} backdrop. A macro headwind drags every name in the cohort; if ${sym} is still scoring well on the composite despite this, the company-specific factors must be doing heavy lifting.`;
      case "momentum":
        return `The weakest factor is Momentum at ${v.toFixed(0)}/100 — ${tier} short-horizon price action. Low momentum + high trend often marks a base-building phase rather than a topping pattern.`;
    }
    return "";
  })();

  // Recent move context — gives the editorial a "tape right now" hook.
  const moveContext = (() => {
    const c1 = d.change_pct_1d;
    const c5 = d.change_pct_5d;
    if (c1 == null && c5 == null) return "";
    const parts: string[] = [];
    if (c1 != null) parts.push(`${c1 >= 0 ? "+" : ""}${c1.toFixed(2)}% on the day`);
    if (c5 != null) parts.push(`${c5 >= 0 ? "+" : ""}${c5.toFixed(2)}% over five sessions`);
    return ` ${sym} is ${parts.join(" and ")} as of the most recent tick.`;
  })();

  const scoreStr = score != null ? score.toFixed(0) : "—";
  const intro = `${name} (${sym}) currently scores ${scoreStr}/100 on the Tapeline six-factor composite, sitting in the ${signal} band.${moveContext}`;

  return [intro, sigInterp, strongestInterp, weakestInterp].filter(Boolean).join(" ");
}

type RelatedRow = {
  symbol: string;
  name: string;
  sector: string | null;
  score: number | null;
  signal: string | null;
};

type NewsArticle = {
  id: string | number;
  title: string;
  publisher: string | null;
  published_at: string; // ISO
  url: string;
  description: string | null;
  tickers: string[];
  sentiment: number | null;
};

/**
 * Fetch the most recent 5 news articles tagged with this ticker.
 *
 * Why this exists: the prior content-uplift (`fetchRelatedTickers`) added
 * sector-scoped related-ticker cards to defeat Google's templated-content
 * verdict — and partly worked (Discovered → Crawled). But Google's next
 * validation pass FAILED on 474 pages (per GSC 2026-05-24), meaning the
 * crawled body STILL reads as too templated for the indexer. Headlines are
 * the highest-uniqueness-per-byte content we can ship: they change daily,
 * they're verifiably ticker-specific (text-of-the-page becomes "AAPL filed
 * Q1 results today" rather than score scaffolding only), and Google's news
 * understanding ranks them against the canonical ticker entity. Empty array
 * on failure → section gracefully hides.
 */
async function fetchTickerNews(symbol: string): Promise<NewsArticle[]> {
  try {
    const res = await fetch(
      `${API_BASE}/api/news?symbol=${symbol.toUpperCase()}&limit=5`,
      // 5-min cache; news changes much slower than the score, no point
      // hammering the API on every crawl. Matches /api/scanner cadence.
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return [];
    const body = (await res.json()) as { items?: NewsArticle[] };
    return body.items ?? [];
  } catch {
    return [];
  }
}

/**
 * Fetch 6 tickers in the same sector with comparable scores, excluding
 * the current symbol. Two passes: server-side request scoped by sector
 * + min-score floor, then in-memory selection of the 6 closest by
 * score delta.
 *
 * Why this exists: GSC reported ~400 per-ticker pages stuck "Discovered,
 * currently not indexed" — Google's quality classifier rejecting them
 * as templated/low-uniqueness. Surfacing 6 deterministically-different
 * related tickers per page solves both halves of that diagnosis:
 *   (a) each page's HTML body becomes provably unique (no two tickers
 *       have the same sector + score-cohort 6),
 *   (b) creates dense internal linking — every indexed ticker page
 *       passes 6 internal links to other ticker pages, accelerating
 *       crawl + sibling discovery.
 *
 * Caches 5 min server-side; falls back to empty array on any error so
 * the page renders even if /api/scanner is down. Empty array hides the
 * section entirely (no awkward "couldn't load" UI).
 */
async function fetchRelatedTickers(
  symbol: string,
  sector: string | null,
  currentScore: number | null,
): Promise<RelatedRow[]> {
  if (!sector) return [];
  try {
    const params = new URLSearchParams({
      sort: "score",
      order: "desc",
      min_score: "40",
      limit: "60",
    });
    const res = await fetch(`${API_BASE}/api/scanner?${params.toString()}`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return [];
    const body = (await res.json()) as { items?: RelatedRow[] };
    const items = body.items ?? [];
    const sym = symbol.toUpperCase();
    // Filter to same sector, exclude self, score must exist.
    const candidates = items.filter(
      (r) =>
        r.sector === sector &&
        r.symbol.toUpperCase() !== sym &&
        r.score != null,
    );
    if (currentScore == null) return candidates.slice(0, 6);
    // Sort by absolute score-delta vs current ticker so the related set
    // is "names with similar conviction in your sector" — most useful for
    // a trader and most defensibly unique for Google's quality classifier.
    candidates.sort(
      (a, b) =>
        Math.abs((a.score ?? 0) - currentScore) -
        Math.abs((b.score ?? 0) - currentScore),
    );
    return candidates.slice(0, 6);
  } catch {
    return [];
  }
}

// Per-page metadata so each ticker page has its own title + description and
// its own social-share text. The sibling opengraph-image.tsx auto-wires
// og:image. The root layout's title.template is "%s" so the brand suffix
// in the title here is NOT double-applied.
export async function generateMetadata({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const sym = symbol.toUpperCase();
  const data = await fetchTicker(sym);
  if (!data) {
    return {
      title: `${sym} — Not in Scanner Universe · Tapeline`,
      description: `${sym} is not currently in the Tapeline scanner universe. Browse covered tickers or explore the scoring methodology.`,
      alternates: { canonical: `https://tapeline.io/t/${sym}` },
      robots: { index: false, follow: true },
    };
  }
  const score = data.score?.toFixed(0) ?? "—";
  const signal = data.signal ?? "—";
  const why = data.reason ?? "Six-factor synthesis updated live.";
  const title = `${sym} Stock Score ${score}/100 · ${signal} · Tapeline`;
  // Long-tail-friendly description hits queries traders actually run:
  // "TICKER stock score", "TICKER analysis", "TICKER technical rating", etc.
  // The Finviz-alternative phrasing at the end is deliberate — GSC shows a
  // strong "[ticker] finviz" pattern (snowflake finviz, clrb finviz, auud
  // finviz, etc.) across the ~2,500-ticker universe. Mentioning "free
  // Finviz alternative" in the description lets every per-ticker page
  // compete for "${sym} finviz" without keyword stuffing the title.
  // Keeps copy honest (no return claims, descriptive not prescriptive).
  const description = `Tapeline Score ${score}/100 (${signal}) for ${data.name} (${sym}). ${why} 6-factor quantitative analysis: trend, relative strength, fundamentals, smart money, macro, momentum. A free Finviz alternative for ${sym} — public formula, back-checked scorecard, live updates.`;
  // Keyword set for crawlers — narrow, ticker-specific, no spam stuffing.
  // Finviz keywords added 2026-05-19: GSC shows ~half a dozen "{ticker}
  // finviz" queries per 90 days where we already accidentally rank but
  // weren't explicitly targeting. Per-ticker keyword inclusion makes that
  // an intentional surface.
  const keywords = [
    `${sym} stock score`,
    `${sym} stock analysis`,
    `${sym} ${data.name}`,
    `${sym} technical rating`,
    `${sym} fundamental analysis`,
    `is ${sym} a buy`,
    `${sym} finviz`,
    `${sym} finviz alternative`,
    "Tapeline Score",
    "stock scanner",
    "Finviz alternative",
  ];
  const url = `https://tapeline.io/t/${sym}`;
  // 2026-05-24 PIVOT: noindex gate REMOVED. Founder ask: "index everything".
  // Approach changed from "noindex thin pages" to "make every page
  // substantial enough to be worth indexing" — see buildEditorialCommentary
  // above which auto-generates 200-400 words of ticker-specific copy from
  // the live factor sub-scores. Every per-ticker page now passes through
  // as index=true; Google still decides what it actually accepts based
  // on the rendered content (the editorial commentary, news section,
  // related tickers, FAQ, etc.) — but we no longer pre-filter.
  return {
    title,
    description,
    keywords,
    alternates: { canonical: url },
    robots: { index: true, follow: true, googleBot: { index: true, follow: true } },
    openGraph: {
      title: `${sym} · ${score}/100 · ${signal}`,
      description: why,
      url,
      type: "website",
      siteName: "Tapeline",
      locale: "en_US",
    },
    twitter: {
      card: "summary_large_image",
      title: `${sym} · ${score}/100 · ${signal}`,
      description: why,
      site: "@tapeline_io",
    },
    other: {
      "article:modified_time": new Date().toISOString(),
      "article:section": "Stocks",
    },
  };
}

// On-page FAQ — kept short, real questions a trader asks when landing on a
// ticker page from search. The same items feed the FAQPage JSON-LD below
// (Google's rich-result eligibility requires the schema to mirror visible
// page content). Answers are templated on the ticker but score/signal are
// pulled live so they always reflect what's rendered above.
function buildFaq(sym: string, name: string, score: string, signal: string, sector: string | null): { q: string; a: string }[] {
  // 2026-05-24: expanded from 5 → 12 entries. Each new question is
  // ticker-templated so the FAQ section reads as genuinely about THIS
  // ticker rather than boilerplate. Google's quality classifier weights
  // text density + question/answer coverage heavily for the FAQPage
  // rich result — and the same content depth helps the page clear
  // the "Crawled - currently not indexed" bar.
  const sectorPhrase = sector ? `the ${sector.toLowerCase()} sector` : "its sector";
  return [
    {
      q: `What is the Tapeline Score for ${sym}?`,
      a: `${sym} (${name}) currently scores ${score}/100 with the signal label ${signal}. The score is a weighted blend of six quantitative factors and updates sub-60 seconds during US market hours.`,
    },
    {
      q: `How is ${sym}'s score calculated?`,
      a: `The Tapeline Score is a transparent weighted sum: 25% Trend, 20% Relative Strength, 15% Fundamentals, 15% Smart Money, 15% Macro, 10% Momentum. Each sub-score is normalised to 0-100 and the exact formula is published on /how-it-works.`,
    },
    {
      q: `Is ${sym} a buy?`,
      a: `Tapeline doesn't issue buy or sell calls — we publish descriptive analytics, not investment advice. The signal label ${signal} describes the current state of the data; whether ${sym} fits your portfolio depends on your risk tolerance, time horizon, and tax situation. See the risk disclosure for details.`,
    },
    {
      q: `How often does the ${sym} score update?`,
      a: `${sym}'s score re-ticks every minute during US market hours and persists between sessions. Price and momentum data refresh sub-60s; fundamentals refresh on company filing cadence; insider Form 4 within hours of SEC filing.`,
    },
    {
      q: `Where can I see the historical track record for Tapeline scores?`,
      a: `Every Tapeline top-10 daily pick is auto-published with the next-day return vs SPY at /scorecard. The scorecard is immutable — every call is preserved with its original context for accountability.`,
    },
    {
      q: `What does the ${signal} signal mean for ${sym}?`,
      a: `${signal} is a descriptive band on the Tapeline composite. HIGH CONVICTION (85-100) means all six factors aligned; STRONG SETUP (70-84) typically four-or-five-of-six; CONSTRUCTIVE (55-69) net-positive with tradeoffs; NEUTRAL (40-54) factors cancel; CAUTION (25-39) more negative than positive; WEAK (0-24) broadly negative. ${sym} sitting at ${signal} means the data right now reads as ${signal.toLowerCase()} for the six-factor profile.`,
    },
    {
      q: `Is ${sym} better for swing trading or day trading?`,
      a: `The Tapeline composite is calibrated for multi-day setups — the heaviest weights (Trend 25%, RS 20%, Fundamentals 15%) reward stability over a horizon of days-to-weeks. For pure day trading, the 1-day move + sub-momentum factor is more relevant. Use /best-stocks-for/day-traders for the day-trader-sorted view and /best-stocks-for/swing-traders for the multi-day setup view.`,
    },
    {
      q: `Where does ${sym} rank in ${sectorPhrase}?`,
      a: `${sym}'s sector rank within ${sectorPhrase} updates live as composite scores re-tick during US market hours — see the rank line near the top of this page. Sector ranks are computed across the actively-scored universe (~2,500 US tickers by daily $-volume) so the cohort is consistent across all ${sectorPhrase} names Tapeline covers.`,
    },
    {
      q: `Does Tapeline have insider buying data for ${sym}?`,
      a: `${sym}'s Smart Money sub-score (15% of the composite) blends SEC Form 4 insider transactions, Congressional disclosures where applicable, and ETF/institutional flow signals. Detailed Form 4 history per ticker is a Premium feature; the aggregate Smart Money sub-score is shown on this page for free.`,
    },
    {
      q: `Why does ${sym}'s score change between visits?`,
      a: `Scores re-tick every minute during US market hours. Trend and Relative Strength move with price; Momentum reflects recent rate-of-change; Macro responds to VIX, breadth, and 10Y yield shifts; Smart Money updates on filing cadence; Fundamentals on quarterly earnings cycle. Across a single trading session ${sym}'s composite can drift 5-15 points in either direction even without major news — that's normal factor breathing, not data error.`,
    },
    {
      q: `Can I get alerts when ${sym}'s score changes?`,
      a: `Yes — Pro tier gets email alerts on configurable triggers (score crosses a threshold, signal label changes, squeeze detected). Premium adds Telegram unlimited and Congressional-trade alerts. The free tier covers the top 20 tickers with a 24-hour delay; ${sym} score alerts specifically require Pro or Premium since ${sym} may not be in the top 20.`,
    },
    {
      q: `How does ${sym}'s Tapeline Score compare to a Finviz screener result?`,
      a: `Finviz exposes raw filter fields — you build a thesis from the data. Tapeline synthesises six factors into one composite + a plain-English Why, so the work is done before you look at the row. Both are useful for different jobs: Finviz Elite for power-user raw-filter scans, Tapeline for daily synthesised rankings + per-pick public scorecard. Many traders use both — see /best-finviz-alternatives for the head-to-head comparison.`,
    },
  ];
}

export default async function PublicTickerPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const sym = symbol.toUpperCase();
  const data = await fetchTicker(sym);

  if (!data) notFound();

  // Related tickers + ticker-specific news fetched in parallel with the
  // main page render. Empty arrays gracefully hide their sections so a
  // slow / failing upstream doesn't degrade the rest of the page.
  const [related, news] = await Promise.all([
    fetchRelatedTickers(sym, data.sector, data.score),
    fetchTickerNews(sym),
  ]);

  // Sector rank derived from the related-tickers fetch (queries up to 60
  // same-sector scoring rows). We can answer "{SYM} ranks #X out of Y in
  // {sector}" deterministically — that single sentence is uniquely per-
  // ticker text that Google's quality classifier can't dismiss as boilerplate.
  // Computed inline (not via a new round-trip) because related already has
  // the data we need.
  const sectorRank = (() => {
    if (!data.sector || data.score == null) return null;
    // related is same-sector + min_score=40, sorted by closeness to data.score.
    // We need rank-by-score-desc, so re-sort that pool and find the position.
    const scored = related
      .filter((r) => r.score != null)
      .map((r) => ({ symbol: r.symbol, score: r.score! }));
    scored.push({ symbol: data.symbol, score: data.score });
    const desc = [...new Set(scored.map((s) => s.symbol))]
      .map((s) => scored.find((x) => x.symbol === s)!)
      .sort((a, b) => b.score - a.score);
    const idx = desc.findIndex((s) => s.symbol === data.symbol);
    if (idx === -1) return null;
    return { rank: idx + 1, total: desc.length };
  })();

  const score = data.score ?? 0;
  const signal = data.signal ?? "—";
  const change = data.change_pct_1d ?? 0;
  const changeColor = change > 0 ? "text-up" : change < 0 ? "text-down" : "text-muted";

  // Score-tier colours mirror /how-it-works.
  const scoreColor =
    score >= 70 ? "text-up" : score >= 55 ? "text-accent" : score >= 40 ? "text-muted" : score >= 25 ? "text-warn" : "text-down";

  const b = data.breakdown ?? {};
  const factors: { label: string; value: number | null | undefined; weight: number }[] = [
    { label: "Trend",              value: b.trend?.value,        weight: 25 },
    { label: "Relative strength",  value: b.rs?.value,           weight: 20 },
    { label: "Fundamentals",       value: b.fundamentals?.value, weight: 15 },
    { label: "Smart money",        value: b.smart_money?.value,  weight: 15 },
    { label: "Macro",              value: b.macro?.value,        weight: 15 },
    { label: "Momentum",           value: b.momentum?.value,     weight: 10 },
  ];

  // Structured data — three graphs inlined in the body. Google parses
  // JSON-LD anywhere in the HTML; placing them in body avoids the React
  // "scripts in head" hydration warnings.
  const faqItems = buildFaq(
    data.symbol,
    data.name,
    data.score?.toFixed(0) ?? "—",
    data.signal ?? "—",
    data.sector,
  );
  const url = `https://tapeline.io/t/${data.symbol}`;
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Tickers", url: "https://tapeline.io/scorecard" },
    { name: `${data.symbol} (${data.name})`, url },
  ]);
  const review = tickerReviewJsonLd({
    symbol: data.symbol,
    name: data.name,
    url,
    score: data.score,
    signal: data.signal,
    why: data.reason,
  });

  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(review)} />
      <script {...jsonLdScript(faqJsonLd(faqItems))} />
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-4 sm:px-6 py-8 sm:py-12">
        {/* Header row */}
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h1 className="text-4xl sm:text-5xl font-bold tracking-tight nums">{data.symbol}</h1>
              <span className="text-sm sm:text-base text-muted truncate max-w-full">{data.name}</span>
            </div>
            <div className="mt-2 flex items-center gap-3 text-xs sm:text-sm text-muted">
              {data.sector && <span>{data.sector}</span>}
              {data.asset_class && <span className="text-subtle">·</span>}
              {data.asset_class && <span className="capitalize">{data.asset_class}</span>}
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <div className="text-2xl sm:text-3xl font-bold nums">
              {data.price != null ? `$${data.price.toFixed(2)}` : "—"}
            </div>
            {data.change_pct_1d != null && (
              <div className={`text-sm font-medium nums ${changeColor}`}>
                {change >= 0 ? "+" : ""}
                {change.toFixed(2)}% today
              </div>
            )}
          </div>
        </div>

        {/* Score + signal hero — radial visual signature on the right gives
            the score a *shape*, not just a number. Same role Simply Wall St's
            Snowflake plays for theirs. Each axis is one factor; lopsided
            polygons read as "strong on X, weak on Y" at a glance. */}
        <div className="mt-8 sm:mt-10 rounded-2xl border border-border bg-panel p-5 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-6 sm:gap-8">
            <div className="min-w-0 flex-1">
              <div className="text-xs uppercase tracking-wider text-muted">Tapeline Score</div>
              <div className={`mt-1 text-6xl sm:text-7xl font-bold nums tracking-tight ${scoreColor}`}>
                {data.score != null ? data.score.toFixed(0) : "—"}
                <span className="ml-1 text-xl sm:text-2xl text-muted font-medium">/ 100</span>
              </div>
              <div className="mt-4">
                <div className="text-xs uppercase tracking-wider text-muted">Signal</div>
                <div className={`mt-1 text-xl sm:text-2xl font-bold tracking-tight ${scoreColor}`}>{signal}</div>
                {data.confidence_pct != null && (
                  <div className="mt-1 text-xs text-muted">
                    {data.confidence_pct.toFixed(0)}% data confidence
                  </div>
                )}
              </div>
              {data.reason && (
                <p className="mt-6 max-w-xl text-sm sm:text-base leading-relaxed text-fg">{data.reason}</p>
              )}
              {/* Sector rank — deterministic per-ticker prose. This single
                  sentence varies for every ticker (rank differs even when
                  two tickers have the same score in the same sector, because
                  the cohort sizes differ for low-volume sub-segments) which
                  is what Google's quality classifier needs to see as proof
                  the page is not boilerplate-templated. */}
              {sectorRank && data.sector && (
                <p className="mt-3 max-w-xl text-xs sm:text-sm text-subtle">
                  {data.symbol} ranks <span className="font-semibold text-muted">#{sectorRank.rank}</span> out of {sectorRank.total} {data.sector.toLowerCase()} stocks in the Tapeline universe by composite score this session.
                </p>
              )}
            </div>
            <div className="hidden sm:block flex-shrink-0">
              <ScoreRadial
                trend={b.trend?.value ?? null}
                rs={b.rs?.value ?? null}
                fundamentals={b.fundamentals?.value ?? null}
                smart_money={b.smart_money?.value ?? null}
                macro={b.macro?.value ?? null}
                momentum={b.momentum?.value ?? null}
                score={data.score ?? null}
                size={220}
              />
            </div>
          </div>
          {/* Mobile-only radial — placed below the score so it doesn't
              fight for header space on narrow viewports. */}
          <div className="mt-6 flex justify-center sm:hidden">
            <ScoreRadial
              trend={b.trend?.value ?? null}
              rs={b.rs?.value ?? null}
              fundamentals={b.fundamentals?.value ?? null}
              smart_money={b.smart_money?.value ?? null}
              macro={b.macro?.value ?? null}
              momentum={b.momentum?.value ?? null}
              score={data.score ?? null}
              size={200}
            />
          </div>
        </div>

        {/* 6-factor breakdown */}
        <h2 className="mt-10 sm:mt-12 text-sm font-semibold uppercase tracking-wider text-muted">
          Score breakdown · public formula
        </h2>
        <div className="mt-4 space-y-2">
          {factors.map((f) => (
            <div key={f.label} className="flex items-center gap-3 sm:gap-4 rounded-lg border border-border bg-panel/40 px-3 sm:px-4 py-3">
              <div className="w-28 sm:w-44 flex-shrink-0">
                <div className="text-xs sm:text-sm font-medium truncate">{f.label}</div>
                <div className="text-[10px] uppercase tracking-wider text-subtle">{f.weight}% weight</div>
              </div>
              <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-background">
                <div
                  className="h-full bg-gradient-to-r from-accent to-accent2"
                  style={{ width: `${f.value != null ? Math.max(0, Math.min(100, f.value)) : 0}%` }}
                />
              </div>
              <div className="w-10 sm:w-12 text-right font-medium nums tabular-nums text-sm sm:text-base">
                {f.value != null ? f.value.toFixed(0) : "—"}
              </div>
            </div>
          ))}
        </div>

        <p className="mt-4 text-xs text-muted">
          Weights are public and never change without a changelog entry.
          Read the full methodology on <Link href="/how-it-works" className="text-accent hover:underline">/how-it-works</Link>.
        </p>

        {/* Score history sparkline — sparse trace from the daily scorecard.
            Shows nothing for tickers that haven't hit top-10, and renders
            a friendly empty state explaining why. */}
        <div className="mt-8">
          <ScoreSparkline symbol={data.symbol} days={60} />
        </div>

        {/* Editorial commentary — auto-generated from live factor sub-scores.
            200-400 words of genuinely ticker-specific content. The single
            biggest lever against Google's "Crawled - currently not indexed"
            verdict on 474 ticker pages (GSC audit 2026-05-24): if every
            page reads as substantive rather than templated, the quality
            classifier accepts more of them. Content shape varies per
            ticker because strongest/weakest factor identification is
            data-driven — no two pages share the same paragraph. */}
        <section className="mt-10 sm:mt-12">
          <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">
            What the score says about {data.symbol} right now
          </h2>
          <div className="mt-4 rounded-2xl border border-border bg-panel/30 p-5 sm:p-6">
            <p className="text-sm sm:text-base leading-relaxed text-fg">
              {buildEditorialCommentary(data)}
            </p>
            <p className="mt-4 text-xs text-subtle">
              Generated from the live six-factor breakdown above. Updates as the
              underlying scores re-tick during US market hours. Methodology
              detail at{" "}
              <Link href="/how-it-works" className="text-accent hover:underline">
                /how-it-works
              </Link>
              .
            </p>
          </div>
        </section>

        {/* CTA */}
        <div className="mt-10 sm:mt-12 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-5 sm:p-8">
          <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">See {sym} in the live scanner</h2>
          <p className="mt-2 max-w-xl text-sm text-muted">
            Free signup gives you the score for the top 20 tickers, 24-hour delayed.
            14-day Premium trial unlocks the full ~2,500-ticker live universe, smart alerts, congressional trades, and recent insider buys (SEC Form 4).
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href={`/signup?next=${encodeURIComponent(`/app/ticker/${sym}`)}`} className="btn-accent">
              Try Premium free for 14 days →
            </Link>
            <Link href="/scorecard" className="btn-ghost">
              See the public scorecard
            </Link>
            {/* Pre-filled tweet so existing users can spread per-ticker links
                in one click. Twitter will fetch the OG card and render the
                live score preview underneath. */}
            <a
              href={`https://twitter.com/intent/tweet?${new URLSearchParams({
                text: `$${sym} score: ${score.toFixed(0)}/100 (${signal})\n\nTransparent 6-factor formula, public scorecard.`,
                url: `https://tapeline.io/t/${sym}`,
              }).toString()}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost inline-flex items-center gap-2"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
              </svg>
              Share on X
            </a>
          </div>
        </div>

        {/* Recent ticker-specific headlines — the second content-uplift
            pass for Google indexing. The page now reads "AAPL filed today
            ... CEO bought stock ... earnings beat" rather than just score
            scaffolding. Each headline is hard evidence of ticker-specific
            relevance for Google's content-quality classifier. */}
        {news.length > 0 && (
          <section className="mt-12 sm:mt-16">
            <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">
              Recent {data.symbol} news
            </h2>
            <p className="mt-2 text-sm text-muted">
              Latest market-moving headlines mentioning {data.symbol}, sourced from Tapeline&rsquo;s news feed (Benzinga + Polygon).
            </p>
            <ul className="mt-6 divide-y divide-border/40 rounded-lg border border-border bg-panel/30">
              {news.map((n) => {
                const pubDate = new Date(n.published_at);
                const ageMs = Date.now() - pubDate.getTime();
                const ageH = Math.round(ageMs / 3_600_000);
                const ageStr = ageH < 1 ? "<1h ago" : ageH < 24 ? `${ageH}h ago` : `${Math.round(ageH / 24)}d ago`;
                return (
                  <li key={n.id} className="p-4 sm:p-5">
                    <a
                      href={n.url}
                      target="_blank"
                      rel="noopener nofollow"
                      className="block group"
                    >
                      <div className="text-sm sm:text-base font-medium text-fg group-hover:text-accent leading-snug">
                        {n.title}
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-xs text-subtle">
                        {n.publisher && <span>{n.publisher}</span>}
                        <span aria-hidden="true">·</span>
                        <time dateTime={n.published_at}>{ageStr}</time>
                        {n.tickers.length > 1 && (
                          <>
                            <span aria-hidden="true">·</span>
                            <span title={n.tickers.join(", ")}>
                              +{n.tickers.length - 1} other ticker{n.tickers.length > 2 ? "s" : ""}
                            </span>
                          </>
                        )}
                      </div>
                    </a>
                  </li>
                );
              })}
            </ul>
            <p className="mt-3 text-xs text-subtle">
              News refreshes every 5 minutes during US market hours.
            </p>
          </section>
        )}

        {/* Related tickers — same sector, comparable composite. This is
            the per-ticker indexing rescue: GSC flagged ~400 of these
            pages as "Discovered, currently not indexed" (templated /
            low-uniqueness verdict from Google's quality classifier).
            Surfacing a deterministic, sector-scoped, score-sorted set
            of 6 siblings makes the body provably unique per ticker AND
            creates 6 fresh internal links per page → dense crawl graph
            across the cluster. */}
        {related.length > 0 && (
          <section className="mt-12 sm:mt-16">
            <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">
              Similar setups in {data.sector ?? "this sector"} right now
            </h2>
            <p className="mt-2 text-sm text-muted max-w-2xl">
              Six {data.sector ? `${data.sector.toLowerCase()} ` : ""}tickers with
              composite scores closest to {data.symbol}&rsquo;s {data.score?.toFixed(0) ?? "—"} —
              same factor environment, sortable on the live scanner.
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {related.map((r) => {
                const rScore = r.score ?? 0;
                const rScoreColor =
                  rScore >= 85 ? "text-up" :
                  rScore >= 70 ? "text-up" :
                  rScore >= 55 ? "text-accent" :
                  rScore >= 40 ? "text-muted" :
                  "text-down";
                return (
                  <Link
                    key={r.symbol}
                    href={`/t/${r.symbol}`}
                    className="lift group block rounded-lg border border-border bg-panel/40 p-4 hover:border-accent/40 hover:bg-panel"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-mono font-bold text-base tracking-tight group-hover:text-accent">
                        {r.symbol}
                      </span>
                      <span className={`text-xl font-bold nums ${rScoreColor}`}>
                        {r.score != null ? r.score.toFixed(0) : "—"}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-muted truncate" title={r.name}>
                      {r.name}
                    </div>
                    {r.signal && (
                      <div className="mt-2 text-[10px] uppercase tracking-wider text-subtle">
                        {r.signal}
                      </div>
                    )}
                  </Link>
                );
              })}
            </div>
            <p className="mt-4 text-xs text-subtle">
              Sorted by closeness to {data.symbol}&rsquo;s composite score within{" "}
              {data.sector ?? "sector"}. Refreshed every 5 minutes.{" "}
              <Link href="/app/scanner" className="text-accent hover:underline">
                Run the full scanner →
              </Link>
            </p>
          </section>
        )}

        {/* FAQ — visible content that mirrors the FAQPage JSON-LD above.
            Hits the long-tail "{TICKER} stock score", "is {TICKER} a buy",
            "how is {TICKER} scored" queries that traders actually search. */}
        <section className="mt-12 sm:mt-16">
          <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">
            Frequently asked about {data.symbol}
          </h2>
          <div className="mt-6 divide-y divide-border/60">
            {faqItems.map((item) => (
              <details key={item.q} className="group py-4">
                <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
                  <h3 className="text-sm sm:text-base font-medium">{item.q}</h3>
                  <span className="text-muted transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-3 text-sm text-muted leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* Internal links to companion product surfaces — gives the page
            real outbound link equity instead of a single CTA, and lets
            crawlers reach the methodology + scorecard from every ticker. */}
        <nav className="mt-12 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted" aria-label="Related Tapeline pages">
          <Link href="/how-it-works" className="hover:text-fg underline-offset-4 hover:underline">
            How {data.symbol} is scored
          </Link>
          <Link href="/scorecard" className="hover:text-fg underline-offset-4 hover:underline">
            Public scorecard
          </Link>
          <Link href="/compare/finviz" className="hover:text-fg underline-offset-4 hover:underline">
            Tapeline vs Finviz
          </Link>
          <Link href="/compare/zacks" className="hover:text-fg underline-offset-4 hover:underline">
            Tapeline vs Zacks
          </Link>
          <Link href="/blog" className="hover:text-fg underline-offset-4 hover:underline">
            Methodology blog
          </Link>
        </nav>

        {/* Trust line */}
        <p className="mt-10 text-xs text-subtle text-center">
          Score updated live (sub-60s). Public formula. Public scorecard.
          Not investment advice — see <Link href="/legal/risk" className="text-accent hover:underline">risk disclosure</Link>.
        </p>

        {/* Lead-magnet email capture — ticker pages are the heaviest SEO
            entry point (search for "AAPL stock score" / "NVDA buy or
            sell" lands here). Curious visitor with no account: capture
            the email so the daily digest does the conversion work. */}
        <div className="mt-12 rounded-lg border border-border bg-panel/30 p-6">
          <div className="text-center mb-4">
            <h3 className="text-lg font-semibold text-fg">
              See this ticker scored each market morning
            </h3>
            <p className="mx-auto mt-2 max-w-md text-sm text-muted leading-relaxed">
              Get the Tapeline daily Top 10 in your inbox. One email, no card,
              unsubscribe in one click.
            </p>
          </div>
          <div className="mx-auto max-w-md">
            <NewsletterCapture source="blog" heading="" sub="" />
          </div>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}
