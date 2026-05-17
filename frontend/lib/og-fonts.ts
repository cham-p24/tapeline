/**
 * Shared Inter font loader for `next/og` ImageResponse routes.
 *
 * `next/og` runs on Vercel's edge runtime which does NOT bundle any font.
 * The `font-family: "Inter, ..."` CSS declaration silently falls back to a
 * generic embedded sans-serif - close to Inter at a glance, but visibly
 * off-brand when placed next to the real thing.
 *
 * The fix is to pass actual Inter font binaries to `ImageResponse`'s
 * `fonts` option. Satori (the rendering engine inside next/og) supports
 * TTF, OTF, and WOFF (NOT WOFF2). jsdelivr's @fontsource/inter mirror
 * serves WOFF files with permissive CORS + long cache headers, so each
 * cold start fetches ~30 KB per weight - cheap, and the CDN holds it
 * after the first hit.
 *
 * Usage:
 *   const fonts = await loadInter([500, 700]);
 *   return new ImageResponse(<div>...</div>, { width, height, fonts });
 */

const FONTSOURCE_BASE =
  "https://cdn.jsdelivr.net/npm/@fontsource/inter@5.0.16/files";

type InterWeight = 400 | 500 | 600 | 700;

const URLS: Record<InterWeight, string> = {
  400: `${FONTSOURCE_BASE}/inter-latin-400-normal.woff`,
  500: `${FONTSOURCE_BASE}/inter-latin-500-normal.woff`,
  600: `${FONTSOURCE_BASE}/inter-latin-600-normal.woff`,
  700: `${FONTSOURCE_BASE}/inter-latin-700-normal.woff`,
};

export type OgFont = {
  name: string;
  data: ArrayBuffer;
  weight: InterWeight;
  style: "normal";
};

/**
 * Fetch Inter in the requested weights, ready to pass into
 * `ImageResponse({ ..., fonts })`. Returns nothing on fetch failure -
 * the route then degrades to the embedded fallback font rather than
 * 500-ing the social card.
 */
export async function loadInter(weights: InterWeight[]): Promise<OgFont[]> {
  try {
    return await Promise.all(
      weights.map(async (w) => ({
        name: "Inter",
        data: await fetch(URLS[w]).then((r) => {
          if (!r.ok) throw new Error(`inter ${w} fetch ${r.status}`);
          return r.arrayBuffer();
        }),
        weight: w,
        style: "normal" as const,
      })),
    );
  } catch {
    // Silent degrade - better a slightly-off font than a 500.
    return [];
  }
}
