#!/usr/bin/env node
/**
 * IndexNow auto-submitter for tapeline.io — self-service search-engine indexing.
 *
 * Fetches the live sitemap and pings the IndexNow endpoint so new/changed pages
 * get crawled with NObody logging in. IndexNow is accepted by Bing, Yandex,
 * Seznam and Naver. (Google does NOT support IndexNow as of 2026 — Google
 * indexing is discovery-via-sitemap-crawl + the GSC UI; there is no public API
 * to "request indexing" of ordinary pages, so it can't be automated here.)
 *
 * Why this needs NO credentials: IndexNow's entire auth model is a key file
 * hosted on the site itself (frontend/public/<key>.txt). The endpoint fetches
 * that file to prove ownership. That's it — no OAuth, no service account, no
 * secret. This is the one indexing lever that can run fully autonomously.
 *
 * Run:
 *   node frontend/scripts/indexnow-submit.mjs             # submit all sitemap URLs
 *   node frontend/scripts/indexnow-submit.mjs --dry-run   # parse + count only, no POST
 *
 * Env (all optional — defaults target production):
 *   INDEXNOW_SITE      default "tapeline.io"
 *   INDEXNOW_KEY       default the hosted key below
 *   INDEXNOW_SITEMAP   default "https://<site>/sitemap.xml"
 *
 * Scheduled by .github/workflows/indexnow.yml (on deploy to main + weekly).
 * Requires Node 18+ (global fetch).
 */

const SITE = process.env.INDEXNOW_SITE || "tapeline.io";
// One of the two keys hosted in frontend/public/. Any hosted, self-matching key
// is valid; override via env if it's ever rotated.
const KEY = process.env.INDEXNOW_KEY || "2f761f0829298a6251b237657434f12e";
const SITEMAP = process.env.INDEXNOW_SITEMAP || `https://${SITE}/sitemap.xml`;
const KEY_LOCATION = `https://${SITE}/${KEY}.txt`;
const ENDPOINT = "https://api.indexnow.org/indexnow";
const BATCH = 10000; // IndexNow accepts up to 10,000 URLs per request
const DRY = process.argv.includes("--dry-run");

async function main() {
  // 1. The key file must be served AND contain exactly the key, or IndexNow
  //    rejects the whole submission. Fail loud if the hosting ever breaks.
  const kf = await fetch(KEY_LOCATION);
  const kbody = (await kf.text()).trim();
  if (!kf.ok || kbody !== KEY) {
    console.error(
      `key file ${KEY_LOCATION} invalid (status ${kf.status}, body "${kbody.slice(0, 24)}") — aborting`,
    );
    process.exit(1);
  }

  // 2. Pull the sitemap and extract same-host URLs.
  const sm = await fetch(SITEMAP);
  if (!sm.ok) {
    console.error(`sitemap fetch failed: HTTP ${sm.status} ${SITEMAP}`);
    process.exit(1);
  }
  const xml = await sm.text();
  const urls = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)]
    .map((m) => m[1].trim())
    .filter((u) => u.startsWith(`https://${SITE}`));
  if (urls.length === 0) {
    console.error("no <loc> URLs found in sitemap — aborting");
    process.exit(1);
  }
  console.log(`${urls.length} URL(s) from ${SITEMAP}`);

  if (DRY) {
    console.log("dry-run — not submitting. Sample:\n  " + urls.slice(0, 5).join("\n  "));
    return;
  }

  // 3. POST in batches; count accepted (200/202).
  let accepted = 0;
  for (let i = 0; i < urls.length; i += BATCH) {
    const urlList = urls.slice(i, i + BATCH);
    const res = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ host: SITE, key: KEY, keyLocation: KEY_LOCATION, urlList }),
    });
    const batchNo = Math.floor(i / BATCH) + 1;
    console.log(`batch ${batchNo}: ${urlList.length} URL(s) -> HTTP ${res.status} ${res.statusText}`);
    if (res.status === 200 || res.status === 202) accepted += urlList.length;
  }
  console.log(`IndexNow: ${accepted}/${urls.length} URL(s) accepted (Bing/Yandex/Seznam/Naver).`);
  if (accepted === 0) process.exit(1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
