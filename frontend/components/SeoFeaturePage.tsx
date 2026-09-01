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
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { breadcrumbJsonLd, faqJsonLd, jsonLdScript } from "@/lib/jsonld";
import { scoredTickersLabel } from "@/lib/universe";

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

// Adjacent strategy listicles for the cross-feature nav. Each feature page
// surfaces 3-4 of these in its "Related rankings" strip — funnels visitors
// from a feature explanation page into a concrete ticker list, then on to
// /signup. Strategy slugs map to /best-stocks-for/<slug>.
export type RelatedStrategy = { slug: string; label: string };
export const STRATEGY_LINKS: RelatedStrategy[] = [
  { slug: "high-conviction", label: "Highest-scored stocks today" },
  { slug: "breakouts",       label: "Stocks breaking out today" },
  { slug: "growth-stocks",   label: "Best growth stocks" },
  { slug: "ai-stocks",       label: "Best AI stocks" },
  { slug: "swing-traders",   label: "Best stocks to swing trade" },
  { slug: "day-traders",     label: "Best stocks to day trade" },
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
  /** Premium feature? Drives the CTA copy.
      No "free" member, for a reason that has now changed twice. The 2026-08-22
      card gate walled new accounts, so a "free tier" line under this button
      would have been false and the member was removed. #683 (2026-08-30) took
      the wall away: signing up takes an email and a password and lands on the
      free plan. A free line would be honest again — the member stays absent
      only because no caller uses it. What this template must NOT do is imply
      the trial is card-free; the trial still takes a card. */
  tier: "pro" | "premium";
  /** Message-match slug appended to the /signup CTA as ?from=<slug>. The
      signup page restates the matching promise in its H1 (see signup
      FROM_COPY) so ad → landing → signup copy stays consistent. Constrained
      to the slugs the signup page actually handles; scanner/screener-style
      feature pages should pass "screener". Defaults to "compare". */
  signupFrom?: "finviz" | "screener" | "scorecard" | "compare";
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
  signupFrom = "compare",
}: Props) {
  const url = `https://tapeline.io/${slug}`;
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Features", url: "https://tapeline.io/" },
    { name: h1, url },
  ]);
  const tierLabel = tier === "premium" ? "Premium" : "Pro";
  // Says what the reader gets, not what the tier is called. The previous
  // Pro line ("14-day Premium trial that includes everything in Pro") was
  // circular — it described the trial in terms of the tier and the tier in
  // terms of the trial, and made no argument at all.
  const tierCopy =
    tier === "premium"
      ? "Included in Premium, and in the 14-day trial from day one."
      : "Included in Pro, and in the 14-day Premium trial from day one.";

  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(faq))} />
      <MarketingNav />

      <article className="mx-auto max-w-5xl px-4 sm:px-6 py-8">
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
        <section className="mt-12 border-t border-border/60 pt-8">
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
          className="mt-12 border-t border-border/60 pt-8"
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

        {/* Related rankings — links into /best-stocks-for/ listicle pages.
            Tightens the cross-cluster link graph so the strategy + feature
            pages reinforce each other in Google's eyes (per GSC audit, the
            isolated feature pages weren't accumulating crawl signals
            because they had no inbound from the rest of the site). */}
        <nav
          aria-label="Related ticker rankings"
          className="mt-6 border-t border-border/60 pt-8"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Related ticker rankings
          </h2>
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {STRATEGY_LINKS.slice(0, 4).map((s) => (
              <Link
                key={s.slug}
                href={`/best-stocks-for/${s.slug}`}
                className="text-muted hover:text-accent underline-offset-4 hover:underline"
              >
                {s.label}
              </Link>
            ))}
          </div>
        </nav>

        {/* Newsletter mid-funnel capture — for visitors not ready to start
            a trial but willing to give us an email for the daily Top 10
            digest. Lower-commitment than /signup; same conversion bucket
            in GA4 via method='newsletter'. */}
        <section className="mt-12 border-t border-border/60 pt-8">
          <NewsletterCapture source="feature" heading="" sub="" />
        </section>

        {/* CTA — tier-aware copy + same gradient as the homepage final CTA.
         *
         * REBUILT 2026-09-01 against what actually produces a card.
         *
         * Every account that has ever put a card on Tapeline did it within
         * 2m08s of signing up, without touching the product first. Nobody was
         * converted by usage: the longest-tenured account in the base (21 days)
         * never carded, and the free-tier cap meter has fired six times in its
         * life and converted no one. The decision is made BEFORE the account
         * exists, which makes this block — not the app — the selling surface.
         *
         * Two changes follow from that:
         *
         * 1. The record is a primary path, not a footnote. The fastest card on
         *    record (29 seconds, direct traffic) came from someone who arrived
         *    already convinced; /scorecard is the only asset that can do that,
         *    and it needs no account and no card. Sending an unconvinced
         *    visitor there beats sending them to a signup form they abandon —
         *    these pages currently convert signups to cards at 0%.
         *
         * 2. The card terms are stated here rather than discovered at checkout.
         *    That is the mechanism behind the only ad concept in the 2026-08
         *    burst that produced cards: name the money question and answer it
         *    completely, up front. See docs/ads/meta-burst-2026-08/.
         *
         * Ticker count comes from lib/universe — it was hardcoded "~2,500"
         * here and understated the real figure by 2.7x.
         */}
        <section className="mt-12 rounded-2xl bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <p className="eyebrow text-accent">{tierLabel} feature</p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight">
            See this live across {scoredTickersLabel} scored tickers.
          </h2>
          <p className="mt-3 text-sm text-muted">{tierCopy}</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href={`/signup?from=${signupFrom}`} className="btn-primary">
              Start the 14-day Premium trial &rarr;
            </Link>
            <Link href="/scorecard" className="btn-ghost">
              Read the record first &rarr;
            </Link>
          </div>
          <p className="mt-4 text-xs text-subtle">
            The record needs no account and no card. The trial takes a card,
            charges $0 today, and shows the date of the first charge before you
            confirm.{" "}
            <Link href="/pricing" className="text-accent hover:underline">
              See pricing
            </Link>
            .
          </p>
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
