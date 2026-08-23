/**
 * Re-shoot the press-kit screenshots.
 *
 * WHY THIS EXISTS. The four PNGs in public/press/ were captured by hand on
 * 2026-08-20 and then went stale in the worst possible way: the 2026-08-22 card
 * gate made their copy false, and the claims were baked into the pixels where
 * no linter, test or grep could see them. `tapeline-scorecard.png` shipped
 * "Free forever tier — no card" and "14-day Premium trial — no card, nothing
 * charged"; the landing shot carried "No credit card, no payment details,
 * nothing charged". docs/OFFSITE.md points press outreach at these files, so
 * they were a live route to handing a journalist a false claim about money.
 *
 * A hand-shot asset cannot be kept honest. This script makes them reproducible:
 * run it after any copy change that touches these four screens.
 *
 *   node scripts/capture-press-shots.mjs                  # shoot production
 *   node scripts/capture-press-shots.mjs --base http://localhost:3000
 *   node scripts/capture-press-shots.mjs --out /tmp/shots # don't overwrite
 *
 * Geometry matches the originals exactly: a 1270x760 viewport at DPR 2 gives
 * the same 2540x1520 asset, so anything already embedding them is unaffected.
 * Dark is forced rather than left to `prefers-color-scheme`, because the site
 * defaults to Auto and a CI runner would otherwise shoot light.
 */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_OUT = resolve(HERE, "..", "public", "press");

const args = process.argv.slice(2);
const argOf = (flag, fallback) => {
  const i = args.indexOf(flag);
  return i !== -1 && args[i + 1] ? args[i + 1] : fallback;
};
const BASE = argOf("--base", "https://tapeline.io").replace(/\/$/, "");
const OUT = resolve(argOf("--out", DEFAULT_OUT));

/**
 * Filenames are load-bearing — docs/OFFSITE.md and the growth dossier link them
 * directly — so the mapping stays fixed and only the pixels change.
 */
const SHOTS = [
  { file: "tapeline-scanner.png", path: "/", wait: "h1" },
  { file: "tapeline-scorecard.png", path: "/scorecard", wait: "text=/THE RECORD SO FAR/i" },
  { file: "tapeline-ticker.png", path: "/t/AAPL", wait: "text=/AAPL/" },
  { file: "tapeline-verify.png", path: "/verify", wait: "text=/scorecard/i" },
];

/**
 * Claims that must never appear in a press asset again. Checked against the
 * rendered text before the shot is written, so a regression fails the run
 * instead of silently shipping. Mirrors the card-honesty rule in
 * frontend/app/signup/page.tsx and /legal/refund.
 *
 * These target the ACCOUNT and the TRIAL specifically. A bare "no card" is not
 * banned, because it is still true of the things that really are card-free —
 * the daily-picks newsletter ("One email, one minute, no card") and the public
 * record. Banning the bare phrase flagged all four pages on the first run for
 * copy that is perfectly honest, which is exactly the over-correction this
 * whole cleanup kept having to undo.
 */
const BANNED = [
  /no credit card/i,
  /free forever/i,
  /nothing charged/i,
  /try premium free/i,
  // The gap excludes \n deliberately. Without it a "no card" ending one line
  // matched an "account" opening the next, and the landing page failed on two
  // unrelated sentences.
  /(account|sign ?up|trial)[^.!?\n]{0,40}\bno card\b/i,
  /\bno card\b[^.!?\n]{0,40}(account|sign ?up|trial)/i,
];

/**
 * Sentences that legitimately say "no card" get lifted out before the scan, so
 * the contextual patterns above cannot trip on them. Keyed on the newsletter
 * and public-record language rather than on the claim itself.
 */
const CARD_FREE_AND_TRUE = /(unsubscribe|inbox|each (US )?market morning|public record|scorecard|daily top 10)/i;

const run = async () => {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1270, height: 760 },
    deviceScaleFactor: 2,
    colorScheme: "dark",
    // The site reads a theme cookie before falling back to prefers-color-scheme.
    // Without this the shot can land mid-flip between light and dark.
    extraHTTPHeaders: { "Accept-Language": "en-US,en;q=0.9" },
  });
  await ctx.addInitScript(() => {
    try {
      window.localStorage.setItem("tapeline_theme", "dark");
    } catch {
      /* storage blocked — the colorScheme above still applies */
    }
  });

  const page = await ctx.newPage();
  const failures = [];

  for (const shot of SHOTS) {
    const url = `${BASE}${shot.path}`;
    process.stdout.write(`  ${shot.file.padEnd(26)} ${url} … `);
    await page.goto(url, { waitUntil: "networkidle", timeout: 60_000 });
    try {
      await page.waitForSelector(shot.wait, { timeout: 15_000 });
    } catch {
      process.stdout.write("(content selector missed) ");
    }
    // Let webfonts settle so glyphs don't shift between runs.
    await page.evaluate(() => document.fonts?.ready);
    await page.waitForTimeout(600);

    const text = await page.evaluate(() => document.body.innerText);
    const scannable = text
      .split(/\n+/)
      .filter((line) => !CARD_FREE_AND_TRUE.test(line))
      .join("\n");
    const hits = BANNED.filter((re) => re.test(scannable)).map(String);
    if (hits.length) failures.push(`${shot.path} still renders: ${hits.join(", ")}`);

    // Next 16's SWC drops the whitespace in `{expr} word`, so a number glued to
    // the following word ("up to 1,000rows") ships silently. Both live cases
    // were found by eye in a press shot, which is far too late — this catches
    // the numeric half automatically. It cannot catch word-to-word glue
    // ("Tapeline Scoreblends"), which still needs a human looking at the image.
    // Units that are legitimately written tight ("~5min refresh", "60fps") are
    // allowlisted, so the check stays worth reading. Without this it flagged
    // LiveCounters' deliberate "~5min" alongside the real "1,000rows" bug.
    const COMPACT_UNIT = /^\d+(min|mins|hr|hrs|sec|secs|ms|fps|px|kb|mb|gb|am|pm|yr|yrs|mo|wk|st|nd|rd|th)$/i;
    const glued = [...text.matchAll(/\d[a-z]{2,}/g)]
      .map((m) => m[0])
      .filter((w) => !COMPACT_UNIT.test(w));
    if (glued.length) {
      failures.push(`${shot.path} has glued text (missing {" "}): ${[...new Set(glued)].join(", ")}`);
    }

    await page.screenshot({ path: join(OUT, shot.file) });
    console.log(hits.length ? `WROTE (${hits.length} banned)` : "ok");
  }

  await browser.close();

  if (failures.length) {
    console.error("\nBANNED COPY STILL ON THE PAGE — do not ship these assets:");
    for (const f of failures) console.error(`  - ${f}`);
    process.exit(1);
  }
  console.log(`\nAll four clean. Written to ${OUT}`);
};

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
