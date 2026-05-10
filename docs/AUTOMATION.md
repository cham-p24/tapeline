# SEO Automation

**Last updated:** 2026-05-10
**Owner:** Founder
**Status:** Active — IndexNow + post-deploy ping wired; weekly recap is human-reviewed

---

## What's automated

The site has three automation surfaces. Each one is owned by a single script or workflow file so you always know where to look when something stops working.

| Surface                                      | What it does                                                                                                                                                          | Trigger                                              | File                                                                                                          |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Sitemap generation**                       | Pulls the top-500 tickers from `/api/public/top-tickers`, plus all static + sector + signal + blog URLs, into a single `sitemap.xml` revalidated hourly                | Crawler request to `/sitemap.xml`                    | [`frontend/app/sitemap.ts`](../frontend/app/sitemap.ts)                                                       |
| **IndexNow + Bing sitemap ping**             | Notifies Bing/Yandex/Naver/Seznam/Yep that pages have updated. IndexNow batch covers all of them with one POST.                                                       | After deploy (manual) + daily at 14:00 UTC (cron)    | [`frontend/scripts/notify-search-engines.mjs`](../frontend/scripts/notify-search-engines.mjs) → [`.github/workflows/post-deploy-seo.yml`](../.github/workflows/post-deploy-seo.yml) |
| **Weekly scorecard recap blog post (draft)** | Pulls last 7 days of `/api/scorecard`, computes summary stats + best/worst 5, writes a draft `.ts` file to `frontend/app/blog/_drafts/` for human review and editing  | Manual: `node frontend/scripts/generate-weekly-recap.mjs` | [`frontend/scripts/generate-weekly-recap.mjs`](../frontend/scripts/generate-weekly-recap.mjs)                  |

---

## One-time setup

### IndexNow key

1. Generate a key (any 8-128 hex chars):
   ```sh
   node -e 'console.log(require("crypto").randomBytes(16).toString("hex"))'
   ```
2. Set the same value in two places:
   - **Hosting env vars** (Vercel / Fly / wherever the frontend runs) as `INDEXNOW_KEY`
   - **GitHub Actions secrets** as `INDEXNOW_KEY` — at https://github.com/cham-p24/tapeline/settings/secrets/actions
3. Verify by visiting `https://tapeline.io/<KEY>.txt` — it should return the key as plaintext (served by [`middleware.ts`](../frontend/middleware.ts)). The middleware regex restricts to single-segment hex `.txt` URLs so it never collides with `robots.txt`, `ads.txt`, or any other legitimate file.
4. Once verified, the next post-deploy ping will use the key automatically.

### Search Console + Bing Webmaster

These aren't automation per se but the post-deploy ping assumes the sitemap is already submitted:

1. Search Console: add `tapeline.io` as a **Domain property** (not URL property — covers all subdomains). Verify via DNS TXT record. Submit `https://tapeline.io/sitemap.xml`.
2. Bing Webmaster: add `tapeline.io`, import GSC verification, submit the same sitemap.
3. Both portals will start surfacing impression data within 2-7 days of the first crawl.

### GitHub Actions repository variable

The workflow reads `vars.SITE_URL` (defaulting to `https://tapeline.io`). Set it explicitly only if you ever run the workflow against a staging or preview URL:

- https://github.com/cham-p24/tapeline/settings/variables/actions
- Add: `SITE_URL` = `https://tapeline.io`

---

## How the automation runs

### After a deploy (manual trigger, ~10 seconds)

1. Open https://github.com/cham-p24/tapeline/actions/workflows/post-deploy-seo.yml
2. Click **Run workflow**
3. (Optional) Paste a space-separated list of URLs to ping — e.g. `https://tapeline.io/blog/new-post https://tapeline.io/best-stock-scanners`. If empty, the full sitemap is re-announced.
4. Click **Run workflow** again to confirm

The workflow logs `✓ IndexNow accepted N URLs` and `✓ Bing sitemap ping accepted` on success. Failures are non-zero exit codes — GitHub Actions will surface a red X next to the run.

### Daily safety net (automatic)

The same workflow runs at 14:00 UTC every day on cron. This catches:
- Deploys that didn't trigger the manual ping
- Drift in the sitemap (newly-discovered tickers, lastmod updates)
- IndexNow caching invalidations on the search-engine side

It's idempotent — pinging the same URLs twice in a day does nothing harmful.

### Weekly recap (manual draft generation, ~30s + 15-30 min editing)

The pipeline is intentionally human-in-the-loop because programmatic content claiming past performance needs careful framing. Process:

1. Run `node frontend/scripts/generate-weekly-recap.mjs` (locally or via a one-off GitHub Actions step you can add later)
2. The script writes a draft to `frontend/app/blog/_drafts/weekly-scorecard-YYYY-MM-DD.ts`
3. Open the draft and:
   - Read every sentence — confirm the numbers match `/scorecard`
   - Replace the `[FOUNDER NARRATIVE]` block with a 2-3 sentence read on the week
   - Optionally tighten the title and excerpt
4. Copy the post object into `frontend/app/blog/posts.ts` `POSTS` array
5. Commit, push, deploy
6. Trigger the post-deploy ping (with the new blog URL as an explicit URL argument for fastest indexing)

You can wire this into a weekly cron later if you trust the prose enough — the script accepts an `OUT_DIR` env var so it could write to a Pull Request branch instead of the local file system.

---

## How to extend

### Ping search engines on a different schedule

Edit the cron in [`.github/workflows/post-deploy-seo.yml`](../.github/workflows/post-deploy-seo.yml). GitHub Actions cron is best-effort under load (sometimes runs 5-15 min late) — don't over-tune the timing.

### Ping search engines from the app on demand

Call the script directly from a Next.js Server Action or a backend handler:

```ts
import { exec } from "node:child_process";
exec(
  `node frontend/scripts/notify-search-engines.mjs ${urls.join(" ")}`,
  { env: { ...process.env, INDEXNOW_KEY: process.env.INDEXNOW_KEY } },
);
```

Use case: trigger after a new blog post is published, or after a material update to a comparison page.

### Add new URLs to the sitemap

Add to the `staticEntries` array in [`frontend/app/sitemap.ts`](../frontend/app/sitemap.ts). The next crawl picks them up automatically — no IndexNow ping needed for sitemap inclusion (but a ping will speed up indexing for those specific URLs).

### Add new structured data

Use the helpers in [`frontend/lib/jsonld.ts`](../frontend/lib/jsonld.ts):
- `faqJsonLd(items)` — for FAQ pages
- `breadcrumbJsonLd(items)` — for breadcrumbs
- `articleJsonLd(args)` — for blog posts
- `tickerReviewJsonLd(args)` — for per-ticker pages
- `jsonLdScript(data)` — render helper

All of these return plain objects suitable for `<script {...jsonLdScript(faqJsonLd([...]))}/>`. Validate at https://search.google.com/test/rich-results before deploying.

### Wire up Plausible event tracking for SEO conversion

Plausible is already loaded via `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` in [`layout.tsx`](../frontend/app/layout.tsx). To track SEO-attributed signup conversions specifically:

```html
<a href="/signup" data-event-name="signup_from_organic" onclick="plausible('SignupCTA',{props:{source:'organic'}})">
```

This requires identifying which sessions came from organic search — Plausible exposes that via the Source filter. Cleanest implementation is a Plausible Goals webhook → in-app analytics dashboard.

---

## Monitoring

| Metric                            | Where                                                                                                       | How often    |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------ |
| Indexed-page count                | Search Console → Coverage                                                                                   | Weekly       |
| Top organic queries / pages       | Search Console → Performance (set date range to 28 days)                                                    | Weekly       |
| IndexNow ping success/failure     | https://github.com/cham-p24/tapeline/actions/workflows/post-deploy-seo.yml — green tick = pass, red X = fail | After each run |
| Sitemap freshness                 | https://tapeline.io/sitemap.xml — check the `<lastmod>` on the homepage entry                                | After each deploy |
| Schema validation                 | https://search.google.com/test/rich-results — paste a URL, look for parsing errors                          | After deploy of any new schema |
| Backlink growth                   | Bing Webmaster Tools → Backlinks (Ahrefs free tier as a complement)                                          | Monthly      |

---

## Failure modes & what to do

| Symptom                                                            | Likely cause                                                                                  | Fix                                                                                              |
| ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `notify-search-engines.mjs` exits with `IndexNow 422`              | Key file at `/<KEY>.txt` doesn't return 200 with the key as content                          | Confirm `INDEXNOW_KEY` env var is set on the host AND matches the URL the request used          |
| `notify-search-engines.mjs` reports `INDEXNOW_KEY not set`          | GitHub Actions secret missing                                                                  | Set it at https://github.com/cham-p24/tapeline/settings/secrets/actions                         |
| Sitemap fetch fails in the script                                  | Hosting is down, or `SITE_URL` is wrong                                                       | Check `https://tapeline.io/sitemap.xml` returns 200 in a browser                                 |
| New page in sitemap but Google says "Discovered — not indexed"     | Site is too new for Google to crawl everything; OR the page has thin content                  | Wait 2-4 weeks for new sites; for thin pages, add more unique content (especially in `/sector/*`) |
| FAQ rich result not appearing despite valid schema                 | Google de-prioritised FAQ rich results in 2023 except for gov + health domains                | Schema is still valuable for AI search engines (ChatGPT, Perplexity); don't remove it           |
| Post-deploy ping not firing automatically                          | The workflow is `workflow_dispatch` (manual) by design — there's no auto trigger on Vercel deploy | Either click "Run workflow" manually, or wire a Vercel Deployment Hook to call the GitHub API   |

---

## What's NOT automated (and why)

- **Blog post writing.** Generator drafts the structure; founder writes the prose. Auto-published AI content claiming past financial performance is both an SEO and a regulatory risk.
- **Social posting.** Cross-posting to X/LinkedIn is platform-policy-grey when scripted; tools like Buffer or Typefully are the right surface, not a homemade script.
- **Backlink outreach.** Manual relationship work — automation here is spam by another name.
- **Ad spend / SEM.** Out of scope for the SEO branch entirely.

---

## Related

- **[docs/SEO.md](./SEO.md)** — strategy, keyword targets, content roadmap
- **[docs/OFFSITE.md](./OFFSITE.md)** — off-site profile creation checklist
- **[frontend/app/sitemap.ts](../frontend/app/sitemap.ts)** — sitemap generator
- **[frontend/middleware.ts](../frontend/middleware.ts)** — IndexNow key endpoint
