/**
 * Every scored ticker from /api/public/signals, paged.
 *
 * The endpoint hard-caps each response at 2,000 rows and orders score-desc, so
 * one call returns only the top slice of a universe of about 11,500. A page
 * that states "every scored ticker" (a count, an average) has to page through.
 * Same scheme as app/stocks/page.tsx and app/sitemap.ts: windows advance by
 * LESS than a page so consecutive windows overlap and a ticker whose rank
 * drifts across a boundary between two separately-cached fetches is not lost;
 * the overlap's duplicates are dropped by symbol.
 */
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

export const UNIVERSE_PAGE_SIZE = 2000; // = backend hard cap per response
export const UNIVERSE_STRIDE = 1500;
export const UNIVERSE_MAX_PAGES = 12; // 12 x 1,500 + 2,000 = 18.5k, well above today's pool

export async function fetchPublicUniverse<T extends { symbol: string }>(
  init: RequestInit & { next?: { revalidate: number } },
): Promise<T[]> {
  const all: T[] = [];
  const seen = new Set<string>();
  try {
    for (let page = 0; page < UNIVERSE_MAX_PAGES; page++) {
      const offset = page * UNIVERSE_STRIDE;
      const res = await fetch(
        `${API_BASE}/api/public/signals?limit=${UNIVERSE_PAGE_SIZE}&offset=${offset}`,
        init,
      );
      if (!res.ok) break;
      const body = (await res.json()) as { items?: T[] };
      const items = body.items ?? [];
      for (const r of items) {
        if (r.symbol && !seen.has(r.symbol)) {
          seen.add(r.symbol);
          all.push(r);
        }
      }
      if (items.length < UNIVERSE_PAGE_SIZE) break;
    }
  } catch {
    // Use whatever was collected; callers render an empty state for none.
  }
  return all;
}
