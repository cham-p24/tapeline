"use client";

/**
 * Three-column comparison: Free / Pro ($29.99/mo or $24.99/mo annual) /
 * Premium ($49.99/mo or $39.99/mo annual). Mirrors the gating in
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
      { label: "Ticker universe", free: "Top 20", pro: "~2,500 US equities, ETFs & commodity ETFs", premium: "~2,500 US equities, ETFs & commodity ETFs" },
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
      { label: "Browser push", free: "—", pro: "✓", premium: "✓" },
      { label: "Telegram alerts", free: "—", pro: "—", premium: "Unlimited · hourly digest" },
    ],
  },
  {
    name: "Pro intelligence",
    rows: [
      { label: "Congressional trades feed", free: "—", pro: "—", premium: "✓" },
      { label: "Recent insider buys (SEC Form 4)", free: "—", pro: "—", premium: "✓" },
      // Public API row removed — programmatic /api/v1/* with API-key auth
      // isn't built yet. Re-add when the endpoint ships rather than leaving
      // a 1,000 req/day claim that has no backing implementation.
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
    // Constrain to max-w-5xl + center so the table doesn't stretch the
    // full viewport on wide monitors (was creating an ugly empty band
    // between the FEATURE column and the plan columns). Keep
    // overflow-x-auto so the table scrolls horizontally on phones.
    <div className="card mt-8 mx-auto max-w-5xl overflow-x-auto">
      <div className="px-4 pt-3 text-right text-[10px] uppercase tracking-wider text-subtle">All prices in USD</div>
      <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
        {/* Explicit column widths so the FEATURE column doesn't greedily
            absorb all the leftover space on wide screens. ~40% feature,
            ~20% per plan column. */}
        <colgroup>
          <col style={{ width: "40%" }} />
          <col style={{ width: "20%" }} />
          <col style={{ width: "20%" }} />
          <col style={{ width: "20%" }} />
        </colgroup>
        <thead className="border-b border-border bg-black/40">
          <tr>
            <th className="px-4 py-3 text-left text-xs uppercase text-muted align-bottom">Feature</th>
            <th className="px-4 py-3 text-center text-xs uppercase text-muted align-bottom">Free</th>
            <th className="px-4 py-3 text-center align-bottom">
              <span className="text-fg block text-xs uppercase">Pro</span>
              <span className="text-[11px] text-muted block mt-1.5 nums">$29.99/mo</span>
              <span className="text-[10px] text-subtle block nums">or $24.99/mo annual</span>
            </th>
            <th className="px-4 py-3 text-center align-bottom">
              <span className="text-accent block text-xs uppercase">Premium</span>
              <span className="text-[11px] text-muted block mt-1.5 nums">$49.99/mo</span>
              <span className="text-[10px] text-subtle block nums">or $39.99/mo annual</span>
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
