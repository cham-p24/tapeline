/**
 * Stylised mini-scanner preview for the landing hero.
 * Not wired to real data — it's purely visual so first-time visitors see the product.
 */
export function ScannerPreview() {
  const rows = [
    { sym: "NVDA", sector: "Tech",       score: 92.4, sig: "HIGH CONVICTION", d1:  2.14, why: "Strong uptrend, outperforming sector, accelerating momentum" },
    { sym: "MSFT", sector: "Tech",       score: 88.7, sig: "HIGH CONVICTION", d1:  1.02, why: "Strong uptrend, solid fundamentals, insider buying" },
    { sym: "LLY",  sector: "Healthcare", score: 81.3, sig: "STRONG SETUP",    d1:  0.74, why: "Outperforming sector, accelerating momentum" },
    { sym: "CAT",  sector: "Industrials",score: 76.1, sig: "STRONG SETUP",    d1:  0.45, why: "Solid fundamentals, favourable macro backdrop" },
    { sym: "XOM",  sector: "Energy",     score: 68.9, sig: "CONSTRUCTIVE",    d1: -0.32, why: "Insider buying, favourable macro" },
    { sym: "AAPL", sector: "Tech",       score: 58.4, sig: "NEUTRAL",         d1: -0.15, why: "Mixed signals across factors" },
  ];
  return (
    <div className="card overflow-hidden shadow-2xl">
      <div className="flex items-center justify-between border-b border-border bg-black/40 px-4 py-2 text-xs">
        <div className="flex items-center gap-2 text-muted">
          <span className="h-2 w-2 animate-pulse rounded-full bg-up" />
          Live · updated just now
        </div>
        <div className="text-muted">Showing 6 of 1,000 tickers</div>
      </div>
      <table className="w-full text-sm nums">
        <thead className="border-b border-border/50 text-xs uppercase text-muted">
          <tr>
            <th className="px-3 py-2 text-left">Ticker</th>
            <th className="px-3 py-2 text-right">Score</th>
            <th className="px-3 py-2 text-left">Signal</th>
            <th className="px-3 py-2 text-right">1D</th>
            <th className="hidden px-3 py-2 text-left sm:table-cell">Why</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.sym} className="border-b border-border/30">
              <td className="px-3 py-2 font-mono font-medium">{r.sym}</td>
              <td className={`px-3 py-2 text-right font-semibold ${r.score >= 80 ? "text-up" : r.score >= 60 ? "text-up/80" : "text-fg"}`}>{r.score.toFixed(1)}</td>
              <td className="px-3 py-2">
                <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${
                  r.sig === "HIGH CONVICTION" ? "bg-up/20 text-up"
                  : r.sig === "STRONG SETUP" ? "bg-up/10 text-up"
                  : r.sig === "CONSTRUCTIVE" ? "bg-accent/10 text-accent"
                  : "bg-muted/20 text-muted"
                }`}>{r.sig}</span>
              </td>
              <td className={`px-3 py-2 text-right ${r.d1 > 0 ? "text-up" : "text-down"}`}>{r.d1 >= 0 ? "+" : ""}{r.d1.toFixed(2)}%</td>
              <td className="hidden px-3 py-2 text-xs text-muted sm:table-cell max-w-[300px] truncate">{r.why}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
