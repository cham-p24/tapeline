/**
 * 6-axis radar showing each factor's sub-score behind the Tapeline Score.
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
 * Axis order matches the factor order on /how-it-works (descending weight,
 * Trend heaviest through Momentum lightest):
 *   12  Trend
 *    2  Relative str
 *    4  Fundamentals
 *    6  Smart money
 *    8  Macro
 *   10  Momentum
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

// Descending weight order (Trend heaviest through Momentum lightest); exact
// weights are intentionally not encoded here.
const FACTORS = [
  { key: "trend",        short: "Trend" },
  { key: "rs",           short: "RS" },
  { key: "fundamentals", short: "Fund" },
  { key: "smart_money",  short: "SM" },
  { key: "macro",        short: "Macro" },
  { key: "momentum",     short: "Mom" },
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

  // Value polygon. A factor we hold NO value for is not plotted: it used to be
  // pushed to the origin, which draws exactly the same shape as a measured
  // near-zero, so a data-thin ticker read as a scored-badly one. Absence now
  // BREAKS the outline on that axis (no vertex, no dot, the spoke is dashed
  // below) and the reader can see the ring is simply open there.
  const valueVertices = FACTORS.map((f, i) => {
    const v = values[f.key];
    return v == null ? null : { i, ...pointAt(i, v / 100) };
  });
  const valuePoints = valueVertices.filter((p) => p != null);
  const hasGap = valuePoints.length < FACTORS.length;

  // Walk the six axes and start a fresh sub-path after every gap, so a stroke
  // is drawn only between two axes we hold ADJACENT readings for. When there
  // is a gap the walk starts at the first axis following one, so a run that
  // wraps past Momentum → Trend draws as a single arc, not two stubs.
  const n = FACTORS.length;
  const firstAfterGap = valueVertices.findIndex(
    (p, i) => p != null && valueVertices[(i + n - 1) % n] == null,
  );
  const start = hasGap && firstAfterGap >= 0 ? firstAfterGap : 0;
  const segments: string[] = [];
  let current: string[] = [];
  for (let k = 0; k < n; k++) {
    const p = valueVertices[(start + k) % n];
    if (p == null) {
      if (current.length > 1) segments.push(current.join(" "));
      current = [];
      continue;
    }
    current.push(`${current.length === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`);
  }
  if (current.length > 1) segments.push(current.join(" "));
  // Only a complete hexagon closes (and only a closed ring may be filled): an
  // implicit close across a gap would paint area over an axis we hold nothing
  // for, which is the misreading this is fixing.
  const valuePath = hasGap ? segments.join(" ") : segments.join(" ") + " Z";

  // Score-tier colour echoes /how-it-works tier system. Defaults to accent
  // when score isn't provided.
  //
  // The design tokens are space-separated RGB TRIPLETS (globals.css:
  // `--accent: 0 122 255`), so they must be consumed as `rgb(var(--token))`
  // like every other call site. Passing the bare `var(--accent)` yields
  // `fill="0 122 255"`, which is not a valid <color>: the browser discards it
  // and falls back to the SVG initial values — fill:black, stroke:none — so the
  // whole factor polygon rendered invisible against the dark card (verified in
  // prod: computed fill was rgb(0,0,0), stroke none). The `#3b82f6`-style
  // fallbacks never fired either, because the tokens ARE defined; the fallback
  // now lives inside rgb() as a triplet so it works if a token is ever missing.
  const tone =
    score == null            ? "rgb(var(--accent, 0 122 255))" :
    score >= 70              ? "rgb(var(--up, 26 127 55))" :
    score >= 55              ? "rgb(var(--accent, 0 122 255))" :
    score >= 40              ? "rgb(var(--muted, 113 113 122))" :
    score >= 25              ? "rgb(250, 204, 21)" :
                               "rgb(var(--down, 193 18 31))";

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
          // 0.08 was far too faint to read as a grid on the dark card — the
          // hexagonal "web" is the whole point of the visual, so lift the inner
          // rings and the outer frame to where they're actually legible.
          strokeOpacity={r === 1 ? 0.35 : 0.14}
          strokeWidth={r === 1 ? 1 : 0.75}
          className="text-muted"
        />
      ))}

      {/* Axis spokes. An axis we hold no reading for is dashed and carries a
          <title>, so absence has a visible treatment of its own instead of
          being silently indistinguishable from a measured zero. */}
      {FACTORS.map((f, i) => {
        const p = pointAt(i, 1);
        const missing = values[f.key] == null;
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={p.x}
            y2={p.y}
            stroke="currentColor"
            strokeOpacity={0.16}
            strokeWidth={0.75}
            strokeDasharray={missing ? "2 3" : undefined}
            data-missing={missing ? "true" : undefined}
            className="text-muted"
          >
            {missing && <title>{`${f.short}: no reading held`}</title>}
          </line>
        );
      })}

      {/* Value polygon — draws in via stroke-dashoffset on mount, then the
          fill + dots fade in just behind. Honours prefers-reduced-motion.
          Filled only when all six axes are held: on an incomplete ring the
          fill would have to close across the gap, painting area over an axis
          we hold no value for. Open outline, no area, on those. */}
      {valuePath && (
        <path
          d={valuePath}
          fill={hasGap ? "none" : tone}
          fillOpacity={hasGap ? 0 : 0.18}
          stroke={tone}
          strokeWidth={1.75}
          strokeLinejoin="round"
          strokeLinecap="round"
          className="radial-polygon"
          data-complete={hasGap ? "false" : "true"}
        />
      )}

      {/* Vertex dots — one per axis we actually hold a value for. */}
      <g className="radial-fade-in">
        {valuePoints.map((p) => (
          <circle key={p.i} cx={p.x} cy={p.y} r={2.5} fill={tone} />
        ))}
      </g>

      {/* Labels */}
      {showLabels &&
        FACTORS.map((f, i) => {
          const p = labelPos(i);
          // Anchor based on which side of the centre the label sits, so text
          // hugs toward the radial rather than overlapping the polygon.
          const anchor = p.x < cx - 1 ? "end" : p.x > cx + 1 ? "start" : "middle";
          // Keep the label inside the viewBox. The anchor makes text grow AWAY
          // from centre, so a long label on a 150°/210° vertex starts left of
          // x=0 and the SVG clips it: "Macro" rendered as "lacro" on /t/AAPL,
          // and shipped that way in the press screenshot. Nudging x inward is
          // enough — these vertices sit well clear of the polygon — and the
          // width estimate only has to be close, since it is a floor not a
          // layout. 0.62em per character is a safe over-estimate for the
          // geometric sans this renders in.
          const fontSize = Math.round(size * 0.052);
          const approxWidth = f.short.length * fontSize * 0.62;
          const x =
            anchor === "end"
              ? Math.max(p.x, approxWidth + 2)
              : anchor === "start"
                ? Math.min(p.x, size - approxWidth - 2)
                : p.x;
          return (
            <text
              key={f.key}
              x={x}
              y={p.y}
              textAnchor={anchor}
              dominantBaseline="middle"
              className="fill-current text-muted"
              style={{ fontSize }}
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
