import Link from "next/link";
import { ScannerPreview } from "@/components/ScannerPreview";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TickerSearch } from "@/components/TickerSearch";
import { LiveCounters } from "@/components/LiveCounters";
import { FadeIn } from "@/components/FadeIn";

export default function LandingPage() {
  return (
    <main className="min-h-screen">
      <MarketingNav />

      {/* Hero + product preview in one fold.
          Soft accent-coloured radial glow behind the section gives depth
          without colour — Linear/Vercel-style. Pointer-events disabled so
          it never traps clicks. */}
      <section className="relative overflow-hidden px-6 pt-16 pb-12">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 -top-40 -z-10 mx-auto h-[640px] max-w-6xl"
        >
          <div className="absolute left-1/2 top-0 h-[480px] w-[920px] -translate-x-1/2 rounded-full bg-accent/10 blur-3xl" />
          <div className="absolute left-[12%] top-32 h-[280px] w-[420px] rounded-full bg-up/5 blur-3xl" />
        </div>
        <div className="mx-auto max-w-6xl grid gap-10 lg:grid-cols-5 lg:gap-8">
          {/* Left: copy */}
          <div className="lg:col-span-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-panel px-3 py-1 text-xs text-muted">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" />
              Live market scanning
            </div>
            <h1 className="mt-6 text-5xl font-bold tracking-tight sm:text-6xl">
              A scanner that
              <br />
              <span className="text-accent">shows its work.</span>
            </h1>
            <p className="mt-6 text-lg text-muted">
              The <span className="text-fg font-medium">Tapeline Score</span> blends six factors at published weights into one
              read on every ticker. Every call goes on a permanent public record — same day.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/signup" className="btn-primary text-base">Start 14-day trial &rarr;</Link>
              <Link href="/scorecard" className="btn-ghost text-base">See the record</Link>
            </div>
            <p className="mt-3 text-xs text-muted">14-day Premium trial · no credit card · cancel in one click</p>
            {/* Compare strip — visitors actively comparing scanners click here
                rather than bouncing. Lands on the existing /compare/* pages. */}
            <p className="mt-5 text-xs text-muted">
              Compare with{" "}
              <Link href="/compare/zacks" className="text-accent hover:underline">Zacks</Link>
              {" · "}
              <Link href="/compare/finviz" className="text-accent hover:underline">Finviz</Link>
              {" · "}
              <Link href="/compare/wallstreetzen" className="text-accent hover:underline">WallStreetZen</Link>
            </p>
          </div>

          {/* Right: product preview + try-it search.
              Search lives next to the scanner preview so the visitor sees the
              live mock, then immediately gets to type their own ticker — the
              "see what you'd get" loop happens before any signup ask. */}
          <div className="lg:col-span-3">
            <ScannerPreview />
            <p className="mt-3 text-center text-xs text-muted">
              Every ticker scored on 6 factors · hover any score in the app for the full breakdown
            </p>
            <div className="mt-6 rounded-2xl border border-border bg-panel/40 p-5">
              <TickerSearch />
            </div>
          </div>
        </div>
      </section>

      {/* Live counters strip — concrete numbers fetched from /api/status,
          refreshed every 60s. Replaces vague "live" with specifics: how
          many tickers, how many news items, current regime, last tick. */}
      <section className="border-t border-border bg-panel/20">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <LiveCounters />
        </div>
      </section>

      {/* Headline trust pillars — the moat in three lines.
          Lands between the hero and the data/legal microcopy strip below.
          Reads as a confident factual claim, not a marketing line, because
          each pillar links to the artefact that proves it. */}
      <section>
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-10 sm:grid-cols-3">
          <FadeIn delayMs={0}>
            <Pillar
              label="Six published weights"
              body={<>
                Trend 25% · RS 20% · Fund 15% · SM 15% · Macro 15% · Mom 10%.
                No black box, no hidden multipliers.
              </>}
              href="/how-it-works"
              cta="See the formula"
            />
          </FadeIn>
          <FadeIn delayMs={100}>
            <Pillar
              label="Every call back-checked vs SPY"
              body="Top-10 picks logged at close. Next-day return + alpha vs SPY recorded automatically."
              href="/scorecard"
              cta="See the scorecard"
            />
          </FadeIn>
          <FadeIn delayMs={200}>
            <Pillar
              label="100% on the public record"
              body="No cherry-picking. No hindsight edits. Original reasoning preserved with every entry."
              href="/scorecard"
              cta="Audit any day"
            />
          </FadeIn>
        </div>
      </section>

      {/* Data + legal microcopy — quieter strip beneath the moat pillars. */}
      <section className="border-y border-border bg-panel/50">
        <div className="mx-auto grid max-w-6xl gap-3 px-6 py-4 text-center text-xs text-muted sm:grid-cols-3">
          <div>🔬 Powered by Massive (formerly Polygon.io) licensed data</div>
          <div>📈 Every pick on the <Link href="/scorecard" className="text-accent hover:underline">public scorecard</Link></div>
          <div>⚠️ Informational only — <Link href="/legal/risk" className="text-accent hover:underline">not investment advice</Link></div>
        </div>
      </section>

      {/* How it works — 3 steps */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="text-3xl font-bold tracking-tight">How it works</h2>
        <p className="mt-2 text-muted">From data to decision in one glance.</p>

        <div className="mt-10 grid gap-6 md:grid-cols-3">
          <FadeIn delayMs={0}>
            <Step n="1" title="Six factors, exact weights">
              Trend 25% · relative strength 20% · fundamentals 15% · smart money 15% · macro 15% · momentum 10%.
              Weights are public. Every change is announced before it ships.
            </Step>
          </FadeIn>
          <FadeIn delayMs={100}>
            <Step n="2" title="One sentence per ticker">
              Default plain-English Why on every row — no chat session required, no premium gate.
              Hover the score for the factor breakdown.
            </Step>
          </FadeIn>
          <FadeIn delayMs={200}>
            <Step n="3" title="Every call on the public record">
              Top-10 picks logged daily to the <Link href="/scorecard" className="text-accent">public scorecard</Link>{" "}
              with the original reasoning preserved. Performance vs SPY recorded next session. No cherry-picking, no hindsight edits.
            </Step>
          </FadeIn>
        </div>

        <div className="mt-8 text-center">
          <Link href="/how-it-works" className="text-sm text-accent hover:underline">
            See the exact weights and methodology →
          </Link>
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-4xl px-6 pt-10 pb-20 text-center">
        <h2 className="text-4xl font-bold tracking-tight">Stop scrolling. Start scanning.</h2>
        <p className="mt-4 text-muted">14 days free · No credit card · Cancel in one click</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/signup" className="btn-primary text-base">
            Open the live scanner &rarr;
          </Link>
          <Link href="/pricing" className="btn-ghost text-base">
            See pricing
          </Link>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}

function Step({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <div className="card p-6">
      <div className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-accent/10 font-mono text-sm font-bold text-accent">
        {n}
      </div>
      <h3 className="mt-4 text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-muted leading-relaxed">{children}</p>
    </div>
  );
}

function Pillar({
  label, body, href, cta,
}: {
  label: string;
  body: React.ReactNode;
  href: string;
  cta: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-2.5">
        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-up/15 text-up">
          <svg className="h-3 w-3" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M3 8l3 3 7-7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <h3 className="text-sm font-semibold tracking-tight">{label}</h3>
      </div>
      <p className="mt-2 text-sm text-muted leading-relaxed">{body}</p>
      <Link href={href} className="mt-2 inline-block text-xs text-accent hover:underline">
        {cta} →
      </Link>
    </div>
  );
}

