// glyph-core.js: shared constants and helpers for cipher-glyph canvases.
// Plain ES module, no dependencies, browser only where it touches the DOM.

/** Light to dense. A glyph's index is its brightness: index = floor(light * RAMP.length). */
export const RAMP = ".,:;'-+/\\|!*=%#&$@";

export const MONO = 'ui-monospace, "SF Mono", Menlo, monospace';

/* Cell sizes in CSS pixels. A cell is taller than wide, like the glyphs it holds. */
export const ART_CELL = { w: 4, h: 7, font: `7px ${MONO}` }; // pictures sampled from paint
export const FINE_CELL = { w: 4, h: 6.5, font: `7px ${MONO}` }; // figures and traced solids
export const FIELD_CELL = { w: 11, h: 18, font: `13px ${MONO}` }; // the quiet background field

/* Colours as "r,g,b" so an alpha can be appended. One neutral, one accent, one glow. */
export const TONES = { paper: "236,231,222", brass: "200,164,106", glow: "255,223,154" };
export const INK = "#0c0d0f"; // the page behind every canvas

export const clamp01 = (v) => Math.max(0, Math.min(1, v));
/** Slow in, slow out (cubic). */
export const ease = (v) => (v < 0.5 ? 4 * v * v * v : 1 - Math.pow(-2 * v + 2, 3) / 2);
/** Eased progress 0..1 of time t through the window [from, to]. */
export const span = (t, [from, to]) => ease(clamp01((t - from) / (to - from)));

export const prefersStill = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Fill styles for one colour at `levels` brightness steps, built once so the draw loop never
 * formats a string. `floor` is the alpha of the dimmest step: glyphs below about 0.2 vanish.
 */
export const alphaStyles = (rgb, levels, floor) => Array.from({ length: levels }, (_, i) => `rgba(${rgb},${(floor + ((1 - floor) * (i + 1)) / levels).toFixed(2)})`);

/**
 * Sizes the canvas's backing store to its CSS box (device pixel ratio capped at 2) and returns
 * the glyph grid that fits, centred. The canvas needs a CSS size (width plus height or
 * aspect-ratio, display: block). Returns null while the box is empty.
 */
export function fitCanvas(canvas, cell) {
  const box = canvas.getBoundingClientRect();
  const w = Math.round(box.width);
  const h = Math.round(box.height);
  if (!w || !h) return null;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  const cols = Math.floor(w / cell.w);
  const rows = Math.floor(h / cell.h);
  return { w, h, dpr, cols, rows, padX: (w - cols * cell.w) / 2, padY: (h - rows * cell.h) / 2 };
}

/** Clears the canvas and sets it up to draw glyphs centred on cell centres. */
export function beginGlyphs(ctx, grid, font) {
  ctx.setTransform(grid.dpr, 0, 0, grid.dpr, 0, 0);
  ctx.clearRect(0, 0, grid.w, grid.h);
  ctx.font = font;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
}

/** A fixed pseudo-random integer per cell, for texture that does not move. */
export const cellHash = (c, r) => (Math.imul(c, 73856093) ^ Math.imul(r, 19349663)) >>> 0;

/**
 * Smooth value noise in space, 0..1. Sample it at a surface point (scaled by about 0.034 per
 * unit of a 512-unit drawing) and slide the sample point over time: the texture then flows
 * across the object and turns with it, instead of flickering in screen space.
 */
export function grain(x, y, z) {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const zi = Math.floor(z);
  const fx = x - xi;
  const fy = y - yi;
  const fz = z - zi;
  const at = (i, j, k) => {
    let h = Math.imul(i, 374761393) ^ Math.imul(j, 668265263) ^ Math.imul(k, 2147483647);
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
  };
  const sx = fx * fx * (3 - 2 * fx);
  const sy = fy * fy * (3 - 2 * fy);
  const sz = fz * fz * (3 - 2 * fz);
  const mix = (a, b, t) => a + (b - a) * t;
  return mix(
    mix(mix(at(xi, yi, zi), at(xi + 1, yi, zi), sx), mix(at(xi, yi + 1, zi), at(xi + 1, yi + 1, zi), sx), sy),
    mix(mix(at(xi, yi, zi + 1), at(xi + 1, yi, zi + 1), sx), mix(at(xi, yi + 1, zi + 1), at(xi + 1, yi + 1, zi + 1), sx), sy),
    sz,
  );
}
