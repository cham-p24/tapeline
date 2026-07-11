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
        a: "Underlying scores update sub-60 seconds during US market hours. The 1-day change column is live. This snapshot view caches for an hour server-side to avoid hammering the API on every search-engine crawl; the live scanner at /app/scanner shows the real-time ranking.",
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
    h1: "Best Swing Trade Stocks Right Now — Live Top 30 by Score",
    // metaTitle / metaDescription rewritten 2026-05-19 against GSC data:
    // page sat at position 12.4 with 304 impressions over 90 days (biggest
    // single-page impression bucket on the site), but the previous 87-char
    // title was truncating in the SERP and burying the keyword. New title is
    // 60 chars, front-loads "Best Stocks to Swing Trade 2026" verbatim
    // (matches "best swing trading stocks 2026", "best us stocks for swing
    // trading 2026", "top swing trade stocks 2026" — all queries we already
    // rank for), keeps the specific number "Top 30" + brand. New description
    // is 142 chars (well under desktop truncation), leads with "today" for
    // freshness and ends with the public-scorecard credibility hook.
    // 2026-07-11: retuned to the exact plural noun "Best Swing Trade Stocks"
    // (front-loaded) — GSC shows the page at pos ~23 on 2,046 impressions for
    // "best swing trade stocks" / "swing trade stocks" / "swing trading stocks".
    metaTitle: "Best Swing Trade Stocks 2026 — Top 30 by Score | Tapeline",
    metaDescription:
      "Today's 30 best swing trade stocks, ranked by Tapeline's public 6-factor composite — live scores, daily refresh, next-day scorecard vs SPY.",
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
    h1: "Momentum Stocks List — Top 30 Right Now by 5-Day Move + Score",
    // metaTitle / metaDescription rewritten 2026-05-19 against GSC data:
    // page sat at position 11.3 with 160 impressions over 90 days — right
    // at the page-1/page-2 border, where a sharper title is the highest-
    // leverage move. The previous 84-char title was truncating; new title
    // is 63 chars and leads with the exact query string the cluster uses:
    // "Top Momentum Stocks 2026" (4 imp), "top 5 momentum stocks may 2026"
    // (12 imp), "top momentum stocks for swing trading may 2026" (4 imp),
    // "momentum stocks 2026" (1 imp pos 6.0). Description trimmed to
    // 138 chars, leads with the "biggest 5-day movers WITH score 60+"
    // differentiator and ends with the public-scorecard credibility hook.
    // 2026-07-11: "Momentum Stocks List" front-loads the exact query (GSC:
    // "momentum stocks list" / "momentum stocks", 777 impressions at pos ~23)
    // and removes the old "Top…Top" repetition.
    metaTitle: "Momentum Stocks List 2026 — Top 30 5-Day Movers | Tapeline",
    metaDescription:
      "An updated momentum stocks list — the 30 biggest 5-day US movers also scoring 60+ on Tapeline's public 6-factor composite. Live, daily refresh.",
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
        a: "Tapeline's scorecard back-checks each daily top-10 pick against next-day return and keeps the full record — winners and losers — public at /scorecard. It's an unedited track record versus SPY, which it currently trails; it is not a claim about how long any setup runs or how it will perform.",
      },
      {
        q: "Should I trade pure momentum or wait for confluence?",
        a: "Confluence. Pure-momentum scans (e.g. 'top 10 by 5-day return') surface names where much of the move is already priced in by the time the screen catches it. Filtering to score 60+ surfaces names where momentum is corroborated by trend + RS + macro rather than momentum alone — a descriptive confluence read, not a hit-rate or continuation claim.",
      },
    ],
  },
  {
    slug: "dividend",
    display: "Dividend Investors",
    h1: "Best Dividend Stocks — Quality Scored by the Six-Factor Composite",
    metaTitle: "Best Dividend Stocks 2026 — Top Scores Across Yield Sectors on Tapeline",
    metaDescription:
      "Live ranking of US dividend-relevant sectors — Financials, Utilities, Real Estate, Consumer Defensive — scored by the Tapeline six-factor composite. Quality dividend names ranked by trend + fundamentals confluence. Free tier; Pro at $8.25/mo annual.",
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
  // ---- 2026-05-20: keyword-cluster expansion ----
  // Each entry below targets a long-tail query cluster that was previously
  // uncovered. Filters use the new min_price/max_price scanner params plus
  // composite-score thresholds so each list is genuinely distinct from the
  // others (no duplicate-content risk).
  {
    slug: "penny-stocks",
    display: "Penny Stocks",
    h1: "Best Penny Stocks — Live Top 30 Under $5 by Composite Score",
    metaTitle: "Best Penny Stocks 2026 — Top 30 Under $5 by Score | Tapeline",
    metaDescription:
      "30 US penny stocks (under $5) ranked by Tapeline's public 6-factor composite. Score-filtered so the list isn't just 'cheap and dying'. Live, daily refresh.",
    lede:
      "Pure 'cheapest stocks' lists are a guaranteed loss machine — most names under $5 are cheap for a reason (deteriorating fundamentals, failed growth stories, dilution risk). The list below filters US tickers under $5 to a composite score of 35+, which removes the structurally broken names and leaves the small-cap candidates that at least have factor confluence. Tapeline's six-factor formula treats a $3 stock the same way it treats a mega-cap: trend, fundamentals, smart money, macro, momentum. Cheap isn't a strategy. Cheap with the score behind it might be.",
    apiParams: { sort: "score", order: "desc", max_price: 5, min_score: "35", limit: "30" },
    factorEmphasis: "score floor + trend",
    faq: [
      {
        q: "Why filter penny stocks by score at all?",
        a: "Because most stocks under $5 are there because the market has correctly priced in serious problems — declining revenue, balance-sheet stress, dilution. A score floor of 35 removes the worst of those and leaves cheap names where at least some factor (trend, fundamentals, or relative strength) is holding up. It's a quality screen applied to a price universe.",
      },
      {
        q: "Are penny stocks dangerous?",
        a: "Yes. Penny stocks have wider bid-ask spreads, higher manipulation risk (pump-and-dump schemes are real), lower analyst coverage, and structurally higher bankruptcy rates than mid- and large-caps. Position sizing matters here even more than usual. Tapeline scores them the same way it scores everything else — the score doesn't fix the structural risk of the asset class.",
      },
      {
        q: "What's a 'good' Tapeline score for a penny stock?",
        a: "Anything 60+ on a sub-$5 name is genuinely rare and worth attention — it means the composite is overcoming the natural drag of the small-cap discount. Most usable penny-stock setups sit in the 40–60 band: score isn't great but not terrible, with one or two specific factors that look strong. Click any row for the per-factor breakdown.",
      },
      {
        q: "Do you cover OTC stocks?",
        a: "No. Tapeline's universe is NYSE/Nasdaq-listed US equities and ETFs. OTC-listed names (the venue most retail traders associate with 'penny stocks') aren't in the database. The under-$5 names here are all real exchange-listed companies; that already filters out a lot of the worst-of-the-worst.",
      },
      {
        q: "How is this different from /best-stocks-for/under-5?",
        a: "Same filter, different framing. /under-5 is the price-anchored search-intent version; /penny-stocks is the strategy-anchored version. They surface the same names — duplicate listings exist because the search queries are different and ranking-wise we want to cover both.",
      },
    ],
  },
  {
    slug: "under-10",
    display: "Under $10",
    h1: "Best Stocks Under $10 — Live Top 30 by Tapeline Score",
    metaTitle: "Best Stocks Under $10 in 2026 — Top 30 by Score | Tapeline",
    metaDescription:
      "30 best US stocks priced under $10, ranked by Tapeline's public 6-factor composite. Quality-filtered so cheap doesn't mean broken. Live universe, daily refresh.",
    lede:
      "Stocks priced under $10 sit between the penny-stock void and the mid-cap mainstream — a sweet spot of underfollowed names where score-based scoring can still find edge. Tapeline ranks every US ticker under $10 by composite score, filters to 45+ (the lower half of CONSTRUCTIVE), and surfaces the top 30. Cheap names with the trend, fundamentals, or relative strength backing them up.",
    apiParams: { sort: "score", order: "desc", max_price: 10, min_score: "45", limit: "30" },
    factorEmphasis: "score + relative strength",
    faq: [
      {
        q: "Why $10 as the cutoff?",
        a: "It's the conventional retail dividing line — most brokerages screen 'cheap stocks' at $10, and the cluster of search queries ('best stocks under $10', 'cheap stocks to buy 2026') uses $10 as the anchor. Tapeline matches the convention; the actual edge is composite-score quality within that price band, not the round number.",
      },
      {
        q: "How is this different from Penny Stocks?",
        a: "Penny stocks (under $5) is a much riskier universe with higher manipulation and bankruptcy rates. Under $10 includes a lot of small- and mid-caps that are simply trading in the $5-$10 range without the deep penny-stock baggage. Score floor here is also higher (45 vs 35) so the surfaced names are higher-quality.",
      },
      {
        q: "Are there mega-cap stocks under $10?",
        a: "Rarely. Most $10-and-under names are small- to mid-caps, plus the occasional fallen large-cap that hasn't recovered. The Tapeline score is structural — it weighs trend, fundamentals, and macro the same regardless of market cap. So the under-$10 list is mostly small-caps but the scoring lens is consistent.",
      },
      {
        q: "What if I want to see all cheap stocks, not just the top 30?",
        a: "The live scanner at /app/scanner has full price-range filtering — set min_price/max_price to any range you want, then sort and filter by score, sector, signal label. The list above is an SEO-friendly opinionated view; the scanner is the working tool.",
      },
    ],
  },
  {
    slug: "growth-stocks",
    display: "Growth Stocks",
    // 2026-07-11: "Best Growth Stocks" front-loaded + "right now" intent (GSC:
    // "growth stocks" 178 + "best growth stocks" 80, 586 impressions at pos ~23).
    // Sort stays "1M Move" in the title — this list sorts by change_pct_1m, not
    // score, so a "by Score" title would be inaccurate.
    h1: "Best Growth Stocks Right Now — Live Top 30 by 1-Month Move",
    metaTitle: "Best Growth Stocks 2026 — Live Top 30 by 1M Move | Tapeline",
    metaDescription:
      "Today's best US growth stocks, ranked by 1-month move and filtered to composite 65+ on Tapeline's public 6-factor formula. Live, daily refresh.",
    lede:
      "Growth investing rewards stocks where the price has been moving up over weeks, not days — sustained advance backed by improving fundamentals and broadening participation. The list below ranks US tickers by 1-month percentage change, filtered to composite score 65+ (the lower half of STRONG SETUP). Pure '1-month winners' lists pick up bounces from broken names; the score filter keeps the structurally healthy ones.",
    apiParams: { sort: "change_pct_1m", order: "desc", min_score: "65", limit: "30" },
    factorEmphasis: "trend + momentum + RS",
    faq: [
      {
        q: "What's the difference between growth and momentum?",
        a: "Momentum is short-window (1-5 day) price acceleration. Growth is multi-month sustained advance — usually backed by improving fundamentals, expanding margins, or revenue acceleration. Tapeline doesn't have a 'Growth' factor explicitly; the composite picks up growth stocks via the combination of high Trend (25% weight), high Fundamentals (15%), and rising relative strength (20%). Sorting by 1-month change gives you the momentum-adjacent version of growth.",
      },
      {
        q: "Why a min_score of 65 instead of 85+?",
        a: "Because the goal is to catch growth stocks before they hit HIGH CONVICTION territory — by 85+, the move is already widely recognised. The 65-84 STRONG SETUP band is where unrecognised growth tends to live: trend and fundamentals are confirming but the score hasn't yet pushed into the top of the distribution. That's the entry-friendly zone.",
      },
      {
        q: "Are these mostly tech stocks?",
        a: "Often, but not always. Tech naturally dominates growth lists because the Information Technology and Communication Services sectors tend to have the highest median 1-month moves. But healthcare biotechs, consumer discretionary names, and even financials can show up when the macro regime favours them. The composite filter cares about confluence, not sector.",
      },
      {
        q: "What about valuation? Won't these be expensive?",
        a: "Tapeline doesn't have a P/E ratio cutoff — the Fundamentals factor (15% weight) weighs earnings quality, margins, and balance-sheet health, but not 'cheap multiple'. Growth stocks tend to trade at premium multiples by definition; the question this list answers is 'which growth names are confirmed by trend + RS', not 'which growth names are also cheap'. For value-oriented growth, see /best-stocks-for/value.",
      },
    ],
  },
  {
    slug: "breakouts",
    display: "Breakout Stocks",
    h1: "Stocks Breaking Out Today — Top 30 by 1-Day Move + Score",
    metaTitle: "Stocks Breaking Out Today 2026 — Top 30 Movers + Score | Tapeline",
    metaDescription:
      "30 US stocks with the biggest 1-day move today, filtered to composite 70+. The 'biggest movers + factor confluence' filter that pure-momentum lists miss. Live.",
    lede:
      "Breakout scans live or die on the score filter. A pure 'biggest 1-day movers' list is mostly noise — small-caps spiking on news, short squeezes, low-quality penny stocks. The list below ranks today's biggest US movers, filtered to composite 70+ (STRONG SETUP and above). That's the breakout-with-confluence cluster: the move plus the trend, relative strength, and fundamentals confirming it. Real breakouts, not head-fakes.",
    apiParams: { sort: "change_pct_1d", order: "desc", min_score: "70", limit: "30" },
    factorEmphasis: "momentum + confluence",
    faq: [
      {
        q: "What makes a 'real' breakout vs a head-fake?",
        a: "Real breakouts have confluence: the 1-day move is supported by the longer-term trend (Trend factor), the stock is outperforming its sector + SPY (Relative Strength), and the volume confirms participation (Momentum factor). Head-fakes have the 1-day move but the score is low — meaning trend and RS aren't agreeing with the spike. The filter to score 70+ removes most head-fakes.",
      },
      {
        q: "How is this different from Day Traders?",
        a: "/best-stocks-for/day-traders uses score 60+ (lower floor, broader list). This Breakouts list uses 70+ (tighter, higher-conviction). Day traders want a wider candidate pool to work through; breakout-focused traders want only the cleanest setups. Same data, different filter intensity.",
      },
      {
        q: "What time of day is best to scan?",
        a: "Late morning (US ET) is typically the sweet spot — early-day moves driven by overnight news have settled, and the names showing 1-day moves backed by score confluence are the ones likely to continue. Tapeline's underlying scores refresh sub-60 seconds during market hours, so the list updates throughout the session.",
      },
      {
        q: "Do I need to act intraday or can I act on a daily-close breakout?",
        a: "Both work. The 1-day move column is live during the session and final at close. Tapeline's scorecard back-checks against next-session return — so the model is built around next-session continuation, not intraday continuation. Daily-close breakouts that the model picks up tend to extend in the next 1-3 sessions; intraday breakouts often mean-revert by end of day.",
      },
    ],
  },
  {
    slug: "ai-stocks",
    display: "AI Stocks",
    h1: "Best AI Stocks — Tech-Sector Leaders Scored by the Tapeline Composite",
    metaTitle: "Best AI Stocks 2026 — Tech Leaders by Tapeline Score | Tapeline",
    metaDescription:
      "Top 30 US Information Technology names ranked by Tapeline's public 6-factor composite. The AI cluster filtered for trend + fundamentals confluence. Live, daily refresh.",
    lede:
      "Every retail trader wants a piece of the AI story. The problem is that 'AI stocks' as a screen is messy — it's not a sector and the qualifying companies range from semis (NVDA, AMD) to hyperscalers (MSFT, GOOGL, META, AMZN) to applied-AI plays (PLTR, ORCL). The list below filters to Information Technology — the GICS sector with the densest AI exposure — and ranks by Tapeline composite. The score knows trend, relative strength, and fundamentals matter more than the headline label.",
    apiParams: { sort: "score", order: "desc", min_score: "60", sector: "Information Technology", limit: "30" },
    factorEmphasis: "score + sector concentration",
    faq: [
      {
        q: "Why filter to Information Technology only?",
        a: "Because the GICS taxonomy doesn't have an 'AI' sector — AI exposure is spread across Information Technology (most semis, most software), Communication Services (the AI-leveraged platforms), and Industrials (robotics, automation). Information Technology is the densest single bucket. For a broader view including Communication Services giants like META and GOOGL, see /sector/communication-services or use /app/scanner with multi-sector filtering.",
      },
      {
        q: "Which specific AI names show up most often?",
        a: "Mega-caps with strong scores: NVDA, AMD, AVGO, MSFT, ORCL, TSM (when scored), and the applied-AI software names. The composite tends to favour names where the AI story is backed by actual revenue traction (Fundamentals factor) plus chart confirmation (Trend + RS factors). Pure-narrative AI plays without revenue confluence tend to score lower.",
      },
      {
        q: "Is this just the same as the Technology sector page?",
        a: "Closely related but not identical. /sector/information-technology shows the full Tech-sector ranking. This page applies an explicit composite-60 floor and limits to 30 names, which surfaces the leaders rather than the full list. Same universe, different opinionated cut.",
      },
      {
        q: "Are AI stocks a bubble?",
        a: "Tapeline doesn't make valuation calls — that's not a six-factor question. What the composite can tell you: if trend and fundamentals are diverging (rising price, deteriorating margins) the score drops, regardless of theme. The names that stay near the top of the list over time are the ones where the AI story is being confirmed by actual factor improvement, not just multiple expansion.",
      },
    ],
  },
  {
    slug: "high-conviction",
    display: "High Conviction",
    h1: "Highest-Scored US Stocks Right Now — Tapeline's HIGH CONVICTION Tier",
    metaTitle: "Highest Scored Stocks Today — Top 30 HIGH CONVICTION | Tapeline",
    metaDescription:
      "The 30 US stocks scoring highest on Tapeline's public 6-factor composite — HIGH CONVICTION tier (score 85+). Live ranking, daily public scorecard.",
    lede:
      "The HIGH CONVICTION tier is the top 1-3% of the universe at any time — names where Trend, Relative Strength, Fundamentals, Smart Money, Macro, and Momentum all agree. The list below ranks them by composite score. Every name here is back-checked daily against next-session SPY return at /scorecard, no edits. This is the most concentrated view of the model's strongest signals.",
    apiParams: { sort: "score", order: "desc", signal: "HIGH CONVICTION", limit: "30" },
    factorEmphasis: "score 85+ across all six factors",
    faq: [
      {
        q: "What is the HIGH CONVICTION tier exactly?",
        a: "It's the score band 85-100 on Tapeline's 0-100 composite. The label is descriptive (the data is aligned) not prescriptive (we are not telling you to buy). HIGH CONVICTION ≠ guaranteed return — it means trend, RS, fundamentals, smart money, macro, and momentum all read constructive at the same time. See /how-it-works for the full methodology.",
      },
      {
        q: "How many stocks are usually in HIGH CONVICTION at once?",
        a: "Typically 30-80 names depending on the macro regime. In Risk On regimes (broad participation, low VIX) the number can spike above 100 — the rising tide lifts more boats into the top tier. In Risk Off the count compresses to 20-30 as confluence becomes rarer.",
      },
      {
        q: "What's the scorecard performance of HIGH CONVICTION picks?",
        a: "Every daily top-10 pick is back-checked against next-day SPY return. The full record — winners and losers — is at /scorecard, including the days the model called HIGH CONVICTION on names that then underperformed. We don't edit the record, and it currently trails SPY. The scorecard is a descriptive track record, not a performance target or a forecast.",
      },
      {
        q: "Is HIGH CONVICTION a buy recommendation?",
        a: "No. Tapeline never tells you to buy, sell, or hold. The descriptive label means the six factors all read constructive at the moment of scoring. The decision — whether to act, position size, when to exit — is yours. See the risk disclosure at /legal/risk.",
      },
    ],
  },
];

export function findStrategy(slug: string): StrategyConfig | null {
  return STRATEGIES.find((s) => s.slug === slug) ?? null;
}
