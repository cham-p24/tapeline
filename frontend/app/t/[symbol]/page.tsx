/**
 * Public per-ticker share page at /t/[symbol].
 *
 * Lives outside /app so search engines can index it and unauthenticated
 * traders pasting links to friends actually see content. Shows the score,
 * signal, 6-factor breakdown, and the why sentence — paywalls news / charts /
 * alerts behind a sign-up CTA. The full deep-dive lives at /app/ticker/[symbol].
 *
 * Why this matters:
 *   1. SEO — every ticker becomes a landing page for "AAPL stock score" queries.
 *   2. Viral loop — existing users tweet $TICKER + a /t/TICKER link, the OG card
 *      (next to this file) shows the live score so the share previews self-sell.
 *   3. Trust — the public-formula moat needs a public surface to land on.
 */
import Link from "next/link";
import { notFound } from "next/navigation";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

type TickerData = {
  symbol: string;
  name: string;
  sector: string | null;
  asset_class: string;
  price: number | null;
  score: number | null;
  signal: string | null;
  confidence_pct: number | null;
  change_pct_1d: number | null;
  change_pct_5d: number | null;
  change_pct_1m: number | null;
  volume: number | null;
  reason: string | null;
  sub_trend?: number | null;
  sub_rs?: number | null;
  sub_fundamentals?: number | null;
  sub_smart_money?: number | null;
  sub_macro?: number | null;
  sub_momentum?: number | null;
};

async function fetchTicker(symbol: string): Promise<TickerData | null> {
  try {
    const res = await fetch(`${API_BASE}/api/ticker/${symbol.toUpperCase()}`, {
      // Cache for 60s — matches the worker tick cadence so the page is fresh
      // without hammering the API on every social-card crawl.
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return (await res.json()) as TickerData;
  } catch {
    return null;
  }
}

// Per-page metadata so each ticker page has its own title + description AND
// its own social-share text. The sibling opengraph-image.tsx auto-wires
// og:image — but og:title / og:description / twitter:title are inherited from
// the root layout unless we override them here.
export async function generateMetadata({ params }: { params: { symbol: string } }) {
  const sym = params.symbol.toUpperCase();
  const data = await fetchTicker(sym);
  if (!data) {
    return {
      title: `${sym} — not in scanner`,
      description: `${sym} is not currently in the Tapeline scanner universe.`,
    };
  }
  const score = data.score?.toFixed(0) ?? "—";
  const signal = data.signal ?? "—";
  const why = data.reason ?? "Six-factor synthesis updated live.";
  const title = `${sym} score ${score} · ${signal}`;
  const description = `Tapeline score ${score}/100 (${signal}) for ${data.name}. ${why} See the formula on /how-it-works.`;
  return {
    title,
    description,
    alternates: { canonical: `https://tapeline.io/t/${sym}` },
    openGraph: {
      title: `${sym} · ${score}/100 · ${signal}`,
      description: why,
      url: `https://tapeline.io/t/${sym}`,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: `${sym} · ${score}/100 · ${signal}`,
      description: why,
    },
  };
}

export default async function PublicTickerPage({ params }: { params: { symbol: string } }) {
  const sym = params.symbol.toUpperCase();
  const data = await fetchTicker(sym);

  if (!data) notFound();

  const score = data.score ?? 0;
  const signal = data.signal ?? "—";
  const change = data.change_pct_1d ?? 0;
  const changeColor = change > 0 ? "text-up" : change < 0 ? "text-down" : "text-muted";

  // Score-tier colours mirror /how-it-works.
  const scoreColor =
    score >= 70 ? "text-up" : score >= 55 ? "text-accent" : score >= 40 ? "text-muted" : score >= 25 ? "text-yellow-400" : "text-down";

  const factors: { label: string; value: number | null | undefined; weight: number }[] = [
    { label: "Trend",              value: data.sub_trend,        weight: 25 },
    { label: "Relative strength",  value: data.sub_rs,           weight: 20 },
    { label: "Fundamentals",       value: data.sub_fundamentals, weight: 15 },
    { label: "Smart money",        value: data.sub_smart_money,  weight: 15 },
    { label: "Macro",              value: data.sub_macro,        weight: 15 },
    { label: "Momentum",           value: data.sub_momentum,     weight: 10 },
  ];

  return (
    <main className="min-h-screen">
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-4 sm:px-6 py-8 sm:py-12">
        {/* Header row */}
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h1 className="text-4xl sm:text-5xl font-bold tracking-tight nums">{data.symbol}</h1>
              <span className="text-sm sm:text-base text-muted truncate max-w-full">{data.name}</span>
            </div>
            <div className="mt-2 flex items-center gap-3 text-xs sm:text-sm text-muted">
              {data.sector && <span>{data.sector}</span>}
              {data.asset_class && <span className="text-subtle">·</span>}
              {data.asset_class && <span className="capitalize">{data.asset_class}</span>}
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <div className="text-2xl sm:text-3xl font-bold nums">
              {data.price != null ? `$${data.price.toFixed(2)}` : "—"}
            </div>
            {data.change_pct_1d != null && (
              <div className={`text-sm font-medium nums ${changeColor}`}>
                {change >= 0 ? "+" : ""}
                {change.toFixed(2)}% today
              </div>
            )}
          </div>
        </div>

        {/* Score + signal hero */}
        <div className="mt-8 sm:mt-10 rounded-2xl border border-border bg-panel p-5 sm:p-8">
          <div className="flex flex-wrap items-end gap-6 sm:gap-8">
            <div>
              <div className="text-xs uppercase tracking-wider text-muted">Tapeline score</div>
              <div className={`mt-1 text-6xl sm:text-7xl font-bold nums tracking-tight ${scoreColor}`}>
                {data.score != null ? data.score.toFixed(0) : "—"}
                <span className="ml-1 text-xl sm:text-2xl text-muted font-medium">/ 100</span>
              </div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wider text-muted">Signal</div>
              <div className={`mt-1 text-xl sm:text-2xl font-bold tracking-tight ${scoreColor}`}>{signal}</div>
              {data.confidence_pct != null && (
                <div className="mt-1 text-xs text-muted">
                  {data.confidence_pct.toFixed(0)}% data confidence
                </div>
              )}
            </div>
          </div>
          {data.reason && (
            <p className="mt-6 max-w-2xl text-sm sm:text-base leading-relaxed text-fg">{data.reason}</p>
          )}
        </div>

        {/* 6-factor breakdown */}
        <h2 className="mt-10 sm:mt-12 text-sm font-semibold uppercase tracking-wider text-muted">
          Score breakdown · public formula
        </h2>
        <div className="mt-4 space-y-2">
          {factors.map((f) => (
            <div key={f.label} className="flex items-center gap-3 sm:gap-4 rounded-lg border border-border bg-panel/40 px-3 sm:px-4 py-3">
              <div className="w-28 sm:w-44 flex-shrink-0">
                <div className="text-xs sm:text-sm font-medium truncate">{f.label}</div>
                <div className="text-[10px] uppercase tracking-wider text-subtle">{f.weight}% weight</div>
              </div>
              <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-background">
                <div
                  className="h-full bg-gradient-to-r from-accent to-accent2"
                  style={{ width: `${f.value != null ? Math.max(0, Math.min(100, f.value)) : 0}%` }}
                />
              </div>
              <div className="w-10 sm:w-12 text-right font-medium nums tabular-nums text-sm sm:text-base">
                {f.value != null ? f.value.toFixed(0) : "—"}
              </div>
            </div>
          ))}
        </div>

        <p className="mt-4 text-xs text-muted">
          Weights are public and never change without a changelog entry.
          Read the full methodology on <Link href="/how-it-works" className="text-accent hover:underline">/how-it-works</Link>.
        </p>

        {/* CTA */}
        <div className="mt-10 sm:mt-12 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-5 sm:p-8">
          <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">See {sym} in the live scanner</h2>
          <p className="mt-2 max-w-xl text-sm text-muted">
            Free signup gives you the score for the top 20 tickers, 24-hour delayed.
            14-day Premium trial unlocks the full ~870-ticker live universe, smart alerts, congressional trades, and elite-fund 13F holdings.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href={`/signup?next=${encodeURIComponent(`/app/ticker/${sym}`)}`} className="btn-accent">
              Start 14-day Premium trial →
            </Link>
            <Link href="/scorecard" className="btn-ghost">
              See the public scorecard
            </Link>
            {/* Pre-filled tweet so existing users can spread per-ticker links
                in one click. Twitter will fetch the OG card and render the
                live score preview underneath. */}
            <a
              href={`https://twitter.com/intent/tweet?${new URLSearchParams({
                text: `$${sym} score: ${score.toFixed(0)}/100 (${signal})\n\nTransparent 6-factor formula, public scorecard.`,
                url: `https://tapeline.io/t/${sym}`,
              }).toString()}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost inline-flex items-center gap-2"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
              </svg>
              Share on X
            </a>
          </div>
        </div>

        {/* Trust line */}
        <p className="mt-10 text-xs text-subtle text-center">
          Score updated live (sub-60s). Public formula. Public scorecard.
          Not investment advice — see <Link href="/legal/risk" className="text-accent hover:underline">risk disclosure</Link>.
        </p>
      </section>

      <MarketingFooter />
    </main>
  );
}
