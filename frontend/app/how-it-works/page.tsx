import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "How Tapeline Works: 6-Factor Stock Scoring Formula (Public Weights)",
  description:
    "How the Tapeline Score is calculated: a weighted blend of Trend 25%, RS 20%, Fundamentals 15%, Smart Money 15%, Macro 15%, Momentum 10%. No black box.",
  path: "/how-it-works",
});

// Q/A drawn from the page so Google can render the methodology FAQ under
// "tapeline how it works" / "how is the tapeline score calculated" SERPs.
const HOW_FAQ = [
  {
    q: "How is the Tapeline Score calculated?",
    a: "Each ticker gets six sub-scores (Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum), each normalised to 0-100. The composite is a weighted sum: 25% Trend + 20% Relative Strength + 15% Fundamentals + 15% Smart Money + 15% Macro + 10% Momentum. Weights are fixed and public; any change ships through the public changelog.",
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
    q: "Is the formula really public?",
    a: "Yes. The exact 6-factor weighted equation is published on this page and reproduced in our blog, with every weight change versioned in the public changelog. The moat is the data spine plus the public scorecard — anyone is welcome to copy the formula.",
  },
];

const FACTORS = [
  { name: "Trend",               weight: 25, desc: "Slope of 20/50/200-day moving averages, MACD direction, distance from 200DMA." },
  { name: "Relative strength",   weight: 20, desc: "Price performance vs SPY and sector ETF over 3M, 6M, 1Y." },
  { name: "Fundamentals",        weight: 15, desc: "Revenue growth, margin trend, P/E, debt/equity, ROE, EPS surprises." },
  { name: "Smart money",         weight: 15, desc: "Insider net buying (SEC Form 4), Congressional disclosures." },
  { name: "Macro",               weight: 15, desc: "Current market regime, sector rotation, rate direction, VIX level." },
  { name: "Momentum",            weight: 10, desc: "RSI, Bollinger Band width percentile, volume expansion, breakout proximity." },
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
    <main className="min-h-screen">
      {/* FAQPage schema for the methodology questions below. */}
      <script {...jsonLdScript(faqJsonLd(HOW_FAQ))} />
      <MarketingNav />

      {/* Hero */}
      <section className="relative section py-8 sm:py-10">
        <div className="pointer-events-none absolute inset-0 bg-hero opacity-60" />
        <div className="relative mx-auto max-w-3xl text-center">
          <p className="eyebrow">Methodology</p>
          <h1 className="mt-3 text-4xl font-bold sm:text-6xl">Six factors. Exact weights. Public record.</h1>
          <p className="mt-6 text-lg text-muted">
            Every score is a transparent weighted blend of six published factors —
            no black box, no mystery AI, no chat assistant required. You see each contribution on every ticker.
          </p>
        </div>
      </section>

      {/* Factors */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-4xl">
          <p className="eyebrow">The six factors</p>
          <h2 className="mt-3 text-3xl font-semibold">Composite = weighted sum of 6 sub-scores</h2>

          <div className="mt-12 space-y-3">
            {FACTORS.map((f) => (
              <div key={f.name} className="flex items-start gap-6 rounded-xl border border-border bg-panel p-6 transition-colors hover:border-border2">
                <div className="font-mono text-xl font-semibold text-accent nums w-14">{f.weight}%</div>
                <div className="flex-1">
                  <h3 className="font-semibold">{f.name}</h3>
                  <p className="mt-1.5 text-sm text-muted leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 rounded-xl border border-border bg-panel p-6">
            <p className="text-xs uppercase tracking-wider text-subtle">The formula</p>
            <pre className="mt-3 overflow-x-auto text-sm text-muted nums leading-relaxed">
{`score = 0.25 × trend
      + 0.20 × relative_strength
      + 0.15 × fundamentals
      + 0.15 × smart_money
      + 0.15 × macro
      + 0.10 × momentum`}
            </pre>
            <p className="mt-4 text-xs text-subtle leading-relaxed">
              Each sub-score is normalised to 0–100 using factor-specific rules. Weights are
              fixed and visible. We publish changes before rolling them out, tracked on the{" "}
              <Link href="/scorecard" className="link">public scorecard</Link>.
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
