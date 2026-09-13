import type { Metadata } from "next";
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { ssrInternalHeaders } from "@/lib/ssrHeaders";

/*
 * /short-squeeze-scanner — HONEST EMPTY STATE (integrity fix, T-01).
 *
 * Until this change the page showed rows as a "Live preview". In production
 * those rows were 15 mock-tick rows written on 2026-07-18 UTC (no real writer is
 * configured: SPIKE_INTELLIGENCE_CSV_URL was unset on the worker when checked on
 * 2026-09-14), and when the API returned nothing the page fell back to a
 * hardcoded SHOWCASE_ROWS table labelled "Recent example". Both are gone:
 *
 *   - the backend now serves only publishable rows
 *     (backend/app/services/squeeze_integrity.py: written after 2026-07-19 and
 *     in the last 48 hours), so today the API returns an empty list;
 *   - an empty list, an API error or a timeout all render the same empty state.
 *     There is no fallback table.
 *
 * The page is noindex while no data source exists. Remove the `robots` override
 * only once a real writer is configured AND this page has shown real rows.
 */

export const revalidate = 3600;

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

const EMPTY_STATE_TEXT =
  "No squeeze data right now. We don't have a live source for this list, so we aren't showing one.";

export const metadata: Metadata = {
  ...pageMeta({
    title: "Short Squeeze Scanner | Tapeline",
    description:
      "Tapeline's squeeze list has no live data source right now, so it is empty. This page explains what the list would show and why nothing is listed.",
    path: "/short-squeeze-scanner",
  }),
  robots: {
    index: false,
    follow: true,
    googleBot: { index: false, follow: true },
  },
};

type SqueezeRow = {
  symbol: string;
  spike_score: number;
  squeeze_days: number;
  volume_multiple: number;
  obv_trend: string;
  breakout_type: string;
  reason: string;
  updated_at?: string | null;
};

async function fetchSqueeze(): Promise<SqueezeRow[]> {
  try {
    const res = await fetch(`${API_BASE}/api/public/squeeze?limit=5`, {
      next: { revalidate: 3600 },
      headers: ssrInternalHeaders(),
      // Bound the build-time fetch so a slow API can't hang static export.
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return [];
    const body = (await res.json()) as { items?: SqueezeRow[] };
    return Array.isArray(body.items) ? body.items : [];
  } catch {
    return [];
  }
}

/** "14 Sep 2026, 13:05 UTC" — the newest write time among the rows shown. */
function newestUpdate(rows: SqueezeRow[]): string | null {
  const times = rows
    .map((r) => (r.updated_at ? Date.parse(r.updated_at) : NaN))
    .filter((t) => Number.isFinite(t));
  if (times.length === 0) return null;
  const d = new Date(Math.max(...times));
  return (
    d.toLocaleString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
    }) + " UTC"
  );
}

const FAQ: { q: string; a: string }[] = [
  {
    q: "Why is the list empty?",
    a: "We don't have a live data source for squeeze setups. Rather than show old or made-up rows, we show nothing until a real source is connected.",
  },
  {
    q: "Did this page show squeeze data before?",
    a: "Yes, and it wasn't real. Rows produced by test code, not market data, were shown here as if they were current setups. The latest of those rows were written on 18 July 2026 (UTC). When those rows could not load, the page showed a hand-typed example table instead. Both have been removed from this page and from the in-app Squeeze Watch list, and squeeze alerts can no longer use them.",
  },
  {
    q: "What happens to a squeeze alert I already set?",
    a: "It stays saved. It can't send anything while there is no squeeze data, and your other alert types keep working as before.",
  },
];

export default async function ShortSqueezeScannerPage() {
  const rows = await fetchSqueeze();
  const updated = newestUpdate(rows);

  return (
    <main id="main" className="min-h-screen">
      <MarketingNav />

      <article className="mx-auto max-w-5xl px-4 sm:px-6 py-8">
        <p className="eyebrow">Feature · Squeeze Watch</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          Short Squeeze Scanner
        </h1>
        <p className="mt-4 text-lg text-muted leading-relaxed">
          This list is meant to show stocks whose price range has narrowed,
          ranked by a spike score. It only shows rows from a live data source,
          and right now we don&rsquo;t have one.
        </p>

        <section className="mt-10">
          {rows.length === 0 ? (
            <div className="card p-8 text-center" data-testid="squeeze-empty-state">
              <p className="text-base font-medium">{EMPTY_STATE_TEXT}</p>
              <p className="mt-3 text-sm text-muted">
                Correction: this page used to show squeeze rows produced by test
                code (the latest written on 18 July 2026, UTC) as if they were current
                setups and, when data could not load, a hand-typed example table.
                Neither was market data, and we have removed both.
              </p>
            </div>
          ) : (
            <div className="card overflow-x-auto">
              <div className="px-4 pt-3 text-[10px] uppercase tracking-wider text-subtle">
                {updated ? `Snapshot · updated ${updated}` : "Snapshot"}
              </div>
              <table className="mt-2 w-full text-sm">
                <thead className="border-b border-border bg-panel text-xs uppercase text-muted">
                  <tr>
                    <th className="px-3 py-3 text-left">#</th>
                    <th className="px-3 py-3 text-left">Ticker</th>
                    <th className="px-3 py-3 text-right">Spike</th>
                    <th className="px-3 py-3 text-right">Days tight</th>
                    <th className="px-3 py-3 text-right">Vol vs 20d</th>
                    <th className="px-3 py-3 text-left">OBV</th>
                    <th className="px-3 py-3 text-left">Setup</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={r.symbol} className="border-b border-border/30 hover:bg-panel/40">
                      <td className="px-3 py-3 font-mono text-subtle">{i + 1}</td>
                      <td className="px-3 py-3 font-mono font-medium">
                        <Link href={`/t/${r.symbol}`} className="hover:text-accent">
                          {r.symbol}
                        </Link>
                      </td>
                      <td className="px-3 py-3 text-right font-mono nums font-semibold">
                        {r.spike_score.toFixed(0)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono nums">{r.squeeze_days}</td>
                      <td className="px-3 py-3 text-right font-mono nums">
                        {r.volume_multiple.toFixed(1)}x
                      </td>
                      <td className="px-3 py-3 text-xs font-medium text-muted">{r.obv_trend}</td>
                      <td className="px-3 py-3 text-xs text-muted">{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="mt-12 border-t border-border/60 pt-8">
          <h2 className="text-lg font-semibold">What the list would show</h2>
          <div className="mt-3 space-y-3 text-sm text-muted leading-relaxed">
            <p>
              Each row would carry a spike score, the number of days the price
              range has been tight, the day&rsquo;s volume against its 20-day
              average, and the direction of on-balance volume (OBV). It would
              not predict which way a stock moves or when.
            </p>
            <p>
              How every Tapeline score is built is on{" "}
              <Link href="/how-it-works" className="link">
                how it works
              </Link>
              .
            </p>
          </div>
        </section>

        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">Common questions</h2>
          <div className="mt-6 divide-y divide-border/60">
            {FAQ.map((item) => (
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

        <p className="mt-10 text-xs text-subtle text-center">
          Not investment advice. See the{" "}
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
