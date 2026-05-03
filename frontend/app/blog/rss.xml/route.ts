/**
 * Blog RSS feed at /blog/rss.xml.
 *
 * Why: RSS isn't dead — power users read in Feedly/NetNewsWire, indexers
 * (Google News, Brave) prefer feeds for content discovery, and Substack-
 * style aggregators auto-import from RSS. Free SEO + reach for ~30 lines.
 *
 * Spec: RSS 2.0 (https://www.rssboard.org/rss-specification). Item bodies
 * are content:encoded HTML for readers that render rich content.
 *
 * Cache: revalidate hourly so a new post shows up within an hour without
 * paying CDN regeneration on every crawler hit.
 */
import { POSTS } from "../posts";

export const revalidate = 3600;

const SITE = "https://tapeline.io";

function escape(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export async function GET() {
  const sorted = [...POSTS].sort(
    (a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
  );

  const items = sorted
    .map((p) => {
      const link = `${SITE}/blog/${p.slug}`;
      const pubDate = new Date(p.publishedAt).toUTCString();
      return `
    <item>
      <title>${escape(p.title)}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      <pubDate>${pubDate}</pubDate>
      <author>noreply@tapeline.io (${escape(p.author)})</author>
      <description>${escape(p.excerpt)}</description>
      <content:encoded><![CDATA[${p.body}]]></content:encoded>
    </item>`;
    })
    .join("");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Tapeline — Notes from building</title>
    <link>${SITE}/blog</link>
    <atom:link href="${SITE}/blog/rss.xml" rel="self" type="application/rss+xml" />
    <description>Methodology, market commentary, and occasional rants about scanner pricing, from the team building tapeline.io.</description>
    <language>en-us</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <generator>tapeline.io</generator>${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600, s-maxage=3600",
    },
  });
}
