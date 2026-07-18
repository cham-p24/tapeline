/**
 * Free-tier preview fetches for the three "intelligence" surfaces
 * (/app/heatmap, /app/congress, /app/holdings).
 *
 * Why this module exists: those pages used to call their Pro/Premium-gated
 * endpoint unconditionally. For a Free user the request 403'd BEFORE anything
 * rendered, so the upgrade card blurred a literally empty page — the heatmap
 * showed "Showing 0 tickers across 0 sectors" behind the paywall. A free user
 * saw zero evidence the paid feature had any content.
 *
 * Each helper below returns a small slice of REAL data plus a REAL total, so
 * the pages can render populated rows/tiles and state the true held-back
 * count. Nothing here fabricates or pads data: if the backend has no rows, the
 * preview is empty and the UI says so.
 *
 * Kept separate from lib/api.ts on purpose — these are the unauthenticated /
 * any-tier preview reads, and the heatmap one targets the pre-existing public
 * endpoint rather than the gated router.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.clone().json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* not JSON — keep the status line */
    }
    throw new Error(detail);
  }
  return res.json();
}

/**
 * One canonical sector's aggregate 1D move. `change_pct_1d` is the
 * dollar-volume-weighted average across `ticker_count` live tickers — both
 * computed server-side in GET /api/public/heatmap.
 */
export type PublicHeatmapSector = {
  sector: string;
  change_pct_1d: number;
  ticker_count: number;
};

/** Sector-level heatmap aggregate — the Free/anon teaser for /app/heatmap. */
export const heatmapPreview = () =>
  getJson<{ count: number; sectors: PublicHeatmapSector[] }>("/api/public/heatmap");

/** Mirrors backend routers/congress.FREE_CONGRESS_PREVIEW_LIMIT. */
export const FREE_CONGRESS_PREVIEW_LIMIT = 3;

/** Mirrors backend routers/holdings.FREE_INSIDER_PREVIEW_LIMIT. */
export const FREE_INSIDER_PREVIEW_LIMIT = 3;

/**
 * 3 most recently disclosed REAL congressional trades + the real total row
 * count of the full feed. Any logged-in tier; anonymous callers get 401.
 */
export const congressPreview = <T>() =>
  getJson<{
    count: number;
    preview: true;
    limit: number;
    total_disclosures: number;
    items: T[];
  }>("/api/congress/preview");

/**
 * 3 most recent REAL Form 4 filings + `feed_size`, the real total row count of
 * the DB-backed insider feed. Any logged-in tier; anonymous callers get 401.
 */
export const holdingsPreview = <T>() =>
  getJson<{
    count: number;
    preview: true;
    limit: number;
    days: number;
    feed_size: number;
    items: T[];
  }>("/api/holdings/preview");
