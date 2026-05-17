import Link from "next/link";
import { ScannerPreview } from "@/components/ScannerPreview";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { LiveCounters } from "@/components/LiveCounters";
import { FadeIn } from "@/components/FadeIn";

export default function LandingPage() {
  return (
    <main className="min-h-screen">
      <MarketingNav />

      {/* HERO — single-purpose fold.
          Left: one sentence value prop + one primary CTA + one ghost CTA.
          Right: live mock table (ScannerPreview). Nothing else competes.
          The TickerSearch previously sat under the preview, doing the same
          job twice; removed so the eye lands on one demo, not two. */}
      <section className="relative overflow-hidden px-6 pt-20 pb-16">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 -top-40 -z-10 mx-auto h-[640px] max-w-6xl"
        >
          <div className="absolute left-1/2 top-0 h-[480px] w-[920px] -translate-x-1/2 rounded-full bg-accent/10 blur-3xl" />
          <div className="absolute left-[12%] top-32 h-[280px] w-[420px] rounded-full bg-up/5 blur-3xl" />
        </div>
        <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-5 lg:gap-10">
          <div className="lg:col-span-2 lg:pt-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-panel px-3 py-1 text-xs text-muted">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" />
              Live market scanning
            </div>
            <h1 className="mt-6 text-5xl font-bold tracking-tight sm:text-6xl">
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
                Start 14-day trial &rarr;
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
      <section className="border-y border-border bg-panel/20">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <LiveCounters />
        </div>
      </section>

      {/* WHY THIS IS DIFFERENT — three bold contrastive claims, NOT cards.
          The trust pillars used to be a 3-card grid, identical in shape to
          the "How it works" cards below — same rhythm twice. Now: typography-
          led statements with thin dividers, then cards for the process. Two
          different visual treatments for two different jobs. */}
      <section className="mx-auto max-w-6xl px-6 py-24">
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
      </section>

      {/* HOW IT WORKS — three-step process. Cards are appropriate here
          because each step is sequential and self-contained. */}
      <section className="border-t border-border bg-panel/10">
        <div className="mx-auto max-w-6xl px-6 py-24">
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

      {/* OBJECTION HANDLING / FAQ — five short answers to the questions every
          first-time visitor asks before they sign up. Conversion best
          practice: anticipate the doubt that's actually killing the signup
          and answer it before they need to ask. */}
      <section className="mx-auto max-w-3xl px-6 py-24">
        <p className="eyebrow text-accent">Common questions</p>
        <h2 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
          Things people ask before signing up.
        </h2>
        <div className="mt-10 divide-y divide-border border-t border-b border-border">
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
            US equities + commodity ETFs from Massive (formerly Polygon.io),
            macro from FRED, fundamentals + insider Form 4 from Finnhub, news
            wire from Benzinga. Full list on{" "}
            <Link href="/data-sources" className="link">
              data sources
            </Link>
            .
          </Faq>
        </div>
      </section>

      {/* FINAL CTA — mirrors the hero promise rather than a generic
          "Stop scrolling" line. Restated specifically: one score, one
          sentence, one public record. */}
      <section className="border-t border-border bg-gradient-to-b from-panel/20 to-transparent">
        <div className="mx-auto max-w-3xl px-6 py-24 text-center">
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
              Start free trial &rarr;
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
