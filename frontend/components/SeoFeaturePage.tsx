/**
 * Shared shell for the public feature landing pages — squeeze, congressional
 * trades, insider buys, heatmap, regime. Each of these is a high-intent
 * keyword cluster Tapeline targets with its own /feature-name URL.
 *
 * Why a shared component rather than 5 copies:
 *   - The chrome (hero, FAQ accordion, methodology block, CTA, sister-feature
 *     nav) is identical across all 5; only the data section + copy varies.
 *   - One place to update the CTA wording, the FAQ rendering, the sister-
 *     features link list when new features ship.
 *   - Each individual `page.tsx` stays focused on its data block + copy —
 *     no boilerplate drift between pages.
 *
 * Each feature page renders <SeoFeaturePage> with feature-specific props
 * and slots its own `dataSection` (the live or showcase data block) in
 * via children. Breadcrumb + FAQ JSON-LD is emitted from inside the shell
 * so every page automatically ships the right structured data.
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { breadcrumbJsonLd, faqJsonLd, jsonLdScript } from "@/lib/jsonld";

export type FeatureFAQ = { q: string; a: string };

export type SisterFeature = {
  slug: string;     // URL path without leading slash, e.g. "short-squeeze-scanner"
  label: string;    // Short label for the link, e.g. "Short squeeze scanner"
};

// Canonical list of sister features. Add new feature pages here so they
// cross-link from every other feature page automatically.
export const FEATURE_PAGES: SisterFeature[] = [
  { slug: "short-squeeze-scanner", label: "Short squeeze scanner" },
  { slug: "congressional-trades",  label: "Congressional trades" },
  { slug: "insider-buying",        label: "Insider buying (Form 4)" },
  { slug: "stock-market-heatmap",  label: "Stock market heatmap" },
  { slug: "market-regime",         label: "Market regime indicator" },
];

type Props = {
  /** URL slug for this page, e.g. "short-squeeze-scanner". Used for canonical
      + breadcrumb URL, and to filter the sister-feature link list. */
  slug: string;
  /** Eyebrow label above the H1. Short category descriptor. */
  eyebrow: string;
  /** Page H1. Front-load the target keyword. */
  h1: string;
  /** Hero lede paragraph below the H1. 2-3 sentences, sells the page. */
  lede: string;
  /** Data section — live data table, heatmap, regime card, whatever fits.
      Slotted in as children so each page can render whatever shape works. */
  children: React.ReactNode;
  /** Methodology heading + body. Explains how Tapeline computes / surfaces
      this feature. Long-form content for both the user + SEO depth signal. */
  methodology: {
    heading: string;
    body: React.ReactNode;
  };
  /** FAQ — visible accordion + JSON-LD FAQPage schema. 5-6 items ideal. */
  faq: FeatureFAQ[];
  /** Premium feature? Drives the CTA copy. */
  tier: "free" | "pro" | "premium";
};

export function SeoFeaturePage({
  slug,
  eyebrow,
  h1,
  lede,
  children,
  methodology,
  faq,
  tier,
}: Props) {
  const url = `https://tapeline.io/${slug}`;
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Features", url: "https://tapeline.io/" },
    { name: h1, url },
  ]);
  const tierLabel = tier === "premium" ? "Premium" : tier === "pro" ? "Pro" : "Free";
  const tierCopy =
    tier === "premium"
      ? "Premium · 14-day trial, no credit card."
      : tier === "pro"
        ? "Pro · 14-day Premium trial that includes everything in Pro."
        : "Free tier — see the live universe today.";

  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(faq))} />
      <MarketingNav />

      <article className="mx-auto max-w-4xl px-4 sm:px-6 py-8">
        {/* Hero */}
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          {h1}
        </h1>
        <p className="mt-4 text-lg text-muted leading-relaxed">{lede}</p>

        {/* Data section — page-specific */}
        <section className="mt-10">{children}</section>

        {/* Methodology — long-form, signals depth to Google + answers the
            "how does this actually work" question new visitors ask. */}
        <section className="mt-12 rounded-xl border border-border bg-panel/40 p-6">
          <h2 className="text-lg font-semibold">{methodology.heading}</h2>
          <div className="mt-3 space-y-3 text-sm text-muted leading-relaxed">
            {methodology.body}
          </div>
        </section>

        {/* FAQ — visible mirror of FAQPage JSON-LD above. */}
        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">
            Common questions
          </h2>
          <div className="mt-6 divide-y divide-border/60">
            {faq.map((item) => (
              <details key={item.q} className="group py-4">
                <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
                  <h3 className="text-sm font-medium">{item.q}</h3>
                  <span className="text-muted transition-transform group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="mt-3 text-sm text-muted leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* Sister features — spreads crawl across the cluster + gives the
            visitor 4 adjacent things to look at if this one didn't land. */}
        <nav
          aria-label="Other Tapeline features"
          className="mt-12 rounded-xl border border-border bg-panel/40 p-6"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Other Tapeline features
          </h2>
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {FEATURE_PAGES.filter((f) => f.slug !== slug).map((f) => (
              <Link
                key={f.slug}
                href={`/${f.slug}`}
                className="text-muted hover:text-accent underline-offset-4 hover:underline"
              >
                {f.label}
              </Link>
            ))}
          </div>
        </nav>

        {/* CTA — tier-aware copy + same gradient as the homepage final CTA. */}
        <section className="mt-12 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <p className="eyebrow text-accent">{tierLabel} feature</p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight">
            See this live across the full ~2,500-ticker universe.
          </h2>
          <p className="mt-3 text-sm text-muted">{tierCopy}</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="btn-primary">
              Try Premium free &rarr;
            </Link>
            <Link href="/pricing" className="btn-ghost">
              See pricing
            </Link>
          </div>
        </section>

        <p className="mt-10 text-xs text-subtle text-center">
          Data refreshes during US market hours. Not investment advice — see{" "}
          <Link href="/legal/risk" className="text-accent hover:underline">
            risk disclosure
          </Link>
          .
        </p>
      </article>

      <MarketingFooter />
    </main>
  );
}
