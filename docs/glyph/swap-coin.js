// swap-coin.js: the hero's solid. One coin, traced in glyphs: the NEAR mark struck on one face,
// and on the other Bitcoin and Zcash by turns. It turns over slowly, rests, and turns back: a
// swap, with the only moment you cannot read being the middle of the turn. The far face changes
// coin while NEAR is the one facing us, so the change is never seen.
//
//   swapCoin(canvas);

import { clamp01, ease } from "./glyph-core.js";
import { rasterise, fieldFromMask } from "./path-field.js";
import { glyphSolid, metal, matte } from "./glyph-solid.js";

/* Lengths are in the drawing's units (a 512 box), centred, y up, z towards the viewer. */
const RADIUS = 192; // the coin
const HALF = 30; // half its thickness
const ROUND = 9; // how soft its edge is
const RIM = 30; // width of the raised rim
const DISH = 10; // how far the faces sit below the rim
const REST = 5.2; // seconds a face is shown
const TURN = 2.6; // seconds the turn takes
const LEAN = -0.42; // it never faces us square: we always see a little of its edge

const BODY = 1;
const FRONT = 2;
const BACK = 3;
const SECOND = 4; // the front face while it shows Zcash

/** The Bitcoin mark: a leaning B with strokes above and below, its bowls drawn as outlines. */
function paintB(ctx) {
  const r = 190;
  ctx.translate(256, 256);
  ctx.rotate(0.244);
  ctx.fillStyle = ctx.strokeStyle = "#fff";
  const line = r * 0.16;
  const top = -r * 0.5;
  const bottom = r * 0.5;
  const left = -r * 0.31;
  ctx.lineWidth = line;
  ctx.lineJoin = "miter";
  const bowl = (y0, y1, width) => {
    const tall = y1 - y0;
    ctx.beginPath();
    ctx.roundRect(left + line / 2, y0, width - line, tall, [0, tall / 2, tall / 2, 0]);
    ctx.stroke();
  };
  bowl(top + line / 2, 0, r * 0.66);
  bowl(0, bottom - line / 2, r * 0.76);
  const bar = r * 0.12;
  const reach = r * 0.2;
  for (const x of [left + r * 0.18, left + r * 0.42]) {
    ctx.fillRect(x, top - reach, bar, reach + 1);
    ctx.fillRect(x, bottom - 1, bar, reach + 1);
  }
  ctx.fillRect(left - r * 0.15, top, r * 0.17, line);
  ctx.fillRect(left - r * 0.15, bottom - line, r * 0.17, line);
}

/** The Zcash mark: a Z with a short stroke above and below. */
function paintZ(ctx) {
  const r = 190;
  ctx.translate(256, 256);
  ctx.fillStyle = "#fff";
  const half = r * 0.4; // half its width
  const tall = r * 0.47; // half its height
  const line = r * 0.17;
  const slant = line * 1.5;
  ctx.fillRect(-half, -tall, half * 2, line);
  ctx.fillRect(-half, tall - line, half * 2, line);
  ctx.beginPath();
  ctx.moveTo(half - slant, -tall + line - 1);
  ctx.lineTo(half, -tall + line - 1);
  ctx.lineTo(-half + slant, tall - line + 1);
  ctx.lineTo(-half, tall - line + 1);
  ctx.closePath();
  ctx.fill();
  const bar = r * 0.14;
  const reach = r * 0.21;
  ctx.fillRect(-bar / 2, -tall - reach, bar, reach + 1);
  ctx.fillRect(-bar / 2, tall - 1, bar, reach + 1);
}

/** The NEAR mark, drawn in a 90-unit box and centred on the face. */
const NEAR_MARK =
  "M72.2 4.6L53.4 32.5c-1.3 1.9 1.2 4.2 3 2.6L74.9 19c.5-.4 1.2-.1 1.2.6v50.3c0 .7-.9 1-1.3.5l-56-67C17.1 1.3 14.4 0 11.5 0h-2C4.3 0 0 4.3 0 9.6v70.8C0 85.7 4.3 90 9.6 90c3.3 0 6.4-1.7 8.2-4.6l18.8-27.900c1.3-1.900-1.200-4.200-3-2.600l-18.500 16c-.5.4-1.200.1-1.200-.6V20.100c0-.7.9-1 1.300-.5l56 67c1.800 2.200 4.600 3.500 7.400 3.500h2c5.300 0 9.600-4.300 9.600-9.600V9.600C90 4.300 85.700 0 80.400 0c-3.400 0-6.500 1.700-8.200 4.600z";
function paintNear(ctx) {
  const size = 216;
  ctx.translate(256 - size / 2, 256 - size / 2);
  ctx.scale(size / 90, size / 90);
  ctx.fillStyle = "#fff";
  ctx.fill(new Path2D(NEAR_MARK));
}

export function swapCoin(canvas, opts = {}) {
  const fronts = [fieldFromMask(rasterise(paintB), 176), fieldFromMask(rasterise(paintZ), 176)];
  let showing = 0; // which coin the front face carries: 0 Bitcoin, 1 Zcash
  const back = fieldFromMask(rasterise(paintNear), 176);
  const middle = HALF - DISH / 2 - 1; // where the struck marks sit, between the dish and the rim
  const depth = DISH / 2 - 1;

  /** Distance from a point to the coin, in the coin's own space. */
  const scene = (x, y, z, hit) => {
    hit.kind = BODY;
    const away = Math.hypot(x, y, z);
    if (away > RADIUS + 70) return away - RADIUS - 24; // far away: a ball around it will do
    const out = Math.hypot(x, y);
    const deep = Math.abs(z);
    // The milled edge: fine ridges round the rim.
    let radius = RADIUS;
    if (out > RADIUS - 16 && deep < HALF + 8) radius += Math.cos(Math.atan2(y, x) * 46) * 1.7;
    const a = out - (radius - ROUND);
    const b = deep - (HALF - ROUND);
    let d = Math.min(Math.max(a, b), 0) + Math.hypot(Math.max(a, 0), Math.max(b, 0)) - ROUND;
    // Both faces are dished inside the rim.
    const dish = Math.max(out - (RADIUS - RIM), HALF - DISH - deep);
    if (-dish > d) d = -dish;
    // The marks are struck up from the dished faces. The back one is mirrored, so it reads
    // the right way round once the coin has turned over.
    if (deep > HALF - DISH - 6 && out < RADIUS - RIM) {
      const mark = z > 0 ? fronts[showing](x, y) : back(-x, y);
      const struck = Math.max(mark, Math.abs(deep - middle) - depth);
      if (struck < d) {
        d = struck;
        hit.kind = z > 0 ? (showing ? SECOND : FRONT) : BACK;
      }
    }
    return d;
  };

  /** It rests on one face, turns over, rests on the other, and so on, swaying a little throughout. */
  const pose = (t, idle) => {
    const clock = idle + (t > 0 && !idle ? t : 0);
    const cycle = REST + TURN;
    const turns = Math.floor(clock / cycle);
    const within = clock - turns * cycle;
    const turned = ease(clamp01((within - REST) / TURN));
    showing = Math.floor((turns + 1) / 2) % 2; // changes at the instant NEAR comes to face us
    return {
      ry: LEAN + Math.PI * (turns + turned) + Math.sin(clock * 0.55) * 0.16,
      rx: 0.1 + Math.sin(clock * 0.37) * 0.05,
    };
  };

  return glyphSolid(canvas, {
    scene,
    pose,
    end: 0,
    bound: { y: 0, r: RADIUS + 22 },
    spread: 0.132,
    replayOnHover: false,
    materials: {
      [BODY]: { rgb: "236,231,222", light: (s) => metal(s) * 0.8 },
      [FRONT]: { rgb: "247,147,26", light: (s) => Math.min(1, matte(s) * 1.25 + 0.12) },
      [BACK]: { rgb: "0,236,151", light: (s) => Math.min(1, matte(s) * 1.25 + 0.12) },
      [SECOND]: { rgb: "244,183,40", light: (s) => Math.min(1, matte(s) * 1.32 + 0.15) },
    },
    ...opts,
  });
}
