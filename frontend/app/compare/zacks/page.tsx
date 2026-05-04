import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";

export const metadata = {
  title: "Tapeline vs Zacks — live scoring, public formula, daily scorecard",
  description:
    "Why traders move from Zacks Premium to Tapeline. Public weights, sub-60s live data, plain-English Why on every ticker — none of which Zacks publishes.",
};

// Tapeline-wins first. Each row carries concrete diff copy that lands the
// punch — not just "✓ vs —", but a one-line reason it matters.
const WINS = [
  {
    label: "Public scoring formula",
    tapeline: "✓ Six factors, exact weights on /how-it-works",
    competitor: "Factors named, weights opaque",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence on every ticker",
    competitor: "—  (you read multi-page reports)",
  },
  {
    label: "Per-pick public scorecard",
    tapeline: "✓ Every top-10 back-checked vs SPY next day",
    competitor: "Aggregate Rank performance only — no per-pick receipts",
  },
  {
    label: "Live data refresh",
    tapeline: "Sub-60s — score reacts intraday",
    competitor: "Daily rebuild — yesterday's score until tomorrow",
  },
  {
    label: "Squeeze + setup detection",
    tapeline: "✓ BB compression + volume + OBV scored",
    competitor: "—",
  },
  {
    label: "Congressional trades feed",
    tapeline: "✓ House + Senate, daily",
    competitor: "—",
  },
  {
    label: "Elite 13F holdings",
    tapeline: "✓ Buffett, Burry, Tepper, Ackman + 4 more",
    competitor: "—",
  },
  {
    label: "Top tier price",
    tapeline: "$49/mo (Premium)",
    competitor: "$2,995/yr ≈ $250/mo (Ultimate) — 5× more",
  },
  {
    label: "Email noise level",
    tapeline: "10/day cap (Pro) · digests opt-in",
    competitor: "Heavy daily volume — top complaint in reviews",
  },
  {
    label: "UI / mobile",
    tapeline: "✓ 2026 build, mobile-responsive, dark mode",
    competitor: "Late-2000s table UI, weak on phone",
  },
  {
    label: "Try without a card",
    tapeline: "✓ 14-day Premium trial, no card",
    competitor: "Direct paid signup",
  },
];

const TRADEOFFS = [
  {
    label: "Brand history",
    tapeline: "Pre-launch (under 12 months)",
    competitor: "37-year track record + academic citations",
    note: "Zacks' aggregate Rank performance is genuinely impressive. We're younger — that's why our scorecard is per-pick public from day one rather than a 37-year aggregate.",
  },
  {
    label: "Cheapest paid tier",
    tapeline: "$24.99/mo (Pro, billed annually)",
    competitor: "~$21/mo (Premium, $249/yr only)",
    note: "Effectively the same. Tapeline has month-to-month pricing too; Zacks Premium is annual-only with no monthly option.",
  },
  {
    label: "Universe size",
    tapeline: "~1,000 actively scored (top by $-volume) · 5,757 tracked",
    competitor: "4,400+ US stocks ranked daily",
    note: "Zacks ranks more names. Tapeline scores the top ~1,000 by daily dollar-volume — the cutoff lands around the bottom of the S&P MidCap 400. Below that, bid-ask spreads make a Rank #1 on a $0.20 micro-cap with 50K shares of daily volume non-actionable. The other ~4,700 names in our universe table are tracked for watchlist + news + per-ticker pages, just not actively scored.",
  },
];

const VERIFIED_ON = "2026-05-04";

export default function VsZacksPage() {
  return (
    <main className="min-h-screen">
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-4 sm:px-6 py-12">
        <p className="eyebrow">Comparison</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          Tapeline vs Zacks — why traders switch.
        </h1>
        <p className="mt-4 text-lg text-muted">
          Zacks built a 37-year reputation on the Zacks Rank — a proprietary,
          opaque-weighted, daily-rebuilt #1–#5 grade that emails you the picks. Tapeline
          publishes the exact 6-factor weights, recomputes the score sub-60s on every
          ticker, and back-checks every top-10 against the next-day price publicly. Pick
          Tapeline if you want transparency + speed; pick Zacks if 37 years of brand
          history outweighs everything else.
        </p>
        <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-up/30 bg-up/5 px-4 py-2 text-sm text-up">
          <span className="text-base">✓</span>
          <span><strong>11 categories</strong> Tapeline wins outright. <strong>3</strong> honest tradeoffs.</span>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-4 sm:px-6 pb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-up">
          Where Tapeline wins
        </h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3 text-left">Feature</th>
                <th className="px-4 py-3 text-left text-accent">Tapeline</th>
                <th className="px-4 py-3 text-left">Zacks Premium</th>
              </tr>
            </thead>
            <tbody>
              {WINS.map((r) => (
                <tr key={r.label} className="border-b border-border/30">
                  <td className="px-4 py-3 font-medium">{r.label}</td>
                  <td className="px-4 py-3 font-medium text-accent">{r.tapeline}</td>
                  <td className="px-4 py-3 text-subtle">{r.competitor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-4 sm:px-6 pb-12">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Honest tradeoffs
        </h2>
        <p className="mb-3 text-xs text-subtle">
          Where Zacks has a real edge — explained so you can decide what matters.
        </p>
        <div className="space-y-3">
          {TRADEOFFS.map((r) => (
            <div key={r.label} className="rounded-lg border border-border bg-panel/40 p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h3 className="font-medium">{r.label}</h3>
                <div className="text-xs text-subtle">{r.competitor} <span className="opacity-50">vs</span> {r.tapeline}</div>
              </div>
              <p className="mt-2 text-sm text-muted leading-relaxed">{r.note}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-4 sm:px-6 py-12 text-center">
        <h2 className="text-3xl font-bold tracking-tight">Try Tapeline free for 14 days.</h2>
        <p className="mt-3 text-muted">No credit card. Cancel in one click.</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href="/signup" className="btn-primary">Start free trial →</Link>
          <Link href="/scorecard" className="btn-ghost">See the scorecard first</Link>
        </div>
        <p className="mt-4 text-xs text-subtle">
          Or read the <Link href="/how-it-works" className="link">methodology</Link>.
        </p>
      </section>

      <p className="mx-auto max-w-3xl px-4 sm:px-6 pb-12 text-center text-[11px] text-subtle">
        Comparison data verified {VERIFIED_ON}. Competitor pricing and feature claims sourced from
        their public pages. Spot a mistake?{" "}
        <a href="mailto:support@tapeline.io" className="text-accent hover:underline">Tell us</a> — we
        update within 48 hours.
      </p>

      <MarketingFooter />
    </main>
  );
}
