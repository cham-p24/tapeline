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
import { PRICING, usd, usdCompact } from "@/lib/pricing";
import { TRIAL_DAYS } from "@/lib/trial";
import { PRICE_FRESHNESS_SENTENCE, SCORE_CADENCE_SENTENCE } from "@/lib/freshness";

export const metadata = pageMeta({
  title: "Tapeline Press Kit — Logos, Fact Sheet, Founder Bio",
  description:
    "Tapeline media resources: brand logos, factual one-paragraph and one-sentence descriptions, founder bio, screenshot kit, and direct press contact (press@tapeline.io).",
  path: "/press",
});

const LAST_UPDATED = "2026-08-24";
const LAST_UPDATED_DISPLAY = "August 24, 2026";

const FACT_SHEET = [
  { label: "Company",         value: "Tapeline (tapeline.io)" },
  { label: "Founder",         value: "Christian Piyatilaka (solo founder)" },
  { label: "Founded",         value: "2025 (engine), 2026 (public launch)" },
  { label: "Headquarters",    value: "Melbourne, Victoria, Australia" },
  { label: "Funding",         value: "Bootstrapped — no external investment" },
  // Derived from lib/pricing.ts (the sitewide pricing source of truth) so the
  // press kit can never quote a price checkout doesn't charge.
  {
    label: "Pricing",
    value:
      `Free · Pro ${usdCompact(PRICING.pro.annual)}/yr (or ${usd(PRICING.pro.monthly)}/mo) · ` +
      `Premium ${usdCompact(PRICING.premium.annual)}/yr (or ${usd(PRICING.premium.monthly)}/mo) — annual billing is the default`,
  },
  // "Premium trial", never "Free trial": the trial is the one thing that takes a card,
  // and its length comes from lib/trial.ts so this line cannot say two numbers at once again.
  { label: "Premium trial",   value: `${TRIAL_DAYS}-day Premium; card required, $0 charged today, first charge on day ${TRIAL_DAYS}` },
  { label: "Universe scored", value: "About 11,500 US-listed stocks and ETFs (an unfiltered scan returned 11,501 on 13 September 2026), plus about 100 crypto pairs scored separately from daily closes, which can be several days old" },
  // Measured 14 Sep 2026 (integrity wave): vendor prices ~15 min delayed,
  // worker passes about 60 s apart since #843 (70-74 s before it), scores
  // change about once a day.
  { label: "Update cadence",  value: `${PRICE_FRESHNESS_SENTENCE} ${SCORE_CADENCE_SENTENCE}` },
  { label: "Data categories", value: "Market data (prices delayed about 15 minutes), fundamentals, macro indicators, SEC filings, news" },
  { label: "Integrations",    value: "Public MCP server for AI assistants (tapeline.io/mcp) · CSV export · API (tapeline.io/developers)" },
  { label: "Press contact",   value: "press@tapeline.io" },
  { label: "Last updated",    value: LAST_UPDATED_DISPLAY },
];

const ONE_LINER =
  "Tapeline is a quantitative stock scanner that names the six factors behind its score and back-checks each recorded daily top-10 pick against the next-day SPY-relative move.";

// Prices interpolate from lib/pricing.ts so a future reprice can't strand a
// stale figure in the most-copied paragraph on the site.
const ONE_PARAGRAPH = `Tapeline is a quantitative stock scanner for active retail traders, built on the principle that the methodology and the track record should both be public. Every ticker in the scored universe (about 11,500 US-listed stocks and ETFs) gets one 0-100 composite score blended from six named factors — Trend, Relative Strength, Fundamentals, Smart Money, Macro, and Momentum, weighted most toward Trend and Relative Strength and least toward Momentum — recalculated on each worker pass during US market hours over prices delayed about 15 minutes, though most inputs are daily readings, so a score usually changes about once a day. Each recorded daily top 10 is published to a public scorecard (open to everyone 7 days after the session) and back-checked against SPY the next session. Entries are not re-ranked or deleted. We have corrected recorded values twice, and said so: prices on 25 August 2026, and scores from 18 May to 12 June capped on 15 June 2026. Tapeline is bootstrapped, launched in 2026, and competes with Finviz, Zacks, WallStreetZen, TradingView, Trade Ideas, and Koyfin, priced annual-first at Pro ${usdCompact(PRICING.pro.annual)}/yr and Premium ${usdCompact(PRICING.premium.annual)}/yr.`;

const PULL_QUOTES = [
  {
    quote:
      "We name the six factors and publish a per-pick scorecard — it's not a mystery black box. The moat is the data spine plus that public scorecard back-checking every call we make.",
    attribution: "Tapeline founder, on the transparency moat",
  },
  {
    quote:
      "Newsletter shops have known for 30 years that hiding losers is the easiest way to look better than you are. We publish each recorded daily top-10 pick regardless of how it moved: subscribers see it the next day, everyone else 7 days after the session.",
    attribution: "Tapeline founder, on why the scorecard is unfiltered",
  },
  {
    quote:
      "Six descriptive labels, no buy-or-sell language. We tell you what the data says — you decide what to do with it.",
    attribution: "Tapeline founder, on descriptive vs prescriptive scoring",
  },
];

/**
 * Downloadable brand files. Everything here is a real file in /public (or a
 * live image route) — no dead links, no "email us for the logo" for the
 * basics. The PNGs regenerate reproducibly via
 * `node scripts/make-press-assets.mjs` from the favicon.svg geometry.
 */
const BRAND_ASSETS = [
  {
    label: "Logo (SVG, vector)",
    href: "/favicon.svg",
    note: "Canonical mark; scales to any size",
    download: "tapeline-logo.svg",
  },
  {
    label: "Logo 1024×1024 (PNG)",
    href: "/press/tapeline-logo-1024.png",
    note: "Transparent rounded corners",
  },
  {
    label: "Logo 512×512 (PNG)",
    href: "/press/tapeline-logo-512.png",
    note: "Transparent rounded corners",
  },
  {
    label: "Logo tile 240 (PNG, @2x — 480×480)",
    href: "/press/tapeline-logo-240.png",
    note: "Directory / launch-listing tile",
  },
  {
    label: "Gallery banner 1270×760 (PNG)",
    href: "/press/tapeline-gallery-1270x760.png",
    note: "Logo + wordmark + descriptor, for review-site galleries",
  },
  {
    label: "Social card 1200×630 (PNG)",
    href: "/opengraph-image",
    note: "The sitewide OpenGraph card",
    download: "tapeline-og.png",
  },
];

/**
 * Pre-captured product screenshots — retina captures (1270×760 @2x, so
 * 2540×1520 actual pixels) of the four launch surfaces, committed 2026-08.
 */
const SCREENSHOT_FILES = [
  { label: "Scanner (home)", href: "/press/tapeline-scanner.png" },
  { label: "Public scorecard", href: "/press/tapeline-scorecard.png" },
  { label: "Per-ticker page", href: "/press/tapeline-ticker.png" },
  { label: "Verify-a-pick page", href: "/press/tapeline-verify.png" },
];

const SCREENSHOTS = [
  {
    label: "Scanner",
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
    desc: "The six named scoring factors, the ordering of their weights, and signal-label definitions.",
    href: "/how-it-works",
  },
  {
    label: "Public scorecard",
    desc: "Dated record of each daily top-10 pick with its next-session return vs SPY; losses kept, corrections dated.",
    href: "/scorecard",
  },
];

// Founder Person schema — teaches the Knowledge Graph that the human
// "Christian Piyatilaka" is the founder of the organisation "Tapeline".
// Helps two SERP problems at once:
//   1. The brand-query problem (positions Tapeline as a company with a
//      named founder, not a generic word).
//   2. The founder-discovery problem (if a journalist or investor
//      searches "Christian Piyatilaka", the result links them to
//      Tapeline rather than to unrelated namesakes).
const FOUNDER_PERSON_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "Person",
  name: "Christian Piyatilaka",
  jobTitle: "Founder",
  worksFor: {
    "@type": "Organization",
    name: "Tapeline",
    url: "https://tapeline.io",
  },
  knowsAbout: [
    "Quantitative trading",
    "Stock scanners",
    "US equities",
    "Software engineering",
    "Financial technology",
    "Retail trading",
  ],
  sameAs: [
    "https://x.com/tapeline_io",
    "https://github.com/cham-p24",
  ],
};

export default function PressPage() {
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Press", url: "https://tapeline.io/press" },
  ]);

  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(FOUNDER_PERSON_JSON_LD)} />
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

        {/* Brand assets — real downloadable files served from /public/press. */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">Brand assets</h2>
          <p className="mt-3 text-sm text-muted">
            The Tapeline mark as vector SVG and PNG at three sizes, plus a
            gallery banner and the social card. The tile ground is #0a0a0a and
            reads correctly on light or dark backgrounds as-is.
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {BRAND_ASSETS.map((a) => (
              <a
                key={a.href}
                href={a.href}
                download={a.download ?? true}
                className="rounded-lg border border-border bg-panel/40 px-4 py-3 hover:border-border2 hover:bg-panel/60 transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{a.label}</span>
                  <span className="shrink-0 text-xs text-subtle">Download →</span>
                </div>
                <p className="mt-1 text-xs text-muted">{a.note}</p>
              </a>
            ))}
          </div>
          <p className="mt-3 text-xs text-subtle">
            Need a size or format not listed?{" "}
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
            Pre-captured retina screenshots (1270×760 @2x) of the four core
            surfaces — download and use directly, credit Tapeline.io.
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {SCREENSHOT_FILES.map((s) => (
              <a
                key={s.href}
                href={s.href}
                download
                className="flex items-center justify-between gap-3 rounded-lg border border-border bg-panel/40 px-4 py-3 hover:border-border2 hover:bg-panel/60 transition-colors"
              >
                <span className="font-medium">{s.label}</span>
                <span className="shrink-0 text-xs text-subtle">PNG →</span>
              </a>
            ))}
          </div>
          <p className="mt-5 text-sm text-muted">
            Prefer a fresh capture? Direct links to the live screens — open,
            screenshot, credit Tapeline.io.
          </p>
          <div className="mt-4 space-y-3">
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

        {/* Founder bio — Person schema-eligible and named so the Knowledge
            Graph picks up the founder ↔ company link. */}
        <section className="mt-12 rounded-2xl border border-border bg-panel/40 p-6 sm:p-8">
          <h2 className="text-xl font-bold tracking-tight">Founder bio</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            <strong className="text-fg">Christian Piyatilaka</strong> is the
            solo founder of Tapeline. Based in Melbourne, Australia. Software
            engineer + active retail trader; built the underlying scoring
            engine in 2025 as a personal trading bot before opening it up as
            a public SaaS in 2026.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            The same 6-factor scoring engine that powers tapeline.io continues
            to run as a personal trading system in production — including
            paper-trading via Alpaca against the same signals shown publicly
            on the scorecard. Tapeline is the public version of that work,
            rebuilt for traders who want one number and one sentence per
            ticker rather than 60 raw filter fields and a blank stare.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Available for podcast and interview requests via{" "}
            <a href="mailto:press@tapeline.io" className="text-accent hover:underline">
              press@tapeline.io
            </a>
            {" "}— usually returns within one business day. Topics most
            comfortable speaking to: transparent quantitative scoring,
            public-track-record accountability, building SaaS solo, retail
            trader workflows, and why the 'AI stock picker' category is
            mostly opaque ML black boxes.
          </p>
          <p className="mt-4 text-xs text-subtle">
            Headshot and detailed prior-background CV available on request.
            Public profiles:{" "}
            <a href="https://x.com/tapeline_io" target="_blank" rel="noopener" className="text-accent hover:underline">X / tapeline_io</a>
            {" · "}
            <a href="https://github.com/cham-p24" target="_blank" rel="noopener" className="text-accent hover:underline">GitHub / cham-p24</a>
            .
          </p>
        </section>

        {/* What Tapeline is NOT — common journalist due-diligence questions
            answered up-front so the legal/regulatory posture is clear and
            doesn't surprise anyone post-publication. */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">What Tapeline is NOT</h2>
          <p className="mt-3 text-sm text-muted">
            For journalist due-diligence and to head off common
            misinterpretations:
          </p>
          <ul className="mt-5 space-y-3 text-sm text-muted leading-relaxed">
            <li className="rounded-lg border border-border/60 bg-panel/30 p-4">
              <strong className="text-fg">Not a registered investment adviser.</strong>{" "}
              Tapeline is a research tool that publishes descriptive analytics
              ("CONSTRUCTIVE", "STRONG SETUP") — not prescriptive recommendations
              ("BUY NOW"). This is the publisher&rsquo;s exemption posture from
              investment-adviser registration in the US, AU, and EU.
            </li>
            <li className="rounded-lg border border-border/60 bg-panel/30 p-4">
              <strong className="text-fg">Not a broker, custodian, or wallet.</strong>{" "}
              Tapeline does not hold client funds, execute trades, or accept
              custody of securities. Scores are displayed; users trade
              elsewhere.
            </li>
            <li className="rounded-lg border border-border/60 bg-panel/30 p-4">
              <strong className="text-fg">Not an AI black box.</strong> The
              composite score uses six named factors documented
              at <Link href="/how-it-works" className="text-accent hover:underline">/how-it-works</Link>,
              with each factor&apos;s contribution shown on every ticker.
              No proprietary ML rerank step is applied
              between the composite and the displayed number.
            </li>
            <li className="rounded-lg border border-border/60 bg-panel/30 p-4">
              <strong className="text-fg">Not options.</strong>{" "}
              About 11,500 US-listed stocks and ETFs are scored. About 100
              crypto pairs are scored in a separate list from daily closes
              (refreshed about once a day, and several days old when the daily
              pass misses a pair), from four of the six factors, and are never
              ranked against stocks.
            </li>
          </ul>
        </section>

        {/* Recent press — empty state structure ready for the first
            coverage. When the first piece publishes, replace the empty
            state with a Press[] array and a Link list. */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">Recent press</h2>
          <p className="mt-3 text-sm text-muted">
            Coverage, interviews, and mentions. Tapeline launched publicly
            in 2026 — be the first to cover it.
          </p>
          <div className="mt-5 rounded-lg border border-dashed border-border/60 bg-panel/20 p-6 text-center">
            <p className="text-sm text-muted">
              First publication slot reserved. Email{" "}
              <a href="mailto:press@tapeline.io" className="text-accent hover:underline">
                press@tapeline.io
              </a>{" "}
              with your outlet, deadline, and angle — we&rsquo;ll send a
              founder quote, custom data pull, or full embargo set
              depending on what your piece needs.
            </p>
          </div>
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
