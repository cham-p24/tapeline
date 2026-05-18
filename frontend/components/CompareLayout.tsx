import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
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
  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(faqJsonLd(faq))} />
      <script {...jsonLdScript(breadcrumbs)} />
      {headToHead.map((g, i) => (
        <script key={`compld-${i}`} {...jsonLdScript(g)} />
      ))}
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-4 sm:px-6 py-12">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">{heading}</h1>
        <p className="mt-4 text-lg text-muted">{lede}</p>
        <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-up/30 bg-up/5 px-4 py-2 text-sm text-up">
          <span className="text-base">✓</span>
          <span>
            <strong>{wins.length} categories</strong> Tapeline wins outright.{" "}
            <strong>{tradeoffs.length}</strong> honest tradeoff{tradeoffs.length === 1 ? "" : "s"}.
          </span>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-4 sm:px-6 pb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-up">
          Where Tapeline wins
        </h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-panel text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3 text-left">Feature</th>
                <th className="px-4 py-3 text-left text-accent">Tapeline</th>
                <th className="px-4 py-3 text-left">{competitor}</th>
              </tr>
            </thead>
            <tbody>
              {wins.map((r) => (
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

      <section className="mx-auto max-w-3xl px-4 sm:px-6 py-12 text-center">
        <h2 className="text-3xl font-bold tracking-tight">Try Tapeline free for 14 days.</h2>
        <p className="mt-3 text-muted">No credit card. Cancel in one click.</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href="/signup" className="btn-primary">Try Premium free →</Link>
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
        <div className="mt-6 divide-y divide-border border-y border-border">
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

      <MarketingFooter />
    </main>
  );
}
