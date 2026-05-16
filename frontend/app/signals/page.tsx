/**
 * PUBLIC universe view — every Tapeline-scored ticker, no auth required.
 *
 * Companion to /scorecard. Where /scorecard shows the daily top-10 picks
 * back-checked against SPY (trust mechanism for the picks), /signals
 * shows the FULL UNIVERSE with current composite scores (trust mechanism
 * for the breadth). Together they're the "public formula, public
 * scorecard, public everything" brand stance made literal.
 *
 * Distinct from /app/scanner: the paid scanner's value moves to its
 * features (filter UX, watchlist, alerts, exports). This page is
 * read-only — no filter chips, no sort dropdowns, no save-screener.
 * Sorting via URL param (?sort=score) keeps it crawlable; users who
 * want richer slicing convert to Pro.
 *
 * Server-rendered for SEO. Revalidates every 5 minutes (matches the
 * sheet-feed refresh cadence in services/sheet_feed.py so the page
 * never shows staler data than the sheet itself).
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, jsonLdScript } from "@/lib/jsonld";

export const revalidate = 300;

export const metadata = pageMeta({
  title: "All Tapeline-Scored Tickers — Live Universe with Public 6-Factor Score",
  description:
    "Every US stock Tapeline scores, ranked by the live 0-100 composite. " +
    "Same published formula as our public scorecard; no signup, no paywall. " +
    "Each ticker links to its score breakdown.",
  path: "/signals",
});

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

type SignalRow = {
  symbol: string;
  name: string | null;
  sector: string | null;
  asset_class: string;
  score: number | null;
  signal: string | null;
  price: number | null;
  change_pct_1d: number | null;
  change_pct_5d: number | null;
  change_pct_1m: number | null;
  confidence_pct: number | null;
  sub_trend: number | null;
  sub_rs: number | null;
  sub_fundamentals: number | null;
  sub_momentum: number | null;
  sub_macro: number | null;
  sub_smart_money: number | null;
  updated_at: string | null;
};

type SignalsResponse = {
  count: number;
  limit: number;
  offset: number;
  items: SignalRow[];
};

async function fetchSignals(): Promise<SignalsResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/api/public/signals?limit=2000`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    return (await res.json()) as SignalsResponse;
  } catch {
    return null;
  }
}

function scoreColor(score: number | null): string {
  if (score === null) return "text-muted";
  if (score >= 85) return "text-up";
  if (score >= 70) return "text-up/80";
  if (score >= 55) return "text-accent";
  if (score >= 40) return "text-muted";
  if (score >= 25) return "text-yellow-400";
  return "text-down";
}

function signalBadge(signal: string | null): string {
  switch (signal) {
    case "HIGH CONVICTION":
      return "bg-up/15 text-up border-up/30";
    case "STRONG SETUP":
      return "bg-up/10 text-up/90 border-up/20";
    case "CONSTRUCTIVE":
      return "bg-accent/15 text-accent border-accent/30";
    case "NEUTRAL":
      return "bg-muted/20 text-muted border-border";
    case "CAUTION":
      return "bg-yellow-500/15 text-yellow-400 border-yellow-500/30";
    case "WEAK":
      return "bg-down/15 text-down border-down/30";
    default:
      return "bg-panel text-muted border-border";
  }
}

function fmtPct(v: number | null): string {
  if (v === null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function fmtPrice(v: number | null): string {
  if (v === null || Number.isNaN(v)) return "—";
  if (v >= 1000) return `$${v.toFixed(0)}`;
  return `$${v.toFixed(2)}`;
}

export default async function SignalsPage() {
  const data = await fetchSignals();
  const items = data?.items ?? [];

  // Bucket the universe by signal tier for the headline counts row.
  const bucket = (label: string) =>
    items.filter((r) => r.signal === label).length;
  const counts = {
    high: bucket("HIGH CONVICTION"),
    strong: bucket("STRONG SETUP"),
    constructive: bucket("CONSTRUCTIVE"),
    neutral: bucket("NEUTRAL"),
    caution: bucket("CAUTION"),
    weak: bucket("WEAK"),
  };

  const breadcrumb = breadcrumbJsonLd([
    { name: "Home", url: "https://tapeline.io/" },
    { name: "All scored tickers", url: "https://tapeline.io/signals" },
  ]);

  return (
    <main className="min-h-screen">
      <MarketingNav />
      <script {...jsonLdScript(breadcrumb)} />

      <section className="mx-auto max-w-6xl px-6 py-12">
        <p className="eyebrow">Public universe</p>
        <h1 className="mt-3 text-5xl font-bold tracking-tight">
          Every ticker we score.
        </h1>
        <p className="mt-4 max-w-3xl text-lg text-muted">
          One transparent 0–100 score per US stock using the same{" "}
          <Link href="/how-it-works" className="link">
            public 6-factor formula
          </Link>{" "}
          we publish on our{" "}
          <Link href="/scorecard" className="link">
            back-checked scorecard
          </Link>
          . Read the page or tap any ticker for the score breakdown. No signup
          required.
        </p>

        {/* Aggregate counts by tier — gives a snapshot of the universe at
            a glance and signals to crawlers that this is a data-rich page
            worth indexing. */}
        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <CountTile label="High conviction" count={counts.high} tone="bg-up/15 text-up" />
          <CountTile label="Strong setup" count={counts.strong} tone="bg-up/10 text-up/90" />
          <CountTile label="Constructive" count={counts.constructive} tone="bg-accent/15 text-accent" />
          <CountTile label="Neutral" count={counts.neutral} tone="bg-muted/20 text-muted" />
          <CountTile label="Caution" count={counts.caution} tone="bg-yellow-500/15 text-yellow-400" />
          <CountTile label="Weak" count={counts.weak} tone="bg-down/15 text-down" />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16">
        {!data || items.length === 0 ? (
          <div className="card p-8 text-center text-muted">
            <p className="text-lg">No tickers loaded yet.</p>
            <p className="mt-2 text-sm">
              If you&rsquo;ve just configured the signal-source, give the worker a
              few minutes to refresh — this page reloads every 5 minutes.
            </p>
          </div>
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-panel">
                <tr className="text-left text-xs uppercase tracking-wide text-muted">
                  <th className="py-3 pl-4 pr-3">Symbol</th>
                  <th className="py-3 pr-3">Name</th>
                  <th className="py-3 pr-3">Sector</th>
                  <th className="py-3 pr-3 text-right">Score</th>
                  <th className="py-3 pr-3">Signal</th>
                  <th className="py-3 pr-3 text-right">Price</th>
                  <th className="py-3 pr-3 text-right">1D</th>
                  <th className="py-3 pr-3 text-right">1M</th>
                  <th className="py-3 pr-4 text-right">Conf</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((r) => (
                  <tr key={r.symbol} className="hover:bg-panel/40">
                    <td className="py-2 pl-4 pr-3">
                      <Link
                        href={`/t/${r.symbol}`}
                        className="font-mono font-semibold text-fg hover:text-accent"
                      >
                        {r.symbol}
                      </Link>
                    </td>
                    <td className="py-2 pr-3 text-muted">
                      {r.name === r.symbol ? "—" : r.name ?? "—"}
                    </td>
                    <td className="py-2 pr-3 text-xs text-muted">
                      {r.sector ?? "—"}
                    </td>
                    <td className={`nums py-2 pr-3 text-right font-semibold ${scoreColor(r.score)}`}>
                      {r.score === null ? "—" : r.score.toFixed(0)}
                    </td>
                    <td className="py-2 pr-3">
                      <span
                        className={`inline-block rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${signalBadge(r.signal)}`}
                      >
                        {r.signal ?? "—"}
                      </span>
                    </td>
                    <td className="nums py-2 pr-3 text-right">
                      {fmtPrice(r.price)}
                    </td>
                    <td
                      className={`nums py-2 pr-3 text-right ${
                        (r.change_pct_1d ?? 0) > 0
                          ? "text-up"
                          : (r.change_pct_1d ?? 0) < 0
                          ? "text-down"
                          : ""
                      }`}
                    >
                      {fmtPct(r.change_pct_1d)}
                    </td>
                    <td
                      className={`nums py-2 pr-3 text-right ${
                        (r.change_pct_1m ?? 0) > 0
                          ? "text-up"
                          : (r.change_pct_1m ?? 0) < 0
                          ? "text-down"
                          : ""
                      }`}
                    >
                      {fmtPct(r.change_pct_1m)}
                    </td>
                    <td className="nums py-2 pr-4 text-right text-muted">
                      {r.confidence_pct === null
                        ? "—"
                        : `${r.confidence_pct.toFixed(0)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-6 text-sm text-muted">
          <strong className="text-fg">Reading this page.</strong>{" "}
          <em>Score</em> is the composite 6-factor 0–100. <em>Signal</em> is the
          descriptive label per the band (HIGH CONVICTION ≥85, STRONG SETUP ≥70,
          CONSTRUCTIVE ≥55, NEUTRAL ≥40, CAUTION ≥25, WEAK &lt;25). <em>Conf</em>{" "}
          is per-ticker data confidence — mega-caps with full data coverage land
          80–95; less-followed names sit lower. None of the labels are
          prescriptive — see{" "}
          <Link href="/legal/disclosure" className="link">
            disclosure
          </Link>
          .
        </p>

        <div className="mt-8 rounded-xl border border-border bg-panel p-6">
          <p className="text-sm text-muted">
            Want to filter, sort, screen, and set alerts on these signals?
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            <Link href="/signup" className="btn-primary">
              Start a free Premium trial &rarr;
            </Link>
            <Link href="/pricing" className="btn-ghost">
              See pricing
            </Link>
          </div>
        </div>
      </section>

      <TransparencyStrip current="/signals" />
      <MarketingFooter />
    </main>
  );
}

function CountTile({
  label,
  count,
  tone,
}: {
  label: string;
  count: number;
  tone: string;
}) {
  return (
    <div className={`rounded-md border border-border p-3 ${tone}`}>
      <div className="text-xs uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-bold nums">{count}</div>
    </div>
  );
}
