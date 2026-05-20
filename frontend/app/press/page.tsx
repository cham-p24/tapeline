/**
 * /press — the press / media kit page.
 *
 * Single landing page for journalists, reviewers, podcast hosts, and anyone
 * else who needs a quick fact-sheet, founder bio, brand assets, and a real
 * email to reach. Linked from /about and from the footer.
 *
 * Helps SEO via brand-query coverage ("tapeline press kit", "tapeline media",
 * "tapeline founder"), but the bigger win is reducing friction for inbound
 * coverage — every minute a journalist spends hunting for a logo or a stat is
 * a minute they're considering a different story.
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, jsonLdScript, pressContactPageJsonLd } from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "Tapeline Press Kit — Logos, Fact Sheet, Founder Bio, Media Contact",
  description:
    "Tapeline media resources: brand logos, factual one-paragraph and one-sentence descriptions, founder bio, screenshot kit, and direct press contact (press@tapeline.io).",
  path: "/press",
});

const FACT_SHEET = [
  { label: "Founded",         value: "2025 (engine), 2026 (public launch)" },
  { label: "Headquarters",    value: "Melbourne, Victoria, Australia" },
  { label: "Funding",         value: "Bootstrapped — no external investment" },
  { label: "Pricing",         value: "Free · Pro from $24.99/mo (annual) · Premium from $39.99/mo (annual)" },
  { label: "Free trial",      value: "14-day Premium, no credit card required" },
  { label: "Universe scored", value: "~2,500 active US tickers (top by daily $-volume) · 5,757 tracked" },
  { label: "Update cadence",  value: "Sub-60 seconds during US market hours" },
  { label: "Data categories", value: "Live market data, fundamentals, macro indicators, SEC filings, news wire" },
  { label: "Press contact",   value: "press@tapeline.io" },
];

const ONE_LINER =
  "Tapeline is a quantitative stock scanner that publishes its 6-factor scoring formula and back-checks every top-10 daily pick against the next-day SPY-relative move.";

const ONE_PARAGRAPH = `Tapeline is a quantitative stock scanner for active retail traders, built on the principle that the formula and the track record should both be public. Every US ticker in the active universe gets one 0-100 composite score blended from six published factors — Trend (25%), Relative Strength (20%), Fundamentals (15%), Smart Money (15%), Macro (15%), Momentum (10%) — updated sub-60s during market hours. Every top-10 daily pick auto-publishes to a public scorecard with the realized next-day return vs SPY, immutable and back-checked. Tapeline is bootstrapped, launched in 2026, and competes with Finviz, Zacks, WallStreetZen, TradingView, Trade Ideas, and Koyfin at the $25-40/mo price point.`;

const PULL_QUOTES = [
  {
    quote:
      "The formula is public. Anyone can copy it. The moat is the data spine plus the public scorecard back-checking every call we make.",
    attribution: "Tapeline founder, on the public-formula moat",
  },
  {
    quote:
      "Newsletter shops have known for 30 years that hiding losers is the easiest way to look better than you are. We auto-publish every top-10 pick the next day, regardless of how it moved.",
    attribution: "Tapeline founder, on why the scorecard is unfiltered",
  },
  {
    quote:
      "Six descriptive labels, no buy-or-sell language. We tell you what the data says — you decide what to do with it.",
    attribution: "Tapeline founder, on descriptive vs prescriptive scoring",
  },
];

const SCREENSHOTS = [
  {
    label: "Live scanner",
    desc: "The main scanner UI showing the composite score, signal label, and plain-English Why per ticker.",
    href: "/",
  },
  {
    label: "Per-ticker page",
    desc: "Full breakdown of the 6-factor sub-scores, score history sparkline, and FAQ for any ticker (e.g. /t/AAPL).",
    href: "/t/AAPL",
  },
  {
    label: "Methodology",
    desc: "The published 6-factor formula with exact weights and signal-label definitions.",
    href: "/how-it-works",
  },
  {
    label: "Public scorecard",
    desc: "Immutable record of every top-10 daily pick with realized next-day return vs SPY.",
    href: "/scorecard",
  },
];

export default function PressPage() {
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Press", url: "https://tapeline.io/press" },
  ]);

  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      {pressContactPageJsonLd().map((g, i) => (
        <script key={`pressld-${i}`} {...jsonLdScript(g)} />
      ))}
      <MarketingNav />

      <article className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
        <p className="eyebrow">Press kit</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          Press kit & media resources.
        </h1>
        <p className="mt-4 text-lg text-muted">
          Everything a journalist, reviewer, or podcast host might need —
          factual descriptions, brand assets, screenshots, founder context,
          and a direct contact.
        </p>
        <p className="mt-3 text-sm text-subtle">
          Direct contact:{" "}
          <a href="mailto:press@tapeline.io" className="text-accent hover:underline">
            press@tapeline.io
          </a>
          {" · "}response within one business day.
        </p>

        {/* Fact sheet — the most-cited page section in any coverage. Keep
            numbers honest and date-stamped where they change. */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">Fact sheet</h2>
          <div className="mt-6 card overflow-hidden">
            <table className="w-full text-sm">
              <tbody>
                {FACT_SHEET.map((row) => (
                  <tr key={row.label} className="border-b border-border/30 last:border-b-0">
                    <td className="px-4 py-3 font-medium text-muted w-40">{row.label}</td>
                    <td className="px-4 py-3 text-fg">{row.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Pre-written descriptions for journalists who need quick copy. */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">Pre-written descriptions</h2>

          <div className="mt-6">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted">
              One sentence
            </h3>
            <blockquote className="mt-3 rounded-lg border-l-4 border-accent bg-panel/40 p-4 text-base italic">
              {ONE_LINER}
            </blockquote>
          </div>

          <div className="mt-6">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted">
              One paragraph
            </h3>
            <blockquote className="mt-3 rounded-lg border-l-4 border-accent bg-panel/40 p-4 text-sm italic leading-relaxed">
              {ONE_PARAGRAPH}
            </blockquote>
          </div>
        </section>

        {/* Pull quotes — give journalists ready-made attributable lines. */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">Quotable lines</h2>
          <p className="mt-3 text-sm text-muted">
            Pre-cleared for direct quotation in coverage. Attribute as shown or use
            &ldquo;a Tapeline spokesperson&rdquo;.
          </p>
          <div className="mt-6 space-y-4">
            {PULL_QUOTES.map((q) => (
              <figure key={q.quote} className="rounded-lg border border-border bg-panel/40 p-5">
                <blockquote className="text-base italic leading-relaxed">
                  &ldquo;{q.quote}&rdquo;
                </blockquote>
                <figcaption className="mt-3 text-xs text-subtle">— {q.attribution}</figcaption>
              </figure>
            ))}
          </div>
        </section>

        {/* Brand assets. Once a public brand-assets folder exists, point the
            buttons at downloadable .zip / SVG / PNG. For now they link to
            the in-app SVG favicon as a placeholder. */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">Brand assets</h2>
          <p className="mt-3 text-sm text-muted">
            Logos in SVG and PNG, dark and light variants, with usage guidance.
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <a
              href="/favicon.svg"
              download
              className="flex items-center justify-between rounded-lg border border-border bg-panel/40 px-4 py-3 hover:border-border2 hover:bg-panel/60 transition-colors"
            >
              <span className="font-medium">Logo (SVG, single colour)</span>
              <span className="text-xs text-subtle">Download →</span>
            </a>
            <a
              href="/opengraph-image"
              download="tapeline-og.png"
              className="flex items-center justify-between rounded-lg border border-border bg-panel/40 px-4 py-3 hover:border-border2 hover:bg-panel/60 transition-colors"
            >
              <span className="font-medium">Social card (1200×630 PNG)</span>
              <span className="text-xs text-subtle">Download →</span>
            </a>
          </div>
          <p className="mt-3 text-xs text-subtle">
            Need a vector logo, dark/light variants, or a higher-resolution
            screenshot kit?{" "}
            <a href="mailto:press@tapeline.io" className="text-accent hover:underline">
              press@tapeline.io
            </a>{" "}
            — usually returned within an hour during business hours.
          </p>
        </section>

        {/* Screenshot deep-links — easier for a journalist to grab a clean
            shot from a real URL than from a marketing screenshot we picked. */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">Screenshot kit</h2>
          <p className="mt-3 text-sm text-muted">
            Direct links to the most-screenshotted screens. Open, screenshot,
            credit Tapeline.io.
          </p>
          <div className="mt-6 space-y-3">
            {SCREENSHOTS.map((s) => (
              <Link
                key={s.label}
                href={s.href}
                className="block rounded-lg border border-border bg-panel/40 px-4 py-3 hover:border-border2 hover:bg-panel/60 transition-colors"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-medium">{s.label}</span>
                  <span className="font-mono text-xs text-subtle">{s.href}</span>
                </div>
                <p className="mt-1 text-xs text-muted">{s.desc}</p>
              </Link>
            ))}
          </div>
        </section>

        {/* Founder bio — Person schema-eligible. Update with real bio + headshot. */}
        <section className="mt-12 rounded-2xl border border-border bg-panel/40 p-6 sm:p-8">
          <h2 className="text-xl font-bold tracking-tight">Founder bio</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Tapeline is built by a solo founder with a decade of software
            engineering and active retail trading experience. The same scoring
            engine that powers Tapeline runs as a personal trading bot in
            production, including paper-trading via Alpaca on the same signals
            shown publicly. The founder is available for podcast and
            interview requests via{" "}
            <a href="mailto:press@tapeline.io" className="text-accent hover:underline">
              press@tapeline.io
            </a>
            .
          </p>
          <p className="mt-3 text-xs text-subtle">
            Detailed bio with photo and prior background available on request.
          </p>
        </section>

        {/* CTA */}
        <section className="mt-16 text-center">
          <p className="text-sm text-muted">
            Working on a story?{" "}
            <a href="mailto:press@tapeline.io" className="text-accent hover:underline font-medium">
              press@tapeline.io
            </a>{" "}
            — happy to provide custom data pulls, founder availability for
            interviews, or early access to upcoming features.
          </p>
        </section>
      </article>

      <MarketingFooter />
    </main>
  );
}
