/**
 * Strategy manifest for the /best-stocks-for/[strategy] programmatic-SEO
 * route. Each entry targets a long-tail "best stocks for {strategy}" query
 * cluster with strategy-specific copy + a unique scanner sort/filter so the
 * five pages aren't duplicate content.
 *
 * Adding a strategy: append to STRATEGIES with a unique slug. The dynamic
 * route at /app/best-stocks-for/[strategy]/page.tsx auto-picks it up via
 * generateStaticParams.
 */

export type StrategyFAQ = { q: string; a: string };

export type StrategyConfig = {
  slug: string;
  display: string;
  h1: string;
  metaTitle: string;
  metaDescription: string;
  lede: string;
  apiParams: Record<string, string | number>;
  factorEmphasis: string;
  faq: StrategyFAQ[];
};

export const STRATEGIES: StrategyConfig[] = [
  {
    slug: "day-traders",
    display: "Day Traders",
    h1: "Best Stocks to Day Trade — Today's Top 30 by Move + Composite Score",
    metaTitle: "Best Stocks to Day Trade Today — Live Top 30 Movers with Score Confluence | Tapeline",
    metaDescription:
      "30 US stocks with the biggest moves today that also score 60+ on Tapeline's 6-factor composite — momentum confirmed by trend and relative strength. Sub-60s refresh. Public scorecard, no edits.",
    lede:
      "Day trading lives or dies on confluence: setups where the score, the trend, the relative strength, and the day's price action all point the same direction. The list below ranks today's US tickers sorted by today's 1-day move, filtered to names with a Tapeline composite at or above 60. The tape is fresh — the underlying scores re-tick sub-60 seconds during market hours.",
    apiParams: { sort: "change_pct_1d", order: "desc", min_score: "60", limit: "30" },
    factorEmphasis: "momentum + trend",
    faq: [
      {
        q: "What makes a good day-trading stock?",
        a: "For a day-trading workflow, the actionable filter is confluence: strong intraday momentum, healthy relative strength vs sector and SPY, decent liquidity, and a score that's already in the upper half of the distribution. A 90-momentum, 30-trend name is a head-fake. A 70-momentum, 70-trend, 70-RS name is a setup. Tapeline's composite is built to surface that confluence in one number.",
      },
      {
        q: "How often does the day-trading list update?",
        a: "Underlying scores update sub-60 seconds during US market hours. The 1-day change column is live. This snapshot view caches for 5 minutes server-side to avoid hammering the API on every search-engine crawl; the live scanner at /app/scanner shows the real-time ranking.",
      },
      {
        q: "What's the difference between this and your live scanner?",
        a: "This page is a SEO-friendly opinionated view: top 30 by today's move, filtered to score 60+. The live scanner at /app/scanner is the full ~2,500-ticker universe with every filter exposed (sort by any factor, threshold any sub-score, filter by sector or signal label). This page is for surfacing candidates; the scanner is for working through them.",
      },
      {
        q: "Why filter to score 60+ rather than just 'biggest movers'?",
        a: "Pure 'biggest movers' lists are mostly noise — small-caps spiking on rumours and short squeezes with no underlying setup. Filtering to composite 60+ keeps the day's movers that also have factor confluence behind them. It's a quality filter applied to a momentum sort.",
      },
    ],
  },
  {
    slug: "swing-traders",
    display: "Swing Traders",
    h1: "Best Stocks to Swing Trade — Live Top 30 by Composite Score",
    // metaTitle targets exact-match for the cluster: "best stocks to swing
    // trade" (5 imp), "best swing trade stocks" (4 imp), "top momentum stocks
    // for swing trading may 2026" (4 imp). Front-loaded with the verb form
    // ("to Swing Trade") that the queries actually use; trailing freshness
    // signal ("Updated Daily") + specific number ("Top 30") improves CTR.
    metaTitle: "Best Stocks to Swing Trade — Live Top 30 Composite Scores (Updated Daily) | Tapeline",
    metaDescription:
      "30 US stocks currently scoring highest for swing trading on Tapeline's 6-factor composite — trend, relative strength, fundamentals, smart money, macro, momentum. Updated daily. Public scorecard tracks every pick vs SPY, no edits.",
    lede:
      "Swing trading rewards the names where multiple factors line up over multiple sessions. The list below ranks US tickers by Tapeline composite score — the six factors weighted at exact published percentages — filtered to a minimum score of 65 (top third of the distribution). Sorted by composite descending. The composite is the best summary number for a multi-day setup.",
    apiParams: { sort: "score", order: "desc", min_score: "65", limit: "30" },
    factorEmphasis: "score + relative strength",
    faq: [
      {
        q: "What's the typical Tapeline score threshold for a swing trade?",
        a: "By signal-label convention: STRONG SETUP (70-84) is where the textbook swing setups cluster. HIGH CONVICTION (85-100) is rarer and tends to be late in a move rather than the entry. CONSTRUCTIVE (55-69) is a watchlist tier — adding to your radar without committing capital. Use 65+ as a screening floor; let your own discretion narrow from there.",
      },
      {
        q: "How is this different from the day-traders list?",
        a: "Day traders sort by today's 1-day move; swing traders sort by composite score. Day-trader confluence is intraday and time-decays in hours. Swing-trader confluence is multi-day and time-decays in weeks. Same scoring engine, different sort order — different actionable shape.",
      },
      {
        q: "Should I use this list or build my own filter?",
        a: "Start here, then narrow in /app/scanner. This page is the opinionated view that gives you top 30 candidates without you constructing a filter. The full scanner lets you tighten — minimum trend score, specific sector, signal-label filter, etc. Once a few candidates pass the broader screen here, dig into the per-ticker breakdown to decide which deserve real position size.",
      },
      {
        q: "What's the public scorecard?",
        a: "Every top-10 daily pick gets auto-published at /scorecard with the original composite score, signal label, and one-sentence reasoning. Twenty-four hours later, the next-session realised return vs SPY is appended — no edits, no deletions. It's the public track record so you can see whether the model's high-conviction calls are actually delivering positive alpha over time.",
      },
    ],
  },
  {
    slug: "momentum",
    display: "Momentum Trading",
    h1: "Top Momentum Stocks — Live Top 30 by 5-Day Move with Score Confluence",
    // metaTitle targets: "top momentum stocks 2026" (4), "top 5 momentum stocks
    // may 2026" (10), "top momentum stocks for swing trading may 2026" (4) —
    // a strong cluster. Updated to lead with "Top Momentum Stocks" (matches
    // 3 of the top 10 queries) and add "5-Day" specificity.
    metaTitle: "Top Momentum Stocks Right Now — Live 5-Day Movers with Score Confluence | Tapeline",
    metaDescription:
      "30 US stocks with the biggest 5-day moves that also score 60+ on Tapeline's 6-factor composite — momentum confirmed by trend, relative strength, and fundamentals. Updated daily. Public scorecard, no edits.",
    lede:
      "Momentum without score confirmation is a coin flip. Pure 'biggest 5-day movers' lists are dominated by news pops, short squeezes, and reversals that fail in the next session. The list below filters to composite 60+ before sorting by 5-day change — the move PLUS the underlying factor confluence. Trend, relative strength, smart money: if those agree with the recent momentum, you've got a structural runner. If they don't, you've got a name to fade.",
    apiParams: { sort: "change_pct_5d", order: "desc", min_score: "60", limit: "30" },
    factorEmphasis: "momentum + trend + RS",
    faq: [
      {
        q: "Why filter to a minimum composite before sorting by 5-day move?",
        a: "Because raw '5-day winners' is mostly noise. A stock can be up 30% in 5 days because of an earnings beat with strong fundamentals (real momentum) or because of a short squeeze on broken fundamentals (failed momentum). The composite filter keeps the first category and removes the second. The score IS the noise filter.",
      },
      {
        q: "What's the Tapeline 'Momentum' factor specifically?",
        a: "Momentum (10% of the composite weight) captures short-horizon price acceleration: rate of change, RSI position, MACD posture, volume confirmation, and recent breakout structure. It's deliberately a smaller factor weight than Trend (25%) and Relative Strength (20%) — because pure momentum without longer-timeframe trend tends to mean-revert. The composite balances all six.",
      },
      {
        q: "How long do momentum setups typically run?",
        a: "Tapeline's scorecard back-checks against next-day return. Most momentum-driven HIGH CONVICTION picks see meaningful continuation in the first 1-3 sessions, then mean-revert toward sector beta. The scorecard at /scorecard records exactly that pattern in the public record.",
      },
      {
        q: "Should I trade pure momentum or wait for confluence?",
        a: "Confluence. Pure-momentum scans (e.g. 'top 10 by 5-day return') have a poor hit rate because most of the move is already priced in by the time the screen surfaces it. Filtering to score 60+ means you're picking names where the momentum is confirmed by trend + RS + macro — much higher base rate of continuation.",
      },
    ],
  },
  {
    slug: "dividend",
    display: "Dividend Investors",
    h1: "Best Dividend Stocks — Quality Scored by the Six-Factor Composite",
    metaTitle: "Best Dividend Stocks 2026 — Top Scores Across Yield Sectors on Tapeline",
    metaDescription:
      "Live ranking of US dividend-relevant sectors — Financials, Utilities, Real Estate, Consumer Defensive — scored by the Tapeline six-factor composite. Quality dividend names ranked by trend + fundamentals confluence. Free tier; Pro at $24.99/mo annual.",
    lede:
      "Dividend investing fails when 'high yield' is the only filter — high yields are often the market pricing in dividend risk. The right filter is yield in the context of quality: are the fundamentals strong, is the trend confirming, is the sector regime supportive? The list below ranks US tickers in dividend-rich sectors (Financials, Utilities, Real Estate, Consumer Defensive) by Tapeline composite — the same six-factor formula that prices in trend, fundamentals, and macro alongside the yield. High score in a dividend sector means yield WITH durability.",
    apiParams: { sort: "score", order: "desc", min_score: "55", limit: "30" },
    factorEmphasis: "fundamentals + trend",
    faq: [
      {
        q: "Why composite-score dividend stocks instead of just sorting by yield?",
        a: "High-yield-first lists surface dividend traps — stocks where the yield is high because the price collapsed and the dividend is at risk of being cut. The composite score blends fundamentals (earnings quality, balance-sheet health), trend (is the stock holding up?), and macro (is the regime supportive of yield names?). High composite in a dividend-rich sector means yield with the underlying strength to defend it.",
      },
      {
        q: "Which sectors does this list focus on?",
        a: "Financials, Utilities, Real Estate, and Consumer Defensive — the four sectors that historically house the highest-conviction dividend names. Filter by any one of them on /app/scanner if you want a single-sector view (e.g. /sector/real-estate or /sector/utilities).",
      },
      {
        q: "How does Tapeline read dividend safety?",
        a: "Dividend safety isn't an explicit factor in the score, but it's heavily implied by the Fundamentals factor (15% weight). Strong fundamentals — earnings quality, low debt, healthy free cash flow — is the structural backstop for a defensible payout. If the Fundamentals sub-score is below 40 on a high-yield name, that's the red flag the composite is asking you to weigh.",
      },
      {
        q: "Should I cross-check with another tool?",
        a: "For deep dividend-specific research (payout-ratio history, dividend-growth streaks, ex-div schedule), Simply Wall St's Snowflake includes a Dividends dimension that's purpose-built. Many dividend investors run Tapeline for the live composite + Simply Wall St for the dividend-specific deep dive. See the head-to-head comparison.",
      },
    ],
  },
  {
    slug: "value",
    display: "Value Investors",
    h1: "Best Value Stocks — Quality Composite at Reasonable Multiples",
    metaTitle: "Best Value Stocks 2026 — Tapeline Score Confluence on Quality Names",
    metaDescription:
      "Live ranking of US value-investor candidates — Tapeline composite filter on quality fundamentals with the score in the constructive range. Six-factor scoring catches value traps before you do. 14-day Pro trial, no card.",
    lede:
      "Value investing fails when you buy a stock just because it's cheap. The market is usually cheap-for-a-reason; the trick is separating temporarily cheap from structurally broken. Tapeline's composite is built on six factors with Fundamentals weighted at 15% — strong fundamentals score combined with a constructive overall composite (score 55-75 — the upper-middle of the distribution, not the top) is where value setups actually live. Top of the distribution is already-priced-in; bottom is broken. The middle, filtered to quality, is the value-investor zone.",
    apiParams: { sort: "score", order: "desc", min_score: "55", limit: "30" },
    factorEmphasis: "fundamentals + quality",
    faq: [
      {
        q: "Why filter to score 55+ for value when high-conviction is 85+?",
        a: "High-conviction names are already-priced-in — the market has fully discovered them and the move has happened. Value investors want quality names that haven't fully been bid up yet. The 55-75 score band — CONSTRUCTIVE through STRONG SETUP — is where unrecognised quality tends to live. Below 55 the data is telling you something's actually wrong; above 75 the move has already started without you.",
      },
      {
        q: "What's the Fundamentals factor specifically?",
        a: "Fundamentals (15% weight) blends earnings quality, margin trend, balance-sheet health, revenue growth, ROE, and free-cash-flow stability. Sourced from a third-party data feed's basic-financials data. A 70+ Fundamentals sub-score is the quality screen; a name passing that AND in the 55-75 composite range is the value-investor's setup.",
      },
      {
        q: "How is this different from Simply Wall St's value screen?",
        a: "Simply Wall St's Value dimension is bottom-up DCF-style — intrinsic value vs current price, with their internal model. Useful but cadence is daily. Tapeline's value-zone filter is composite-based, live, and contextualised by macro and smart-money signals — it tells you not just whether the stock is undervalued by their model, but whether the market regime is supportive of the rerating. Different angles on the same problem.",
      },
      {
        q: "What signal labels suit value investors?",
        a: "CONSTRUCTIVE (55-69) is the value-investor's primary zone — quality with mixed factors, often where rerating opportunity lives. STRONG SETUP (70-84) is where rerating has begun; useful as confirmation. HIGH CONVICTION (85-100) is too late for typical value entries — the move is already in. CAUTION (25-39) and WEAK (0-24) deserve genuine scepticism; the market is usually right that something is wrong.",
      },
    ],
  },
];

export function findStrategy(slug: string): StrategyConfig | null {
  return STRATEGIES.find((s) => s.slug === slug) ?? null;
}
