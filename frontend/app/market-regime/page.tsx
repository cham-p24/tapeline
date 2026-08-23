import Link from "next/link";
import { SeoFeaturePage } from "@/components/SeoFeaturePage";
import { pageMeta } from "@/lib/seo";
import { ssrInternalHeaders } from "@/lib/ssrHeaders";

export const revalidate = 3600;

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

export const metadata = pageMeta({
  title: "Market Regime Indicator — Live VIX Thresholds + Advancers | Tapeline",
  description:
    "Tapeline's market regime label is set by the VIX against four fixed thresholds. We publish it next to the advancer count, rate direction and SPY momentum, and show exactly which of those feed the label. Cached snapshot, refreshed hourly.",
  path: "/market-regime",
});

// Every reading is nullable on the LIVE path. The API can answer with a regime
// label and no VIX (the FRED leg failed, the cache is cold), and substituting
// the showcase's number there prints an invented measurement on a card headed
// "Cached snapshot". Absence renders as an em-dash — same contract as
// sector_leaders below.
type RegimePreview = {
  regime: string;
  vix: number | null;
  breadth_pct: number | null;
  rate_direction: string | null;
  yield_10y: number | null;
  fear_greed: { score: number; label: string } | null;
  sector_leaders: string;
};

const EMPTY = "—";

const SHOWCASE: RegimePreview = {
  regime: "NEUTRAL",
  vix: 17.26,
  breadth_pct: 57.4,
  rate_direction: "RISING",
  yield_10y: 4.47,
  fear_greed: { score: 71, label: "Greed" },
  sector_leaders: "Information Technology · Communication Services · Health Care",
};

async function fetchRegime(): Promise<{ data: RegimePreview; live: boolean }> {
  try {
    const res = await fetch(`${API_BASE}/api/public/regime`, {
      next: { revalidate: 3600 },
      headers: ssrInternalHeaders(),
      // Bound the build-time fetch so a degraded/slow API can't hang static
      // export past Next's 60s budget (a hang isn't caught by try/catch).
      // Matches /stocks + /signals; falls back to SHOWCASE below.
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return { data: SHOWCASE, live: false };
    const body = (await res.json()) as Partial<RegimePreview> & { available?: boolean };
    if (!body.available || !body.regime) return { data: SHOWCASE, live: false };
    return {
      // NO SHOWCASE FALLBACKS on this branch. The whole card is labelled
      // "Cached snapshot" here, so borrowing the example's numbers for whatever
      // the API omitted would present invented readings as real ones — the
      // showcase VIX of 17.26 is not a measurement of anything. Absent stays
      // absent; each one renders as an em-dash.
      data: {
        regime: body.regime,
        vix: body.vix ?? null,
        breadth_pct: body.breadth_pct ?? null,
        rate_direction: body.rate_direction ?? null,
        yield_10y: body.yield_10y ?? null,
        fear_greed: body.fear_greed ?? null,
        sector_leaders: body.sector_leaders || "—",
      },
      live: true,
    };
  } catch {
    return { data: SHOWCASE, live: false };
  }
}

export default async function MarketRegimePage() {
  const { data, live } = await fetchRegime();
  // Tone the F&G number by its score band so the colour matches what the
  // dial would show: red below 25, amber to 44, muted to 54, accent to 74,
  // green at 75+.
  const fgScore = data.fear_greed?.score ?? null;
  const fgTone =
    fgScore == null ? "text-muted"
    : fgScore < 25 ? "text-down"
    : fgScore < 45 ? "text-warn"
    : fgScore < 55 ? "text-muted"
    : fgScore < 75 ? "text-accent"
    : "text-up";
  return (
    <SeoFeaturePage
      slug="market-regime"
      eyebrow="Feature · Market regime"
      h1="Market Regime Indicator — Live VIX, Advancers, Rates"
      lede="Every individual scoring decision is downstream of the macro state. Tapeline's regime label is set by one input: the VIX, against four fixed thresholds — below 15 BULL (risk on), 15–20 NEUTRAL, 20–25 CAUTIOUS, 25 and above BEAR (risk off). We publish the other macro figures we track next to it — advancers today, rate direction (10Y yield slope from FRED), and short-window SPY momentum — and we tell you plainly that they are context, not inputs. The Fear &amp; Greed dial is the number here that does blend all four into the familiar 0–100 sentiment scale."
      methodology={{
        heading: "How the regime is computed",
        body: (
          <>
            <p>
              Two different things share this page. The{" "}
              <strong>regime label</strong> is not a composite: it is the VIX
              read against four fixed thresholds — below 15 BULL, 15&ndash;20
              NEUTRAL, 20&ndash;25 CAUTIOUS, 25 and above BEAR — and nothing
              else. When our macro workbook publishes an explicit market-mode
              read, that read is written last and supersedes the ladder.
            </p>
            <p>
              The <strong>Fear &amp; Greed score</strong> is the composite.
              Four inputs, leaning most on the volatility and advancer
              readings: VIX (lower = greed), advancers today (more of the
              moving names closing up = greed), the regime label itself, and
              5-day SPY momentum (positive = greed). Because the label is
              VIX-derived, that third term partly re-weights VIX rather than
              adding an independent input. The composite maps to{" "}
              <strong>0&ndash;24 Extreme Fear</strong>, <strong>25&ndash;44 Fear</strong>,{" "}
              <strong>45&ndash;54 Neutral</strong>, <strong>55&ndash;74 Greed</strong>,{" "}
              <strong>75&ndash;100 Extreme Greed</strong> &mdash; matches the labels
              CNN&rsquo;s familiar version uses so anyone who&rsquo;s seen one before
              can read it instantly.
            </p>
            <p>
              Because the ladder is VIX-only, the label can disagree with the
              other figures on this page &mdash; a calm VIX reads Risk On even
              on a day when most moving names fell. We show both rather than
              reconciling them behind the scenes. Most days land in{" "}
              <strong>Neutral</strong> or <strong>Cautious</strong>.
            </p>
            <p>
              The macro figures come from FRED via the free-tier API: VIX
              (VIXCLS), 10Y yield (DGS10), USD broad index (DTWEXBGS). The
              advancer count and the sector ranking are computed live each
              worker tick across the Tapeline universe. Full live regime panel
              + Fear &amp; Greed dial at{" "}
              <Link href="/app/regime" className="link">
                /app/regime
              </Link>
              .
            </p>
          </>
        ),
      }}
      faq={[
        {
          q: "What's the difference between 'Risk On' (BULL) and 'Risk Off' (BEAR)?",
          a: "Only the VIX level. BULL is VIX below 15, NEUTRAL is 15–20, CAUTIOUS is 20–25, and BEAR is 25 or above — those four labels are what the app displays. Nothing else moves the label: not the advancer count, not rates, not the sector ranking. We used to describe this as a blend of those inputs; it never was one, and the page now states the thresholds instead.",
        },
        {
          q: "How is the Fear & Greed score different from CNN's?",
          a: "Same labels (Extreme Fear / Fear / Neutral / Greed / Extreme Greed), different inputs. CNN blends seven inputs including put/call ratio, junk bond demand, market momentum, etc. Tapeline uses four: VIX, advancers today, the regime label, and SPY 5d momentum. Two of those four are VIX-derived, since the regime label is itself a VIX threshold read — so our score leans on volatility more than the four-way split suggests. Every component score is visible in the response, so you can audit which input is driving the headline number.",
        },
        {
          q: "How often does the regime update?",
          a: "Every worker tick — sub-60 seconds during US market hours. The underlying FRED series (VIX, 10Y) update once a day at end-of-day, so the regime label only moves when that daily VIX close crosses a threshold; the advancer count and SPY momentum are live; the Fear & Greed composite recomputes on each tick.",
        },
        {
          q: "Does the regime change scoring weights?",
          a: "No — Tapeline's six factors (Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum) and the ordering of their weights are fixed and public; the exact numeric weights are not published. The regime classifier is a separate macro context indicator. What changes per regime isn't the scoring, it's which scores you might pay more attention to: high-momentum names in Risk On, high-quality fundamentals + low-beta names in Risk Off.",
        },
        {
          q: "What is 'advancers today' exactly?",
          a: "Of the names that moved today, the share that closed up: advancers ÷ (advancers + decliners), computed live from the Tapeline scoring universe each tick. Names with no price read for the day, and names that closed unchanged, are excluded from both sides. It is a same-day advance/decline ratio, so 50% means advancers and decliners were balanced. It is not the percentage of stocks above their 200-day moving average — that is a different measure, and we do not currently publish it. One session's ratio describes that session only; it is not a trend reading.",
        },
        {
          q: "What tier do I need?",
          a: "Market regime is a Pro feature ($8.25/mo billed annually, or $9.99/mo monthly). The 14-day Premium trial includes it. Premium adds Congressional trades, recent insider buys (SEC Form 4) on top of everything in Pro.",
        },
      ]}
      tier="pro"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Regime card */}
        <div className="rounded-2xl border border-accent/30 bg-gradient-to-br from-accent/10 via-panel to-panel p-6">
          <div className="flex items-center gap-2">
            <p className="text-xs uppercase tracking-wider text-muted">Current regime</p>
            {live && (
              <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted">
                <span className="h-1.5 w-1.5 rounded-full bg-muted" />
                Cached
              </span>
            )}
          </div>
          <p className="mt-2 text-5xl font-bold tracking-tight text-accent">{data.regime}</p>
          <p className="mt-3 text-xs text-muted leading-relaxed">
            Set by the VIX against four fixed thresholds. Updated each worker
            tick (~60s).
          </p>
          <p className="mt-4 text-[11px] uppercase tracking-wider text-subtle">
            Highest-scoring sectors (our composite)
          </p>
          <p className="text-xs">{data.sector_leaders}</p>
        </div>

        {/* Fear & Greed card */}
        <div className="rounded-2xl border border-border bg-panel/40 p-6">
          <p className="text-xs uppercase tracking-wider text-muted">Fear &amp; Greed</p>
          <div className="mt-2 flex items-baseline gap-3">
            <span className={`text-5xl font-bold tracking-tight ${data.fear_greed ? fgTone : "text-muted"}`}>
              {data.fear_greed ? data.fear_greed.score : EMPTY}
            </span>
            <span className={`text-base font-semibold uppercase tracking-wider ${data.fear_greed ? fgTone : "text-muted"}`}>
              {data.fear_greed ? data.fear_greed.label : "No reading held"}
            </span>
          </div>
          <p className="mt-3 text-xs text-muted leading-relaxed">
            Blended from VIX, advancers today, the regime label, and 5-day SPY
            momentum. The composite maps to 0–24 Extreme Fear, 25–44 Fear,
            45–54 Neutral, 55–74 Greed, 75–100 Extreme Greed.
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="VIX" value={data.vix != null ? data.vix.toFixed(2) : EMPTY} />
        <Kpi label="10Y Yield" value={data.yield_10y != null ? `${data.yield_10y.toFixed(2)}%` : EMPTY} />
        <Kpi label="Rate direction" value={data.rate_direction || EMPTY} />
        <Kpi
          label="Advancers today (% of names that moved)"
          value={data.breadth_pct != null ? `${data.breadth_pct.toFixed(1)}%` : EMPTY}
        />
      </div>

      <p className="mt-3 text-xs text-subtle">
        {live ? "Cached snapshot — refreshes hourly." : "Snapshot example."} The{" "}
        <Link href="/app/regime" className="text-accent hover:underline">
          live regime panel
        </Link>{" "}
        updates every 60s with the live Fear &amp; Greed dial and full
        component-score breakdown.
      </p>
    </SeoFeaturePage>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-panel/40 p-4">
      <div className="text-[10px] uppercase tracking-wider text-subtle">{label}</div>
      <div className="mt-1 text-2xl font-bold tracking-tight nums">{value}</div>
    </div>
  );
}
