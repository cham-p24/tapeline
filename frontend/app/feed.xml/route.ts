/**
 * /feed.xml — RSS 2.0 feed of the Tapeline daily Top 10.
 *
 * Why bother with RSS in 2026:
 *
 *   - Financial-aggregator pipelines (Feedly, Inoreader, NewsBlur, Old
 *     Reader, Stocktwits feeds, Substack imports, etc.) still index RSS
 *     daily. Listing the scorecard there gets us inbound traffic from
 *     people who never visit tapeline.io directly.
 *   - Google still treats RSS as a crawl signal and uses it to discover
 *     fresh content. New /daily-picks editions surface in SERPs faster
 *     when there's a feed pointing at them.
 *   - The feed contains exactly the same data the email newsletter does
 *     — no incremental engineering, just a different distribution
 *     channel. Free top-of-funnel.
 *
 * What it includes:
 *
 *   - One item per top-10 pick, dated today.
 *   - Each item links to the per-ticker page (/t/SYMBOL) with
 *     ?utm_source=rss&utm_medium=feed&utm_campaign=scorecard_<YYYYMMDD>
 *     so we can attribute downstream conversions.
 *   - Composite score + signal label + one-sentence read in the
 *     description. No paywalled fields.
 *
 * Caching:
 *   - 30-min ISR via Next's Response cache headers. Aggregators poll
 *     every 15–60 min so longer caching makes sense than for a human
 *     browsing surface.
 */
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

const SITE = process.env.NEXT_PUBLIC_APP_URL || "https://tapeline.io";

type ScannerRow = {
  symbol: string;
  name: string;
  score: number | null;
  signal: string | null;
  reason: string | null;
};

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function rssDate(d: Date): string {
  // RFC 822 — RSS 2.0 standard. Aggregators reject ISO-8601 here.
  return d.toUTCString();
}

export async function GET(): Promise<Response> {
  let picks: ScannerRow[] = [];
  try {
    const res = await fetch(`${API_BASE}/api/scanner?limit=20`, {
      next: { revalidate: 1800 },
    });
    if (res.ok) {
      const body = (await res.json()) as { items?: ScannerRow[] };
      picks = (body.items || []).slice(0, 10);
    }
  } catch {
    // Empty-picks fallback below — feed still validates as RSS.
  }

  const now = new Date();
  const ymd = now.toISOString().slice(0, 10).replace(/-/g, "");
  const campaign = `scorecard_${ymd}`;

  const items = picks
    .map((p) => {
      const link =
        `${SITE}/t/${encodeURIComponent(p.symbol)}` +
        `?utm_source=rss&utm_medium=feed&utm_campaign=${campaign}`;
      const score = p.score == null ? "—" : Math.round(p.score).toString();
      const signal = (p.signal || "").toUpperCase();
      const reason = (p.reason || "").trim();
      const title = `${p.symbol} · ${score} ${signal}`.trim();
      const desc =
        `${p.name || p.symbol} — composite ${score} ` +
        `(${signal || "n/a"}). ${reason || ""}`.trim();
      return `
    <item>
      <title>${esc(title)}</title>
      <link>${esc(link)}</link>
      <guid isPermaLink="false">tapeline-${ymd}-${esc(p.symbol)}</guid>
      <pubDate>${rssDate(now)}</pubDate>
      <description>${esc(desc)}</description>
    </item>`;
    })
    .join("");

  const feed = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Tapeline — Daily Top 10</title>
    <link>${SITE}/daily-picks</link>
    <atom:link href="${SITE}/feed.xml" rel="self" type="application/rss+xml" />
    <description>The 10 highest-scoring US tickers from the Tapeline 6-factor composite, refreshed each US market morning. Public formula. Public scorecard. Not investment advice.</description>
    <language>en-us</language>
    <copyright>© ${now.getUTCFullYear()} Tapeline</copyright>
    <lastBuildDate>${rssDate(now)}</lastBuildDate>
    <ttl>30</ttl>${items}
  </channel>
</rss>
`;

  return new Response(feed, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      // Vary on Accept so we don't surprise an HTML-expecting client.
      Vary: "Accept",
      // CDN cache hint matching the ISR revalidate window.
      "Cache-Control": "public, s-maxage=1800, stale-while-revalidate=3600",
    },
  });
}

export const revalidate = 1800;
