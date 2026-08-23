/**
 * Term manifest for the /glossary programmatic SEO + AEO surface.
 *
 * Lives outside the page modules because Next.js App Router page files may only
 * export the default component, generateMetadata, generateStaticParams and the
 * fixed metadata fields — app/sitemap.ts imports TERMS from here (same pattern
 * as app/how-it-works/factors.ts and app/sector/sectors.ts).
 *
 * ── WHY THIS EXISTS ──────────────────────────────────────────────────────
 * Answer engines cite definitional content disproportionately: a page that
 * answers "what is X, how is it measured, why does it matter" in clean prose
 * is the shape a retrieval system can lift a paragraph out of. Every term
 * below is one a retail swing trader actually types. The pages are written to
 * be CITABLE rather than keyword-dense.
 *
 * ── ACCURACY IS THE POINT ────────────────────────────────────────────────
 * The `tapeline` field is optional AND SHOULD STAY THAT WAY. It is only filled
 * in where the statement is true of the running implementation — checked
 * against app/how-it-works/factors.ts, which is itself checked against
 * backend/app/services/score.py. Several terms here (RSI, MACD, the Piotroski
 * F-Score, 13F) are deliberately marked as NOT inputs to the composite,
 * because they are not. A glossary that quietly implies every indicator feeds
 * the score would be a documented false statement about a financial product.
 *
 * ── DISCLOSURE BOUNDARY (PR #342) ────────────────────────────────────────
 * Name the six factors and their weight ORDERING. Never the numeric weights,
 * the scoring equation, or the band edges. "Weighted most toward Trend and
 * Relative Strength, least toward Momentum" is in bounds. "Trend is 25%" is
 * not.
 *
 * ── COPY RULES ───────────────────────────────────────────────────────────
 * Enforced mechanically by scripts/lint-copy-compliance.mjs (this file is in
 * its include set) and structurally by __tests__/glossaryTerms.test.ts:
 *   - Descriptive only. Define what a measurement IS, never what to do about
 *     it. No "should", no buy/sell framing, no forecasts.
 *   - No evaluative adjective anywhere near a security noun.
 *   - No numeric percentage in a `title` or `description` — those are headline
 *     slots under Rule 3 and a figure sitting next to a benchmark word there
 *     reads as a performance claim.
 */

import type { FaqItem } from "@/lib/jsonld";

/** The six published scoring factors, by /how-it-works/{slug}. */
export type FactorSlug =
  | "trend"
  | "relative-strength"
  | "fundamentals"
  | "smart-money"
  | "macro"
  | "momentum";

export type GlossaryCategory =
  | "Trend & momentum"
  | "Relative performance"
  | "Fundamentals"
  | "Market structure"
  | "Disclosure & flow"
  | "Risk"
  | "Macro & regime"
  | "Scoring & signals";

/** Render order on the index page. */
export const CATEGORY_ORDER: GlossaryCategory[] = [
  "Trend & momentum",
  "Relative performance",
  "Fundamentals",
  "Market structure",
  "Disclosure & flow",
  "Risk",
  "Macro & regime",
  "Scoring & signals",
];

export type GlossaryTerm = {
  /** URL segment: /glossary/{slug} */
  slug: string;
  /** Display name, as a trader would say it. */
  term: string;
  /** Other names the same idea travels under. Fed to DefinedTerm alternateName. */
  aliases?: string[];
  category: GlossaryCategory;
  /** Full <title>. No percentage figures — Rule 3 headline slot. */
  title: string;
  /** Meta description, ~110-200 chars. No percentage figures. */
  description: string;
  h1: string;
  /** Plain-English definition. Doubles as the schema.org DefinedTerm description. */
  definition: string;
  /** How the quantity is actually measured. Observable procedure only. */
  measured: string;
  /** Why a swing trader would care. Descriptive — never an instruction. */
  matters: string;
  /**
   * How Tapeline uses it — ONLY where genuinely true of the implementation.
   * Omit rather than stretch. Where a widely-known indicator is NOT an input,
   * say so here explicitly; that is more useful than silence.
   */
  tapeline?: string;
  /** The scoring factor this term feeds, where it genuinely feeds one. */
  factor?: FactorSlug;
  /** A relevant product or methodology page. Every term gets one. */
  related: { href: string; label: string };
  /** Sibling term slugs, for the internal link graph. */
  see: string[];
};

export const TERMS: GlossaryTerm[] = [
  /* ─────────────────────────── Trend & momentum ─────────────────────────── */
  {
    slug: "moving-average",
    term: "Moving average",
    aliases: ["MA", "simple moving average", "SMA"],
    category: "Trend & momentum",
    title: "What Is a Moving Average? Plain-English Definition | Tapeline Glossary",
    description:
      "A moving average is the average closing price over a rolling window of sessions. How it is calculated, what it smooths out, and where it lags.",
    h1: "Moving average",
    definition:
      "A moving average is the average closing price of a security over a fixed number of recent sessions, recalculated each session so the window rolls forward. It converts a jagged price series into a smoother line.",
    measured:
      "Add the closing prices over the chosen window and divide by the number of sessions in it. A 50-session average uses the last 50 closes. An exponential variant weights recent closes more heavily than older ones, so it turns sooner. The window length is the only real parameter, and it is chosen, not derived.",
    matters:
      "Swing traders use moving averages as a reference line rather than as a measurement in their own right: price sitting above a longer average describes a period in which price has generally risen, and the distance between price and the line describes how far the recent move has carried. Every moving average is arithmetic on prices that have already printed, so it turns after the move it is summarising, not before it.",
    tapeline:
      "Tapeline's Trend factor does not read moving averages or moving-average crossovers. It measures a multi-month price change and where the latest price sits inside the ticker's own 52-week range.",
    factor: "trend",
    related: { href: "/how-it-works/trend", label: "What the Trend factor measures" },
    see: ["dma-stack", "golden-cross", "macd", "momentum"],
  },
  {
    slug: "dma-stack",
    term: "DMA stack",
    aliases: ["moving average stack", "MA stack", "stacked moving averages"],
    category: "Trend & momentum",
    title: "What Is a DMA Stack? Moving-Average Alignment Explained | Tapeline Glossary",
    description:
      "A DMA stack describes several day-moving averages lined up in order, shortest to longest. How the alignment is read and why it is a description of the past.",
    h1: "DMA stack",
    definition:
      "A DMA stack describes a chart where several day-moving averages of different lengths sit in order — the shortest above the next-shortest, and so on down to the longest. Traders call the arrangement 'stacked' when the ordering is unbroken.",
    measured:
      "Plot two or more day-moving averages of different window lengths on the same price series — commonly a short, a medium and a long window — and check whether their current values are ordered by window length. Ordered shortest-highest is one arrangement; ordered shortest-lowest is the inverse; anything else is unstacked.",
    matters:
      "The arrangement compresses several lookback windows into one glance: a stack in ordering means the short-window average, the medium-window average and the long-window average have all been moving the same way relative to each other. Swing traders watch it as a summary of how consistent a multi-month move has been. It says nothing about what happens next, and the stack re-orders only after the underlying prices have already moved.",
    tapeline:
      "Not an input to any Tapeline factor. The Trend factor reads a multi-month price change and the position of price inside the 52-week range instead.",
    factor: "trend",
    related: { href: "/how-it-works/trend", label: "What the Trend factor measures" },
    see: ["moving-average", "golden-cross", "trend"],
  },
  {
    slug: "golden-cross",
    term: "Golden cross",
    aliases: ["moving average crossover", "death cross"],
    category: "Trend & momentum",
    title: "What Is a Golden Cross? Crossover Definition | Tapeline Glossary",
    description:
      "A golden cross describes a shorter moving average crossing above a longer one. What the crossover is, how it is dated, and why it is always late.",
    h1: "Golden cross",
    definition:
      "A golden cross describes the session on which a shorter-window moving average crosses above a longer-window one. The inverse arrangement — the shorter average crossing below the longer — is conventionally called a death cross.",
    measured:
      "Track two moving averages of different window lengths on the same price series. The crossover is dated to the session where the sign of the difference between them flips. Both averages are arithmetic on closes that have already printed, so the crossover date is knowable only after the fact.",
    matters:
      "The crossover is one of the most widely watched chart events in retail trading, which makes it worth knowing as vocabulary even for a trader who does not use it. Mechanically it is a lagging restatement: by the time a short average has crossed a long one, the price move that produced the crossing has already happened. Swing traders who use it treat it as confirmation of a period that has passed rather than as a signal about the next one.",
    tapeline:
      "Not an input to any Tapeline factor. The methodology page for Trend states plainly that the factor does not use moving-average crossovers.",
    factor: "trend",
    related: { href: "/how-it-works/trend", label: "What the Trend factor measures" },
    see: ["moving-average", "dma-stack", "trend"],
  },
  {
    slug: "macd",
    term: "MACD",
    aliases: ["moving average convergence divergence"],
    category: "Trend & momentum",
    title: "What Is MACD? Moving Average Convergence Divergence | Tapeline Glossary",
    description:
      "MACD is the difference between two exponential moving averages, plotted against a signal line. How the three components are built and what each one shows.",
    h1: "MACD (moving average convergence divergence)",
    definition:
      "MACD is an indicator built from the difference between two exponential moving averages of price. That difference is plotted as a line, a second average of the line is plotted alongside it as a signal line, and the gap between the two is drawn as a histogram.",
    measured:
      "Subtract a longer-window exponential moving average from a shorter-window one to get the MACD line. Take an exponential average of that line to get the signal line. The histogram is the MACD line minus the signal line. All three are derived from closing prices, so all three are recalculated as each session closes.",
    matters:
      "MACD is a rate-of-change measurement dressed as a chart study: the two averages converge when a move is decelerating and diverge when it is accelerating. Swing traders read it for that acceleration rather than for direction, which price itself already shows. Because every component is an average of past closes, the indicator inherits the lag of its longest window.",
    tapeline:
      "Not an input to any Tapeline factor. The Momentum factor reads a momentum-quality input and a short-horizon return instead.",
    related: { href: "/how-it-works/momentum", label: "What the Momentum factor measures" },
    see: ["moving-average", "rate-of-change", "momentum", "rsi"],
  },
  {
    slug: "rsi",
    term: "RSI",
    aliases: ["relative strength index"],
    category: "Trend & momentum",
    title: "What Is RSI? Relative Strength Index Explained | Tapeline Glossary",
    description:
      "RSI compares the size of a security's recent gains to the size of its recent losses on a 0-100 scale. How it is calculated and what the scale actually says.",
    h1: "RSI (relative strength index)",
    definition:
      "RSI is an oscillator that compares the average size of a security's up sessions to the average size of its down sessions over a recent window, expressed on a 0-100 scale. Despite the name it has nothing to do with relative strength against a benchmark — it compares a security only to its own recent history.",
    measured:
      "Over a rolling window of sessions, average the size of the sessions that closed up and average the size of the sessions that closed down. The ratio of those two averages is mapped onto a 0-100 scale. Readings near the top of the scale mean recent up sessions have been larger than recent down sessions; readings near the bottom mean the reverse.",
    matters:
      "The scale is bounded, which is the useful part: unlike price it cannot run away, so it puts very different securities on comparable footing. The common trap is treating a reading near either end as a turning point — a security in a sustained move can hold an extreme reading for weeks, because the oscillator is describing the character of the move rather than its remaining length.",
    tapeline:
      "Not an input to any Tapeline factor. The similarly-named Relative Strength factor is a completely different measurement: it compares a ticker's price change to a broad-market benchmark's over the same period.",
    related: { href: "/glossary/relative-strength", label: "Relative strength, the other meaning" },
    see: ["relative-strength", "macd", "rate-of-change", "volatility"],
  },
  {
    slug: "rate-of-change",
    term: "Rate of change",
    aliases: ["ROC", "price rate of change"],
    category: "Trend & momentum",
    title: "What Is Rate of Change? ROC Definition for Traders | Tapeline Glossary",
    description:
      "Rate of change is the percentage price change over a fixed lookback window. The simplest momentum measurement, and how window length changes what it sees.",
    h1: "Rate of change",
    definition:
      "Rate of change is the percentage difference between the current price and the price a fixed number of sessions ago. It is the most direct measurement of how quickly price has moved, with no smoothing in between.",
    measured:
      "Take the current price, subtract the price at the start of the lookback window, and divide by that starting price. The lookback length is the whole design decision: a short window reacts fast and reverses often, a long window is steadier but reaches a genuine turn late.",
    matters:
      "Almost every momentum study reduces to a rate of change with extra processing on top, so understanding the raw version makes the derived ones legible. For a swing trader the practical caution is that the measurement is a two-point comparison — it reads only the start and the end of the window, so a sharp move that fully reversed inside the window is invisible to it.",
    tapeline:
      "This is the shape of the Momentum factor. Tapeline's Momentum sub-score reads a short-horizon return alongside a momentum-quality input, and the composite weights Momentum least of the six factors because short-horizon rate of change reverses often.",
    factor: "momentum",
    related: { href: "/how-it-works/momentum", label: "What the Momentum factor measures" },
    see: ["momentum", "macd", "relative-strength", "volatility"],
  },
  {
    slug: "momentum",
    term: "Momentum",
    category: "Trend & momentum",
    title: "What Is Momentum in Stock Trading? Definition | Tapeline Glossary",
    description:
      "Momentum describes how fast and how persistently price has been moving. What the measurement covers, and why it is the noisiest of the common factors.",
    h1: "Momentum",
    definition:
      "Momentum describes the speed and persistence of a security's recent price movement. As a measurement it is a short-horizon rate of change; as a factor it is the observation that recent price behaviour tends to carry some information about near-term price behaviour.",
    measured:
      "Compute the return over a recent window — days to a few months — and compare it across a universe of securities, or place it on a fixed scale. Implementations differ mainly in window length and in whether the raw return is adjusted for how choppy the path was.",
    matters:
      "Momentum answers a different question from trend: trend describes where price has travelled over months, momentum describes how quickly it is travelling now. Swing traders track it because a multi-week holding period sits in exactly the window momentum measures. It is also the noisiest common factor — short-horizon readings reverse frequently, and a reading built on a few weeks of data is heavily exposed to single events like an earnings gap or an index-inclusion flow.",
    tapeline:
      "Momentum is one of the six named factors in the Tapeline composite, and deliberately the least-weighted of them. The methodology page states why, including the fact that its short-horizon component is an approximation rather than a direct measurement.",
    factor: "momentum",
    related: { href: "/how-it-works/momentum", label: "What the Momentum factor measures" },
    see: ["rate-of-change", "trend", "relative-strength", "breakout"],
  },
  {
    slug: "trend",
    term: "Trend",
    category: "Trend & momentum",
    title: "What Is a Trend in Stock Trading? Definition | Tapeline Glossary",
    description:
      "A trend describes the direction and persistence of price over a multi-month window. How trend differs from momentum, and why every trend reading is backward-looking.",
    h1: "Trend",
    definition:
      "A trend describes the direction price has generally travelled over an extended window, and how consistently it has travelled that way. It is a statement about a period of price history rather than about any single session.",
    measured:
      "The two common approaches are a price change over a multi-month lookback, and the position of the current price inside a longer high-to-low range. Chart-based methods add moving averages or successive highs and lows, but every method reduces to arithmetic on prices that have already printed.",
    matters:
      "Trend is the longest-memory of the common measurements, which makes it the steadiest and the slowest. Swing traders use it as context for shorter signals: the same short-horizon reading means something different inside a multi-month advance than inside a multi-month decline. Because it is backward-looking by construction, a trend reading is a description of the past and carries no information about valuation, solvency, or what the company does.",
    tapeline:
      "Trend counts for more than any other factor in the Tapeline composite. It reads a multi-month price change and where the latest price sits inside the ticker's own 52-week range.",
    factor: "trend",
    related: { href: "/how-it-works/trend", label: "What the Trend factor measures" },
    see: ["momentum", "moving-average", "dma-stack", "relative-strength"],
  },
  {
    slug: "breakout",
    term: "Breakout",
    category: "Trend & momentum",
    // NOT "What Is a Breakout…" — the copy linter's Rule 2 fires on
    // "is a breakout" (the predictive form), and a <title> is exactly the
    // templated slot that rule exists to police.
    title: "What Does Breakout Mean in Trading? Definition | Tapeline Glossary",
    description:
      "A breakout describes price moving beyond a level that previously contained it. How the level is defined, and why breakouts are only identifiable after the fact.",
    h1: "Breakout",
    definition:
      "A breakout describes price moving beyond a level that had previously contained it — a prior high, a prior low, or the boundary of a range price had been oscillating inside. The word names the event, not a prediction about what follows it.",
    measured:
      "Define the containing level first: a recent range high or low, a multi-week high, or a horizontal level price has repeatedly turned at. The move past that level is then dated to the session that closed beyond it. Because the containing level is drawn by whoever is looking, two traders can date the same event differently.",
    matters:
      "The concept matters mostly as vocabulary and as a scan category: a large share of retail scanners are organised around it. The measurement problem worth knowing is that the containing level is chosen rather than derived, and that a move past a level is confirmed only after the session it happened in. Volume and the wider trend are what most traders check alongside it, because a move past a level on thin participation looks identical to one on heavy participation until the volume is examined.",
    related: { href: "/best-stocks-for/breakouts", label: "Today's biggest movers, score-filtered" },
    see: ["momentum", "relative-volume", "volume", "trend"],
  },

  /* ────────────────────────── Relative performance ───────────────────────── */
  {
    slug: "relative-strength",
    term: "Relative strength",
    aliases: ["RS", "relative performance"],
    category: "Relative performance",
    title: "What Is Relative Strength? Definition for Traders | Tapeline Glossary",
    description:
      "Relative strength is a security's price change minus a benchmark's over the same period. How it is measured, and why it can read high while price falls.",
    h1: "Relative strength",
    definition:
      "Relative strength is a difference, not a standalone reading: a security's price change over a period, minus a benchmark's price change over exactly the same period. It answers whether a security moved by more or less than the market it trades in.",
    measured:
      "Take the security's percentage change over a chosen horizon. Take the benchmark's percentage change over that identical horizon. Subtract the second from the first. Running the calculation across several horizons — a quarter, half a year, a year — and combining them keeps a single noisy quarter from dominating the result.",
    matters:
      "Because it is a difference between two numbers that can both be negative, the reading separates a security's own behaviour from the market's. A security can read well above the midpoint over a period in which its price fell, because the benchmark fell further. For a swing trader that distinction is the point: it identifies which securities are moving on something specific to them rather than on the whole market moving together.",
    tapeline:
      "Relative Strength is the second-heaviest factor in the Tapeline composite, after Trend. It measures the ticker's change minus a broad-market benchmark's change across three horizons. It is not sector-adjusted.",
    factor: "relative-strength",
    related: { href: "/how-it-works/relative-strength", label: "What the Relative Strength factor measures" },
    see: ["alpha", "beta", "rsi", "sector-rotation"],
  },
  {
    slug: "alpha",
    term: "Alpha",
    category: "Relative performance",
    title: "What Is Alpha in Investing? Plain-English Definition | Tapeline Glossary",
    description:
      "Alpha is the part of a return not explained by the benchmark's move over the same period. How it is computed and why the window and benchmark choice decide it.",
    h1: "Alpha",
    definition:
      "Alpha is the part of a return that is not explained by the benchmark's move over the same period — the difference between what a holding did and what its benchmark did while it was held. In its stricter form the benchmark's contribution is scaled by beta before the subtraction.",
    measured:
      "Measure the return over a defined window. Measure the benchmark's return over that identical window. Subtract. The stricter version multiplies the benchmark return by the holding's beta first, so that a security which simply moves more than the market is not credited for the extra movement. Both the window and the benchmark are choices, and changing either changes the answer.",
    matters:
      "Alpha is the vocabulary for 'did this do anything the market did not already do', which is the only version of the question that survives a market-wide move up or down. The measurement caution for a swing trader is that alpha over a single short window is mostly noise — one session's difference against a benchmark tells you almost nothing, and the number stabilises only across a large sample.",
    tapeline:
      "Tapeline's public scorecard records each daily top-10 pick's realised next-session return alongside the benchmark's over the same session, with the sample size disclosed and losing days published unedited.",
    related: { href: "/scorecard", label: "The public scorecard record" },
    see: ["beta", "relative-strength", "drawdown", "composite-score"],
  },
  {
    slug: "beta",
    term: "Beta",
    category: "Relative performance",
    title: "What Is Beta in Stocks? Plain-English Definition | Tapeline Glossary",
    description:
      "Beta measures how much a security has moved for a given move in its benchmark. How it is estimated, and why it is a historical statistic, not a property.",
    h1: "Beta",
    definition:
      "Beta measures how much a security's price has historically moved for a given move in its benchmark. A beta of one describes a security that has moved roughly in line with the benchmark; above one describes larger swings in both directions, below one describes smaller ones.",
    measured:
      "Regress the security's periodic returns against the benchmark's over a sample window. The slope of that regression is beta. The window length and the return interval — daily, weekly, monthly — both change the estimate, which is why published betas for the same security differ between data providers.",
    matters:
      "Beta is the standard adjustment for comparing securities that move at different amplitudes: without it, a security that swings twice as hard as the market will look remarkable in any up period and alarming in any down one, purely because of its amplitude. The caution is that beta is an estimate from a past sample, not a fixed property — it drifts as a company's business, leverage and shareholder base change.",
    related: { href: "/how-it-works/relative-strength", label: "How Tapeline compares against a benchmark" },
    see: ["alpha", "relative-strength", "volatility", "drawdown"],
  },
  {
    slug: "relative-volume",
    term: "Relative volume",
    aliases: ["RVOL"],
    category: "Relative performance",
    title: "What Is Relative Volume? RVOL Definition | Tapeline Glossary",
    description:
      "Relative volume compares today's traded volume to a security's own typical volume. How the baseline is built and what an elevated reading does and does not say.",
    h1: "Relative volume",
    definition:
      "Relative volume compares the volume traded in a session to that same security's own average volume over a recent window, expressed as a multiple. A reading of one describes a typical session for that security.",
    measured:
      "Divide the session's traded volume by the average session volume over a lookback window — commonly a few weeks to a few months. Intraday versions compare volume so far today against the average volume by the same time of day, which is necessary because volume is heavily concentrated near the open and the close.",
    matters:
      "Raw volume is not comparable between securities — a mega-cap's quiet session dwarfs a small-cap's busiest one — so normalising against a security's own baseline is what makes participation legible across a scan. Swing traders read it as a participation check on any price event: the same percentage move on ordinary volume and on many times ordinary volume are different events. An elevated reading says more people traded, not which direction they were leaning.",
    related: { href: "/app/scanner", label: "The live scanner" },
    see: ["volume", "average-dollar-volume", "breakout", "bid-ask-spread"],
  },
  {
    slug: "sector-rotation",
    term: "Sector rotation",
    category: "Relative performance",
    title: "What Is Sector Rotation? Definition for Traders | Tapeline Glossary",
    description:
      "Sector rotation describes leadership shifting between sectors over weeks or months. How rotation is observed, and why it is identified only in hindsight.",
    h1: "Sector rotation",
    definition:
      "Sector rotation describes a shift in which parts of the market are moving most, as capital concentrates in some sectors and thins out of others over weeks or months. It is an observation about the dispersion of returns across sectors, not a schedule.",
    measured:
      "Compute each sector's return over a rolling window — usually via a sector index or a sector ETF — and rank them. Rotation is visible as a change in that ranking over time, and as a widening or narrowing of the gap between the top and bottom of it. There is no single agreed window, so the picture depends on the one chosen.",
    matters:
      "Sector membership explains a large share of any individual security's movement, so knowing which sectors have been moving separates company-specific behaviour from a sector-wide move that lifts or drags every name in it. The caution worth stating: rotation is identified after it is under way. A ranking of the last quarter is a description of the last quarter, and the popular idea that sectors rotate in a fixed order through an economic cycle is a stylised model, not a measured regularity.",
    tapeline:
      "Tapeline publishes a live per-sector ranking of the scored universe, and the Relative Strength factor is measured against a single broad-market benchmark rather than a sector one — so a whole sector moving together shows up in every name in it.",
    related: { href: "/sectors", label: "Live sector rankings" },
    see: ["relative-strength", "market-breadth", "market-regime", "beta"],
  },

  /* ──────────────────────────────  Fundamentals ─────────────────────────── */
  {
    slug: "piotroski-f-score",
    term: "Piotroski F-Score",
    aliases: ["F-Score"],
    category: "Fundamentals",
    title: "What Is the Piotroski F-Score? Definition | Tapeline Glossary",
    description:
      "The Piotroski F-Score is a nine-point checklist of accounting tests scored one point each. What the nine tests cover and what the total does and does not mean.",
    h1: "Piotroski F-Score",
    definition:
      "The Piotroski F-Score is a nine-point checklist of accounting tests, each scored one point if the company passes and zero if it does not. The total runs from zero to nine and summarises whether a set of reported financial trends improved or deteriorated between periods.",
    measured:
      "The nine binary tests group into three families: profitability — positive net income, positive operating cash flow, an improving return on assets, and operating cash flow exceeding net income; leverage and liquidity — falling long-term debt, an improving current ratio, and no new share issuance; and operating efficiency — an improving gross margin and an improving asset turnover. Each passed test scores one point.",
    matters:
      "The F-Score is worth knowing because it is the clearest illustration of a whole class of scoring approaches: reduce a set of reported figures to pass/fail tests, then count. That design makes it transparent and reproducible from filings alone, and also blunt — it treats a marginal pass and a large one identically, and it moves only when new financials are filed, which for most companies means it is static for weeks at a time.",
    tapeline:
      "Not used by Tapeline. The Fundamentals factor reads reported profit margin, return on equity, earnings-per-share growth, revenue growth and an earnings multiple, each placed on a common scale.",
    factor: "fundamentals",
    related: { href: "/how-it-works/fundamentals", label: "What the Fundamentals factor measures" },
    see: ["return-on-equity", "profit-margin", "free-cash-flow", "price-to-earnings"],
  },
  {
    slug: "price-to-earnings",
    term: "Price-to-earnings ratio",
    aliases: ["P/E ratio", "earnings multiple", "PE"],
    category: "Fundamentals",
    title: "What Is the P/E Ratio? Earnings Multiple Explained | Tapeline Glossary",
    description:
      "The price-to-earnings ratio is share price divided by earnings per share. How trailing and forward versions differ and why the ratio is not comparable across sectors.",
    h1: "Price-to-earnings ratio (P/E)",
    definition:
      "The price-to-earnings ratio is a company's share price divided by its earnings per share. It expresses how much is being paid per unit of reported annual earnings, and is the most widely quoted of the earnings multiples.",
    measured:
      "Divide the current share price by earnings per share. The trailing version uses the last four reported quarters, which are facts. The forward version uses an analyst estimate of the next four, which is a projection and moves as estimates are revised. A company with negative earnings has no meaningful ratio, so the measurement simply does not exist for it.",
    matters:
      "The multiple is a compact way to compare what is being paid for reported earnings across companies in the same business. Its limits are the important part: it is not comparable across sectors, because durable differences in growth rate, capital intensity and accounting treatment mean the ordinary range in one industry is unusual in another. It also says nothing about debt, since it prices equity alone.",
    tapeline:
      "An earnings multiple is one of the five inputs to Tapeline's Fundamentals factor, placed on a common scale alongside margin, return on equity, and earnings and revenue growth.",
    factor: "fundamentals",
    related: { href: "/how-it-works/fundamentals", label: "What the Fundamentals factor measures" },
    see: ["eps-growth", "return-on-equity", "profit-margin", "piotroski-f-score"],
  },
  {
    slug: "return-on-equity",
    term: "Return on equity",
    aliases: ["ROE"],
    category: "Fundamentals",
    title: "What Is Return on Equity? ROE Definition | Tapeline Glossary",
    description:
      "Return on equity is net income divided by shareholders' equity. How it is computed, why leverage inflates it, and what a negative equity base does to it.",
    h1: "Return on equity (ROE)",
    definition:
      "Return on equity is net income divided by shareholders' equity, expressed as a rate. It describes how much accounting profit a company produced per unit of the equity capital its balance sheet reports.",
    measured:
      "Divide net income for a period by shareholders' equity, usually averaged across the start and end of that period. Every input comes from the filed financial statements, so the measurement is exactly as current as the last filing and does not move between reports.",
    matters:
      "ROE is one of the standard summaries of capital efficiency: two companies earning the same profit on very different equity bases are doing genuinely different things. Two mechanical cautions matter more than most. Leverage raises ROE without any improvement in the underlying business, because debt-funded assets produce income while shrinking the equity denominator. And large buybacks or accumulated losses can drive equity toward zero or below, at which point the ratio becomes erratic or meaningless.",
    tapeline:
      "Return on equity is one of the five inputs to Tapeline's Fundamentals factor. The same broad bands are applied to every company regardless of sector, which the methodology page describes plainly as a blunt instrument.",
    factor: "fundamentals",
    related: { href: "/how-it-works/fundamentals", label: "What the Fundamentals factor measures" },
    see: ["profit-margin", "price-to-earnings", "free-cash-flow", "piotroski-f-score"],
  },
  {
    slug: "profit-margin",
    term: "Profit margin",
    aliases: ["net margin", "gross margin", "operating margin"],
    category: "Fundamentals",
    title: "What Is Profit Margin? Gross, Operating and Net | Tapeline Glossary",
    description:
      "Profit margin is profit as a share of revenue. How the gross, operating and net versions differ and why margins are only comparable within an industry.",
    h1: "Profit margin",
    definition:
      "Profit margin is profit expressed as a share of revenue. Which profit is used defines which margin it is: gross margin uses revenue minus the direct cost of goods, operating margin subtracts operating expenses as well, and net margin is what remains after interest, tax and everything else.",
    measured:
      "Divide the relevant profit line from the income statement by revenue for the same period. All three versions come from the same filed statement, so all three refresh on filing cadence rather than continuously, and all three are restated when the underlying financials are.",
    matters:
      "The three levels answer different questions, and reading the wrong one is the common error: gross margin describes the economics of the product itself, operating margin describes the business built around it, and net margin describes what the capital structure and tax position leave behind. Margins are only comparable within an industry — a software company and a grocer operate at structurally different levels for reasons that have nothing to do with how well either is run. The direction of a margin over several periods usually carries more information than its level in any one.",
    tapeline:
      "Profit margin is one of the five inputs to Tapeline's Fundamentals factor. The factor is not sector-relative, which the methodology page states as a known limitation.",
    factor: "fundamentals",
    related: { href: "/how-it-works/fundamentals", label: "What the Fundamentals factor measures" },
    see: ["return-on-equity", "revenue-growth", "free-cash-flow", "price-to-earnings"],
  },
  {
    slug: "eps-growth",
    term: "EPS growth",
    aliases: ["earnings per share growth", "earnings growth"],
    category: "Fundamentals",
    title: "What Is EPS Growth? Earnings Per Share Explained | Tapeline Glossary",
    description:
      "EPS growth is the change in earnings per share between reported periods. How share count affects it, and why one quarter's figure is a weak measurement.",
    h1: "EPS growth",
    definition:
      "Earnings per share is net income divided by the number of shares outstanding, and EPS growth is the change in that figure between two reported periods. It combines how profit changed with how the share count changed.",
    measured:
      "Compare earnings per share in one reported period to the same figure in an earlier one — usually the same quarter a year before, which removes seasonality. The diluted version counts shares that would exist if outstanding options and convertibles were exercised, and is the more conservative of the two.",
    matters:
      "EPS growth is a per-owner measurement rather than a company-wide one, which is the reason to prefer it over raw profit growth: buybacks shrink the denominator and lift the figure without any change in the business, while share issuance does the reverse. The other caution is sample size — a single quarter's growth is heavily exposed to one-off items, so the direction across several periods is the more stable reading.",
    tapeline:
      "Earnings-per-share growth between reported periods is one of the five inputs to Tapeline's Fundamentals factor.",
    factor: "fundamentals",
    related: { href: "/how-it-works/fundamentals", label: "What the Fundamentals factor measures" },
    see: ["revenue-growth", "price-to-earnings", "profit-margin", "earnings-surprise"],
  },
  {
    slug: "revenue-growth",
    term: "Revenue growth",
    aliases: ["sales growth", "top-line growth"],
    category: "Fundamentals",
    title: "What Is Revenue Growth? Top-Line Definition | Tapeline Glossary",
    description:
      "Revenue growth is the change in reported sales between periods. Why it is harder to flatter than profit growth, and where acquisitions distort it.",
    h1: "Revenue growth",
    definition:
      "Revenue growth is the change in a company's reported sales between two periods, expressed as a rate. It sits at the top of the income statement, before any cost, interest or tax line has been applied.",
    measured:
      "Compare revenue in one reported period to revenue in an earlier one, most commonly the same quarter a year earlier so that seasonal patterns cancel. Organic growth strips out revenue acquired through acquisitions and the effect of currency moves; headline growth does not, and the two can differ substantially.",
    matters:
      "Revenue is the hardest of the major lines to flatter, because it sits above every discretionary cost and accounting choice further down the statement. That makes its direction a useful cross-check on profit growth: profit rising while revenue is flat describes cost reduction, which is finite, rather than expansion. The main distortion to watch for is acquisition — a company can report substantial headline growth while its existing business is static.",
    tapeline:
      "Revenue growth between reported periods is one of the five inputs to Tapeline's Fundamentals factor.",
    factor: "fundamentals",
    related: { href: "/how-it-works/fundamentals", label: "What the Fundamentals factor measures" },
    see: ["eps-growth", "profit-margin", "free-cash-flow", "market-capitalisation"],
  },
  {
    slug: "free-cash-flow",
    term: "Free cash flow",
    aliases: ["FCF"],
    category: "Fundamentals",
    title: "What Is Free Cash Flow? FCF Definition | Tapeline Glossary",
    description:
      "Free cash flow is operating cash flow minus capital expenditure. Why it differs from reported profit and what a persistent gap between the two indicates.",
    h1: "Free cash flow",
    definition:
      "Free cash flow is the cash a business generated from operations after subtracting the capital spending needed to maintain and grow its asset base. It measures cash movement rather than accounting profit.",
    measured:
      "Take cash flow from operations as reported on the cash-flow statement and subtract capital expenditure. Both figures come from the same filed statement. Definitions vary at the edges — some exclude acquisitions, some subtract lease payments — so figures from different sources are not always comparable.",
    matters:
      "Profit and cash diverge for legitimate reasons: revenue can be recognised before payment arrives, and large asset purchases hit cash immediately while reaching profit gradually as depreciation. Tracking both is how that divergence becomes visible. A company reporting profit while consistently consuming cash is describing a working-capital or capital-intensity situation that the income statement alone does not show.",
    related: { href: "/how-it-works/fundamentals", label: "What the Fundamentals factor measures" },
    see: ["profit-margin", "return-on-equity", "piotroski-f-score", "revenue-growth"],
  },
  {
    slug: "earnings-surprise",
    term: "Earnings surprise",
    aliases: ["earnings beat", "earnings miss"],
    category: "Fundamentals",
    title: "What Is an Earnings Surprise? Definition | Tapeline Glossary",
    description:
      "An earnings surprise is the gap between reported results and the analyst consensus. How consensus is built and why the reaction often ignores the headline number.",
    h1: "Earnings surprise",
    definition:
      "An earnings surprise is the difference between a company's reported result and the consensus analyst estimate for that period. Reporting above the estimate is conventionally called a beat, reporting below it a miss.",
    measured:
      "Subtract the consensus estimate from the reported figure, usually on earnings per share and often on revenue as well. Consensus is a compiled average of individual analyst estimates, so it moves as analysts revise, and the same result can be a beat against one vendor's compilation and in line with another's.",
    matters:
      "The measurement is a comparison against expectations, not against the prior period, which is why it is possible to report lower profit than last year and still register a beat. For a swing trader the practical point is that the price reaction frequently tracks the forward guidance issued alongside the result rather than the headline number, and that the reaction is concentrated in the sessions immediately around the report — which is why earnings dates are worth knowing before a multi-day holding period, in either direction.",
    related: { href: "/app/earnings", label: "The earnings calendar" },
    see: ["eps-growth", "revenue-growth", "volatility", "gap"],
  },

  /* ────────────────────────────  Market structure ───────────────────────── */
  {
    slug: "float",
    term: "Float",
    aliases: ["free float", "public float", "shares outstanding"],
    category: "Market structure",
    title: "What Is Float in Stocks? Free Float Explained | Tapeline Glossary",
    description:
      "Float is the count of shares actually available to trade, excluding closely held blocks. How it differs from shares outstanding and why a small float moves prices.",
    h1: "Float",
    definition:
      "Float is the number of a company's shares that are actually available to trade in the open market. It is shares outstanding minus the blocks that are closely held — insider holdings, founder stakes, and other restricted positions that do not circulate.",
    measured:
      "Start from total shares outstanding as reported in filings, then subtract restricted and closely held blocks, which are themselves disclosed in ownership filings. Vendors apply the exclusions slightly differently, so published float figures for the same company vary between data sources.",
    matters:
      "Float is the supply side of price formation. The same dollar amount of buying pressure moves a security with a small tradable supply much further than one with a large one, which is why small-float securities show larger percentage swings on ordinary-looking order flow. It is also the denominator underneath short interest, so a short position that looks modest against shares outstanding can be large against float.",
    tapeline:
      "Tapeline's Momentum methodology notes that low-float tickers produce large readings from small dollar flows, and that a liquidity floor is applied to the ranked scanner and the public scorecard for that reason.",
    related: { href: "/short-squeeze-scanner", label: "The squeeze scanner" },
    see: ["short-interest", "short-squeeze", "average-dollar-volume", "market-capitalisation"],
  },
  {
    slug: "short-interest",
    term: "Short interest",
    category: "Market structure",
    title: "What Is Short Interest? Definition and Reporting Lag | Tapeline Glossary",
    description:
      "Short interest is the count of shares sold short and not yet closed. How it is reported, how often, and why the figure is always several days old.",
    h1: "Short interest",
    definition:
      "Short interest is the number of a security's shares that have been sold short and not yet bought back. It is usually quoted as a percentage — of shares outstanding, or of float, which produces a higher figure for the same position.",
    measured:
      "US exchanges collect short positions from member firms on scheduled settlement dates and publish the aggregate, historically twice a month. The figure is compiled as of a specific date and published after a lag of several business days, so the number in circulation always describes a position that existed some time ago.",
    matters:
      "Short interest describes the size of the position that has to be closed by buying, which is why it is tracked alongside volume: a large position relative to typical daily trading takes many sessions to unwind. Two cautions matter. The reporting lag means the figure can be badly stale during exactly the fast-moving periods when traders look at it. And a large position is not evidence of a coming move in either direction — some of it is hedging against convertible bonds or options books rather than a directional view.",
    tapeline:
      "Short-interest data feeds Tapeline's squeeze detection, which is a separate product surface from the composite score — it is not one of the six scoring factors.",
    related: { href: "/short-squeeze-scanner", label: "The squeeze scanner" },
    see: ["days-to-cover", "short-squeeze", "float", "volume"],
  },
  {
    slug: "days-to-cover",
    term: "Days to cover",
    aliases: ["short ratio", "short interest ratio"],
    category: "Market structure",
    title: "What Is Days to Cover? Short Interest Ratio | Tapeline Glossary",
    description:
      "Days to cover is short interest divided by average daily volume. What the ratio estimates, and the assumption that makes it only an approximation.",
    h1: "Days to cover",
    definition:
      "Days to cover is short interest divided by average daily trading volume. It estimates how many sessions of ordinary trading it would take for the whole short position to be bought back, if that buying were the only activity.",
    measured:
      "Divide the reported short interest by average daily volume over a recent window, commonly a month. Both inputs are backward-looking, and the short-interest figure carries its own reporting lag, so the ratio inherits the staleness of the older of the two.",
    matters:
      "The ratio normalises a raw short position against how much a security actually trades, which is what makes it comparable between a mega-cap and a small-cap. Its built-in assumption is also its main weakness: it implicitly treats future volume as equal to past volume, and volume expands sharply in exactly the conditions where the ratio is being consulted. A high reading describes a position that is large relative to recent liquidity — nothing more.",
    tapeline:
      "Days to cover is one of the inputs to Tapeline's squeeze detection, a separate surface from the six-factor composite score.",
    related: { href: "/short-squeeze-scanner", label: "The squeeze scanner" },
    see: ["short-interest", "short-squeeze", "volume", "float"],
  },
  {
    slug: "short-squeeze",
    term: "Short squeeze",
    aliases: ["squeeze"],
    category: "Market structure",
    title: "What Is a Short Squeeze? Definition and Mechanics | Tapeline Glossary",
    description:
      "A short squeeze describes rising prices forcing short positions to be closed by buying, which adds further buying. The mechanics, conditions and limits.",
    h1: "Short squeeze",
    definition:
      "A short squeeze describes a sequence in which a rising price forces holders of short positions to close them, and closing a short position requires buying — which adds to the buying pressure that is already pushing the price up. The word names the feedback mechanism, not a prediction that one will occur.",
    measured:
      "There is no single measurement, which is worth stating plainly. Analysis of squeeze conditions combines short interest relative to float, days to cover, the cost of borrowing the shares, and the tradable supply itself. Those describe the conditions under which the mechanism could operate; whether it does depends on price action that has not happened yet.",
    matters:
      "Understanding the mechanism explains why some price moves accelerate far past what the underlying news appears to justify: closing a short is a purchase, so the mechanism is self-reinforcing while it runs. The corresponding caution is symmetry — the same conditions that allow a squeeze to run allow it to unwind just as fast once the forced buying is exhausted, and the conditions themselves are present far more often than squeezes actually occur.",
    tapeline:
      "Tapeline runs squeeze detection as its own surface, available on Pro and above. It reads short interest, days to cover and float; it is not one of the six factors in the composite score.",
    related: { href: "/short-squeeze-scanner", label: "The squeeze scanner" },
    see: ["short-interest", "days-to-cover", "float", "volatility"],
  },
  {
    slug: "volume",
    term: "Volume",
    category: "Market structure",
    title: "What Is Trading Volume? Definition for Traders | Tapeline Glossary",
    description:
      "Volume is the number of shares traded in a period. How it is counted, when it clusters, and why it measures participation rather than direction.",
    h1: "Volume",
    definition:
      "Volume is the number of shares that changed hands over a period. Every trade has a buyer and a seller, so volume counts transactions — it does not measure net buying or net selling.",
    measured:
      "Sum the shares executed across all venues over the period. Consolidated volume aggregates every exchange and reporting facility; single-venue figures are lower and not comparable to it. Volume is heavily concentrated around the opening and closing auctions, so any intraday comparison has to be against the same time of day.",
    matters:
      "Volume is the participation dimension underneath every price move: the same percentage change on very light and very heavy trading are different events, because one describes a price agreed by few participants and the other a price agreed by many. The persistent misreading is treating volume as directional. A session with heavy volume and a falling price tells you many participants transacted, not that sellers outnumbered buyers — by construction, they cannot.",
    related: { href: "/app/scanner", label: "The live scanner" },
    see: ["relative-volume", "average-dollar-volume", "accumulation-distribution", "breakout"],
  },
  {
    slug: "average-dollar-volume",
    term: "Average dollar volume",
    aliases: ["ADV", "dollar volume", "liquidity"],
    category: "Market structure",
    title: "What Is Average Dollar Volume? Liquidity Measure | Tapeline Glossary",
    description:
      "Average dollar volume is shares traded multiplied by price, averaged over recent sessions. Why it is the better liquidity screen than share volume alone.",
    h1: "Average dollar volume",
    definition:
      "Average dollar volume is the value traded in a typical session — shares traded multiplied by price — averaged over a recent window. It is the standard practical measure of how much capital a security can absorb without the trade itself moving the price.",
    measured:
      "For each session in the window, multiply volume by a representative price, then average across the window. Twenty sessions is a common choice. Using value rather than share count is what makes the figure comparable: a million shares of a low-priced security and a million shares of a high-priced one are entirely different amounts of capital.",
    matters:
      "Dollar volume is the constraint that decides which securities a given trader can realistically transact in, and it is the reason a scan result can be arithmetically correct and practically unusable. Thin securities also produce noisy inputs for everything else — period returns, relative-strength differences and momentum readings all become erratic when few trades set the price.",
    tapeline:
      "Tapeline applies a liquidity floor to the ranked scanner and the public scorecard for this reason. The floor can be switched off on the scanner to browse the full scored universe.",
    related: { href: "/app/scanner", label: "The live scanner" },
    see: ["volume", "relative-volume", "bid-ask-spread", "float"],
  },
  {
    slug: "bid-ask-spread",
    term: "Bid-ask spread",
    aliases: ["spread"],
    category: "Market structure",
    title: "What Is the Bid-Ask Spread? Definition | Tapeline Glossary",
    description:
      "The bid-ask spread is the gap between the highest bid and the lowest offer. How it is quoted, what widens it, and why it is a real transaction cost.",
    h1: "Bid-ask spread",
    definition:
      "The bid-ask spread is the difference between the highest price a buyer is currently willing to pay and the lowest price a seller is currently willing to accept. It is the immediate cost of transacting rather than waiting.",
    measured:
      "Subtract the best bid from the best offer at a moment in time. Quoting it as a percentage of the midpoint makes it comparable between securities at different price levels. It is not a fixed attribute — it widens around news, at the open and close, and in thinly traded securities, and it is quoted for a specific size, so a larger order can transact outside the displayed quote.",
    matters:
      "The spread is a transaction cost that is paid on entry and again on exit, and it is invisible in any performance figure computed from closing prices. On a multi-day holding period in a liquid security it is usually a rounding error; in a thin one, or at high turnover, it accumulates into a material drag that back-of-the-envelope arithmetic on closes will not show.",
    related: { href: "/limitations", label: "What Tapeline does not model" },
    see: ["average-dollar-volume", "volume", "float", "volatility"],
  },
  {
    slug: "market-capitalisation",
    term: "Market capitalisation",
    aliases: ["market cap", "market capitalization"],
    category: "Market structure",
    title: "What Is Market Capitalisation? Market Cap Explained | Tapeline Glossary",
    description:
      "Market capitalisation is share price multiplied by shares outstanding. What it measures, why it is not the price of the company, and how the size bands work.",
    h1: "Market capitalisation",
    definition:
      "Market capitalisation is a company's share price multiplied by its total shares outstanding. It is the market value of the equity — not the value of the whole business, because it excludes debt and excludes cash.",
    measured:
      "Multiply the current share price by shares outstanding as reported in the most recent filing. A float-adjusted version uses only the tradable shares, which is what most index providers weight by. Enterprise value is the related figure that adds debt and subtracts cash to describe the whole capital structure.",
    matters:
      "Size is one of the strongest determinants of how a security behaves: larger companies have more analyst coverage, deeper trading, tighter spreads and smaller typical percentage swings, while smaller ones have the reverse of each. The conventional bands — large, mid, small and micro — are useful shorthand with no official boundaries. The common misreading is treating market cap as what it would cost to acquire the company; that figure is enterprise value.",
    related: { href: "/stocks", label: "The full scored universe" },
    see: ["float", "average-dollar-volume", "price-to-earnings", "beta"],
  },
  {
    slug: "gap",
    term: "Gap",
    aliases: ["gap up", "gap down", "overnight gap"],
    category: "Market structure",
    title: "What Is a Gap in Stock Prices? Definition | Tapeline Glossary",
    description:
      "A gap is a jump between one session's close and the next session's open with no trading in between. Why gaps form and what they mean for stop orders.",
    h1: "Gap",
    definition:
      "A gap is a discontinuity between one session's closing price and the next session's opening price, where the market reopens at a level with no trading in between. Gaps up and gaps down are named for the direction of the jump.",
    measured:
      "Subtract the previous session's close from the current session's open. Expressing the difference as a percentage of the previous close makes gaps comparable across securities. The measurement is exact and unambiguous — unlike most chart concepts, there is nothing to draw or choose.",
    matters:
      "Gaps exist because information keeps arriving while the market is closed, and the reopening price is where the accumulated overnight orders clear. For a swing trader holding across sessions this is the structural exposure worth understanding: a stop order resting below the market does not execute at its trigger price when the market reopens beneath it — it becomes an order at the reopening level, wherever that is. Scheduled events like earnings reports concentrate that exposure into known dates.",
    related: { href: "/legal/risk", label: "Risk disclosure" },
    see: ["earnings-surprise", "volatility", "stop-loss", "breakout"],
  },

  /* ───────────────────────────  Disclosure & flow ───────────────────────── */
  {
    slug: "sec-form-4",
    term: "SEC Form 4",
    aliases: ["Form 4", "insider transaction", "insider buying"],
    category: "Disclosure & flow",
    title: "What Is SEC Form 4? Insider Transaction Filing | Tapeline Glossary",
    description:
      "SEC Form 4 is the filing that reports a corporate insider's transaction in their own company's shares. Who files, the deadline, and what the filing omits.",
    h1: "SEC Form 4",
    definition:
      "Form 4 is the filing corporate insiders submit to the SEC to report transactions in their own company's securities. Insiders for this purpose are officers, directors, and holders of more than ten percent of a registered class of shares.",
    measured:
      "Each filing states the transaction date, the type of transaction by code, the number of shares, the price, and the resulting holding. It is due within two business days of the transaction. Aggregating filings across a window and netting purchases against sales by value is the standard way to summarise insider activity for a company.",
    matters:
      "Form 4 is one of the few genuinely non-public-until-filed disclosures available to retail traders, and it reports completed transactions rather than opinions. The interpretation problem is that many filings carry no view at all: sales scheduled months ahead under a pre-arranged trading plan, option exercises, vesting events and sales made purely to cover tax withholding all arrive as Form 4 filings and look like ordinary transactions. A filing records that a transaction happened, never why.",
    tapeline:
      "Form 4 filings are the sole input to Tapeline's Smart Money factor, netted by value over a recent rolling window. A ticker with no filings in the window has no reading, and the composite substitutes a mid-range value rather than treating the absence as negative.",
    factor: "smart-money",
    related: { href: "/insider-buying", label: "Recent insider buys" },
    see: ["form-13f", "congressional-trade-disclosure", "accumulation-distribution", "float"],
  },
  {
    slug: "form-13f",
    term: "13F filing",
    aliases: ["Form 13F", "institutional holdings"],
    category: "Disclosure & flow",
    title: "What Is a 13F Filing? Institutional Holdings Report | Tapeline Glossary",
    description:
      "A 13F is the quarterly report large institutional managers file listing US equity holdings. What it covers, the 45-day lag, and what it leaves out entirely.",
    h1: "13F filing",
    definition:
      "A 13F is a quarterly report that institutional investment managers exceeding a size threshold must file with the SEC, listing their US-listed equity positions as of the quarter end. It is the standard public window into large institutional holdings.",
    measured:
      "Managers report each covered position and its size as of the last day of the quarter, and the filing is due within 45 days of that date. The scope is limited: it covers long US-listed equity and some options, and excludes short positions, cash, bonds, commodities and non-US listings.",
    matters:
      "13F data is the most widely cited institutional-positioning source and the most widely over-read. Two structural limits do most of the damage. The report is a snapshot of one specific day, published up to 45 days later, so a position shown may have been opened and closed since. And because short positions are excluded entirely, a long holding shown in isolation may be one leg of a hedge whose other leg is invisible.",
    tapeline:
      "Not used by Tapeline. The Smart Money factor reads SEC Form 4 corporate-insider transactions only. The site previously described a 13F input; that was corrected in May 2026 and the correction is logged in the changelog.",
    related: { href: "/changelog", label: "The correction log" },
    see: ["sec-form-4", "congressional-trade-disclosure", "float", "market-capitalisation"],
  },
  {
    slug: "congressional-trade-disclosure",
    term: "Congressional trade disclosure",
    aliases: ["STOCK Act", "congress trading", "congressional trades"],
    category: "Disclosure & flow",
    title: "What Are Congressional Trade Disclosures? STOCK Act | Tapeline Glossary",
    description:
      "US legislators must disclose securities transactions under the STOCK Act. The reporting deadline, what the filings contain, and their known limitations.",
    h1: "Congressional trade disclosure",
    definition:
      "US members of Congress and certain senior staff are required to disclose transactions in securities under the STOCK Act. Each periodic transaction report names the security, the transaction type and the date, with the size given as a broad value band rather than an exact amount.",
    measured:
      "Filings are due within 45 days of a transaction. The disclosed amount is a range — the bands are wide, and the widest is open-ended at the top — so aggregating filings produces an estimate with substantial uncertainty rather than a precise total. Filings are submitted per person, so a household's activity may appear across several documents.",
    matters:
      "These filings are followed closely because of who is filing rather than because of demonstrated informational content, and the honest framing is that the data is interesting rather than proven. The mechanical limits are real: the reporting deadline is generous enough that a disclosure can arrive well after the market has already absorbed whatever prompted it, the value bands are too wide for position sizing to be inferred, and many transactions are executed by advisers under arrangements the filer does not direct.",
    tapeline:
      "Tapeline ingests congressional disclosures and publishes them as their own Premium feed. The methodology page for Smart Money states explicitly that this data is not an input to that sub-score today.",
    related: { href: "/congressional-trades", label: "Congressional trades feed" },
    see: ["sec-form-4", "form-13f", "accumulation-distribution", "composite-score"],
  },
  {
    slug: "accumulation-distribution",
    term: "Accumulation / distribution",
    aliases: ["accumulation", "distribution", "A/D line"],
    category: "Disclosure & flow",
    title: "What Is Accumulation / Distribution? Definition | Tapeline Glossary",
    description:
      "Accumulation and distribution describe buying or selling spread over time to limit price impact, and the volume studies built to infer it.",
    h1: "Accumulation / distribution",
    definition:
      "Accumulation describes building a position gradually over many sessions to avoid moving the price; distribution describes unwinding one the same way. The terms also name a family of volume-weighted indicators that attempt to infer which is happening from price and volume data alone.",
    measured:
      "The classic indicator weights each session's volume by where the close landed inside that session's high-to-low range, then accumulates the result into a running line. A close near the session high assigns most of the volume positively; a close near the low assigns it negatively. Variants substitute different weightings, but all of them infer intent from price location rather than observing it.",
    matters:
      "The underlying behaviour is real and is why large positions are worked over days rather than executed at once. The measurement is the weak part, and this is the honest framing: because every trade has a buyer and a seller, no indicator built from public price and volume data can identify who was accumulating. These studies produce an inference, not an observation. Filed disclosures like Form 4 are the only sources that report actual transactions by identified parties.",
    related: { href: "/insider-buying", label: "Disclosed insider transactions" },
    see: ["volume", "sec-form-4", "relative-volume", "float"],
  },

  /* ────────────────────────────────  Risk ──────────────────────────────── */
  {
    slug: "drawdown",
    term: "Drawdown",
    aliases: ["maximum drawdown", "max DD"],
    category: "Risk",
    title: "What Is Drawdown? Peak-to-Trough Definition | Tapeline Glossary",
    description:
      "Drawdown is the decline from a peak to the following trough, as a share of the peak. How maximum drawdown is measured and why recovery is asymmetric.",
    h1: "Drawdown",
    definition:
      "Drawdown is the decline from a peak value to the lowest point reached before a new peak, expressed as a share of that peak. Maximum drawdown is the largest such decline observed over a period.",
    measured:
      "Walk forward through the value series. At each point, compare the current value to the highest value seen so far and record the shortfall. The largest shortfall recorded is the maximum drawdown. Two further descriptors are commonly reported alongside it: the duration of the decline, and the time taken to regain the prior peak.",
    matters:
      "Drawdown describes the depth of a decline, which is the dimension a percentage change between two endpoints hides entirely. The arithmetic is also asymmetric in a way that is easy to state and easy to forget: recovering from a decline requires a larger percentage rise than the percentage fall that caused it, because the rise is computed from a smaller base. That asymmetry grows sharply as declines deepen.",
    related: { href: "/limitations", label: "What Tapeline does not model" },
    see: ["volatility", "average-true-range", "position-sizing", "stop-loss"],
  },
  {
    slug: "volatility",
    term: "Volatility",
    aliases: ["realised volatility", "implied volatility"],
    category: "Risk",
    title: "What Is Volatility? Realised vs Implied | Tapeline Glossary",
    description:
      "Volatility measures how much price varies around its own average. How realised and implied volatility are derived and why they answer different questions.",
    h1: "Volatility",
    definition:
      "Volatility measures how much a security's price varies around its own average over a period. It describes the size of movement, in both directions — a security that rises steeply and steadily is high-volatility, and volatility on its own says nothing about direction.",
    measured:
      "Realised volatility is the standard deviation of periodic returns over a past window, usually rescaled to a common time unit for comparability. Implied volatility is derived from current options prices by solving an options-pricing model for the volatility input that reproduces the observed price. The first summarises what happened; the second summarises what options are currently priced for.",
    matters:
      "Volatility is the scaling factor that makes different securities comparable: the same percentage move means something different in a security that typically moves a little and one that typically moves a lot. It is also the input underneath most position-sizing arithmetic. The known limits are that it clusters — calm periods and turbulent ones both persist, so a recent reading is a poor guide to a distant one — and that standard deviation treats upside and downside variation identically.",
    related: { href: "/market-regime", label: "The live market regime view" },
    see: ["average-true-range", "vix", "drawdown", "beta"],
  },
  {
    slug: "average-true-range",
    term: "Average true range",
    aliases: ["ATR"],
    category: "Risk",
    title: "What Is Average True Range? ATR Definition | Tapeline Glossary",
    description:
      "ATR is the average size of a security's daily range, including overnight gaps. How true range is defined and why ATR is quoted in dollars, not percent.",
    h1: "Average true range (ATR)",
    definition:
      "Average true range is the average size of a security's daily trading range over a recent window, where the range is defined to include any overnight gap. It expresses typical daily movement in the security's own price units.",
    measured:
      "True range for a session is the largest of three quantities: the session's high minus its low, the high minus the previous close, and the previous close minus the low. Including the previous close is what captures a gap. Averaging true range across a window — fourteen sessions is the conventional choice — gives ATR.",
    matters:
      "ATR is the practical answer to 'how much does this security normally move in a day', which is the quantity that makes distances on a chart comparable between securities at different prices and volatility levels. It is quoted in dollars rather than as a percentage, so comparing ATR across securities requires dividing by price first — a step that is easy to skip and produces nonsense when it is.",
    related: { href: "/limitations", label: "What Tapeline does not model" },
    see: ["volatility", "drawdown", "gap", "position-sizing"],
  },
  {
    slug: "position-sizing",
    term: "Position sizing",
    category: "Risk",
    title: "What Is Position Sizing? Definition | Tapeline Glossary",
    description:
      "Position sizing is the decision of how much to commit to a single holding. The common frameworks, and why Tapeline does not and cannot set sizes.",
    h1: "Position sizing",
    definition:
      "Position sizing is the decision of how much capital to commit to any single holding. It is separate from the decision of what to hold, and it is the input that determines what any individual outcome does to the whole.",
    measured:
      "Common frameworks express size as a fixed fraction of total capital, or scale size so that a defined adverse move costs a constant amount — which makes the size inversely proportional to the security's typical movement, often measured with ATR. Each framework is a convention with tradeoffs, not a derived optimum.",
    matters:
      "Sizing determines how much any single outcome matters, which is why two people acting on identical information can end up in entirely different situations. It is also the reason drawdown arithmetic is worth understanding before it is needed rather than after. Appropriate sizing depends on circumstances specific to each person — Tapeline has no knowledge of any of them, does not model them, and does not suggest sizes.",
    related: { href: "/legal/risk", label: "Risk disclosure" },
    see: ["drawdown", "average-true-range", "volatility", "stop-loss"],
  },
  {
    slug: "stop-loss",
    term: "Stop-loss order",
    aliases: ["stop order", "stop"],
    category: "Risk",
    title: "What Is a Stop-Loss Order? Definition and Limits | Tapeline Glossary",
    description:
      "A stop-loss is a resting order that activates when price reaches a trigger. How stop-market and stop-limit differ, and why neither fixes an exit price.",
    h1: "Stop-loss order",
    definition:
      "A stop-loss is a resting instruction to a broker that becomes active when price reaches a specified trigger level. It is an order type, not a guarantee of an exit price.",
    measured:
      "There are two common forms and the difference matters. A stop-market order becomes a market order once triggered, so it transacts at whatever the next available price is. A stop-limit order becomes a limit order, which will not transact below a specified price — and therefore may not transact at all if price moves through the level quickly.",
    matters:
      "Stops are how a defined exit level is expressed mechanically instead of relying on being present and deciding in the moment. The limitation worth understanding before relying on one is that a trigger level is not an execution level: when a market reopens below a resting stop after an overnight gap, the order activates at the reopening price, not at the trigger. Neither order type removes gap exposure, and the two failure modes are opposites — one transacts at an unexpected price, the other may not transact.",
    related: { href: "/legal/risk", label: "Risk disclosure" },
    see: ["gap", "position-sizing", "drawdown", "bid-ask-spread"],
  },

  /* ────────────────────────────  Macro & regime ─────────────────────────── */
  {
    slug: "vix",
    term: "VIX",
    aliases: ["volatility index", "fear index"],
    category: "Macro & regime",
    title: "What Is the VIX? Volatility Index Explained | Tapeline Glossary",
    description:
      "The VIX is an index of expected 30-day volatility derived from S&P 500 options prices. What it measures, and the two things it is routinely misread as.",
    h1: "VIX",
    definition:
      "The VIX is an index of the volatility expected over the next 30 days in the S&P 500, derived from the prices of that index's options. It is quoted as an annualised percentage and is often described as a fear gauge, which is loose but not baseless.",
    measured:
      "The calculation aggregates the prices of a wide strip of index options across strikes at two nearby expiries, and interpolates between them to produce a constant 30-day horizon. The inputs are current option prices, so the index reflects what participants are paying for optionality right now, not a survey and not a forecast anyone has published.",
    matters:
      "The VIX summarises expected market-wide movement in one number, which is why it is the standard shorthand for market conditions. Two misreadings are worth naming. It is not directional — it measures expected size of movement, not expected direction, though in practice it rises most when the index falls because that is when demand for downside protection concentrates. And it is not a forecast of the level of the index; it is a price for expected movement, which can be systematically above or below what subsequently occurs.",
    related: { href: "/market-regime", label: "The live market regime view" },
    see: ["volatility", "market-regime", "market-breadth", "beta"],
  },
  {
    slug: "market-breadth",
    term: "Market breadth",
    aliases: ["breadth", "advance-decline"],
    category: "Macro & regime",
    title: "What Is Market Breadth? Advance-Decline Explained | Tapeline Glossary",
    description:
      "Market breadth measures how many securities are participating in a market move rather than how far an index has travelled. The common measures and their limits.",
    h1: "Market breadth",
    definition:
      "Market breadth measures how widely a market move is shared across the securities in it, rather than how far the index itself has travelled. It answers whether an index move reflects most of its members or a concentrated few.",
    measured:
      "Common measures include the count of advancing securities against declining ones, the running total of that difference as an advance-decline line, the share of members trading above a longer moving average, and counts of new highs against new lows. Each is computed over a defined universe, and the choice of universe changes the answer — an equal-weighted view and a capitalisation-weighted view can disagree sharply.",
    matters:
      "Breadth separates a broad advance from a narrow one, which matters because a capitalisation-weighted index can rise on a handful of very large members while most of its constituents are flat or falling. For a swing trader picking individual securities, that distinction bears directly on how representative the index is of what any given name is doing. Breadth is a description of current participation, not a leading indicator, despite frequently being presented as one.",
    related: { href: "/market-regime", label: "The live market regime view" },
    see: ["market-regime", "sector-rotation", "vix", "relative-strength"],
  },
  {
    slug: "market-regime",
    term: "Market regime",
    category: "Macro & regime",
    title: "What Is a Market Regime? Definition for Traders | Tapeline Glossary",
    description:
      "A market regime is a broad classification of prevailing conditions into named states. How regimes are identified and why they are always recognised in arrears.",
    h1: "Market regime",
    definition:
      "A market regime is a broad classification of prevailing market conditions into a small set of named states — risk-on and risk-off being the most common pair, sometimes with a neutral state between them. It is a label imposed on continuous conditions, not a measured quantity.",
    measured:
      "Regime classifications are built by combining market-wide inputs — an expected-volatility index, benchmark trend, participation breadth, interest-rate direction, currency strength — and resolving them into a state. Because the boundaries between states are chosen rather than derived, the classification steps discretely when an underlying reading crosses a threshold, which can happen on a small move.",
    matters:
      "A regime label is context: the same reading on an individual security occurs in very different market conditions, and knowing which conditions prevail is what keeps a broad market move from being mistaken for something specific to one name. The limitation to hold onto is that regimes are identified once they are already under way. A classification describes conditions that have been observed, and none of the common approaches forecasts a change of state.",
    tapeline:
      "The Macro factor is exactly this: a single market-wide regime classification mapped onto the scale. It is the same value for every ticker on a given tick, so it moves the whole board together rather than distinguishing one company from another.",
    factor: "macro",
    related: { href: "/how-it-works/macro", label: "What the Macro factor measures" },
    see: ["vix", "market-breadth", "yield-curve", "sector-rotation"],
  },
  {
    slug: "yield-curve",
    term: "Yield curve",
    aliases: ["inverted yield curve", "term structure"],
    category: "Macro & regime",
    title: "What Is the Yield Curve? Inversion Explained | Tapeline Glossary",
    description:
      "The yield curve plots government bond yields against maturity. What its shape describes, what inversion means, and the lag that makes it hard to trade.",
    h1: "Yield curve",
    definition:
      "The yield curve plots the yields on government bonds of the same issuer against their time to maturity. Its shape describes what the bond market is currently pricing for interest rates across horizons.",
    measured:
      "Take current yields across maturities — from a few months out to thirty years — and plot them against maturity. The curve is usually summarised by the spread between two points on it. An upward slope, where longer maturities yield more, is the ordinary shape. Inversion describes a curve where a shorter maturity yields more than a longer one.",
    matters:
      "Rate direction is one of the market-wide inputs that regime classifications are built from, so the curve sits upstream of a lot of the macro vocabulary. Inversion in particular has drawn attention because it has historically preceded US recessions, but the two properties that make it hard to act on are rarely stated together: the lag between inversion and recession has been long and highly variable, and the sample of historical occurrences is small enough that the regularity is far weaker evidence than the frequency of its citation suggests.",
    tapeline:
      "Interest-rate direction is one of the macro series tracked upstream of Tapeline's regime classification, which is what the Macro factor reads.",
    factor: "macro",
    related: { href: "/how-it-works/macro", label: "What the Macro factor measures" },
    see: ["market-regime", "vix", "market-breadth", "sector-rotation"],
  },

  /* ────────────────────────── Scoring & signals ─────────────────────────── */
  {
    slug: "composite-score",
    term: "Composite score",
    aliases: ["Tapeline Score", "multi-factor score"],
    category: "Scoring & signals",
    title: "What Is a Composite Score? Multi-Factor Scoring | Tapeline Glossary",
    description:
      "A composite score blends several separate measurements into one number on a common scale. How blending works, what it hides, and how Tapeline's is built.",
    h1: "Composite score",
    definition:
      "A composite score blends several separate measurements into a single number on a common scale. Each input is placed on the same scale first, then combined by a weighting that decides how much each one contributes.",
    measured:
      "Every input is mapped onto a shared range so that measurements in different units become addable. The inputs are then combined by weight. The two design decisions that determine everything downstream are which measurements are included and how the weighting is set — and both are choices made by whoever built the score.",
    matters:
      "A composite is a summary, and every summary discards information: a mid-range total can mean every input read mid-range, or that opposing inputs cancelled, and the total alone cannot tell those apart. That is why the per-input breakdown matters more than the headline number. The other thing worth knowing is that any composite is only as legible as its disclosure — a score whose inputs are unnamed cannot be checked by the person relying on it.",
    tapeline:
      "The Tapeline composite runs 0-100 and blends six named factors — Trend, Relative Strength, Fundamentals, Smart Money, Macro and Momentum — weighted most toward Trend and Relative Strength and least toward Momentum. Every ticker's individual factor readings are shown alongside the total, and the ordering of the weights is published while the numeric weights are not.",
    related: { href: "/how-it-works", label: "The full methodology" },
    see: ["momentum", "trend", "relative-strength", "alpha"],
  },
];

export function findTerm(slug: string): GlossaryTerm | undefined {
  return TERMS.find((t) => t.slug === slug);
}

/**
 * The term as it reads mid-sentence.
 *
 * Naive `.toLowerCase()` mangles the acronyms and proper nouns ("sec form 4",
 * "piotroski f-score", "vix"), and leaving the display casing alone puts a
 * stray capital in the middle of every generated question. An uppercase
 * letter anywhere past the first character marks a term whose casing is
 * meaningful, so only the sentence-case ones get down-cased.
 */
export function spokenTerm(term: string): string {
  if (/[A-Z]/.test(term.slice(1))) return term;
  return term.charAt(0).toLowerCase() + term.slice(1);
}

/**
 * The four questions each term page answers, in render order.
 *
 * Single source for BOTH the visible section headings and the FAQPage
 * JSON-LD, so the structured data can never describe a Q&A that is not on
 * the page — which is the thing Google's FAQ guidance is explicit about.
 * The fourth entry only exists when `tapeline` does.
 */
export function termQuestions(term: GlossaryTerm): FaqItem[] {
  const name = spokenTerm(term.term);
  const items: FaqItem[] = [
    { q: `What is ${name}?`, a: term.definition },
    { q: `How is ${name} measured?`, a: term.measured },
    { q: `Why does ${name} matter to a swing trader?`, a: term.matters },
  ];
  if (term.tapeline) {
    items.push({ q: `Does Tapeline use ${name}?`, a: term.tapeline });
  }
  return items;
}

/** Terms grouped for the index page, in CATEGORY_ORDER. Empty groups are dropped. */
export function termsByCategory(): { category: GlossaryCategory; terms: GlossaryTerm[] }[] {
  return CATEGORY_ORDER.map((category) => ({
    category,
    terms: TERMS.filter((t) => t.category === category),
  })).filter((g) => g.terms.length > 0);
}
