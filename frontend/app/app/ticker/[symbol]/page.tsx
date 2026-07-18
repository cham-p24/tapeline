"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type TickerDetail, TierGateError, LookupLimitError, errorMessage } from "@/lib/api";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { LiveBadge } from "@/components/LiveBadge";
import { useLiveStream } from "@/lib/useLiveStream";
import { recordTickerVisit } from "@/components/RecentTickers";
import { AnalystRatings } from "@/components/AnalystRatings";
import { FinancialsTab } from "@/components/FinancialsTab";
import { InsiderTab } from "@/components/InsiderTab";
import { Paywall, PaywallModal } from "@/components/Paywall";
import { LookupWall } from "@/components/LookupWall";
import { ScoreRadial } from "@/components/ScoreRadial";
import { ScoreSparkline } from "@/components/ScoreSparkline";
import { useCountUp } from "@/lib/useCountUp";
import { formatAbsolute, formatRelativeOrAbsolute } from "@/lib/datetime";
import { EarningsPill } from "@/components/EarningsPill";
import { useEarningsCalendar } from "@/lib/useEarningsCalendar";
import { trackEvent, trackFirstTickerAdded } from "@/lib/gtag";

type DetailTab = "financials" | "insider";

/**
 * Freemium daily look-up meter, returned by GET /api/ticker/{symbol} alongside
 * the ticker payload.
 *
 * `null` for anonymous callers (not metered on that endpoint). `limit: null`
 * is the UNLIMITED sentinel — paid tier, active no-card trial, or a brand-new
 * account inside its first-session grace window.
 *
 * Read structurally off the response rather than from the shared TickerDetail
 * type: lib/api.ts is outside this change's file lane. Folding `lookups` into
 * TickerDetail is the follow-up.
 */
export type LookupMeter = {
  used: number;
  limit: number | null;
  remaining: number | null;
  resets_at: string | null;
};

/**
 * Show the meter once this few look-ups remain. Chosen so a 12/day free user
 * sees it on look-ups 9-12 — enough runway to understand the limit and decide,
 * rather than meeting it for the first time as a 402 wall.
 */
export const LOOKUP_METER_REMAINING_THRESHOLD = 3;

/**
 * Calm, factual statement of the user's OWN look-up usage.
 *
 * Compliance (docs/COMPLIANCE_COPY_RULES.md R6): this is permitted because it
 * reports a real, first-party count — but it must never be dressed as
 * pressure. Deliberately: muted/border-only styling with NO red, warn or down
 * tones, no progress bar filling toward a threat, no countdown, no "only N
 * left" / "running out" phrasing, no exclamation. It states the count, states
 * what the plans do (R1: describes the product, never a market outcome), and
 * stops.
 *
 * Renders nothing when the caller is unmetered or still has runway, so the
 * page is unchanged for everyone except a free user approaching the cap.
 */
export function LookupMeterPill({
  used,
  limit,
  remaining,
}: {
  used: number;
  limit: number | null;
  remaining: number | null;
}) {
  // Unmetered caller (paid / trial / first-session grace) — nothing to report.
  if (limit == null || remaining == null) return null;
  if (remaining > LOOKUP_METER_REMAINING_THRESHOLD) return null;

  return (
    <div
      role="status"
      data-testid="lookup-meter"
      aria-label="Your daily look-up count"
      className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-border bg-panel px-3 py-2 text-xs text-muted"
    >
      <span className="nums font-medium text-fg">
        Look-up {used} of {limit} today
      </span>
      <span aria-hidden="true">·</span>
      <span>
        The free plan includes {limit} detailed look-ups a day, and the count
        resets tomorrow. Paid plans are not metered.
      </span>
      <Link href="/pricing" className="text-accent hover:underline">
        Compare plans
      </Link>
    </div>
  );
}

export default function TickerPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol: rawSymbol } = use(params);
  const symbol = rawSymbol.toUpperCase();
  const [data, setData] = useState<TickerDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Set when GET /api/ticker returns 402 (free/anon daily look-up cap). When
  // present we render the LookupWall instead of ticker data or the generic
  // error card. Pro/Premium/active-trial users are unlimited and never hit this.
  const [lookupLimit, setLookupLimit] = useState<LookupLimitError | null>(null);
  const [adding, setAdding] = useState(false);
  const [addMsg, setAddMsg] = useState<string | null>(null);
  // Server's watchlist-cap message when the add 403s. Non-null opens the
  // upgrade modal — same treatment as the scanner star.
  const [capMsg, setCapMsg] = useState<string | null>(null);
  const [newsAlerting, setNewsAlerting] = useState(false);
  const [newsAlertMsg, setNewsAlertMsg] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("financials");
  // Upcoming-earnings lookup for the header pill. 14-day window matches the
  // earnings page; non-fatal if it fails (pill just won't show).
  const earningsBySymbol = useEarningsCalendar(14);

  const load = useCallback(async () => {
    try {
      setData(await api.ticker(symbol));
      setError(null);
      setLookupLimit(null);
    } catch (e: unknown) {
      // 402 → free/anon daily look-up cap. Render the LookupWall (upgrade or
      // sign-up variant) instead of the generic error card. Clear any stale
      // data so the wall replaces the ticker rather than overlaying it.
      if (e instanceof LookupLimitError) {
        setLookupLimit(e);
        setData(null);
        setError(null);
        return;
      }
      setError(errorMessage(e));
    }
  }, [symbol]);

  useEffect(() => { load(); }, [load]);
  // Track this visit so it appears in the "Recent" pill row across the app.
  useEffect(() => { recordTickerVisit(symbol); }, [symbol]);
  // GA4 engagement event — declared in lib/gtag.ts but never fired until now,
  // so ticker-detail depth was invisible in the funnel. Re-fires per symbol
  // (each is a distinct view), fire-and-forget.
  useEffect(() => { trackEvent("view_ticker", { symbol }); }, [symbol]);
  const { status, lastUpdate } = useLiveStream(load);
  // Score count-up — called unconditionally here, before the loading/error
  // early-returns below, so the hook count never changes between renders
  // (react-hooks/rules-of-hooks). `data` is null while loading, so pass null
  // and let useCountUp no-op until the score lands. Snaps (not re-animates)
  // on the 60s live refresh; ×10 keeps the one-decimal precision on an int.
  const animatedScoreX10 = useCountUp(
    data?.score != null ? Math.round(data.score * 10) : null,
  );

  async function addWatch() {
    setAdding(true);
    setAddMsg(null);
    try {
      await api.watchlistAdd(symbol);
      // Activation signal, shared with the scanner rows + watchlist page so
      // the first add counts exactly once per browser regardless of surface.
      trackFirstTickerAdded(symbol, "ticker");
      setAddMsg(`${symbol} added to watchlist`);
    } catch (e: unknown) {
      // 403 = server-enforced watchlist cap. Open the upgrade modal with the
      // backend's real cap message instead of a terse failure line.
      if (e instanceof TierGateError) {
        setCapMsg(e.message);
        setAdding(false);
        return;
      }
      const m = errorMessage(e);
      if (m.includes("401")) {
        window.location.href = `/signin?next=${encodeURIComponent(`/app/ticker/${symbol}`)}`;
        return;
      }
      setAddMsg(m.includes("409") ? "Already in watchlist" : `Failed: ${m}`);
    }
    setAdding(false);
  }

  async function subscribeNews() {
    setNewsAlerting(true);
    setNewsAlertMsg(null);
    try {
      await api.alertRuleCreate({
        name: `News on ${symbol}`,
        rule_type: "news",
        symbol,
        // No threshold — we want every fresh article. Users can later edit
        // the rule on /app/alerts to require sentiment >= 0.3 etc.
        threshold: null,
        channel: "email",
      });
      setNewsAlertMsg(`✓ Email alerts on for ${symbol} news`);
    } catch (e: unknown) {
      // 401 is auto-handled by lib/api handle401() — page redirects to /signin.
      if (e instanceof TierGateError) {
        // Backend's exact message — e.g. "Email alerts require Pro tier"
        setNewsAlertMsg(`${e.message} — upgrade at /app/billing`);
      } else {
        const m = errorMessage(e);
        if (m.includes("409")) setNewsAlertMsg("Already subscribed to news for this ticker");
        else setNewsAlertMsg(`Failed: ${m}`);
      }
    }
    setNewsAlerting(false);
  }

  // Free/anon daily look-up cap reached — render the wall (checked before the
  // generic error so a 402 never falls through to the raw error card).
  if (lookupLimit)
    return (
      <div className="py-8">
        <LookupWall reason={lookupLimit.reason} symbol={symbol} limit={lookupLimit.limit} />
      </div>
    );
  if (error) return <div className="card p-8 text-down">Error: {error}</div>;
  if (!data)
    return (
      <div className="space-y-4">
        {/* Skeleton matches the post-load ticker page header + first-row
            cards, so the layout doesn't shift when data lands. Plain
            "Loading…" text was jarring on a page this dense. */}
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="h-3 w-32 animate-pulse rounded bg-panel" />
            <div className="h-10 w-28 animate-pulse rounded bg-panel" />
            <div className="h-4 w-48 animate-pulse rounded bg-panel" />
          </div>
          <div className="space-y-2 text-right">
            <div className="ml-auto h-10 w-28 animate-pulse rounded bg-panel" />
            <div className="ml-auto h-4 w-20 animate-pulse rounded bg-panel" />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="card h-40 animate-pulse" />
          <div className="card h-40 animate-pulse" />
          <div className="card h-40 animate-pulse" />
        </div>
      </div>
    );

  const toneSig =
    data.signal === "HIGH CONVICTION" ? "text-up bg-up/20"
    : data.signal === "STRONG SETUP" ? "text-up bg-up/10"
    : data.signal === "CONSTRUCTIVE" ? "text-accent bg-accent/10"
    : data.signal === "NEUTRAL" ? "text-muted bg-muted/20"
    : data.signal === "CAUTION" ? "text-warn bg-warn/10"
    : "text-down bg-down/10";

  const displayScore =
    animatedScoreX10 != null ? (animatedScoreX10 / 10).toFixed(1) : "—";

  // Freemium look-up meter for this caller. Absent on older API builds and for
  // anonymous callers, so treat it as optional and default to "nothing to show".
  const lookups =
    (data as TickerDetail & { lookups?: LookupMeter | null }).lookups ?? null;

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <Link href="/app/scanner" className="text-muted hover:text-fg text-sm">&larr; Scanner</Link>
            <LiveBadge status={status} lastUpdate={lastUpdate} />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <h1 className="text-4xl font-bold tracking-tight font-mono">{data.symbol}</h1>
            {/* Earnings pill — surfaces an imminent report as a catalyst.
                Descriptive ("Reports in 3d"), never prescriptive. */}
            <EarningsPill reportDate={earningsBySymbol.get(data.symbol)} />
          </div>
          <p className="mt-1 text-muted">{data.name} &middot; {data.sector}</p>
        </div>
        <div className="text-right">
          <div className="text-4xl font-bold nums">${data.price?.toFixed(2)}</div>
          <div className={`nums ${data.change_pct_1d == null || data.change_pct_1d === 0 ? "text-muted" : data.change_pct_1d > 0 ? "text-up" : "text-down"}`}>
            {data.change_pct_1d == null
              ? "—"
              : `${data.change_pct_1d >= 0 ? "+" : ""}${data.change_pct_1d.toFixed(2)}% today`}
          </div>
          {/* Share opens X with the public /t/[symbol] URL pre-filled. The
              social card crawler hits opengraph-image.tsx and renders the
              tier-coloured score preview. */}
          <a
            href={`https://twitter.com/intent/tweet?${new URLSearchParams({
              text: `$${data.symbol} score: ${(data.score ?? 0).toFixed(0)}/100 (${data.signal ?? "—"})\n\nTransparent 6-factor formula, public scorecard.`,
              url: `https://tapeline.io/t/${data.symbol}`,
              // `via=` adds "via @tapeline_io" to the tweet draft so every
              // share attributes back to the brand account. Don't include the
              // @ — X strips it. See https://x.com/tapeline_io
              via: "tapeline_io",
            }).toString()}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted hover:text-fg transition-colors"
            title="Tweet this score with the live OG card"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
            </svg>
            Share
          </a>
        </div>
      </div>

      {/* Daily look-up meter — self-hiding unless a metered (free) caller is
          within LOOKUP_METER_REMAINING_THRESHOLD of the cap. Sits above the
          fold so the count is seen BEFORE the wall, never as a surprise. */}
      {lookups && (
        <LookupMeterPill
          used={lookups.used}
          limit={lookups.limit}
          remaining={lookups.remaining}
        />
      )}

      {/* Top row: score + signal + actions */}
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <div className="card p-5 flex items-center gap-4">
          {/* Inline radial — small visual signature next to the number,
              showing the shape of the 6 sub-scores at a glance. */}
          <ScoreRadial
            trend={data.breakdown.trend?.value}
            rs={data.breakdown.rs?.value}
            fundamentals={data.breakdown.fundamentals?.value}
            smart_money={data.breakdown.smart_money?.value}
            macro={data.breakdown.macro?.value}
            momentum={data.breakdown.momentum?.value}
            score={data.score ?? null}
            size={108}
            showCenter={false}
            showLabels={false}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <div className="text-xs uppercase text-muted">Tapeline Score</div>
              {data.confidence_pct != null && (
                <span className={`text-xs nums ${confColor(data.confidence_pct)}`}
                      title={confLabel(data.confidence_pct)}>
                  conf {data.confidence_pct.toFixed(0)}%
                </span>
              )}
            </div>
            <div className="mt-1 text-4xl font-bold nums">{displayScore}</div>
            <div className={`mt-2 inline-block rounded px-2 py-0.5 text-xs ${toneSig}`}>
              {data.signal}
            </div>
          </div>
        </div>
        <div className="card p-5">
          <div className="text-xs uppercase text-muted">Performance</div>
          <div className="mt-2 space-y-1 text-sm">
            <Row label="5D" value={data.change_pct_5d} />
            <Row label="1M" value={data.change_pct_1m} />
            <Row label="Volume" value={data.volume} formatter={compact} />
          </div>
        </div>
        <div className="card p-5">
          <div className="text-xs uppercase text-muted">Actions</div>
          <button onClick={addWatch} disabled={adding} className="btn-primary mt-3 w-full text-sm">
            {adding ? "Adding…" : "★ Add to watchlist"}
          </button>
          {addMsg && <p className="mt-2 text-xs text-muted">{addMsg}</p>}
          <button
            onClick={subscribeNews}
            disabled={newsAlerting}
            className="btn-ghost mt-2 w-full text-sm"
            title="Email me whenever a fresh article mentions this ticker"
          >
            {newsAlerting ? "Subscribing…" : "📰 Notify me on news"}
          </button>
          {newsAlertMsg && <p className="mt-2 text-xs text-muted">{newsAlertMsg}</p>}
        </div>
      </div>

      {/* Score breakdown panel */}
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="card lg:col-span-2">
          <div className="border-b border-border p-4">
            <h2 className="font-semibold">Why score {data.score?.toFixed(1)}</h2>
            <p className="text-xs text-muted">Contribution of each factor to the composite.</p>
          </div>
          <ScoreBreakdown
            trend={data.breakdown.trend?.value}
            rs={data.breakdown.rs?.value}
            fundamentals={data.breakdown.fundamentals?.value}
            momentum={data.breakdown.momentum?.value}
            macro={data.breakdown.macro?.value}
            smart_money={data.breakdown.smart_money?.value}
            reason={data.reason}
          />
        </div>

        {/* Squeeze panel, only if detected */}
        {data.squeeze ? (
          <div className="card">
            <div className="border-b border-border p-4">
              <h2 className="font-semibold">🔥 Squeeze detected</h2>
            </div>
            <dl className="space-y-2 p-4 text-sm">
              <Kv k="Spike score" v={data.squeeze.spike_score != null ? data.squeeze.spike_score.toFixed(1) : "—"} />
              <Kv k="Squeeze days" v={`${data.squeeze.squeeze_days}d`} />
              <Kv k="Volume x avg" v={data.squeeze.volume_multiple != null ? `${data.squeeze.volume_multiple.toFixed(2)}x` : "—"} />
              <Kv k="OBV" v={data.squeeze.obv_trend} />
              <Kv k="Pattern" v={data.squeeze.breakout_type} />
              <Kv k="Window" v={data.squeeze.suggested_window} />
            </dl>
            <p className="p-4 text-xs text-muted italic">{data.squeeze.reason}</p>
          </div>
        ) : (
          <div className="card p-5">
            <h2 className="font-semibold text-muted">No squeeze setup</h2>
            <p className="mt-2 text-sm text-muted">Volatility is within normal range for this ticker right now.</p>
          </div>
        )}
      </div>

      {/* Score history sparkline — trace from the daily scorecard, sparse
          by design (only top-10 days populate). Empty-state-friendly. */}
      <div className="mt-6">
        <ScoreSparkline symbol={data.symbol} days={60} />
      </div>

      {/* Analyst ratings — Premium tier only. Finnhub aggregate consensus
          (US + UK / international ADRs). Trial users
          see this for free since trial = Premium for 14 days; post-trial
          Free + Pro users see the Paywall instead. Mirrors how other
          Premium intelligence (Congress, insider Form 4, Telegram) is gated. */}
      <div className="mt-6">
        <Paywall feature="ratings.analyst" title="Analyst consensus is Premium">
          <AnalystRatings symbol={data.symbol} currentPrice={data.price} />
        </Paywall>
      </div>

      {/* More on {symbol} — Financials tab is public (basic per-ticker
          fundamentals from Finnhub). Insider tab is Premium-gated via
          insider.form4 and shows the last 90 days of Form 4 filings.
          Both endpoints have their own caching so tab-switching is cheap. */}
      <div className="mt-6 card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="font-semibold">More on {data.symbol}</h2>
          <div className="flex gap-1 rounded-md border border-border p-1 text-xs">
            <button
              onClick={() => setDetailTab("financials")}
              className={`rounded px-2.5 py-1 transition-colors ${
                detailTab === "financials" ? "bg-accent/15 text-accent" : "text-muted hover:text-fg"
              }`}
              aria-pressed={detailTab === "financials"}
            >
              Financials
            </button>
            <button
              onClick={() => setDetailTab("insider")}
              className={`rounded px-2.5 py-1 transition-colors ${
                detailTab === "insider" ? "bg-accent/15 text-accent" : "text-muted hover:text-fg"
              }`}
              aria-pressed={detailTab === "insider"}
            >
              Insider activity
            </button>
          </div>
        </div>
        <div className="p-4">
          {detailTab === "financials" ? (
            <FinancialsTab symbol={data.symbol} />
          ) : (
            <Paywall feature="insider.form4" title="Insider activity is Premium">
              <InsiderTab symbol={data.symbol} />
            </Paywall>
          )}
        </div>
      </div>

      {/* TradingView chart embed */}
      <div className="mt-6 card p-4">
        <h2 className="mb-3 font-semibold">Chart</h2>
        <div className="overflow-hidden rounded-md">
          <iframe
            src={`https://s.tradingview.com/widgetembed/?frameElementId=tv_${data.symbol}&symbol=${data.symbol.replace(".", "-")}&interval=D&theme=dark&style=1&timezone=exchange&withdateranges=1&hide_side_toolbar=1&allow_symbol_change=0&studies=%5B%22RSI@tv-basicstudies%22%5D`}
            className="h-[500px] w-full border-0"
            title={`${data.symbol} chart`}
          />
        </div>
      </div>

      {/* News */}
      <div className="mt-6 card">
        <div className="border-b border-border p-4">
          <h2 className="font-semibold">📰 Recent news</h2>
        </div>
        <ul className="divide-y divide-border">
          {data.news.length === 0 && (
            <li className="p-4 text-sm text-muted">No news indexed for {data.symbol} yet.</li>
          )}
          {data.news.map((n) => (
            <li key={n.id} className="p-4">
              <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:text-accent">
                {n.title}
              </a>
              <div className="mt-1 flex items-center gap-3 text-xs text-muted">
                <span>{n.publisher}</span>
                <span>·</span>
                <span title={formatAbsolute(n.published_at)}>
                  {formatRelativeOrAbsolute(n.published_at)}
                </span>
                {n.sentiment != null && (
                  <span className={n.sentiment > 0 ? "text-up" : n.sentiment < 0 ? "text-down" : ""}>
                    sentiment {n.sentiment > 0 ? "+" : ""}{n.sentiment.toFixed(2)}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* Watchlist-cap upgrade moment — opens when the server 403s the
          "★ Add to watchlist" action. Backend message carries the real
          cap numbers. */}
      <PaywallModal
        open={capMsg != null}
        onClose={() => setCapMsg(null)}
        feature="watchlist"
        heading="Your watchlist is full"
        description={capMsg ?? undefined}
      />
    </div>
  );
}

function Row({ label, value, formatter }: { label: string; value: number | null | undefined; formatter?: (n: number) => string }) {
  const v = value ?? 0;
  const fmt = formatter ? formatter(v) : (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className={`nums ${!formatter ? (v > 0 ? "text-up" : v < 0 ? "text-down" : "") : ""}`}>{fmt}</span>
    </div>
  );
}
function Kv({ k, v }: { k: string; v: string | number }) {
  return (
    <div className="flex justify-between text-sm">
      <dt className="text-muted">{k}</dt>
      <dd className="nums font-medium">{v}</dd>
    </div>
  );
}
function compact(n: number) {
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
  return String(n);
}
function confColor(c: number) {
  if (c >= 80) return "text-up";
  if (c >= 60) return "text-fg";
  if (c >= 40) return "text-warn";
  return "text-down";
}
function confLabel(c: number) {
  if (c >= 95) return "Full data on every signal feature — strongest evidence";
  if (c >= 80) return "Most features present, missing 1–3 minor data points";
  if (c >= 60) return "Core scoring data + most fundamentals — typical liquid stock";
  if (c >= 40) return "Only basic price/trend data — caution";
  return "Sparse data — unreliable signals, deprioritise";
}
