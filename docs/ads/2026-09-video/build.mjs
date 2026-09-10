import { writeFileSync, mkdirSync, readFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import ffmpeg from "ffmpeg-static";

const OUT = process.cwd();
const OUTU = OUT.replace(/\\/g, "/");
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const REPO = "C:/Project 1";

// Read the live constants. An ad that hardcodes these goes stale silently --
// exactly what happened when the trial moved 14 -> 30 days (#737) and the
// creative kept saying 14 while it was running.
const trialSrc = readFileSync(join(REPO, "frontend/lib/trial.ts"), "utf8");
const TRIAL_DAYS = /TRIAL_DAYS = (\d+)/.exec(trialSrc)[1];
const priceSrc = readFileSync(join(REPO, "frontend/lib/pricing.ts"), "utf8");
const PREM = /premium: \{ monthly: ([\d.]+), annual: (\d+)/.exec(priceSrc);
const PREMIUM_M = PREM[1];
const PREMIUM_Y = PREM[2];

const BG = "#0B1220";
const ACCENT = "#2D7DF6";
const FG = "#E8EDF5";
const MUTED = "#8A9BB4";

const DISCLOSURE =
  "Descriptive analytics, not recommendations. Not investment advice. " +
  "Past performance is not indicative of future performance. " +
  "Published by Tapeline &middot; Melbourne, Victoria, Australia.";

function shell(w, h, safeTop, safeBottom, body, opts) {
  opts = opts || {};
  const pad = Math.round(w * 0.078);
  // Three lines of disclosure at its own size/leading, plus breathing room.
  const discReserve = Math.round(w * 0.0215 * 1.4 * 3) + Math.round(h * 0.022);
  return [
    '<!doctype html><html><head><meta charset="utf-8"><style>',
    "*{margin:0;padding:0;box-sizing:border-box}",
    "html,body{width:" + w + "px;height:" + h + "px;background:" + BG + ";overflow:hidden}",
    'body{font-family:"Segoe UI",system-ui,sans-serif;-webkit-font-smoothing:antialiased;',
    "background:radial-gradient(120% 80% at 50% 0%, #12203A 0%, " + BG + " 62%);}",
    // Stage stops above the disclosure block so copy can never overlap it.
    ".stage{position:absolute;left:0;right:0;top:" + safeTop + "px;bottom:" + (safeBottom + discReserve) + "px;",
    "padding:0 " + pad + "px;display:flex;flex-direction:column;justify-content:center;}",
    ".brand{display:flex;align-items:center;gap:" + Math.round(w * 0.017) + "px;margin-bottom:" + Math.round(h * 0.032) + "px}",
    ".dot{width:" + Math.round(w * 0.05) + "px;height:" + Math.round(w * 0.011) + "px;border-radius:99px;background:" + ACCENT + "}",
    ".wm{color:" + FG + ";font-size:" + Math.round(w * 0.031) + "px;font-weight:600;letter-spacing:.01em}",
    "h1{color:#fff;font-size:" + (opts.hSize || Math.round(w * 0.080)) + "px;line-height:1.11;font-weight:700;letter-spacing:-0.02em}",
    "h1 em{font-style:normal;color:" + ACCENT + "}",
    "p.sub{color:" + MUTED + ";font-size:" + Math.round(w * 0.038) + "px;line-height:1.45;margin-top:" + Math.round(h * 0.022) + "px}",
    // The disclosure has to sit INSIDE the safe zone, not at the foot of the
    // canvas. Pinned to the bottom of a 1920px Reels frame it lands under
    // Instagram's caption/profile/CTA chrome, i.e. legally required text that
    // no viewer ever sees. Bottom-anchored to safeBottom instead.
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

// A cropped window onto a real screenshot. Pulling the actual product in beats
// a text card: none of the competitor ads in this niche show a calm, specific
// product moment, and Tapeline's existing creative is text-only.
function crop(file, boxH, imgW, top, left, w) {
  return (
    '<div class="frame" style="height:' + boxH + 'px">' +
    '<img src="file:///' + OUTU + "/" + file + '" style="display:block;width:' + imgW +
    "px;margin-top:-" + top + "px;margin-left:-" + left + 'px"></div>'
  );
}

// Source capture is 1440 wide; the NVDA score panel sits at x 232..1208,
// y 268..840. Fit its full width into the padded stage.
const SRC_W = 1440, PANEL_X = 232, PANEL_Y = 268, PANEL_W = 976, PANEL_H = 572;

function panelGeom(w) {
  const stageW = w - 2 * Math.round(w * 0.078);
  const k = stageW / PANEL_W;
  return {
    imgW: Math.round(SRC_W * k),
    left: Math.round(PANEL_X * k),
    top: Math.round(PANEL_Y * k),
    boxH: Math.round(PANEL_H * k),
  };
}

function scenes(w, h, sTop, sBot) {
  const inner = h - sTop - sBot;
  const PANEL = panelGeom(w);
  return [
    {
      id: "01-hook", hold: 2.6,
      html: shell(w, h, sTop, sBot,
        '<div class="stage">' + brand +
        "<h1>Every stock screener<br>hands you <em>500 filters</em><br>and a blank stare.</h1></div>"),
    },
    {
      id: "02-turn", hold: 2.6,
      html: shell(w, h, sTop, sBot,
        '<div class="stage">' + brand +
        "<h1>Tapeline hands you<br><em>one number.</em></h1>" +
        '<p class="sub">Six named factors, one 0&ndash;100 composite, re-scored through the US session.</p></div>'),
    },
    {
      id: "03-proof", hold: 3.4,
      html: shell(w, h, sTop, sBot,
        '<div class="stage">' + brand +
        // Geometry is derived, not eyeballed. The score panel occupies
        // x 232..1208, y 268..840 of the 1440px-wide capture. Scale it so the
        // panel's full width lands inside the padded stage -- the first pass
        // scaled to 1.6x and sliced the radar chart, which is the single most
        // distinctive thing on the page, straight off the right edge.
        crop("shot-ticker.png", PANEL.boxH, PANEL.imgW, PANEL.top, PANEL.left, w) +
        '<p class="sub">A real ticker page: the score, the six factors behind it, and the data confidence.</p></div>'),
    },
    {
      id: "04-sentence", hold: 2.8,
      html: shell(w, h, sTop, sBot,
        '<div class="stage">' + brand +
        "<h1>And <em>one plain sentence</em><br>saying what moved it.</h1>" +
        '<p class="sub">Descriptive language only &mdash; what the factors measured, never what to do about it.</p></div>'),
    },
    {
      id: "05-money", hold: 3.4,
      html: shell(w, h, sTop, sBot,
        '<div class="stage">' + brand +
        "<h1><em>$0 today.</em><br>The charge date<br>is on the page.</h1>" +
        '<p class="sub">' + TRIAL_DAYS + "-day Premium trial. It takes a card, charges nothing that day, and shows " +
        "the exact first-charge date before you confirm. One click cancels before then.</p></div>"),
    },
    {
      id: "06-cta", hold: 3.2,
      html: shell(w, h, sTop, sBot,
        '<div class="stage">' + brand +
        '<h1 style="font-size:' + Math.round(w * 0.068) + 'px">Read the record<br>before you sign up.</h1>' +
        '<p class="sub">The published top-10 archive &mdash; the misses included &mdash; needs no account and no card.</p>' +
        '<div class="kv" style="margin-top:' + Math.round(h * 0.024) + 'px">Premium <b>$' + PREMIUM_M +
        "/mo</b> or <b>$" + PREMIUM_Y + "/yr</b></div>" +
        '<div style="margin-top:' + Math.round(h * 0.028) + 'px"><span class="cta">tapeline.io/scorecard</span></div></div>'),
    },
  ];
}

function render(fmt, w, h, sTop, sBot) {
  const dir = join(OUT, fmt);
  mkdirSync(dir, { recursive: true });
  const list = scenes(w, h, sTop, sBot);
  for (const s of list) {
    const f = join(dir, s.id + ".html");
    writeFileSync(f, s.html, "utf8");
    const png = join(dir, s.id + ".png");
    execFileSync(CHROME, [
      "--headless=new", "--disable-gpu", "--hide-scrollbars",
      "--force-device-scale-factor=1", "--window-size=" + w + "," + h,
      "--virtual-time-budget=3000", "--screenshot=" + png,
      "file:///" + f.replace(/\\/g, "/"),
    ], { stdio: "ignore" });
    if (!existsSync(png)) throw new Error("render failed: " + fmt + "/" + s.id);
  }
  const lines = [];
  for (const s of list) {
    lines.push("file '" + join(dir, s.id + ".png").replace(/\\/g, "/") + "'");
    lines.push("duration " + s.hold);
  }
  lines.push("file '" + join(dir, list[list.length - 1].id + ".png").replace(/\\/g, "/") + "'");
  const cf = join(dir, "concat.txt");
  writeFileSync(cf, lines.join("\n") + "\n", "utf8");
  const mp4 = join(OUT, "tapeline-" + fmt + ".mp4");
  execFileSync(ffmpeg, [
    "-y", "-f", "concat", "-safe", "0", "-i", cf,
    "-vf", "fps=30,scale=" + w + ":" + h + ":flags=lanczos,format=yuv420p",
    "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-movflags", "+faststart", mp4,
  ], { stdio: "ignore" });
  return { fmt, mp4, scenes: list.length, secs: +list.reduce((a, s) => a + s.hold, 0).toFixed(1) };
}

const results = [
  render("9x16", 1080, 1920, 270, 690),
  render("1x1", 1080, 1080, 90, 140),
  render("4x5", 1080, 1350, 100, 160),
];
console.log(JSON.stringify({ TRIAL_DAYS, PREMIUM_M, PREMIUM_Y, results }, null, 2));
