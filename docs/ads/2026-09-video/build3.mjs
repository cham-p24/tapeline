// Voice-over cuts of concepts B, D and E — 2026-09-11.
//
// THE TIMING RULE THAT MATTERS
// ----------------------------
// The silent cuts were timed for READING: 2.6-3.4s a scene. Speech is slower.
// The first script ran 41.2s of speech (45.1s cut) for B -- 2.5x the silent
// version, far past where Reels attention holds. So the lines are short, the
// voice is generated FIRST and measured, and each scene is held for
// max(base hold, lead-in + spoken length + tail). The picture follows the
// voice, never the reverse.
//
// Scenes 05 and 06 are identical across all three concepts, sound included, so
// a difference in results is attributable to the hook.
//
// COMPLIANCE GATE: the build writes every spoken line to vo-script.md and runs
// the strict --ads linter on it BEFORE synthesising anything. What is spoken
// is therefore exactly what was checked -- a separately-maintained script file
// could drift from the strings in here.
//
// The trial length is deliberately NOT spoken. It is on screen, read from
// frontend/lib/trial.ts. A spoken number is one more place for it to go stale.
//
// Voice: en-US-AndrewNeural (Microsoft neural, via edge-tts). Local SAPI only
// offers David/Zira, which would make the ads worse than silence.

import { writeFileSync, mkdirSync, readFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import ffmpeg from "ffmpeg-static";

const OUT = process.cwd();
const OUTU = OUT.replace(/\\/g, "/");
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REPO = "C:/Project 1";
const TTS = join(OUT, "..", "ttsvenv", "Scripts", "edge-tts.exe");
const VOICE = "en-US-AndrewNeural";
const RATE = "+0%";
const LEAD = 0.15;   // voice starts just after the cut, so the cut never clips it
const TAIL = 0.50;   // breath before the next scene

// Retry + surface stderr. The first run lost a whole batch to one transient
// ffmpeg crash whose reason was invisible because stdio was "ignore"; the
// identical command exited 0 on a manual rerun.
function run(bin, args, label) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      return execFileSync(bin, args, { stdio: ["ignore", "ignore", "pipe"], maxBuffer: 64 * 1024 * 1024 });
    } catch (e) {
      if (attempt === 3) {
        throw new Error(label + " failed after 3 attempts:\n" + String(e.stderr || e.message).slice(-2500));
      }
    }
  }
}

const trialSrc = readFileSync(join(REPO, "frontend/lib/trial.ts"), "utf8");
const TRIAL_DAYS = /TRIAL_DAYS = (\d+)/.exec(trialSrc)[1];
const priceSrc = readFileSync(join(REPO, "frontend/lib/pricing.ts"), "utf8");
const PREM = /premium: \{ monthly: ([\d.]+), annual: (\d+)/.exec(priceSrc);
const PREMIUM_M = PREM[1];
const PREMIUM_Y = PREM[2];

const BG = "#0B1220", ACCENT = "#2D7DF6", FG = "#E8EDF5", MUTED = "#8A9BB4";
const DISCLOSURE =
  "Descriptive analytics, not recommendations. Not investment advice. " +
  "Past performance is not indicative of future performance. " +
  "Published by Tapeline &middot; Melbourne, Victoria, Australia.";

function shell(w, h, safeTop, safeBottom, body) {
  const pad = Math.round(w * 0.078);
  const discReserve = Math.round(w * 0.0215 * 1.4 * 3) + Math.round(h * 0.022);
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
    ".wm{color:" + FG + ";font-size:" + Math.round(w * 0.031) + "px;font-weight:600;letter-spacing:.01em}",
    "h1{color:#fff;font-size:" + Math.round(w * 0.080) + "px;line-height:1.11;font-weight:700;letter-spacing:-0.02em}",
    "h1 em{font-style:normal;color:" + ACCENT + "}",
    "p.sub{color:" + MUTED + ";font-size:" + Math.round(w * 0.038) + "px;line-height:1.45;margin-top:" + Math.round(h * 0.022) + "px}",
    ".disc{position:absolute;left:" + pad + "px;right:" + pad + "px;bottom:" + (safeBottom + Math.round(h * 0.012)) + "px;",
    "color:#6B7C95;font-size:" + Math.round(w * 0.0215) + "px;line-height:1.4}",
    ".frame{overflow:hidden;border-radius:" + Math.round(w * 0.022) + "px;border:1px solid #1E2C44;",
    "box-shadow:0 " + Math.round(h * 0.018) + "px " + Math.round(h * 0.045) + "px rgba(0,0,0,.55)}",
    ".cta{display:inline-block;background:" + ACCENT + ";color:#fff;font-weight:600;",
    "font-size:" + Math.round(w * 0.037) + "px;padding:" + Math.round(w * 0.026) + "px " + Math.round(w * 0.052) + "px;border-radius:99px}",
    ".kv{color:" + FG + ";font-size:" + Math.round(w * 0.034) + "px;line-height:1.8}",
    ".kv b{color:#fff}",
    "</style></head><body>",
    body,
    '<div class="disc">' + DISCLOSURE + "</div></body></html>",
  ].join("\n");
}
const brand = '<div class="brand"><div class="dot"></div><div class="wm">Tapeline</div></div>';

const SRC_W = 1440, PANEL_X = 232, PANEL_Y = 268, PANEL_W = 976, PANEL_H = 572;
// Fit the product frame by width AND height. Width-only fitting overflowed the
// stage on 1:1 and on the 40%-clear 9:16, pushing the frame into the top UI
// band and onto the disclosure. 265px is the brand row plus a two-line caption.
function crop(w, inner) {
  const stageW = w - 2 * Math.round(w * 0.078);
  const k = Math.min(stageW / PANEL_W, (inner - 265) / PANEL_H);
  return '<div class="frame" style="width:' + Math.round(PANEL_W * k) + 'px;height:' + Math.round(PANEL_H * k) + 'px">' +
    '<img src="file:///' + OUTU + '/shot-ticker.png" style="display:block;width:' + Math.round(SRC_W * k) +
    "px;margin-top:-" + Math.round(PANEL_Y * k) + "px;margin-left:-" + Math.round(PANEL_X * k) + 'px"></div>';
}
const stage = (inner) => '<div class="stage">' + brand + inner + "</div>";

// ---------------------------------------------------------------------------
// Scenes: { id, base, screen(w,h) -> inner HTML, vo }
// Spoken lines are short on purpose; the screen carries the detail.
// ---------------------------------------------------------------------------
const PROOF = {
  id: "03-proof", base: 3.4,
  screen: (w, h, inner) => crop(w, inner) + '<p class="sub">A real ticker page: the score, the six factors behind it, and the data confidence.</p>',
  vo: "A real ticker page. The score, and the six factors behind it.",
};
const MONEY = {
  id: "05-money", base: 3.4,
  screen: () => "<h1><em>$0 today.</em><br>The charge date<br>is on the page.</h1>" +
    '<p class="sub">' + TRIAL_DAYS + "-day Premium trial. It takes a card, charges nothing that day, and shows " +
    "the exact first-charge date before you confirm. One click cancels before then.</p>",
  vo: "The trial takes a card, charges nothing on day one, and shows the charge date before you confirm. One click cancels.",
};
const CTA = {
  id: "06-cta", base: 3.2,
  screen: (w, h) => '<h1 style="font-size:' + Math.round(w * 0.068) + 'px">Read the record<br>before you sign up.</h1>' +
    '<p class="sub">The published top-10 archive &mdash; the misses included &mdash; needs no account and no card.</p>' +
    '<div class="kv" style="margin-top:' + Math.round(h * 0.024) + 'px">Premium <b>$' + PREMIUM_M +
    "/mo</b> or <b>$" + PREMIUM_Y + "/yr</b></div>" +
    '<div style="margin-top:' + Math.round(h * 0.028) + 'px"><span class="cta">tapeline.io/scorecard</span></div>',
  vo: "Read the record first. Tapeline dot I O. Not investment advice.",
};
const SENTENCE_SUB = '<p class="sub">Descriptive language only &mdash; what the factors measured, never what to do about it.</p>';

const CONCEPTS = {
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
  e: [
    // Was "Every scanner shows you its good weeks." -- false: Zacks has
    // published a record for decades. Now a truism, not a competitor claim.
    { id: "01-hook", base: 2.8,
      screen: () => "<h1>Anyone can show you<br>their <em>good weeks.</em></h1>",
      vo: "Anyone can show you their good weeks." },
    { id: "02-turn", base: 3.2,
      screen: () => "<h1>We publish <em>every</em> day.<br>Including the bad ones.</h1>" +
        '<p class="sub">Each session\'s top ten is written down when it prints, and never re-ranked, back-filled or removed afterwards.</p>',
      vo: "We publish every day. Including the bad ones." },
    { id: "03-proof", base: 3.4,
      screen: (w, h, inner) => crop(w, inner) + '<p class="sub">The same score that goes in the archive is the one you see on the page.</p>',
      vo: "The score in the archive is the one on the page." },
    { id: "04-sentence", base: 3.0,
      screen: () => "<h1>Read it <em>before</em><br>you pay us anything.</h1>" +
        '<p class="sub">The archive is public, downloadable as CSV, and needs no account.</p>',
      vo: "Read it before you pay us anything." },
    MONEY, CTA,
  ],
};

// ---- Compliance gate: lint every spoken line before anything is synthesised.
function lintSpokenLines() {
  const seen = new Set();
  const lines = ["# Spoken voice-over lines (generated by build3.mjs)", ""];
  for (const [key, scenes] of Object.entries(CONCEPTS)) {
    lines.push("## " + key.toUpperCase());
    for (const s of scenes) if (!seen.has(s.vo)) { seen.add(s.vo); lines.push(s.vo); }
    lines.push("");
  }
  const file = join(OUT, "vo-script.md");
  writeFileSync(file, lines.join("\n"), "utf8");
  try {
    execFileSync("node", [join(REPO, "scripts/lint-copy-compliance.mjs"), "--ads", file], { stdio: "pipe" });
  } catch (e) {
    throw new Error("VOICE SCRIPT FAILED THE AD LINT -- nothing rendered.\n" + String(e.stdout || "") + String(e.stderr || ""));
  }
}

function probeSeconds(file) {
  let err = "";
  try { execFileSync(ffmpeg, ["-i", file], { stdio: ["ignore", "ignore", "pipe"] }); }
  catch (e) { err = String(e.stderr || ""); }
  const m = /Duration: (\d+):(\d+):([\d.]+)/.exec(err);
  if (!m) throw new Error("cannot probe " + file);
  return +m[1] * 3600 + +m[2] * 60 + +m[3];
}

// 1. Voice first, once per concept (audio does not depend on aspect ratio).
function voice(key) {
  const dir = join(OUT, "vo", key);
  mkdirSync(dir, { recursive: true });
  return CONCEPTS[key].map((s) => {
    const mp3 = join(dir, s.id + ".mp3");
    run(TTS, ["--voice", VOICE, "--rate=" + RATE, "--text", s.vo, "--write-media", mp3], "tts " + key + "/" + s.id);
    const dur = probeSeconds(mp3);
    const hold = Math.max(s.base, +(LEAD + dur + TAIL).toFixed(2));
    return { ...s, mp3, dur: +dur.toFixed(2), hold };
  });
}

// 2. One audio track per concept: each line delayed by LEAD, padded to its hold.
function audioTrack(key, timed) {
  const dir = join(OUT, "vo", key);
  const segs = timed.map((s, i) => {
    const wav = join(dir, "seg-" + i + ".wav");
    run(ffmpeg, ["-y", "-i", s.mp3,
      "-af", "adelay=" + Math.round(LEAD * 1000) + ",apad=whole_dur=" + s.hold,
      "-t", String(s.hold), "-ar", "48000", "-ac", "1", wav], "seg " + key + "/" + i);
    return wav;
  });
  const list = join(dir, "segs.txt");
  writeFileSync(list, segs.map((f) => "file '" + f.replace(/\\/g, "/") + "'").join("\n") + "\n");
  const track = join(dir, "track.wav");
  const total = timed.reduce((a, s) => a + s.hold, 0);
  // -16 LUFS integrated is the social-video norm; true-peak ceiling below 0.
  run(ffmpeg, ["-y", "-f", "concat", "-safe", "0", "-i", list,
    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:d=0.08,afade=t=out:st=" + (total - 0.3).toFixed(2) + ":d=0.3",
    "-ar", "48000", "-ac", "2", track], "track " + key);
  return track;
}

// 3. Picture, per ratio, held to the voice's timings, then muxed.
function render(key, timed, track, fmt, w, h, sTop, sBot) {
  const dir = join(OUT, "concept-" + key + "-vo", fmt);
  mkdirSync(dir, { recursive: true });
  for (const s of timed) {
    const f = join(dir, s.id + ".html");
    // Stage height = canvas minus both safe bands minus the disclosure block.
    const inner = h - sTop - sBot - (Math.round(w * 0.0215 * 1.4 * 3) + Math.round(h * 0.022));
    writeFileSync(f, shell(w, h, sTop, sBot, stage(s.screen(w, h, inner))), "utf8");
    const png = join(dir, s.id + ".png");
    run(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars",
      "--force-device-scale-factor=1", "--window-size=" + w + "," + h,
      "--virtual-time-budget=3000", "--screenshot=" + png, "file:///" + f.replace(/\\/g, "/")],
      "chrome " + key + "/" + fmt + "/" + s.id);
    if (!existsSync(png)) throw new Error("render failed: " + key + "/" + fmt + "/" + s.id);
  }
  const lines = [];
  for (const s of timed) {
    lines.push("file '" + join(dir, s.id + ".png").replace(/\\/g, "/") + "'");
    lines.push("duration " + s.hold);
  }
  lines.push("file '" + join(dir, timed[timed.length - 1].id + ".png").replace(/\\/g, "/") + "'");
  const cf = join(dir, "concat.txt");
  writeFileSync(cf, lines.join("\n") + "\n");
  const total = timed.reduce((a, s) => a + s.hold, 0);
  const silent = join(dir, "silent.mp4");
  run(ffmpeg, ["-y", "-f", "concat", "-safe", "0", "-i", cf,
    "-vf", "fps=30,scale=" + w + ":" + h + ":flags=lanczos,format=yuv420p",
    "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-t", total.toFixed(2), silent], "video " + key + "/" + fmt);
  const mp4 = join(OUT, "tapeline-concept-" + key + "-vo-" + fmt + ".mp4");
  run(ffmpeg, ["-y", "-i", silent, "-i", track,
    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
    "-t", total.toFixed(2), "-movflags", "+faststart", mp4], "mux " + key + "/" + fmt);
  return { mp4, secs: +total.toFixed(1) };
}

lintSpokenLines();
const report = {};
for (const key of ["b", "d", "e"]) {
  const timed = voice(key);
  const track = audioTrack(key, timed);
  report[key] = {
    speech_s: +timed.reduce((a, s) => a + s.dur, 0).toFixed(1),
    scenes: timed.map((s) => ({ id: s.id, vo_s: s.dur, hold_s: s.hold })),
    out: [
      render(key, timed, track, "9x16", 1080, 1920, 270, 770),  // bottom 40% clear (Meta Reels + disclaimer)
      render(key, timed, track, "4x5", 1080, 1350, 100, 160),
      render(key, timed, track, "1x1", 1080, 1080, 90, 140),
    ],
  };
}
console.log(JSON.stringify({ VOICE, RATE, TRIAL_DAYS, report }, null, 2));
