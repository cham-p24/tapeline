/**
 * Pure, framework-free filter + search helpers shared by every live-monitor
 * page (scanner, squeeze, congress, news, earnings, IPOs, watchlist).
 *
 * Why a separate module: the page components are `"use client"` React and
 * awkward to unit-test in isolation, but the actual filtering logic is pure
 * data-in/data-out. Keeping it here lets us cover the matching rules with a
 * fast vitest unit test (see __tests__/filters.test.ts) and reuse the exact
 * same predicate everywhere, so "search NVDA" behaves identically on every
 * page.
 *
 * Design rule from the founder's brief: prefer the scanner's EXISTING
 * server-side query params for filtering when they exist; only fall back to
 * client-side filtering of already-fetched rows when there is no backend
 * param. These helpers are the client-side fallback — they never call the
 * network.
 */

/**
 * Case-insensitive substring match of `query` against any of the given
 * `fields` on a row. Empty/whitespace-only query matches everything (so an
 * empty search box is a no-op, not a "hide all rows"). Null/undefined field
 * values are skipped safely.
 *
 * Used for the ticker/company/name search box on each page. We match on
 * symbol AND name (and politician on the congress page) so typing either the
 * ticker or the company name finds the row.
 */
export function matchesQuery(
  query: string,
  fields: Array<string | null | undefined>,
): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return fields.some(
    (f) => typeof f === "string" && f.toLowerCase().includes(needle),
  );
}

/**
 * Inclusive numeric range test. Either bound may be null/undefined ("no
 * bound on this side"). A null value (e.g. a row with no score yet) fails a
 * bounded test but passes when both bounds are absent — i.e. range filtering
 * never silently drops un-scored rows unless the user actually set a bound.
 */
export function inRange(
  value: number | null | undefined,
  min: number | null | undefined,
  max: number | null | undefined,
): boolean {
  const hasMin = typeof min === "number" && !Number.isNaN(min);
  const hasMax = typeof max === "number" && !Number.isNaN(max);
  if (!hasMin && !hasMax) return true;
  if (value == null || Number.isNaN(value)) return false;
  if (hasMin && value < min!) return false;
  if (hasMax && value > max!) return false;
  return true;
}

/**
 * Equality test that treats an empty selection ("") as "all". Used by the
 * <SelectFilter> dropdowns (sector, signal, chamber, action, status, …)
 * where the first option is always an "All …" sentinel with value "".
 * Comparison is case-insensitive so a dropdown value of "buy" matches a row
 * value of "BUY".
 */
export function matchesSelect(
  selected: string,
  value: string | null | undefined,
): boolean {
  if (!selected) return true;
  if (value == null) return false;
  return value.toLowerCase() === selected.toLowerCase();
}

/**
 * Map a raw `asset_class` column value to one of three coarse UI buckets.
 * The backend stores fine-grained classes ("equity", "etf", "future", …);
 * the scanner filter only needs Stocks / ETFs / Other, so collapse here.
 * There is no server-side asset_class param, so this drives a client-side
 * filter over the already-fetched scanner rows.
 */
export type AssetBucket = "" | "equity" | "etf" | "other";

export function assetBucket(assetClass: string | null | undefined): AssetBucket {
  const a = (assetClass ?? "").toLowerCase();
  if (a === "etf" || a === "fund") return "etf";
  if (a === "equity" || a === "stock") return "equity";
  if (!a) return "";
  return "other";
}

export function matchesAssetBucket(
  selected: AssetBucket,
  assetClass: string | null | undefined,
): boolean {
  if (!selected) return true;
  return assetBucket(assetClass) === selected;
}
