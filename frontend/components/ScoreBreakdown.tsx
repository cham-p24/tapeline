"use client";

/**
 * The synthesis moat, made visible.
 *
 * Shows the weighted contribution of each factor to the composite score.
 * Used as a hover popover on every scanner row + as a full panel on the
 * ticker detail page.
 *
 * DATA PROVENANCE (see backend/app/services/polygon_feed.py fetch_snapshots
 * docstring, "Strategy" section). In production today only Fundamentals is
 * sourced from live data, alongside the Price and Volume inputs. The other
 * five sub-scores — Trend, Relative strength, Smart money, Macro, Momentum —
 * are placeholder values until each factor's live source is wired in, so the
 * composite and the per-ticker reason are partly placeholder too. We tag the
 * five inline rather than let them read as live data. Flip `live: true` on a
 * row here in the same PR that moves that factor to a live source.
 */

const LIVE_TOOLTIP =
  "Not yet powered by live data — placeholder pending its live source.";

/** Small inline marker on a factor that is not yet sourced from live data. */
function BetaTag() {
  return (
    <span
      title={LIVE_TOOLTIP}
      aria-label={`beta — ${LIVE_TOOLTIP}`}
      className="ml-1.5 inline-block cursor-help rounded border border-border px-1 text-[0.55rem] font-medium uppercase tracking-wide text-subtle align-middle"
    >
      beta
    </span>
  );
}

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
  // `live` marks whether the sub-score is sourced from live data today; the
  // five placeholder factors carry a beta tag so they never read as live.
  const rows = [
    { label: "Trend", value: trend, emphasis: "most", live: false },
    { label: "Relative strength", value: rs, emphasis: "high", live: false },
    { label: "Fundamentals", value: fundamentals, emphasis: "core", live: true },
    { label: "Smart money", value: smart_money, emphasis: "core", live: false },
    { label: "Macro", value: macro, emphasis: "core", live: false },
    { label: "Momentum", value: momentum, emphasis: "least", live: false },
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
                <span className="text-muted">
                  {r.label} <span className="opacity-50">({r.emphasis})</span>
                  {!r.live && <BetaTag />}
                </span>
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
      {/* Honest provenance footnote. Keeps the tags from reading as a defect
          badge: it names what IS live and frames the rest as in-migration. */}
      <p className="mt-3 border-t border-border/40 pt-2 text-[0.65rem] leading-snug text-subtle">
        Live data today: Fundamentals, plus the Price and Volume inputs. The
        factors tagged <span className="uppercase tracking-wide">beta</span> run
        on placeholder values while each is migrated to its live source.
      </p>
    </div>
  );
}
