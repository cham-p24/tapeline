"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Regime, TierGateError } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { CardSkeleton } from "@/components/Skeleton";
import { FearGreedDial } from "@/components/FearGreedDial";
import { Paywall } from "@/components/Paywall";

/**
 * Market Regime page.
 *
 * **2026-05-20 clarity pass** — founder feedback "needs to have more
 * clarity behind it". Added:
 *   1. Plain-English subtitle above the metric grid explaining what
 *      the regime synthesises and why it matters per ticker
 *   2. Each KPI now carries a one-line description + a threshold hint
 *      (e.g. VIX > 25 = stress) so a reader who's never traded options
 *      can interpret the value without leaving the page
 *   3. "What this means for trading today" panel under the regime hero
 *      — turns "NEUTRAL" / "BULL" / etc. into concrete behaviour
 *   4. "Where the regime comes from" panel surfaces the formula —
 *      consistent with the rest of the site's transparency posture
 */

// FRED / vendor feeds occasionally hand back null between refreshes (the
// 2026-05-20 Sentry crash TAPELINE-BACKEND-6 was exactly this — null.toFixed
// in production). Treat null as the em-dash placeholder rather than letting
// the whole page error-boundary out.
function fmtKpi(v: number | null | undefined, digits: number, suffix = ""): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits) + suffix;
}
function fmtScore(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(0);
}

// Per-KPI metadata (description + threshold notes) so the page can
// teach as it surfaces numbers. Kept inline rather than imported so
// each KPI is self-documenting in source.
type KpiCopy = {
  desc: string;
  hint: (val: number | string) => string;
  tone?: (val: number) => "up" | "down" | "warn" | "muted";
};

const VIX_COPY: KpiCopy = {
  desc: "Implied 30-day S&P 500 volatility. Sometimes called the 'fear index'.",
  hint: (v) => {
    const n = typeof v === "number" ? v : parseFloat(String(v));
    if (n < 15) return "Below 15 — complacent. Risk premiums compressed.";
    if (n < 20) return "15-20 — calm. Typical bull-market regime.";
    if (n < 25) return "20-25 — elevated. Caution warranted.";
    if (n < 35) return "25-35 — stress. Drawdowns common.";
    return "Above 35 — panic. Historical floors form here.";
  },
  tone: (n) => (n < 20 ? "up" : n < 25 ? "muted" : n < 35 ? "warn" : "down"),
};

const DXY_COPY: KpiCopy = {
  desc: "Broad trade-weighted USD index (FRED DTWEXBGS). Rising USD usually pressures stocks and commodities.",
  hint: () => "Compare day-over-day direction — sustained moves matter more than the level.",
};

const TY_COPY: KpiCopy = {
  desc: "US 10-year Treasury yield. Discount rate for every long-duration risk asset.",
  hint: (v) => {
    const n = typeof v === "string" ? parseFloat(v) : v;
    if (n < 3.5) return "Below 3.5% — easy money tailwind for growth stocks.";
    if (n < 4.5) return "3.5-4.5% — neutral discount-rate regime.";
    if (n < 5.5) return "4.5-5.5% — restrictive. Duration assets struggle.";
    return "Above 5.5% — credit-stress territory.";
  },
};

const RD_COPY: KpiCopy = {
  desc: "Trend of the 10-year yield over the last ~30 trading days. Direction matters more than absolute level for risk-on/off behaviour.",
  hint: () => "RISING = headwind for growth equities. FALLING = tailwind. SIDEWAYS = neutral.",
};

// Advance/decline ratio, NOT a 200-day-moving-average breadth read. The
// writers compute 100 * advancers / (advancers + decliners) from today's
// change_pct_1d, so the bands below are centred on 50 (balanced) rather than
// on the 60-70% levels a 200DMA breadth series is read against. It describes
// one session only — a single day's A/D says nothing about the trend.
const BR_COPY: KpiCopy = {
  desc: "Of the names that moved today, the share that closed up — advancers ÷ (advancers + decliners), across the Tapeline universe. Names with no price read, and names that closed unchanged, are excluded.",
  hint: (v) => {
    const n = typeof v === "number" ? v : parseFloat(String(v));
    if (n > 70) return "Above 70% — broad advance; most moving names rose today.";
    if (n > 60) return "60-70% — advancers clearly outnumber decliners today.";
    if (n >= 40) return "40-60% — mixed session; advancers and decliners roughly balanced.";
    if (n >= 30) return "30-40% — decliners outnumber advancers today.";
    return "Below 30% — broad decline; most moving names fell today.";
  },
  tone: (n) => (n > 60 ? "up" : n >= 40 ? "muted" : n >= 30 ? "warn" : "down"),
};

const SL_COPY: KpiCopy = {
  desc: "The 3 sectors with the highest mean Tapeline composite score this tick, across the symbols we scored that carry a known sector. Our own ranking — not relative strength vs SPY.",
  hint: () => "Reflects where our scores currently cluster, not a measured sector return. Shows — when we could not rank sectors this tick.",
};

// Descriptive characterisation of how the score distribution behaves in each
// regime. Tapeline never issues buy/sell/position-sizing directives — the
// regime is a multiplier on the composite, so these bullets describe what the
// scores do, not what a reader should do with capital.
const REGIME_PLAYBOOK: Record<string, { headline: string; bullets: string[] }> = {
  BULL: {
    headline: "Volatility is compressed. The regime multiplier lifts scores across the universe.",
    bullets: [
      "A larger share of the universe sits in the STRONG SETUP and HIGH CONVICTION bands — factor confluence is more common in this regime.",
      "The Trend and Relative Strength factors stay elevated for more names.",
      "A given factor profile scores higher in BULL than the same profile would in CAUTIOUS or BEAR.",
    ],
  },
  NEUTRAL: {
    headline: "Index direction is muted; scores separate on company-specific factors.",
    bullets: [
      "The regime multiplier is roughly neutral, so a name's score reflects its own factor confluence rather than a market tailwind.",
      "Fewer names cluster at the top than in BULL — the HIGH CONVICTION count typically compresses.",
      "Idiosyncratic factors (Trend, Fundamentals, Smart Money) drive the spread between names more than macro does.",
    ],
  },
  CAUTIOUS: {
    headline: "Volatility is elevated; the regime multiplier marks scores down.",
    bullets: [
      "Weak-factor names score lower here — the composite weights drag more heavily than in BULL.",
      "The top bands thin out: fewer names reach STRONG SETUP, and HIGH CONVICTION becomes rarer.",
      "A further rise in VIX past 25 moves the label to BEAR — the classifier reads nothing else, so the advancer count above can disagree with the label.",
    ],
  },
  BEAR: {
    headline: "Capital-preservation regime; the multiplier marks most scores down hard.",
    bullets: [
      "Very few names hold a high composite — typically only defensive sectors with intact base structure and positive Smart Money flows.",
      "HIGH CONVICTION counts compress to the low tens as factor confluence becomes rare.",
      "Descriptively, the names that go on to lead the next BULL are often the ones that hold up structurally through BEAR — the watchlist tier is where the regime surfaces them.",
    ],
  },
};

export default function RegimePage() {
  const [r, setR] = useState<Regime | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      setR(await api.regime());
      setLoadError(null);
    } catch (e) {
      // 403 (Free tier) → the <Paywall> wrapper below owns the presentation.
      // Rendering the error card here was a dead end: "Try again" can never
      // succeed for the tier, and the copy never mentioned upgrading.
      if (e instanceof TierGateError) {
        setLoadError(null);
        return;
      }
      console.error(e);
      setLoadError(e instanceof Error ? e.message : "Failed to load regime");
    }
  }, []);
  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  const toneBg =
    r?.regime === "BULL" ? "bg-up/15 text-up"
    : r?.regime === "NEUTRAL" ? "bg-accent/15 text-accent"
    : r?.regime === "CAUTIOUS" ? "bg-warn/15 text-warn"
    : "bg-down/15 text-down";
  const playbook = r ? REGIME_PLAYBOOK[r.regime] : null;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Market Regime</h1>
          <p className="mt-1 text-sm text-muted">
            One macro classification of the US equity market, refreshed each
            worker tick (~60s). The regime acts as a multiplier on every
            Tapeline score — names that look great in BULL get marked down
            during CAUTIOUS, and vice-versa.
          </p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      {/* Regime legend — open by default so the meanings are above the fold.
          States the actual VIX cut-offs. It previously described breadth and
          200DMA criteria that the classifier does not read. */}
      <details className="card mt-5 cursor-pointer p-4 text-sm" open>
        <summary className="font-semibold">What each regime means</summary>
        <div className="mt-3 grid gap-3 text-muted sm:grid-cols-2">
          <div><strong className="text-up">BULL</strong> &mdash; VIX below 15. Volatility is compressed; the multiplier lifts scores across the universe.</div>
          <div><strong className="text-accent">NEUTRAL</strong> &mdash; VIX 15&ndash;20. The multiplier is roughly neutral, so company-specific factors separate the scores.</div>
          <div><strong className="text-warn">CAUTIOUS</strong> &mdash; VIX 20&ndash;25. Elevated volatility; the multiplier marks scores down.</div>
          <div><strong className="text-down">BEAR</strong> &mdash; VIX 25 or above. The multiplier marks most scores down hard.</div>
        </div>
        <p className="mt-3 text-xs text-subtle">
          These four cut-offs are the whole classifier. The other figures on
          this page are context we publish alongside the label &mdash; they do
          not feed it.
        </p>
      </details>

      {/* Pro gate — same pattern as the sibling gated pages (heatmap,
          holdings): Free users see the upgrade card over a blurred skeleton
          instead of a dead-end error + eternally failing "Try again". */}
      <Paywall feature="regime.full" title="Market Regime dashboard">
      {loadError && (
        <div className="card mt-5 border border-down/30 p-4 text-sm">
          <p className="text-down">Couldn&apos;t load the regime feed.</p>
          <p className="mt-2 text-xs text-muted">{loadError}</p>
          <button
            type="button"
            onClick={() => { load(); }}
            className="mt-3 rounded-md border border-border px-3 py-1.5 text-xs hover:border-accent hover:text-accent"
          >
            Try again
          </button>
        </div>
      )}

      {!r && !loadError ? (
        <CardSkeleton rows={5} />
      ) : r ? (
        <>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {/* Current regime hero */}
            <div className={`card p-8 ${toneBg.split(" ")[0]}`}>
              <div className="text-xs uppercase tracking-wider text-muted">Current regime</div>
              <div className={`mt-1 text-6xl font-bold tracking-tight ${toneBg.split(" ")[1]}`}>
                {r.regime}
              </div>
              {playbook && (
                <>
                  <p className="mt-4 text-sm font-medium">{playbook.headline}</p>
                  <ul className="mt-3 space-y-1.5 text-xs text-muted">
                    {playbook.bullets.map((b) => (
                      <li key={b} className="flex gap-2"><span className="text-subtle">›</span>{b}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>

            {/* Fear & Greed dial */}
            {r.fear_greed && (
              <div className="card flex flex-col items-center p-6">
                <div className="self-start text-xs uppercase tracking-wider text-muted">Fear &amp; Greed</div>
                <div className="mt-2">
                  <FearGreedDial
                    score={r.fear_greed.score}
                    label={r.fear_greed.label}
                    color={r.fear_greed.color}
                  />
                </div>
                <p className="mt-4 text-center text-[11px] leading-relaxed text-subtle">
                  Composite of VIX ({fmtScore(r.fear_greed.components.vix.score)}),
                  advancers today ({fmtScore(r.fear_greed.components.breadth.score)}),
                  regime label ({fmtScore(r.fear_greed.components.regime.score)}),
                  and 5-day SPY momentum ({fmtScore(r.fear_greed.components.spy_5d.score)}).
                </p>
              </div>
            )}
          </div>

          {/* Section heading above the KPI grid — signals "this is where
              the numbers explaining the regime live" */}
          <div className="mt-8 mb-3 flex items-baseline justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Inputs feeding the regime</h2>
            <span className="text-[11px] text-subtle">All live, refreshed each tick</span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Kpi label="VIX" value={fmtKpi(r.vix, 2)} copy={VIX_COPY} numericValue={r.vix} />
            {/* FRED series DTWEXBGS — broad trade-weighted USD index, not
                ICE DXY. Reads ~115-125 right now; ICE DXY (the futures
                contract most traders watch) is ~100-110. Label kept
                honest to the source. */}
            <Kpi label="USD Broad Index" value={fmtKpi(r.dxy, 2)} copy={DXY_COPY} numericValue={r.dxy} />
            <Kpi label="10Y Yield" value={fmtKpi(r.yield_10y, 3, "%")} copy={TY_COPY} numericValue={r.yield_10y} />
            <Kpi label="Rate direction" value={r.rate_direction} copy={RD_COPY} />
            <Kpi label="Advancers today (% of names that moved)" value={fmtKpi(r.breadth_pct, 1, "%")} copy={BR_COPY} numericValue={r.breadth_pct} />
            <Kpi label="Highest-scoring sectors (our composite)" value={r.sector_leaders || "—"} copy={SL_COPY} small />
          </div>

          {/* Where the regime comes from — transparency block. p-6 to match
              the other top-level regime cards (Current Regime, F&G dial)
              on this page; previously p-5 made this block look subtly
              smaller than its peers despite carrying the same weight. */}
          <div className="card mt-8 p-6 text-sm">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Where this regime label comes from</h2>
            <p className="mt-3 text-muted leading-relaxed">
              There is no composite. The label is decided by the VIX level
              against four fixed thresholds, and nothing else:{" "}
              <strong>below 15 = BULL</strong>, <strong>15&ndash;20 = NEUTRAL</strong>,{" "}
              <strong>20&ndash;25 = CAUTIOUS</strong>, <strong>25 or above = BEAR</strong>.
              When our macro workbook publishes an explicit market-mode read,
              that read is written last and supersedes the VIX ladder.
            </p>
            <p className="mt-3 text-muted leading-relaxed">
              The other figures above — advancers today, the 10-year yield and
              its direction, the USD index, and the highest-scoring sectors —
              are published as context. None of them are inputs to the label.
              The Fear &amp; Greed dial is the one number here that is a
              weighted blend, and it reads the label as one of its four terms.
              The thresholds are fixed and visible — any change ships with a
              changelog entry.
            </p>
          </div>
        </>
      ) : null}
      </Paywall>
    </div>
  );
}

function Kpi({
  label,
  value,
  copy,
  numericValue,
  small,
}: {
  label: string;
  value: string;
  copy: KpiCopy;
  numericValue?: number;
  small?: boolean;
}) {
  const toneClass =
    copy.tone && numericValue !== undefined
      ? (() => {
          const t = copy.tone(numericValue);
          return t === "up" ? "text-up"
            : t === "down" ? "text-down"
            : t === "warn" ? "text-warn"
            : "text-fg";
        })()
      : "text-fg";
  return (
    <div className="card p-5">
      <div className="text-xs uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-1 font-semibold nums ${small ? "text-base" : "text-2xl"} ${toneClass}`}>{value}</div>
      <p className="mt-3 text-[11px] leading-relaxed text-muted">{copy.desc}</p>
      <p className="mt-1.5 text-[11px] leading-relaxed text-subtle">{copy.hint(numericValue ?? value)}</p>
    </div>
  );
}
