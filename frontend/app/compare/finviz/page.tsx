import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { CompareIndex } from "@/components/CompareIndex";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, compareJsonLd, faqJsonLd, jsonLdScript } from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "Tapeline vs Finviz Elite (2026): Synthesis, Public Formula, Daily Scorecard",
  description:
    "Tapeline vs Finviz Elite — one composite score per ticker, plain-English Why on every row, and a public next-day scorecard, none of which Finviz publishes. 9 categories Tapeline wins, 3 honest tradeoffs.",
  path: "/compare/finviz",
});

// Targets the long-tail SERPs around "is tapeline better than finviz",
// "finviz alternative reddit", "tapeline vs finviz pricing".
const COMPARE_FAQ = [
  {
    q: "Is Tapeline a Finviz alternative?",
    a: "Yes. Tapeline is a 2026-built quantitative scanner that gives you one composite score per US ticker, a plain-English sentence explaining it, and a public scorecard back-checking every call vs SPY — at the same effective price as Finviz Elite ($24.99/mo annual vs $24.96/mo). Finviz remains the better pick if you want raw filters across 60+ technical and fundamental fields and don't want a synthesised answer.",
  },
  {
    q: "How does Tapeline pricing compare to Finviz Elite?",
    a: "Tapeline Pro is $24.99/mo billed annually ($299.99/yr) or $29.99/mo monthly. Premium is $39.99/mo billed annually ($479.99/yr) or $49.99/mo monthly. Finviz Elite is $24.96/mo billed annually or $39.50/mo monthly. Effectively identical at the entry tier, with Tapeline including the score, sentence, and scorecard at the same price.",
  },
  {
    q: "Does Finviz publish its scoring formula?",
    a: "Finviz does not publish a single composite score per ticker. It provides ~60 raw screener fields (P/E, RSI, EMA distance, insider ownership, etc.) and lets you filter against them. Tapeline publishes its 6-factor weighted formula and the exact percentages on /how-it-works.",
  },
  {
    q: "Does Tapeline cover penny stocks like Finviz?",
    a: "Tapeline actively scores the top ~2,500 US tickers by daily dollar-volume from the full liquid US universe — covering everything liquid down to small-caps. Finviz indexes everything including OTC and sub-$1 stocks and you filter manually. If your strategy depends on penny stocks below the liquidity cutoff, Finviz is the better fit.",
  },
  {
    q: "Can I try Tapeline before paying?",
    a: "Yes — 14-day Premium trial, no credit card required, cancel in one click. Free tier (top 20 tickers, 24-hour delayed) stays available indefinitely.",
  },
];

// "Tapeline wins" rows first — the categories that decide which tool earns
// a slot in someone's daily workflow. Tradeoff rows below are reframed: every
// category Finviz "wins" is reframed as a feature-not-bug for our positioning.
//
// Competitor-column copy uses "Not available — <one-liner>" (not bare em-dash)
// per the §5 audit: a lone — reads as a data-dump error, not as deliberate
// "absent here" contrast.
const WINS = [
  {
    label: "One composite score per ticker",
    tapeline: "✓ Six factors, public weights",
    competitor: "Not available — no synthesis at all",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence, every ticker",
    competitor: "Not available — you write your own thesis",
  },
  {
    label: "Public scorecard with receipts",
    tapeline: "✓ Every top-10 back-checked vs SPY next day",
    competitor: "Not available — no track record published",
  },
  {
    label: "Squeeze setup detection",
    tapeline: "✓ BB compression + volume + OBV scored",
    competitor: "Not available — you build it from raw filters",
  },
  {
    label: "Congressional trades feed",
    tapeline: "✓ House + Senate disclosed trades, daily",
    competitor: "Not available — Finviz Elite doesn't track Congressional disclosures",
  },
  {
    label: "Recent insider buys (SEC Form 4)",
    tapeline: "✓ Live SEC Form 4 insider activity across ~2,500 tickers",
    competitor: "Insider screener present, but no curated activity feed",
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
    tapeline: "~2,500 actively scored (top by $-volume) from the full liquid US universe",
    competitor: "9,000+ including OTC + penny stocks",
    note: "Finviz indexes everything including OTC + sub-$1 stocks; you filter manually. Tapeline scores the top ~2,500 by daily dollar-volume — covers everything liquid down to small-caps. Below that, bid-ask spreads make a high score on a $0.20 stock with 80K shares/day non-actionable. The rest of the universe is tracked for watchlist + news + per-ticker pages, just not actively scored.",
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

const VERIFIED_ON = "2026-05-04";

export default function VsFinvizPage() {
  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(faqJsonLd(COMPARE_FAQ))} />
      <script
        {...jsonLdScript(
          breadcrumbJsonLd([
            { name: "Tapeline", url: "https://tapeline.io/" },
            { name: "Compare", url: "https://tapeline.io/compare" },
            { name: "vs Finviz", url: "https://tapeline.io/compare/finviz" },
          ]),
        )}
      />
      {compareJsonLd({
        competitorName: "Finviz",
        competitorUrl: "https://finviz.com",
        competitorPriceMonthly: 39.5,
        competitorAnnualNote: "Elite ~$24.96/mo billed annually; $39.50/mo monthly",
        pageUrl: "https://tapeline.io/compare/finviz",
      }).map((g, i) => (
        <script key={`finvizld-${i}`} {...jsonLdScript(g)} />
      ))}
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-4 sm:px-6 py-8">
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

        {/* Above-the-fold CTA — paid traffic lands here; the in-body trial CTA
            is otherwise only at the very bottom of the comparison. */}
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/signup" className="btn-primary">
            Try Premium free &mdash; 14 days, no card &rarr;
          </Link>
          <Link href="/scorecard" className="btn-ghost">
            See the public scorecard
          </Link>
        </div>
        {/* Hype pill removed 2026-05 — counting categories Tapeline "wins
            outright" reads as marketing not honesty. The table below speaks
            for itself; the tradeoffs section names the places Finviz wins. */}
      </section>

      {/* Where Tapeline wins */}
      <section className="mx-auto max-w-4xl px-4 sm:px-6 pb-8">
        {/* "All prices in USD" used to float top-right next to the section
            heading — looked orphaned, especially because the table has no
            prices itself (pricing is on the tradeoffs section below). Moved
            into the comparison-data-verified footer at the bottom of the
            page, where it belongs alongside the data-provenance note. */}
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-up">
          Where Tapeline wins
        </h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
            {/* Explicit column widths so neither side hogs space on wide
                screens. Feature column 32%, Tapeline 36%, Finviz 32%. */}
            <colgroup>
              <col style={{ width: "32%" }} />
              <col style={{ width: "36%" }} />
              <col style={{ width: "32%" }} />
            </colgroup>
            <thead className="border-b border-border bg-panel/60 text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3 text-left">Feature</th>
                <th className="px-4 py-3 text-left text-accent border-l border-border/40">Tapeline</th>
                <th className="px-4 py-3 text-left border-l border-border/40">Finviz Elite</th>
              </tr>
            </thead>
            <tbody>
              {WINS.map((r, i) => (
                <tr
                  key={r.label}
                  // Alternating row tint — uses bg-panel so it adapts to the
                  // active theme (was bg-panel/40 which was invisible in light
                  // mode after the marketing-nav theme toggle shipped).
                  // Subtle vertical column dividers + a per-row min-height
                  // (via min-h on each cell) keep the rhythm consistent even
                  // when one cell wraps to two lines and others don't.
                  className={
                    "border-b border-border/30 " +
                    (i % 2 === 1 ? "bg-panel/40" : "")
                  }
                >
                  <td className="px-4 py-3 font-medium align-top min-h-[3rem]">{r.label}</td>
                  <td className="px-4 py-3 font-medium text-accent align-top border-l border-border/30 min-h-[3rem]">{r.tapeline}</td>
                  <td className="px-4 py-3 text-muted align-top border-l border-border/30 min-h-[3rem]">{r.competitor}</td>
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

      <section className="mx-auto max-w-3xl px-4 sm:px-6 py-8 text-center">
        <h2 className="text-3xl font-bold tracking-tight">Try Tapeline free for 14 days.</h2>
        <p className="mt-3 text-muted">No credit card. Cancel in one click.</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href="/signup?from=finviz" className="btn-primary">Try Premium free →</Link>
          <Link href="/scorecard" className="btn-ghost">See the scorecard first</Link>
        </div>
        <p className="mt-4 text-xs text-subtle">
          Or read the <Link href="/how-it-works" className="link">methodology</Link>.
        </p>
      </section>

      {/* Visible FAQ — mirrors COMPARE_FAQ above so the FAQPage schema
          reflects on-page content (Google's rich-result requirement). */}
      <section className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
        <h2 className="text-2xl font-semibold tracking-tight">Tapeline vs Finviz — questions</h2>
        <div className="mt-6 divide-y divide-border/60">
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

      <p className="mx-auto max-w-3xl px-4 sm:px-6 pb-12 text-center text-[11px] text-subtle">
        Comparison data verified {VERIFIED_ON}. All prices in USD. Competitor pricing and feature claims sourced from
        their public pages. Spot a mistake?{" "}
        <a href="mailto:support@tapeline.io" className="text-accent hover:underline">Tell us</a> — we
        update within 48 hours.
      </p>

      <CompareIndex currentSlug="finviz" />
      <MarketingFooter />
    </main>
  );
}
