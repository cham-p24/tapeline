/**
 * Blog post manifest.
 *
 * Adding a post: append to POSTS with a unique slug + a body of HTML
 * fragments. Lightweight by design — when the corpus grows past 10-15
 * posts, swap to MDX or fetch from a CMS without changing the route
 * shape (slug-based).
 */
export type BlogPost = {
  slug: string;
  title: string;
  excerpt: string;
  publishedAt: string; // ISO 8601 date
  author: string;
  body: string; // Trusted HTML — keep this internal-only.
};

export const POSTS: BlogPost[] = [
  {
    slug: "what-smart-money-actually-means",
    title: "What 'Smart Money' actually means in the Tapeline Score (and why it's not what you think).",
    excerpt:
      "'Smart money' is the most misused phrase in retail finance. It's not influencer alpha, not the latest hedge-fund headline, not yesterday's CNBC clip. Here's what Tapeline's Smart Money factor — 15% of the composite — actually measures, what the data sources are, and where the lags lie.",
    publishedAt: "2026-05-13",
    author: "Tapeline",
    body: `
      <p>"Smart money" is the most misused phrase in retail finance. Open
      any trading subreddit, scroll any finance TikTok, look at any
      newsletter sales page — somebody is selling you "what the smart
      money is doing." Almost always, what they mean is "what one
      famous person on CNBC said in a clip yesterday." That's not smart
      money. That's TV.</p>

      <p>Tapeline's Smart Money factor is 15% of the composite score
      (<a href="/how-it-works">see the full formula</a>). It's a real
      number, sourced from real filings, with real lags. This post is
      the deep dive on what it actually measures and where the
      limitations are — because a 15% weight in our scoring engine
      deserves a paragraph more than "trust us, we're tracking the
      smart money."</p>

      <h2>The three data sources behind the factor</h2>
      <p>Smart Money sums to a 0–100 sub-score from three independent
      data streams, each with its own lag and signal-to-noise
      characteristics:</p>
      <ol>
        <li><strong>Congressional disclosures</strong> — required by the
        STOCK Act (Stop Trading on Congressional Knowledge Act, 2012).
        US House and Senate members must disclose trades over $1,000
        within 30–45 days. The signal: when multiple members on relevant
        committees buy or sell the same name, that's information they
        plausibly had access to that the market didn't.</li>
        <li><strong>Insider Form 4 filings</strong> — required by the
        SEC within 2 business days of any insider transaction
        (executives, directors, 10%+ owners). The signal: insiders are
        the only buyers who know more about the company than the
        market, by definition. Clusters of buying — multiple insiders
        in the same window — are a stronger signal than single-buyer
        events.</li>
      </ol>

      <h2>What "smart money buying" actually predicts</h2>
      <p>Each data source has a different predictive horizon. Let me
      walk through the cases that matter:</p>

      <p><strong>Congressional buying</strong> works best on names
      where committee members have informational access — defense
      contractors near a relevant Armed Services committee member, healthcare names near
      a Finance committee member, regulatory beneficiaries before a
      relevant ruling. The base rate of edge is small but non-zero;
      academic studies (Ziobrowski et al., Belmont & Sayers) have
      shown weak positive alpha on a portfolio basis. The Tapeline
      signal weights Congressional flow by relevance — committee
      assignment + filing volume + recency — not raw transaction
      count.</p>

      <p><strong>Insider Form 4 filings</strong> have the shortest lag
      (1–3 business days) and the highest signal-to-noise for cluster
      events. Single-insider buys are weak — executives buy for
      compensation reasons, exercising options is mechanical, charity
      donations get filed too. Multi-insider buys in the same window
      where the executives have no scheduled compensation event are
      what the score weights. Selling clusters are downweighted (they
      can mean tax planning, diversification, or genuine signal — hard
      to disambiguate).</p>

      <h2>Why Smart Money is 15% weight, not higher</h2>
      <p>A natural retail-trader question: if Smart Money is so
      signal-rich, why isn't it 30% of the composite or higher? Three
      reasons:</p>

      <p><strong>The lags compound.</strong> Insider Form 4 filings
      arrive 1–3 days after the trade. Congressional STOCK Act filings
      can be 30–45 days late and include trades that have already been
      unwound. By the time the data is clean and public, much of the
      move has happened.</p>

      <p><strong>It's a confirmation factor, not a leading one.</strong>
      Smart money flow is most useful in confluence with the other
      factors — when Trend, Relative Strength, and Smart Money all
      agree, that's the highest-conviction setup. Smart Money alone is
      late information; combined with leading factors it becomes
      directional certainty.</p>

      <p><strong>Survivorship and crowding.</strong> The fund managers
      most retail tools point at — Buffett, Burry, Tepper — are also
      the most-watched in the world. Their moves are crowded trades by
      the time any 13F filing publishes. Buffett buying Apple in 2016
      was signal; Buffett buying Apple in 2024 was a market price-anchor,
      not new information. This is one reason Tapeline doesn't fold 13F
      filings into the Smart Money sub-score directly — by the time a
      filing is public, the edge is largely priced.</p>

      <h2>How the Tapeline score uses it differently from competitors</h2>
      <p>Most "smart money" scoring in retail tools is broken in one of
      two ways: either it's a single-source (just hedge fund holdings,
      or just Congressional) which misses the confluence signal, or
      it's opaque (Tipranks' Hedge Fund Sentiment is a Smart Score
      input but the weighting and the underlying fund list are not
      published). Tapeline:</p>
      <ul>
        <li>Combines Congressional STOCK Act disclosures and SEC Form 4
        insider transactions into a single 0-100 sub-score with
        published methodology.</li>
        <li>Weights the sub-score at 15% of the composite — high enough
        to matter, low enough not to drown out the leading factors when
        smart money is late or noisy.</li>
        <li>Surfaces the actual data feeds: the Premium tier exposes
        the underlying Congressional trades feed at /app/congress and
        the recent insider buys at /app/holdings — not just the
        aggregated score.</li>
      </ul>

      <h2>What to actually do with this</h2>
      <p>Don't treat Smart Money as a trigger on its own. Treat it as
      a confluence multiplier:</p>
      <ul>
        <li>A 90 Smart Money sub-score on a 40 composite is a value
        signal — institutions are positioning before the market has
        rerated it. Worth a watchlist add.</li>
        <li>A 90 Smart Money sub-score on a 75 composite is confirmation
        — the smart money is in a setup that's already showing up in
        Trend, RS, and Momentum. Standard signal-of-signals.</li>
        <li>A 30 Smart Money sub-score on a 75 composite is a yellow
        flag — strong setup, but institutions and insiders aren't
        confirming. Worth understanding why before sizing up.</li>
        <li>A 90 Smart Money sub-score with no other factor confirming
        is curious but not actionable. Maybe insiders are buying for a
        reason the market hasn't seen yet; maybe they're wrong.</li>
      </ul>

      <p>The point of breaking out the sub-score is exactly this kind
      of nuance. The composite gives you a summary; the breakdown lets
      you read where the conviction actually lives, and where it's
      conspicuously absent.</p>

      <p>You can see live Smart Money sub-scores on any ticker page —
      e.g. <a href="/t/NVDA">/t/NVDA</a>, <a href="/t/AAPL">/t/AAPL</a>
      — or filter by it on the live scanner. The full Congressional
      trades feed and recent insider buys are Premium features at
      /app/congress and /app/holdings; the score weighting itself is
      free for everyone, every row, every day.</p>
    `,
  },
  {
    slug: "stock-screener-vs-stock-scanner",
    title: "Stock screener vs stock scanner: the difference matters in 2026.",
    excerpt:
      "Everyone uses 'screener' and 'scanner' interchangeably. They're not the same thing — and the difference predicts whether your tool will earn its slot in your daily workflow or get cancelled in three months.",
    publishedAt: "2026-05-13",
    author: "Tapeline",
    body: `
      <p>Two of the most common Google queries in active retail trading
      are "stock screener" and "stock scanner". Most people treat them as
      synonyms. Most tools position themselves as both. They are not the
      same thing, and conflating them is how traders end up with $30/mo
      subscriptions they never open.</p>

      <p>The difference, in one sentence: <strong>a screener gives you
      filters; a scanner gives you a verdict.</strong> Both can be useful.
      Only one of them earns daily reuse.</p>

      <h2>What a screener actually does</h2>
      <p>A screener is a multi-field filter. You pick fields (price, P/E,
      RSI, market cap, sector, 20DMA distance, IV rank, insider ownership
      …) and set thresholds. The screener returns the rows that match.
      That's it. The output is a list of tickers; the synthesis — what
      each row actually means — is on you.</p>

      <p>Canonical example: Finviz. You can build a screen for "small-cap
      tech, P/E under 15, RSI below 30, above the 200DMA, insider buying
      last 6 months" and get a list back. The tool has done a database
      query for you. It hasn't formed an opinion.</p>

      <p>This is genuinely useful for a particular workflow: when you
      already know what you're looking for and you need a fast database
      query against the whole market. Anyone who's run a value-investing
      checklist or scanned for option-IV outliers has used screeners well.</p>

      <p>It is <em>not</em> what most retail traders actually need most
      mornings. Most mornings, what a retail trader wants is "what
      changed overnight that I should care about." Screening doesn't
      answer that — you have to know in advance what filter to set.</p>

      <h2>What a scanner actually does</h2>
      <p>A scanner is opinionated. It runs a model — anything from a
      simple weighted score to a deep-learning ensemble — and produces a
      ranked list with a verdict per row. The output is a recommendation
      shape: <em>this</em> is the top of the distribution today,
      <em>here's</em> why, <em>here's</em> how the signal label maps to
      the underlying score.</p>

      <p>The point of a scanner isn't the filters. It's the synthesis.
      The tool has decided what matters, weighted it, and surfaced the
      conclusion. You can disagree with the weighting — but you can't
      avoid <em>seeing</em> the conclusion.</p>

      <p>This matters because the binding constraint on most retail
      traders isn't data access. It's attention. The market has 2,500
      liquid US tickers; nobody reads all of them. A screener helps you
      find what you're looking for. A scanner helps you find what you
      didn't know to look for.</p>

      <h2>Why the distinction predicts six-month retention</h2>
      <p>If you've subscribed to multiple finance tools, you've seen this
      pattern: a screener gets daily use for the first week, then weekly
      use, then monthly, then never. A good scanner gets daily use
      indefinitely. The difference isn't the data behind them — most
      tools use overlapping data feeds. The difference is the cognitive
      load per session.</p>

      <p>Screeners require you to bring the question. Scanners hand you
      the question already formed. When you have 10 minutes before
      market open and three personal-life things on your mind, the
      cognitive cost of "construct a useful screen this morning"
      outweighs the cost of opening the app at all. So you don't open it.</p>

      <p>This isn't a problem with the user. It's a structural property
      of the tool category. The scanner format has lower activation
      energy and therefore higher retention.</p>

      <h2>The "scanner that gives you a screener" trap</h2>
      <p>Many tools position as both. TradingView calls itself a scanner;
      the actual product is a charting platform with filter overlays.
      Trade Ideas has Holly AI (scanner-shaped) AND a flexible filter
      builder (screener-shaped). The marketing fudges the line.</p>

      <p>That's fine as positioning. It does mean you need to look at
      what the tool actually defaults to when you open it. If the
      default view is a blank filter panel waiting for you to build
      something, you have a screener. If the default view is a ranked
      list with a verdict per row, you have a scanner.</p>

      <p>By that test, Tipranks, Zacks, and WallStreetZen are scanners
      (they default to a ranking with a per-row verdict — a Smart Score,
      a Zacks Rank, a Zen Rating). Finviz, in spite of its premium tier,
      is a screener (the default is a filterable table where you bring
      the criteria). Most "AI stock scanners" in 2025/26 are also
      scanners by this test — though many hide the formula behind that
      verdict, which is its own problem
      (<a href="/blog/the-formula-is-public">the formula is public</a>
      goes deep on that).</p>

      <h2>Which one Tapeline is</h2>
      <p>Tapeline is a scanner. The default view at
      <a href="/app/scanner">/app/scanner</a> is a ranked list of every
      liquid US ticker with a 0–100 composite score and a plain-English
      sentence per row. The
      <a href="/how-it-works">six-factor formula</a> is public; the
      <a href="/scorecard">scorecard</a> back-checks every top-10 daily
      pick against the next session vs SPY.</p>

      <p>You can also filter — by sector, by signal label, by minimum
      score, etc. — and the score breakdown lets you reproduce screener-
      shaped queries when you want to. But the default is the verdict.
      That's the design choice, and it's deliberate. Five minutes a
      morning, ranked list, one sentence per row. Click the names you
      care about; ignore the rest.</p>

      <h2>How to decide which you need</h2>
      <p>Pick the screener if:</p>
      <ul>
        <li>You already have a defined strategy (value, momentum,
        options-IV outliers, post-earnings drift) and you need to surface
        candidates that fit it.</li>
        <li>You enjoy designing filters and tuning them over time.</li>
        <li>You're willing to do the synthesis work yourself.</li>
      </ul>
      <p>Pick the scanner if:</p>
      <ul>
        <li>You want a daily ranked starting point you didn't have to
        build.</li>
        <li>You want the tool to do the synthesis work and you'll bring
        the discretion.</li>
        <li>You want accountability — a scanner with a public scorecard
        is the only way to tell whether the model is actually working
        over time.</li>
      </ul>

      <p>Both can be useful. Don't pay for two if you only use one.
      Don't subscribe to either if you can't tell which kind you have.</p>

      <p>If you're not sure where to start, the
      <a href="/compare/finviz">Tapeline vs Finviz comparison</a> goes
      into the screener-vs-scanner question head-to-head with a real
      $24.99/mo entry tier. Both products do useful work; they don't do
      the same work.</p>
    `,
  },
  {
    slug: "reading-a-tapeline-score",
    title: "Reading a Tapeline Score: a 10-minute walkthrough on $NVDA.",
    excerpt:
      "Most scanner scores are a number with no instructions. This is the opposite: a worked example on NVIDIA showing what each of the six factors is saying, how to read the radar, and when the composite is telling you the trade is harder than it looks.",
    publishedAt: "2026-05-12",
    author: "Tapeline",
    body: `
      <p>Most stock scanners give you a score and call it done. The score is
      the easy part — the hard part is knowing what it's actually telling you.
      Two stocks can both score 58, and one is a textbook setup while the
      other is a fundamentally strong name that the market hasn't priced in
      yet. The composite hides the difference; the factor breakdown shows it.</p>

      <p>So here's the walkthrough I wish every scanner gave you: a real
      ticker, a real score, and what each of the six numbers underneath is
      telling you. We'll do <a href="/t/NVDA"><strong>NVDA</strong></a> — at
      the time of writing, it's sitting at a composite of <strong>57.9</strong>
      with the signal <strong>CONSTRUCTIVE</strong>. That's a 58 with three
      different stories inside it, and reading them all is the difference
      between an action and a watch.</p>

      <h2>Step 1 — Don't start with the composite</h2>
      <p>The composite is a summary. It's where most traders stop. It's where
      every other scanner stops too. The composite tells you "the data is
      roughly net-positive on this name" — and that's about it. Same number
      can come from a sleepy large-cap with strong fundamentals and a weak
      chart, or from a momentum name where the trend is on fire but the
      balance sheet is questionable. Same 58, two opposite trades.</p>

      <p>So we ignore the headline for a minute and look at the six factors.
      The Tapeline radar shows them as a hexagon — six axes, each one a
      sub-score from 0–100, all weighted into the composite with the
      <a href="/how-it-works">published weights</a>:</p>

      <pre style="background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;padding:18px;overflow-x:auto;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:13px;line-height:1.5;">
NVDA — composite 57.9 (CONSTRUCTIVE)

  Trend                41   weight 25%
  Relative Strength    32   weight 20%
  Fundamentals         55   weight 15%
  Smart Money          97   weight 15%
  Macro                65   weight 15%
  Momentum             87   weight 10%</pre>

      <p>That's where the actual signal lives. Now we read it.</p>

      <h2>Step 2 — Look for the contradictions</h2>
      <p>Most scores tell a single story. Strong trend, strong RS, strong
      fundamentals — easy, the data points the same direction, you're in or
      out. NVDA doesn't do that. Look at the spread:</p>

      <ul>
        <li><strong>Smart Money 97</strong> (top 3%) — insiders are
        net-accumulating. Congressional disclosures and SEC Form 4 buying
        — both flowing in.</li>
        <li><strong>Momentum 87</strong> (top 13%) — short-term price action
        is accelerating, volume is confirming, breakouts are recent.</li>
        <li><strong>Trend 41</strong> (below median) — but the multi-timeframe
        trend isn't fully aligned yet. The weekly and monthly haven't caught
        up to the burst the momentum factor is seeing.</li>
        <li><strong>Relative Strength 32</strong> (bottom third) — and the
        name is actually <em>lagging</em> tech peers on the multi-week view.</li>
      </ul>

      <p>That's a contradiction. Smart money is in. Short-term price is
      ripping. But the longer-timeframe trend hasn't confirmed yet, and the
      sector is running ahead of it on a 1M view. You read that as: the
      institutional buying may be early to a move that hasn't fully started,
      OR it's catching a bounce inside a chop and the bigger trend won't
      cooperate. The score can't tell you which. You have to overlay your
      own read of where we are in the regime.</p>

      <h2>Step 3 — Use the macro factor to ground it</h2>
      <p>This is the factor most other scanners don't expose at all. NVDA's
      <strong>Macro 65</strong> says the broader regime is mildly supportive —
      breadth is healthy, the 10Y isn't spiking, VIX is contained. That
      matters. A 58 composite in a friendly regime reads very differently
      from a 58 composite during a vol shock; the latter is a "wait and see"
      and the former is closer to "this is a real setup the regime isn't
      fighting."</p>

      <p>You can think of macro as the gain on the whole signal. Same factor
      configuration in a hostile regime gets a different verdict. We surface
      it explicitly so you don't have to remember.</p>

      <h2>Step 4 — Read the fundamentals factor like a quality filter</h2>
      <p><strong>Fundamentals 55</strong> on NVDA is the least interesting
      number in the row, which is itself informative. It says: this isn't a
      fundamentals trade. The earnings quality, margin trend, balance-sheet
      health — all sitting in the "supportive but not the reason to be here"
      zone. If you're trading on a multi-quarter horizon, you'd want this
      number higher. If you're trading the next two weeks, 55 is fine — it's
      saying the name isn't fundamentally broken.</p>

      <h2>Step 5 — What the composite actually meant</h2>
      <p>So back to the headline number. 57.9 CONSTRUCTIVE on NVDA isn't
      "buy this." It's "the data is net-positive but split between leading
      and lagging factors, in a regime that's mildly helpful." If you were
      already long, the composite says hold. If you were flat, the composite
      says either wait for the trend factor to confirm (it'll climb when the
      weekly catches up to the daily) or take a smaller-than-normal size
      because the leading-vs-lagging spread is wide.</p>

      <p>Every other scanner that gives you a "BUY" or a "7/10" hides this.
      The composite hides it too. The six-factor radar is what shows it.</p>

      <h2>Step 6 — Compare to what the scorecard recorded</h2>
      <p>This part is the accountability check. On the
      <a href="/scorecard">public scorecard</a>, every top-10 daily pick
      we've flagged is logged with its composite, its signal label, its
      one-sentence reason, and the next-day return vs SPY. So if NVDA
      surfaces in tomorrow's top 10, we'll record what the model thought
      tonight, and we'll know in 24 hours whether the read held up.</p>

      <p>Most scanners never close that loop. They tell you the score
      tonight and they're silent the next morning. We're the opposite:
      tonight's score lives on the page tomorrow, with the realised return
      next to it. If our reads are systematically wrong on a factor,
      <em>you can see it</em>, and you can adjust.</p>

      <h2>The five things to take from this</h2>
      <ol>
        <li>The composite is a summary. The factor row is the signal.</li>
        <li>Look for contradictions between Trend, RS, Smart Money, and
        Momentum — that's where the real read lives.</li>
        <li>The Macro factor scales everything; same composite in different
        regimes is not the same trade.</li>
        <li>Fundamentals is a quality filter, not a directional vote — use
        it to confirm the name isn't broken.</li>
        <li>Cross-reference every read against the scorecard. If our model
        is consistently wrong on the kind of setup you're looking at, the
        scorecard will show it.</li>
      </ol>

      <p>Run the same walkthrough on any ticker you care about at
      <a href="/t/AAPL">/t/&lt;TICKER&gt;</a>. Every page shows the
      composite, the radar, the factor sub-scores, and the why sentence.
      If you want them all in one view ranked by score, the live
      <a href="/app/scanner">scanner</a> is the home for that — Free
      gets the top 20 tickers 24h-delayed, the
      <a href="/signup">14-day trial</a> opens the full universe live.</p>
    `,
  },
  {
    slug: "evaluating-a-stock-scanner",
    title: "How to evaluate a stock scanner: 5 questions before you pay.",
    excerpt:
      "Most scanner sales pages are 50 filters and a screenshot. Here are the five questions that actually predict whether a tool will be useful in six months — and how Finviz, Trade Ideas, Zacks, and Tapeline answer them.",
    publishedAt: "2026-05-03",
    author: "Tapeline",
    body: `
      <p>I've signed up for almost every prosumer stock scanner since 2018.
      Most fail the same way: the tool is fine for a week, then you realise
      you have no way to tell whether the calls it surfaces are actually
      working. By month three you've added it to the pile of $20-$50/month
      subscriptions you keep forgetting to cancel.</p>

      <p>If you're shopping for a scanner, these five questions will save you
      the cycle:</p>

      <h2>1. Can you see the formula?</h2>
      <p>If the answer is "we use a proprietary blend of signals" you're being
      sold magic. The two questions you can't answer about magic are "is this
      working?" and "will this still work next month?" Tipranks, Zacks,
      Kavout, WallStreetZen all hide theirs. Tapeline publishes the exact
      6-factor weighted equation on <a href="/how-it-works">/how-it-works</a>.</p>

      <h2>2. Where's the public scorecard?</h2>
      <p>Newsletter shops have known for 30 years that you should hide your
      losers. Mark Hulbert built a career being the only neutral grader of
      newsletter performance because everyone else hid the data. Look for
      a tool that <em>auto-publishes</em> every call it makes against the
      next-day market move — not a curated highlight reel. We do this at
      <a href="/scorecard">/scorecard</a>; almost nobody else does.</p>

      <h2>3. What does the data come from?</h2>
      <p>"AI-powered signals" usually means "we bought a feed from a third-party market-data feed
      and slapped a score on top." Which is fine — that's also our spine.
      But know it. Bloomberg Terminal at $32k/yr uses similar feeds; the
      premium is the speed and breadth of their proprietary chat and
      curated news, not the raw data. Anyone charging $200/month for
      "exclusive AI signals" is reselling a third-party market-data feed and a third-party data feed.</p>

      <h2>4. Is the cheapest tier real?</h2>
      <p>Test it. If the free or cheapest paid tier strips out so many
      features the product is unusable, the team is incentivised to
      upgrade-trap rather than retain. Tapeline Free is hard-capped to
      20 tickers and 24-hour delayed by design — the real product, just
      narrower — because that's the most honest preview.</p>

      <h2>5. Can you cancel in one click?</h2>
      <p>If you have to email support to cancel, that's a tell about how
      the team treats you generally. Stripe-portal cancel-in-one-click is
      table stakes; if it's not there, leave. (Yes, ours is.)</p>

      <p>If a tool can't answer questions 1 and 2, walk away regardless of
      price. They're cheap to ask and predict 80% of the future regret.</p>
    `,
  },
  {
    slug: "what-signal-labels-mean",
    title: "What our signal labels mean: HIGH CONVICTION through WEAK.",
    excerpt:
      "Six descriptive labels, no buy/sell language. Here's what each one represents in the underlying score, why we picked descriptive words, and what it means when a ticker moves between them.",
    publishedAt: "2026-05-03",
    author: "Tapeline",
    body: `
      <p>Every Tapeline ticker carries one of six labels. They're not buy
      signals. They're descriptions of the score's tier — which exists for
      legal reasons (we are not a registered investment adviser) and for
      design reasons (you should make the call, we just summarise the data).</p>

      <h2>The mapping</h2>
      <ul>
        <li><strong>HIGH CONVICTION</strong> (85-100) — all six factors
        aligned positive. Trend up, RS strong, fundamentals fine, smart-money
        net buying, macro supportive, momentum healthy. Rare.</li>
        <li><strong>STRONG SETUP</strong> (70-84) — most factors favourable,
        usually 4-5 of 6. The kind of name that shows up in our scorecard
        most often.</li>
        <li><strong>CONSTRUCTIVE</strong> (55-69) — net positive but with
        meaningful trade-offs. Often a great fundamentals story with a weak
        trend, or a hot trend with stretched valuation.</li>
        <li><strong>NEUTRAL</strong> (40-54) — factors cancel. The data
        isn't telling you to do anything.</li>
        <li><strong>CAUTION</strong> (25-39) — more factors negative than
        positive. Trend down, RS lagging, smart money distributing.</li>
        <li><strong>WEAK</strong> (0-24) — broadly negative. Almost always
        reflects a clear downtrend confirmed by deteriorating fundamentals.</li>
      </ul>

      <h2>Why descriptive, not prescriptive</h2>
      <p>The previous version of these labels said BUY NOW, STRONG
      ACCUMULATE, ACCUMULATE, HOLD, WATCH, AVOID. We changed them on day
      one. Two reasons:</p>
      <ul>
        <li><strong>Legal.</strong> Prescriptive language pushes you toward
        being classified as an investment adviser in the US, AU, and UK.
        Descriptive language ("here's what the data says") protects the
        publisher's exemption.</li>
        <li><strong>Honest.</strong> A score of 92 doesn't mean you should
        buy. It means six independent signals are aligned. Whether to act
        depends on your portfolio, risk tolerance, time horizon, and tax
        situation — none of which we know.</li>
      </ul>

      <h2>What a label change means</h2>
      <p>The most useful watchlist signal isn't an absolute level — it's a
      transition. CONSTRUCTIVE → STRONG SETUP is a meaningful shift; STRONG
      SETUP → STRONG SETUP with the score moving from 71 to 84 is also
      meaningful. We send watchlist alerts when the underlying score moves
      by your threshold (default 10 points), not just when the label flips,
      so you don't miss meaningful intra-tier moves.</p>

      <p>If you're new and want to play with this, the public scorecard at
      <a href="/scorecard">/scorecard</a> shows every top-10 we've published
      and how each name moved the next day. That's the most honest demo of
      what the labels actually predict.</p>
    `,
  },
  {
    slug: "why-we-score-2500-not-5000",
    title: "Why we score 2,500 tickers, not 5,000.",
    excerpt:
      "The a third-party market-data feed feed gives us 5,757 US tickers. We actively score 2,500. Here's why that cutoff exists, what we do with the rest, and why bigger isn't better.",
    publishedAt: "2026-05-03",
    author: "Tapeline",
    body: `
      <p>The data feed (a third-party market-data feed) gives us coverage of
      every listed US security. About 5,757 tickers, after filtering out
      OTC. We actively score the top 2,500 by daily dollar-volume.
      Roughly half the new-user feedback is "why isn't $XYZ scored?" — so
      here's the reasoning, written once.</p>

      <h2>The filter is liquidity</h2>
      <p>The 2,500 are picked by daily dollar-volume — price × volume —
      and the cutoff lands well below the S&amp;P MidCap 400, deep into
      small-cap territory. Everything below has bid-ask spreads wide
      enough that the "score" stops representing anything actionable. A
      90 score on a $0.15 stock that trades 80,000 shares a day is a
      fiction; you can't get in or out at that price without moving the
      tape against yourself.</p>

      <h2>The factors aren't equally available below the cutoff</h2>
      <p>Trend, momentum, and macro work fine on any ticker with a year
      of bars. Fundamentals and insider Form 4 are sparse for sub-$200M
      caps — small companies just file less often, and analyst coverage
      thins out. Forcing a score across the entire 5,757-row universe
      would mean ~3,200 confidence values landing under 40%. That's
      noise, not signal — exactly the experience we're trying to
      replace.</p>

      <h2>What we do with the other 3,200</h2>
      <p>The full 5,757-row universe table is auto-populated weekly from
      a third-party market-data feed's reference API. We use it for: watchlist tracking (you
      can watch any ticker, scored or not), per-ticker pages with price
      and 1-day change, news feeds with sentiment tagging, and ranking —
      so when liquidity grows on a name, it gets promoted into the
      active 2,500 automatically on the next refresh cycle.</p>

      <h2>Why not just score all 5,757?</h2>
      <p>Two reasons. First, the noise above. Second, a third-party data feed's free tier
      is 60 calls/minute — enough for the fundamentals refresh on 2,500
      names but not 5,000+. A bigger universe means a bigger a third-party data feed bill,
      not a better product. We'll only expand if customer behaviour says
      the marginal names are actually being scanned.</p>

      <p>The 2,500 covers basically every US name a retail trader is
      plausibly considering: every S&amp;P 500 + every NASDAQ-100 + every
      Russell 1000 component, plus the most actively-traded sector and
      commodity ETFs. If your watchlist already lives in that range —
      which most do — Tapeline scores everything you care about.</p>
    `,
  },
  {
    slug: "the-formula-is-public",
    title: "The formula is public. Here's why that matters.",
    excerpt:
      "Every other prosumer score-per-ticker tool hides their methodology as IP. We publish the six factors and the exact weights — because the day the formula stops working, you should know to leave.",
    publishedAt: "2026-05-02",
    author: "Tapeline",
    body: `
      <p>If you ask Tipranks why a stock has a 7/10 Smart Score, you get
      "we aggregate analyst consensus, hedge fund moves, insider trades, and
      blogger sentiment." If you ask Zacks why a stock has a #1 rank, the answer
      is "earnings estimate revisions" but the cutoffs are proprietary. If you ask
      Kavout why their Kai Score moved, you get a black-box ML answer.</p>

      <p>Tapeline gives you the literal expression. It's on
      <a href="/how-it-works">/how-it-works</a> and reproduced here:</p>

      <pre style="background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;padding:18px;overflow-x:auto;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:14px;line-height:1.5;">
score = 0.25 × trend
      + 0.20 × relative_strength
      + 0.15 × fundamentals
      + 0.15 × smart_money
      + 0.15 × macro
      + 0.10 × momentum</pre>

      <p>Why publish it?</p>
      <ul>
        <li><strong>Trust compounds when you can audit.</strong> If you find a
        ticker scoring 90 when its trend is clearly broken, you can call it out
        — and we'd rather you do that than churn silently.</li>
        <li><strong>The moat isn't the formula, it's the data spine.</strong>
        Plenty of competitors could copy the equation. None of them will
        publish their public scorecard back-checking every call against
        next-day prices the way we do.</li>
        <li><strong>If the formula stops working, you should leave.</strong>
        We'd rather you make that call honestly than discover via a slow drip
        of bad picks.</li>
      </ul>

      <p>The weights are versioned in our changelog. The day they change, you
      see why. That's the whole product, in one paragraph.</p>
    `,
  },
  // ---- 2026-05-20: educational long-tail posts ----
  // Each post targets a high-volume "explain this concept" search query
  // that retail traders type into Google constantly. Internal links back to
  // /how-it-works, /scorecard, and the relevant /best-stocks-for/ slug so
  // the educational traffic warm-funnels into the product.
  {
    slug: "what-is-rsi",
    title: "What is RSI in stocks? A retail trader's plain-English guide (with examples).",
    excerpt:
      "RSI stands for Relative Strength Index — a 0–100 momentum oscillator that signals overbought vs oversold conditions. Here's how it actually works, what the 70/30 thresholds mean, and the three mistakes retail traders make using it.",
    publishedAt: "2026-05-20",
    author: "Tapeline",
    body: `
      <p>RSI is one of those acronyms every trading YouTube channel mentions
      and almost no one explains properly. Here's the plain-English version:
      what it is, how it's computed, what the 70/30 thresholds mean, and the
      three mistakes retail traders make using it.</p>

      <h2>What RSI actually measures</h2>
      <p><strong>RSI = Relative Strength Index</strong>. It's a momentum
      oscillator that compares the magnitude of recent gains to the magnitude
      of recent losses over a lookback period (default: 14 trading days).
      The output is a 0–100 number, where:</p>
      <ul>
        <li><strong>RSI &gt; 70</strong> — traditionally read as "overbought".
        The stock has rallied hard and may be due for a pause or pullback.</li>
        <li><strong>RSI &lt; 30</strong> — traditionally read as "oversold".
        The stock has dropped hard and may be due for a bounce.</li>
        <li><strong>RSI 30–70</strong> — neutral zone. Most of the time RSI
        sits here and isn't telling you much on its own.</li>
      </ul>

      <h2>How RSI is computed</h2>
      <p>The formula is straightforward. Over the lookback window (14 days
      standard):</p>
      <pre>
RS = average gain / average loss
RSI = 100 - (100 / (1 + RS))</pre>
      <p>Average gain = sum of positive daily changes / 14. Average loss =
      sum of absolute negative daily changes / 14. The 100 / (1 + RS) part
      bounds the output to 0–100. The exact arithmetic doesn't matter for
      trading; the intuition does: <strong>RSI rises when up-days outweigh
      down-days, and falls when down-days outweigh up-days.</strong></p>

      <h2>The three mistakes retail traders make with RSI</h2>

      <h3>1. Trading the 70/30 cross mechanically</h3>
      <p>"RSI hit 70, time to short" is the most common — and the most
      reliably wrong — RSI rule. Strong uptrends ride RSI in the 70–90 range
      for weeks. Selling every time RSI crosses 70 means selling every
      strong rally early. Strong downtrends similarly camp out at RSI 20–30.
      Mechanical 70/30 trades work in choppy range-bound markets and lose
      in trending ones.</p>

      <h3>2. Ignoring the timeframe</h3>
      <p>RSI on a 1-minute chart is noise. RSI on a daily chart is signal.
      RSI on a weekly chart is a long-term sentiment gauge. Same number,
      wildly different meanings. Most retail traders look at RSI on whatever
      timeframe their chart happens to be open to, then trade as if the
      signal is universal. It isn't. Pick your timeframe deliberately.</p>

      <h3>3. Treating RSI as a standalone signal</h3>
      <p>RSI is most useful in confluence with other indicators — trend,
      relative strength vs the market, volume, fundamentals. Pure-RSI
      trading is gambling on mean reversion in a market that mostly
      trends. RSI as part of a broader composite (like
      <a href="/how-it-works">Tapeline's 6-factor score</a>) is a far more
      reliable filter.</p>

      <h2>How Tapeline uses RSI</h2>
      <p>RSI feeds into the <strong>Momentum</strong> factor (10% weight in
      the composite). Specifically, the Momentum factor looks at RSI
      position (where in the 0–100 range), the rate of change of RSI (is
      momentum accelerating or decelerating), and divergences between RSI
      and price (rare, but high-signal when they appear).</p>

      <p>The reason Momentum is only 10% of the composite — and not, say,
      30% — is exactly because pure-momentum signals like RSI mean-revert
      so reliably. The composite balances RSI against
      <a href="/how-it-works">Trend, Relative Strength, Fundamentals,
      Smart Money, and Macro</a> so you're not betting your account on a
      single overbought reading.</p>

      <h2>Practical use cases</h2>
      <ul>
        <li><strong>Pullback entries</strong> — in a confirmed uptrend
        (price above 200DMA, rising RS line), an RSI dip into 35–45 is a
        higher-probability pullback entry than a random pullback to a
        chart level. Confluence with the bigger trend.</li>
        <li><strong>Exhaustion warning</strong> — RSI above 80 on the
        daily, sustained for multiple sessions, is a yellow flag that the
        rally is running on fumes. Doesn't mean short; means don't add.</li>
        <li><strong>Divergence</strong> — when price makes a new high but
        RSI makes a lower high (or vice versa), the underlying momentum
        isn't confirming the price action. Rare but high-quality when
        you spot it.</li>
      </ul>

      <h2>The bottom line</h2>
      <p>RSI is a useful tool — not a crystal ball. Treat the 70/30
      thresholds as warnings, not triggers. Pair RSI with trend and
      relative-strength context. Don't fight strong trends because RSI
      is "overbought" — that's how retail traders blow up.</p>

      <p>Want to see RSI in context for every US ticker? The Tapeline
      composite blends RSI into a single 0–100 score along with five other
      factors. <a href="/signup">Try the 14-day Premium trial</a> — no
      credit card.</p>
    `,
  },
  {
    slug: "how-to-find-momentum-stocks",
    title: "How to find momentum stocks (without buying every spike).",
    excerpt:
      "Momentum investing rewards stocks where price is sustainably accelerating up. The problem: pure 'biggest movers' lists are mostly noise. Here's how to filter for real momentum, including the three confluence checks that separate runners from head-fakes.",
    publishedAt: "2026-05-20",
    author: "Tapeline",
    body: `
      <p>Every retail trader wants to find momentum stocks early. The problem:
      pure "biggest movers today" lists are mostly noise — small-caps spiking
      on rumours, short squeezes that fail by tomorrow, news-pop reversals.
      Finding <em>real</em> momentum means filtering for stocks where the
      move is backed by trend, volume, and underlying fundamentals — not
      stocks where the move <em>is</em> the trade.</p>

      <p>This post is the practical playbook. Three confluence checks to
      apply to any momentum candidate before you take a position.</p>

      <h2>What "momentum" actually means</h2>
      <p>Academic finance defines momentum as the tendency of stocks that
      have outperformed over a 3–12 month window to continue outperforming
      over the next 1–3 months. Retail finance uses "momentum" more loosely
      — usually to mean "a stock that's moving up right now." Both are valid
      but they're not the same thing.</p>

      <p>For trading purposes, momentum is the combination of: <strong>price
      acceleration</strong> (the rate of price change is increasing),
      <strong>volume confirmation</strong> (more shares trading on up-days
      than down-days), and <strong>relative strength</strong> (the stock is
      outperforming its sector and the broader market). Without all three,
      what you have is a price spike, not momentum.</p>

      <h2>The three confluence checks</h2>

      <h3>1. Is the stock above its 200-day moving average?</h3>
      <p>Simple but devastating. Real momentum almost always happens in
      stocks already in established uptrends — meaning price is above the
      200-day moving average and the 200DMA itself is sloping up. A stock
      surging 15% in a day while still below its 200DMA is more often a
      dead-cat bounce than a momentum breakout. The 200DMA filter cuts the
      list by 60–70% and removes most of the false signals.</p>

      <h3>2. Is volume confirming the move?</h3>
      <p>Real momentum moves on above-average volume. A 5% up-day on 0.5×
      average volume is suspicious — somebody's chasing the price but the
      institutional flow isn't there. A 5% up-day on 2× average volume is
      structural — real demand is showing up. Always check the volume
      multiple (day's volume / 20-day average) before treating a price
      move as actionable. Below 1.2× is weak; above 1.5× is real.</p>

      <h3>3. Is the stock outperforming its sector AND the S&amp;P 500?</h3>
      <p>The relative-strength check. If the stock is up 10% but the sector
      ETF is also up 8%, what you have is sector beta — the stock isn't
      actually doing anything special, the whole sector is moving. Real
      momentum stocks show meaningful spread between the stock's return
      and the sector's return, AND between the sector's return and SPY's.
      That's leadership. Without it, you're just buying the sector at a
      slight markup.</p>

      <h2>The mistakes to avoid</h2>

      <h3>Buying after the gap</h3>
      <p>Most momentum trades fail because the trader sees the move, buys
      at the top of the daily range, and watches it mean-revert. The
      structural setup is identified the day <em>before</em> the spike —
      stocks already in uptrends with rising relative strength and
      accumulating volume, that haven't yet had their breakout day.
      Tapeline's composite is built to catch these <em>before</em> the
      spike, not after.</p>

      <h3>Ignoring fundamentals</h3>
      <p>Pure-momentum scans pick up junk stocks too. A $2 small-cap with
      no revenue spiking 80% on a press release isn't momentum — it's a
      pump. Real momentum tends to come with at least decent fundamentals
      (positive cash flow, manageable debt, sector tailwind). When a
      momentum scan and a fundamentals scan disagree, trust the
      fundamentals scan.</p>

      <h3>Treating every list the same</h3>
      <p>A "top 30 by 1-day move" list and a "top 30 by 1-month move" list
      are wildly different universes. Day-trading momentum lives in the
      1-day list. Swing-trading momentum lives in the 5-day to 1-month
      list. Long-term position momentum lives in the 3-month to 12-month
      list. Pick the timeframe that matches how long you intend to hold,
      then filter that specific list.</p>

      <h2>How Tapeline filters momentum</h2>
      <p>The Tapeline composite includes a Momentum factor (10% weight)
      that captures price acceleration, RSI position, MACD posture, and
      volume confirmation in a single 0–100 sub-score. But Momentum alone
      isn't enough — the composite balances it against Trend (25%),
      Relative Strength (20%), and Fundamentals (15%) precisely because
      pure-momentum signals mean-revert.</p>

      <p>The pre-filtered momentum lists are at
      <a href="/best-stocks-for/momentum">/best-stocks-for/momentum</a>
      (5-day move + composite 60+),
      <a href="/best-stocks-for/breakouts">/best-stocks-for/breakouts</a>
      (1-day move + composite 70+), and
      <a href="/best-stocks-for/growth-stocks">/best-stocks-for/growth-stocks</a>
      (1-month move + composite 65+). Same universe, different timeframes.
      Pick the one that matches your holding period.</p>

      <h2>The bottom line</h2>
      <p>Finding momentum stocks is easy. Finding the momentum stocks
      that <em>continue</em> is hard — and is mostly about filtering out
      the head-fakes. Confluence is the answer: above 200DMA, volume
      confirming, beating sector + SPY, supportive fundamentals. Any one
      of those is necessary but not sufficient. All four together is the
      pattern.</p>
    `,
  },
  {
    slug: "best-time-to-buy-stocks",
    title: "What's the best time to buy stocks? The data answer (it's not what you'd think).",
    excerpt:
      "Retail trading folklore says 'buy at the open', 'wait until the last hour', or 'never on Mondays'. We pulled the data on intraday + day-of-week + month-of-year patterns. Here's what actually holds up — and what's just superstition.",
    publishedAt: "2026-05-20",
    author: "Tapeline",
    body: `
      <p>Every retail trader has heard them: "Mondays are bearish." "Buy at
      the open, sell at the close." "Avoid trading the first 30 minutes."
      "Tax-loss season hits the market in November." A lot of this is
      folklore that survived because it sounds plausible. Some of it is
      real, with explanations rooted in market structure.</p>

      <p>Here's what actually holds up under data scrutiny — for the
      retail trader making decisions about <em>when</em> to enter a
      position, not just which one.</p>

      <h2>Day-of-week effects</h2>

      <h3>The Monday Effect (mostly gone)</h3>
      <p>Decades of academic studies documented a "Monday effect" —
      historical underperformance of Mondays vs Tuesday–Friday. The
      explanation was bad news being held until weekends + Sunday-night
      hand-wringing pricing in by Monday open. Most studies after 2010
      find the effect has faded substantially — possibly because
      24/7 financial news + extended-hours trading prices weekend news
      in faster. Mondays still skew slightly negative on average but the
      edge is too small to trade on its own.</p>

      <h3>The Friday-into-Monday rollover</h3>
      <p>One pattern that <em>has</em> held up: Friday afternoons see
      reduced institutional positioning ahead of the weekend, which can
      produce thin liquidity and outsized moves on relatively normal
      news. If you're entering a position late Friday, expect more noise
      than usual. If you're holding through weekend, expect a Monday gap
      either direction.</p>

      <h2>Intraday timing</h2>

      <h3>The first 30 minutes</h3>
      <p>The market open (9:30–10:00 ET) is the most volatile window of
      the trading day. Spreads are wider, prices gap on overnight news,
      retail order flow is concentrated. For most retail traders, the
      first 30 minutes is the worst time to enter — you're trading
      against algos optimised for that exact window. Wait until 10:00 ET
      and the picture stabilises substantially.</p>

      <h3>The midday lull</h3>
      <p>11:30 ET to roughly 14:00 ET is the lowest-volume window of the
      US session — institutional desks are at lunch, news flow slows.
      Prices drift, ranges compress. For swing traders, this is a fine
      window to enter at a confirmed setup. For day traders, this is
      often a time to do nothing.</p>

      <h3>The close</h3>
      <p>The last 30 minutes (15:30–16:00 ET) sees a return of volume
      and volatility as end-of-day flows hit: closing auctions, MOC
      orders, index rebalancing. The closing print sets the official
      record for the day's price. If you're entering on a confirmed
      breakout, the last hour is often a stronger entry than the
      midday range because volume confirms the move.</p>

      <h2>Month and quarter effects</h2>

      <h3>The January Effect</h3>
      <p>Small-caps have historically outperformed in January, possibly
      because of December tax-loss selling reversing + new-year fund
      allocations. The effect has weakened over the last 20 years but
      isn't dead. Small-cap-heavy strategies have a mild structural
      tailwind in early January.</p>

      <h3>Sell in May and go away</h3>
      <p>This one is half-real. The May–October window has, on average,
      lower returns than the November–April window over the last century.
      But "lower" doesn't mean "negative" — May–October has been
      positive on average. The trade isn't "sell in May" so much as "be
      a bit more selective about new positions in the summer months."</p>

      <h3>Earnings seasons</h3>
      <p>Mid-January, mid-April, mid-July, mid-October — earnings
      announcements concentrate. Implied volatility rises across the
      board. Individual stocks gap on earnings beats and misses. If
      you're trading individual names, knowing which weeks are dense
      with reports for your holdings matters more than any seasonal
      calendar effect. Tapeline's earnings calendar at
      <a href="/app/earnings">/app/earnings</a> filters to the names
      you actually care about.</p>

      <h2>The honest answer</h2>
      <p>The best time to buy a stock is when the setup is right, not
      when the calendar says so. Day-of-week effects are weak and
      mostly arbitraged away. Intraday timing matters more — avoid
      the first 30 minutes, use the close window for confirmed
      breakouts, treat the midday lull as a research window. Month
      effects are real but small.</p>

      <p>The bigger question — "is this stock setting up?" — matters
      far more than "what time of day is it?" The Tapeline composite
      is built to answer the first question. The second question
      mostly takes care of itself once the first one is settled.</p>

      <p><a href="/signup">Try the 14-day Premium trial</a> — no card,
      cancel in one click. Read every score the same way our public
      scorecard does.</p>
    `,
  },
  {
    slug: "best-stock-scanner-under-30",
    title: "Best stock scanner under $30/month in 2026 (honest cost-quality breakdown).",
    excerpt:
      "We benchmarked the four sub-$30/mo stock scanners retail traders actually consider in 2026 — Finviz Elite, Stock Rover Essentials, Zacks Premium, and Tapeline Pro — across feature depth, data freshness, and (the part nobody else publishes) whether the picks beat SPY. Here's the honest matrix.",
    publishedAt: "2026-05-20",
    author: "Tapeline",
    body: `
      <p>Most "best stock scanner under $30" articles you find online
      are affiliate-fee farms. The author gets paid per signup, every
      product gets a 9/10 review, and the conclusion is always "they're
      all great, pick what suits you." If you've read more than two of
      them, you know the type.</p>

      <p>This isn't that. Tapeline is one of the four scanners in this
      matrix and we're not going to pretend otherwise — but the
      comparison is structured so you can rule us out cleanly if we
      don't fit. The criteria are public, the rankings are explicit,
      and the rows where we lose are highlighted, not hidden.</p>

      <h2>The four scanners under $30/mo retail traders actually buy</h2>

      <p>"Under $30/mo" rules out the institutional tier — Bloomberg
      Terminal ($24K/yr), Koyfin Plus ($59/mo), Trade Ideas Premium
      ($188/mo), Benzinga Pro ($177/mo). Those are tools built for
      sell-side and prop-desk users; if you're a retail trader running
      one or two accounts, they're not realistic. The actual sub-$30/mo
      shortlist in 2026:</p>

      <ul>
        <li><strong>Finviz Elite</strong> — $24.96/mo annual ($29.96/mo
        monthly). The veteran. Maps + heatmaps + 70+ screener filters.
        Free tier is the entry point most retail traders started with.</li>
        <li><strong>Stock Rover Essentials</strong> — $7.99/mo annual
        ($9.99/mo monthly). Long-only fundamentals focus. Strong
        portfolio analytics, weaker on intraday data.</li>
        <li><strong>Zacks Premium</strong> — $20.83/mo annual ($24.95/mo
        monthly). Earnings + analyst-rating focus. The Zacks Rank is the
        core differentiator; everything else is supporting.</li>
        <li><strong>Tapeline Pro</strong> — $24.99/mo annual ($29.99/mo
        monthly). One 0-100 composite per ticker from a
        <a href="/how-it-works">public 6-factor formula</a>, with a
        public daily back-checked scorecard.</li>
      </ul>

      <h2>The matrix (data current as of 2026-05-21)</h2>

      <p>I've split the comparison into four axes that actually matter
      to the retail trader spending $25/mo on a scanner: feature depth,
      data freshness, transparency of the methodology, and — the one
      nobody else publishes — whether the daily picks actually beat
      SPY.</p>

      <h3>1. Feature depth</h3>

      <p><strong>Finviz Elite</strong> wins on raw filter count — 70+
      screening criteria, real-time data, advanced charting, custom
      groups. If you're the type who wants to express a thesis as a
      seven-condition AND-filter, it's hard to beat.</p>

      <p><strong>Stock Rover</strong> wins on fundamentals depth —
      150+ fundamental metrics, multi-year history, portfolio tracking
      with allocation drift alerts. Built for the long-only quality
      investor.</p>

      <p><strong>Zacks</strong> wins on earnings + analyst ratings —
      the Zacks Rank is the original "stock signal" and still the
      reference for that style of scoring. Earnings ESP, broker rating
      changes, and surprise history are deeper than competitors.</p>

      <p><strong>Tapeline Pro</strong> ranks lower on raw filter
      breadth (we don't try to expose 70 filters), higher on signal
      density — the composite score does the synthesis work that
      filter-by-filter screening makes the user do manually. Different
      product philosophy, not necessarily a better one for everyone.</p>

      <h3>2. Data freshness</h3>

      <p>This one's measurable. We checked the actual delay on each
      product's free tier:</p>

      <ul>
        <li>Finviz free: 15-minute delay. Elite: real-time.</li>
        <li>Stock Rover free: end-of-day. Essentials: 15-minute delay.</li>
        <li>Zacks free: 20-minute delay. Premium: real-time on most exchanges.</li>
        <li>Tapeline free: 24-hour delay (intentional gating; full
        universe ~60-second freshness on Pro+).</li>
      </ul>

      <p>Tapeline's free tier delay is the harshest of the four, which
      is a deliberate trade-off — we want Pro to be obviously
      differentiated. If you're testing the product, the
      <a href="/scorecard">public scorecard</a> shows the real
      composite quality at full freshness.</p>

      <h3>3. Methodology transparency</h3>

      <p>This is the criterion most retail-trader comparisons skip
      entirely. "How is the score calculated?" is a question every
      product answers with marketing copy ("proprietary algorithm",
      "decades of research"). The actual formula is rarely published.</p>

      <ul>
        <li><strong>Finviz</strong>: no composite score. Filters only.
        N/A.</li>
        <li><strong>Stock Rover</strong>: "Score" and "Growth Score"
        published as relative-to-universe percentile rankings; weights
        not disclosed.</li>
        <li><strong>Zacks</strong>: The Zacks Rank methodology is
        published at high level (earnings ESP + earnings surprise +
        broker rating changes) but the exact weights are proprietary.</li>
        <li><strong>Tapeline</strong>: Full formula at
        <a href="/how-it-works">/how-it-works</a> with exact weights
        (Trend 25% / RS 20% / Fundamentals 15% / Smart Money 15% /
        Macro 15% / Momentum 10%). Weight changes are announced in the
        changelog before they ship.</li>
      </ul>

      <h3>4. Does it beat SPY?</h3>

      <p>This is the question that should drive the buy decision and
      the one nobody answers honestly. The reason: most product owners
      don't actually track it. The "back-tested results" in marketing
      materials are usually one-time historical simulations, not live
      forward-tracked records.</p>

      <p>Of the four, Tapeline is the only one that publishes a
      permanent, append-only daily log of every top-10 pick with
      next-day return vs SPY at
      <a href="/scorecard">tapeline.io/scorecard</a>. The losers stay
      on the page. The hit rate, median alpha, and best/worst days
      update automatically.</p>

      <p>Stock Rover and Zacks both publish historical performance for
      their internal ranks (Stock Rover's Premier list, Zacks #1
      Strong Buy), but those use proprietary universe-construction
      rules that aren't easy to verify externally. Finviz doesn't
      claim a stock-picking record at all — it's a tool, not a
      signal.</p>

      <h2>When to pick which</h2>

      <ul>
        <li><strong>Pick Finviz Elite</strong> if you have a specific
        thesis to express as a filter and want raw breadth (the most
        screens, the most filters).</li>
        <li><strong>Pick Stock Rover Essentials</strong> if you're a
        long-only quality investor with portfolio analytics needs and
        don't trade intraday.</li>
        <li><strong>Pick Zacks Premium</strong> if you trade earnings
        events and want the deepest analyst-rating + earnings-surprise
        data set.</li>
        <li><strong>Pick Tapeline Pro</strong> if you want one
        synthesised read on every US ticker, a transparent formula
        you can argue with, and a live track record you can audit
        before you trust it.</li>
      </ul>

      <h2>The honest pitch for Tapeline</h2>

      <p>I'm not going to tell you Tapeline replaces Finviz's filter
      breadth, because it doesn't. I'm not going to tell you it has
      Stock Rover's portfolio analytics, because it doesn't. What it
      does have is one read per ticker from a formula you can argue
      with line-by-line, and a public daily record of whether that
      formula's top-10 picks actually beat SPY.</p>

      <p>If that's the criterion that should drive the buy decision —
      and we'd argue it should — then the
      <a href="/scorecard">scorecard</a> is the test. Read it. If the
      numbers don't hold up, we're not the right product for you. If
      they do, the
      <a href="/signup?utm_source=blog&utm_medium=post&utm_campaign=best_scanner_under_30">14-day
      Premium trial</a> is the no-card way to see it from the inside.</p>
    `,
  },
  {
    slug: "how-to-read-sec-form-4",
    title: "How to read SEC Form 4 insider buying (and what's actually a signal).",
    excerpt:
      "SEC Form 4 — the filing every corporate insider must submit within 2 business days of a trade — is the rawest 'smart money' signal retail traders can access. But 90% of Form 4 activity is noise. Here's how to filter for the 10% that matters, and how Tapeline's Smart Money sub-score does it automatically.",
    publishedAt: "2026-05-20",
    author: "Tapeline",
    body: `
      <p>If you've ever read a finance Twitter thread that ends with
      "the insider just bought 50,000 shares" and felt vaguely
      compelled to investigate further, you've encountered SEC Form 4.
      It's the filing every corporate insider — directors, officers,
      anyone with 10%+ ownership — must submit to the SEC within 2
      business days of any trade in the company's stock. It's been
      mandatory since 1934. The signal is real. The noise around it is
      what kills retail traders.</p>

      <p>This post is the field guide: what Form 4 actually contains,
      which 90% of filings to ignore, and what the remaining 10%
      reliably predicts. Tapeline's Smart Money sub-score (15% of the
      composite — <a href="/how-it-works">see the formula</a>) does
      this filtering automatically, but the underlying logic is worth
      understanding regardless of what tool you use.</p>

      <h2>What Form 4 actually is</h2>

      <p>A Form 4 filing has six things you care about:</p>

      <ol>
        <li><strong>The insider's name and role</strong> — CEO, CFO,
        director, 10%+ owner. Role matters; we'll get to why.</li>
        <li><strong>Transaction code</strong> — a one-letter code from
        a fixed table. The ones that matter for "is this a signal":
        <code>P</code> (open-market purchase), <code>S</code>
        (open-market sale), <code>A</code> (grant — almost never
        meaningful), <code>F</code> (tax-withholding sale — almost
        never meaningful).</li>
        <li><strong>Number of shares</strong> — raw count, not dollar
        amount. You compute the $ from price.</li>
        <li><strong>Price per share</strong> — the executed price.</li>
        <li><strong>Date of trade</strong> — not the filing date. The
        filing window is 2 business days, so the trade is up to 48
        hours older than the filing.</li>
        <li><strong>Shares held after transaction</strong> — total
        post-trade. This is the field most retail traders ignore and
        the one that determines whether the trade is a signal or
        noise.</li>
      </ol>

      <h2>The 90% that's noise — what to ignore</h2>

      <h3>1. Anything that isn't transaction code P or S</h3>

      <p>Form 4 has 30+ transaction codes. Most of them — grants,
      vestings, exercises, gifts, withholdings — are not voluntary
      market activity. An insider getting shares via an automatic
      restricted-stock vesting tells you nothing about their view of
      the company's valuation. They didn't choose to acquire the
      shares; the comp plan did. Filter to code P (open-market buy)
      and code S (open-market sale) only. Everything else is HR
      paperwork dressed as a filing.</p>

      <h3>2. 10b5-1 sales</h3>

      <p>10b5-1 plans are pre-arranged trading schedules executives
      use to sell stock systematically without being accused of
      insider trading. A CFO who set up a 10b5-1 plan in March 2025
      that triggers a sale of 10,000 shares every quarter is selling
      mechanically — it's not their reaction to current information.
      These show up as code S sales but are explicitly marked
      "pursuant to 10b5-1 plan" in footnotes. Filter them out;
      they're noise.</p>

      <h3>3. Tiny purchases relative to ownership</h3>

      <p>A board member who already owns 500,000 shares buying 100
      more is not a signal. They're rounding error in their own
      portfolio. The relevant ratio is <em>shares purchased ÷ shares
      held after</em>. Anything under 1-2% is meaningless.</p>

      <h3>4. Director purchases at companies with mandatory
      share-ownership requirements</h3>

      <p>Many large companies require directors to own at least N×
      their annual cash retainer in stock. When a newly-appointed
      director makes a small open-market purchase, they're often just
      complying with the requirement — not expressing a view on
      valuation. The clue: it's their first purchase, it's small, and
      it happens within 90 days of board appointment.</p>

      <h2>The 10% that matters — what's actually a signal</h2>

      <h3>1. Cluster buying</h3>

      <p>The single highest-information Form 4 pattern. Multiple
      different insiders — usually CEO + CFO + at least one director
      — all making open-market purchases (code P) within a tight
      time window (say 30 days), at meaningful sizes (1%+ of their
      existing holdings each). This is hard to fake and hard to
      explain via comp-plan mechanics. When you see it, the people
      closest to the company's actual numbers have collectively
      decided the stock is mispriced low.</p>

      <h3>2. CEO purchases at a meaningful percentage of net worth</h3>

      <p>If the CEO buys $1M of stock and their compensation suggests
      a net worth in the $50M range, that's 2% of their net worth in
      one position. That's a real bet. Cross-check via the proxy
      statement (DEF 14A) for total compensation history.</p>

      <h3>3. CFO buying when others are selling</h3>

      <p>The CFO has the cleanest, earliest view of the company's
      actual financials — quarterly closing, working-capital trends,
      cash-flow forecast. When a CFO buys against a sector tape that
      has other peers selling, it's an unusually strong dissenting
      signal.</p>

      <h3>4. First-time purchases at companies that haven't seen
      insider buying for 12+ months</h3>

      <p>Companies in steady-state mode often see zero insider
      open-market activity for stretches. When that dry spell breaks
      with a meaningful purchase, something has changed in management's
      view. Pull the most-recent 4-5 Form 4s and check the gap.</p>

      <h2>How Tapeline scores this automatically</h2>

      <p>Tapeline's Smart Money sub-score — 15% of the
      <a href="/how-it-works">composite formula</a> — looks at the
      90-day rolling net Form 4 transaction count and dollar volume,
      filtered to:</p>

      <ul>
        <li>Transaction codes P and S only (excludes grants,
        vestings, withholdings).</li>
        <li>Excludes 10b5-1 marked sales.</li>
        <li>Weights by insider role (CEO and CFO buys count more than
        director buys).</li>
        <li>Weights by transaction size relative to insider's existing
        position.</li>
        <li>Bonuses for cluster signals (3+ different insiders, same
        direction, 30-day window).</li>
      </ul>

      <p>The result is a 0-100 sub-score that lands in the composite.
      Recent insider buys are also displayed on Tapeline Premium at
      <a href="/app/holdings">/app/holdings</a> — raw filtered Form 4
      data per ticker, sorted by date, with the same noise filters
      applied. Read alongside the composite score, not in place of it.</p>

      <h2>Where the signal breaks down</h2>

      <p>Three honest caveats:</p>

      <ul>
        <li><strong>2-day filing lag</strong>. By the time you see the
        Form 4, the insider's trade is up to 48 hours old. The market
        often already moved.</li>
        <li><strong>Selling is less informative than buying</strong>.
        Insiders sell for personal reasons (diversification, house
        purchase, divorce) that aren't tied to their view of the
        company. Buying is almost always a directional view; selling
        is mixed.</li>
        <li><strong>Small-cap signal-to-noise is worse than
        large-cap</strong>. Microcap insiders trade more frequently
        for personal-liquidity reasons. The cluster filter helps but
        doesn't eliminate the noise.</li>
      </ul>

      <h2>The pitch</h2>

      <p>Form 4 is one of the few real edges retail traders have
      access to — the raw data is public, the filing is mandatory,
      and most retail traders don't read it. The hard part isn't
      access; it's filtering. Tapeline Premium does the filtering
      and surfaces it as both (1) a sub-score in the composite and
      (2) raw filtered transactions at /app/holdings.</p>

      <p><a href="/signup?utm_source=blog&utm_medium=post&utm_campaign=form_4_insider_buying">14-day
      Premium trial — no card</a>. Read 90 days of filtered Form 4
      activity across the full universe. Cancel in one click.</p>
    `,
  },
  {
    slug: "how-to-evaluate-a-stock-scanner-track-record",
    title: "How to evaluate a stock scanner you can actually trust (5 criteria most fail).",
    excerpt:
      "Every stock scanner claims to beat the market. Almost none publish a daily, append-only, back-checked track record you can audit. Here are the five tests we'd put any scanner through before paying — and how to read between the lines when the answers get vague.",
    publishedAt: "2026-05-21",
    author: "Tapeline",
    body: `
      <p>Choosing a stock scanner is mostly an exercise in detecting
      what isn't said. Every product claims to "beat the market" or
      "outperform" or "deliver signals." Almost none publish the data
      that would let you verify those claims. The asymmetry is the
      whole story: the products with real records publish them
      prominently; the products without real records hide behind
      proprietary algorithms and selected case studies.</p>

      <p>This post is the buyer's checklist — five tests we'd put any
      scanner through, with the questions to ask and what each answer
      tells you. Tapeline is one of the products you might evaluate
      with these criteria; we score ourselves at the end so you can
      compare us against the same yardstick we'd apply to a
      competitor.</p>

      <h2>Test 1: Can you see every pick, including the losers?</h2>

      <p>This is the single most important test and the one most
      products fail. "Picks of the day" or "today's recommendations"
      are easy to publish; what's hard is publishing every pick that
      was wrong, with the same prominence, on the same page, with the
      original score and signal still attached.</p>

      <p>The right answer looks like: <em>"Yes, every top-10 daily
      pick we've ever published is logged at this URL, sorted by
      date, with the next-day return and the original score visible.
      The page is append-only — we can't go back and edit it. You can
      see every win and every miss."</em></p>

      <p>The wrong answer looks like: <em>"Our algorithm has a 67%
      win rate based on internal testing"</em> with no link to the
      raw record. That's a marketing claim, not a verifiable
      statement.</p>

      <p>Test it: ask for the URL of the daily picks log. If they
      hesitate, you have your answer.</p>

      <h2>Test 2: Is the benchmark named?</h2>

      <p>"Outperforms the market" is a meaningless claim without a
      named benchmark. Outperforms which market? The S&amp;P 500?
      Russell 2000? Equal-weighted universe? Sector ETF? The choice
      of benchmark changes the answer by 5-10 percentage points
      annually.</p>

      <p>Real answer: <em>"Picks are back-checked against SPY (S&amp;P
      500 ETF) on a same-day, next-trading-day basis. Alpha is the
      pick's 1-day return minus SPY's same-day return."</em></p>

      <p>Vague answer: <em>"Outperforms the broader market"</em> with
      no specific index named.</p>

      <p>Tapeline's choice: SPY same-day-pick to next-trading-day-close
      vs SPY same window. Documented at
      <a href="/scorecard">/scorecard</a>.</p>

      <h2>Test 3: Is the scoring methodology published?</h2>

      <p>This is the test most products fail through omission rather
      than misdirection. They simply don't disclose the formula at
      all. "Proprietary algorithm developed over X years" is the
      standard formulation.</p>

      <p>The right answer publishes the inputs, the weights, and any
      transformations explicitly. Tapeline's example:
      Trend 25% / Relative Strength 20% / Fundamentals 15% / Smart
      Money 15% / Macro 15% / Momentum 10%, summed to a 0-100
      composite. Each sub-score's input data sources and computation
      steps are documented at <a href="/how-it-works">/how-it-works</a>.</p>

      <p>What this enables: if the product underperforms in a
      particular regime, you can look at the score breakdown and see
      <em>which factor is dragging</em>. You can disagree with the
      weights and reason about that disagreement. With a black box,
      you can't do any of that — you can only stop using it.</p>

      <h2>Test 4: How fresh is the data?</h2>

      <p>"Real-time" means different things at different price tiers.
      On a free tier, "real-time" often means 15-minute delayed,
      because that's the IEX exchange delay limit on free
      consolidated feeds. On a paid tier, "real-time" usually means
      direct exchange data with sub-second latency.</p>

      <p>Test it by checking the timestamp on a single quote. If
      it's behind the broker quote you'd see at your trading
      platform, you have your answer.</p>

      <p>For composite scanners (like Tapeline), the question is
      slightly different: how often does the SCORE refresh, not just
      the underlying price? Tapeline's worker ticks every 60 seconds
      during market hours, recomputing the composite from fresh
      snapshot data. Free tier is 24-hour-delayed (intentional
      gating); Pro is 60-second freshness.</p>

      <h2>Test 5: What's the unsubscribe / cancel friction?</h2>

      <p>This is the dirtiest test, but the most diagnostic. Products
      that are confident in their value make it trivial to leave.
      Products that depend on dark-pattern retention make it hard.</p>

      <p>Check before you sign up:</p>

      <ul>
        <li>Can you cancel from a settings page in one click, or do
        you need to email support and wait?</li>
        <li>Is the trial auto-converting? Do you have to add a credit
        card?</li>
        <li>What's the refund window?</li>
      </ul>

      <p>Tapeline's policy: trial doesn't require a card, cancel from
      /app/billing in one click, 7-day refund window on monthly
      subscriptions. We'd rather lose subscribers cleanly than retain
      them via friction.</p>

      <h2>How Tapeline scores against the checklist</h2>

      <table>
        <thead>
          <tr><th>Test</th><th>Tapeline</th></tr>
        </thead>
        <tbody>
          <tr><td>Public daily picks log with losers visible</td>
              <td>Yes — <a href="/scorecard">/scorecard</a></td></tr>
          <tr><td>Named benchmark</td><td>SPY, same-day-pick to next-trading-day-close</td></tr>
          <tr><td>Public scoring formula with weights</td>
              <td>Yes — <a href="/how-it-works">/how-it-works</a> with exact weights</td></tr>
          <tr><td>Data freshness</td>
              <td>60s composite refresh on Pro+; 24h delayed on Free (intentional)</td></tr>
          <tr><td>Cancel friction</td>
              <td>One-click cancel, 7-day refund, no card required for trial</td></tr>
        </tbody>
      </table>

      <h2>What this checklist does NOT test</h2>

      <p>To be honest: none of these criteria tell you whether the
      product will work for YOUR specific trading style. You might
      need filter breadth Tapeline doesn't have. You might need
      international coverage we don't offer (US-only for now). You
      might prefer the analyst-rating focus Zacks does better than
      anyone. The checklist tells you whether the product is
      <em>honest about what it does</em>, not whether what it does
      matches your needs.</p>

      <p>The two questions you need to answer separately:</p>

      <ol>
        <li>Does this product publish enough evidence for me to
        verify their claims? (Checklist above.)</li>
        <li>Does the thing they're publishing evidence FOR match what
        I actually want to do? (Read the product page + try the free
        tier + read the scorecard.)</li>
      </ol>

      <p>Tapeline's pitch: we'd rather lose your business to a
      product that fits you better than win it via misleading
      claims. If the scorecard convinces you, the
      <a href="/signup?utm_source=blog&utm_medium=post&utm_campaign=evaluate_scanner">14-day
      Premium trial</a> is the no-card way to see the rest. If it
      doesn't, that's useful information too.</p>
    `,
  },
];

export function findPost(slug: string): BlogPost | null {
  return POSTS.find((p) => p.slug === slug) ?? null;
}
