/**
 * Per-factor methodology content for /how-it-works/{slug}.
 *
 * Lives outside the page module because Next.js App Router page files may only
 * export the default component, generateMetadata, generateStaticParams and the
 * fixed metadata fields — the sitemap imports FACTORS from here (same pattern
 * as app/sector/sectors.ts).
 *
 * ── ACCURACY IS THE POINT ────────────────────────────────────────────────
 * These pages are the trust surface. Everything below was written against the
 * running implementation, not against the marketing copy:
 *
 *   backend/app/services/score.py
 *     sub_trend, sub_rs, sub_fundamentals, sub_smart_money, sub_macro,
 *     sub_momentum, WEIGHTS, NEUTRAL
 *   backend/app/services/finnhub_feed.py
 *     compute_fundamentals_score, compute_smart_money_score
 *   backend/app/services/sheet_feed.py
 *     market-regime parsing
 *
 * If you change a factor's implementation, change its page in the same PR and
 * add a /changelog entry. A methodology page that has drifted from the code is
 * worse than no methodology page, because it is a documented false statement
 * about a financial product.
 *
 * ── DISCLOSURE BOUNDARY (set in PR #342, "drop exact weights / equation /
 * indicator recipe") ─────────────────────────────────────────────────────
 * These pages name each factor and explain what it MEASURES and, conceptually,
 * how the measurement becomes a reading. They deliberately do NOT publish:
 *   - the numeric weight of any factor in the composite,
 *   - the scoring equation,
 *   - the numeric mappings, thresholds and band edges.
 * The RELATIVE ORDERING of the weights is already public on /how-it-works, so
 * repeating "Trend counts most, Momentum least" is in bounds. "Trend is 25% of
 * the score" is not. If you are tempted to add a threshold, that is the line —
 * describe the mechanism and stop.
 *
 * ── COPY RULE ────────────────────────────────────────────────────────────
 * Nothing here may describe a security, or predict what a reading implies for
 * future price. Describe what the factor measured. Every factor carries a
 * `caveat` that is rendered INLINE next to the positive material, not
 * quarantined on /limitations — an honest limit stated where the claim is made
 * is the whole point of the page.
 */
import type { FaqItem } from "@/lib/jsonld";

export type Factor = {
  /** URL segment: /how-it-works/{slug} */
  slug: string;
  /** Display name, matching the label used in the product's score breakdown. */
  name: string;
  /** Full <title>. No vs-SPY figure, no performance framing. */
  title: string;
  /** Meta description, ~150-160 chars. */
  description: string;
  h1: string;
  /** Where this factor sits in the published weight ORDER (never the number). */
  weightNote: string;
  /** Lede paragraph. */
  summary: string;
  /** What the factor measures — observable quantities only. */
  measures: string[];
  /** How the sub-score is derived, conceptually. No parameters, no equation. */
  computed: string[];
  /** Which data categories feed it. Mirrors /data-sources. */
  feeds: { name: string; detail: string }[];
  /** The short, honest admission rendered inline beside the explanation. */
  caveat: string;
  /** Known weaknesses of this factor, stated plainly. */
  limitations: string[];
  faq: FaqItem[];
};

/**
 * Shared, true-for-every-factor note about missing data.
 *
 * score.py substitutes NEUTRAL (a mid-range value) when a factor is
 * unavailable for a ticker, so a missing input never drags the composite
 * toward zero. That is a deliberate design choice with a real downside, and
 * every factor page states it rather than only the ones where it bites.
 */
export const MISSING_DATA_NOTE =
  "When a factor cannot be computed for a ticker, the composite substitutes a mid-range value rather than a zero, so a missing input does not drag the score down. The trade-off is that a mid-range reading can mean 'measured, and unremarkable' or 'not available' — the per-ticker confidence percentage is what separates the two.";

export const FACTORS: Factor[] = [
  {
    slug: "trend",
    name: "Trend",
    title: "Trend Factor — What Tapeline Measures and How | Methodology",
    description:
      "What the Trend sub-score measures: multi-month price change and where price sits inside its own 52-week range. How the reading is derived, what data feeds it, and where it fails.",
    h1: "Trend: where price has already been",
    weightNote: "Counts for more than any other factor in the composite.",
    summary:
      "Trend describes the shape of a ticker's own recent price history — how much it has moved over a multi-month lookback, and how close it currently sits to the top of its own 52-week range. Both are descriptions of price that has already happened.",
    measures: [
      "The ticker's price change over a multi-month lookback window.",
      "Where the latest price sits inside the ticker's own 52-week high-to-low range.",
    ],
    computed: [
      "Each measurement is mapped onto a common 0–100 range using a fixed scale that is the same for every ticker. There is no per-name override and no discretionary adjustment.",
      "Where both measurements are available they are averaged. Where only one is available, that one is used on its own.",
      "The scale is absolute, not a ranking: a Trend reading is not a ticker's position against other tickers on that tick, it is that ticker's own measurement placed on a fixed scale.",
      "Readings are clamped to the 0–100 range, so a move past the end of the scale saturates rather than extending.",
    ],
    feeds: [
      {
        name: "Live market data",
        detail:
          "Adjusted daily and intraday OHLC bars. Refreshed sub-60 seconds during US market hours.",
      },
    ],
    caveat:
      "Trend is backward-looking by construction. It describes price history and nothing else — it cannot see a pending earnings report, a halt, or an overnight gap, and a high reading is a statement about the past rather than a forecast.",
    limitations: [
      "Because the scale is fixed and clamped, two tickers with very different moves can both sit at the top of the range. Past the end of the scale the reading stops distinguishing between them.",
      "Recently listed tickers have too little history for the 52-week component. The reading is computed from what exists and the per-ticker confidence percentage drops to reflect that.",
      "Corporate actions — splits, spin-offs, large special dividends — distort a raw price series until the adjustment propagates through the feed.",
      "In a range-bound market the reading drifts without a persistent move behind it. A changing Trend reading is not the same as a changing situation.",
      "A high Trend reading carries no information about valuation, solvency, or what the company does.",
    ],
    faq: [
      {
        q: "Does a high Trend reading mean the price will keep rising?",
        a: "No. Trend is a description of price history that has already happened. Tapeline does not forecast prices and does not issue buy or sell calls.",
      },
      {
        q: "Which moving averages does Trend use?",
        a: "It does not use moving-average crossovers. The two inputs are a multi-month price change and the position of the current price inside the 52-week range. Tapeline publishes the measurement, not the exact scale used to convert it into a reading.",
      },
    ],
  },
  {
    slug: "relative-strength",
    name: "Relative Strength",
    title: "Relative Strength Factor — What Tapeline Measures | Methodology",
    description:
      "What the Relative Strength sub-score measures: a ticker's price change minus the broad-market benchmark's, over three horizons from a quarter to a year. Derivation, feeds and limits.",
    h1: "Relative Strength: the same period, measured against a benchmark",
    weightNote: "The second-heaviest factor in the composite, after Trend.",
    summary:
      "Relative Strength is a difference, not a standalone reading. It takes a ticker's price change over three horizons — roughly a quarter, half a year and a year — and subtracts the broad-market benchmark's change over exactly those same periods.",
    measures: [
      "The ticker's price change over roughly a quarter, half a year and a year.",
      "The broad-market benchmark's change over each of those same three periods.",
      "The difference between the two, computed separately for each horizon.",
    ],
    computed: [
      "The three per-horizon differences are combined into one reading. The longer horizons carry more weight than the shorter one, so a single quarter cannot dominate the result.",
      "The combined difference is mapped onto a common 0–100 scale centred on a midpoint, where the midpoint means 'moved with the benchmark'. Above the midpoint the ticker changed by more than the benchmark over the period; below it, by less.",
      "Horizons with no data are skipped, and the reading is built from whichever of the three are available.",
      "Readings are clamped to the 0–100 range.",
    ],
    feeds: [
      {
        name: "Live market data",
        detail:
          "Prices for the ticker and for the broad-market benchmark. Sub-60 seconds during US market hours.",
      },
    ],
    caveat:
      "This is a difference between two numbers, and both can be negative. A ticker can read well above the midpoint over a period in which its own price fell — because the benchmark fell further. A high Relative Strength reading is not a statement that the ticker went up.",
    limitations: [
      "The reading moves when the benchmark moves, not only when the ticker does. A quiet ticker in a moving market produces a moving reading.",
      "The comparison is against a single broad-market benchmark. It is not sector-adjusted, so a whole sector moving together shows up as a ticker-level reading for every name in it.",
      "ETFs and funds are compared against the same broad-market benchmark regardless of what they actually hold, which for a narrow or inverse fund is close to meaningless.",
      "Thin-volume tickers produce noisy period returns, and therefore noisy differences.",
      "Three horizons is a coarse view of a year. A sharp move that reversed inside a horizon is invisible to it.",
    ],
    faq: [
      {
        q: "Which benchmark does Relative Strength compare against?",
        a: "A single broad-market US equity benchmark, measured over the same three horizons as the ticker. The factor is not adjusted for the ticker's own sector.",
      },
      {
        q: "Can a ticker read high on Relative Strength while falling?",
        a: "Yes. The factor measures the difference against the benchmark. If both fell and the ticker fell less, the difference is positive and the reading sits above the midpoint.",
      },
    ],
  },
  {
    slug: "fundamentals",
    name: "Fundamentals",
    title: "Fundamentals Factor — What Tapeline Measures | Methodology",
    description:
      "What the Fundamentals sub-score reads: reported margin, return on equity, EPS and revenue growth, and an earnings multiple. How it is derived, which filings feed it, and where coverage ends.",
    h1: "Fundamentals: what the last filing reported",
    weightNote: "One of three mid-weighted factors, alongside Smart Money and Macro.",
    summary:
      "Fundamentals reads a small set of reported financial metrics and places each on a common scale. Every input is a figure the company has already published in a filing — nothing here is estimated, projected or modelled.",
    measures: [
      "Profit margin, as reported.",
      "Return on equity, as reported.",
      "Earnings-per-share growth between reported periods.",
      "Revenue growth between reported periods.",
      "An earnings multiple, where a lower multiple moves the reading up and a higher one moves it down.",
    ],
    computed: [
      "Each metric that is available is mapped onto a common 0–100 scale using fixed, broadly-drawn bands.",
      "The available components are averaged. A metric that is missing is left out entirely rather than filled in with a guess, and the ticker's confidence percentage falls to reflect the thinner evidence.",
      "If none of the metrics are available — as with most ETFs and funds — the factor is unavailable for that ticker and the composite substitutes a mid-range value.",
    ],
    feeds: [
      {
        name: "Fundamentals",
        detail:
          "Reported financial ratios and growth rates. Refreshed on company filing cadence, not continuously.",
      },
    ],
    caveat:
      "The bands are broad and the same bands are applied to every company regardless of sector — a bank, a biotech and a software company are placed on one scale. That is a blunt instrument, and this factor should be read as a rough sort rather than a considered financial analysis.",
    limitations: [
      "It is not sector-relative. Margin and return-on-equity levels that are ordinary in one industry are unusual in another, and this factor does not adjust for that.",
      "ETFs, funds, trusts and many ADRs have no comparable company financials. The factor is simply unavailable for them.",
      "The reading is exactly as current as the last filing. Between reports it does not move, even when the business does — for most companies that means it is static for weeks at a time.",
      "A reported figure describes a period that has already closed. It describes the last reported quarter, not the current one.",
      "Restatements change previously reported history, and the reading changes with them.",
      "Five metrics is a narrow view of a company. It sees nothing of competitive position, management, litigation, customer concentration, or anything else that does not appear in these five numbers.",
    ],
    faq: [
      {
        q: "Why do some tickers have no Fundamentals reading?",
        a: "ETFs, funds and some foreign-listed structures do not report comparable company financials. Rather than substitute a guess, the factor is treated as unavailable and the composite uses a mid-range value in its place.",
      },
      {
        q: "Is the Fundamentals factor a valuation model?",
        a: "No. It places five reported metrics on a fixed scale and averages them. It does not build a valuation, a fair-value estimate or a price target, and it is not sector-adjusted.",
      },
    ],
  },
  {
    slug: "smart-money",
    name: "Smart Money",
    title: "Smart Money Factor — Disclosed Insider Filings | Methodology",
    description:
      "What the Smart Money sub-score measures: disclosed corporate-insider transactions from SEC Form 4, netted over a recent window. Derivation, data feeds, statutory reporting lag and limits.",
    h1: "Smart Money: transactions somebody was legally required to disclose",
    weightNote: "One of three mid-weighted factors, alongside Fundamentals and Macro.",
    summary:
      "Smart Money reads filings, not intentions. It aggregates transactions that corporate insiders have already disclosed to the SEC on Form 4 within a recent rolling window, and nets them by direction and size.",
    measures: [
      "Disclosed insider purchases and sales in a recent rolling window, from SEC Form 4.",
      "The signed dollar value of each disclosed transaction — shares changed, multiplied by the disclosed transaction price.",
      "The net of those signed values against the total transaction value in the window.",
    ],
    computed: [
      "Every disclosed transaction in the window is converted to a signed dollar value, and the net is taken against the gross. The result is a ratio running from all-selling to all-buying.",
      "That ratio is mapped onto a 0–100 scale around a midpoint, so the reading reflects the balance of disclosed activity rather than its raw size. One large disclosed purchase can outweigh several small disclosed sales, but only on a net basis.",
      "A ticker with no disclosed filings in the window has no reading at all, and the composite substitutes a mid-range value. An absence of filings is treated as an absence of information, not as a negative signal.",
    ],
    feeds: [
      {
        name: "SEC filings",
        detail: "Form 4 insider transactions, ingested daily for the liquid universe.",
      },
    ],
    caveat:
      "Disclosure is lagged by statute, not by Tapeline. A Form 4 is filed days after the transaction it reports, so this factor is always reading the past — and the filing records that a transaction happened, never why.",
    limitations: [
      "Many disclosed transactions carry no view at all. Sales scheduled months in advance under a 10b5-1 plan, option exercises, vesting events and share sales made purely to cover tax withholding all arrive as Form 4 filings and are netted like any other.",
      "Smaller and less-covered companies file rarely, so the window is frequently empty and the factor is unavailable for long stretches.",
      "The factor reads corporate-insider Form 4 filings. Congressional disclosure data is ingested by Tapeline and published as its own feed in the product, but it is not an input to this sub-score today.",
      "Netting by dollar value means one large filer can dominate a company with many reporting insiders.",
      "Insiders are not a uniformly informed group, and this factor makes no claim that they are. The name of the factor is conventional industry shorthand, not an assessment of anyone's judgement.",
    ],
    faq: [
      {
        q: "Does Smart Money include 13F institutional holdings?",
        a: "No. The factor reads SEC Form 4 corporate-insider transactions. The site previously described a 13F input; that was corrected on 2026-05-17 and the correction is logged in the changelog.",
      },
      {
        q: "What happens if a ticker has no insider filings?",
        a: "The factor is unavailable and the composite substitutes a mid-range value. No filings means no information, which is not the same as a negative reading.",
      },
    ],
  },
  {
    slug: "macro",
    name: "Macro",
    title: "Macro Factor — Market Regime Classification | Methodology",
    description:
      "What the Macro sub-score reads: a single market-wide regime classification resolved into three broad states. Why it is the same number for every ticker, and where that is a weakness.",
    h1: "Macro: the backdrop, and the same number for everyone",
    weightNote: "One of three mid-weighted factors, alongside Fundamentals and Smart Money.",
    summary:
      "Macro is the one factor that is not about the ticker. It reads a single market-wide regime classification produced upstream in Tapeline's scoring pipeline and maps it to a value. On any given tick that value is identical for every ticker on the board.",
    measures: [
      "The prevailing market-regime classification, expressed as a small set of named states rather than as a continuous number.",
      "Nothing about the individual ticker. No price, no filing, no company data enters this factor.",
    ],
    computed: [
      "The incoming classification is normalised and resolved into one of three broad families — a rising or positive family, a sideways or neutral family, and a falling or negative family — and each resolved state maps to a fixed value on the 0–100 scale.",
      "Because the upstream classification arrives as free text rather than as an enumerated code, the resolution is tolerant of phrasing. Negative wording is checked before positive wording, so a phrase that negates a positive term resolves to the negative reading rather than matching the positive term inside it.",
      "The resulting value is applied identically to every scored ticker on that tick.",
      "If no classification arrives, or the wording is one Tapeline does not recognise, the factor is treated as unavailable for that tick and the composite substitutes a mid-range value — the same handling every other factor gets when its data is missing.",
    ],
    feeds: [
      {
        name: "Macro indicators",
        detail:
          "A single market-wide regime classification, resolved from the macro series tracked upstream in Tapeline's scoring pipeline and refreshed on the worker tick.",
      },
    ],
    caveat:
      "Because this factor is market-wide, it is the same number for every ticker at a given moment. It moves the whole board up or down together and never distinguishes one company from another — so it should not be read as a statement about any specific ticker.",
    limitations: [
      "A regime label is a discrete bucket imposed on a continuous world. The reading steps when a classification changes, which can happen on a small underlying move.",
      "Regimes are identified once they are already under way. There is no forecast of a regime change here, and none is implied.",
      "Because the value is common to every ticker, it compresses the spread between tickers rather than separating them. It contributes to the level of the whole board more than to its ordering.",
      "Handling an unrecognised classification as missing data is deliberately quiet. It keeps scoring running rather than failing the tick, but it means an upstream wording change shows up as an unremarkable mid-range reading instead of as a visible error.",
      "Resolving free text by matching wording is inherently approximate. It is tolerant by design, and tolerance is not the same as correctness.",
      "The underlying macro series that inform any regime view are published on a lag and are revised after publication.",
      "Tapeline separately publishes a live macro dashboard on the market-regime page. Read that as a descriptive view of current conditions; it is presented on its own terms and is not a restatement of this factor's input.",
    ],
    faq: [
      {
        q: "Why is my ticker's Macro reading the same as everything else's?",
        a: "Because it is market-wide by design. The regime classification applies to the entire scored universe on a given tick, and the factor is not adjusted per ticker or per sector.",
      },
      {
        q: "Does the Macro factor predict a recession or a market turn?",
        a: "No. It reads a classification of conditions that have already been observed and maps it to a value. Tapeline makes no forecast of regime changes, and none is implied by the reading.",
      },
    ],
  },
  {
    slug: "momentum",
    name: "Momentum",
    title: "Momentum Factor — Short-Horizon Rate of Change | Methodology",
    description:
      "What the Momentum sub-score reads: a momentum-quality reading plus a short-horizon return approximated from a longer window. Why Tapeline weights it least, and where it is weak.",
    h1: "Momentum: the shortest memory, and the least weight",
    weightNote: "Counts for less than any other factor in the composite.",
    summary:
      "Momentum describes how quickly price has moved recently. It is the shortest-memory factor in the set, the noisiest, and of the six it is the one the composite leans on least — deliberately.",
    measures: [
      "A momentum-quality reading for the ticker, supplied by the upstream signal system either as a number or as a graded label.",
      "A short-horizon return, approximated by rescaling the ticker's multi-month price change.",
    ],
    computed: [
      "Each available component is mapped onto a common 0–100 scale and the available ones are averaged.",
      "Where the momentum-quality input arrives as a label rather than a number, the label is resolved to a value on the same scale.",
      "The composite weights Momentum least of the six factors, because short-horizon rate of change reverses often. The ordering of the factor weights is published on /how-it-works; the numeric weights are not.",
    ],
    feeds: [
      {
        name: "Live market data",
        detail: "Daily and intraday bars. Sub-60 seconds during US market hours.",
      },
      {
        name: "Upstream signal system",
        detail:
          "The momentum-quality reading, supplied per ticker by Tapeline's scoring pipeline and refreshed on the worker tick.",
      },
    ],
    caveat:
      "The short-horizon component is an approximation, derived by rescaling a longer multi-month return rather than measured over a short window directly. It is therefore smoother than a true short-window reading and will lag a genuine recent turn. This is the weakest-constructed of the six factors, and it carries the least weight for that reason.",
    limitations: [
      "The short-horizon input is a proxy, not a measurement. A sharp move in the last few weeks reaches this factor diluted by the longer window it is derived from.",
      "It is sensitive to one-off events — an earnings gap, a news spike, an index-inclusion flow — and cannot distinguish those from a sustained move.",
      "Low-float and low-liquidity tickers produce large readings from small dollar flows. Tapeline applies a liquidity floor to the ranked scanner and the public scorecard for this reason; that floor can be switched off on the scanner to browse the full scored universe.",
      "Where the upstream momentum-quality input is a coarse label rather than a number, the reading it produces is correspondingly coarse.",
      "It carries no information about the company at all.",
    ],
    faq: [
      {
        q: "Why is Momentum weighted least?",
        a: "Two reasons, both stated plainly: short-horizon rate of change reverses often enough to be a noisy input on its own, and one of its two components is an approximation rather than a direct measurement. The relative ordering of the six factor weights is published; the exact numeric weights are not.",
      },
      {
        q: "Why does the Momentum reading change less than I expect day to day?",
        a: "Because its short-horizon component is derived by rescaling a longer multi-month return rather than measured over a short window. That makes it smoother, and slower to reflect a genuine recent turn, than the factor's name suggests.",
      },
    ],
  },
];

export function findFactor(slug: string): Factor | undefined {
  return FACTORS.find((f) => f.slug === slug);
}
