/**
 * Tickers Tapeline has retired because they stopped trading.
 *
 * The backend stamps `delisted_at` on a row when a complete walk of the data
 * vendor's active US listings no longer lists the symbol, and /api/ticker then
 * answers 404 with a detail that starts with RETIRED_PREFIX and says why
 * (backend/app/services/delisting.py, `retired_message`). The /t/{symbol} page
 * shows that sentence as is, on a small noindex page, instead of Next's 404:
 * the symbol can still be linked from the public record (TOI was on it 1-5
 * June 2026), so the link must land somewhere that says what happened.
 *
 * Before 2026-09-19 nothing retired a ticker, and a symbol that had stopped
 * trading kept a frozen price and a moving rank: GREE, renamed VIP on 24 Jul
 * 2026, read 75.8 STRONG SETUP on 19 Sep.
 */

/** Pinned to backend/app/services/delisting.py RETIRED_PREFIX. */
export const RETIRED_PREFIX = "No longer trading:";

/** The retirement sentence from a 404 body, or null for any other 404. */
export function retiredDetail(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  return typeof detail === "string" && detail.startsWith(RETIRED_PREFIX) ? detail : null;
}
