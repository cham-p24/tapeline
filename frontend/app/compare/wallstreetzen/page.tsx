import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, compareJsonLd, faqJsonLd, jsonLdScript } from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "Tapeline vs WallStreetZen (2026): Public Weights, Live Data, Per-Pick Scorecard",
  description:
    "Tapeline vs WallStreetZen Premium — 6-factor model with PUBLISHED weights, sub-60s live data, per-pick public scorecard, vs WallStreetZen's 115-factor proprietary Zen Ratings. Honest comparison.",
  path: "/compare/wallstreetzen",
});

const COMPARE_FAQ = [
  {
    q: "Is Tapeline a WallStreetZen alternative?",
    a: "Yes. Both score US stocks, but Tapeline publishes the exact 6-factor formula and weights, recomputes the score sub-60s, and back-checks every top-10 pick publicly vs SPY the next day. WallStreetZen's Zen Ratings combine 115 factors at undisclosed weights and update less frequently.",
  },
  {
    q: "How is the Tapeline Score different from WallStreetZen Zen Ratings?",
    a: "Zen Ratings is a multi-factor proprietary score across 115 inputs, with the underlying weighting derived from documentation rather than published. Tapeline publishes the exact 6 factors and percentages: Trend (25%), Relative Strength (20%), Fundamentals (15%), Smart Money (15%), Macro (15%), Momentum (10%). Fewer factors, fully transparent weights.",
  },
  {
    q: "How do prices compare?",
    a: "Tapeline Pro is $24.99/mo billed annually; Premium is $39.99/mo billed annually. WallStreetZen Premium is approximately $24.50/mo billed annually. Effectively identical entry pricing, with Tapeline including the public scorecard, plain-English Why on every row, and Congressional + insider activity feeds (Premium tier).",
  },
  {
    q: "Does WallStreetZen publish a per-pick track record?",
    a: "WallStreetZen publishes aggregate Zen Ratings performance metrics, but does not auto-publish every individual rating with the original thesis preserved and back-checked next-day. Tapeline auto-publishes every top-10 daily pick at /scorecard with realized 1-day return vs SPY.",
  },
  {
    q: "Should I use both?",
    a: "WallStreetZen has stronger investor-education content and broader analyst commentary; Tapeline has the live multi-factor synthesis and the public scorecard. The 14-day no-credit-card Tapeline trial lets you compare directly against your existing WallStreetZen workflow.",
  },
];

const WINS = [
  {
    label: "Factor weights — fully public",
    tapeline: "✓ Six factors, exact percentages on /how-it-works",
    competitor: "115 factors, weights derived from docs (not published)",
  },
  {
    label: "Live data refresh",
    tapeline: "Sub-60s — score reacts intraday",
    competitor: "Daily rebuild — Tuesday's score Wednesday morning",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Auto-generated sentence on every ticker",
    competitor: "Strength bars per factor, no narrative",
  },
  {
    label: "Per-pick scorecard with thesis preserved",
    tapeline: "✓ Every top-10 logged with original Why + next-day SPY-relative move",
    competitor: "Aggregate A/B/C grade returns since 2003 (no per-pick visibility)",
  },
  {
    label: "Squeeze / volatility setup detection",
    tapeline: "✓ Bollinger compression + volume + OBV scored",
    competitor: "—",
  },
  {
    label: "Congressional trades feed",
    tapeline: "✓ House + Senate, daily disclosure sync",
    competitor: "—",
  },
  {
    label: "Recent insider buys (SEC Form 4)",
    tapeline: "✓ Live SEC Form 4 insider activity across ~2,500 tickers",
    competitor: "—",
  },
  {
    label: "Smart watchlist alerts",
    tapeline: "✓ Score-change alerts via email + Telegram + browser push",
    competitor: "Email digest only",
  },
  {
    label: "Active-trader timescale",
    tapeline: "✓ Built for sub-week decisions (live tick + intraday Why)",
    competitor: "Intentionally long-term: \"buy and hold for the next 5+ years\"",
  },
  {
    label: "Try without a card",
    tapeline: "✓ 14-day full Premium trial, no card",
    competitor: "Annual subscription only on Premium",
  },
  {
    label: "Macro regime + sector heatmap in same tool",
    tapeline: "✓ Live VIX / DXY / 10Y from FRED, breadth + sector rotation",
    competitor: "—",
  },
];

const TRADEOFFS = [
  {
    label: "Free tier strength",
    tapeline: "20 tickers, 24-hour delayed, watchlist of 5",
    competitor: "4,600+ stocks with free Zen Ratings — genuinely strong",
    note: "WallStreetZen's free tier is the strongest in the category. Tapeline's free tier is hard-capped on purpose so the trial-to-paid transition is meaningful — same product, narrower window.",
  },
  {
    label: "Cheapest paid tier",
    tapeline: "$24.99/mo (Pro, billed annually)",
    competitor: "$19.50/mo (Premium, billed annually)",
    note: "WallStreetZen is ~$5/mo cheaper. You're getting fewer features for the saving — Tapeline includes the live tick, scorecard, and squeeze module at the same price band.",
  },
  {
    label: "Brand history",
    tapeline: "Pre-launch (under 12 months)",
    competitor: "5+ years of published Zen Ratings performance",
    note: "WallStreetZen has the longer track record. Tapeline's response is to publish per-pick receipts from day one rather than wait 5 years to claim aggregate performance.",
  },
  {
    label: "Universe size",
    tapeline: "~2,500 actively scored (top by $-volume) · 5,757 tracked",
    competitor: "4,600+ US stocks rated daily",
    note: "WallStreetZen rates more names. Tapeline scores the top ~2,500 by daily dollar-volume (price × volume) — covers everything liquid down to small-caps. Below that, bid-ask spreads make 'actionable' a fiction; a strong rating on a $0.20 stock you can't get out of cleanly is theatre. The other ~3,200 names in our universe table are tracked for watchlist + news + per-ticker pages, just not actively scored.",
  },
];

// Last-verified stamp — bump when you re-check competitor pricing/features.
// Honest dating means the page reads as researched, not marketing copy.
const VERIFIED_ON = "2026-05-04";

export default function VsWallStreetZenPage() {
  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(faqJsonLd(COMPARE_FAQ))} />
      <script
        {...jsonLdScript(
          breadcrumbJsonLd([
            { name: "Tapeline", url: "https://tapeline.io/" },
            { name: "Compare", url: "https://tapeline.io/compare" },
            { name: "vs WallStreetZen", url: "https://tapeline.io/compare/wallstreetzen" },
          ]),
        )}
      />
      {compareJsonLd({
        competitorName: "WallStreetZen",
        competitorUrl: "https://www.wallstreetzen.com",
        competitorPriceMonthly: 24.5,
        competitorAnnualNote: "Premium ~$24.50/mo billed annually",
        pageUrl: "https://tapeline.io/compare/wallstreetzen",
      }).map((g, i) => (
        <script key={`wszld-${i}`} {...jsonLdScript(g)} />
      ))}
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-4 sm:px-6 py-12">
        <p className="eyebrow">Comparison</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          Tapeline vs WallStreetZen — why active traders switch.
        </h1>
        <p className="mt-4 text-lg text-muted">
          WallStreetZen built a strong long-term-investor product around their 115-factor
          Zen Ratings — daily-rebuilt letter grades, no live tick. Tapeline publishes the
          exact 6-factor weights, recomputes the score sub-60s, and pairs every top-10
          with a per-pick public scorecard. If you trade on a sub-week timescale,
          Tapeline is built for you. If you buy-and-hold for 5+ years and the strong
          free tier is enough, WallStreetZen is the right choice.
        </p>
        <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-up/30 bg-up/5 px-4 py-2 text-sm text-up">
          <span className="text-base">✓</span>
          <span><strong>11 categories</strong> Tapeline wins outright. <strong>4</strong> honest tradeoffs.</span>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-4 sm:px-6 pb-8">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-up">
            Where Tapeline wins
          </h2>
          <span className="text-[10px] uppercase tracking-wider text-subtle">All prices in USD</span>
        </div>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3 text-left">Feature</th>
                <th className="px-4 py-3 text-left text-accent">Tapeline</th>
                <th className="px-4 py-3 text-left">WallStreetZen Premium</th>
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
          Where WallStreetZen has a genuine edge — explained so you can decide what matters for your workflow.
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
        <p className="mt-3 text-muted">
          Free tier is hard-capped on purpose (20 tickers, 24h delayed). Start the trial to see the live product properly. No card.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href="/signup" className="btn-primary">Try Premium free →</Link>
          <Link href="/scorecard" className="btn-ghost">See the scorecard first</Link>
        </div>
        <p className="mt-4 text-xs text-subtle">
          Or read the <Link href="/how-it-works" className="link">methodology</Link>.
        </p>
      </section>

      {/* Visible FAQ — mirrors COMPARE_FAQ JSON-LD. */}
      <section className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
        <h2 className="text-2xl font-semibold tracking-tight">Tapeline vs WallStreetZen — questions</h2>
        <div className="mt-6 divide-y divide-border border-y border-border">
          {COMPARE_FAQ.map((item) => (
            <details key={item.q} className="group py-4">
              <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
                <h3 className="text-sm font-medium">{item.q}</h3>
                <span className="text-muted transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="mt-3 text-sm text-muted leading-relaxed">{item.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* Honesty stamp — re-verify quarterly */}
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
