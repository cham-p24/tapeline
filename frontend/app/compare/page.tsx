import Link from "next/link";
import { Button } from "@/components/Button";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { COMPARE_INDEX } from "@/components/CompareIndex";
import { allComparePairs, canonicalMatchup } from "@/lib/comparePairs";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, jsonLdScript } from "@/lib/jsonld";

/**
 * /compare index — the crawlable parent for the whole comparison cluster.
 *
 * Two clusters previously had NO shared hub: the 18 tool-comparison pages
 * (/compare/finviz, /compare/koyfin, …) and the ticker-vs-ticker pages
 * (/compare/[a]-vs-[b]). The /compare/[matchup] breadcrumb even linked here
 * to a page that didn't exist — a live 404. This page fixes that dead link and
 * gives both clusters a single hub, so a visitor (and a crawler) can reach any
 * comparison from one place. Content-only, statically rendered.
 */
export const metadata = pageMeta({
  title: "Compare Tapeline — vs every major screener, and stock vs stock",
  description:
    "One place to compare: Tapeline against 18 screeners and brokers (Finviz, TradingView, Koyfin, Stock Rover and more), plus stock-vs-stock head-to-heads on the published six-factor score.",
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
          Compare Tapeline
        </h1>
        <p className="mt-3 max-w-2xl text-muted leading-relaxed">
          How Tapeline lines up against the tools you already know, and how any two stocks stack up on
          the same published six-factor score. Every comparison is descriptive and rules-based — a
          reading, not a recommendation.
        </p>

        {/* ── Tool comparisons ─────────────────────────────────────────── */}
        <section className="mt-12">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Tapeline vs the tools you know
          </h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {COMPARE_INDEX.map((c) => (
              <Link
                key={c.slug}
                href={`/compare/${c.slug}`}
                className="group rounded-xl border border-border bg-panel p-4 transition-colors hover:border-border2 hover:bg-panel2"
              >
                <div className="font-medium text-fg">
                  Tapeline vs {c.name}
                </div>
                <div className="mt-0.5 text-sm text-muted">{c.hint}</div>
              </Link>
            ))}
          </div>
        </section>

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
            The same six-factor score on the full live scanner — top rows free, no card to look.
          </p>
          <Button href="/signup" variant="primary" shape="rounded" className="mt-5">
            Sign up &rarr;
          </Button>
        </div>
      </div>

      <MarketingFooter />
    </main>
  );
}
