import Link from "next/link";
import { Button } from "@/components/Button";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { ComparePicker } from "@/components/ComparePicker";
import { CompareFeatured } from "@/components/CompareFeatured";
import { CompareDirectory } from "@/components/CompareDirectory";
import { COMPARE_NAMES, comparePairsByGroup } from "@/lib/comparePairs";
import { COMPARE_FACTORS } from "@/lib/compareTicker";
import { FEATURED_PAIRS, loadFeaturedMatchups } from "@/lib/compareFeatured";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, jsonLdScript } from "@/lib/jsonld";

/**
 * /compare index — the crawlable parent for the ticker-vs-ticker cluster.
 *
 * The 18 tool-comparison pages (/compare/finviz, /compare/koyfin, …) were
 * REMOVED 2026-09-03 on the founder's decision. They returned 0 of 10
 * instrumented signups while other programmatic content returned 4, and they
 * had cost five separate copy-correction sweeps across four months purely to
 * keep claims about competitors' pricing and terms true. Their URLs now serve
 * 410 Gone (see next.config.mjs) rather than a silent 404, so crawlers delist
 * them deliberately instead of retrying.
 *
 * What remains is the stock-vs-stock cluster, which is a different surface: it
 * compares two tickers on Tapeline's own published score and makes no claim
 * about any third party.
 *
 * Layout (2026-09 redesign — the old page was one wall of ~165 identical pills):
 *   1. a two-ticker picker that routes to the canonical matchup URL;
 *   2. a featured head-to-head read from the ticker API server-side — hidden
 *      entirely if that read fails, never filled with placeholder numbers;
 *   3. every curated pair, grouped by theme (lib/comparePairs COMPARE_GROUPS).
 *      All hrefs stay in the server-rendered HTML — they are the cluster's SEO
 *      entry points.
 */

// The featured preview reads current scores, so the page is ISR rather than fully
// static — same hourly window as /compare/[matchup].
export const revalidate = 3600;

export const metadata = pageMeta({
  title: "Compare any two stocks on one score — Tapeline",
  description:
    "Stock-vs-stock head-to-heads on the same published six-factor score, factor by factor, each name back-checked on the public scorecard.",
  path: "/compare",
});


export default async function CompareIndexPage() {
  const groups = comparePairsByGroup();
  const totalPairs = groups.reduce((n, g) => n + g.pairs.length, 0);
  const featured = await loadFeaturedMatchups();
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io" },
    { name: "Compare", url: "https://tapeline.io/compare" },
  ]);

  // Every figure in this strip is counted from code, not written in by hand.
  const stats = [
    { value: String(totalPairs), label: "Curated pairs" },
    { value: String(groups.length), label: "Themes" },
    { value: String(COMPARE_FACTORS.length), label: "Published factors" },
    { value: "0–100", label: "Composite scale" },
  ];

  return (
    <main>
      <script {...jsonLdScript(breadcrumbs)} />
      <MarketingNav />

      <div className="mx-auto max-w-6xl px-4 pb-16 pt-6 sm:px-6 sm:pt-8">
        {/* ── Hero + picker ─────────────────────────────────────────────── */}
        <section className="relative rounded-3xl border border-border bg-gradient-to-br from-accent/10 via-panel to-panel px-4 py-8 sm:px-10 sm:py-12">
          {/* Soft accent glows — decorative, token colours only. They sit in
              their own clipped layer: clipping the hero itself would make it a
              scroll container (focusing the picker scrolled it sideways) and
              would cut off the typeahead list. */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden rounded-3xl">
            <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-accent2/20 blur-3xl" />
            <div className="absolute -bottom-32 -left-20 h-72 w-72 rounded-full bg-accent/10 blur-3xl" />
          </div>

          <div className="relative">
            <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-muted">
              <Link href="/" className="hover:text-fg">Tapeline</Link>
              <span aria-hidden="true" className="text-subtle">/</span>
              <span aria-current="page" className="text-fg">Compare</span>
            </nav>

            <div className="mt-5 max-w-3xl">
              <p className="eyebrow">Stock vs stock</p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight text-balance sm:text-5xl">
                Compare any two stocks,{" "}
                <span className="bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent">
                  factor by factor.
                </span>
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
                How any two stocks stack up on the same published six-factor score, factor by factor.
                Every comparison is descriptive and rules-based — a reading, not a recommendation.
              </p>
            </div>

            <div className="mt-7 max-w-4xl">
              <ComparePicker suggestions={FEATURED_PAIRS.map(([a, b]) => ({ a, b }))} />
            </div>

            <dl className="mt-8 grid max-w-4xl grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-4">
              {stats.map((s) => (
                <div key={s.label} className="bg-surface px-4 py-3">
                  <dt className="text-[11px] uppercase tracking-wider text-subtle">{s.label}</dt>
                  <dd className="nums mt-0.5 text-xl font-semibold tracking-tight">{s.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* ── Featured head-to-head (real API data, or nothing) ─────────── */}
        {featured.length > 0 && (
          <div className="mt-10 sm:mt-12">
            <CompareFeatured matchups={featured} />
          </div>
        )}

        {/* ── How to read a comparison ──────────────────────────────────── */}
        <section aria-labelledby="how-heading" className="mt-10 sm:mt-12">
          <h2 id="how-heading" className="sr-only">How a comparison reads</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              {
                title: "One published score",
                body: "Both names are read on the same six-factor composite, 0 to 100, with the method written out in public.",
                href: "/how-it-works",
                cta: "The six-factor method",
              },
              {
                title: "Factor by factor",
                body: "Trend, relative strength, fundamentals, smart money, macro and momentum, side by side.",
                href: null,
                cta: null,
              },
              {
                title: "A reading, not a call",
                body: "Scores describe; they don't pick. Every top pick is back-checked on the public scorecard, losses included.",
                href: "/scorecard",
                cta: "The public scorecard",
              },
            ].map((c) => (
              <div key={c.title} className="rounded-2xl border border-border bg-panel p-5">
                <h3 className="text-sm font-semibold">{c.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{c.body}</p>
                {c.href && c.cta && (
                  <Link href={c.href} className="link mt-3 inline-block text-sm">
                    {c.cta}{" "}&rarr;
                  </Link>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* ── Every curated pair, by theme ──────────────────────────────── */}
        <section aria-labelledby="themes-heading" className="mt-14 sm:mt-16">
          <div className="max-w-2xl">
            <p className="eyebrow">Browse</p>
            <h2 id="themes-heading" className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
              Head-to-heads by theme
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              Two tickers, two composite scores, factor by factor — each back-checked on the public
              scorecard. A curated set of within-theme pairs; the picker above takes any two tickers.
            </p>
          </div>
          <div className="mt-6">
            <CompareDirectory groups={groups} names={COMPARE_NAMES} />
          </div>
        </section>

        {/* ── CTA ──────────────────────────────────────────────────────── */}
        <div className="mt-14 rounded-3xl border border-border bg-gradient-to-br from-accent/10 via-panel to-panel p-6 text-center sm:p-10">
          <h2 className="text-xl font-semibold sm:text-2xl">See any ticker scored yourself</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            The same six-factor score on the scanner. The published record is free
            to read with no account; an account is an email and a password, and opens the
            scanner on the top ten scored rows of any scan. A card starts the 30-day
            Premium trial — every matching row instead of the first ten, $0 today, one
            click to cancel.
          </p>
          <Button href="/signup" variant="primary" shape="rounded" className="mt-5">
            Create your free account &rarr;
          </Button>
        </div>
      </div>

      <MarketingFooter />
    </main>
  );
}
