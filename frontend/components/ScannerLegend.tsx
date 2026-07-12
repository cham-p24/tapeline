"use client";

/**
 * Legend shown above the scanner table. Makes the language concrete and
 * transparent — users know exactly what each signal + score range means.
 */
export function ScannerLegend() {
  const signals = [
    { label: "HIGH CONVICTION", range: "85–100", tone: "bg-up/20 text-up", desc: "All six factors aligned positive. Clean setup." },
    { label: "STRONG SETUP",    range: "70–84",  tone: "bg-up/10 text-up", desc: "Most factors favorable, one or two mixed." },
    { label: "CONSTRUCTIVE",    range: "55–69",  tone: "bg-accent/10 text-accent", desc: "Net positive but not decisive. Worth watching." },
    { label: "NEUTRAL",         range: "40–54",  tone: "bg-muted/20 text-muted", desc: "Factors cancel out. No edge either way." },
    { label: "CAUTION",         range: "25–39",  tone: "bg-warn/10 text-warn", desc: "More factors negative than positive." },
    { label: "WEAK",            range: "0–24",   tone: "bg-down/10 text-down", desc: "Factors broadly negative. Avoid longs, consider shorts." },
  ];
  return (
    <details className="card mt-4 cursor-pointer group">
      <summary className="flex items-center justify-between p-3 list-none">
        <div>
          <h2 className="text-sm font-semibold">How to read this table</h2>
          <p className="mt-0.5 text-xs text-muted">Click for signal labels, score ranges, and the 6 factors.</p>
        </div>
        <span className="text-accent transition group-open:rotate-45">+</span>
      </summary>
      <div className="p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {signals.map((s) => (
            <div key={s.label} className="flex items-start gap-3">
              <span className={`nums mt-0.5 rounded px-2 py-0.5 text-xs font-medium ${s.tone}`}>{s.label}</span>
              <div className="flex-1">
                <div className="font-mono text-xs text-muted">{s.range}</div>
                <p className="text-xs text-muted">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 pt-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Score = weighted blend of 6 named factors</p>
          <div className="flex flex-wrap gap-3 text-xs">
            <Factor name="Trend" emphasis="Weighted most" desc="Price-trend direction and quality" />
            <Factor name="Rel. Strength" emphasis="High" desc="Performance vs market and sector" />
            <Factor name="Fundamentals" emphasis="Core" desc="Earnings quality and balance-sheet health" />
            <Factor name="Smart Money" emphasis="Core" desc="Insider + institutional + Congress" />
            <Factor name="Macro" emphasis="Core" desc="Regime + rates + sector rotation" />
            <Factor name="Momentum" emphasis="Weighted least" desc="Short-horizon price acceleration" />
          </div>
          <p className="mt-3 text-xs text-muted">
            Hover any score for the per-ticker breakdown and plain-English reason. Click a ticker for the full page.
          </p>
        </div>

        <p className="mt-4 pt-3 text-xs text-muted italic">
          Scores are descriptive of factor data, not prescriptive of trading actions. Tapeline is not investment advice.
        </p>
      </div>
    </details>
  );
}

function Factor({ name, emphasis, desc }: { name: string; emphasis: string; desc: string }) {
  return (
    <div className="rounded-md border border-border bg-panel px-3 py-2">
      <div className="flex items-baseline gap-2">
        <span className="font-semibold">{name}</span>
        <span className="font-mono text-[0.65rem] uppercase tracking-wide text-accent">{emphasis}</span>
      </div>
      <p className="mt-0.5 text-muted">{desc}</p>
    </div>
  );
}
