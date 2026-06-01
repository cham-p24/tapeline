/**
 * /stocks — the complete public stock-coverage directory.
 *
 * WHY THIS PAGE EXISTS (orphan-rescue, 2026-06-01):
 * The 2026-05-17 /signals preview-wall pivot caps the anonymous (and
 * therefore Googlebot) view to the top-10 rows; /sector/{slug} hubs only
 * fetch the top-20 by score (the /api/scanner Free-tier row cap). Net
 * effect: the long-tail small/mid-cap /t/{SYMBOL} pages lost every inbound
 * internal link and went orphan — Google "Discovered" them via the sitemap
 * but never spent crawl budget, parking ~20+ of them in
 * "Discovered - currently not indexed".
 *
 * This directory is the classic HTML-sitemap fix: one well-linked
 * (footer-linked on every marketing page) server-rendered page that emits a
 * crawlable <a href="/t/{SYMBOL}"> for EVERY actively-scored ticker, grouped
 * by sector. It restores a clean crawl path to the whole universe without
 * touching the /signals conversion wall, and it scales automatically as the
 * universe grows — no manual maintenance.
 *
 * Frontend-only by design: it reuses the existing no-auth, no-tier-cap
 * /api/public/signals endpoint (the same one /signals + the sitemap use), so
 * shipping it needs only a Vercel deploy — no backend change.
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, jsonLdScript } from "@/lib/jsonld";
import { SECTORS } from "@/app/sector/sectors";

// Hourly ISR. The directory only needs to reflect universe membership
// (which churns slowly via auto-discovery), not live scores — so a 1h cache
// matches the sitemap's cadence and keeps crawler-driven DB load near zero.
export const revalidate = 3600;

export const metadata = pageMeta({
  title: "Stock Directory — Every Ticker Tapeline Scores, by Sector",
  description:
    "Browse the full Tapeline coverage universe — every US stock we score, " +
    "grouped by GICS sector. Each ticker links to its live 6-factor score, " +
    "plain-English breakdown, and FAQ.",
  path: "/stocks",
});

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

type DirectoryRow = {
  symbol: string;
  name: string | null;
  sector: string | null;
};

type SignalsResponse = {
  count: number;
  items: DirectoryRow[];
};

async function fetchUniverse(): Promise<DirectoryRow[]> {
  try {
    // limit=2000 returns the full scored universe in one call (currently a
    // few hundred names; the endpoint hard-caps at 2000). revalidate keeps
    // the fetch behind the 1h ISR cache so crawlers don't hit the API live.
    const res = await fetch(`${API_BASE}/api/public/signals?limit=2000`, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return [];
    const body = (await res.json()) as SignalsResponse;
    return body.items ?? [];
  } catch {
    return [];
  }
}

// A rendered section: a GICS sector (with a /sector hub link) or the
// catch-all "Other" bucket (ETFs, commodities, Unknown — no hub page).
type Group = {
  key: string;
  display: string;
  slug: string | null; // null = no /sector/{slug} hub
  rows: DirectoryRow[];
};

function groupBySector(rows: DirectoryRow[]): Group[] {
  // Seed groups in canonical SECTORS order so the page reads the same way
  // every render, then a trailing "Other" bucket for anything off-taxonomy.
  const bySector = new Map<string, Group>();
  for (const s of SECTORS) {
    bySector.set(s.api, { key: s.api, display: s.display, slug: s.slug, rows: [] });
  }
  const other: Group = { key: "__other__", display: "ETFs, commodities & other", slug: null, rows: [] };

  for (const r of rows) {
    const g = (r.sector ? bySector.get(r.sector) : undefined) ?? other;
    g.rows.push(r);
  }

  // Alphabetical by symbol within each section — stable, scannable, and the
  // order Google sees on every crawl.
  const ordered: Group[] = [...SECTORS.map((s) => bySector.get(s.api)!), other];
  for (const g of ordered) {
    g.rows.sort((a, b) => a.symbol.localeCompare(b.symbol));
  }
  return ordered.filter((g) => g.rows.length > 0);
}

function displayName(r: DirectoryRow): string | null {
  // The feed sometimes stores name === symbol (no resolved company name);
  // suppress it so the link doesn't read "AAPL AAPL".
  if (!r.name || r.name === r.symbol) return null;
  return r.name;
}

export default async function StocksDirectoryPage() {
  const rows = await fetchUniverse();
  const groups = groupBySector(rows);
  const total = rows.length;

  const breadcrumb = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Stock directory", url: "https://tapeline.io/stocks" },
  ]);

  const collection = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "@id": "https://tapeline.io/stocks#collection",
    url: "https://tapeline.io/stocks",
    name: "Tapeline Stock Directory",
    description:
      "Complete index of every US stock actively scored by the Tapeline " +
      "6-factor scanner, grouped by GICS sector. Each entry links to a " +
      "per-ticker page with the live composite score and factor breakdown.",
    isPartOf: { "@type": "WebSite", url: "https://tapeline.io", name: "Tapeline" },
    isAccessibleForFree: true,
  };

  return (
    <main className="min-h-screen">
      <MarketingNav />
      <script {...jsonLdScript(breadcrumb)} />
      <script {...jsonLdScript(collection)} />

      <article className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
        {/* Visible breadcrumb — mirrors the BreadcrumbList JSON-LD */}
        <nav aria-label="Breadcrumb" className="text-xs text-subtle">
          <ol className="flex flex-wrap items-center gap-1.5">
            <li>
              <Link href="/" className="hover:text-accent">Tapeline</Link>
            </li>
            <li aria-hidden className="text-border">/</li>
            <li className="text-muted">Stock directory</li>
          </ol>
        </nav>

        <p className="eyebrow mt-4">Coverage directory</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          Every stock Tapeline scores
        </h1>
        <p className="mt-4 max-w-3xl text-lg text-muted">
          The complete map of our coverage universe
          {total > 0 ? <> — <span className="font-semibold text-fg">{total.toLocaleString()}</span> actively-scored US tickers</> : null}, grouped by
          GICS sector. Every name links to its per-ticker page with the live
          0–100{" "}
          <Link href="/how-it-works" className="link">6-factor score</Link>,
          factor breakdown, and FAQ. The same published formula runs on every
          row — see how today&rsquo;s picks have held up on the{" "}
          <Link href="/scorecard" className="link">public scorecard</Link>.
        </p>

        {groups.length === 0 ? (
          <div className="mt-10 rounded-xl border border-border bg-panel p-8 text-center">
            <p className="text-muted">The coverage directory is refreshing.</p>
            <p className="mt-3 text-sm text-subtle">
              This page rebuilds hourly — check back shortly, or browse the live{" "}
              <Link href="/signals" className="text-accent hover:underline">
                signals universe
              </Link>{" "}
              in the meantime.
            </p>
          </div>
        ) : (
          <>
            {/* Sector jump-nav — in-page anchors double as a compact table of
                contents and spread internal-link signal across the sections. */}
            <nav
              aria-label="Jump to sector"
              className="mt-8 flex flex-wrap gap-x-4 gap-y-2 rounded-xl border border-border bg-panel/40 p-4 text-sm"
            >
              {groups.map((g) => (
                <a
                  key={g.key}
                  href={`#${sectorAnchor(g)}`}
                  className="text-muted hover:text-accent underline-offset-4 hover:underline"
                >
                  {g.display}{" "}
                  <span className="text-subtle">({g.rows.length})</span>
                </a>
              ))}
            </nav>

            <div className="mt-10 space-y-12">
              {groups.map((g) => (
                <section key={g.key} id={sectorAnchor(g)} className="scroll-mt-24">
                  <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-2">
                    <h2 className="text-xl font-semibold tracking-tight">
                      {g.slug ? (
                        <Link href={`/sector/${g.slug}`} className="hover:text-accent">
                          {g.display}
                        </Link>
                      ) : (
                        g.display
                      )}
                    </h2>
                    <span className="text-xs text-subtle">
                      {g.rows.length.toLocaleString()} {g.rows.length === 1 ? "ticker" : "tickers"}
                      {g.slug ? (
                        <>
                          {" · "}
                          <Link href={`/sector/${g.slug}`} className="text-accent hover:underline">
                            ranked view →
                          </Link>
                        </>
                      ) : null}
                    </span>
                  </div>

                  <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3 lg:grid-cols-4">
                    {g.rows.map((r) => {
                      const name = displayName(r);
                      return (
                        <li key={r.symbol} className="truncate">
                          <Link
                            href={`/t/${r.symbol}`}
                            className="group inline-flex items-baseline gap-1.5 text-sm hover:text-accent"
                            title={name ? `${r.symbol} — ${name}` : r.symbol}
                          >
                            <span className="font-mono font-medium">{r.symbol}</span>
                            {name ? (
                              <span className="truncate text-muted group-hover:text-accent/80">
                                {name}
                              </span>
                            ) : null}
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          </>
        )}

        {/* Cross-links to the sibling discovery surfaces — keeps the directory
            wired into the rest of the crawl graph rather than a dead end. */}
        <nav
          aria-label="Related pages"
          className="mt-14 flex flex-wrap gap-x-6 gap-y-2 border-t border-border pt-6 text-sm text-muted"
        >
          <Link href="/signals" className="hover:text-fg underline-offset-4 hover:underline">
            Live signals universe
          </Link>
          <Link href="/sectors" className="hover:text-fg underline-offset-4 hover:underline">
            Sector rankings
          </Link>
          <Link href="/scorecard" className="hover:text-fg underline-offset-4 hover:underline">
            Public scorecard
          </Link>
          <Link href="/how-it-works" className="hover:text-fg underline-offset-4 hover:underline">
            How the score works
          </Link>
        </nav>

        <p className="mt-8 text-xs text-subtle">
          Directory rebuilds hourly. Scores update sub-60s during US market
          hours on each ticker&rsquo;s page. Descriptive analytics, not
          investment advice — see{" "}
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

// Stable in-page anchor per section. GICS sectors use their slug; the
// "Other" bucket gets a fixed id so the jump-nav link never breaks.
function sectorAnchor(g: Group): string {
  return g.slug ?? "other";
}
