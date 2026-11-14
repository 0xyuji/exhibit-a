// path-field.js: an SVG path (a logo, a silhouette) as 2D distance fields.
//
// A field answers "how far is this point of the drawing from the edge of the shape?", negative
// inside it. The path is painted once onto a small canvas, and distances are spread out from its
// edge in two sweeps (a chamfer distance transform); lookups blend the four nearest samples, so
// the field is smooth enough to trace rays against.
//
// Coordinates of the samplers: the drawing's own units, CENTRED, with y UPWARDS. For a 512-unit
// drawing, x and y run from -256 to 256.
//
//   const { mark, body } = pathFields(d);     // d drawn in a 512 x 512 box
//   mark(0, 0)   // < 0: the centre is inside the mark

/** Distance field from a mask of n x n samples (1 inside, 0 outside) covering `size` units. */
export function fieldFromMask(inside, n, size = 512) {
  const unit = size / n;
  const far = 1e6;
  const spread = (target) => {
    const d = new Float32Array(n * n);
    for (let i = 0; i < n * n; i++) d[i] = inside[i] === target ? 0 : far;
    const relax = (i, x, y, dx, dy, cost) => {
      const nx = x + dx;
      const ny = y + dy;
      if (nx < 0 || ny < 0 || nx >= n || ny >= n) return;
      const v = d[ny * n + nx] + cost;
      if (v < d[i]) d[i] = v;
    };
    for (let y = 0; y < n; y++)
      for (let x = 0; x < n; x++) {
        const i = y * n + x;
        relax(i, x, y, -1, 0, 1);
        relax(i, x, y, 0, -1, 1);
        relax(i, x, y, -1, -1, 1.414);
        relax(i, x, y, 1, -1, 1.414);
      }
    for (let y = n - 1; y >= 0; y--)
      for (let x = n - 1; x >= 0; x--) {
        const i = y * n + x;
        relax(i, x, y, 1, 0, 1);
        relax(i, x, y, 0, 1, 1);
        relax(i, x, y, 1, 1, 1.414);
        relax(i, x, y, -1, 1, 1.414);
      }
    return d;
  };
  const toInside = spread(1); // 0 inside, growing outwards
  const toOutside = spread(0); // 0 outside, growing inwards
  const data = new Float32Array(n * n);
  for (let i = 0; i < n * n; i++) data[i] = (toInside[i] - toOutside[i]) * unit;
  const half = size / 2;
  return (x, y) => {
    const u = Math.max(0, Math.min(n - 1.001, ((x + half) / size) * n - 0.5));
    const v = Math.max(0, Math.min(n - 1.001, ((half - y) / size) * n - 0.5));
    const x0 = Math.floor(u);
    const y0 = Math.floor(v);
    const fx = u - x0;
    const fy = v - y0;
    const i = y0 * n + x0;
    const top = data[i] * (1 - fx) + data[i + 1] * fx;
    const bottom = data[i + n] * (1 - fx) + data[i + n + 1] * fx;
    return top * (1 - fy) + bottom * fy;
  };
}

/** Paints a path (or runs paint(ctx) in drawing units) and returns the n x n inside mask. */
export function rasterise(dOrPaint, { size = 512, samples = 176, fillRule = "evenodd" } = {}) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = samples;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.scale(samples / size, samples / size);
  if (typeof dOrPaint === "function") dOrPaint(ctx);
  else ctx.fill(new Path2D(dOrPaint), fillRule);
  const px = ctx.getImageData(0, 0, samples, samples).data;
  const inside = new Uint8Array(samples * samples);
  for (let i = 0; i < samples * samples; i++) inside[i] = px[i * 4 + 3] > 127 ? 1 : 0;
  return inside;
}

/**
 * The silhouette with its hollows filled in: in every row, everything between the shape's
 * leftmost and rightmost point. This is the outline of the BODY a mark is swollen into; the
 * hollows are cut back into its front afterwards. With `standing`, the widest of its bottom rows
 * carries on down to the edge of the drawing, so the body has no lower edge and can stand on a
 * ground plane.
 */
export function fillRows(inside, n, { standing = false, baseRows = 6 } = {}) {
  const filled = new Uint8Array(n * n);
  let lastRow = 0;
  for (let y = 0; y < n; y++) {
    let left = -1;
    let right = -1;
    for (let x = 0; x < n; x++) {
      if (!inside[y * n + x]) continue;
      if (left < 0) left = x;
      right = x;
    }
    if (left < 0) continue;
    lastRow = y;
    for (let x = left; x <= right; x++) filled[y * n + x] = 1;
  }
  if (standing) {
    let baseLeft = n;
    let baseRight = -1;
    for (let y = Math.max(0, lastRow - baseRows); y <= lastRow; y++) {
      for (let x = 0; x < n; x++) {
        if (!filled[y * n + x]) continue;
        baseLeft = Math.min(baseLeft, x);
        baseRight = Math.max(baseRight, x);
      }
    }
    for (let y = Math.max(0, lastRow - baseRows); y < n; y++) for (let x = baseLeft; x <= baseRight; x++) filled[y * n + x] = 1;
  }
  return filled;
}

/**
 * Both fields for a path: `mark` is the shape itself, `body` the shape with its hollows filled.
 * 176 samples across a 512-unit drawing is about 3 units a sample: finer than a glyph cell at any
 * size these are drawn at, and the whole thing builds in a few milliseconds.
 */
export function pathFields(d, { size = 512, samples = 176, fillRule = "evenodd", standing = false } = {}) {
  const inside = rasterise(d, { size, samples, fillRule });
  return {
    mark: fieldFromMask(inside, samples, size),
    body: fieldFromMask(fillRows(inside, samples, { standing }), samples, size),
  };
}
