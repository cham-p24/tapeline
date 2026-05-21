import Link from "next/link";

/**
 * Cross-link block for /compare/* pages.
 *
 * Why this exists: the 17 /compare/X pages were islands — each ranked
 * its own keyword but contributed zero internal-link equity to the
 * sister pages in the cluster. Per the 2026-05-21 GSC audit ("Discovered
 * — currently not indexed" was concentrated on the comparison cluster),
 * the single highest-leverage internal-linking play is to graph the
 * cluster: every /compare/X page links to all other /compare/Y pages.
 *
 * Effect: shifts crawl budget from "templated single-page test" to
 * "topic cluster", which is what Google's quality classifier rewards.
 * Also gives a human reader an obvious next step ("how does Tapeline
 * compare to X?") so the page does double duty as a hub.
 *
 * Pass `currentSlug` so the current page is excluded from the list.
 */

export type CompareEntry = {
  slug: string;
  name: string;
  hint: string;
};

// Single source of truth for the comparison-cluster. Keep alphabetical
// so the render is stable regardless of insertion order.
export const COMPARE_INDEX: CompareEntry[] = [
  { slug: "benzinga-pro", name: "Benzinga Pro", hint: "Newsroom-grade headlines" },
  { slug: "bloomberg-terminal", name: "Bloomberg Terminal", hint: "Institutional terminal" },
  { slug: "finviz", name: "Finviz Elite", hint: "Raw screener fields" },
  { slug: "koyfin", name: "Koyfin", hint: "Bloomberg-style data" },
  { slug: "marketsmith", name: "MarketSmith", hint: "CAN SLIM methodology" },
  { slug: "robinhood", name: "Robinhood", hint: "Commission-free broker" },
  { slug: "seeking-alpha", name: "Seeking Alpha", hint: "Crowd-sourced analysis" },
  { slug: "simply-wall-st", name: "Simply Wall St", hint: "Snowflake visualisation" },
  { slug: "stock-rover", name: "Stock Rover", hint: "Long-term fundamentals" },
  { slug: "stockcharts", name: "StockCharts", hint: "Charting + alerts" },
  { slug: "tipranks", name: "TipRanks", hint: "Analyst consensus" },
  { slug: "trade-ideas", name: "Trade Ideas", hint: "Intraday AI signals" },
  { slug: "tradingview", name: "TradingView", hint: "Charting + community" },
  { slug: "wallstreetzen", name: "WallStreetZen", hint: "115-factor Zen Rating" },
  { slug: "webull", name: "Webull", hint: "Mobile-first broker" },
  { slug: "yahoo-finance", name: "Yahoo Finance", hint: "Free fundamental data" },
  { slug: "zacks", name: "Zacks Premium", hint: "Earnings-revision rank" },
];

export function CompareIndex({ currentSlug }: { currentSlug: string }) {
  const others = COMPARE_INDEX.filter((c) => c.slug !== currentSlug);
  return (
    <section
      aria-label="Other Tapeline comparisons"
      className="mx-auto max-w-4xl px-4 sm:px-6 py-10 border-t border-border/40"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
        Compare Tapeline to another tool
      </h2>
      <p className="mt-2 text-sm text-muted">
        We&rsquo;ve published side-by-side comparisons against the {COMPARE_INDEX.length} tools
        traders most commonly evaluate Tapeline against. Pick yours — each comparison includes
        pricing, scoring methodology, scorecard transparency, and the categories where the
        competitor honestly wins.
      </p>
      <ul className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {others.map((c) => (
          <li key={c.slug}>
            <Link
              href={`/compare/${c.slug}`}
              className="group block rounded-md border border-border/60 bg-panel/40 px-3 py-2.5 hover:border-accent/60 hover:bg-panel transition"
            >
              <div className="text-sm font-medium group-hover:text-accent">
                Tapeline vs {c.name}
              </div>
              <div className="text-[11px] text-subtle">{c.hint}</div>
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-5 text-xs text-subtle">
        Don&rsquo;t see your tool?{" "}
        <a href="mailto:support@tapeline.io" className="text-accent hover:underline">
          Tell us
        </a>{" "}
        — we publish a new comparison every two weeks based on requests.
      </p>
    </section>
  );
}
