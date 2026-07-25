"use client";

/**
 * The synthesis moat, made visible.
 *
 * Shows the weighted contribution of each factor to the composite score.
 * Used as a hover popover on every scanner row + as a full panel on the
 * ticker detail page.
 */
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
          const v = r.value ?? 0;
          const color =
            v >= 70 ? "bg-up"
            : v >= 45 ? "bg-accent"
            : v >= 30 ? "bg-yellow-500"
            : "bg-down";
          return (
            <div key={r.label} className="text-xs">
              <div className="flex justify-between">
                <span className="text-muted">{r.label} <span className="opacity-50">({r.emphasis})</span></span>
                <span className="nums font-medium">{v.toFixed(0)}</span>
              </div>
              <div className="mt-1 h-1.5 w-full rounded-full bg-panel">
                <div
                  className={`h-full rounded-full ${color}`}
                  style={{ width: `${Math.max(2, v)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
