import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "How Tapeline Works: Our 6-Factor Stock Scoring Methodology",
  description:
    "How the Tapeline Score is calculated: a weighted blend of six named factors — Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum. No black box; every pick logged to a public scorecard.",
  path: "/how-it-works",
});

// Q/A drawn from the page so Google can render the methodology FAQ under
// "tapeline how it works" / "how is the tapeline score calculated" SERPs.
const HOW_FAQ = [
  {
    q: "How is the Tapeline Score calculated?",
    a: "Each ticker gets six sub-scores (Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum), each normalised to 0-100. The composite is a weighted blend of the six — weighted most heavily toward Trend and Relative Strength, and least toward Momentum. The factor set is fixed and public; any change ships through the public changelog.",
  },
  {
    q: "What do the signal labels mean?",
    a: "Six descriptive tiers map to score ranges: HIGH CONVICTION (85-100), STRONG SETUP (70-84), CONSTRUCTIVE (55-69), NEUTRAL (40-54), CAUTION (25-39), WEAK (0-24). Labels are descriptive, not prescriptive — Tapeline is not a registered investment adviser and does not issue buy/sell calls.",
  },
  {
    q: "How often does the score update?",
    a: "Scores re-tick every minute during market hours and persist between sessions. Most data feeds (price, volume, RSI, MACD, regime) update sub-60s; fundamentals refresh on company filing cadence; insider Form 4 within hours of SEC filing.",
  },
  {
    q: "What is the per-ticker confidence percentage?",
    a: "Confidence reflects how many of the underlying data feeds returned data for a given ticker — not every name has fundamentals coverage, recent insider filings, or analyst coverage. 95%+ means full data on every signal feature; under 40% means sparse data and the score should be deprioritised.",
  },
  {
    q: "Is the methodology really public?",
    a: "Yes. We name all six factors, show each factor's contribution on every ticker, and log every top-10 daily pick to a public scorecard that's back-checked against SPY the next session. Any change to the factor set ships through the public changelog. The moat is the data spine plus that public track record — not a secret list of factors.",
  },
];

// Factors are listed in descending weight order. We publish the ordering
// (which factors matter most) and each factor's contribution per ticker, but
// not the exact numeric weights — those are applied consistently to every name.
// Each factor now has its own un-gated page at /how-it-works/{slug} explaining
// what it measures, how the reading is derived, what feeds it, and where it is
// weak. Content for those pages lives in ./factors.ts.
//
// 2026-07-18 accuracy fix: the Smart money line previously read "Insider net
// buying (SEC Form 4) and, where applicable, Congressional disclosures and
// institutional flow." Only the Form 4 half is true — the sub-score reads
// disclosed insider transactions and nothing else. Congressional disclosure
// data is ingested and published as its own feed in the product, but it is not
// an input to this factor, and there is no institutional-flow input at all.
// Corrected here rather than left to contradict the factor page it links to.
//
// Same fix on Relative strength: the line claimed a sector comparison. sub_rs
// in backend/app/services/score.py measures the ticker's change minus the
// broad-market benchmark's over 3M/6M/1Y and is not sector-adjusted at all.
const FACTORS = [
  { name: "Trend",               slug: "trend",             emphasis: "Weighted most", desc: "Direction and quality of the price trend across short-, medium-, and long-term timeframes." },
  { name: "Relative strength",   slug: "relative-strength", emphasis: "High",          desc: "The stock's price change minus the broad-market benchmark's, over three horizons. Not sector-adjusted." },
  { name: "Fundamentals",        slug: "fundamentals",      emphasis: "Core",          desc: "Earnings quality, growth, profitability, and balance-sheet health." },
  { name: "Smart money",         slug: "smart-money",       emphasis: "Core",          desc: "Net direction of insider transactions disclosed to the SEC on Form 4." },
  { name: "Macro",               slug: "macro",             emphasis: "Core",          desc: "The prevailing market regime, applied identically to every ticker on a given tick." },
  { name: "Momentum",            slug: "momentum",          emphasis: "Weighted least", desc: "Short-horizon price acceleration and breakout posture." },
];

const SIGNALS = [
  { label: "HIGH CONVICTION", range: "85–100", tone: "text-up",            desc: "All six factors aligned positive." },
  { label: "STRONG SETUP",    range: "70–84",  tone: "text-up/80",         desc: "Most factors favourable." },
  { label: "CONSTRUCTIVE",    range: "55–69",  tone: "text-accent",        desc: "Net positive, not decisive." },
  { label: "NEUTRAL",         range: "40–54",  tone: "text-muted",         desc: "Factors cancel out." },
  { label: "CAUTION",         range: "25–39",  tone: "text-warn",    desc: "More factors negative." },
  { label: "WEAK",            range: "0–24",   tone: "text-down",          desc: "Broadly negative." },
];

export default function HowItWorksPage() {
  return (
    <main id="main" className="min-h-screen">
      {/* FAQPage schema for the methodology questions below. */}
      <script {...jsonLdScript(faqJsonLd(HOW_FAQ))} />
      <MarketingNav />

      {/* Hero */}
      <section className="relative section py-8 sm:py-10">
        <div className="pointer-events-none absolute inset-0 bg-hero opacity-60" />
        <div className="relative mx-auto max-w-3xl text-center">
          <p className="eyebrow">Methodology</p>
          <h1 className="mt-3 text-4xl font-bold sm:text-6xl">Six factors. Named. Public record.</h1>
          <p className="mt-6 text-lg text-muted">
            Every score is a weighted blend of six named factors —
            no black box, no mystery AI, no chat assistant required. You see each factor&apos;s contribution on every ticker.
          </p>
        </div>
      </section>

      {/* Factors */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-4xl">
          <p className="eyebrow">The six factors</p>
          <h2 className="mt-3 text-3xl font-semibold">Composite = weighted blend of 6 sub-scores</h2>

          <div className="mt-12 space-y-3">
            {FACTORS.map((f) => (
              <Link
                key={f.name}
                href={`/how-it-works/${f.slug}`}
                className="group flex items-start gap-6 rounded-xl border border-border bg-panel p-6 transition-colors hover:border-accent/40"
              >
                <div className="font-mono text-[0.7rem] font-semibold uppercase tracking-wider text-accent w-24 pt-1">{f.emphasis}</div>
                <div className="flex-1">
                  <h3 className="font-semibold transition-colors group-hover:text-accent">
                    {f.name}
                    <span aria-hidden="true" className="ml-2 text-xs text-subtle">&rarr;</span>
                  </h3>
                  <p className="mt-1.5 text-sm text-muted leading-relaxed">{f.desc}</p>
                </div>
              </Link>
            ))}
          </div>

          <p className="mt-4 text-xs text-subtle leading-relaxed">
            Each factor has its own page: what it measures, how the reading is
            derived, which data feeds it, and where it is weak. The honest limits
            are stated on each factor&rsquo;s own page rather than collected out
            of sight.
          </p>

          <div className="mt-8 rounded-xl border border-border bg-panel p-6">
            <p className="text-xs uppercase tracking-wider text-subtle">How the blend is weighted</p>
            <p className="mt-3 text-sm text-muted leading-relaxed">
              The composite leans most heavily on <strong>Trend</strong> and <strong>Relative
              Strength</strong>, then <strong>Fundamentals</strong>, <strong>Smart Money</strong>,
              and <strong>Macro</strong>, and least on <strong>Momentum</strong> — short-term
              momentum on its own tends to mean-revert, so it&apos;s the smallest input. Each
              sub-score is normalised to 0–100 and the same weighting is applied to every ticker.
            </p>
            <p className="mt-4 text-xs text-subtle leading-relaxed">
              The factor set is fixed and visible, and each factor&apos;s contribution is shown on
              every ticker. Any change to the factors ships through the{" "}
              <Link href="/scorecard" className="link">public scorecard</Link> and changelog.
            </p>
          </div>

          {/* Confidence band — explains the per-ticker confidence column */}
          <div className="mt-6 rounded-xl border border-border bg-panel p-6">
            <p className="text-xs uppercase tracking-wider text-subtle">Per-ticker confidence</p>
            <h3 className="mt-2 text-lg font-semibold">Not every signal has the same evidence behind it.</h3>
            <p className="mt-3 text-sm text-muted leading-relaxed">
              We surface a confidence percentage on every row. It varies based on which underlying
              data feeds returned data for that ticker — not every ETF has a P/E, not every
              stock has recent insider filings, not every name has analyst coverage.
            </p>
            <div className="mt-4 grid gap-2 text-sm">
              <div className="flex justify-between border-b border-border/30 py-2">
                <span className="text-up font-medium">95%+</span>
                <span className="text-muted">Full data on every signal feature — strongest evidence</span>
              </div>
              <div className="flex justify-between border-b border-border/30 py-2">
                <span className="text-up font-medium">80–95%</span>
                <span className="text-muted">Most features present, missing 1–3 minor data points</span>
              </div>
              <div className="flex justify-between border-b border-border/30 py-2">
                <span className="font-medium">60–80%</span>
                <span className="text-muted">Core scoring data + most fundamentals — typical liquid stock</span>
              </div>
              <div className="flex justify-between border-b border-border/30 py-2">
                <span className="text-warn font-medium">40–60%</span>
                <span className="text-muted">Only basic price/trend data — caution</span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-down font-medium">&lt;40%</span>
                <span className="text-muted">Sparse data — unreliable signals, deprioritise</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Signals */}
      <section>
        <div className="section py-8 sm:py-10">
          <div className="mx-auto max-w-3xl">
            <p className="eyebrow">Signal labels</p>
            <h2 className="mt-3 text-3xl font-semibold">Descriptive, not prescriptive.</h2>
            <p className="mt-4 text-muted">
              Each score maps to a label that describes the state of factor data.
              We never tell you what to do with it.
            </p>

            <div className="mt-10 space-y-2">
              {SIGNALS.map((s) => (
                <div
                  key={s.label}
                  className="grid grid-cols-[minmax(8.5rem,auto)_1fr_auto] items-center gap-x-4 gap-y-1 py-4"
                >
                  <span className={`font-mono text-sm font-medium ${s.tone}`}>{s.label}</span>
                  <span className="text-sm text-muted">{s.desc}</span>
                  <span className="font-mono text-xs text-muted nums w-16 text-right">{s.range}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* FAQ — visible content that mirrors HOW_FAQ JSON-LD above. */}
      <section>
        <div className="section py-10">
          <div className="mx-auto max-w-3xl">
            <p className="eyebrow">Common questions</p>
            <h2 className="mt-3 text-3xl font-semibold">Methodology FAQ</h2>
            <div className="mt-8 divide-y divide-border/60">
              {HOW_FAQ.map((item) => (
                <details key={item.q} className="group py-4">
                  <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
                    <h3 className="text-sm sm:text-base font-medium">{item.q}</h3>
                    <span className="text-muted transition-transform group-open:rotate-45">+</span>
                  </summary>
                  <p className="mt-3 text-sm text-muted leading-relaxed">{item.a}</p>
                </details>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Trust surfaces — un-gated, no signup. /limitations is listed FIRST and
          described plainly, because burying the weaknesses page under the CTA
          would defeat the point of having written it. */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">Before you trust any of this</p>
          <h2 className="mt-3 text-3xl font-semibold">Read the parts that argue against us.</h2>
          <div className="mt-8 grid gap-3 sm:grid-cols-3">
            <Link
              href="/limitations"
              className="lift group rounded-xl border border-border bg-panel p-5 hover:border-accent/40"
            >
              <h3 className="text-sm font-semibold transition-colors group-hover:text-accent">Limitations</h3>
              <p className="mt-1.5 text-xs text-muted leading-relaxed">
                What Tapeline is not good at: a small public sample, a blunt
                six-factor screen, and data that can be late or wrong.
              </p>
            </Link>
            <Link
              href="/scorecard"
              className="lift group rounded-xl border border-border bg-panel p-5 hover:border-accent/40"
            >
              <h3 className="text-sm font-semibold transition-colors group-hover:text-accent">Public scorecard</h3>
              <p className="mt-1.5 text-xs text-muted leading-relaxed">
                Every daily top-10, back-checked against the next session, with
                the sample size shown and losing days left in.
              </p>
            </Link>
            <Link
              href="/why"
              className="lift group rounded-xl border border-border bg-panel p-5 hover:border-accent/40"
            >
              <h3 className="text-sm font-semibold transition-colors group-hover:text-accent">Why it works this way</h3>
              <p className="mt-1.5 text-xs text-muted leading-relaxed">
                A note from the founder on publishing the method and the record,
                including the days the picks went nowhere.
              </p>
            </Link>
          </div>
          <p className="mt-6 text-sm text-muted">
            Methodology changes, data errors and corrections are dated in the{" "}
            <Link href="/changelog" className="link">changelog</Link>.
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="section py-8 sm:py-10 text-center">
        <h2 className="text-3xl font-semibold">See the scores live.</h2>
        <p className="mt-3 text-muted">14-day Premium trial. No credit card.</p>
        <Link href="/signup" className="btn-primary mt-6 inline-flex h-11 px-6 text-base">
          Try Premium free &rarr;
        </Link>
      </section>

      <TransparencyStrip current="/how-it-works" />
      <MarketingFooter />
    </main>
  );
}
