// glyph-field.js: a full-page backdrop of cipher glyphs, optionally with a figure standing in it.
//
// Every glyph is a particle on a spring. The pointer pushes glyphs out of its way and sweeps them
// along with its motion; they spring back home. While it moves, a glyph turns into a stroke
// (- / | \) aligned with its motion. A click sends out a ring. At rest, one glyph in a hundred
// is re-rolled each frame, so the ciphertext keeps changing a little at a time.
//
// A figure is a list of SVG paths painted into a mask on a much finer grid than the field, in
// brighter and denser glyphs on stiffer springs. The field stays out of its silhouette, so the
// body reads as dark with lit cloth on it.
//
// The canvas should sit behind the page:
//   canvas { position: fixed; inset: 0; z-index: 0; pointer-events: none; }
//
//   const field = glyphField(canvas, { figure, quiet });
//   field.destroy();

import { RAMP, FIELD_CELL, FINE_CELL, TONES, prefersStill } from "./glyph-core.js";

const LIGHT = RAMP.slice(0, 10); // the field: only the light half of the ramp, so it stays quiet
const HEAVY = RAMP.slice(10); // the figure: the dense half
const RADIUS = 110; // px, how far the pointer pushes
const FPS = 45;

/** Stroke glyph for a motion direction (screen y points down). */
function stroke(dx, dy) {
  const a = ((Math.atan2(dy, dx) * 180) / Math.PI + 180) % 180;
  if (a < 22.5 || a >= 157.5) return "-";
  if (a < 67.5) return "\\";
  if (a < 112.5) return "|";
  return "/";
}

/**
 * The default quiet zone: the field fades to nothing inside an ellipse around the headline, so
 * text stays readable. Centre and radii are fractions of the viewport. Returns 0 (hidden) .. 1.
 */
export const quietEllipse = ({ x = 0.5, y = 0.46, rx = 0.32, ry = 0.3, inner = 0.55 } = {}) => (hx, hy, w, h) =>
  Math.min(1, Math.max(0, Math.hypot((hx - w * x) / (w * rx), (hy - h * y) / (h * ry)) - inner));

/**
 * figure: {
 *   width, height,           the box the paths were drawn in
 *   paths: [{ tone, d, width? }]   painted in order; `width` makes a path a line, else it is filled
 *       tone "shape":  the whole silhouette. The field stays out; no glyphs of its own.
 *       tone "lit":    surfaces catching the light. Bright glyphs.
 *       tone "shadow": folds and seams cut back out of the lit parts.
 *       tone "face":   an emptiness that must stay empty; paint it last.
 *   fit?(w, h) -> { scale, left, top } | null     where it stands; null hides it
 *   fade?(hx, hy, w, h) -> 0..1                   dim parts of it, e.g. where text crosses it
 *   minScale?                                     below this the detail is lost: hide it (0.45)
 * }
 * quiet: (hx, hy, w, h) -> 0..1, or null for an even field.
 */
export function glyphField(canvas, { figure = null, quiet = quietEllipse(), rgb = TONES.paper, cell = FIELD_CELL, fine = FINE_CELL } = {}) {
  const ctx = canvas.getContext("2d");
  const still = prefersStill();
  let cells = [];
  let raf = 0;
  let last = 0;
  const ptr = { x: -9999, y: -9999, vx: 0, vy: 0, px: -9999, py: -9999, active: false };
  const waves = [];
  const rand = (s) => s[(Math.random() * s.length) | 0];

  /** Paints the figure into a mask with one pixel per fine cell. */
  function figureMask(w, h) {
    if (!figure) return null;
    const place = figure.fit ? figure.fit(w, h) : { scale: (h * 0.87) / figure.height, left: w - (figure.width * h * 0.87) / figure.height, top: h * 0.13 };
    if (!place || place.scale < (figure.minScale ?? 0.45)) return null;
    const cols = Math.ceil(w / fine.w);
    const rows = Math.ceil(h / fine.h);
    const m = document.createElement("canvas");
    m.width = cols;
    m.height = rows;
    const g = m.getContext("2d", { willReadFrequently: true });
    g.fillStyle = "#000";
    g.fillRect(0, 0, cols, rows);
    g.setTransform(place.scale / fine.w, 0, 0, place.scale / fine.h, place.left / fine.w, place.top / fine.h);
    g.lineCap = "round";
    // Two channels: green = part of the figure, red + green = lit. Red alone = the empty face.
    const color = { shape: "#0f0", lit: "#fff", shadow: "#0f0", face: "#f00" };
    for (const p of figure.paths) {
      const path = new Path2D(p.d);
      if (p.width) {
        g.strokeStyle = color[p.tone];
        g.lineWidth = p.width;
        g.stroke(path);
      } else {
        g.fillStyle = color[p.tone];
        g.fill(path);
      }
    }
    const data = g.getImageData(0, 0, cols, rows).data;
    const at = (c, r) => (r * cols + c) * 4;
    return {
      cols,
      rows,
      lit: (c, r) => data[at(c, r)] > 128 && data[at(c, r) + 1] > 128,
      solid: (px, py) => {
        const i = at(Math.floor(px / fine.w), Math.floor(py / fine.h));
        return data[i] > 128 || data[i + 1] > 128;
      },
    };
  }

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = window.innerWidth;
    const h = window.innerHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.textBaseline = "middle";
    ctx.textAlign = "center";
    const cols = Math.ceil(w / cell.w);
    const rows = Math.ceil(h / cell.h);
    const mask = figureMask(w, h);
    const make = (hx, hy, ch, dense, fade) => ({ hx, hy, ox: 0, oy: 0, vx: 0, vy: 0, ch, dense, fade });
    const next = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const hx = c * cell.w + cell.w / 2;
        const hy = r * cell.h + cell.h / 2;
        if (mask?.solid(hx, hy)) continue;
        const fade = quiet ? quiet(hx, hy, w, h) : 1;
        if (fade > 0) next.push(make(hx, hy, rand(LIGHT), false, fade));
      }
    }
    // The figure's cells come after the field's: draw() switches font once, at the first of them.
    if (mask) {
      for (let r = 0; r < mask.rows; r++) {
        for (let c = 0; c < mask.cols; c++) {
          if (!mask.lit(c, r)) continue;
          const hx = c * fine.w + fine.w / 2;
          const hy = r * fine.h + fine.h / 2;
          const fade = figure.fade ? figure.fade(hx, hy, w, h) : 1;
          if (fade > 0) next.push(make(hx, hy, rand(HEAVY), true, fade));
        }
      }
    }
    cells = next;
    draw();
  }

  function physics() {
    // Pointer velocity (for the sweep); it decays when the pointer stops.
    if (ptr.px > -9000) {
      ptr.vx = ptr.vx * 0.5 + (ptr.x - ptr.px) * 0.5;
      ptr.vy = ptr.vy * 0.5 + (ptr.y - ptr.py) * 0.5;
    }
    ptr.px = ptr.x;
    ptr.py = ptr.y;
    for (const wv of waves) {
      wv.r += 14;
      wv.life -= 1;
    }
    for (let i = waves.length - 1; i >= 0; i--) if (waves[i].life <= 0) waves.splice(i, 1);

    const R2 = RADIUS * RADIUS;
    for (const c of cells) {
      const x = c.hx + c.ox;
      const y = c.hy + c.oy;
      const heavy = c.dense ? 0.45 : 1; // the figure resists more
      if (ptr.active) {
        const dx = x - ptr.x;
        const dy = y - ptr.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < R2 && d2 > 0.01) {
          const d = Math.sqrt(d2);
          const f = (1 - d / RADIUS) ** 2;
          c.vx += (dx / d) * f * 3.2 * heavy + ptr.vx * f * 0.12 * heavy;
          c.vy += (dy / d) * f * 3.2 * heavy + ptr.vy * f * 0.12 * heavy;
        }
      }
      for (const wv of waves) {
        const dx = x - wv.x;
        const dy = y - wv.y;
        const d = Math.hypot(dx, dy) || 1;
        const band = Math.abs(d - wv.r);
        if (band < 26) {
          const f = (1 - band / 26) * (wv.life / 40) * 4 * heavy;
          c.vx += (dx / d) * f;
          c.vy += (dy / d) * f;
        }
      }
      const k = c.dense ? 0.11 : 0.07; // the spring home; 0.84 is the damping
      c.vx = (c.vx - c.ox * k) * 0.84;
      c.vy = (c.vy - c.oy * k) * 0.84;
      c.ox += c.vx;
      c.oy += c.vy;
    }
  }

  function draw() {
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    ctx.font = cell.font;
    let inFigure = false;
    for (const c of cells) {
      if (c.dense && !inFigure) {
        inFigure = true;
        ctx.font = fine.font;
      }
      const disp = Math.hypot(c.ox, c.oy);
      const speed = Math.hypot(c.vx, c.vy);
      const ch = speed > 0.9 ? stroke(c.vx, c.vy) : disp > 3 ? stroke(c.ox, c.oy) : c.ch;
      // At rest the field is barely there (0.06); the figure sits at 0.36. Both brighten as they move.
      const a = c.dense ? Math.min(0.7, 0.36 + disp * 0.006 + speed * 0.02) : Math.min(0.5, 0.06 + disp * 0.006 + speed * 0.02);
      ctx.fillStyle = `rgba(${rgb},${a * c.fade})`;
      ctx.fillText(ch, c.hx + c.ox, c.hy + c.oy);
    }
  }

  function tick(now) {
    raf = requestAnimationFrame(tick);
    if (now - last < 1000 / FPS) return;
    last = now;
    physics();
    for (let i = 0; i < cells.length * 0.01; i++) {
      const c = cells[(Math.random() * cells.length) | 0];
      if (Math.abs(c.ox) + Math.abs(c.oy) < 1) c.ch = c.dense ? rand(HEAVY) : rand(LIGHT); // only glyphs at rest
    }
    draw();
  }

  const onMove = (e) => {
    if (ptr.px < -9000) {
      ptr.px = e.clientX;
      ptr.py = e.clientY;
    }
    ptr.x = e.clientX;
    ptr.y = e.clientY;
    ptr.active = true;
  };
  const onLeave = () => {
    ptr.active = false;
    ptr.vx = ptr.vy = 0;
  };
  const onDown = (e) => waves.push({ x: e.clientX, y: e.clientY, r: 0, life: 40 });
  const onVis = () => {
    cancelAnimationFrame(raf);
    if (!document.hidden && !still) raf = requestAnimationFrame(tick);
  };

  resize();
  window.addEventListener("resize", resize);
  if (!still) {
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerdown", onDown, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    window.addEventListener("blur", onLeave);
    document.addEventListener("visibilitychange", onVis);
    raf = requestAnimationFrame(tick);
  }

  return {
    destroy() {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      document.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("blur", onLeave);
      document.removeEventListener("visibilitychange", onVis);
    },
  };
}
