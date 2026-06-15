import Link from "next/link";
import { SeoFeaturePage } from "@/components/SeoFeaturePage";
import { pageMeta } from "@/lib/seo";

export const revalidate = 3600;

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

export const metadata = pageMeta({
  title: "Market Regime Indicator — Live VIX + Breadth + Rate Direction | Tapeline",
  description:
    "Tapeline's market regime classifier synthesizes VIX, breadth, rate direction, and SPY momentum into one read on macro conditions: Risk On, Neutral, Cautious, Risk Off. Cached snapshot, refreshed hourly.",
  path: "/market-regime",
});

type RegimePreview = {
  regime: string;
  vix: number;
  breadth_pct: number;
  rate_direction: string;
  yield_10y: number;
  fear_greed: { score: number; label: string };
  sector_leaders: string;
};

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
      // Bound the build-time fetch so a degraded/slow API can't hang static
      // export past Next's 60s budget (a hang isn't caught by try/catch).
      // Matches /stocks + /signals; falls back to SHOWCASE below.
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return { data: SHOWCASE, live: false };
    const body = (await res.json()) as Partial<RegimePreview> & { available?: boolean };
    if (!body.available || !body.regime) return { data: SHOWCASE, live: false };
    return {
      data: {
        regime: body.regime,
        vix: body.vix ?? SHOWCASE.vix,
        breadth_pct: body.breadth_pct ?? SHOWCASE.breadth_pct,
        rate_direction: body.rate_direction ?? SHOWCASE.rate_direction,
        yield_10y: body.yield_10y ?? SHOWCASE.yield_10y,
        fear_greed: body.fear_greed ?? SHOWCASE.fear_greed,
        sector_leaders: body.sector_leaders ?? SHOWCASE.sector_leaders,
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
  const fgTone =
    data.fear_greed.score < 25 ? "text-down"
    : data.fear_greed.score < 45 ? "text-warn"
    : data.fear_greed.score < 55 ? "text-muted"
    : data.fear_greed.score < 75 ? "text-accent"
    : "text-up";
  return (
    <SeoFeaturePage
      slug="market-regime"
      eyebrow="Feature · Market regime"
      h1="Market Regime Indicator — Live VIX, Breadth, Rates"
      lede="Every individual scoring decision is downstream of the macro state. Tapeline's regime classifier synthesizes the four inputs that actually drive sector rotation — VIX (volatility), breadth (% of S&P above 200DMA), rate direction (10Y yield slope from FRED), and short-window SPY momentum — into one descriptive read: Risk On, Neutral, Cautious, or Risk Off. The Fear &amp; Greed dial blends the same inputs into the familiar 0–100 sentiment scale."
      methodology={{
        heading: "How the regime is computed",
        body: (
          <>
            <p>
              Four inputs, each weighted into a composite Fear &amp; Greed score:
              VIX (35%, lower = greed), breadth (30%, more % above 200DMA = greed),
              regime label (20%, BULL/NEUTRAL/CAUTIOUS/BEAR), and 5-day SPY
              momentum (15%, positive = greed). The composite maps to{" "}
              <strong>0&ndash;24 Extreme Fear</strong>, <strong>25&ndash;44 Fear</strong>,{" "}
              <strong>45&ndash;54 Neutral</strong>, <strong>55&ndash;74 Greed</strong>,{" "}
              <strong>75&ndash;100 Extreme Greed</strong> &mdash; matches the labels
              CNN&rsquo;s familiar version uses so anyone who&rsquo;s seen one before
              can read it instantly.
            </p>
            <p>
              The regime label itself anchors more loosely. <strong>Risk On</strong>{" "}
              when VIX is low, breadth is wide, and rates aren&rsquo;t threatening
              a sharp move. <strong>Risk Off</strong> when those flip. Most days
              are <strong>Neutral</strong> or <strong>Cautious</strong> &mdash; the
              regime isn&rsquo;t a coin flip, it&rsquo;s a slow-moving
              classification that filters which factor weights deserve more
              weight in this moment of the cycle.
            </p>
            <p>
              All four macro inputs come from FRED via the free-tier API: VIX
              (VIXCLS), 10Y yield (DGS10), USD broad index (DTWEXBGS). Breadth
              and sector leaders are computed live each worker tick across the
              full Tapeline universe. Full live regime panel + Fear &amp; Greed dial
              at{" "}
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
          q: "What's the difference between 'Risk On' and 'Risk Off'?",
          a: "Risk On means the macro inputs that historically support equity gains are aligned: low VIX (calm), wide breadth (broad participation, not just mega-caps carrying the index), and stable or falling rates. Risk Off is the opposite — VIX spiking, breadth narrowing, rates jumping. Neutral and Cautious sit between, and reflect the fact that most days aren't unambiguously one or the other.",
        },
        {
          q: "How is the Fear & Greed score different from CNN's?",
          a: "Same labels (Extreme Fear / Fear / Neutral / Greed / Extreme Greed), different inputs. CNN blends seven inputs including put/call ratio, junk bond demand, market momentum, etc. Tapeline uses four: VIX, breadth, regime label, SPY 5d momentum. The simpler input set converges on similar reads but is fully transparent — every component score is visible in the response, so you can audit which input is driving the headline number.",
        },
        {
          q: "How often does the regime update?",
          a: "Every worker tick — sub-60 seconds during US market hours. The underlying FRED series (VIX, 10Y) update once a day at end-of-day; the breadth and SPY momentum inputs are live; the composite recomputes on each tick.",
        },
        {
          q: "Does the regime change scoring weights?",
          a: "No — Tapeline's 6-factor weights (Trend 25% / RS 20% / Fund 15% / SM 15% / Macro 15% / Mom 10%) are fixed and public. The regime classifier is a separate macro context indicator. What changes per regime isn't the formula, it's which scores you might pay more attention to: high-momentum names in Risk On, high-quality fundamentals + low-beta names in Risk Off.",
        },
        {
          q: "What's 'breadth' here exactly?",
          a: "Percentage of S&P 500 components trading above their 200-day moving average. Above 70% = broad participation, equity rally is healthy. Below 30% = narrow market, the rally is concentrated and fragile. Mid-range (40–60%) is the most common state. Computed live from the underlying Tapeline scoring universe each tick.",
        },
        {
          q: "What tier do I need?",
          a: "Market regime is a Pro feature ($24.99/mo billed annually, or $29.99/mo monthly). The 14-day Premium trial includes it. Premium adds Congressional trades, recent insider buys (SEC Form 4), and unlimited Telegram alerts on top of everything in Pro.",
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
            Synthesized from VIX, breadth, rate direction, and short-window SPY
            momentum. Updated each worker tick (~60s).
          </p>
          <p className="mt-4 text-[11px] uppercase tracking-wider text-subtle">
            Sector leaders
          </p>
          <p className="text-xs">{data.sector_leaders}</p>
        </div>

        {/* Fear & Greed card */}
        <div className="rounded-2xl border border-border bg-panel/40 p-6">
          <p className="text-xs uppercase tracking-wider text-muted">Fear &amp; Greed</p>
          <div className="mt-2 flex items-baseline gap-3">
            <span className={`text-5xl font-bold tracking-tight ${fgTone}`}>
              {data.fear_greed.score}
            </span>
            <span className={`text-base font-semibold uppercase tracking-wider ${fgTone}`}>
              {data.fear_greed.label}
            </span>
          </div>
          <p className="mt-3 text-xs text-muted leading-relaxed">
            VIX 35% · Breadth 30% · Regime 20% · SPY 5d 15%. The composite maps
            to 0–24 Extreme Fear, 25–44 Fear, 45–54 Neutral, 55–74 Greed, 75–100
            Extreme Greed.
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="VIX" value={data.vix.toFixed(2)} />
        <Kpi label="10Y Yield" value={`${data.yield_10y.toFixed(2)}%`} />
        <Kpi label="Rate direction" value={data.rate_direction} />
        <Kpi label="Breadth above 200DMA" value={`${data.breadth_pct.toFixed(1)}%`} />
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
