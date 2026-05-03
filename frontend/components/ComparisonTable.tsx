"use client";

/**
 * Three-column comparison: Free / Pro ($29/mo or $24.99/mo annual) /
 * Premium ($49/mo or $39.99/mo annual). Mirrors the gating in
 * backend/app/services/tier.py.
 *
 * Rows are grouped into sections (Data, Scoring, Discovery, Watchlist & Alerts,
 * Pro intelligence, Account & support) so the table reads like a spec sheet,
 * not a wall of bullets.
 */

type Row = { label: string; free: string; pro: string; premium: string };
type Section = { name: string; rows: Row[] };

const SECTIONS: Section[] = [
  {
    name: "Data & coverage",
    rows: [
      { label: "Ticker universe", free: "Top 20", pro: "~870 US equities, ETFs & commodity ETFs", premium: "~870 US equities, ETFs & commodity ETFs" },
      { label: "Data freshness", free: "24-hour delayed", pro: "Live, sub-60s refresh", premium: "Live, sub-60s refresh" },
      { label: "News feed", free: "Headlines only", pro: "Real-time Massive + sentiment", premium: "Real-time Massive + sentiment" },
    ],
  },
  {
    name: "Scoring & analysis",
    rows: [
      { label: "6-factor score breakdown", free: "Top 20 only", pro: "Every ticker, every row", premium: "Every ticker, every row" },
      { label: "Plain-English Why column", free: "—", pro: "✓", premium: "✓" },
      { label: "TradingView charts", free: "—", pro: "On every ticker page", premium: "On every ticker page" },
    ],
  },
  {
    name: "Discovery tools",
    rows: [
      { label: "Squeeze Watch", free: "—", pro: "✓", premium: "✓" },
      { label: "Market Heatmap", free: "—", pro: "✓", premium: "✓" },
      { label: "IPO + Earnings calendars", free: "—", pro: "✓", premium: "✓" },
      { label: "Saved scans", free: "—", pro: "10", premium: "100" },
    ],
  },
  {
    name: "Watchlist & alerts",
    rows: [
      { label: "Watchlist", free: "5 tickers · no alerts", pro: "50 tickers · smart alerts", premium: "200 tickers · smart alerts" },
      { label: "Email alerts per day", free: "—", pro: "10", premium: "Unlimited" },
      { label: "Daily briefing email", free: "—", pro: "✓", premium: "✓" },
      { label: "Browser push + Discord", free: "—", pro: "✓", premium: "✓" },
      { label: "Telegram alerts", free: "—", pro: "—", premium: "Unlimited · hourly digest" },
      { label: "SMS alerts", free: "—", pro: "—", premium: "✓" },
    ],
  },
  {
    name: "Pro intelligence",
    rows: [
      { label: "Congressional trades feed", free: "—", pro: "—", premium: "✓" },
      { label: "Elite 13F holdings", free: "—", pro: "—", premium: "✓" },
      { label: "Public API access", free: "—", pro: "—", premium: "1,000 req/day" },
      { label: "CSV export", free: "—", pro: "✓", premium: "✓" },
    ],
  },
  {
    name: "Account & support",
    rows: [
      { label: "Public scorecard access", free: "✓", pro: "✓", premium: "✓" },
      { label: "Support", free: "Community", pro: "Email · 48h", premium: "Priority" },
    ],
  },
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
              <span className="text-fg block">Pro</span>
              <span className="text-[10px] normal-case text-muted block mt-0.5">$29/mo · $24.99/mo annual</span>
            </th>
            <th className="px-4 py-3 text-center text-xs uppercase w-48">
              <span className="text-accent block">Premium</span>
              <span className="text-[10px] normal-case text-muted block mt-0.5">$49/mo · $39.99/mo annual</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {SECTIONS.map((sec) => (
            <SectionGroup key={sec.name} section={sec} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SectionGroup({ section }: { section: Section }) {
  return (
    <>
      <tr className="bg-panel/50 border-y border-border/60">
        <td colSpan={4} className="px-4 py-2.5 text-[11px] uppercase tracking-wider text-accent font-semibold">
          {section.name}
        </td>
      </tr>
      {section.rows.map((r) => (
        <tr key={r.label} className="border-b border-border/30">
          <td className="px-4 py-3 text-fg">{r.label}</td>
          <td className="px-4 py-3 text-center nums text-xs text-muted">{r.free}</td>
          <td className="px-4 py-3 text-center nums text-xs">{r.pro}</td>
          <td className="px-4 py-3 text-center nums text-xs font-medium text-accent">{r.premium}</td>
        </tr>
      ))}
    </>
  );
}
