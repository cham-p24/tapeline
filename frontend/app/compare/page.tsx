import Link from "next/link";
import { Button } from "@/components/Button";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { allComparePairs, canonicalMatchup } from "@/lib/comparePairs";
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
 */
export const metadata = pageMeta({
  title: "Compare any two stocks on one score — Tapeline",
  description:
    "Stock-vs-stock head-to-heads on the same published six-factor score, factor by factor, each name back-checked on the public scorecard.",
  path: "/compare",
});

export default function CompareIndexPage() {
  const pairs = allComparePairs();
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io" },
    { name: "Compare", url: "https://tapeline.io/compare" },
  ]);

  return (
    <main>
      <script {...jsonLdScript(breadcrumbs)} />
      <MarketingNav />

      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-12">
        <nav className="text-xs text-muted">Compare</nav>
        <h1 className="mt-3 text-3xl font-bold tracking-tight text-balance sm:text-4xl">
          Compare any two stocks
        </h1>
        <p className="mt-3 max-w-2xl text-muted leading-relaxed">
          How any two stocks stack up on the same published six-factor score, factor by factor.
          Every comparison is descriptive and rules-based — a reading, not a recommendation.
        </p>

        {/* ── Ticker head-to-heads ─────────────────────────────────────── */}
        <section className="mt-12">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Stock vs stock
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-muted">
            Two tickers, two composite scores, factor by factor — each back-checked on the public
            scorecard.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {pairs.map(({ a, b }) => {
              const slug = canonicalMatchup(a, b);
              return (
                <Link
                  key={slug}
                  href={`/compare/${slug}`}
                  className="rounded-full border border-border bg-panel px-3 py-1.5 font-mono text-sm text-muted transition-colors hover:border-accent hover:text-fg"
                >
                  {a} vs {b}
                </Link>
              );
            })}
          </div>
        </section>

        {/* ── CTA ──────────────────────────────────────────────────────── */}
        <div className="mt-14 rounded-2xl border border-border bg-panel p-6 text-center sm:p-8">
          <h2 className="text-xl font-semibold">See any ticker scored yourself</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            The same six-factor score on the live scanner. The published record is free
            to read with no account; an account is an email and a password, and opens the
            scanner on the top ten scored rows of any scan. A card starts the 14-day
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
