"use client";

/**
 * Three-column comparison: Free / Pro $29 / Premium $49.
 * Mirrors the gating in backend/app/services/tier.py.
 */

const ROWS = [
  { label: "Ticker universe", free: "Top 20", pro: "~870 US equities, ETFs & commodity ETFs", premium: "~870 US equities, ETFs & commodity ETFs" },
  { label: "Data freshness", free: "24-hour delayed", pro: "Live, sub-60s refresh", premium: "Live, sub-60s refresh" },
  { label: "6-factor score breakdown", free: "Top 20 only", pro: "Every ticker, every row", premium: "Every ticker, every row" },
  { label: "Plain-English Why column", free: "—", pro: "✓", premium: "✓" },
  { label: "Squeeze Watch", free: "—", pro: "✓", premium: "✓" },
  { label: "Market Heatmap", free: "—", pro: "✓", premium: "✓" },
  { label: "IPO + Earnings + News calendars", free: "—", pro: "✓", premium: "✓" },
  { label: "Watchlist", free: "5 tickers · no alerts", pro: "50 tickers · smart alerts", premium: "200 tickers · smart alerts" },
  { label: "TradingView charts", free: "—", pro: "On every ticker page", premium: "On every ticker page" },
  { label: "Email alerts per day", free: "—", pro: "10", premium: "Unlimited" },
  { label: "Daily briefing email", free: "—", pro: "✓", premium: "✓" },
  { label: "CSV export", free: "—", pro: "✓", premium: "✓" },
  { label: "Congressional trades feed", free: "—", pro: "—", premium: "✓" },
  { label: "Telegram alerts", free: "—", pro: "—", premium: "Unlimited · hourly digest" },
  { label: "Public API access", free: "—", pro: "—", premium: "1,000 req/day" },
  { label: "Saved scans", free: "—", pro: "10", premium: "100" },
  { label: "Public scorecard access", free: "✓", pro: "✓", premium: "✓" },
  { label: "Support", free: "Community", pro: "Email · 48h", premium: "Priority" },
];

export function ComparisonTable() {
  return (
    <div className="card mt-8 overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-black/40">
          <tr>
            <th className="px-4 py-3 text-left text-xs uppercase text-muted">Feature</th>
            <th className="px-4 py-3 text-center text-xs uppercase text-muted w-40">Free</th>
            <th className="px-4 py-3 text-center text-xs uppercase w-48">
              <span className="text-fg">Pro — $29/mo</span>
            </th>
            <th className="px-4 py-3 text-center text-xs uppercase w-48">
              <span className="text-accent">Premium — $49/mo</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => (
            <tr key={r.label} className="border-b border-border/30">
              <td className="px-4 py-3 text-muted">{r.label}</td>
              <td className="px-4 py-3 text-center nums text-xs">{r.free}</td>
              <td className="px-4 py-3 text-center nums text-xs">{r.pro}</td>
              <td className="px-4 py-3 text-center nums text-xs font-medium text-accent">{r.premium}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
