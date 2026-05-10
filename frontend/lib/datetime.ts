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
 * Locale resolution priority:
 *   1. Explicit `locale` argument (used by server components that resolve
 *      the cookie via next/headers).
 *   2. `tapeline_locale` cookie set by middleware.ts from Vercel's edge
 *      geo data — gives us the visitor's country-appropriate BCP 47 tag
 *      regardless of what their browser reports.
 *   3. en-GB final fallback (DD MMM YYYY — unambiguous for everyone).
 *
 * The user's actual timezone is always picked up automatically since we
 * never pass `timeZone` — Intl resolves it to the runtime timezone.
 */

const FALLBACK_LOCALE = "en-GB";

/** Pull `tapeline_locale` from the document cookie jar on the client. */
function readCookieLocale(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)tapeline_locale=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function resolveLocale(explicit?: string): string {
  if (explicit) return explicit;
  return readCookieLocale() || FALLBACK_LOCALE;
}

/** "8 May 2026, 14:30" — locale-aware day-month-year + 24h time, in user's tz. */
export function formatAbsolute(input: string | Date, locale?: string): string {
  const d = typeof input === "string" ? new Date(input) : input;
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString(resolveLocale(locale), {
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
export function formatRelativeOrAbsolute(input: string | Date, locale?: string): string {
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
  // Older than a week — show absolute date in the visitor's locale.
  return d.toLocaleDateString(resolveLocale(locale), {
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

/** Read the resolved locale (cookie or fallback) — handy for client components
 *  that want to render a single locale-aware date themselves. */
export function userLocale(): string {
  return resolveLocale();
}
