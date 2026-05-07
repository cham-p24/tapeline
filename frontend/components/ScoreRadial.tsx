/**
 * 6-axis radar showing each factor's contribution to the Tapeline Score.
 *
 * Visual signature for the score — same role Simply Wall St's "Snowflake"
 * plays for theirs. Each axis is one of the 6 factors; the radius along
 * each axis is the sub-score 0–100. The filled polygon's *shape* tells you
 * at a glance whether the score is balanced (regular hexagon-ish) or
 * lopsided (stretched on momentum, weak on fundamentals, etc.).
 *
 * Pure SVG, no charting lib — keeps bundle small and lets the rendered
 * markup match the dark-mode design tokens exactly.
 *
 * Axis order matches the published formula on /how-it-works:
 *   12  Trend        (25%)
 *    2  Relative str (20%)
 *    4  Fundamentals (15%)
 *    6  Smart money  (15%)
 *    8  Macro        (15%)
 *   10  Momentum     (10%)
 */
type Sub = number | null | undefined;

type Props = {
  trend: Sub;
  rs: Sub;
  fundamentals: Sub;
  smart_money: Sub;
  macro: Sub;
  momentum: Sub;
  score?: number | null;
  /** Pixel size; SVG is square. Default 220. */
  size?: number;
  /** Show the composite score number in the centre. Default true. */
  showCenter?: boolean;
  /** Show factor labels around the outside. Default true. */
  showLabels?: boolean;
};

const FACTORS = [
  { key: "trend",        short: "Trend",  weight: 25 },
  { key: "rs",           short: "RS",     weight: 20 },
  { key: "fundamentals", short: "Fund",   weight: 15 },
  { key: "smart_money",  short: "SM",     weight: 15 },
  { key: "macro",        short: "Macro",  weight: 15 },
  { key: "momentum",     short: "Mom",    weight: 10 },
] as const;

export function ScoreRadial({
  trend, rs, fundamentals, smart_money, macro, momentum,
  score,
  size = 220,
  showCenter = true,
  showLabels = true,
}: Props) {
  const values: Record<string, Sub> = {
    trend, rs, fundamentals, smart_money, macro, momentum,
  };

  // Geometry. Reserve ~28% of the half-extent for the label gutter so
  // letters don't clip against the SVG edge at small sizes.
  const cx = size / 2;
  const cy = size / 2;
  const labelGutter = showLabels ? 0.28 : 0.05;
  const rMax = (size / 2) * (1 - labelGutter);

  // Convert factor index → polar coordinate. Start at -90° (top), step 60°.
  function pointAt(i: number, fraction: number) {
    const angleDeg = -90 + i * 60;
    const angle = (angleDeg * Math.PI) / 180;
    const r = rMax * Math.max(0, Math.min(1, fraction));
    return {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
  }

  // Reference rings at 25/50/75/100% for context.
  const rings = [0.25, 0.5, 0.75, 1.0];

  // Hexagonal grid points (the "frame" connecting axis endpoints at each ring).
  function hexPath(fraction: number): string {
    return FACTORS.map((_, i) => {
      const p = pointAt(i, fraction);
      return `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`;
    }).join(" ") + " Z";
  }

  // Filled value polygon. Missing factors render at 0 (collapses inward),
  // visually distinguishing data-thin tickers from comprehensive ones.
  const valuePoints = FACTORS.map((f, i) => {
    const v = values[f.key];
    const frac = v == null ? 0 : v / 100;
    return pointAt(i, frac);
  });
  const valuePath = valuePoints
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(" ") + " Z";

  // Score-tier colour echoes /how-it-works tier system. Defaults to accent
  // when score isn't provided.
  const tone =
    score == null            ? "var(--accent, #3b82f6)" :
    score >= 70              ? "var(--up, #22c55e)" :
    score >= 55              ? "var(--accent, #3b82f6)" :
    score >= 40              ? "var(--muted, #94a3b8)" :
    score >= 25              ? "rgb(250, 204, 21)" :
                               "var(--down, #ef4444)";

  const labelRadius = (size / 2) * (1 - labelGutter * 0.4);
  function labelPos(i: number) {
    const angleDeg = -90 + i * 60;
    const angle = (angleDeg * Math.PI) / 180;
    return {
      x: cx + labelRadius * Math.cos(angle),
      y: cy + labelRadius * Math.sin(angle),
    };
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`Tapeline Score radial: trend ${pretty(trend)}, RS ${pretty(rs)}, fundamentals ${pretty(fundamentals)}, smart money ${pretty(smart_money)}, macro ${pretty(macro)}, momentum ${pretty(momentum)}`}
      className="block"
    >
      {/* Reference rings */}
      {rings.map((r) => (
        <path
          key={r}
          d={hexPath(r)}
          fill="none"
          stroke="currentColor"
          strokeOpacity={r === 1 ? 0.25 : 0.08}
          strokeWidth={r === 1 ? 1 : 0.75}
          className="text-muted"
        />
      ))}

      {/* Axis spokes */}
      {FACTORS.map((_, i) => {
        const p = pointAt(i, 1);
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={p.x}
            y2={p.y}
            stroke="currentColor"
            strokeOpacity={0.1}
            strokeWidth={0.75}
            className="text-muted"
          />
        );
      })}

      {/* Value polygon */}
      <path d={valuePath} fill={tone} fillOpacity={0.18} stroke={tone} strokeWidth={1.75} strokeLinejoin="round" />

      {/* Vertex dots */}
      {valuePoints.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={2.5} fill={tone} />
      ))}

      {/* Labels */}
      {showLabels &&
        FACTORS.map((f, i) => {
          const p = labelPos(i);
          // Anchor based on which side of the centre the label sits, so text
          // hugs toward the radial rather than overlapping the polygon.
          const anchor = p.x < cx - 1 ? "end" : p.x > cx + 1 ? "start" : "middle";
          return (
            <text
              key={f.key}
              x={p.x}
              y={p.y}
              textAnchor={anchor}
              dominantBaseline="middle"
              className="fill-current text-muted"
              style={{ fontSize: Math.round(size * 0.052) }}
            >
              {f.short}
            </text>
          );
        })}

      {/* Centre score */}
      {showCenter && score != null && (
        <>
          <text
            x={cx}
            y={cy - size * 0.01}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-current font-bold"
            style={{ fontSize: Math.round(size * 0.18), fill: tone }}
          >
            {Math.round(score)}
          </text>
          <text
            x={cx}
            y={cy + size * 0.11}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-current text-subtle"
            style={{ fontSize: Math.round(size * 0.055) }}
          >
            / 100
          </text>
        </>
      )}
    </svg>
  );
}

function pretty(v: Sub): string {
  return v == null ? "—" : v.toFixed(0);
}
