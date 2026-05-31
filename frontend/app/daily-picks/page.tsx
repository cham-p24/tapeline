/**
 * /daily-picks — public sample of what newsletter subscribers receive.
 *
 * Conversion-funnel role: the highest-leverage lead-magnet landing page.
 *
 *   - Targets commercial-investigation queries like "free daily stock picks",
 *     "daily top 10 stocks", "stock newsletter daily picks".
 *   - Shows exactly what the email digest delivers — 10 highest-scoring US
 *     tickers with score / signal / one-sentence read — using the same data
 *     anyone can see on /scorecard, just framed as "what you'd get in your
 *     inbox tomorrow."
 *   - Newsletter capture form is the primary CTA (no trial-or-bounce
 *     pressure).
 *   - Trial CTA is secondary, below the picks.
 *
 * Why this is distinct from /scorecard:
 *   /scorecard is the back-checked TRACK RECORD (logged picks + next-day
 *   returns + alpha vs SPY). /daily-picks is TODAY'S TOP 10 + the value
 *   prop for the recurring email. Different SERP intent, different CTA
 *   placement, different content.
 *
 * Data source: /api/scanner anonymously (returns the FREE tier — top 20
 * by score, 24-hour delayed). We take 10. Same data we put in the email.
 *
 * Caching: 30-min ISR so we're not hammering the backend on every crawler
 * hit, but the page stays fresh enough to feel "today's picks."
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";

// Refresh every 30 min — backend free-tier data is 24-hour delayed
// anyway, so sub-minute freshness is wasted budget.
export const revalidate = 1800;

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

export const metadata = pageMeta({
  title: "Free Daily Stock Picks — Tapeline Daily Top 10 (no card)",
  description:
    "Get the Tapeline daily Top 10 picks free in your inbox each US market morning. The 10 highest-scoring US tickers from a public 6-factor composite, one-sentence read on each. No credit card. Unsubscribe in one click.",
  path: "/daily-picks",
});

type ScannerRow = {
  symbol: string;
  name: string;
  sector: string | null;
  score: number | null;
  signal: string | null;
  price: number | null;
  change_pct_1d: number | null;
  reason: string | null;
};

async function fetchTopTen(): Promise<ScannerRow[]> {
  try {
    // Anonymous request returns FREE tier — top 20 by score with 24h
    // delay. We slice to 10 to match the email digest exactly.
    const res = await fetch(`${API_BASE}/api/scanner?limit=20`, {
      next: { revalidate: 1800 },
    });
    if (!res.ok) return [];
    const body = (await res.json()) as { items?: ScannerRow[] };
    return (body.items || []).slice(0, 10);
  } catch {
    return [];
  }
}

const FAQ_ITEMS = [
  {
    q: "How much does the daily Top 10 email cost?",
    a: "Free. No card, no trial, no upsell to read it. Unsubscribe in one click from the link in every email.",
  },
  {
    q: "How are the picks chosen?",
    a: "The 10 highest-scoring tickers from the Tapeline composite — a 0-100 blend of Trend (25%), Relative Strength (20%), Fundamentals (15%), Smart Money (15%), Macro (15%), Momentum (10%). Same formula at /how-it-works, no hidden multipliers.",
  },
  {
    q: "When does the email send?",
    a: "Each US market morning (Mon-Fri), at 13:00 UTC — about 9 AM ET, just before the open. So you read the picks before the bell rings.",
  },
  {
    q: "Is this investment advice?",
    a: "No. Tapeline is a quantitative data tool. The scores are descriptive readings of the tape (HIGH CONVICTION / STRONG SETUP / CONSTRUCTIVE / NEUTRAL / CAUTION / WEAK), never prescriptive (“BUY” / “SELL”). Tapeline operates under the publisher exemption from AFSL requirements.",
  },
  {
    q: "How is this different from the public scorecard?",
    a: "The scorecard is the back-checked TRACK RECORD — every picks day logged with next-day returns vs SPY at tapeline.io/scorecard. The daily email is TODAY'S PICKS in your inbox before the open. Different surface, same composite.",
  },
];

export default async function DailyPicksPage() {
  const picks = await fetchTopTen();
  // ISR fallback for crawlers — if the API is mid-deploy or down, show
  // the page anyway with an explanatory copy block in place of the
  // picks table. Better than a 500.
  const hasPicks = picks.length > 0;

  return (
    <main className="relative min-h-screen overflow-x-hidden">
      <MarketingNav />

      <section className="px-6 pt-12 pb-10 sm:pt-20 sm:pb-12">
        <div className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-panel px-3 py-1 text-xs text-muted">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" />
            Free · no card · unsubscribe one click
          </div>
          <h1 className="mt-6 text-4xl font-bold tracking-tight sm:text-5xl">
            Free daily stock picks,
            <br />
            <span className="text-accent">in your inbox before the open.</span>
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-lg text-muted leading-relaxed">
            The Tapeline daily Top 10 — 10 highest-scoring US tickers from a{" "}
            <Link href="/how-it-works" className="text-accent hover:underline">
              public 6-factor composite
            </Link>
            , one-sentence read on each, sent each US market morning.
          </p>

          <div className="mx-auto mt-8 max-w-md">
            <NewsletterCapture source="homepage" heading="" sub="" />
          </div>
          <p className="mt-3 text-xs text-muted">
            Same numbers anyone can read on{" "}
            <Link href="/scorecard" className="hover:text-fg underline-offset-2 hover:underline">
              the public scorecard
            </Link>
            .
          </p>
        </div>
      </section>

      <section className="border-y border-border/60 bg-panel/20 py-10 sm:py-14">
        <div className="mx-auto max-w-3xl px-6">
          <div className="mb-6 flex items-end justify-between">
            <div>
              <p className="eyebrow text-accent">Today&rsquo;s preview</p>
              <h2 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">
                The Top 10 right now
              </h2>
              <p className="mt-2 text-sm text-muted">
                Free-tier view (24-hour delayed). Email subscribers get the
                same picks, fresher.
              </p>
            </div>
            <Link
              href="/scorecard"
              className="text-sm text-accent hover:underline whitespace-nowrap"
            >
              Track record →
            </Link>
          </div>

          {hasPicks ? (
            <div className="overflow-hidden rounded-lg border border-border bg-bg">
              <table className="w-full text-sm">
                <thead className="bg-panel/60">
                  <tr className="text-xs uppercase tracking-wider text-muted">
                    <th className="px-3 py-3 text-left font-medium">#</th>
                    <th className="px-3 py-3 text-left font-medium">Ticker</th>
                    <th className="px-3 py-3 text-right font-medium">Score</th>
                    <th className="hidden px-3 py-3 text-left font-medium sm:table-cell">
                      Read
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {picks.map((p, i) => {
                    const score = p.score == null ? "—" : Math.round(p.score);
                    const signal = (p.signal || "").toUpperCase();
                    const reason = (p.reason || "").trim();
                    return (
                      <tr key={p.symbol} className="hover:bg-panel/40">
                        <td className="px-3 py-3 text-muted">#{i + 1}</td>
                        <td className="px-3 py-3">
                          <Link
                            href={`/t/${p.symbol}`}
                            className="font-semibold text-fg hover:text-accent"
                          >
                            ${p.symbol}
                          </Link>
                          <div className="text-xs text-muted truncate max-w-[180px]">
                            {(p.name || p.symbol).slice(0, 40)}
                          </div>
                        </td>
                        <td className="px-3 py-3 text-right">
                          <div className="font-mono text-base font-semibold text-fg">
                            {score}
                          </div>
                          <div className="text-[10px] uppercase tracking-wider text-muted">
                            {signal || "—"}
                          </div>
                        </td>
                        <td className="hidden px-3 py-3 text-muted sm:table-cell">
                          {reason ? (
                            reason.length > 90 ? reason.slice(0, 87) + "…" : reason
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-bg px-6 py-10 text-center text-sm text-muted">
              <p>Picks loading. The page caches every 30 minutes — refresh shortly.</p>
              <p className="mt-2">
                Or read the back-checked record at{" "}
                <Link href="/scorecard" className="text-accent hover:underline">
                  /scorecard
                </Link>
                .
              </p>
            </div>
          )}

          <div className="mt-8 text-center">
            <p className="text-sm text-muted leading-relaxed">
              Want this every morning?
            </p>
            <div className="mx-auto mt-3 max-w-md">
              <NewsletterCapture source="homepage" heading="" sub="" />
            </div>
          </div>
        </div>
      </section>

      <section className="py-10 sm:py-14">
        <div className="mx-auto max-w-3xl px-6">
          <p className="eyebrow text-accent">What you get</p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
            One email. One minute. Same composite as the public scorecard.
          </h2>

          <div className="mt-8 grid gap-6 sm:grid-cols-3">
            <div>
              <div className="text-3xl font-bold text-accent">10</div>
              <h3 className="mt-2 font-semibold text-fg">Picks per day</h3>
              <p className="mt-1 text-sm text-muted leading-relaxed">
                The 10 highest-scoring US tickers from the live composite,
                ranked. Same set, ranked by composite, every morning.
              </p>
            </div>
            <div>
              <div className="text-3xl font-bold text-accent">6</div>
              <h3 className="mt-2 font-semibold text-fg">Factors per score</h3>
              <p className="mt-1 text-sm text-muted leading-relaxed">
                Trend, RS, Fundamentals, Smart Money, Macro, Momentum — weighted
                at <Link href="/how-it-works" className="text-accent hover:underline">published rates</Link> and back-checked
                vs SPY every day.
              </p>
            </div>
            <div>
              <div className="text-3xl font-bold text-accent">$0</div>
              <h3 className="mt-2 font-semibold text-fg">No card, ever</h3>
              <p className="mt-1 text-sm text-muted leading-relaxed">
                The daily email is free. If you ever want live scoring, watchlist
                alerts, or the full universe, the trial is one click away — no
                pressure.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-border/60 bg-panel/10 py-10 sm:py-14">
        <div className="mx-auto max-w-3xl px-6">
          <p className="eyebrow text-accent">Common questions</p>
          <div className="mt-6 divide-y divide-border/60">
            {FAQ_ITEMS.map((item) => (
              <details key={item.q} className="group py-4">
                <summary className="flex cursor-pointer items-start justify-between gap-4 list-none">
                  <h3 className="text-sm font-medium text-fg">{item.q}</h3>
                  <span className="mt-0.5 text-muted transition-transform group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="mt-3 text-sm text-muted leading-relaxed">
                  {item.a}
                </p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="py-10 sm:py-14 text-center">
        <div className="mx-auto max-w-2xl px-6">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Want the same composite, live and on your own watchlist?
          </h2>
          <p className="mt-3 text-muted">
            14-day Premium trial — no card. The daily email keeps coming
            either way.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="btn-primary text-base">
              Try Premium free &rarr;
            </Link>
            <Link href="/pricing" className="btn-ghost text-base">
              See pricing
            </Link>
          </div>
        </div>
      </section>

      <script {...jsonLdScript(faqJsonLd(FAQ_ITEMS))} />

      <MarketingFooter />
    </main>
  );
}
