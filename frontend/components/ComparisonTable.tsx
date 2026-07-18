"use client";

import { PRICING, FREE_LIMITS, usd, annualSaving } from "@/lib/pricing";

/**
 * Three-column comparison: Free / Pro ($9.99/mo or $8.25/mo annual) /
 * Premium ($19.99/mo or $16.58/mo annual). Prices render from lib/pricing.ts
 * (single source of truth). Mirrors the gating in
 * backend/app/services/tier.py.
 *
 * Rows are grouped into sections (Data, Scoring, Discovery, Watchlist & Alerts,
 * Pro intelligence, Account & support) so the table reads like a spec sheet,
 * not a wall of bullets.
 *
 * **2026-05-20 redesign** — founder feedback: prior version "looks a bit
 * ugly". Changes:
 *  - Plan column headers turned into stacked badges (name + price block,
 *    cleaner hierarchy than 3 cramped lines of text)
 *  - "—" replaced with a styled muted dot so missing features read as
 *    "deliberately not included" instead of "we forgot a value"
 *  - "✓" checks use the up-green accent so present features pop without
 *    over-colouring every Premium cell in blue
 *  - Premium column gets a subtle column-wide tint (bg-accent/[0.04])
 *    instead of per-cell text-accent — same emphasis, less noisy
 *  - Section headers use bg-panel2 + larger padding for stronger
 *    visual separation
 *  - "Best value" pill on Pro since that's the conversion target (factual
 *    framing — never a popularity claim we can't back with customer counts)
 */

type Row = { label: string; free: string; pro: string; premium: string };
type Section = { name: string; rows: Row[] };

const SECTIONS: Section[] = [
  {
    name: "Data & coverage",
    rows: [
      { label: "Scanner rows", free: `Top ${FREE_LIMITS.scannerRows}`, pro: "Full ~2,500-ticker universe", premium: "Full ~2,500-ticker universe" },
      { label: "Data freshness", free: "Live — no delay", pro: "Live, sub-60s refresh", premium: "Live, sub-60s refresh" },
      { label: "Ticker look-ups per day", free: `${FREE_LIMITS.dailyLookups} · unmetered first ${FREE_LIMITS.firstSessionGraceHours}h`, pro: "Unlimited", premium: "Unlimited" },
      { label: "News feed", free: "Headlines only", pro: "Real-time news + sentiment", premium: "Real-time news + sentiment" },
    ],
  },
  {
    name: "Scoring & analysis",
    rows: [
      { label: "6-factor score breakdown", free: `${FREE_LIMITS.dailyLookups} look-ups/day`, pro: "Every ticker, every row", premium: "Every ticker, every row" },
      { label: "Plain-English Why column", free: "On look-ups", pro: "✓", premium: "✓" },
      { label: "TradingView charts", free: "—", pro: "On every ticker page", premium: "On every ticker page" },
    ],
  },
  {
    name: "Discovery tools",
    rows: [
      { label: "Squeeze Watch", free: `Top-${FREE_LIMITS.squeezePreviewRows} preview`, pro: "✓", premium: "✓" },
      { label: "Market Heatmap", free: "—", pro: "✓", premium: "✓" },
      { label: "IPO + Earnings calendars", free: "—", pro: "✓", premium: "✓" },
      { label: "Saved scans", free: "—", pro: "10", premium: "100" },
    ],
  },
  {
    name: "Watchlist & alerts",
    rows: [
      { label: "Watchlist", free: `${FREE_LIMITS.watchlistTickers} tickers`, pro: "50 tickers · smart alerts", premium: "200 tickers · smart alerts" },
      { label: "Email alerts per day", free: "—", pro: "10", premium: "Unlimited" },
      { label: "Daily briefing email", free: "—", pro: "✓", premium: "✓" },
      { label: "Browser push", free: `${FREE_LIMITS.webPushAlerts} alert rules`, pro: "✓", premium: "✓" },
      { label: "Telegram alerts", free: "—", pro: "—", premium: "Unlimited · hourly digest" },
    ],
  },
  {
    name: "Pro intelligence",
    rows: [
      { label: "Congressional trades feed", free: "—", pro: "—", premium: "✓" },
      { label: "Recent insider buys (SEC Form 4)", free: "—", pro: "—", premium: "✓" },
      // Public API shipped 2026-06-01 (PR8): key-authenticated /api/v1/* with a
      // 1,000 req/day Premium quota. Backed by services/api_keys + routers/api_v1.
      { label: "Public API access", free: "—", pro: "—", premium: "1,000 requests/day" },
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
    // full viewport on wide monitors. Outer surface uses `bg-panel` so
    // the atmospheric layer underneath shows through — `bg-surface` was
    // rendering as a stark white island against the blue tint.
    <div className="mx-auto mt-8 max-w-5xl overflow-hidden rounded-2xl border border-border bg-panel shadow-[0_1px_3px_rgb(var(--shadow))]">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
          {/* Explicit column widths so the FEATURE column doesn't greedily
              absorb all the leftover space on wide screens. ~36% feature,
              ~21% per plan column (slightly wider Premium for the
              "Unlimited · hourly digest" string). */}
          <colgroup>
            <col style={{ width: "36%" }} />
            <col style={{ width: "21%" }} />
            <col style={{ width: "21%" }} />
            <col style={{ width: "22%" }} />
          </colgroup>
          <thead>
            <tr className="border-b border-border2 bg-panel">
              <th className="px-5 py-5 text-left align-bottom">
                <span className="block text-[10px] uppercase tracking-[0.12em] text-subtle">Feature</span>
              </th>
              <th className="px-3 py-5 text-center align-bottom">
                <span className="block text-xs font-semibold uppercase tracking-wider text-muted">Free</span>
                <span className="mt-2 block text-lg font-bold text-fg nums">$0</span>
                <span className="block text-[10px] text-subtle">/forever</span>
              </th>
              <th className="relative px-3 py-5 text-center align-bottom">
                <span className="absolute left-1/2 top-2 -translate-x-1/2 whitespace-nowrap rounded-full bg-fg px-2 py-[2px] text-[9px] font-bold uppercase tracking-[0.08em] text-background">
                  Best value
                </span>
                <span className="mt-2 block text-xs font-semibold uppercase tracking-wider text-fg">Pro</span>
                <span className="mt-2 block text-lg font-bold text-fg nums">{usd(PRICING.pro.annualPerMonth)}</span>
                <span className="block text-[10px] text-subtle">{`/mo · annual · save $${annualSaving(PRICING.pro)}`}</span>
              </th>
              <th className="bg-accent/[0.04] px-3 py-5 text-center align-bottom">
                <span className="block text-xs font-semibold uppercase tracking-wider text-accent">Premium</span>
                <span className="mt-2 block text-lg font-bold text-fg nums">{usd(PRICING.premium.annualPerMonth)}</span>
                <span className="block text-[10px] text-subtle">{`/mo · annual · save $${annualSaving(PRICING.premium)}`}</span>
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
      <div className="border-t border-border/60 px-5 py-3 text-right text-[10px] uppercase tracking-wider text-subtle">
        {`All prices in USD · Monthly billing $${(PRICING.pro.monthly - PRICING.pro.annualPerMonth).toFixed(2)} / $${(PRICING.premium.monthly - PRICING.premium.annualPerMonth).toFixed(2)} higher`}
      </div>
    </div>
  );
}

function SectionGroup({ section }: { section: Section }) {
  return (
    <>
      <tr>
        <td
          colSpan={4}
          className="border-y border-border/60 bg-panel2 px-5 py-3 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-accent"
        >
          {section.name}
        </td>
      </tr>
      {section.rows.map((r) => (
        <tr key={r.label} className="border-b border-border/40">
          <td className="px-5 py-3.5 text-fg">{r.label}</td>
          <Cell value={r.free} tone="muted" />
          <Cell value={r.pro} tone="default" />
          <Cell value={r.premium} tone="premium" />
        </tr>
      ))}
    </>
  );
}

/**
 * One body cell — renders three visual treatments depending on value:
 *  - "—" (missing)       → small muted dot, signals "deliberately not in this tier"
 *  - "✓" (present)       → up-green check, reads as positive without over-colouring
 *  - anything else (str) → plain text, tone-coloured
 *
 * `tone="premium"` applies the Premium column tint band — kept as a column
 * background, NOT per-cell text colour, so the Premium column reads as a
 * highlighted unit instead of every value shouting in accent blue.
 */
function Cell({ value, tone }: { value: string; tone: "muted" | "default" | "premium" }) {
  const bg = tone === "premium" ? "bg-accent/[0.04]" : "";
  const text =
    tone === "muted" ? "text-muted"
    : tone === "premium" ? "text-fg font-medium"
    : "text-fg";

  if (value === "—") {
    return (
      <td className={`px-3 py-3.5 text-center ${bg}`}>
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-border2" aria-label="not included" />
      </td>
    );
  }
  if (value === "✓") {
    return (
      <td className={`px-3 py-3.5 text-center ${bg}`}>
        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-up/15 text-[11px] font-bold text-up">✓</span>
      </td>
    );
  }
  return (
    <td className={`px-3 py-3.5 text-center text-xs nums ${text} ${bg}`}>{value}</td>
  );
}
