/**
 * PUBLIC universe view — preview of every Tapeline-scored ticker.
 *
 * Anonymous visitors see the top 10 rows + signup CTA. Signed-in users
 * see the full universe. The aggregate counts row stays visible to all
 * (it sells the breadth of coverage without giving the actual rows away).
 *
 * Pivoted 2026-05-17 from fully-public to a preview wall. The trust
 * mechanism (public formula, public scorecard) stays intact on /scorecard;
 * /signals is the "what's live right now" demo, and the preview wall
 * gives anonymous visitors a real taste while turning every scroll
 * past row 10 into a signup CTA.
 *
 * Now dynamic (per-request) because we read the session cookie to decide
 * which view to render. Previously had `revalidate = 300` for static
 * caching — that's gone; the page is cheap enough to render fresh.
 */
import { cookies } from "next/headers";
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, jsonLdScript } from "@/lib/jsonld";

// Number of rows shown to anonymous visitors before the signup gate.
// Big enough to demonstrate the product (top 10 = clear ranking with
// real signals and prices); small enough that the rest of the universe
// is genuinely behind the wall.
const PREVIEW_ROWS = 10;

export const metadata = pageMeta({
  title: "All Tapeline-Scored Tickers — Live Universe with Public 6-Factor Score",
  description:
    "Every US stock Tapeline scores, ranked by the live 0-100 composite. " +
    "Same published formula as our public scorecard. Sign up to see the full universe.",
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
      next: { revalidate: 3600 },
      // Abort a hung/slow API so static export never blows Next's 60s
      // per-page budget. A hang is NOT caught by the try/catch (only a
      // thrown error is) — the timeout turns it into a catchable
      // TimeoutError -> graceful null below -> build succeeds. Matches the
      // /stocks + sitemap resilience pattern. ISR (revalidate:300) backfills
      // real data on the next successful fetch once the API is healthy.
      signal: AbortSignal.timeout(8000),
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
  if (score >= 25) return "text-warn";
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
      return "bg-warn/15 text-warn border-warn/30";
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

  // Gate: signed-in users see everything, anonymous visitors see the top
  // PREVIEW_ROWS. The session cookie is set by /api/auth/signup + signin
  // on the api.tapeline.io subdomain with Domain=tapeline.io, so it's
  // visible here. We don't validate the JWT — that's the backend's job
  // on the actual /api/* calls. Presence is enough to decide the gate.
  const isSignedIn = !!(await cookies()).get("tapeline_session")?.value;
  const visibleItems = isSignedIn ? items : items.slice(0, PREVIEW_ROWS);
  const hiddenCount = Math.max(0, items.length - visibleItems.length);

  // Bucket the universe by signal tier for the headline counts row.
  // Always computed on the FULL universe — anonymous visitors still
  // see the total breadth, which sells the gate ('580 high-conviction
  // names, sign up to see them all').
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
    <main id="main" className="min-h-screen">
      <MarketingNav />
      <script {...jsonLdScript(breadcrumb)} />

      <section className="mx-auto max-w-6xl px-6 py-8">
        <p className="eyebrow">Public universe</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
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
          .{" "}
          {isSignedIn ? (
            "Read the page or tap any ticker for the score breakdown."
          ) : (
            <>
              Anonymous visitors see the top {PREVIEW_ROWS} —{" "}
              <Link href="/signup" className="link">sign up free</Link> for a 14-day Premium trial of the full universe.
            </>
          )}
        </p>

        {/* Aggregate counts by tier — gives a snapshot of the universe at
            a glance and signals to crawlers that this is a data-rich page
            worth indexing. */}
        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <CountTile label="High conviction" count={counts.high} tone="bg-up/15 text-up" href="/signal/high-conviction" />
          <CountTile label="Strong setup" count={counts.strong} tone="bg-up/10 text-up/90" href="/signal/strong-setup" />
          <CountTile label="Constructive" count={counts.constructive} tone="bg-accent/15 text-accent" href="/signal/constructive" />
          <CountTile label="Neutral" count={counts.neutral} tone="bg-muted/20 text-muted" href="/signal/neutral" />
          <CountTile label="Caution" count={counts.caution} tone="bg-warn/15 text-warn" href="/signal/caution" />
          <CountTile label="Weak" count={counts.weak} tone="bg-down/15 text-down" href="/signal/weak" />
        </div>
        <p className="mt-3 text-xs text-subtle">
          Tap any tier to see every stock currently at that signal level, with the methodology behind the band.
        </p>
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
                {visibleItems.map((r) => (
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

        {/* Anonymous visitors get the conversion-shaped CTA right under the
            preview rows. Signed-in users get the lower-key 'want filters?'
            upsell instead. Two distinct asks — don't merge them. */}
        {!isSignedIn && hiddenCount > 0 ? (
          <div className="mt-6 overflow-hidden rounded-xl border border-accent/30 bg-gradient-to-br from-accent/10 via-panel to-panel">
            <div className="p-6 sm:p-8 text-center">
              <p className="eyebrow text-accent">{hiddenCount.toLocaleString()} more tickers behind the wall</p>
              <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
                Unlock the full universe — free for 14 days.
              </h2>
              <p className="mx-auto mt-3 max-w-xl text-sm text-muted">
                You&rsquo;re seeing the top {PREVIEW_ROWS} of {items.length.toLocaleString()} scored tickers.
                Your free account includes a 14-day Premium trial — the full live universe,
                no card, same public 6-factor formula on every row.
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-3">
                <Link href="/signup?next=/signals" className="btn-primary">
                  Try Premium free &rarr;
                </Link>
                <Link href="/pricing" className="btn-ghost">
                  See pricing
                </Link>
              </div>
              <p className="mt-4 text-xs text-subtle">
                Already have an account? <Link href="/signin?next=/signals" className="link">Sign in</Link>.
              </p>
            </div>
          </div>
        ) : null}

        <p className="mt-6 text-sm text-muted">
          <strong className="text-fg">Reading this page.</strong>{" "}
          <em>Score</em> is the composite 6-factor 0–100. <em>Signal</em> is the
          descriptive label per the band (HIGH CONVICTION ≥85, STRONG SETUP ≥70,
          CONSTRUCTIVE ≥55, NEUTRAL ≥40, CAUTION ≥25, WEAK &lt;25). <em>Conf</em>{" "}
          is per-ticker data confidence — mega-caps with full data coverage land
          80–95; less-followed names sit lower. None of the labels are
          prescriptive — see{" "}
          <Link href="/legal/risk" className="link">
            disclosure
          </Link>
          .
        </p>

        {/* Newsletter mid-funnel capture — anonymous + free users see this
            below the signup gate; paid users see it below the scanner CTA.
            Either way it's a lower-commitment funnel step. */}
        <section className="mt-8 rounded-xl border border-border bg-panel/40 p-6">
          <NewsletterCapture source="signals" heading="" sub="" />
        </section>

        {isSignedIn && (
          <div className="mt-8 rounded-xl border border-border bg-panel p-6">
            <p className="text-sm text-muted">
              Want to filter, sort, screen, and set alerts on these signals?
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              <Link href="/app/scanner" className="btn-primary">
                Open the live scanner &rarr;
              </Link>
              <Link href="/pricing" className="btn-ghost">
                See pricing
              </Link>
            </div>
          </div>
        )}
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
  href,
}: {
  label: string;
  count: number;
  tone: string;
  href: string;
}) {
  // Each tile links to its /signal/{slug} ranking page. This is the signal
  // cluster's hub-link: /signals (in the main nav + footer) now feeds crawl
  // equity down to all six per-signal-level pages, which were previously
  // only reachable via the sitemap and sibling cross-links.
  //
  // Hide a band tile when its count is 0. The momentum-tilted formula
  // currently never floats names into CAUTION (25–39) or WEAK (<25), so
  // those tiles were perpetually empty — a dead click that lands on a
  // 0-row ranking page. Suppressing the empty tile keeps the strip honest
  // (only shows bands users can actually drill into) without touching any
  // scoring code; the tile reappears automatically if the band ever fills.
  if (count === 0) return null;
  return (
    <Link
      href={href}
      className={`block rounded-md border border-border p-3 transition-colors hover:border-accent/60 ${tone}`}
    >
      <div className="text-xs uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-bold nums">{count}</div>
    </Link>
  );
}
