// Voice-over cuts of concepts B, D and E.
//
//   2026-09-11  Long cuts (26-29 s) in 9:16, 4:5 and 1:1.
//   2026-09-14  Concept E rewritten: its record lines were false. The shared
//               CTA no longer says "no account and no card" beside the trial.
//               The money scene carries "card required", price and interval.
//               Added <=15 s cuts, verbatim .en_US.srt captions, and the Meta
//               text fields (generated here, so they read the same constants).
//   2026-09-15  E's scorecard line said each score sits "next to" the following
//               session's move and SPY's. Not every entry has one, so it now
//               says "where recorded"; the record-claim gate rejects "each next to".
//
// THE TIMING RULE THAT MATTERS
// ----------------------------
// The silent cuts were timed for READING: 2.6-3.4s a scene. Speech is slower.
// The first script ran 41.2s of speech (45.1s cut) for B -- 2.5x the silent
// version, far past where Reels attention holds. So the lines are short, the
// voice is generated FIRST and measured, and each scene is held for
// max(base hold, lead-in + spoken length + tail), rounded to a whole frame so
// the captions, the audio and the picture share one clock. The picture follows
// the voice, never the reverse.
//
// The money and CTA scenes are identical across all three concepts, sound
// included, so a difference in results is attributable to the hook.
//
// COMPLIANCE GATES, all run BEFORE anything is synthesised:
//   1. Every spoken line, every on-screen line, every caption and every Meta
//      text field is written to vo-script.md / meta-copy-2026-09.md and run
//      through `lint-copy-compliance.mjs --ads`.
//   2. The same text is checked against RECORD_CLAIMS: record claims the
//      linter does not catch ("every day", "each session", "frozen",
//      "logged", "never re-ranked"...). Concept E shipped three of them.
//   3. This file's own strings may not hard-code a trial length. It is read
//      from frontend/lib/trial.ts, because the trial moved 14 -> 30 days on
//      2026-09-05 and a live ad kept saying 14.
//   4. Meta's field limits: the price and interval inside the first 125
//      characters of the primary text, headline <= 40, description <= 25.
//
// The trial length is deliberately NOT spoken. It is on screen. A spoken
// number is one more place for it to go stale.
//
// Voice: en-US-AndrewNeural (Microsoft neural, via edge-tts). Local SAPI only
// offers David/Zira, which would make the ads worse than silence.
//
// RUN: from a working folder holding node_modules/ffmpeg-static, a copy of
// shot-ticker.png and ../ttsvenv (edge-tts). Set TAPELINE_REPO to the checkout
// whose constants and linter should be used. Outputs land in that folder:
//   voiceover/*.mp4 + *.en_US.srt, voiceover-15s/*.mp4 + *.en_US.srt,
//   vo-script.md, meta-copy-2026-09.md, check/ (probe report + frame grabs).
//   node build3.mjs              # everything
//   node build3.mjs --copy-only  # text + gates only, no audio or video

import { writeFileSync, mkdirSync, readFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import ffmpeg from "ffmpeg-static";

const OUT = process.cwd();
const OUTU = OUT.replace(/\\/g, "/");
const CHROME = process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REPO = (process.env.TAPELINE_REPO || "C:/Project 1").replace(/\\/g, "/");
const TTS = process.env.EDGE_TTS || join(OUT, "..", "ttsvenv", "Scripts", "edge-tts.exe");
const COPY_ONLY = process.argv.includes("--copy-only");
const VOICE = "en-US-AndrewNeural";
const RATE = "+0%";
const FPS = 30;
const LEAD = 0.15;   // voice starts just after the cut, so the cut never clips it
const TAIL = 0.50;   // breath before the next scene
const SHORT_MAX_S = 15;
const SHORT_MAX_WORDS = 30;

// Retry + surface stderr. The first run lost a whole batch to one transient
// ffmpeg crash whose reason was invisible because stdio was "ignore"; the
// identical command exited 0 on a manual rerun.
function run(bin, args, label) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      return execFileSync(bin, args, { stdio: ["ignore", "pipe", "pipe"], maxBuffer: 64 * 1024 * 1024 });
    } catch (e) {
      if (attempt === 3) {
        throw new Error(label + " failed after 3 attempts:\n" + String(e.stderr || e.message).slice(-2500));
      }
    }
  }
}

function readRepo(rel) {
  return readFileSync(join(REPO, rel), "utf8");
}
function must(re, text, what) {
  const m = re.exec(text);
  if (!m) throw new Error("cannot read " + what + " -- the source moved; fix the pattern, never type the value");
  return m;
}

// ---- Constants are READ, never typed ---------------------------------------
const TRIAL_DAYS = must(/export const TRIAL_DAYS = (\d+)/, readRepo("frontend/lib/trial.ts"), "TRIAL_DAYS")[1];
const PREM = must(/premium: \{ monthly: ([\d.]+), annual: (\d+)/, readRepo("frontend/lib/pricing.ts"), "Premium prices");
const PREMIUM_M = PREM[1];
const PREMIUM_Y = PREM[2];
// Anonymous and Free readers see the scorecard's per-day entries on a delay.
const DELAY_DAYS = must(/^_FREE_DELAY_DAYS = (\d+)/m, readRepo("backend/app/routers/scorecard.py"), "_FREE_DELAY_DAYS")[1];

const PRICE_TEXT = "$" + PREMIUM_M + "/mo or $" + PREMIUM_Y + "/yr";
const PRICE_HTML = "<b>$" + PREMIUM_M + "/mo</b> or <b>$" + PREMIUM_Y + "/yr</b>";

const BG = "#0B1220", ACCENT = "#2D7DF6", FG = "#E8EDF5", MUTED = "#8A9BB4";
const DISCLOSURE =
  "Descriptive analytics, not recommendations. Not investment advice. " +
  "Past performance is not indicative of future performance. " +
  "Published by Tapeline &middot; Melbourne, Victoria, Australia.";

const discReserveFor = (w, h) => Math.round(w * 0.0215 * 1.4 * 3) + Math.round(h * 0.022);

function shell(w, h, safeTop, safeBottom, body) {
  const pad = Math.round(w * 0.078);
  const discReserve = discReserveFor(w, h);
  return [
    '<!doctype html><html><head><meta charset="utf-8"><style>',
    "*{margin:0;padding:0;box-sizing:border-box}",
    "html,body{width:" + w + "px;height:" + h + "px;background:" + BG + ";overflow:hidden}",
    'body{font-family:"Segoe UI",system-ui,sans-serif;-webkit-font-smoothing:antialiased;',
    "background:radial-gradient(120% 80% at 50% 0%, #12203A 0%, " + BG + " 62%);}",
    ".stage{position:absolute;left:0;right:0;top:" + safeTop + "px;bottom:" + (safeBottom + discReserve) + "px;",
    "padding:0 " + pad + "px;display:flex;flex-direction:column;justify-content:center;}",
    ".brand{display:flex;align-items:center;gap:" + Math.round(w * 0.017) + "px;margin-bottom:" + Math.round(h * 0.032) + "px}",
    ".dot{width:" + Math.round(w * 0.05) + "px;height:" + Math.round(w * 0.011) + "px;border-radius:99px;background:" + ACCENT + "}",
    ".wm{color:" + FG + ";font-size:" + Math.round(w * 0.031) + "px;font-weight:600;letter-spacing:.01em;line-height:1.4}",
    "h1{color:#fff;font-size:" + Math.round(w * 0.080) + "px;line-height:1.11;font-weight:700;letter-spacing:-0.02em}",
    "h1 em{font-style:normal;color:" + ACCENT + "}",
    "p.sub{color:" + MUTED + ";font-size:" + Math.round(w * 0.038) + "px;line-height:1.45;margin-top:" + Math.round(h * 0.022) + "px}",
    "p.sub b{color:" + FG + ";font-weight:600}",
    ".disc{position:absolute;left:" + pad + "px;right:" + pad + "px;bottom:" + (safeBottom + Math.round(h * 0.012)) + "px;",
    "color:#6B7C95;font-size:" + Math.round(w * 0.0215) + "px;line-height:1.4}",
    ".frame{overflow:hidden;border-radius:" + Math.round(w * 0.022) + "px;border:1px solid #1E2C44;background:#141414;",
    "box-shadow:0 " + Math.round(h * 0.018) + "px " + Math.round(h * 0.045) + "px rgba(0,0,0,.55)}",
    ".cta{display:inline-block;background:" + ACCENT + ";color:#fff;font-weight:600;",
    "font-size:" + Math.round(w * 0.037) + "px;padding:" + Math.round(w * 0.026) + "px " + Math.round(w * 0.052) + "px;border-radius:99px}",
    ".kv{color:" + FG + ";font-size:" + Math.round(w * 0.036) + "px;line-height:1.7}",
    ".kv b{color:#fff}",
    "</style></head><body>",
    body,
    '<div class="disc">' + DISCLOSURE + "</div></body></html>",
  ].join("\n");
}
const brand = (style) => '<div class="brand"' + (style ? ' style="' + style + '"' : "") +
  '><div class="dot"></div><div class="wm">Tapeline</div></div>';
const stage = (inner) => '<div class="stage">' + brand() + inner + "</div>";

const SRC_W = 1440;
// Long cuts show the whole score panel. Fit by width AND height: width-only
// fitting overflowed the stage on 1:1 and on the 40%-clear 9:16, pushing the
// frame into the top UI band and onto the disclosure. 265px is the brand row
// plus a two-line caption.
const PANEL = { x: 232, y: 268, w: 976, h: 572 };
function crop(w, inner) {
  const stageW = w - 2 * Math.round(w * 0.078);
  const k = Math.min(stageW / PANEL.w, (inner - 265) / PANEL.h);
  return frameHtml(PANEL, k, "");
}
function frameHtml(region, k, style, fw, fh) {
  return '<div class="frame" style="' + style + "width:" + (fw || Math.round(region.w * k)) + "px;height:" + (fh || Math.round(region.h * k)) + 'px">' +
    '<img src="file:///' + OUTU + '/shot-ticker.png" style="display:block;width:' + Math.round(SRC_W * k) +
    "px;margin-top:-" + Math.round(region.y * k) + "px;margin-left:-" + Math.round(region.x * k) + 'px"></div>';
}

// ---------------------------------------------------------------------------
// LONG-CUT SCENES: { id, base, screen(w,h,inner) -> inner HTML, vo }
// Spoken lines are short on purpose; the screen carries the detail.
// ---------------------------------------------------------------------------
const PROOF = {
  id: "03-proof", base: 3.4,
  screen: (w, h, inner) => crop(w, inner) + '<p class="sub">A real ticker page: the score, the six factors behind it, and the data confidence.</p>',
  vo: "A real ticker page. The score, and the six factors behind it.",
};
// "$0 today" never travels without "card required", on screen or in a headline.
const MONEY = {
  id: "05-money", base: 3.6,
  screen: () => "<h1><em>$0 today.</em><br>Card required.</h1>" +
    '<p class="sub">' + TRIAL_DAYS + "-day Premium trial, then " + PRICE_HTML + ", the plan you choose. " +
    "The exact first-charge date is shown before you confirm. Cancel in one click.</p>",
  vo: "The trial takes a card, charges nothing on day one, and shows the charge date before you confirm. One click cancels.",
};
// Was "needs no account and no card" -- true of the scorecard, but one scene
// after the card-required trial it reads as a card-free trial.
const CTA = {
  id: "06-cta", base: 3.2,
  screen: (w, h) => '<h1 style="font-size:' + Math.round(w * 0.068) + 'px">Read the record<br>before you sign up.</h1>' +
    '<p class="sub">The public scorecard needs no account.</p>' +
    '<div class="kv" style="margin-top:' + Math.round(h * 0.024) + 'px">Premium ' + PRICE_HTML + "</div>" +
    '<div style="margin-top:' + Math.round(h * 0.028) + 'px"><span class="cta">tapeline.io/scorecard</span></div>',
  vo: "Read the record first. Tapeline dot I O. Not investment advice.",
};
const SENTENCE_SUB = '<p class="sub">Descriptive language only &mdash; what the factors measured, never what to do about it.</p>';

const LONG = {
  b: [
    { id: "01-hook", base: 2.6,
      screen: () => "<h1>Every stock screener<br>hands you <em>500 filters</em><br>and a blank stare.</h1>",
      vo: "Every screener hands you five hundred filters, and a blank stare." },
    { id: "02-turn", base: 2.6,
      screen: () => "<h1>Tapeline hands you<br><em>one number.</em></h1>" +
        '<p class="sub">Six named factors, one 0&ndash;100 composite, re-scored through the US session.</p>',
      vo: "Tapeline hands you one number." },
    PROOF,
    { id: "04-sentence", base: 2.8,
      screen: () => "<h1>And <em>one plain sentence</em><br>saying what moved it.</h1>" + SENTENCE_SUB,
      vo: "Plus one plain sentence on what moved it." },
    MONEY, CTA,
  ],
  d: [
    { id: "01-hook", base: 2.8,
      screen: () => "<h1>Swing traders don't<br>need <em>more ideas.</em></h1>" +
        '<p class="sub">Forty tickers on the watchlist by Sunday night, and no consistent way to rank them.</p>',
      vo: "Swing traders don't need more ideas." },
    { id: "02-turn", base: 2.8,
      screen: () => "<h1>They need <em>one number</em><br>they can compare.</h1>" +
        '<p class="sub">Six named factors, one 0&ndash;100 composite, re-scored through the US session.</p>',
      vo: "They need one number to rank the watchlist by." },
    PROOF,
    { id: "04-sentence", base: 2.8,
      screen: () => "<h1>Plus <em>one plain sentence</em><br>saying what moved it.</h1>" + SENTENCE_SUB,
      vo: "Plus one plain sentence on what moved it." },
    MONEY, CTA,
  ],
  // REWRITTEN 2026-09-14. The 2026-09-11 cut said "We publish every day.
  // Including the bad ones.", "never re-ranked, back-filled or removed",
  // "each session's top ten is written down when it prints" and "the score in
  // the archive is the one on the page". None of that is true: the record has
  // US trading days with no top ten, and recorded values were corrected after
  // the fact (both dated on /scorecard). What IS true is below, with no figures.
  e: [
    // Was "Every scanner shows you its good weeks." -- false: Zacks has
    // published a record for decades. Now a truism, not a competitor claim.
    { id: "01-hook", base: 2.8,
      screen: () => "<h1>Anyone can show you<br>their <em>good weeks.</em></h1>",
      vo: "Anyone can show you their good weeks." },
    { id: "02-turn", base: 3.2,
      screen: () => "<h1>Our scorecard shows<br>the <em>misses</em> too.</h1>" +
        '<p class="sub">Top-ten scores by date, with the following session&rsquo;s price move and SPY&rsquo;s where recorded.</p>',
      vo: "Our public scorecard shows the misses too." },
    PROOF,
    { id: "04-sentence", base: 3.4,
      screen: (w) => '<h1 style="font-size:' + Math.round(w * 0.07) + 'px">Gaps and corrections<br>are <em>dated</em> on the page.</h1>' +
        '<p class="sub">Read it before you pay us anything. It needs no account. Without Pro or Premium, entries show on a ' +
        DELAY_DAYS + "-day delay.</p>",
      vo: "Gaps and corrections are dated on the page." },
    MONEY, CTA,
  ],
};

// ---------------------------------------------------------------------------
// <=15 s CUTS: hook over a MOVING product frame -> money -> CTA.
// Frame 1 is the product screenshot, already in motion (a slow push-in), with
// the hook and the brand on it. Meta: 6-15 s performs better, key message and
// brand in the first 3 s, motion or a compelling visual in frame 1.
// ---------------------------------------------------------------------------
const MONEY15 = {
  id: "02-money", base: 4.6,
  screen: (w, h) => '<h1 style="font-size:' + Math.round(w * 0.074) + 'px"><em>$0 today.</em><br>Card required.</h1>' +
    '<div class="kv" style="margin-top:' + Math.round(h * 0.02) + 'px">' + TRIAL_DAYS + "-day Premium trial, then<br>" +
    PRICE_HTML + ", the plan you choose.<br><b>Cancel in one click.</b></div>" +
    '<p class="sub">The exact first-charge date is shown before you confirm.</p>',
  vo: "The trial takes a card and charges nothing today. One click cancels.",
};
const CTA15 = {
  id: "03-cta", base: 3.0,
  screen: (w, h) => '<h1 style="font-size:' + Math.round(w * 0.068) + 'px">Read the record<br>before you sign up.</h1>' +
    '<p class="sub">The public scorecard needs no account.</p>' +
    '<div style="margin-top:' + Math.round(h * 0.03) + 'px"><span class="cta">tapeline.io/scorecard</span></div>',
  vo: "Tapeline dot I O. Not investment advice.",
};
const SHORT = {
  b: [
    // No "every screener" here: a question about the experience, not a claim
    // about every competitor.
    { id: "01-hook", base: 3.4, motion: true,
      head: "<em>500 filters</em><br>and a blank stare?",
      sub: "Tapeline hands you one number.",
      vo: "Five hundred filters and a blank stare? Tapeline hands you one number." },
    MONEY15, CTA15,
  ],
  d: [
    { id: "01-hook", base: 3.4, motion: true,
      head: "Swing traders don't<br>need <em>more ideas.</em>",
      sub: "They need one number per ticker.",
      vo: "Swing traders don't need more ideas. They need one number per ticker." },
    MONEY15, CTA15,
  ],
  e: [
    { id: "01-hook", base: 3.4, motion: true,
      head: "Anyone can show<br>their <em>good weeks.</em>",
      sub: "Our scorecard shows the misses too.",
      vo: "Anyone can show their good weeks. Our scorecard shows the misses too." },
    MONEY15, CTA15,
  ],
};

// The hook scene of a short cut is laid out absolutely: the product frame's
// pixel rectangle has to be known, because ffmpeg overlays the moving crop
// exactly on top of it. Text is anchored to the frame, so a font-metric
// difference moves the text, never the overlay.
const CROP15 = { x: 232, y: 268, w: 976, h: 460 }; // score, radar and the plain sentence
function hookLayout(s, w, h, sTop, sBot) {
  const pad = Math.round(w * 0.078);
  const stageW = w - 2 * pad;
  const inner = h - sBot - discReserveFor(w, h) - sTop;
  const brandH = Math.round(w * 0.031 * 1.4);
  const brandGap = Math.round(h * 0.012);
  const h1Fs = Math.round(w * 0.066);
  const h1H = Math.round(2 * h1Fs * 1.11);
  const subFs = Math.round(w * 0.040);
  const subH = Math.round(subFs * 1.45);
  const g1 = Math.round(h * 0.016), g2 = Math.round(h * 0.014);
  const fixed = brandH + brandGap + h1H + g1 + g2 + subH;
  const k = Math.min(stageW / CROP15.w, (inner - fixed) / CROP15.h);
  // Even sizes: zoompan rounds its output to even dimensions, and alphamerge
  // refuses a mask one pixel off.
  const fw = 2 * Math.round(CROP15.w * k / 2), fh = 2 * Math.round(CROP15.h * k / 2);
  const y0 = sTop + Math.max(0, Math.round((inner - fixed - fh) / 2));
  const fy = y0 + brandH + brandGap + h1H + g1;
  const body =
    '<div style="position:absolute;left:' + pad + "px;right:" + pad + "px;bottom:" + (h - fy + g1) + 'px">' +
    brand("margin-bottom:" + brandGap + "px") + '<h1 style="font-size:' + h1Fs + 'px">' + s.head + "</h1></div>" +
    frameHtml(CROP15, k, "position:absolute;left:" + pad + "px;top:" + fy + "px;", fw, fh) +
    '<p class="sub" style="position:absolute;left:' + pad + "px;right:" + pad + "px;top:" + (fy + fh + g2) +
    "px;margin:0;font-size:" + subFs + 'px">' + s.sub + "</p>";
  return { html: shell(w, h, sTop, sBot, body), rect: { x: pad, y: fy, w: fw, h: fh }, radius: Math.round(w * 0.022) };
}

const RATIOS = [
  // 9:16: top 270px (14%) and bottom 770px (40%) clear -- Meta's Reels rule
  // for ads with a disclaimer. Sides 84px (7.8%) against Meta's 6%.
  { fmt: "9x16", w: 1080, h: 1920, sTop: 270, sBot: 770 },
  { fmt: "4x5", w: 1080, h: 1350, sTop: 100, sBot: 160 },
  { fmt: "1x1", w: 1080, h: 1080, sTop: 90, sBot: 140 },
];

// ---------------------------------------------------------------------------
// TEXT GATES
// ---------------------------------------------------------------------------
function htmlToText(html) {
  return html
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<img[^>]*>/gi, " ")
    .replace(/<\/(?:h1|p|div)>/gi, " | ")
    .replace(/<[^>]+>/g, "")
    .replace(/&mdash;/g, "\u2014").replace(/&ndash;/g, "\u2013").replace(/&rsquo;/g, "\u2019")
    .replace(/&middot;/g, "\u00b7").replace(/&amp;/g, "&")
    .replace(/\s*\|\s*(\|\s*)*/g, " | ")
    .replace(/\s+/g, " ")
    .replace(/^\s*\|\s*|\s*\|\s*$/g, "")
    .trim();
}
function onScreenText(s) {
  if (s.motion) return htmlToText("<h1>" + s.head + "</h1><p>" + s.sub + "</p>");
  return htmlToText(s.screen(1080, 1920, 740));
}
// Spoken forms that read badly as captions. Same words, written the way the
// screen writes them.
const CAPTION_FORMS = [
  [/Tapeline dot I O/g, "tapeline.io"],
  [/\bFive hundred\b/g, "500"],
  [/\bfive hundred\b/g, "500"],
];
const captionForm = (t) => CAPTION_FORMS.reduce((acc, [re, to]) => acc.replace(re, to), t);

// Record claims the --ads linter does not know about. The record has days
// with no top ten and dated corrections, so none of these may appear.
const RECORD_CLAIMS = [
  // copy-compliance-allow ad-trading-vocabulary -- a detector that rejects this word in ad lines; it is not copy
  /\bevery\s+(?:single\s+)?(?:day|session|trading\s+day|pick|entry|entries|list|top[-\s]?(?:ten|10))\b/i,
  /\beach\s+(?:day|session|trading\s+day)(?:['\u2019]s)?\b/i,
  /\bdaily\b/i,
  /\bfrozen\b/i,
  /\blogged\b/i,
  /\bappend[-\s]?only\b/i,
  /\bimmutable\b/i,
  /\b(?:never|not)\s+(?:been\s+)?(?:re-?ranked|back-?filled|removed|edited|deleted|changed|touched|rewritten)\b/i,
  /\bcomplete\s+(?:record|archive|history)\b/i,
  /\bwritten\s+down\s+when\b/i,
  /\bwhen\s+it\s+prints\b/i,
  /\bnothing\s+(?:is\s+|gets\s+)?(?:deleted|removed|edited)\b/i,
  /\bwe\s+publish\s+every\b/i,
  /\bscore\s+in\s+the\s+archive\b/i,
  // "each next to the following session's price move" says every entry has
  // one. On 2026-09-14, 34 entries older than the publication delay had no
  // move and no SPY figure on the page, so the line says "where recorded".
  /\beach\s+(?:next\s+to|beside|alongside|with|paired)\b/i,
  // No figures from the record, in any concept.
  /\d\s*%/,
  /\bhit\s+rate\b/i,
  /\balpha\b/i,
  /\b(?:beat|beats|outperform\w*)\b/i,
];
function checkRecordClaims(label, text) {
  for (const re of RECORD_CLAIMS) {
    const m = re.exec(text);
    if (m) throw new Error("RECORD CLAIM in " + label + ': "' + m[0] + '" in: ' + text);
  }
}

// A trial length typed into a string in this file is the bug #737 left behind.
function checkNoTypedTrialLength() {
  // Line comments only: this file has no block comments, and a glob such as
  // "voiceover/*.mp4" in a comment would otherwise open one and hide real code.
  const src = readFileSync(fileURLToPath(import.meta.url), "utf8")
    .split("\n")
    .filter((l) => !/^\s*\/\//.test(l))
    .map((l) => l.replace(/\s\/\/\s.*$/, ""))
    .join("\n");
  const m = /\b(?:7|14|21|30)[-\s]?days?\b/i.exec(src);
  if (m) throw new Error('hard-coded trial length "' + m[0] + '" in build3.mjs -- use TRIAL_DAYS');
}

// Meta text fields. The opener carries the card, $0, price, interval and
// cancel terms inside 125 characters, because Meta truncates primary text
// there and its subscription policy wants price and interval clearly shown.
// The billing period after the trial is an open founder decision, so both
// plans are named.
const OPENER = TRIAL_DAYS + "-day Premium trial: card required, $0 today, then " + PRICE_TEXT +
  ", the plan you choose. Cancel in one click.";
const META = {
  d: {
    name: "D - Swing traders (VO)",
    primary: OPENER + " Swing traders don't need more ideas. They need a consistent way to rank the forty already on " +
      "the watchlist. Tapeline puts one 0-100 score on each, from six named factors, with one plain sentence on " +
      "what moved it. The first-charge date is shown before you confirm.",
    headline: "One number per ticker.",
    description: "Not investment advice.",
  },
  e: {
    name: "E - The record (VO)",
    primary: OPENER + " Anyone can show you their good weeks. Tapeline's public scorecard lists top-ten scores by " +
      "date, with the following session's price move and SPY's where recorded, misses included. Gaps and corrections " +
      "are dated on the page. Reading it needs no account. Without Pro or Premium, entries show on a " + DELAY_DAYS +
      "-day delay.",
    headline: "Read the record first.",
    description: "Not investment advice.",
  },
  b: {
    name: "B2 - money question (VO cut of concept B)",
    primary: OPENER + " The exact first-charge date is shown before you confirm. The public scorecard needs no " +
      "account to read.",
    headline: "$0 today. Card required.",
    description: "Not investment advice.",
  },
};
function checkMetaFields() {
  for (const [key, m] of Object.entries(META)) {
    const first = m.primary.slice(0, 125);
    for (const need of ["$" + PREMIUM_M, "/mo", "$" + PREMIUM_Y, "/yr", "card required", "$0 today", "one click"]) {
      if (!first.toLowerCase().includes(need.toLowerCase())) {
        throw new Error("META " + key + ': "' + need + '" is not inside the first 125 characters of the primary text');
      }
    }
    if (m.headline.length > 40) throw new Error("META " + key + " headline is " + m.headline.length + " chars (max 40)");
    if (m.description && m.description.length > 25) throw new Error("META " + key + " description is " + m.description.length + " chars (max 25)");
    if (/\$0/.test(m.headline) && !/card required/i.test(m.headline)) {
      throw new Error("META " + key + ' headline says "$0" without "card required"');
    }
  }
}

function lintAds(file) {
  try {
    execFileSync("node", [join(REPO, "scripts/lint-copy-compliance.mjs"), "--ads", file], { stdio: "pipe" });
  } catch (e) {
    throw new Error("AD LINT FAILED on " + file + " -- nothing rendered.\n" + String(e.stdout || "") + String(e.stderr || ""));
  }
}

function writeScript() {
  const lines = [
    "# Voice-over script and on-screen text",
    "",
    "Generated by `build3.mjs` from the strings it renders, then linted with",
    "`lint-copy-compliance.mjs --ads` and checked for record claims before any audio",
    "or video is made. Edit `build3.mjs`, not this file.",
    "",
    "Trial length, prices and the scorecard delay are read from",
    "`frontend/lib/trial.ts`, `frontend/lib/pricing.ts` and",
    "`backend/app/routers/scorecard.py` at build time.",
    "",
  ];
  const wordCount = (t) => t.split(/\s+/).filter(Boolean).length;
  for (const key of ["b", "d", "e"]) {
    lines.push("## " + (key === "b" ? "B2 (concept B)" : key.toUpperCase()), "");
    for (const [label, scenes] of [["Long cut", LONG[key]], ["15 s cut", SHORT[key]]]) {
      const words = scenes.reduce((a, s) => a + wordCount(s.vo), 0);
      lines.push("### " + label + " (" + words + " spoken words)", "");
      for (const s of scenes) {
        lines.push("**" + s.id + "**", "", "- Spoken: " + s.vo, "- Caption: " + captionForm(s.vo),
          "- On screen: " + onScreenText(s), "");
      }
    }
  }
  lines.push("## Disclosure line (every frame)", "", htmlToText(DISCLOSURE), "");
  const file = join(OUT, "vo-script.md");
  writeFileSync(file, lines.join("\n"), "utf8");
  return file;
}

function writeMetaCopy() {
  const L = [
    "# Meta ad copy -- relaunch 2026-09 (regenerated 2026-09-14)",
    "",
    "Generated by `build3.mjs`; edit the `META` object there, not this file. Trial",
    "length and prices are read from `frontend/lib/trial.ts` and `frontend/lib/pricing.ts`.",
    "",
    "Rules the build enforces:",
    "",
    "- Meta's subscription-services policy wants price and billing interval clearly shown in the",
    "  ad. Primary text is truncated at about 125 characters, so the card, $0, price, interval and",
    "  cancel terms all sit inside the first 125 characters of every primary text.",
    "- Both plans are named, because the billing period after the trial is an open founder",
    "  decision and checkout accepts either.",
    "- Headline <= 40 characters; description <= 25. \"$0 today\" never appears without \"card",
    "  required\".",
    "- Everything below passes `node scripts/lint-copy-compliance.mjs --ads` and the build's record-claim check.",
    "",
    "Each ad carries both cuts of its concept in all three ratios, with one caption file per video.",
    "See `README.md` for which file goes to which placement.",
    "",
  ];
  const assetList = (key) => ["voiceover", "voiceover-15s"].flatMap((dir) => RATIOS.map((r) => {
    const base = videoName(dir, key, r.fmt);
    return "  - `" + dir + "/" + base + ".mp4` + `" + dir + "/" + base + ".en_US.srt`";
  }));
  for (const key of ["d", "e", "b"]) {
    const m = META[key];
    const priceAt = m.primary.indexOf("$" + PREMIUM_M) + 1;
    L.push("## " + m.name, "");
    L.push("| Field | Characters | Text |", "|---|---|---|");
    L.push("| Primary text | " + m.primary.length + " total; price at character " + priceAt +
      "; card, $0, price, interval and cancel all within the first " + OPENER.length + " | " + m.primary + " |");
    L.push("| Headline | " + m.headline.length + " | " + m.headline + " |");
    L.push("| Description | " + (m.description ? m.description.length : 0) + " | " + (m.description || "(omit)") + " |");
    L.push("", "Videos:", "", ...assetList(key), "");
  }
  const file = join(OUT, "meta-copy-2026-09.md");
  writeFileSync(file, L.join("\n"), "utf8");
  return file;
}

function videoName(dir, key, fmt) {
  return "tapeline-concept-" + key + (dir === "voiceover-15s" ? "-vo15-" : "-vo-") + fmt;
}

function gates() {
  checkNoTypedTrialLength();
  checkMetaFields();
  for (const key of ["b", "d", "e"]) {
    for (const [label, scenes] of [["long", LONG[key]], ["15s", SHORT[key]]]) {
      for (const s of scenes) {
        checkRecordClaims(key + "/" + label + "/" + s.id + " spoken", s.vo);
        checkRecordClaims(key + "/" + label + "/" + s.id + " on screen", onScreenText(s));
      }
    }
    for (const f of ["primary", "headline", "description"]) checkRecordClaims("META " + key + " " + f, META[key][f] || "");
    const words = SHORT[key].reduce((a, s) => a + s.vo.split(/\s+/).filter(Boolean).length, 0);
    if (words > SHORT_MAX_WORDS + 3) throw new Error("15 s cut " + key + " has " + words + " spoken words");
  }
  lintAds(writeScript());
  lintAds(writeMetaCopy());
}

// ---------------------------------------------------------------------------
// AUDIO, CAPTIONS, PICTURE
// ---------------------------------------------------------------------------
function probeSeconds(file) {
  let err = "";
  try { execFileSync(ffmpeg, ["-i", file], { stdio: ["ignore", "ignore", "pipe"] }); }
  catch (e) { err = String(e.stderr || ""); }
  const m = /Duration: (\d+):(\d+):([\d.]+)/.exec(err);
  if (!m) throw new Error("cannot probe " + file);
  return +m[1] * 3600 + +m[2] * 60 + +m[3];
}
const toFrames = (s) => Math.ceil(s * FPS - 1e-6);

function parseSrt(text) {
  const ts = (t) => { const [hh, mm, rest] = t.split(":"); const [ss, ms] = rest.split(","); return +hh * 3600 + +mm * 60 + +ss + +ms / 1000; };
  return text.replace(/\r/g, "").split(/\n\n+/).map((b) => b.trim()).filter(Boolean).map((b) => {
    const rows = b.split("\n");
    const [a, z] = rows[1].split(" --> ");
    return { start: ts(a.trim()), end: ts(z.trim()), text: rows.slice(2).join(" ").trim() };
  });
}

// 1. Voice first, once per concept and cut (audio does not depend on ratio).
function voice(cut, key, scenes) {
  const dir = join(OUT, "work", cut, key, "vo");
  mkdirSync(dir, { recursive: true });
  return scenes.map((s) => {
    const mp3 = join(dir, s.id + ".mp3");
    const srt = join(dir, s.id + ".srt");
    run(TTS, ["--voice", VOICE, "--rate=" + RATE, "--text", s.vo, "--write-media", mp3, "--write-subtitles", srt],
      "tts " + cut + "/" + key + "/" + s.id);
    const dur = probeSeconds(mp3);
    const frames = toFrames(Math.max(s.base, LEAD + dur + TAIL));
    let sentences = parseSrt(readFileSync(srt, "utf8"));
    // Captions must be verbatim: if the service's sentence text does not
    // reassemble into the script line, fall back to the script line.
    const norm = (t) => t.replace(/\s+/g, " ").trim();
    if (norm(sentences.map((x) => x.text).join(" ")) !== norm(s.vo)) {
      sentences = [{ start: 0, end: dur, text: s.vo }];
    }
    return { ...s, mp3, dur: +dur.toFixed(2), frames, hold: frames / FPS, sentences };
  });
}

// 2. One audio track per concept and cut: each line delayed by LEAD, padded to its hold.
function audioTrack(cut, key, timed) {
  const dir = join(OUT, "work", cut, key, "vo");
  const segs = timed.map((s, i) => {
    const wav = join(dir, "seg-" + i + ".wav");
    run(ffmpeg, ["-y", "-i", s.mp3,
      "-af", "adelay=" + Math.round(LEAD * 1000) + ",apad=whole_dur=" + s.hold.toFixed(6),
      "-t", s.hold.toFixed(6), "-ar", "48000", "-ac", "1", wav], "seg " + key + "/" + i);
    return wav;
  });
  const list = join(dir, "segs.txt");
  writeFileSync(list, segs.map((f) => "file '" + f.replace(/\\/g, "/") + "'").join("\n") + "\n");
  const track = join(dir, "track.wav");
  const total = timed.reduce((a, s) => a + s.hold, 0);
  // -16 LUFS integrated is the social-video norm; true-peak ceiling below 0.
  run(ffmpeg, ["-y", "-f", "concat", "-safe", "0", "-i", list,
    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:d=0.08,afade=t=out:st=" + (total - 0.3).toFixed(2) + ":d=0.3",
    "-ar", "48000", "-ac", "2", "-t", total.toFixed(6), track], "track " + key);
  return track;
}

// 3. Verbatim captions on the video's clock: sentence timings from the TTS
// service, long sentences split into cues of at most two 42-character lines.
function srtStamp(t) {
  const ms = Math.max(0, Math.round(t * 1000));
  const p = (n, l = 2) => String(n).padStart(l, "0");
  return p(Math.floor(ms / 3600000)) + ":" + p(Math.floor(ms / 60000) % 60) + ":" + p(Math.floor(ms / 1000) % 60) + "," + p(ms % 1000, 3);
}
const CAP_LINE = 42;
function greedyLines(text, max) {
  const lines = [];
  let cur = "";
  for (const word of text.split(" ")) {
    if (cur && (cur + " " + word).length > max) { lines.push(cur); cur = word; } else { cur = cur ? cur + " " + word : word; }
  }
  if (cur) lines.push(cur);
  return lines;
}
// One cue = at most two lines. Break a sentence at its clauses first, then
// balance each cue's two lines, preferring a break after punctuation, so a
// line never ends on "before" with "you confirm." stranded in the next cue.
function cueTexts(sentence) {
  if (sentence.length <= CAP_LINE) return [sentence];
  const cues = [];
  let cur = "";
  for (const part of sentence.split(/(?<=[,;?])\s+/)) {
    const cand = cur ? cur + " " + part : part;
    if (cur && cand.length > 2 * CAP_LINE) { cues.push(cur); cur = part; } else { cur = cand; }
  }
  if (cur) cues.push(cur);
  return cues.flatMap((c) => {
    if (c.length <= CAP_LINE) return [c];
    let best = null;
    for (let i = 0; i < c.length; i++) {
      if (c[i] !== " ") continue;
      const l = c.slice(0, i), r = c.slice(i + 1);
      if (l.length > CAP_LINE || r.length > CAP_LINE) continue;
      const score = Math.abs(l.length - r.length) - (/[,;.?]$/.test(l) ? 14 : 0);
      if (!best || score < best.score) best = { score, text: l + "\n" + r };
    }
    if (best) return [best.text];
    const lines = greedyLines(c, CAP_LINE);
    const out = [];
    for (let j = 0; j < lines.length; j += 2) out.push(lines.slice(j, j + 2).join("\n"));
    return out;
  });
}
function captions(timed) {
  const cues = [];
  let t0 = 0;
  for (const s of timed) {
    const sceneEnd = t0 + s.hold - 0.05;
    s.sentences.forEach((sent, i) => {
      const start = t0 + LEAD + sent.start;
      const last = i === s.sentences.length - 1;
      const end = Math.min(t0 + LEAD + (last ? s.dur : sent.end), sceneEnd);
      const groups = cueTexts(captionForm(sent.text));
      const chars = groups.map((g) => g.length);
      const totalChars = chars.reduce((a, c) => a + c, 0);
      let cs = start;
      groups.forEach((g, j) => {
        const ce = j === groups.length - 1 ? end : cs + (end - start) * (chars[j] / totalChars);
        cues.push({ start: cs, end: ce, text: g });
        cs = ce;
      });
    });
    t0 += s.hold;
  }
  return cues.map((c, i) => (i + 1) + "\n" + srtStamp(c.start) + " --> " + srtStamp(c.end) + "\n" + c.text + "\n").join("\n");
}

// 4. Picture, per ratio, held to the voice's timings, then muxed.
function chromeShot(htmlFile, png, w, h, label) {
  run(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars",
    "--force-device-scale-factor=1", "--window-size=" + w + "," + h,
    "--virtual-time-budget=3000", "--screenshot=" + png, "file:///" + htmlFile.replace(/\\/g, "/")], label);
  if (!existsSync(png)) throw new Error("render failed: " + label);
}

let SRC15 = null;
function productSource() {
  if (SRC15) return SRC15;
  // Crop once, then upscale 3x: the push-in samples the upscaled source, so a
  // whole-pixel step in ffmpeg's zoompan is a third of a pixel on the page.
  SRC15 = join(OUT, "work", "product-3x.png");
  mkdirSync(join(OUT, "work"), { recursive: true });
  run(ffmpeg, ["-y", "-i", join(OUT, "shot-ticker.png"), "-vf",
    "crop=" + CROP15.w + ":" + CROP15.h + ":" + CROP15.x + ":" + CROP15.y + ",scale=" + CROP15.w * 3 + ":" + CROP15.h * 3 + ":flags=lanczos",
    "-frames:v", "1", "-update", "1", SRC15], "product source");
  return SRC15;
}
function roundedMask(file, w, h, r) {
  const e = "clip(255*(" + r + "+0.5-hypot(max(max(" + r + "-X\\,X-(W-1-" + r + "))\\,0)\\,max(max(" + r + "-Y\\,Y-(H-1-" + r + "))\\,0)))\\,0\\,255)";
  run(ffmpeg, ["-y", "-f", "lavfi", "-i", "color=black:s=" + w + "x" + h, "-vf", "format=gray,geq=lum=" + e,
    "-frames:v", "1", "-update", "1", file], "mask " + w + "x" + h);
}

function render(cut, key, timed, track, r) {
  const { fmt, w, h, sTop, sBot } = r;
  const dir = join(OUT, "work", cut, key, fmt);
  mkdirSync(dir, { recursive: true });
  const inputs = [];
  const graph = [];
  const labels = [];
  timed.forEach((s, i) => {
    const htmlFile = join(dir, s.id + ".html");
    const png = join(dir, s.id + ".png");
    let layout = null;
    if (s.motion) {
      layout = hookLayout(s, w, h, sTop, sBot);
      writeFileSync(htmlFile, layout.html, "utf8");
    } else {
      const inner = h - sTop - sBot - discReserveFor(w, h);
      writeFileSync(htmlFile, shell(w, h, sTop, sBot, stage(s.screen(w, h, inner))), "utf8");
    }
    chromeShot(htmlFile, png, w, h, "chrome " + cut + "/" + key + "/" + fmt + "/" + s.id);
    const loop = (f) => { inputs.push("-loop", "1", "-framerate", String(FPS), "-t", (s.hold + 0.5).toFixed(3), "-i", f); return inputs.filter((x) => x === "-i").length - 1; };
    const base = loop(png);
    if (layout) {
      // Motion: the product crop pushes in inside the frame's border, clipped
      // to its rounded corners. Frame 1 is zoom 1.0, i.e. the still itself.
      const rx = layout.rect.x + 1, ry = layout.rect.y + 1, iw = layout.rect.w - 2, ih = layout.rect.h - 2;
      const mask = join(dir, "mask.png");
      roundedMask(mask, iw, ih, layout.radius - 1);
      const src = loop(productSource());
      const m = loop(mask);
      const N = s.frames - 1;
      graph.push(
        "[" + src + ":v]zoompan=z='1+0.15*(1-pow(1-on/" + N + "\\,2))':x='(iw-iw/zoom)*0.10':y='(ih-ih/zoom)*0.40'" +
          ":d=1:s=" + iw + "x" + ih + ":fps=" + FPS + ",scale=" + iw + ":" + ih + ",setsar=1,format=rgba[z" + i + "]",
        "[" + m + ":v]scale=" + iw + ":" + ih + ",format=gray,setsar=1[m" + i + "]",
        "[z" + i + "][m" + i + "]alphamerge[zm" + i + "]",
        "[" + base + ":v]fps=" + FPS + ",setsar=1,format=rgba[b" + i + "]",
        "[b" + i + "][zm" + i + "]overlay=" + rx + ":" + ry + ":shortest=1,format=yuv420p,trim=end_frame=" + s.frames + ",setpts=N/" + FPS + "/TB[v" + i + "]",
      );
    } else {
      graph.push("[" + base + ":v]fps=" + FPS + ",setsar=1,format=yuv420p,trim=end_frame=" + s.frames + ",setpts=N/" + FPS + "/TB[v" + i + "]");
    }
    labels.push("[v" + i + "]");
  });
  graph.push(labels.join("") + "concat=n=" + timed.length + ":v=1:a=0[v]");
  const totalFrames = timed.reduce((a, s) => a + s.frames, 0);
  const total = totalFrames / FPS;
  const silent = join(dir, "silent.mp4");
  run(ffmpeg, ["-y", ...inputs, "-filter_complex", graph.join(";"), "-map", "[v]",
    "-frames:v", String(totalFrames), "-r", String(FPS), "-c:v", "libx264", "-preset", "slow", "-crf", "20",
    "-pix_fmt", "yuv420p", silent], "video " + cut + "/" + key + "/" + fmt);
  const outDir = join(OUT, cut === "short" ? "voiceover-15s" : "voiceover");
  mkdirSync(outDir, { recursive: true });
  const name = videoName(cut === "short" ? "voiceover-15s" : "voiceover", key, fmt);
  const mp4 = join(outDir, name + ".mp4");
  run(ffmpeg, ["-y", "-i", silent, "-i", track,
    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
    "-t", total.toFixed(3), "-movflags", "+faststart", mp4], "mux " + cut + "/" + key + "/" + fmt);
  const srt = captions(timed);
  const flat = (t) => t.replace(/\s+/g, " ").trim();
  if (flat(parseSrt(srt).map((c) => c.text).join(" ")) !== flat(timed.map((s) => captionForm(s.vo)).join(" "))) {
    throw new Error(name + ": captions are not verbatim to the voice-over");
  }
  writeFileSync(join(outDir, name + ".en_US.srt"), srt, "utf8");
  if (cut === "short" && total > SHORT_MAX_S) throw new Error(name + " is " + total.toFixed(2) + " s (max " + SHORT_MAX_S + ")");
  return { mp4, secs: +total.toFixed(2) };
}

// 5. Probe every output and grab frame 1 plus the frame at 1.5 s, side by side.
function probe(mp4) {
  let err = "";
  try { execFileSync(ffmpeg, ["-hide_banner", "-i", mp4], { stdio: ["ignore", "ignore", "pipe"] }); }
  catch (e) { err = String(e.stderr || ""); }
  const d = /Duration: (\d+):(\d+):([\d.]+)/.exec(err);
  const v = /Stream #\S+.*Video: (\w+).*?, (\d{2,5})x(\d{2,5})[^\n]*?, ([\d.]+) fps/.exec(err);
  const a = /Stream #\S+.*Audio: (\w+)[^\n]*?(\d+) Hz/.exec(err);
  return {
    file: mp4.slice(OUT.length + 1).replace(/\\/g, "/"),
    duration_s: d ? +(+d[1] * 3600 + +d[2] * 60 + +d[3]).toFixed(2) : null,
    video: v ? v[1] + " " + v[2] + "x" + v[3] + " @" + v[4] + "fps" : null,
    audio: a ? a[1] + " " + a[2] + "Hz" : null,
  };
}
function grabFrames(mp4, outPng) {
  run(ffmpeg, ["-y", "-i", mp4, "-filter_complex",
    "[0:v]split=2[a][b];[a]select='eq(n\\,0)',scale=iw/2:-1[f1];[b]select='eq(n\\,45)',scale=iw/2:-1[f2];[f1][f2]hstack=inputs=2",
    "-frames:v", "1", "-update", "1", outPng], "grab " + mp4);
}

gates();
if (COPY_ONLY) {
  console.log("copy-only: text written and gated; nothing rendered.");
  process.exit(0);
}
// --only=short:b:9x16 (any prefix) renders a subset while iterating on layout.
const ONLY = (process.argv.find((a) => a.startsWith("--only=")) || "--only=").slice(7).split(":").filter(Boolean);
const wanted = (...parts) => ONLY.every((o, i) => parts[i] === undefined || parts[i] === o);
const report = { VOICE, RATE, TRIAL_DAYS, PREMIUM_M, PREMIUM_Y, DELAY_DAYS, cuts: {}, probes: [] };
for (const [cut, set] of [["long", LONG], ["short", SHORT]]) {
  for (const key of ["b", "d", "e"]) {
    if (!wanted(cut, key)) continue;
    const timed = voice(cut, key, set[key]);
    const track = audioTrack(cut, key, timed);
    report.cuts[cut + "/" + key] = {
      speech_s: +timed.reduce((a, s) => a + s.dur, 0).toFixed(2),
      words: timed.reduce((a, s) => a + s.vo.split(/\s+/).filter(Boolean).length, 0),
      scenes: timed.map((s) => ({ id: s.id, vo_s: s.dur, hold_s: +s.hold.toFixed(3) })),
      out: RATIOS.filter((r) => wanted(cut, key, r.fmt)).map((r) => render(cut, key, timed, track, r)),
    };
  }
}
mkdirSync(join(OUT, "check"), { recursive: true });
for (const dir of ["voiceover", "voiceover-15s"]) {
  for (const key of ["b", "d", "e"]) {
    for (const r of RATIOS) {
      if (!wanted(dir === "voiceover" ? "long" : "short", key, r.fmt)) continue;
      const mp4 = join(OUT, dir, videoName(dir, key, r.fmt) + ".mp4");
      report.probes.push(probe(mp4));
      grabFrames(mp4, join(OUT, "check", videoName(dir, key, r.fmt) + "-f1-and-1.5s.png"));
    }
  }
}
writeFileSync(join(OUT, "check", "report.json"), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
