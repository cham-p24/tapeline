"use client";

/**
 * The synthesis moat, made visible.
 *
 * Shows each factor's 0–100 sub-score, listed in descending weight order.
 * NOT the weighted contribution: the marketing surfaces state the ordering
 * rather than the constants (PR #342), so the ordering plus the qualitative
 * emphasis label is all this component shows. A copy rule, not a secrecy
 * claim - the repo is public.
 * Used as a hover popover on every scanner row + as a full panel on the
 * ticker detail page.
 *
 * A sub-score we do not hold is NOT a zero. The backend deliberately stores
 * NULL for a factor it has no reading for, and most of the universe is missing
 * at least one, so this path fires constantly. Absence renders as an em-dash
 * over an EMPTY track — the same contract components/ScorePanel.tsx applies to
 * the same six factors on the ticker page. A real measured 0 still renders as
 * "0" with a bar in the bottom band; only the unknown is blank.
 */

/** The single, deliberate rendering of "we do not hold this value". */
const EMPTY = "—";

export function ScoreBreakdown({
  trend, rs, fundamentals, momentum, macro, smart_money,
  reason,
  compact = false,
}: {
  trend?: number | null;
  rs?: number | null;
  fundamentals?: number | null;
  momentum?: number | null;
  macro?: number | null;
  smart_money?: number | null;
  reason?: string | null;
  compact?: boolean;
}) {
  // Listed in descending weight order. We show the qualitative emphasis
  // (which factors carry the most weight) rather than exact percentages.
  const rows = [
    { label: "Trend", value: trend, emphasis: "most" },
    { label: "Relative strength", value: rs, emphasis: "high" },
    { label: "Fundamentals", value: fundamentals, emphasis: "core" },
    { label: "Smart money", value: smart_money, emphasis: "core" },
    { label: "Macro", value: macro, emphasis: "core" },
    { label: "Momentum", value: momentum, emphasis: "least" },
  ];
  return (
    <div className={compact ? "w-64 p-3" : "p-4"}>
      {reason && (
        <p className="mb-3 text-sm text-muted italic">&ldquo;{reason}&rdquo;</p>
      )}
      <div className="space-y-2">
        {rows.map((r) => {
          const v = r.value ?? null;
          // Bands apply only where a value exists. The old `?? 0` sent every
          // missing factor into the bottom band, painting a red bar under a
          // measured-looking "0" for a reading we never had.
          const color =
            v == null ? null
            : v >= 70 ? "bg-up"
            : v >= 45 ? "bg-accent"
            : v >= 30 ? "bg-yellow-500"
            : "bg-down";
          return (
            <div key={r.label} className="text-xs">
              <div className="flex justify-between">
                <span className="text-muted">{r.label} <span className="opacity-50">({r.emphasis})</span></span>
                <span
                  className={v == null ? "nums font-medium text-muted" : "nums font-medium"}
                  title={v == null ? "No reading held for this factor" : undefined}
                >
                  {v != null ? v.toFixed(0) : EMPTY}
                </span>
              </div>
              {/* Empty track, no bar: an unknown must not read as a
                  measurement sitting at the bottom of the scale. */}
              <div className="mt-1 h-1.5 w-full rounded-full bg-panel">
                {v != null && (
                  <div
                    className={`h-full rounded-full ${color}`}
                    style={{ width: `${Math.max(2, v)}%` }}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
