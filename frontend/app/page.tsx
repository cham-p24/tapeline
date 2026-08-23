import Link from "next/link";
import { ScannerPreview } from "@/components/ScannerPreview";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { LiveCounters } from "@/components/LiveCounters";
import { FadeIn } from "@/components/FadeIn";
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { ExitIntentModal } from "@/components/ExitIntentModal";
import { POSTS } from "./blog/posts";
import { REFUND } from "@/lib/pricing";
import { formatTrackedSince, type CitableSummary } from "@/lib/scorecardCitation";
import { ssrInternalHeaders } from "@/lib/ssrHeaders";

// ScannerPreview server-fetches the real anonymous top-scored rows; 30-min
// ISR (same budget as /daily-picks) keeps the homepage static-fast while the
// hero table stays a truthful snapshot of today's list.
export const revalidate = 1800;

// Server-side API base — same fallback chain as app/scorecard/page.tsx.
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || process.env.API_URL || "https://api.tapeline.io";

/**
 * Fetch the tier-invariant archive summary for the usage-as-proof line.
 *
 * Same pattern as app/scorecard/page.tsx fetchSummary(): GET
 * /api/scorecard?days=1 (the summary is computed over ALL history regardless
 * of the window), 30-min ISR, 5s abort so a degraded API can't hang the static
 * build. Any failure returns null and the caller renders no proof line.
 *
 * COMPLIANCE — Rule 3: the landing/hero surface may show ONLY the raw counts
 * and the tracked-since date from this summary. The vs-SPY hit rate and the
 * median-alpha figure are deliberately NOT read here; they stay on /scorecard
 * where the sample size is disclosed alongside them.
 */
async function fetchSummary(): Promise<CitableSummary | null> {
  try {
    const res = await fetch(`${API_BASE}/api/scorecard?days=1`, {
      next: { revalidate: 1800 },
      headers: ssrInternalHeaders(),
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { summary?: CitableSummary };
    return body?.summary ?? null;
  } catch {
    return null;
  }
}

export default async function LandingPage() {
  const summary = await fetchSummary();
  const trackedSince = summary ? formatTrackedSince(summary.first_tracked_date) : null;
  return (
    // The page-wide blue atmospheric gradient now lives on `body::before`
    // in globals.css (PR #141) so EVERY route gets it consistently
    // without per-page wiring. <main> here just needs the structural
    // container styles. `overflow-x-clip` (not -hidden) prevents a horizontal
    // scrollbar WITHOUT turning <main> into a scroll container — `overflow-x:
    // hidden` does, which silently breaks the floating nav's position:sticky
    // (the header scrolls away instead of pinning). `clip` leaves overflow-y
    // visible, so the sticky nav keeps floating.
    <main id="main" className="relative min-h-screen overflow-x-clip">
      <MarketingNav />

      {/* HERO — single-purpose fold.
          Left: one sentence value prop + the record/trial CTA pair + the
          no-account browse pill.
          Right: the REAL anonymous top-scored table (ScannerPreview, server-
          fetched, 30-min ISR) with a zero-signup link to the full Top 10.
          Nothing else competes. The TickerSearch previously sat under the
          preview, doing the same job twice; removed so the eye lands on one
          demo, not two.
          Mobile top padding is half the old pt-8, and the column gap below is
          halved too: on a 375x812 phone the entire left column stacks above
          the product shot, so every pixel of hero padding pushes row one of
          the table past the fold. sm+ keeps the original composition. */}
      <section className="relative overflow-hidden px-6 pt-4 pb-10 sm:pt-20 sm:pb-16">
        {/* Decorative gradient blobs removed 2026-05-22 — too many ambient
            overlays were competing with the actual content + colliding with
            the body::before atmospheric tint, producing an unintentionally
            heavy stacked effect. Sections now use solid panel tints (below)
            for hierarchy rather than blurred colour halos. */}
        {/* Mobile-only reorder (GAP #5): the two-column grid stacks the whole
            text column above the ScannerPreview on a phone, pushing the live
            table below the fold. The hero is split into three grid children so
            Tailwind order-* can interleave them on mobile — badge+h1+value-prop
            +CTAs (order-1), the ScannerPreview column (order-2), then the trial
            fine-print (order-3) — while explicit lg:col-start/lg:row-start
            rebuild the exact desktop two-column composition and lg:order-none
            resets the source order. lg:gap-y-0 keeps the stacked left-column
            blocks on their existing margins (no extra grid row-gap) so the
            desktop layout is unchanged; lg:gap-x-10 preserves the old column
            gap. Reason about a 375px viewport: the scanner now sits directly
            under the CTAs, above the fine-print. */}
        <div className="mx-auto grid max-w-6xl gap-6 sm:gap-12 lg:grid-cols-5 lg:gap-x-10 lg:gap-y-0">
          <div className="order-1 lg:order-none lg:col-span-2 lg:col-start-1 lg:row-start-1 lg:pt-6">
            {/* Static dot on purpose — the hero table refreshes on a 30-min
                ISR cadence, so nothing here should pulse like a stream. */}
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-panel px-3 py-1 text-xs text-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-up" />
              Live market scanning
            </div>
            <h1 className="mt-6 text-4xl font-bold tracking-tight sm:text-6xl">
              Every pick on the public record.
              <br />
              <span className="text-accent">Even the ones that missed.</span>
            </h1>
            <p className="mt-6 text-lg text-muted leading-relaxed">
              Newsletters show you the winners. The{" "}
              <span className="font-medium text-fg">Tapeline Score</span> blends
              six named factors into one read on every ticker &mdash; and every
              call, win or miss, goes on a permanent public record you can check
              before you ever pay. Same day, no edits.
            </p>
            {/* ENTRY POINTS — the proof door and the product door at equal
                weight, with the no-account browse path under them.
                The proof-first repositioning is deliberate and stays: the
                public record leads. But it had left the fold with no way into
                the product at all — both pills pointed at public pages and a
                third text link went to /scorecard a SECOND time, so a visitor
                who was already convinced had nothing to click. /signup is now
                the second pill, outlined in accent rather than muted so
                neither door reads as the afterthought, and the duplicate
                scorecard link is gone. Grid (not flex-wrap) so the pills stay
                equal width on mobile instead of one stretching and the other
                shrinking.
                R6: the trial's terms are stated as fact below — no countdown,
                no deadline, no scarcity. */}
            <div className="mt-8 grid gap-3 sm:max-w-md sm:grid-cols-2">
              <Link href="/scorecard" className="btn-primary text-base">
                See the track record &rarr;
              </Link>
              <Link
                href="/signup"
                className="btn border border-accent/60 text-base text-accent transition-colors hover:bg-accent/10"
              >
                Start the Premium trial
              </Link>
              <Link
                href="/daily-picks"
                className="btn border border-border bg-panel text-base text-fg transition-colors hover:border-accent/50 hover:bg-panel/70 sm:col-span-2"
              >
                Browse without an account
              </Link>
            </div>
            {/* GAP #6: a subtle tertiary text link into /signup, added ABOVE
                the fold alongside the two proof-first pills. It does not remove
                or demote either existing CTA (both stay full pills, test-locked
                in LandingPage.test.tsx) — it just gives an already-convinced
                visitor a low-friction door into the trial. */}
            <p className="mt-3 text-sm">
              <Link
                href="/signup"
                className="text-accent underline-offset-2 hover:underline"
              >
                Start the 14-day trial
              </Link>
            </p>
          </div>

          {/* Block C — the ScannerPreview column. Mobile order-2 so the live
              table sits directly under the CTAs, above the fine-print. */}
          <div className="order-2 lg:order-none lg:col-span-3 lg:col-start-3 lg:row-start-1 lg:row-span-2">
            <ScannerPreview />
            {/* Fold-visible zero-signup path: the table above shows the top
                slice; /daily-picks has the full Top 10, no account needed. */}
            <p className="mt-3 text-center text-xs text-muted">
              <Link
                href="/daily-picks"
                className="text-accent underline-offset-2 hover:underline"
              >
                See today&rsquo;s full Top 10 &mdash; no signup &rarr;
              </Link>
            </p>
            {/* The differentiator, stated directly under the thing that
                evidences it: the artefact itself — today's list and the whole
                logged history, losses included — is readable before anyone
                signs up, which is the one thing the paid rivals don't do.
                Descriptive statement of what is published: no returns claim,
                and no usage figure is asserted because this page carries no
                server-side count to source a real one from. */}
            <p className="mx-auto mt-2 max-w-md text-center text-sm leading-snug text-fg">
              Today&rsquo;s picks and the entire logged history, losses
              included, are readable before you sign up.
            </p>
            {/* GAP #22: one openness line vs the paid rivals. Landing copy
                only — a factual statement of what Tapeline exposes for free.
                (The per-rival free-access claim is verified on the /compare
                pages, not asserted here — see deviations follow-up.) */}
            <p className="mx-auto mt-2 max-w-md text-center text-sm leading-snug text-muted">
              All 10 of today&rsquo;s top picks &mdash; free, no login. Most
              scanners keep their picks behind a paywall.
            </p>
          </div>

          {/* Block B — the trial fine-print. Mobile order-3 so it trails the
              live table; lg:row-start-2 tucks it directly under Block A in the
              left column on desktop (lg:gap-y-0 keeps its mt-3 the only gap, so
              the desktop layout is unchanged). */}
          <p className="order-3 mt-3 text-xs leading-relaxed text-muted lg:order-none lg:col-span-2 lg:col-start-1 lg:row-start-2">
            The trial is 14 days of Premium. Your card goes on at first sign-in
            and nothing is charged that day &mdash; the first charge is on day 14 at
            the plan you pick, we email you three days before, and one click cancels
            before then. The scorecard and daily Top 10 stay free to read with no
            account either way.
          </p>
        </div>
      </section>

      {/* LIVE COUNTERS — concrete numbers from /api/status, refreshed every 60s.
          Replaces vague "live" with specifics: how many tickers, how many
          news items, current regime, last tick. */}
      <section>
        <div className="mx-auto max-w-6xl px-6 py-8">
          <LiveCounters />
          {/* GAP #20: usage-as-proof, sourced LIVE from the scorecard summary
              (server fetch above, 30-min ISR). Renders nothing when the fetch
              failed or the archive is empty.
              COMPLIANCE — Rule 3: ONLY the raw counts and the tracked-since
              date appear here. The vs-SPY hit rate and median-alpha are NOT
              surfaced on the landing/hero — they live on /scorecard with the
              sample size disclosed. */}
          {summary && (
            <p className="mt-4 text-center text-sm text-muted">
              {summary.entries_scored} picks logged across{" "}
              {summary.days_tracked} market days
              {trackedSince ? `, tracked since ${trackedSince}` : ""}.
            </p>
          )}
        </div>
      </section>

      {/* WHY THIS IS DIFFERENT — three bold contrastive claims, NOT cards.
          The trust pillars used to be a 3-card grid, identical in shape to
          the "How it works" cards below — same rhythm twice. Now: typography-
          led statements with thin dividers, then cards for the process. Two
          different visual treatments for two different jobs.
          Section is `relative overflow-hidden` so we can drop in a soft
          right-side accent blob that picks up the atmosphere from the hero. */}
      <section>
        <div className="mx-auto max-w-6xl px-6 py-8 sm:py-12">
        <p className="eyebrow text-accent">Why Tapeline</p>
        <h2 className="mt-3 max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
          Three things every other scanner won&rsquo;t do.
        </h2>

        <div className="mt-12 grid gap-10 md:grid-cols-3 md:gap-12">
          <FadeIn delayMs={0}>
            <Differentiator
              num="01"
              label="Public method, not a black box"
              body={
                <>
                  The six factors and how they&rsquo;re ordered &mdash; weighted
                  most toward Trend and Relative Strength, least toward Momentum
                  &mdash; are public and fixed. No hidden inputs, no mystery AI,
                  and every change is{" "}
                  <Link href="/changelog" className="link">
                    announced before it ships
                  </Link>
                  .
                </>
              }
            />
          </FadeIn>
          <FadeIn delayMs={80}>
            <Differentiator
              num="02"
              label="Back-checked vs SPY"
              body={
                <>
                  Top-10 picks logged at close. Next-day return + alpha vs SPY
                  recorded automatically. The losers stay on the page.{" "}
                  <Link href="/scorecard" className="link">
                    Audit any day
                  </Link>
                  .
                </>
              }
            />
          </FadeIn>
          <FadeIn delayMs={160}>
            <Differentiator
              num="03"
              label="Descriptive, not prescriptive"
              body={
                <>
                  Tapeline never tells you to buy, sell, or hold. Scores describe
                  what the tape is doing &mdash; the decision is yours.{" "}
                  <Link href="/how-it-works" className="link">
                    Read the methodology
                  </Link>
                  .
                </>
              }
            />
          </FadeIn>
        </div>
        </div>
      </section>

      {/* HOW IT WORKS — three-step process. Borderless numbered steps (the
          accent badge keeps them distinct from the mono-numeral Differentiators
          above) on a subtle full-width panel band, rather than three floating
          card panels — seamless, not boxed. */}
      <section className="bg-panel/10">
        <div className="mx-auto max-w-6xl px-6 py-8 sm:py-12">
          <p className="eyebrow text-accent">How it works</p>
          <h2 className="mt-3 max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
            From data to decision in one glance.
          </h2>

          <div className="mt-12 grid gap-10 md:grid-cols-3 md:gap-12">
            <FadeIn delayMs={0}>
              <Step n="1" title="Six named factors">
                Trend &middot; relative strength &middot; fundamentals &middot;
                smart money &middot; macro &middot; momentum &mdash; weighted most
                toward trend and relative strength, least toward momentum. Same
                weighting every tick.
              </Step>
            </FadeIn>
            <FadeIn delayMs={80}>
              <Step n="2" title="One sentence per ticker">
                Plain-English &ldquo;Why&rdquo; on every row &mdash; no chat
                session required, no premium gate. Hover the score for the
                factor breakdown.
              </Step>
            </FadeIn>
            <FadeIn delayMs={160}>
              <Step n="3" title="Every call on the record">
                Top-10 picks logged daily with the original reasoning
                preserved. Performance vs SPY recorded next session. No
                cherry-picking, no hindsight edits.
              </Step>
            </FadeIn>
          </div>
        </div>
      </section>

      {/* FROM THE BLOG — surfaces every methodology + transparency post
          from the homepage. Two jobs:
          (1) Visitor: deeper reads for the curious before they sign up.
          (2) Google crawler: internal-link path from the highest-PageRank
              page on the site (homepage) to every blog post. Without this
              widget the blog posts were stranded in "Discovered - currently
              not indexed" because no high-authority page linked to them
              and Google's crawl budget for a new domain never reached
              /blog → individual post. Posts are sorted newest-first; show
              the most recent 6 inline + "see all" link to /blog. */}
      <section className="bg-panel/10">
        <div className="mx-auto max-w-6xl px-6 py-8 sm:py-12">
          <p className="eyebrow text-accent">From the blog</p>
          <h2 className="mt-3 max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
            How the score works, on the record.
          </h2>
          <p className="mt-4 max-w-2xl text-muted">
            Methodology notes, design choices, and accountability writeups.
            Every post is anchored to public data — no opinion-only takes.
          </p>
          {/* Mobile: cap at 3 cards (≈600px) instead of 6 cards stacked
              vertically (≈1200px) so the page scroll doesn't bloat. Posts
              4-6 reappear at sm+ where they fit in a 2-col grid without
              adding scroll length. The "see all posts" link below still
              gives mobile users a path to the full blog index. */}
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3 [&>*:nth-child(n+4)]:hidden sm:[&>*:nth-child(n+4)]:block">
            {POSTS.slice(0, 6).map((p) => (
              <FadeIn key={p.slug} delayMs={0}>
                <Link
                  href={`/blog/${p.slug}`}
                  className="lift block h-full rounded-2xl bg-panel/40 p-6 hover:bg-panel/70"
                >
                  <p className="text-xs font-mono text-subtle">
                    {new Date(p.publishedAt).toLocaleDateString("en-GB", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </p>
                  <h3 className="mt-3 text-lg font-semibold tracking-tight leading-snug">
                    {p.title}
                  </h3>
                  <p className="mt-3 text-sm text-muted leading-relaxed line-clamp-4">
                    {p.excerpt}
                  </p>
                </Link>
              </FadeIn>
            ))}
          </div>
          <div className="mt-10">
            <Link href="/blog" className="link text-sm">
              See all {POSTS.length}{" "}posts &rarr;
            </Link>
          </div>
        </div>
      </section>

      {/* OBJECTION HANDLING / FAQ — five short answers to the questions every
          first-time visitor asks before they sign up. Conversion best
          practice: anticipate the doubt that's actually killing the signup
          and answer it before they need to ask.
          Wrapped in a relative-positioned container so we can drop a soft
          accent blob behind the FAQ for visual continuity with the rest of
          the page. */}
      <section>
        <div className="mx-auto max-w-3xl px-6 py-8 sm:py-12">
        <p className="eyebrow text-accent">Common questions</p>
        <h2 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
          Things people ask before signing up.
        </h2>
        <div className="mt-10 divide-y divide-border/60">
          <Faq q="Is this financial advice?">
            No. Tapeline publishes a quantitative score derived from public
            market data. Scores describe what the data is doing &mdash; they
            never tell you to buy, sell, or hold. See the{" "}
            <Link href="/legal/risk" className="link">
              risk disclosure
            </Link>
            .
          </Faq>
          <Faq q="How is this different from Finviz / Zacks / TradingView?">
            Other scanners give you 500 filters and a blank stare. Tapeline
            gives you one number, one sentence, and a public track record.
            Side-by-side comparisons:{" "}
            <Link href="/compare/finviz" className="link">
              vs Finviz
            </Link>
            ,{" "}
            <Link href="/compare/tradingview" className="link">
              vs TradingView
            </Link>
            ,{" "}
            <Link href="/compare/zacks" className="link">
              vs Zacks
            </Link>
            .
          </Faq>
          <Faq q="Is the scorecard really real?">
            Yes. Top-10 picks log automatically at market close every day; the
            next session records the actual price move + alpha vs SPY. We
            don&rsquo;t edit losers. The whole record is on{" "}
            <Link href="/scorecard" className="link">
              /scorecard
            </Link>{" "}
            for everyone &mdash; you don&rsquo;t even need an account.
          </Faq>
          <Faq q="What if I cancel?">
            Cancel anytime, one click in billing settings. Monthly plans get a
            full refund within {REFUND.windowDays}{" "}days; annual plans a
            prorated refund within {REFUND.windowDays}{" "}days. See the{" "}
            <Link href={REFUND.policyPath} className="link">
              refund policy
            </Link>
            .
          </Faq>
          <Faq q="What data do you use?">
            US equities and commodity ETFs from live market data feeds, plus
            macro indicators, fundamentals, SEC Form 4 insider filings, and a
            real-time news wire. Categories and refresh cadences listed on{" "}
            <Link href="/data-sources" className="link">
              data sources
            </Link>
            .
          </Faq>
        </div>
        </div>
      </section>

      {/* FINAL CTA — mirrors the hero promise rather than a generic
          "Stop scrolling" line. Restated specifically: one score, one
          sentence, one public record.
          No section bg — body::before gradient (globals.css) is the
          continuous canvas now; the old `from-panel/20 to-transparent`
          here created a visible seam against the FAQ above. */}
      <section>
        <div className="mx-auto max-w-3xl px-6 py-8 sm:py-10 text-center">
          <h2 className="text-4xl font-bold tracking-tight sm:text-5xl">
            One score. One sentence. <br />
            <span className="text-accent">One public record.</span>
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-muted">
            See your watchlist scored the same way we score the public
            scorecard. 14 days of Premium, $0 today.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="btn-primary text-base">
              Sign up &rarr;
            </Link>
            <Link href="/pricing" className="btn-ghost text-base">
              See pricing
            </Link>
          </div>
          <p className="mt-4 text-xs text-muted">
            $0 today &middot; Cancel in one click &middot;{" "}
            {REFUND.windowDays}-day refund on monthly
          </p>
        </div>
      </section>

      {/* Newsletter lead-magnet — second-chance email capture for visitors
          who scrolled past the trial CTAs. Lower commitment than /signup
          (no card, no account). Once they're in the list, the daily Top 10
          send + the in-email Premium CTA do the eventual conversion lift.
          Placed before the footer so it's the last thing the eye sees on
          the way out, not competing with the primary trial CTA above. */}
      <section className="bg-panel/30">
        <div className="mx-auto max-w-3xl px-6 py-8 sm:py-10">
          <div className="text-center mb-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1 text-xs text-muted">
              Free · no card
            </div>
            <h2 className="mt-4 text-2xl font-bold tracking-tight sm:text-3xl">
              Not ready for a trial?
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-muted text-sm sm:text-base leading-relaxed">
              Get the daily Top 10 picks in your inbox each market morning.
              One email, one minute, no card. Unsubscribe in one click.
            </p>
          </div>
          <div className="mx-auto max-w-md">
            <NewsletterCapture source="homepage" heading="" sub="" />
          </div>
          <p className="mx-auto mt-4 max-w-md text-center text-xs text-muted">
            Want to see today&rsquo;s picks first?{" "}
            <Link href="/daily-picks" className="text-accent hover:underline">
              Preview today&rsquo;s Top 10 →
            </Link>
          </p>
        </div>
      </section>

      <MarketingFooter />

      {/* Last-chance email capture — fires once per session when the cursor
          heads for the browser chrome. Self-gating (desktop-only, 5s grace,
          sessionStorage), renders nothing until triggered. Source tag keeps
          homepage exits distinguishable from pricing exits in
          newsletter_subscribers.source. */}
      <ExitIntentModal source="homepage" />
    </main>
  );
}

/* ----- Section helpers ----- */

function Step({
  n,
  title,
  children,
}: {
  n: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-accent/10 font-mono text-sm font-semibold text-accent">
        {n}
      </div>
      <h3 className="mt-5 text-lg font-semibold tracking-tight">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted">{children}</p>
    </div>
  );
}

function Differentiator({
  num,
  label,
  body,
}: {
  num: string;
  label: string;
  body: React.ReactNode;
}) {
  return (
    <div>
      <div className="font-mono text-xs text-subtle">{num}</div>
      <h3 className="mt-2 text-xl font-semibold tracking-tight">{label}</h3>
      <p className="mt-3 text-sm leading-relaxed text-muted">{body}</p>
    </div>
  );
}

function Faq({ q, children }: { q: string; children: React.ReactNode }) {
  return (
    <details className="group py-5">
      <summary className="flex cursor-pointer list-none items-start justify-between gap-4 text-base font-medium text-fg">
        <span>{q}</span>
        <span className="mt-1 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border border-border text-xs text-muted transition group-open:rotate-45 group-open:border-accent group-open:text-accent">
          +
        </span>
      </summary>
      <div className="mt-3 pr-9 text-sm leading-relaxed text-muted">
        {children}
      </div>
    </details>
  );
}
