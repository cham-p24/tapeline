/**
 * Locale-and-timezone-aware date formatters.
 *
 * Why this exists: previously dates were rendered with `toLocaleString()`
 * with no options, which uses whatever locale the browser is set to.
 * For a Chrome installed in Australia but with default English-US locale
 * settings (which is the default for most Australian Chrome users) that
 * produces "1/8/2026" — ambiguous to anyone outside the US (is it Jan 8
 * or Aug 1?).
 *
 * Both helpers below produce *unambiguous* output regardless of browser
 * locale, while still respecting the user's local timezone (via
 * Intl.DateTimeFormat's default `timeZone: undefined` behaviour).
 */

/** "8 May 2026, 14:30" — always day-month-year, 24h time, in user's tz. */
export function formatAbsolute(input: string | Date): string {
  const d = typeof input === "string" ? new Date(input) : input;
  if (isNaN(d.getTime())) return "—";
  // en-GB gives DD MMM YYYY which everyone reads correctly.
  // The user's actual timezone is picked up automatically since we don't
  // pass timeZone — Intl resolves it to the runtime timezone.
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/**
 * "3h ago" / "2d ago" / "8 May 2026" — relative for recent, absolute for older.
 * Threshold: 7 days. Beyond that, the absolute date is more useful than
 * "127d ago".
 */
export function formatRelativeOrAbsolute(input: string | Date): string {
  const d = typeof input === "string" ? new Date(input) : input;
  if (isNaN(d.getTime())) return "—";
  const diffMs = Date.now() - d.getTime();
  const diffMin = Math.round(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  // Older than a week — show absolute date. en-GB for unambiguous DMY.
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Detect the browser's resolved timezone for display purposes ("Australia/Sydney"). */
export function userTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return "UTC";
  }
}
