// glyph-solid.js: a solid, lit, turning object drawn only in cipher glyphs on a 2D canvas.
// No 3D library and no WebGL. For every glyph cell a ray is walked into a small scene described
// by distance functions ("how far is this point from the nearest surface?"), and the cell gets a
// glyph as dense as that spot is bright.
//
// Space: the units of the drawing the object came from (512 across), centred, y up, z towards
// the object's front. The camera sits on +z looking back at it.
//
//   const solid = glyphSolid(canvas, {
//     scene(x, y, z, hit) { ...; hit.kind = 1; return distance; },
//     materials: { 1: { rgb: TONES.paper, light: matte } },
//     pose(t, idle) { return { ry, rx }; },     // t: seconds into the show; idle: seconds since it ended
//     end: 6.5,                                 // length of the show; 0 for none
//   });
//   solid.play(); solid.destroy();
//
// See example-solid.js for a complete scene.

import { RAMP, FINE_CELL, alphaStyles, fitCanvas, beginGlyphs, prefersStill, clamp01, grain } from "./glyph-core.js";

/* ---- distance functions: each returns the distance to a shape, negative inside ---- */

/** A cylinder along z: radius r, from z0 to z1. (cx, cy) is the offset from its axis. */
export const tube = (cx, cy, z, r, z0, z1) => {
  const a = Math.hypot(cx, cy) - r;
  const b = Math.max(z0 - z, z - z1);
  return Math.min(Math.max(a, b), 0) + Math.hypot(Math.max(a, 0), Math.max(b, 0));
};
/** A box with half sizes hx, hy, hz around the origin. Subtract a little to round it. */
export const block = (x, y, z, hx, hy, hz) => {
  const a = Math.abs(x) - hx;
  const b = Math.abs(y) - hy;
  const c = Math.abs(z) - hz;
  return Math.min(Math.max(a, b, c), 0) + Math.hypot(Math.max(a, 0), Math.max(b, 0), Math.max(c, 0));
};
/** A ring (torus): (a, b) lie in the ring's plane, c across it; R is its radius, r its thickness. */
export const ring = (a, b, c, R, r) => Math.hypot(Math.hypot(a, b) - R, c) - r;
/** A flattened ball. Scaled by its thinnest radius, so the distance never overshoots. */
export const ball = (x, y, z, rx, ry, rz) => (Math.hypot(x / rx, y / ry, z / rz) - 1) * Math.min(rx, ry, rz);

/**
 * A flat outline swollen into a BODY: thickest (`depth` each way) once `reach` in from the
 * outline, thinning to nothing at the edge, like a dome over every part of it. `edge` is the
 * outline's 2D distance at (x, y). This is what makes a logo read as a creature or an object
 * rather than a plate cut from sheet metal.
 */
export function swell(edge, z, reach, depth) {
  if (edge >= 0) return Math.hypot(edge, z);
  const u = Math.min(-edge / reach, 1);
  const thick = depth * (2 * u - u * u);
  const slope = ((2 * depth) / reach) * (1 - u);
  return (Math.abs(z) - thick) / Math.sqrt(1 + slope * slope); // an estimate: step short of it
}
/** The same outline pushed straight back into a slab `half` deep each way, edges rounded by `round`. */
export function slab(edge, z, half, round) {
  const a = edge + round;
  const b = Math.abs(z) - (half - round);
  return Math.min(Math.max(a, b), 0) + Math.hypot(Math.max(a, 0), Math.max(b, 0)) - round;
}
/**
 * The hollows of a mark, cut into the FRONT of its body down to z = floor (behind that the body
 * stays solid, so it has a back). Returns the distance to keep with Math.max(body, hollow): where
 * the hollow wins, the point is on the hollow's wall.
 *   bodyEdge: 2D distance to the filled outline; markEdge: 2D distance to the mark itself.
 */
export const hollow = (bodyEdge, markEdge, z, floor) => -Math.max(bodyEdge, -markEdge, floor - z);

/* ---- shading: light 0..1 from a surface sample `s` ---- */

/** Cloth, stone, anything dull: ambient + facing the light + a rim where it turns away. */
export const matte = (s) => 0.27 + 0.8 * s.facing + 0.5 * Math.pow(s.edge, 0.8);
/** The highlight where the light bounces straight to the eye. */
export function shine(s, power = 22) {
  const hx = s.lx - s.dx;
  const hy = s.ly - s.dy;
  const hz = s.lz - s.dz;
  return Math.pow(Math.max(0, (s.nx * hx + s.ny * hy + s.nz * hz) / Math.hypot(hx, hy, hz)), power);
}
/** Metal: less ambient, a sharp highlight. */
export const metal = (s) => 0.34 + 0.5 * s.facing + 0.7 * shine(s) + 0.3 * s.edge;

/**
 * opts:
 *   scene(x, y, z, hit) -> distance      sets hit.kind to the id of the nearest thing
 *   materials: { [kind]: { rgb, light(s) -> 0..1, flat?, grain?(s, drift) -> 0..1 } }
 *       flat: the light does not depend on the surface direction (something glowing): skips
 *       the four extra scene samples a normal costs.
 *   pose(t, idle) -> { ry, rx, open }    the object's turn in radians. `open: true` when something
 *       is outside the bounding ball this frame (disables the quick miss test). May also move
 *       things inside the scene.
 *   end        seconds the one-time show lasts (0: none). It plays once when 75% on screen.
 *   loopRest   seconds to rest before playing again, for a waiting state (null: play once)
 *   bound      { y, r }: a ball around the resting object, centred on the y axis
 *   camera     distance of the eye; spread: tangent of half the vertical field of view
 *   aim        [x, y] the view's centre; sun: direction to the light, in view space
 *   flow       how fast the grain drifts down the surface, units a second
 */
export function glyphSolid(canvas, opts) {
  const {
    scene,
    materials,
    pose = () => null,
    end = 0,
    loopRest = null,
    bound = { y: 0, r: 300 },
    camera = 1750,
    spread = 0.15,
    aim = [0, 0],
    sun = [-0.5, 0.6, 0.62],
    flow = 24,
    cell = FINE_CELL,
    ramp = RAMP,
    levels = 10,
    alphaFloor = 0.34,
    maxSteps = 110,
    stepScale = 0.86, // swell() distances are estimates, so step a little short
    replayOnHover = true,
  } = opts;
  const FRAME_MS = 1000 / 60;
  const ctx = canvas.getContext("2d");
  const still = prefersStill();
  const inks = {};
  for (const kind of Object.keys(materials)) inks[kind] = alphaStyles(materials[kind].rgb, levels, alphaFloor);
  const defaultGrain = (s, drift) => grain(s.px * 0.034, (s.py + drift) * 0.034, s.pz * 0.034);

  let grid = null;
  const hit = { kind: 0 };
  const s = { kind: 0, px: 0, py: 0, pz: 0, nx: 0, ny: 0, nz: 0, dx: 0, dy: 0, dz: 0, lx: 0, ly: 0, lz: 0, facing: 0, edge: 0, t: 0, idle: 0 };
  // Turn of the object, as the rows of the matrix that takes a view direction into its own space.
  const m = [1, 0, 0, 0, 1, 0, 0, 0, 1];

  function draw(t, idle, clock) {
    if (!grid) return;
    const p = pose(t, idle) ?? {};
    const ry = p.ry ?? 0;
    const rx = p.rx ?? 0;
    const cy = Math.cos(ry);
    const sy = Math.sin(ry);
    const cx = Math.cos(rx);
    const sx = Math.sin(rx);
    // The inverse (transpose) of "turn about x, then about y". Rays are turned, not the object.
    m[0] = cy;
    m[1] = 0;
    m[2] = -sy;
    m[3] = sx * sy;
    m[4] = cx;
    m[5] = sx * cy;
    m[6] = cx * sy;
    m[7] = -sx;
    m[8] = cx * cy;

    const drift = clock * flow;
    const { w, h, cols, rows, padX, padY } = grid;
    beginGlyphs(ctx, grid, cell.font);
    const aspect = w / h;
    // The eye's position and the light's direction, taken into the object's space once.
    const ox = m[0] * aim[0] + m[1] * aim[1] + m[2] * camera;
    const oy = m[3] * aim[0] + m[4] * aim[1] + m[5] * camera;
    const oz = m[6] * aim[0] + m[7] * aim[1] + m[8] * camera;
    s.lx = m[0] * sun[0] + m[1] * sun[1] + m[2] * sun[2];
    s.ly = m[3] * sun[0] + m[4] * sun[1] + m[5] * sun[2];
    s.lz = m[6] * sun[0] + m[7] * sun[1] + m[8] * sun[2];
    s.t = t;
    s.idle = idle;
    const far = camera + bound.r + 260;
    const by = oy - bound.y;
    const ballTerm = ox * ox + by * by + oz * oz - bound.r * bound.r;
    for (let r = 0; r < rows; r++) {
      const vy = (1 - ((r + 0.5) / rows) * 2) * spread;
      for (let c = 0; c < cols; c++) {
        const vx = (((c + 0.5) / cols) * 2 - 1) * spread * aspect;
        const inv = 1 / Math.hypot(vx, vy, 1);
        const wx = vx * inv;
        const wy = vy * inv;
        const wz = -inv;
        const dx = m[0] * wx + m[1] * wy + m[2] * wz;
        const dy = m[3] * wx + m[4] * wy + m[5] * wz;
        const dz = m[6] * wx + m[7] * wy + m[8] * wz;
        let at = 120;
        if (!p.open) {
          // Only the object is there: a ray that misses its ball hits nothing, and one that meets
          // it can start walking from where it goes in.
          const along = ox * dx + by * dy + oz * dz;
          const inside = along * along - ballTerm;
          if (inside < 0) continue;
          at = -along - Math.sqrt(inside);
        }
        // Walk along the ray by the distance to the nearest surface each time, until one is reached.
        let kind = 0;
        for (let step = 0; step < maxSteps && at < far; step++) {
          const d = scene(ox + dx * at, oy + dy * at, oz + dz * at, hit);
          if (d < 1.1) {
            kind = hit.kind;
            break;
          }
          at += d * stepScale;
        }
        if (!kind) continue;
        const mat = materials[kind];
        const px = (s.px = ox + dx * at);
        const py = (s.py = oy + dy * at);
        const pz = (s.pz = oz + dz * at);
        s.kind = kind;
        s.dx = dx;
        s.dy = dy;
        s.dz = dz;
        if (!mat.flat) {
          // Which way the surface faces, from how the distance changes around the point.
          const e = 2.4;
          const a = scene(px + e, py - e, pz - e, hit);
          const b = scene(px - e, py - e, pz + e, hit);
          const cc = scene(px - e, py + e, pz - e, hit);
          const dd = scene(px + e, py + e, pz + e, hit);
          let nx = a - b - cc + dd;
          let ny = -a - b + cc + dd;
          let nz = -a + b - cc + dd;
          const n = 1 / (Math.hypot(nx, ny, nz) || 1);
          s.nx = nx *= n;
          s.ny = ny *= n;
          s.nz = nz *= n;
          s.facing = Math.max(0, nx * s.lx + ny * s.ly + nz * s.lz);
          s.edge = Math.pow(1 - Math.max(0, -(nx * dx + ny * dy + nz * dz)), 2.4); // brighter where it turns away
        }
        let light = mat.light(s);
        // The drifting pattern: fixed to the object, sliding down it, so it turns with the surface.
        const pattern = (mat.grain ?? defaultGrain)(s, drift);
        light = clamp01(light * (0.84 + 0.3 * pattern));
        if (light < 0.05) continue;
        const glyph = Math.max(0, Math.min(ramp.length - 1, Math.floor(light * ramp.length + (pattern - 0.5) * 3)));
        ctx.fillStyle = inks[kind][Math.min(levels - 1, Math.floor(light * levels))];
        ctx.fillText(ramp[glyph], padX + c * cell.w + cell.w / 2, padY + r * cell.h + cell.h / 2);
      }
    }
  }

  let visible = false;
  let frame = 0;
  let last = 0;
  let startedAt = null; // when the show began; null until it has
  let awakeAt = 0; // when it ended
  function tick(ms) {
    frame = 0;
    if (ms - last >= FRAME_MS - 2) {
      last = ms;
      const now = ms / 1000;
      let t = startedAt === null ? 0 : now - startedAt;
      if (loopRest !== null && startedAt !== null && t >= end + loopRest) {
        startedAt = now; // waiting: play it again
        awakeAt = 0;
        t = 0;
      }
      if (startedAt !== null && t >= end && !awakeAt) awakeAt = now;
      draw(t, awakeAt ? now - awakeAt + 0.001 : 0, now);
    }
    if (visible) frame = requestAnimationFrame(tick); // even before the show, the grain drifts
  }
  function play() {
    if (still) return;
    startedAt = performance.now() / 1000;
    awakeAt = 0;
    if (!frame) frame = requestAnimationFrame(tick);
  }

  grid = fitCanvas(canvas, cell);
  draw(still ? end + 1 : 0, 0, 0); // under reduced motion: once, in its finished state
  const resized = new ResizeObserver(() => {
    grid = fitCanvas(canvas, cell);
    if (still || !frame) draw(still || startedAt !== null ? end + 1 : 0, 0, 0);
  });
  resized.observe(canvas);
  const watch = new IntersectionObserver(
    ([entry]) => {
      visible = !!entry?.isIntersecting;
      if (still || !visible) return;
      if (startedAt === null && entry.intersectionRatio >= 0.75) play();
      else if (!frame) frame = requestAnimationFrame(tick);
    },
    { threshold: [0, 0.75] },
  );
  watch.observe(canvas);
  const replay = (e) => {
    if (replayOnHover && e.pointerType === "mouse" && awakeAt && end > 0) play();
  };
  canvas.addEventListener("pointerenter", replay);

  return {
    play,
    destroy() {
      cancelAnimationFrame(frame);
      watch.disconnect();
      resized.disconnect();
      canvas.removeEventListener("pointerenter", replay);
    },
  };
}
