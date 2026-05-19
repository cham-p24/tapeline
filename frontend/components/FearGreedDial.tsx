/**
 * Fear & Greed dial — semi-circle gauge with a needle pointing at the score.
 *
 * Mirrors CNN's familiar 0-100 layout (Extreme Fear → Extreme Greed) so any
 * trader who's seen one before knows what they're looking at instantly.
 *
 * Pure SVG — no chart library dep. Renders crisp at any size.
 */
"use client";

type Props = {
  score: number;         // 0-100
  label: string;         // "Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed"
  color: string;         // tailwind token: "down" | "yellow-400" | "muted" | "accent" | "up"
};

// Map our color tokens to the actual hex values used by the Tailwind palette
// (matches /how-it-works tier colours). Inlined because SVG <stop> needs hex,
// not a class.
const HEX: Record<string, string> = {
  down: "#ef4444",
  "yellow-400": "#fbbf24",
  muted: "#a1a1aa",
  accent: "#14b8a6",
  up: "#22c55e",
};

// Geometry — 200x110 viewbox; arc from 180° (left) to 0° (right) sweeping
// through the top. cx/cy is the centre of the circle, R the radius.
const VB_W = 200;
const VB_H = 115;
const CX = 100;
const CY = 100;
const R = 80;

function polar(angleDeg: number, radius = R) {
  const rad = ((180 - angleDeg) * Math.PI) / 180;
  return { x: CX + radius * Math.cos(rad), y: CY - radius * Math.sin(rad) };
}

// Score-to-angle. polar() below treats 0° as leftmost (the EXTREME FEAR end
// of the arc) and 180° as rightmost (EXTREME GREED). Score 0 → 0° → left;
// score 100 → 180° → right. The previous `180 - …` had this inverted, so a
// greed reading of 71 pointed at the fear side. Caught 2026-05-17.
function angleFor(score: number) {
  const s = Math.max(0, Math.min(100, score));
  return (s / 100) * 180;
}

export function FearGreedDial({ score, label, color }: Props) {
  const accentHex = HEX[color] ?? HEX.muted;
  const needleAngle = angleFor(score);
  const needleEnd = polar(needleAngle, R - 8);

  // Outer arc from left (180°) to right (0°)
  const arcStart = polar(180);
  const arcEnd = polar(0);

  // Tick marks at 25, 50, 75 (the bucket boundaries)
  const ticks = [25, 50, 75].map((s) => {
    const a = angleFor(s);
    const inner = polar(a, R - 6);
    const outer = polar(a, R + 4);
    return { s, x1: inner.x, y1: inner.y, x2: outer.x, y2: outer.y };
  });

  return (
    <div className="flex flex-col items-center">
      <svg
        viewBox={`0 0 ${VB_W} ${VB_H}`}
        className="w-full max-w-sm"
        role="img"
        aria-label={`Fear and Greed Index: ${score} (${label})`}
      >
        <defs>
          {/* Gradient across the arc — red (fear) → amber → green (greed) */}
          <linearGradient id="fg-arc-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor="#ef4444" />
            <stop offset="25%"  stopColor="#fbbf24" />
            <stop offset="50%"  stopColor="#a1a1aa" />
            <stop offset="75%"  stopColor="#14b8a6" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
        </defs>

        {/* Background arc */}
        <path
          d={`M ${arcStart.x} ${arcStart.y} A ${R} ${R} 0 0 1 ${arcEnd.x} ${arcEnd.y}`}
          fill="none"
          stroke="url(#fg-arc-gradient)"
          strokeWidth="14"
          strokeLinecap="round"
        />

        {/* Tick marks */}
        {ticks.map((t) => (
          <line
            key={t.s}
            x1={t.x1}
            y1={t.y1}
            x2={t.x2}
            y2={t.y2}
            stroke="#52525b"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        ))}

        {/* Needle base + line */}
        <line
          x1={CX}
          y1={CY}
          x2={needleEnd.x}
          y2={needleEnd.y}
          stroke={accentHex}
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx={CX} cy={CY} r="6" fill={accentHex} stroke="#0a0a0a" strokeWidth="2" />

        {/* End-cap labels under the arc */}
        <text x="12"  y={CY + 14} fontSize="7" fill="#52525b">EXTREME FEAR</text>
        <text x="138" y={CY + 14} fontSize="7" fill="#52525b">EXTREME GREED</text>
      </svg>

      <div className="mt-3 flex items-baseline gap-3">
        <span className="text-5xl font-bold nums tracking-tight" style={{ color: accentHex }}>
          {score}
        </span>
        <span className="text-base font-semibold uppercase tracking-wider" style={{ color: accentHex }}>
          {label}
        </span>
      </div>
    </div>
  );
}
