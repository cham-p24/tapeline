"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type TickerDetail, TierGateError, LookupLimitError, errorMessage } from "@/lib/api";
import { ScorePanel } from "@/components/ScorePanel";
import { TickerRecord } from "@/components/TickerRecord";
import { LiveBadge } from "@/components/LiveBadge";
import { useLiveStream } from "@/lib/useLiveStream";
import { recordTickerVisit } from "@/components/RecentTickers";
import { AnalystRatings } from "@/components/AnalystRatings";
import { FinancialsTab } from "@/components/FinancialsTab";
import { InsiderTab } from "@/components/InsiderTab";
import { Paywall, PaywallModal } from "@/components/Paywall";
import { LookupWall } from "@/components/LookupWall";
import { ScoreSparkline } from "@/components/ScoreSparkline";
import { KeyStatistics, type KeyStats } from "@/components/KeyStatistics";
import { useCountUp } from "@/lib/useCountUp";
import { formatAbsolute, formatRelativeOrAbsolute } from "@/lib/datetime";
import { EarningsPill } from "@/components/EarningsPill";
import { useEarningsCalendar } from "@/lib/useEarningsCalendar";
import { trackEvent, trackFirstTickerAdded, trackCapHit } from "@/lib/gtag";
import { SECTORS } from "@/app/sector/sectors";
import { relatedMatchups, canonicalMatchup } from "@/lib/comparePairs";
import { useTheme } from "@/components/ThemeProvider";
import { useUser } from "@/components/UserContext";

/**
 * In-app scanner, pre-filtered to this sector, if it maps to a known GICS
 * sector; else null. Deliberately points at /app/scanner (not the public
 * /sector/<slug> marketing hub) so an authed user staring at a ticker isn't
 * ejected out of the app shell. The scanner's sector filter keys on the
 * canonical `api` string, which is exactly what Ticker.sector stores.
 */
function sectorScannerPath(sector: string | null): string | null {
  if (!sector) return null;
  const match = SECTORS.find((s) => s.api === sector);
  return match ? `/app/scanner?sector=${encodeURIComponent(match.api)}` : null;
}

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
  // Applied theme ("light" | "dark") for the embedded chart, so it tracks the
  // user's light/dark choice instead of being pinned to dark.
  const { resolved: resolvedTheme } = useTheme();
  // Session user — drives the news-alert channel default (Free users can only
  // create web_push rules; email is a paid channel and would 403 them).
  const { user } = useUser();
  const isFree = !!user && user.tier === "free";
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
  // True when the news-alert failure was a tier gate — the message then gets a
  // real billing <Link> appended after it (a plain "/app/billing" string isn't
  // clickable).
  const [newsAlertGate, setNewsAlertGate] = useState(false);
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
        // Funnel: only the logged-in FREE variant is a cap hit. The anon
        // "signup_required" wall is a sign-up prompt, not a free→paid cap.
        if (e.reason === "free_lookup_limit") trackCapHit("daily_lookups", "ticker");
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
        // Funnel: free user refused a watchlist add — the client half of the
        // watchlist_tickers cap (the durable row is written server-side).
        trackCapHit("watchlist_tickers", "ticker");
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
    setNewsAlertGate(false);
    // Pick the channel the caller can actually create: email is a paid channel,
    // so defaulting a Free user to it walked them straight into a 403. web_push
    // is free-tier, mirroring the /app/alerts create form.
    const channel = isFree ? "web_push" : "email";
    try {
      await api.alertRuleCreate({
        name: `News on ${symbol}`,
        rule_type: "news",
        symbol,
        // No threshold — we want every fresh article. Users can later edit
        // the rule on /app/alerts to require sentiment >= 0.3 etc.
        threshold: null,
        channel,
      });
      setNewsAlertMsg(
        channel === "web_push"
          ? `✓ Browser alerts on for ${symbol} news — enable notifications on /app/alerts if prompted`
          : `✓ Email alerts on for ${symbol} news`,
      );
    } catch (e: unknown) {
      // 401 is auto-handled by lib/api handle401() — page redirects to /signin.
      if (e instanceof TierGateError) {
        // Strip any trailing "at /app/billing" — the JSX appends a real link.
        setNewsAlertMsg(e.message.replace(/\s*at \/app\/billing\.?\s*$/i, "."));
        setNewsAlertGate(true);
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

  const displayScore =
    animatedScoreX10 != null ? (animatedScoreX10 / 10).toFixed(1) : "—";

  // Freemium look-up meter for this caller. Absent on older API builds and for
  // anonymous callers, so treat it as optional and default to "nothing to show".
  const lookups =
    (data as TickerDetail & { lookups?: LookupMeter | null }).lookups ?? null;

  // Key statistics — the `key_stats` group the ticker endpoint returns (see
  // _key_stats_payload in backend/app/routers/ticker.py). Read structurally for
  // the same reason `lookups` above is: TickerDetail lives in lib/api.ts, which
  // is outside this change's file lane. Folding both into TickerDetail is the
  // follow-up.
  //
  // Defaults to an empty object, so a frontend that deploys ahead of the
  // backend renders a block of em-dashes instead of throwing.
  const keyStats =
    (data as TickerDetail & { key_stats?: KeyStats | null }).key_stats ?? {};

  // `peer_percentiles` — the block that turns "sub_trend 82" into "82, 91st
  // percentile of Health Care (n=763)". Built by
  // backend/app/services/percentile.py; null when its aggregate degraded, in
  // which case the page still renders every raw value and simply cannot locate
  // them. Read structurally for the same reason key_stats is, and passed
  // through untouched: components/percentiles.ts owns validation, the
  // minimum-n floor and the refusal to rank on an unusable peer group.
  const percentiles = (data as TickerDetail & { peer_percentiles?: unknown })
    .peer_percentiles;

  // `flag_record` — this ticker's own history on the public scorecard.
  // `undefined` is NOT "never flagged": it is "we were not told", and
  // TickerRecord renders nothing at all in that case. See the three-states
  // comment in components/TickerRecord.tsx.
  const recordBlock = (data as TickerDetail & { flag_record?: unknown }).flag_record;

  return (
    <div>
      {/* Header — stacks on phones so the two text-4xl blocks (symbol + price)
          don't collide; side-by-side from sm up. */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
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
          <p className="mt-1 text-muted">
            {data.name}
            {data.sector && (
              <>
                {" · "}
                {sectorScannerPath(data.sector) ? (
                  <Link
                    href={sectorScannerPath(data.sector)!}
                    className="underline-offset-4 hover:text-fg hover:underline"
                  >
                    {data.sector}
                  </Link>
                ) : (
                  data.sector
                )}
              </>
            )}
          </p>
        </div>
        <div className="sm:text-right">
          {/* A price we don't hold is an em-dash, not "$undefined" and not $0 —
              ~72% of the universe has no daily price read. */}
          <div className="text-4xl font-bold nums">
            {data.price != null ? `$${data.price.toFixed(2)}` : "—"}
          </div>
          <div className={`nums ${data.change_pct_1d == null || data.change_pct_1d === 0 ? "text-muted" : data.change_pct_1d > 0 ? "text-up" : "text-down"}`}>
            {data.change_pct_1d == null
              ? "—"
              : `${data.change_pct_1d >= 0 ? "+" : ""}${data.change_pct_1d.toFixed(2)}% today`}
          </div>
          {/* Explicit as-of stamp. The LiveBadge says whether the stream is
              connected; this says how old the numbers under it actually are,
              which is the thing a reader needs before treating any of them as
              current. Absolute time on hover, relative in the flow. */}
          <div className="mt-1 text-xs text-muted">
            {data.updated_at ? (
              <span title={formatAbsolute(data.updated_at)}>
                As of {formatRelativeOrAbsolute(data.updated_at)}
              </span>
            ) : (
              <span>As of &mdash; (no update stamp on this ticker)</span>
            )}
          </div>
          {/* Share opens X with the public /t/[symbol] URL pre-filled. The
              social card crawler hits opengraph-image.tsx and renders the
              tier-coloured score preview. */}
          <a
            href={`https://twitter.com/intent/tweet?${new URLSearchParams({
              // No `?? 0`: a ticker we hold no score for shares as an em-dash,
              // never as a fabricated zero.
              text: `$${data.symbol} score: ${data.score != null ? data.score.toFixed(0) : "—"}/100 (${data.signal ?? "—"})\n\nSix named factors, public scorecard.`,
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

      {/* Compare — onward navigation from what was a near dead-end. Curated
          head-to-heads that include this ticker; renders nothing when the
          symbol isn't in a curated pair, so it never shows an empty row. */}
      {(() => {
        const pairs = relatedMatchups(data.symbol, 4);
        if (pairs.length === 0) return null;
        const self = data.symbol.toUpperCase();
        return (
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-wider text-subtle">Compare</span>
            {pairs.map(({ a, b }) => {
              const other = a === self ? b : a;
              const slug = canonicalMatchup(a, b);
              return (
                <Link
                  key={slug}
                  href={`/compare/${slug}`}
                  className="rounded-full border border-border bg-panel px-3 py-1 font-mono text-xs text-muted transition-colors hover:border-accent hover:text-fg"
                >
                  {data.symbol} vs {other}
                </Link>
              );
            })}
          </div>
        );
      })()}

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

      {/* ------------------------------------------------------------------
          THE DECISION LAYER.

          The reader arrives asking two questions: "what does this product
          think, and can I check it?" Both are answered before they are shown a
          quote grid. Score panel + factors + the one-sentence read first, then
          this ticker's own record, then the market fields, then everything
          else. That order is the whole point of the page.
          ------------------------------------------------------------------ */}
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ScorePanel
            symbol={data.symbol}
            score={data.score ?? null}
            signal={data.signal ?? null}
            confidencePct={data.confidence_pct ?? null}
            breakdown={data.breakdown}
            percentiles={percentiles}
            reason={data.reason ?? null}
            displayScore={displayScore}
          />
        </div>
        <div className="card h-fit p-5">
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
          {newsAlertMsg && (
            <p className="mt-2 text-xs text-muted">
              {newsAlertMsg}
              {newsAlertGate && (
                <>
                  {" "}
                  <Link href="/app/billing" className="text-accent hover:underline">
                    See plans
                  </Link>
                </>
              )}
            </p>
          )}
          {/* One-tap news alert above; this hands off to the full alerts form
              pre-armed with this ticker + the news rule so the user can tune
              the channel/threshold instead of starting from a blank screen. */}
          <Link
            href={`/app/alerts?symbol=${encodeURIComponent(symbol)}&type=news`}
            className="mt-2 block text-xs text-muted hover:text-accent hover:underline"
          >
            Set a custom alert →
          </Link>
        </div>
      </div>

      {/* "On our record" — the block no rival can print. Renders nothing at all
          when the payload carries no record block: not being told is not the
          same as being told there are no flags. See TickerRecord. */}
      <div className="mt-6">
        <TickerRecord symbol={data.symbol} record={recordBlock} />
      </div>

      {/* ------------------------------------------------------------------
          THE MARKET LAYER — the reported facts about the instrument, below our
          read of them rather than above it.
          ------------------------------------------------------------------ */}
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <KeyStatistics stats={keyStats} />
        </div>
        <div className="card h-fit p-5">
          <div className="text-xs uppercase text-muted">Price change</div>
          <div className="mt-2 space-y-1 text-sm">
            <Row label="1D" value={data.change_pct_1d} />
            <Row label="5D" value={data.change_pct_5d} />
            <Row label="1M" value={data.change_pct_1m} />
          </div>
        </div>
      </div>

      {/* Squeeze panel, only if detected */}
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
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
          see this for free since trial = Premium for 30 days; post-trial
          Free + Pro users see the Paywall instead. Mirrors how other
          Premium intelligence (Congress, insider Form 4) is gated. */}
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
          <div className="flex gap-1 rounded-full bg-fg/5 p-1 text-xs">
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
            src={`https://s.tradingview.com/widgetembed/?frameElementId=tv_${data.symbol}&symbol=${data.symbol.replace(".", "-")}&interval=D&theme=${resolvedTheme}&style=1&timezone=exchange&withdateranges=1&hide_side_toolbar=1&allow_symbol_change=0&studies=%5B%22RSI@tv-basicstudies%22%5D`}
            className="h-[320px] w-full border-0 sm:h-[420px] lg:h-[500px]"
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

/**
 * One period's price change.
 *
 * A period we hold no read for renders as an em-dash in muted type. It used to
 * be `value ?? 0`, which printed "+0.00%" — a fabricated flat session — for
 * every ticker whose 5-day or 1-month change we simply do not have. Zero is
 * never a stand-in for unknown on this page.
 */
function Row({ label, value }: { label: string; value: number | null | undefined }) {
  if (value == null || Number.isNaN(value)) {
    return (
      <div className="flex justify-between">
        <span className="text-muted">{label}</span>
        <span className="nums text-muted">—</span>
      </div>
    );
  }
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className={`nums ${value > 0 ? "text-up" : value < 0 ? "text-down" : ""}`}>
        {(value >= 0 ? "+" : "") + value.toFixed(2)}%
      </span>
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
