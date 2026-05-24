#!/usr/bin/env node
/**
 * Notify search engines that pages have updated.
 *
 * Three protocols, one script:
 *   1. IndexNow (Bing, Yandex, Naver, Seznam, Yep — covered by a single ping)
 *   2. Google sitemap ping (deprecated but still works for some legacy crawlers)
 *   3. Bing sitemap ping
 *
 * Why: Google and Bing both crawl naturally, but they can take days to
 * notice a new URL or a change. Pinging the sitemap on every deploy
 * cuts that latency to hours. IndexNow is real-time — Bing typically
 * indexes within minutes of the ping.
 *
 * Usage (one-shot full sitemap re-announce):
 *   node frontend/scripts/notify-search-engines.mjs
 *
 * Usage (specific URLs — for new blog posts or material content changes):
 *   node frontend/scripts/notify-search-engines.mjs \
 *     https://tapeline.io/blog/new-post \
 *     https://tapeline.io/best-stock-scanners
 *
 * Env vars:
 *   SITE_URL         — defaults to https://tapeline.io
 *   INDEXNOW_KEY     — required for the IndexNow ping. Generate any 8-128
 *                      hex character string and host it at
 *                      $SITE_URL/$INDEXNOW_KEY.txt with the key as content.
 *                      See docs/AUTOMATION.md for setup.
 */

const SITE_URL = (process.env.SITE_URL || "https://tapeline.io").replace(/\/$/, "");
// Static IndexNow key — file lives at frontend/public/<key>.txt and is
// served by Vercel. Override via INDEXNOW_KEY env var only if rotating.
// Keeping a literal default means this script works out of the box in
// CI / on a fresh clone without any GitHub-secret configuration.
const STATIC_INDEXNOW_KEY = "7b3f8c5d2a9e4f1b6c8d0a3e5f7b9c2d";
const INDEXNOW_KEY = process.env.INDEXNOW_KEY || STATIC_INDEXNOW_KEY;
const SITEMAP_URL = `${SITE_URL}/sitemap.xml`;

const explicitUrls = process.argv.slice(2).filter((a) => a.startsWith("http"));

/**
 * Fetch the sitemap and return all <loc> URLs found.
 */
async function fetchSitemapUrls() {
  const res = await fetch(SITEMAP_URL);
  if (!res.ok) throw new Error(`Sitemap fetch failed: ${res.status} ${res.statusText}`);
  const xml = await res.text();
  const matches = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)];
  return matches.map((m) => m[1].trim());
}

/**
 * IndexNow batch ping. One POST covers Bing/Yandex/Naver/Seznam/Yep.
 * Spec: https://www.indexnow.org/documentation/key-location
 */
async function pingIndexNow(urls) {
  if (!INDEXNOW_KEY) {
    console.log("⊘ Skipping IndexNow — INDEXNOW_KEY env var not set");
    return { ok: false, skipped: true };
  }
  const host = new URL(SITE_URL).host;
  const body = {
    host,
    key: INDEXNOW_KEY,
    keyLocation: `${SITE_URL}/${INDEXNOW_KEY}.txt`,
    urlList: urls,
  };
  const res = await fetch("https://api.indexnow.org/indexnow", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(body),
  });
  // 200 OK = accepted, 202 Accepted = queued, both fine.
  // 422 = key/host mismatch (key file not at the expected URL).
  if (res.ok || res.status === 202) {
    console.log(`✓ IndexNow accepted ${urls.length} URLs (${res.status})`);
    return { ok: true };
  }
  const text = await res.text().catch(() => "");
  console.error(`✗ IndexNow ${res.status}: ${text || res.statusText}`);
  return { ok: false, status: res.status };
}

/**
 * Bing sitemap ping (no key required, GET request).
 * Bing's documented endpoint — Google's was retired in mid-2023.
 */
async function pingBingSitemap() {
  const url = `https://www.bing.com/ping?sitemap=${encodeURIComponent(SITEMAP_URL)}`;
  const res = await fetch(url);
  if (res.ok) {
    console.log(`✓ Bing sitemap ping accepted`);
    return { ok: true };
  }
  console.error(`✗ Bing sitemap ping failed: ${res.status}`);
  return { ok: false, status: res.status };
}

async function main() {
  console.log(`Notifying search engines for ${SITE_URL}`);

  let urls;
  if (explicitUrls.length > 0) {
    urls = explicitUrls;
    console.log(`Using ${urls.length} URL(s) from command line`);
  } else {
    console.log(`Fetching sitemap from ${SITEMAP_URL}`);
    urls = await fetchSitemapUrls();
    console.log(`Found ${urls.length} URLs in sitemap`);
  }

  // IndexNow caps a single batch at 10,000 URLs. We're well under that
  // for the foreseeable future, but defensive batching doesn't hurt.
  const BATCH_SIZE = 10000;
  const results = [];
  for (let i = 0; i < urls.length; i += BATCH_SIZE) {
    const batch = urls.slice(i, i + BATCH_SIZE);
    results.push(await pingIndexNow(batch));
  }

  results.push(await pingBingSitemap());

  const failures = results.filter((r) => !r.ok && !r.skipped);
  if (failures.length > 0) {
    console.error(`\n${failures.length} ping(s) failed`);
    process.exit(1);
  }
  console.log(`\nDone.`);
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
