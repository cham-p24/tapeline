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
      <p>"AI-powered signals" usually means "we bought a feed from Polygon
      and slapped a score on top." Which is fine — that's also our spine.
      But know it. Bloomberg Terminal at $32k/yr uses similar feeds; the
      premium is the speed and breadth of their proprietary chat and
      curated news, not the raw data. Anyone charging $200/month for
      "exclusive AI signals" is reselling Polygon and Finnhub.</p>

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
      "The Massive feed gives us 5,757 US tickers. We actively score 2,500. Here's why that cutoff exists, what we do with the rest, and why bigger isn't better.",
    publishedAt: "2026-05-03",
    author: "Tapeline",
    body: `
      <p>The data feed (Massive, formerly Polygon.io) gives us coverage of
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
      of bars. Fundamentals (Finnhub) and insider Form 4 are sparse for
      sub-$200M caps. Smart-money via Quiver tracks 8 elite funds — they
      don't hold $50M micro-caps. Forcing a score across the entire
      5,757-row universe would mean ~3,200 confidence values landing
      under 40%. That's noise, not signal — exactly the experience we're
      trying to replace.</p>

      <h2>What we do with the other 3,200</h2>
      <p>The full 5,757-row universe table is auto-populated weekly from
      Massive's reference API. We use it for: watchlist tracking (you
      can watch any ticker, scored or not), per-ticker pages with price
      and 1-day change, news feeds with sentiment tagging, and ranking —
      so when liquidity grows on a name, it gets promoted into the
      active 2,500 automatically on the next refresh cycle.</p>

      <h2>Why not just score all 5,757?</h2>
      <p>Two reasons. First, the noise above. Second, Finnhub's free tier
      is 60 calls/minute — enough for the fundamentals refresh on 2,500
      names but not 5,000+. A bigger universe means a bigger Finnhub bill,
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
