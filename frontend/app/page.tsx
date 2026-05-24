import Link from "next/link";
import { ScannerPreview } from "@/components/ScannerPreview";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { LiveCounters } from "@/components/LiveCounters";
import { FadeIn } from "@/components/FadeIn";
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { POSTS } from "./blog/posts";

export default function LandingPage() {
  return (
    // The page-wide blue atmospheric gradient now lives on `body::before`
    // in globals.css (PR #141) so EVERY route gets it consistently
    // without per-page wiring. <main> here just needs the structural
    // container styles. `overflow-x-hidden` clips any wide blob halos
    // from the hero section so they can't create a horizontal scrollbar.
    <main className="relative min-h-screen overflow-x-hidden">
      <MarketingNav />

      {/* HERO — single-purpose fold.
          Left: one sentence value prop + one primary CTA + one ghost CTA.
          Right: live mock table (ScannerPreview). Nothing else competes.
          The TickerSearch previously sat under the preview, doing the same
          job twice; removed so the eye lands on one demo, not two. */}
      <section className="relative overflow-hidden px-6 pt-8 pb-10 sm:pt-20 sm:pb-16">
        {/* Decorative gradient blobs removed 2026-05-22 — too many ambient
            overlays were competing with the actual content + colliding with
            the body::before atmospheric tint, producing an unintentionally
            heavy stacked effect. Sections now use solid panel tints (below)
            for hierarchy rather than blurred colour halos. */}
        <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-5 lg:gap-10">
          <div className="lg:col-span-2 lg:pt-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-panel px-3 py-1 text-xs text-muted">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" />
              Live market scanning
            </div>
            <h1 className="mt-6 text-4xl font-bold tracking-tight sm:text-6xl">
              A scanner that
              <br />
              <span className="text-accent">shows its work.</span>
            </h1>
            <p className="mt-6 text-lg text-muted leading-relaxed">
              The <span className="font-medium text-fg">Tapeline Score</span>{" "}
              blends six factors at published weights into one read on every
              ticker. Every call goes on a permanent public record &mdash; same
              day, no edits.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/signup" className="btn-primary text-base">
                Try Premium free for 14 days &rarr;
              </Link>
              <Link href="/scorecard" className="btn-ghost text-base">
                See the record
              </Link>
            </div>
            <p className="mt-3 text-xs text-muted">
              14-day Premium trial &middot; no credit card &middot; cancel in
              one click
            </p>
          </div>

          <div className="lg:col-span-3">
            <ScannerPreview />
            <p className="mt-3 text-center text-xs text-muted">
              Live mock &middot; hover any score in the app for the full
              6-factor breakdown
            </p>
          </div>
        </div>
      </section>

      {/* LIVE COUNTERS — concrete numbers from /api/status, refreshed every 60s.
          Replaces vague "live" with specifics: how many tickers, how many
          news items, current regime, last tick. */}
      <section className="border-y border-border/60">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <LiveCounters />
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
              label="Published weights"
              body={
                <>
                  Trend 25% &middot; RS 20% &middot; Fund 15% &middot; SM 15%
                  &middot; Macro 15% &middot; Mom 10%. No black box. No hidden
                  multipliers. Every weight change is{" "}
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
                    Read the formula
                  </Link>
                  .
                </>
              }
            />
          </FadeIn>
        </div>
        </div>
      </section>

      {/* HOW IT WORKS — three-step process. Cards are appropriate here
          because each step is sequential and self-contained. */}
      <section className="bg-panel/10">
        <div className="mx-auto max-w-6xl px-6 py-8 sm:py-12">
          <p className="eyebrow text-accent">How it works</p>
          <h2 className="mt-3 max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
            From data to decision in one glance.
          </h2>

          <div className="mt-12 grid gap-6 md:grid-cols-3">
            <FadeIn delayMs={0}>
              <Step n="1" title="Six factors, exact weights">
                Trend 25% &middot; relative strength 20% &middot; fundamentals
                15% &middot; smart money 15% &middot; macro 15% &middot;
                momentum 10%. Same weights every tick.
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
                  className="block h-full rounded-2xl border border-border bg-panel/40 p-6 transition hover:border-accent/40 hover:bg-panel/60"
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
              See all {POSTS.length} posts &rarr;
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
            7-day full refund &mdash; if it doesn&rsquo;t click, you owe us
            nothing.
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
            scorecard. Free for 14 days, no card.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="btn-primary text-base">
              Try Premium free &rarr;
            </Link>
            <Link href="/pricing" className="btn-ghost text-base">
              See pricing
            </Link>
          </div>
          <p className="mt-4 text-xs text-muted">
            No credit card &middot; Cancel in one click &middot; 7-day refund
            on monthly
          </p>
        </div>
      </section>

      {/* Newsletter lead-magnet — second-chance email capture for visitors
          who scrolled past the trial CTAs. Lower commitment than /signup
          (no card, no account). Once they're in the list, the daily Top 10
          send + the in-email Premium CTA do the eventual conversion lift.
          Placed before the footer so it's the last thing the eye sees on
          the way out, not competing with the primary trial CTA above. */}
      <section className="border-t border-border bg-panel/30">
        <div className="mx-auto max-w-3xl px-6 py-8 sm:py-10">
          <div className="text-center mb-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-bg px-3 py-1 text-xs text-muted">
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
    <div className="card p-7">
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
