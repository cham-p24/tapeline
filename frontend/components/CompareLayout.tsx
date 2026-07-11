import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { LandingCta } from "@/components/LandingCta";
import { CompareIndex } from "@/components/CompareIndex";
import { PRICING, usd } from "@/lib/pricing";
import {
  breadcrumbJsonLd,
  compareJsonLd,
  faqJsonLd,
  jsonLdScript,
} from "@/lib/jsonld";

export type CompareRow = {
  label: string;
  tapeline: string;
  competitor: string;
};

export type CompareTradeoff = {
  label: string;
  tapeline: string;
  competitor: string;
  note: string;
};

export type CompareFaq = { q: string; a: string };

export type CompareLayoutProps = {
  /** Display name of the competitor (e.g., "TradingView", "Finviz Elite"). */
  competitor: string;
  /** Competitor canonical homepage URL (used in head-to-head SoftwareApplication schema). */
  competitorUrl: string;
  /** Competitor entry monthly price in USD; omit if annual-only or no published price. */
  competitorPriceMonthly?: number;
  /** Free-form annual-pricing note carried into schema description. */
  competitorAnnualNote?: string;
  /** Slug of this comparison route (e.g., "finviz"). Used to build pageUrl. */
  slug: string;
  /** H1 (e.g., "Tapeline vs TradingView — why traders switch."). */
  heading: string;
  /** Lede paragraph beneath H1. */
  lede: string;
  /** Header copy for the "Where Tapeline wins" table. */
  wins: CompareRow[];
  /** "Honest tradeoffs" rows where the competitor wins. */
  tradeoffs: CompareTradeoff[];
  /** FAQs — also rendered into FAQPage JSON-LD. */
  faq: CompareFaq[];
  /** ISO date the comparison data was last verified. */
  verifiedOn: string;
  /** Optional pre-table eyebrow line; defaults to "Comparison". */
  eyebrow?: string;
  /** Optional CTA link copy override. */
  ctaSecondaryHref?: string;
};

/**
 * Shared layout for /compare/{slug} pages.
 *
 * Every comparison page has the same shape:
 *   1. Eyebrow + H1 + lede + ✓/×  callout
 *   2. "Where Tapeline wins" table (CompareRow[])
 *   3. "Honest tradeoffs" cards (CompareTradeoff[])
 *   4. CTA
 *   5. Visible FAQ (mirrors FAQPage JSON-LD)
 *   6. Verification stamp
 *
 * Pages still own their own metadata (via pageMeta) and the structured-
 * data wiring; this component only renders the body.
 */
export function CompareLayout({
  competitor,
  competitorUrl,
  competitorPriceMonthly,
  competitorAnnualNote,
  slug,
  heading,
  lede,
  wins,
  tradeoffs,
  faq,
  verifiedOn,
  eyebrow = "Comparison",
  ctaSecondaryHref = "/scorecard",
}: CompareLayoutProps) {
  const pageUrl = `https://tapeline.io/compare/${slug}`;
  const headToHead = compareJsonLd({
    competitorName: competitor,
    competitorUrl,
    competitorPriceMonthly,
    competitorAnnualNote,
    pageUrl,
  });
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Compare", url: "https://tapeline.io/compare" },
    { name: `vs ${competitor}`, url: pageUrl },
  ]);

  // Review schema — derived dynamically from the actual win/tradeoff
  // counts on this page so no two compare pages claim the same rating.
  // Cap at 4.8 to stay honest (no self-perfect 5.0). Star variant in
  // SERP is typically +20-40% CTR over plain results — meaningful
  // because compare pages get high commercial-investigation traffic.
  // 2026-05-22: added on top of existing FAQ + breadcrumbs + head-to-
  // head schemas, replicating the same pattern that worked on
  // /best-finviz-alternatives (PR #167).
  const winRatio = wins.length / Math.max(1, wins.length + tradeoffs.length);
  const tapelineRating =
    Math.min(4.8, Math.max(3.5, Math.round(winRatio * 5 * 10) / 10));
  const reviewSchema = {
    "@context": "https://schema.org",
    "@type": "Review",
    itemReviewed: {
      "@type": "SoftwareApplication",
      name: "Tapeline",
      applicationCategory: "FinanceApplication",
      applicationSubCategory: "Stock Scanner",
      operatingSystem: "Web",
      url: "https://tapeline.io",
    },
    reviewRating: {
      "@type": "Rating",
      ratingValue: tapelineRating,
      bestRating: 5,
      worstRating: 1,
    },
    author: {
      "@type": "Organization",
      name: "Tapeline editorial",
      url: "https://tapeline.io/about",
    },
    publisher: {
      "@type": "Organization",
      name: "Tapeline",
      url: "https://tapeline.io",
    },
    datePublished: verifiedOn,
    reviewBody: `Side-by-side comparison of Tapeline against ${competitor}: ${wins.length} categor${wins.length === 1 ? "y" : "ies"} compared and ${tradeoffs.length} honest tradeoff${tradeoffs.length === 1 ? "" : "s"} where ${competitor} is the better fit.`,
    name: `Tapeline vs ${competitor}`,
    url: pageUrl,
  };
  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(faqJsonLd(faq))} />
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(reviewSchema)} />
      {headToHead.map((g, i) => (
        <script key={`compld-${i}`} {...jsonLdScript(g)} />
      ))}
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-4 sm:px-6 py-8">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">{heading}</h1>
        <p className="mt-4 text-lg text-muted">{lede}</p>
        {/* Hype pill removed 2026-06-16 — counting categories Tapeline "wins
            outright" reads as marketing, not honesty (matches the finviz
            reference page). The table below speaks for itself and the
            tradeoffs section names where the competitor wins. */}

        {/* Above-the-fold conversion block. Previously the only signup CTA on
            a compare page sat below the FAQ, so a comparison-shopper who
            skimmed the table and left never saw the offer. showPreview is off
            here because the "Where Tapeline wins" table immediately below is
            the product proof for these pages; the CTA + offer strip is what's
            missing up top. from="compare" message-matches the signup H1. */}
        <LandingCta
          from="compare"
          showPreview={false}
          secondaryLabel="See the scorecard first"
        />
      </section>

      <section className="mx-auto max-w-4xl px-4 sm:px-6 pb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-up">
          Where Tapeline wins
        </h2>
        {/* Polished comparison table — mirrors the /compare/finviz reference:
            fixed column widths, 1px column dividers, theme-aware alternating
            row tint, per-cell min-height + align-top for a consistent row
            rhythm even when one cell wraps, and bare "—" competitor cells
            normalised to "Not available" so an empty cell reads as a
            deliberate "absent here" contrast rather than a data error. */}
        <div className="card overflow-x-auto">
          <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: "32%" }} />
              <col style={{ width: "36%" }} />
              <col style={{ width: "32%" }} />
            </colgroup>
            <thead className="border-b border-border bg-panel/60 text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3 text-left">Feature</th>
                <th className="px-4 py-3 text-left text-accent border-l border-border/40">Tapeline</th>
                <th className="px-4 py-3 text-left border-l border-border/40">{competitor}</th>
              </tr>
            </thead>
            <tbody>
              {wins.map((r, i) => (
                <tr
                  key={r.label}
                  className={"border-b border-border/30 " + (i % 2 === 1 ? "bg-panel/40" : "")}
                >
                  <td className="px-4 py-3 font-medium align-top min-h-[3rem]">{r.label}</td>
                  <td className="px-4 py-3 font-medium text-accent align-top border-l border-border/30 min-h-[3rem]">{r.tapeline}</td>
                  <td className="px-4 py-3 text-muted align-top border-l border-border/30 min-h-[3rem]">
                    {r.competitor === "—" ? "Not available" : r.competitor}
                  </td>
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
          Where {competitor} has an edge — explained so you can pick what matters for your workflow.
        </p>
        <div className="space-y-3">
          {tradeoffs.map((r) => (
            <div key={r.label} className="rounded-lg border border-border bg-panel/40 p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h3 className="font-medium">{r.label}</h3>
                <div className="text-xs text-subtle">
                  {r.competitor} <span className="opacity-50">vs</span> {r.tapeline}
                </div>
              </div>
              <p className="mt-2 text-sm text-muted leading-relaxed">{r.note}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Newsletter mid-funnel capture — comparison-shoppers who haven't
          decided yet but will read a daily Top 10 email. Lower commitment
          than /signup; same conversion bucket via method='newsletter'. */}
      <section className="mx-auto max-w-3xl px-4 sm:px-6 py-6">
        <div className="rounded-xl border border-border bg-panel/40 p-6">
          <NewsletterCapture source="compare" heading="" sub="" />
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-4 sm:px-6 py-8 text-center">
        <h2 className="text-3xl font-bold tracking-tight">Try the live scanner free.</h2>
        <p className="mt-3 text-muted">
          Free forever tier — no card. Pro from {usd(PRICING.pro.monthly)}/mo
          ({usd(PRICING.pro.annual)}/yr), with a 30-day money-back guarantee.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href="/signup?from=compare" className="btn-primary">
            Try the live scanner free — no card →
          </Link>
          <Link href={ctaSecondaryHref} className="btn-ghost">See the scorecard first</Link>
        </div>
        <p className="mt-4 text-xs text-subtle">
          Or read the <Link href="/how-it-works" className="link">methodology</Link>.
        </p>
      </section>

      <section className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
        <h2 className="text-2xl font-semibold tracking-tight">
          Tapeline vs {competitor} — questions
        </h2>
        <div className="mt-6 divide-y divide-border/60">
          {faq.map((item) => (
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
        Comparison data verified {verifiedOn}. Competitor pricing and feature claims sourced from
        their public pages. Spot a mistake?{" "}
        <a href="mailto:support@tapeline.io" className="text-accent hover:underline">Tell us</a> —
        we update within 48 hours.
      </p>

      {/* Internal-linking cluster — graphs every /compare/* page to all
          the others. Per the 2026-05-21 GSC audit, the comparison cluster
          had ~14 pages stuck at "Discovered — currently not indexed"
          because each page was a templated island. Cross-linking
          concentrates crawl budget on the topic-cluster rather than
          treating each page as standalone duplicate content. Also gives
          a human visitor an obvious next step. */}
      <CompareIndex currentSlug={slug} />

      <MarketingFooter />
    </main>
  );
}
