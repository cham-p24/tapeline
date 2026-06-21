/**
 * DRAFT — disclosure launch post.
 *
 * Slug: 100-picks-in-public
 * Trigger condition: n=100 scored + back-checked picks recorded on /scorecard.
 * Coordinated with the founder-disclosure env flip:
 *   NEXT_PUBLIC_FOUNDER_DISCLOSED=true
 *   NEXT_PUBLIC_FOUNDER_NAME="Your Real Name"
 *   NEXT_PUBLIC_FOUNDER_LINKEDIN="https://www.linkedin.com/in/your-slug"
 *   NEXT_PUBLIC_FOUNDER_X="https://x.com/your-handle"
 *   NEXT_PUBLIC_FOUNDER_HEADSHOT_URL="https://tapeline.io/founder.jpg"
 *
 * This file is in `app/blog/_drafts/` so the underscore prefix keeps Next.js
 * App Router from making it a route. It is NOT imported by `app/blog/posts.ts`.
 *
 * To publish:
 *   1. Fill in every {{ }} placeholder below with the real numbers from the
 *      first 100 logged picks. Don't ship the post until every placeholder
 *      is gone — half-filled is worse than not posting.
 *   2. Update `publishedAt` to the actual launch date.
 *   3. Import this constant in `app/blog/posts.ts` and prepend it to POSTS:
 *        import { POST_100_PICKS_IN_PUBLIC } from "./_drafts/100-picks-in-public.draft";
 *        export const POSTS: BlogPost[] = [POST_100_PICKS_IN_PUBLIC, ...rest];
 *   4. Flip the four NEXT_PUBLIC_FOUNDER_* env vars in Vercel.
 *   5. Trigger redeploy. Verify with the schema-validator commands in the
 *      seo-tools README.
 */
import type { BlogPost } from "../posts";

export const POST_100_PICKS_IN_PUBLIC: BlogPost = {
  slug: "100-picks-in-public",
  title: "100 picks in public: the scorecard so far, and who's been running it.",
  excerpt:
    "Tapeline has logged its 100th top-10 daily pick. Here's the full track record vs SPY, the biggest miss, the biggest win, what we learned, and — finally — who's been running it.",
  publishedAt: "{{LAUNCH_DATE_ISO_e.g._2026-09-15}}",
  author: "{{FOUNDER_NAME}}",
  body: `
    <p>When Tapeline launched, the only thing it could honestly say about its
    own performance was: "the formula is public, the scorecard is public, come
    back when there are receipts." That sentence was useful exactly once.</p>

    <p>This is the receipt. As of {{LAUNCH_DATE_HUMAN}}, the public scorecard
    holds <strong>100 top-10 daily picks</strong> — every one logged at session
    close with the original score, signal label, and reasoning intact, and
    back-checked against SPY's move the following session. Nothing has been
    edited, deleted, or "re-scored with the benefit of hindsight." The raw
    data lives at <a href="/scorecard">/scorecard</a> and will continue to
    live there as long as Tapeline does.</p>

    <h2>The headline numbers</h2>
    <ul>
      <li><strong>{{TOTAL_PICKS}} top-10 daily picks</strong> logged
      ({{TRADING_DAYS}} trading days × top 10 per day, minus any market-closed
      sessions).</li>
      <li><strong>Average 1-day return: {{AVG_1D_RETURN}}%</strong></li>
      <li><strong>Average alpha vs SPY: {{AVG_ALPHA}}%</strong></li>
      <li><strong>Hit rate (beat SPY next session): {{HIT_RATE}}%</strong></li>
      <li>Best single day for an individual pick:
      <strong>{{BEST_PICK_TICKER}} +{{BEST_PICK_RETURN}}%</strong> on
      {{BEST_PICK_DATE}}.</li>
      <li>Worst single day for an individual pick:
      <strong>{{WORST_PICK_TICKER}} {{WORST_PICK_RETURN}}%</strong> on
      {{WORST_PICK_DATE}}.</li>
    </ul>

    <p>If you're new here: each evening Tapeline auto-publishes the day's
    top-10 highest-scoring tickers from a universe of ~2,500 active US
    names. The 6-factor formula and its weights are public on
    <a href="/how-it-works">/how-it-works</a>; the next day, the scorecard
    records where each name actually closed and computes the alpha vs SPY.
    No hindsight edits, no cherry-picking.</p>

    <h2>What surprised me</h2>
    <p>{{SURPRISE_PARAGRAPH — e.g. "Three things I didn't expect from the first
    100 picks: (1) the macro factor matters more during transitions than during
    steady regimes; (2) CONSTRUCTIVE picks have a tighter alpha distribution
    than HIGH CONVICTION; (3) Tuesdays and Wednesdays show meaningfully
    different hit rates than Mondays and Fridays."}}</p>

    <h2>The biggest miss</h2>
    <p>{{BIGGEST_MISS_PARAGRAPH — a single trade in detail. What the score
    was, what signal it had, what the reasoning said, what actually happened
    the next session, what (if anything) it suggests about the model.}}</p>

    <h2>The biggest win</h2>
    <p>{{BIGGEST_WIN_PARAGRAPH — same shape. Important: this is not a victory
    lap. It's framed honestly — "the model surfaced this name, this is why,
    this is what happened.")}}</p>

    <h2>What the data is NOT saying</h2>
    <p>One hundred picks is fewer than five months of trading days. It is
    enough to argue against random; it is not enough to argue that the model
    is robust across regimes. Three caveats matter:</p>
    <ul>
      <li><strong>Single-day horizon.</strong> The scorecard measures 1-day
      alpha. Most of what Tapeline does well lives on a multi-day to
      multi-week horizon; the daily back-check is honest but it understates
      the signal.</li>
      <li><strong>Single regime.</strong> {{REGIME_DESCRIPTION — e.g. "These
      100 picks span a single market regime — broadly trending up with VIX
      mostly under 20. The model has not yet been tested in a 2022-style
      rate-shock or a sustained correction."}}</li>
      <li><strong>Survivorship.</strong> The universe is the top ~2,500 by
      daily dollar-volume. Names that fell out of liquidity mid-period got
      dropped from new picks but their already-logged picks remain in the
      record — see the scorecard for the full list.</li>
    </ul>

    <h2>Who's been running it</h2>
    <p>I should probably introduce myself.</p>

    <p>I'm <strong>{{FOUNDER_NAME}}</strong>, the solo founder and engineer
    behind Tapeline. I've been writing software for {{YEARS_ENGINEERING}}+
    years and actively trading my own portfolio for {{YEARS_TRADING}}+. The
    scoring engine that powers Tapeline ran for ~12 months as my personal
    trading bot before becoming a product — paper-traded via Alpaca, fed by
    Massive (the rebranded Polygon.io), Finnhub, Quiver, and FRED. The same
    formula. The same factor weights. The same scorecard discipline.</p>

    <p>You can find me at:</p>
    <ul>
      <li>LinkedIn: <a href="{{FOUNDER_LINKEDIN}}" rel="me">{{FOUNDER_LINKEDIN_DISPLAY}}</a></li>
      <li>X: <a href="{{FOUNDER_X}}" rel="me">{{FOUNDER_X_DISPLAY}}</a></li>
      <li>GitHub: <a href="https://github.com/cham-p24" rel="me">cham-p24</a></li>
      <li>Email: <a href="mailto:press@tapeline.io">press@tapeline.io</a></li>
    </ul>

    <p>Why disclose now and not at launch? Because at launch the only honest
    thing I could put in a bio was "trust me." A hundred picks later, the
    receipts speak for themselves, and the bio is just the human attached
    to them.</p>

    <h2>What's next</h2>
    <p>The scorecard keeps running. The formula doesn't change without a
    <a href="/changelog">changelog</a> entry. The plan from here:</p>
    <ul>
      <li>{{NEXT_1 — e.g. "Quarterly recap posts at n=200, n=300, with
      factor-importance attribution from the actual scorecard data."}}</li>
      <li>{{NEXT_2 — e.g. "Open-sourcing the back-check methodology as a
      reproducible notebook so anyone can audit how the alpha is computed."}}</li>
      <li>{{NEXT_3 — e.g. "Expanding programmatic surfaces — per-sector
      scorecards, per-signal-label scorecards."}}</li>
    </ul>

    <p>If you want to be there for the next 100 picks before the receipts
    look this good in public, the 14-day Premium trial is at
    <a href="/signup">/signup</a> — no credit card. The free tier (live scores
    for the top 10 scanner rows, 5 look-ups a day) is forever, and the full
    scorecard is and always will be at <a href="/scorecard">/scorecard</a>.</p>

    <p>Thanks for reading. See you on the next pick.</p>

    <p><em>— {{FOUNDER_FIRST_NAME}}</em></p>
  `,
};
