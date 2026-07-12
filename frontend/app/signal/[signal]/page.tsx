/**
 * Programmatic /signal/{label} landing pages.
 *
 * Each Tapeline signal label gets one indexable URL — landing page for
 * queries like "high conviction stock signals", "stocks scoring strong setup".
 * Pulls live tickers at that signal level from /api/scanner and renders a
 * snapshot ranking, methodology context, and FAQ.
 */
import Link from "next/link";
import { notFound } from "next/navigation";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, faqJsonLd, jsonLdScript } from "@/lib/jsonld";
import { SIGNALS } from "../signals";

// Render on-demand and cache for 5 minutes (ISR). Matches the per-fetch
// `revalidate: 3600` below and the "5-minute snapshot" contract, and keeps this
// route off the build-time critical path (see generateStaticParams).
export const revalidate = 3600;

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

type ScannerRow = {
  symbol: string;
  name: string;
  sector: string | null;
  score: number | null;
  signal: string | null;
  price: number | null;
  change_pct_1d: number | null;
};

async function fetchSignalTickers(signalLabel: string): Promise<ScannerRow[]> {
  try {
    const url = `${API_BASE}/api/scanner?${new URLSearchParams({
      signal: signalLabel,
      limit: "30",
      sort: "score",
      order: "desc",
    }).toString()}`;
    const res = await fetch(url, {
      next: { revalidate: 3600 },
      // Bound the fetch so a degraded backend can't hang the on-demand render
      // (this page is ISR, not build-time — see generateStaticParams). On
      // timeout we fall through to the [] fallback and render fast; ISR refills
      // the data within `revalidate` once the backend recovers.
      signal: AbortSignal.timeout(7000),
    });
    if (!res.ok) return [];
    const body = (await res.json()) as { items?: ScannerRow[] };
    return body.items ?? [];
  } catch {
    return [];
  }
}

// Deliberately NOT pre-rendered at build time — render on-demand (ISR) so a
// degraded backend can't blow the per-page build budget or get hammered by the
// build-time fetch fan-out. Discovery is unaffected: every /signal/{slug} URL is
// emitted in app/sitemap.ts. Mirrors /best-stocks-for, /blog/ticker, /t/[symbol].
export function generateStaticParams(): { signal: string }[] {
  return [];
}

export async function generateMetadata({ params }: { params: Promise<{ signal: string }> }) {
  const { signal: signalSlug } = await params;
  const signal = SIGNALS.find((s) => s.slug === signalSlug);
  if (!signal) {
    return pageMeta({
      title: "Signal not found — Tapeline",
      description: "Browse all signal labels at /how-it-works.",
      path: `/signal/${signalSlug}`,
    });
  }
  return pageMeta({
    title: `${signal.display} Stocks Today (Tapeline Score ${signal.range})`,
    description: `Live ranking of US stocks at the ${signal.display} signal level (Tapeline Score ${signal.range}). Sub-60s updates in US market hours, public 6-factor formula.`,
    path: `/signal/${signal.slug}`,
  });
}

function signalFaq(display: string, range: string, blurb: string) {
  return [
    {
      q: `What does the ${display} signal mean?`,
      a: `${display} maps to Tapeline Scores ${range}. ${blurb} Labels are descriptive — they describe the state of the underlying factor data, not buy/sell calls.`,
    },
    {
      q: `How is the ${display} list calculated?`,
      a: `Every US ticker in the active scanner universe (~2,500 by daily dollar-volume) is scored sub-60s using the public 6-factor weighted formula. Names whose composite score falls in the ${range} band get the ${display} label automatically. The list above shows the top names currently in this tier, sorted by score.`,
    },
    {
      q: `Should I buy ${display} stocks?`,
      a: `Tapeline doesn't issue buy or sell calls — we publish descriptive analytics, not investment advice. Whether a ${display} name fits your portfolio depends on your risk tolerance, time horizon, and tax situation. The ${display} label tells you the data is in a particular state, not what to do about it.`,
    },
    {
      q: `How often does the ${display} list update?`,
      a: `Underlying scores re-tick every minute during US market hours. This landing page caches the snapshot for 5 minutes to avoid hammering the API on every crawl; the in-app scanner shows live ticks.`,
    },
    {
      q: `Where can I see the ${display} historical track record?`,
      a: `The /scorecard page back-checks every top-10 daily pick against the next-day return vs SPY. Many of those picks come from the STRONG SETUP and HIGH CONVICTION tiers; the scorecard preserves every individual call for accountability.`,
    },
  ];
}

export default async function SignalPage({ params }: { params: Promise<{ signal: string }> }) {
  const { signal: signalSlug } = await params;
  const signal = SIGNALS.find((s) => s.slug === signalSlug);
  if (!signal) notFound();

  const tickers = await fetchSignalTickers(signal.display);
  const faq = signalFaq(signal.display, signal.range, signal.blurb);
  const url = `https://tapeline.io/signal/${signal.slug}`;

  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Signals", url: "https://tapeline.io/signals" },
    { name: signal.display, url },
  ]);

  // Tier-based color hint for the headline score chip.
  const tierColor =
    signal.slug === "high-conviction" || signal.slug === "strong-setup"
      ? "text-up"
      : signal.slug === "constructive"
        ? "text-accent"
        : signal.slug === "neutral"
          ? "text-muted"
          : signal.slug === "caution"
            ? "text-warn"
            : "text-down";

  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(faq))} />
      <MarketingNav />

      <article className="mx-auto max-w-4xl px-4 sm:px-6 py-8">
        {/* Visible breadcrumb — mirrors the BreadcrumbList JSON-LD */}
        <nav aria-label="Breadcrumb" className="text-xs text-subtle">
          <ol className="flex flex-wrap items-center gap-1.5">
            <li>
              <Link href="/" className="hover:text-accent">Tapeline</Link>
            </li>
            <li aria-hidden className="text-border">/</li>
            <li>
              <Link href="/signals" className="hover:text-accent">Signals</Link>
            </li>
            <li aria-hidden className="text-border">/</li>
            <li className="text-muted">{signal.display}</li>
          </ol>
        </nav>

        <p className="eyebrow mt-4">Signal level</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          <span className={`font-mono ${tierColor}`}>{signal.display}</span>{" "}
          <span className="text-muted">— stocks today</span>
        </h1>
        <p className="mt-4 text-lg text-muted">
          Score range <span className={`font-mono ${tierColor} nums`}>{signal.range}</span>.{" "}
          {signal.longDesc}
        </p>

        <section className="mt-10">
          {tickers.length === 0 ? (
            <div className="rounded-xl border border-border bg-panel p-8 text-center">
              <p className="text-muted">No live snapshot available right now.</p>
              <p className="mt-3 text-sm text-subtle">
                The {signal.display} list refreshes every 5 minutes — check back shortly. Or
                browse the{" "}
                <Link href="/scorecard" className="text-accent hover:underline">
                  full public scorecard
                </Link>
                .
              </p>
            </div>
          ) : (
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-panel text-xs uppercase text-muted">
                  <tr>
                    <th className="px-3 py-3 text-left">#</th>
                    <th className="px-3 py-3 text-left">Ticker</th>
                    <th className="px-3 py-3 text-left">Name</th>
                    <th className="px-3 py-3 text-left">Sector</th>
                    <th className="px-3 py-3 text-right">Score</th>
                    <th className="px-3 py-3 text-right">Price</th>
                    <th className="px-3 py-3 text-right">1d</th>
                  </tr>
                </thead>
                <tbody>
                  {tickers.map((t, i) => (
                    <tr key={t.symbol} className="border-b border-border/30 hover:bg-panel/40">
                      <td className="px-3 py-3 font-mono text-subtle">{i + 1}</td>
                      <td className="px-3 py-3 font-mono font-medium">
                        <Link href={`/t/${t.symbol}`} className="hover:text-accent">
                          {t.symbol}
                        </Link>
                      </td>
                      <td className="px-3 py-3 text-muted truncate max-w-[18ch]">{t.name}</td>
                      <td className="px-3 py-3 text-xs text-subtle truncate max-w-[14ch]">
                        {t.sector ?? "—"}
                      </td>
                      <td className={`px-3 py-3 text-right font-mono nums font-semibold ${tierColor}`}>
                        {t.score != null ? t.score.toFixed(0) : "—"}
                      </td>
                      <td className="px-3 py-3 text-right font-mono nums">
                        {t.price != null ? `$${t.price.toFixed(2)}` : "—"}
                      </td>
                      <td
                        className={`px-3 py-3 text-right font-mono nums ${
                          (t.change_pct_1d ?? 0) > 0
                            ? "text-up"
                            : (t.change_pct_1d ?? 0) < 0
                              ? "text-down"
                              : "text-muted"
                        }`}
                      >
                        {t.change_pct_1d != null
                          ? `${t.change_pct_1d > 0 ? "+" : ""}${t.change_pct_1d.toFixed(2)}%`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="mt-12 rounded-xl border border-border bg-panel/40 p-6">
          <h2 className="text-lg font-semibold">How {signal.display} is determined</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Every US ticker in the active scanner universe is scored sub-60s using the public
            six-factor composite:{" "}
            <strong>Trend, Relative Strength, Fundamentals, Smart Money, Macro, and Momentum —
            weighted most toward Trend and Relative Strength, least toward Momentum</strong>
            . Names whose composite score falls in the{" "}
            <span className={`font-mono ${tierColor}`}>{signal.range}</span> band get the{" "}
            <span className={`font-mono ${tierColor}`}>{signal.display}</span> label automatically.
            No human curation — the label transitions when the data does.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Read the full methodology on{" "}
            <Link href="/how-it-works" className="text-accent hover:underline">
              /how-it-works
            </Link>
            , or see the full label glossary at the bottom of that page.
          </p>
        </section>

        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">
            Frequently asked about {signal.display}
          </h2>
          <div className="mt-6 divide-y divide-border/60">
            {faq.map((item) => (
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

        <nav
          aria-label="Other signal levels"
          className="mt-12 rounded-xl border border-border bg-panel/40 p-6"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Other signal levels
          </h2>
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {SIGNALS.filter((s) => s.slug !== signal.slug).map((s) => (
              <Link
                key={s.slug}
                href={`/signal/${s.slug}`}
                className="text-muted hover:text-accent underline-offset-4 hover:underline"
              >
                {s.display} <span className="text-subtle nums">({s.range})</span>
              </Link>
            ))}
          </div>
        </nav>

        <p className="mt-10 text-xs text-subtle text-center">
          Snapshot cached 5 minutes. Sub-60s tick during market hours. Not investment advice — see{" "}
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
