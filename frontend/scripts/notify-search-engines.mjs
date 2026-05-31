#!/usr/bin/env node
/**
 * Notify search engines that pages have updated.
 *
 * The ONE working real-time channel for a low-authority site like ours:
 *   • IndexNow — a single POST notifies Bing, Yandex, Naver, Seznam and Yep
 *     at once. Bing typically crawls within minutes of the ping.
 *
 * What we deliberately do NOT do, and why (both verified returning dead
 * status codes against the live endpoints on 2026-05-31):
 *   • Google sitemap ping — RETIRED by Google in June 2023. The old
 *     https://www.google.com/ping?sitemap=… endpoint now returns 404.
 *     Google has no per-URL / per-deploy submission API for ordinary pages
 *     (the Indexing API is restricted to JobPosting / BroadcastEvent, which
 *     we are not). The correct — and only — Google lever is passive:
 *     declare the sitemap in robots.txt (we do:
 *     `Sitemap: https://tapeline.io/sitemap.xml`) with accurate
 *     <lastmod>/<changefreq> (our sitemap has both on all 1138 URLs), and
 *     Google re-crawls changed URLs on its own schedule. There is nothing
 *     to "ping" for Google; calling the dead endpoint only fails the build.
 *   • Bing sitemap ping — ALSO retired; https://www.bing.com/ping?sitemap=…
 *     now returns 410 Gone. Bing is already covered by IndexNow above, which
 *     is strictly better (real-time, per-URL), so the dead GET was pure noise
 *     that turned every deploy ping red.
 *
 * Net: IndexNow is the only thing to call. If IndexNow succeeds, the
 * post-deploy search-engine notification succeeded.
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
 *   INDEXNOW_KEY     — IndexNow key. Defaults to the static key whose proof
 *                      file is served at $SITE_URL/$INDEXNOW_KEY.txt, so this
 *                      works out of the box in CI / on a fresh clone with no
 *                      GitHub-secret configuration. Override only if rotating.
 */

const SITE_URL = (process.env.SITE_URL || "https://tapeline.io").replace(/\/$/, "");
// Static IndexNow key — proof file lives at frontend/public/<key>.txt and is
// served by Vercel. Keeping a literal default means this script works out of
// the box in CI without any GitHub-secret configuration.
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

  // IndexNow caps a single batch at 10,000 URLs. We're well under that for
  // the foreseeable future, but defensive batching doesn't hurt.
  const BATCH_SIZE = 10000;
  const results = [];
  for (let i = 0; i < urls.length; i += BATCH_SIZE) {
    const batch = urls.slice(i, i + BATCH_SIZE);
    results.push(await pingIndexNow(batch));
  }

  // Google: nothing to ping (google.com/ping?sitemap= was retired in 2023 and
  // returns 404). Google discovers and re-crawls via the sitemap declared in
  // robots.txt, driven by per-URL <lastmod>. This line is informational only
  // so the pipeline isn't mistaken for "not notifying Google".
  console.log(
    "ℹ Google: no ping endpoint exists (retired 2023) — discovery is via the " +
      "sitemap declared in robots.txt; re-crawl is driven by <lastmod>."
  );

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
