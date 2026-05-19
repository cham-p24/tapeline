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
];

export function findPost(slug: string): BlogPost | null {
  return POSTS.find((p) => p.slug === slug) ?? null;
}
