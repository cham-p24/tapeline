import { daysUntilEarnings } from "@/lib/useEarningsCalendar";

/**
 * Row-level earnings pill.
 *
 * Renders a small descriptive badge when a ticker has an upcoming earnings
 * report, e.g. "Earnings today", "Reports tomorrow", "Reports in 3d". Used
 * on the scanner rows and the ticker page header so a reader knows a
 * catalyst is imminent before reading the score.
 *
 * Descriptive only — states *when* the company reports, never what to do
 * about it. Renders nothing when there's no upcoming report, a past date,
 * or a date further out than `withinDays` (default 7 = "this week-ish"),
 * so it stays quiet for the vast majority of rows.
 */
export function EarningsPill({
  reportDate,
  withinDays = 7,
  className = "",
}: {
  reportDate: string | null | undefined;
  withinDays?: number;
  className?: string;
}) {
  const d = daysUntilEarnings(reportDate);
  if (d == null || d < 0 || d > withinDays) return null;

  const label =
    d === 0 ? "Earnings today"
    : d === 1 ? "Reports tomorrow"
    : `Reports in ${d}d`;

  // Imminent reports (today / tomorrow) get the warmer accent so they catch
  // the eye; the rest stay muted-amber as supplementary context.
  const tone = d <= 1 ? "bg-warn/20 text-warn" : "bg-warn/10 text-warn";

  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-medium ${tone} ${className}`}
      title={`Scheduled earnings report${reportDate ? ` on ${reportDate}` : ""}`}
    >
      <svg className="h-2.5 w-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
        <rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" />
      </svg>
      {label}
    </span>
  );
}
