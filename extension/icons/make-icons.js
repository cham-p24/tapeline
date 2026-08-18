/**
 * Extension icons — rendered from the canonical Tapeline mark so the toolbar
 * icon is the same logo as the favicon, not a lookalike.
 *
 * Source of truth: frontend/public/favicon.svg and frontend/app/icon.tsx —
 * a #0a0a0a rounded square (radius 6/32) with a centred #3b82f6 pill bar
 * (20x5 of 32, fully rounded). Any change to the brand mark should be made
 * there first and re-rendered here.
 */
const zlib = require("zlib"), fs = require("fs");
const T = (() => { let c, t = []; for (let n = 0; n < 256; n++) { c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc = (b) => { let c = 0xffffffff; for (const x of b) c = T[(c ^ x) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const cc = Buffer.alloc(4); cc.writeUInt32BE(crc(td));
  return Buffer.concat([len, td, cc]);
}
const GROUND = [0x0a, 0x0a, 0x0a], BAR = [0x3b, 0x82, 0xf6];

// Signed distance to a rounded rect centred at (cx,cy), half-extents (hx,hy).
function sdRoundRect(px, py, cx, cy, hx, hy, r) {
  const qx = Math.abs(px - cx) - (hx - r), qy = Math.abs(py - cy) - (hy - r);
  return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - r;
}

function px(x, y, S) {
  const u = x / S, v = y / S, aa = 1.2 / S;
  // Ground: full-bleed rounded square, radius 6/32.
  const dG = sdRoundRect(u, v, .5, .5, .5, .5, 6 / 32);
  const aG = 1 - Math.min(1, Math.max(0, (dG + aa) / aa));
  if (aG <= 0) return [0, 0, 0, 0];
  // Bar: 20x5 of 32, centred, fully rounded (radius = half height).
  const hx = 10 / 32, hy = 2.5 / 32;
  const dB = sdRoundRect(u, v, .5, .5, hx, hy, hy);
  const aB = 1 - Math.min(1, Math.max(0, (dB + aa) / aa));
  const c = [0, 1, 2].map((i) => Math.round(GROUND[i] + (BAR[i] - GROUND[i]) * aB));
  return [...c, Math.round(255 * aG)];
}

for (const S of [16, 48, 128]) {
  const raw = Buffer.alloc(S * (S * 4 + 1));
  let o = 0;
  for (let y = 0; y < S; y++) { raw[o++] = 0; for (let x = 0; x < S; x++) { const p = px(x + .5, y + .5, S); raw[o++] = p[0]; raw[o++] = p[1]; raw[o++] = p[2]; raw[o++] = p[3]; } }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(S, 0); ihdr.writeUInt32BE(S, 4);
  ihdr[8] = 8; ihdr[9] = 6;
  const png = Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw, { level: 9 })), chunk("IEND", Buffer.alloc(0))]);
  fs.writeFileSync(`icon${S}.png`, png);
  console.log(`icon${S}.png  ${png.length} bytes`);
}
