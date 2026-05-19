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
import { ScoreRadial } from "@/components/ScoreRadial";
import { ScoreSparkline } from "@/components/ScoreSparkline";
import {
  breadcrumbJsonLd,
  faqJsonLd,
  jsonLdScript,
  tickerReviewJsonLd,
} from "@/lib/jsonld";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

type FactorEntry = { value: number | null; weight: number; label: string };

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
  // The /api/ticker/{symbol} endpoint returns sub-factor values nested
  // inside `breakdown.<key>.value`, NOT as top-level sub_* fields. The
  // page initially assumed the flat shape and rendered every bar at 0%.
  breakdown?: {
    trend?: FactorEntry;
    rs?: FactorEntry;
    fundamentals?: FactorEntry;
    smart_money?: FactorEntry;
    macro?: FactorEntry;
    momentum?: FactorEntry;
  };
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

// Per-page metadata so each ticker page has its own title + description and
// its own social-share text. The sibling opengraph-image.tsx auto-wires
// og:image. The root layout's title.template is "%s" so the brand suffix
// in the title here is NOT double-applied.
export async function generateMetadata({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const sym = symbol.toUpperCase();
  const data = await fetchTicker(sym);
  if (!data) {
    return {
      title: `${sym} — Not in Scanner Universe · Tapeline`,
      description: `${sym} is not currently in the Tapeline scanner universe. Browse covered tickers or explore the scoring methodology.`,
      alternates: { canonical: `https://tapeline.io/t/${sym}` },
      robots: { index: false, follow: true },
    };
  }
  const score = data.score?.toFixed(0) ?? "—";
  const signal = data.signal ?? "—";
  const why = data.reason ?? "Six-factor synthesis updated live.";
  const title = `${sym} Stock Score ${score}/100 · ${signal} · Tapeline`;
  // Long-tail-friendly description hits queries traders actually run:
  // "TICKER stock score", "TICKER analysis", "TICKER technical rating", etc.
  // The Finviz-alternative phrasing at the end is deliberate — GSC shows a
  // strong "[ticker] finviz" pattern (snowflake finviz, clrb finviz, auud
  // finviz, etc.) across the ~2,500-ticker universe. Mentioning "free
  // Finviz alternative" in the description lets every per-ticker page
  // compete for "${sym} finviz" without keyword stuffing the title.
  // Keeps copy honest (no return claims, descriptive not prescriptive).
  const description = `Tapeline Score ${score}/100 (${signal}) for ${data.name} (${sym}). ${why} 6-factor quantitative analysis: trend, relative strength, fundamentals, smart money, macro, momentum. A free Finviz alternative for ${sym} — public formula, back-checked scorecard, live updates.`;
  // Keyword set for crawlers — narrow, ticker-specific, no spam stuffing.
  // Finviz keywords added 2026-05-19: GSC shows ~half a dozen "{ticker}
  // finviz" queries per 90 days where we already accidentally rank but
  // weren't explicitly targeting. Per-ticker keyword inclusion makes that
  // an intentional surface.
  const keywords = [
    `${sym} stock score`,
    `${sym} stock analysis`,
    `${sym} ${data.name}`,
    `${sym} technical rating`,
    `${sym} fundamental analysis`,
    `is ${sym} a buy`,
    `${sym} finviz`,
    `${sym} finviz alternative`,
    "Tapeline Score",
    "stock scanner",
    "Finviz alternative",
  ];
  const url = `https://tapeline.io/t/${sym}`;
  return {
    title,
    description,
    keywords,
    alternates: { canonical: url },
    openGraph: {
      title: `${sym} · ${score}/100 · ${signal}`,
      description: why,
      url,
      type: "website",
      siteName: "Tapeline",
      locale: "en_US",
    },
    twitter: {
      card: "summary_large_image",
      title: `${sym} · ${score}/100 · ${signal}`,
      description: why,
      site: "@tapeline_io",
    },
    other: {
      "article:modified_time": new Date().toISOString(),
      "article:section": "Stocks",
    },
  };
}

// On-page FAQ — kept short, real questions a trader asks when landing on a
// ticker page from search. The same items feed the FAQPage JSON-LD below
// (Google's rich-result eligibility requires the schema to mirror visible
// page content). Answers are templated on the ticker but score/signal are
// pulled live so they always reflect what's rendered above.
function buildFaq(sym: string, name: string, score: string, signal: string): { q: string; a: string }[] {
  return [
    {
      q: `What is the Tapeline Score for ${sym}?`,
      a: `${sym} (${name}) currently scores ${score}/100 with the signal label ${signal}. The score is a weighted blend of six quantitative factors and updates sub-60 seconds during US market hours.`,
    },
    {
      q: `How is ${sym}'s score calculated?`,
      a: `The Tapeline Score is a transparent weighted sum: 25% Trend, 20% Relative Strength, 15% Fundamentals, 15% Smart Money, 15% Macro, 10% Momentum. Each sub-score is normalised to 0-100 and the exact formula is published on /how-it-works.`,
    },
    {
      q: `Is ${sym} a buy?`,
      a: `Tapeline doesn't issue buy or sell calls — we publish descriptive analytics, not investment advice. The signal label ${signal} describes the current state of the data; whether ${sym} fits your portfolio depends on your risk tolerance, time horizon, and tax situation. See the risk disclosure for details.`,
    },
    {
      q: `How often does the ${sym} score update?`,
      a: `${sym}'s score re-ticks every minute during US market hours and persists between sessions. Price and momentum data refresh sub-60s; fundamentals refresh on company filing cadence; insider Form 4 within hours of SEC filing.`,
    },
    {
      q: `Where can I see the historical track record for Tapeline scores?`,
      a: `Every Tapeline top-10 daily pick is auto-published with the next-day return vs SPY at /scorecard. The scorecard is immutable — every call is preserved with its original context for accountability.`,
    },
  ];
}

export default async function PublicTickerPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const sym = symbol.toUpperCase();
  const data = await fetchTicker(sym);

  if (!data) notFound();

  const score = data.score ?? 0;
  const signal = data.signal ?? "—";
  const change = data.change_pct_1d ?? 0;
  const changeColor = change > 0 ? "text-up" : change < 0 ? "text-down" : "text-muted";

  // Score-tier colours mirror /how-it-works.
  const scoreColor =
    score >= 70 ? "text-up" : score >= 55 ? "text-accent" : score >= 40 ? "text-muted" : score >= 25 ? "text-warn" : "text-down";

  const b = data.breakdown ?? {};
  const factors: { label: string; value: number | null | undefined; weight: number }[] = [
    { label: "Trend",              value: b.trend?.value,        weight: 25 },
    { label: "Relative strength",  value: b.rs?.value,           weight: 20 },
    { label: "Fundamentals",       value: b.fundamentals?.value, weight: 15 },
    { label: "Smart money",        value: b.smart_money?.value,  weight: 15 },
    { label: "Macro",              value: b.macro?.value,        weight: 15 },
    { label: "Momentum",           value: b.momentum?.value,     weight: 10 },
  ];

  // Structured data — three graphs inlined in the body. Google parses
  // JSON-LD anywhere in the HTML; placing them in body avoids the React
  // "scripts in head" hydration warnings.
  const faqItems = buildFaq(
    data.symbol,
    data.name,
    data.score?.toFixed(0) ?? "—",
    data.signal ?? "—",
  );
  const url = `https://tapeline.io/t/${data.symbol}`;
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Tickers", url: "https://tapeline.io/scorecard" },
    { name: `${data.symbol} (${data.name})`, url },
  ]);
  const review = tickerReviewJsonLd({
    symbol: data.symbol,
    name: data.name,
    url,
    score: data.score,
    signal: data.signal,
    why: data.reason,
  });

  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(review)} />
      <script {...jsonLdScript(faqJsonLd(faqItems))} />
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

        {/* Score + signal hero — radial visual signature on the right gives
            the score a *shape*, not just a number. Same role Simply Wall St's
            Snowflake plays for theirs. Each axis is one factor; lopsided
            polygons read as "strong on X, weak on Y" at a glance. */}
        <div className="mt-8 sm:mt-10 rounded-2xl border border-border bg-panel p-5 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-6 sm:gap-8">
            <div className="min-w-0 flex-1">
              <div className="text-xs uppercase tracking-wider text-muted">Tapeline Score</div>
              <div className={`mt-1 text-6xl sm:text-7xl font-bold nums tracking-tight ${scoreColor}`}>
                {data.score != null ? data.score.toFixed(0) : "—"}
                <span className="ml-1 text-xl sm:text-2xl text-muted font-medium">/ 100</span>
              </div>
              <div className="mt-4">
                <div className="text-xs uppercase tracking-wider text-muted">Signal</div>
                <div className={`mt-1 text-xl sm:text-2xl font-bold tracking-tight ${scoreColor}`}>{signal}</div>
                {data.confidence_pct != null && (
                  <div className="mt-1 text-xs text-muted">
                    {data.confidence_pct.toFixed(0)}% data confidence
                  </div>
                )}
              </div>
              {data.reason && (
                <p className="mt-6 max-w-xl text-sm sm:text-base leading-relaxed text-fg">{data.reason}</p>
              )}
            </div>
            <div className="hidden sm:block flex-shrink-0">
              <ScoreRadial
                trend={b.trend?.value ?? null}
                rs={b.rs?.value ?? null}
                fundamentals={b.fundamentals?.value ?? null}
                smart_money={b.smart_money?.value ?? null}
                macro={b.macro?.value ?? null}
                momentum={b.momentum?.value ?? null}
                score={data.score ?? null}
                size={220}
              />
            </div>
          </div>
          {/* Mobile-only radial — placed below the score so it doesn't
              fight for header space on narrow viewports. */}
          <div className="mt-6 flex justify-center sm:hidden">
            <ScoreRadial
              trend={b.trend?.value ?? null}
              rs={b.rs?.value ?? null}
              fundamentals={b.fundamentals?.value ?? null}
              smart_money={b.smart_money?.value ?? null}
              macro={b.macro?.value ?? null}
              momentum={b.momentum?.value ?? null}
              score={data.score ?? null}
              size={200}
            />
          </div>
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

        {/* Score history sparkline — sparse trace from the daily scorecard.
            Shows nothing for tickers that haven't hit top-10, and renders
            a friendly empty state explaining why. */}
        <div className="mt-8">
          <ScoreSparkline symbol={data.symbol} days={60} />
        </div>

        {/* CTA */}
        <div className="mt-10 sm:mt-12 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-5 sm:p-8">
          <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">See {sym} in the live scanner</h2>
          <p className="mt-2 max-w-xl text-sm text-muted">
            Free signup gives you the score for the top 20 tickers, 24-hour delayed.
            14-day Premium trial unlocks the full ~2,500-ticker live universe, smart alerts, congressional trades, and recent insider buys (SEC Form 4).
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href={`/signup?next=${encodeURIComponent(`/app/ticker/${sym}`)}`} className="btn-accent">
              Try Premium free for 14 days →
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

        {/* FAQ — visible content that mirrors the FAQPage JSON-LD above.
            Hits the long-tail "{TICKER} stock score", "is {TICKER} a buy",
            "how is {TICKER} scored" queries that traders actually search. */}
        <section className="mt-12 sm:mt-16">
          <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">
            Frequently asked about {data.symbol}
          </h2>
          <div className="mt-6 divide-y divide-border/60">
            {faqItems.map((item) => (
              <details key={item.q} className="group py-4">
                <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
                  <h3 className="text-sm sm:text-base font-medium">{item.q}</h3>
                  <span className="text-muted transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-3 text-sm text-muted leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* Internal links to companion product surfaces — gives the page
            real outbound link equity instead of a single CTA, and lets
            crawlers reach the methodology + scorecard from every ticker. */}
        <nav className="mt-12 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted" aria-label="Related Tapeline pages">
          <Link href="/how-it-works" className="hover:text-fg underline-offset-4 hover:underline">
            How {data.symbol} is scored
          </Link>
          <Link href="/scorecard" className="hover:text-fg underline-offset-4 hover:underline">
            Public scorecard
          </Link>
          <Link href="/compare/finviz" className="hover:text-fg underline-offset-4 hover:underline">
            Tapeline vs Finviz
          </Link>
          <Link href="/compare/zacks" className="hover:text-fg underline-offset-4 hover:underline">
            Tapeline vs Zacks
          </Link>
          <Link href="/blog" className="hover:text-fg underline-offset-4 hover:underline">
            Methodology blog
          </Link>
        </nav>

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
