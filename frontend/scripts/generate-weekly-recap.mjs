#!/usr/bin/env node
/**
 * Weekly Tapeline scorecard recap generator.
 *
 * Pulls the last 7 days from /api/scorecard, computes summary stats,
 * picks out the 5 best and 5 worst calls, and generates a draft blog
 * post body. The script DOES NOT publish — it writes the draft to a
 * local file under frontend/app/blog/_drafts/ for human review and
 * editing before paste-into blog/posts.ts.
 *
 * Why human-in-the-loop: programmatic SEO posts that claim past
 * performance need careful framing (no return predictions, descriptive
 * not prescriptive, no implied advice). The script does the data
 * extraction; the founder writes the framing.
 *
 * Usage:
 *   node frontend/scripts/generate-weekly-recap.mjs
 *
 * Env vars:
 *   API_BASE   — defaults to https://api.tapeline.io
 *   OUT_DIR    — defaults to frontend/app/blog/_drafts
 */

import { mkdir, writeFile } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..", "..");

const API_BASE = (process.env.API_BASE || "https://api.tapeline.io").replace(/\/$/, "");
const OUT_DIR = process.env.OUT_DIR || join(REPO_ROOT, "frontend/app/blog/_drafts");

async function fetchScorecard(days = 7) {
  const url = `${API_BASE}/api/scorecard?days=${days}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Scorecard fetch failed: ${res.status} ${res.statusText}`);
  return res.json();
}

function fmtPct(n) {
  if (n == null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function isoDate(d = new Date()) {
  return d.toISOString().split("T")[0];
}

function weekRangeLabel() {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 7);
  const fmt = (d) =>
    d.toLocaleDateString("en-US", { month: "long", day: "numeric" });
  return `${fmt(start)} – ${fmt(end)}, ${end.getFullYear()}`;
}

function generateBody(data) {
  const { summary = {}, days = {} } = data;
  const dayKeys = Object.keys(days).sort();
  const allEntries = dayKeys.flatMap((d) =>
    (days[d] || []).map((e) => ({ ...e, day: d })),
  );

  // Best 5 by 1-day post-flag move.
  const best = [...allEntries]
    .filter((e) => e.change_pct_1d_after != null)
    .sort((a, b) => b.change_pct_1d_after - a.change_pct_1d_after)
    .slice(0, 5);

  // Worst 5 by 1-day post-flag move.
  const worst = [...allEntries]
    .filter((e) => e.change_pct_1d_after != null)
    .sort((a, b) => a.change_pct_1d_after - b.change_pct_1d_after)
    .slice(0, 5);

  const totalEntries = summary.entries_scored ?? allEntries.length;
  const hitRate =
    summary.hit_rate_beat_spy != null
      ? `${(summary.hit_rate_beat_spy * 100).toFixed(1)}%`
      : "—";
  const avgAlpha =
    summary.avg_alpha_vs_spy != null ? fmtPct(summary.avg_alpha_vs_spy) : "—";
  const avgReturn =
    summary.avg_1d_return != null ? fmtPct(summary.avg_1d_return) : "—";

  const tableRow = (e) =>
    `        <tr><td><a href="/t/${e.symbol}">${e.symbol}</a></td><td>${e.score_at_flag.toFixed(0)}</td><td>${fmtPct(e.change_pct_1d_after)}</td><td>${fmtPct(e.spy_change_pct_1d)}</td><td>${fmtPct(e.alpha_vs_spy)}</td><td>${e.day}</td></tr>`;

  return `
      <p>The Tapeline scorecard is auto-published and immutable. Every top-10 daily pick
      is back-checked against the next-day SPY-relative move. This is the weekly recap of
      <strong>${weekRangeLabel()}</strong> — what worked, what didn't, and what the
      data shows about the model's current state.</p>

      <h2>Week summary</h2>
      <ul>
        <li><strong>Total picks scored:</strong> ${totalEntries}</li>
        <li><strong>Hit rate (beat SPY next day):</strong> ${hitRate}</li>
        <li><strong>Average 1-day return:</strong> ${avgReturn}</li>
        <li><strong>Average alpha vs SPY:</strong> ${avgAlpha}</li>
      </ul>
      <p>None of these are return predictions. They are descriptive measurements of how
      the published 6-factor formula performed, in aggregate, against a benchmark over the
      week. Past performance is not indicative of future results — see the
      <a href="/legal/risk">risk disclosure</a> for the full caveat.</p>

      <h2>Best 5 calls of the week</h2>
      <table>
        <thead>
          <tr><th>Ticker</th><th>Score at flag</th><th>1d return</th><th>SPY 1d</th><th>Alpha</th><th>Date</th></tr>
        </thead>
        <tbody>
${best.map(tableRow).join("\n")}
        </tbody>
      </table>

      <h2>Worst 5 calls of the week</h2>
      <p>Published with the same prominence as the wins — that's the point of an
      immutable scorecard.</p>
      <table>
        <thead>
          <tr><th>Ticker</th><th>Score at flag</th><th>1d return</th><th>SPY 1d</th><th>Alpha</th><th>Date</th></tr>
        </thead>
        <tbody>
${worst.map(tableRow).join("\n")}
        </tbody>
      </table>

      <h2>What we're watching</h2>
      <p>[FOUNDER NARRATIVE — replace this paragraph with a 2-3 sentence read on the
      current market regime, what was driving the misses, and any methodology
      observations. Examples of what to call out: macro factor rotation, a sector
      with anomalously high or low hit rate, or a known data-feed issue affecting
      a subset of tickers.]</p>

      <p>See the full raw scorecard at <a href="/scorecard">/scorecard</a>; the methodology
      is at <a href="/how-it-works">/how-it-works</a>.</p>
  `.trim();
}

function generatePostMeta(data) {
  const today = isoDate();
  const slug = `weekly-scorecard-${today}`;
  const summary = data.summary ?? {};
  const hitRate =
    summary.hit_rate_beat_spy != null
      ? `${(summary.hit_rate_beat_spy * 100).toFixed(0)}%`
      : "—";
  const avgAlpha =
    summary.avg_alpha_vs_spy != null
      ? fmtPct(summary.avg_alpha_vs_spy)
      : "—";

  return {
    slug,
    title: `Weekly scorecard: ${weekRangeLabel()}`,
    excerpt: `Hit rate ${hitRate}, average alpha ${avgAlpha} vs SPY. The full breakdown of what the Tapeline 6-factor model called this week — best 5 and worst 5 calls, both published with equal prominence.`,
    publishedAt: today,
    author: "Tapeline",
  };
}

async function main() {
  console.log(`Pulling last 7 days from ${API_BASE}/api/scorecard...`);
  const data = await fetchScorecard(7);
  const meta = generatePostMeta(data);
  const body = generateBody(data);

  const draft = `// AUTO-GENERATED DRAFT — review before pasting into blog/posts.ts.
// Generated: ${new Date().toISOString()}
// Source: ${API_BASE}/api/scorecard?days=7

export const draft = {
  slug: "${meta.slug}",
  title: ${JSON.stringify(meta.title)},
  excerpt: ${JSON.stringify(meta.excerpt)},
  publishedAt: "${meta.publishedAt}",
  author: "${meta.author}",
  body: \`${body.replace(/`/g, "\\`").replace(/\$\{/g, "\\${")}\`,
};
`;

  await mkdir(OUT_DIR, { recursive: true });
  const outPath = join(OUT_DIR, `${meta.slug}.ts`);
  await writeFile(outPath, draft, "utf8");
  console.log(`✓ Draft written to ${outPath}`);
  console.log(`\nNext steps:`);
  console.log(`  1. Review the draft (especially the [FOUNDER NARRATIVE] block)`);
  console.log(`  2. Edit prose where needed`);
  console.log(`  3. Add the post object to POSTS in frontend/app/blog/posts.ts`);
  console.log(`  4. Commit, push, deploy — the post auto-lands in sitemap + RSS`);
  console.log(`  5. Run notify-search-engines.mjs to expedite indexing`);
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
