import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";

export const metadata = {
  title: "Tapeline vs Finviz — synthesis, transparency, public scorecard",
  description:
    "Why traders pick Tapeline over Finviz Elite for serious stock picking. One score per ticker, public formula, public scorecard — none of which Finviz publishes.",
};

// "Tapeline wins" rows first — the categories that decide which tool earns
// a slot in someone's daily workflow. Tradeoff rows below are reframed: every
// category Finviz "wins" is reframed as a feature-not-bug for our positioning.
const WINS = [
  {
    label: "One composite score per ticker",
    tapeline: "✓ Six factors, public weights",
    competitor: "—  (no synthesis at all)",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence, every ticker",
    competitor: "—  (you write your own thesis)",
  },
  {
    label: "Public scorecard with receipts",
    tapeline: "✓ Every top-10 back-checked vs SPY next day",
    competitor: "—  (no track record published)",
  },
  {
    label: "Squeeze setup detection",
    tapeline: "✓ BB compression + volume + OBV scored",
    competitor: "—  (you build it from raw filters)",
  },
  {
    label: "Congressional trades feed",
    tapeline: "✓ House + Senate disclosed trades, daily",
    competitor: "—",
  },
  {
    label: "Elite 13F holdings",
    tapeline: "✓ Buffett, Burry, Tepper, Ackman + 4 more",
    competitor: "—",
  },
  {
    label: "Smart watchlist alerts",
    tapeline: "✓ Score-change alerts via email + Telegram + push",
    competitor: "Email only, simple price alerts",
  },
  {
    label: "Modern UI",
    tapeline: "✓ Built 2026, mobile-responsive, dark mode",
    competitor: "Late-90s table aesthetic",
  },
  {
    label: "Try without a card",
    tapeline: "✓ 14-day full Premium trial, no card",
    competitor: "Direct paid signup, no trial",
  },
];

// Honest tradeoffs — Finviz wins each, but reframed honestly so the prospect
// can decide which tradeoff matters for THEIR workflow.
const TRADEOFFS = [
  {
    label: "Universe size",
    tapeline: "~112 most-liquid US tickers + sector ETFs",
    competitor: "9,000+ including OTC + penny stocks",
    note: "We filter for liquidity — a score on a $0.20 stock you can't trade out of is fiction. Finviz returns everything; you filter.",
  },
  {
    label: "Number of raw filters",
    tapeline: "Sector + score + signal + watchlist",
    competitor: "60+ ratios + technical filters",
    note: "Tapeline gives you the synthesised answer. Finviz gives you the raw inputs to compute it yourself.",
  },
  {
    label: "Cheapest paid tier",
    tapeline: "$24.99/mo (Pro, billed annually)",
    competitor: "$24.96/mo (Elite, billed annually)",
    note: "Effectively identical. Tapeline includes the score + sentence + scorecard at the same price.",
  },
];

export default function VsFinvizPage() {
  return (
    <main className="min-h-screen">
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-4 sm:px-6 py-12">
        <p className="eyebrow">Comparison</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          Tapeline vs Finviz — why traders switch.
        </h1>
        <p className="mt-4 text-lg text-muted">
          Finviz Elite is a 25-year-old screener with every filter you can name. Tapeline
          is a 2026-built scanner with one synthesised score per ticker, a sentence
          explaining it, and a public daily scorecard tracking every call we make. Pick
          the second one if you want a tool that does the synthesis for you — and shows
          its work.
        </p>
        <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-up/30 bg-up/5 px-4 py-2 text-sm text-up">
          <span className="text-base">✓</span>
          <span><strong>9 categories</strong> Tapeline wins outright. <strong>3</strong> honest tradeoffs.</span>
        </div>
      </section>

      {/* Where Tapeline wins */}
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
                <th className="px-4 py-3 text-left">Finviz Elite</th>
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

      {/* Honest tradeoffs */}
      <section className="mx-auto max-w-4xl px-4 sm:px-6 pb-12">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Honest tradeoffs
        </h2>
        <p className="mb-3 text-xs text-subtle">
          Where Finviz Elite has an edge — explained so you can pick what matters for
          your workflow.
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

      <MarketingFooter />
    </main>
  );
}
