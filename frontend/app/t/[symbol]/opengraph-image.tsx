/**
 * Per-ticker dynamic Open Graph image — the centrepiece of the viral loop.
 *
 * When anyone pastes https://tapeline.io/t/NVDA into Twitter / LinkedIn /
 * Slack / iMessage, the platform fetches THIS edge function. It pulls the
 * ticker's live data from the API and renders a 1200x630 PNG showing the
 * score, signal, price, and 1-day change. That preview self-sells.
 *
 * Cached at the CDN by Vercel for ~60s (matches the worker tick), so even a
 * tweet that gets thousands of crawls doesn't hammer the API.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export const alt = "Tapeline Score for this ticker";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

type FactorEntry = { value: number | null; weight: number; label: string };

type TickerData = {
  symbol: string;
  name: string;
  sector: string | null;
  price: number | null;
  score: number | null;
  signal: string | null;
  change_pct_1d: number | null;
  reason: string | null;
  // The score breakdown drives the small radial signature in the corner
  // of the OG image. Same shape as the /api/ticker response.
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
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return (await res.json()) as TickerData;
  } catch {
    return null;
  }
}

export default async function OG({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const sym = symbol.toUpperCase();
  const data = await fetchTicker(sym);

  // Score-tier accent (mirrors /how-it-works tier colours)
  const score = data?.score ?? null;
  const signal = data?.signal ?? "—";
  const change = data?.change_pct_1d ?? null;
  const accent =
    score == null
      ? "#71717a"
      : score >= 70
      ? "#22c55e" // up green
      : score >= 55
      ? "#14b8a6" // accent teal
      : score >= 40
      ? "#a1a1aa" // muted
      : score >= 25
      ? "#fbbf24" // amber
      : "#ef4444"; // down red

  const accentSoft = `${accent}1f`; // ~12% alpha for backgrounds

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: "linear-gradient(135deg, #07090c 0%, #0d1218 50%, #0a0f15 100%)",
          padding: "70px 80px",
          fontFamily: "Inter, system-ui, sans-serif",
          color: "#f4f4f5",
          position: "relative",
        }}
      >
        {/* Tier-coloured corner glow */}
        <div
          style={{
            position: "absolute",
            top: "-200px",
            right: "-200px",
            width: "560px",
            height: "560px",
            background: `radial-gradient(circle, ${accent}33 0%, transparent 70%)`,
            display: "flex",
          }}
        />

        {/* Brand row */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div
            style={{
              width: "56px",
              height: "12px",
              background: "linear-gradient(90deg, #22c55e 0%, #14b8a6 100%)",
              borderRadius: "999px",
              display: "flex",
            }}
          />
          <span style={{ fontSize: "30px", fontWeight: 600, letterSpacing: "-0.02em" }}>
            Tapeline
          </span>
          <span style={{ fontSize: "26px", color: "#52525b", marginLeft: "auto", display: "flex" }}>
            tapeline.io/t/{sym}
          </span>
        </div>

        {/* Header — symbol + name */}
        <div style={{ marginTop: "60px", display: "flex", alignItems: "baseline", gap: "20px" }}>
          <span style={{ fontSize: "120px", fontWeight: 700, letterSpacing: "-0.04em", display: "flex" }}>
            {sym}
          </span>
          {data?.name && (
            <span style={{ fontSize: "30px", color: "#a1a1aa", maxWidth: "640px", display: "flex" }}>
              {data.name.length > 38 ? data.name.slice(0, 38) + "…" : data.name}
            </span>
          )}
        </div>

        {/* Score + signal block */}
        {data ? (
          <div
            style={{
              marginTop: "32px",
              display: "flex",
              alignItems: "center",
              gap: "40px",
            }}
          >
            <div
              style={{
                padding: "24px 36px",
                borderRadius: "20px",
                background: accentSoft,
                border: `2px solid ${accent}66`,
                display: "flex",
                flexDirection: "column",
                gap: "4px",
              }}
            >
              <span
                style={{
                  fontSize: "16px",
                  color: "#71717a",
                  textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  display: "flex",
                }}
              >
                Score
              </span>
              <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
                <span style={{ fontSize: "84px", fontWeight: 700, color: accent, letterSpacing: "-0.03em" }}>
                  {score != null ? score.toFixed(0) : "—"}
                </span>
                <span style={{ fontSize: "28px", color: "#52525b", display: "flex" }}>/ 100</span>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <span
                style={{
                  fontSize: "16px",
                  color: "#71717a",
                  textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  display: "flex",
                }}
              >
                Signal
              </span>
              <span style={{ fontSize: "44px", fontWeight: 700, color: accent, letterSpacing: "-0.02em", display: "flex" }}>
                {signal}
              </span>
            </div>
          </div>
        ) : (
          <div style={{ marginTop: "32px", fontSize: "32px", color: "#a1a1aa", display: "flex" }}>
            Not in the scanner universe yet.
          </div>
        )}

        {/* Brand-mark radial — corner signature derived from the actual
            sub-scores. Same role Simply Wall St's Snowflake plays in their
            share previews — a recognisable shape that's instantly
            "Tapeline" without requiring the full app surface. */}
        {data && (
          <div
            style={{
              position: "absolute",
              top: "120px",
              right: "80px",
              width: "240px",
              height: "240px",
              display: "flex",
            }}
          >
            <RadialMark data={data} accent={accent} />
          </div>
        )}

        {/* Footer row — price + change + tagline */}
        <div
          style={{
            marginTop: "auto",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
          }}
        >
          {data?.price != null ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span
                style={{
                  fontSize: "14px",
                  color: "#71717a",
                  textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  display: "flex",
                }}
              >
                Last
              </span>
              <div style={{ display: "flex", alignItems: "baseline", gap: "16px" }}>
                <span style={{ fontSize: "44px", fontWeight: 700, letterSpacing: "-0.02em" }}>
                  ${data.price.toFixed(2)}
                </span>
                {change != null && (
                  <span
                    style={{
                      fontSize: "26px",
                      fontWeight: 600,
                      color: change > 0 ? "#22c55e" : change < 0 ? "#ef4444" : "#a1a1aa",
                      display: "flex",
                    }}
                  >
                    {change >= 0 ? "+" : ""}
                    {change.toFixed(2)}%
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div />
          )}
          <div
            style={{
              fontSize: "20px",
              color: "#52525b",
              textAlign: "right",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
            }}
          >
            <span style={{ display: "flex" }}>One score. One sentence.</span>
            <span style={{ display: "flex" }}>Six factors. Public formula.</span>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}

/**
 * Inline 6-axis radial used as the OG image corner brand mark. Pure SVG
 * inside a flex container — next/og's edge runtime supports inline <svg>.
 *
 * Keeps the polygon math identical to <ScoreRadial> so the social preview
 * shape matches what the visitor sees once they click through. Visual
 * continuity from share → page.
 */
function RadialMark({
  data,
  accent,
}: {
  data: TickerData;
  accent: string;
}) {
  const subs = [
    data.breakdown?.trend?.value,
    data.breakdown?.rs?.value,
    data.breakdown?.fundamentals?.value,
    data.breakdown?.smart_money?.value,
    data.breakdown?.macro?.value,
    data.breakdown?.momentum?.value,
  ];
  const size = 240;
  const cx = size / 2;
  const cy = size / 2;
  const rMax = size / 2 - 12;

  function pointAt(i: number, frac: number) {
    const angleDeg = -90 + i * 60;
    const a = (angleDeg * Math.PI) / 180;
    const r = rMax * Math.max(0, Math.min(1, frac));
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)] as const;
  }

  function hexPath(frac: number): string {
    return subs.map((_, i) => {
      const [x, y] = pointAt(i, frac);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ") + " Z";
  }

  const valuePath = subs.map((v, i) => {
    const [x, y] = pointAt(i, v == null ? 0 : v / 100);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ") + " Z";

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: "block" }}>
      {/* reference rings */}
      {[0.25, 0.5, 0.75, 1.0].map((r) => (
        <path key={r} d={hexPath(r)} fill="none" stroke="#52525b" strokeOpacity={r === 1 ? 0.45 : 0.18} strokeWidth={r === 1 ? 1.5 : 1} />
      ))}
      {/* axes */}
      {subs.map((_, i) => {
        const [x, y] = pointAt(i, 1);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="#52525b" strokeOpacity={0.18} strokeWidth={1} />;
      })}
      {/* value polygon */}
      <path d={valuePath} fill={accent} fillOpacity={0.22} stroke={accent} strokeWidth={2.5} strokeLinejoin="round" />
      {/* vertex dots */}
      {subs.map((v, i) => {
        const [x, y] = pointAt(i, v == null ? 0 : v / 100);
        return <circle key={i} cx={x} cy={y} r={3.5} fill={accent} />;
      })}
    </svg>
  );
}
