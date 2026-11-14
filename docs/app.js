// Exhibit A: every mark on this page is a grid of small glyphs on a plain 2D canvas.
// Readable text stands for what is public, rolling cipher glyphs for what is confidential.
// All numbers come from data.json, written by build.py.

import { glyphField, quietEllipse } from "./glyph/glyph-field.js";
import { swapCoin } from "./glyph/swap-coin.js";

const RAMP = ".,:;'-+/\\|!*=%#&$@";
const CW = 5;          // glyph cell, CSS pixels
const CH = 9;
const INK = {
  clear: "rgba(236,231,222,0.92)",
  cipher: "rgba(200,164,106,0.9)",
  ghost: "rgba(236,231,222,0.3)",
  near: "rgba(0,236,151,0.92)",
  faint: "rgba(236,231,222,0.14)",
  mark: "rgba(236,231,222,0.36)",
};
const STYLES = Object.keys(INK);
const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
const sheets = new Set();

const hash = (c, r) => (Math.imul(c + 11, 73856093) ^ Math.imul(r + 7, 19349663)) >>> 0;
const roll = () => RAMP.charCodeAt(7 + Math.floor(Math.random() * 11));

function glyph(part, c, r) {
  if (part.style === "cipher") return roll();
  if (part.style === "ghost") return RAMP.charCodeAt(2 + (hash(c, r) % 8));
  if (part.style === "faint") return RAMP.charCodeAt(hash(c, r) % 3);
  if (part.style === "mark") return 58; // ":"
  const text = part.text || "#";
  return text.charCodeAt((c + r * 2) % text.length);
}

class Sheet {
  constructor(canvas, paint, cell = { w: CW, h: CH, font: 8 }) {
    this.canvas = canvas;
    this.paint = paint;
    this.cw = cell.w;
    this.ch = cell.h;
    this.font = cell.font;
    this.ctx = canvas.getContext("2d");
    this.cols = 0;
    this.rows = 0;
    this.cipher = [];
    this.seen = false;
    sheets.add(this);
    new ResizeObserver(() => this.layout()).observe(canvas);
    new IntersectionObserver(([entry]) => { this.seen = entry.isIntersecting; }).observe(canvas);
  }

  layout() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    if (!w || !h) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.w = w;
    this.h = h;
    this.cols = Math.floor(w / this.cw);
    this.rows = Math.floor(h / this.ch);
    this.style = new Uint8Array(this.cols * this.rows);
    this.code = new Uint8Array(this.cols * this.rows);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.ctx.font = `${this.font}px "JetBrains Mono", ui-monospace, Menlo, monospace`;
    this.ctx.textBaseline = "top";
    this.paint(this);
    this.draw();
  }

  // row 0 is the bottom row
  put(col, row, part) {
    if (col < 0 || row < 0 || col >= this.cols || row >= this.rows) return;
    const code = glyph(part, col, row);
    if (code === 32) return;
    const i = row * this.cols + col;
    this.style[i] = STYLES.indexOf(part.style) + 1;
    this.code[i] = code;
  }

  place(i) {
    const col = i % this.cols;
    const row = (i - col) / this.cols;
    return [col * this.cw, this.h - (row + 1) * this.ch];
  }

  draw() {
    const { ctx } = this;
    ctx.clearRect(0, 0, this.w, this.h);
    this.cipher = [];
    for (let s = 1; s <= STYLES.length; s++) {
      ctx.fillStyle = INK[STYLES[s - 1]];
      for (let i = 0; i < this.style.length; i++) {
        if (this.style[i] !== s) continue;
        const [x, y] = this.place(i);
        ctx.fillText(String.fromCharCode(this.code[i]), x, y + 1);
        if (STYLES[s - 1] === "cipher") this.cipher.push(i);
      }
    }
  }

  // re-roll a few cipher glyphs so confidential marks never settle
  tick() {
    if (!this.seen || !this.cipher.length) return;
    const { ctx } = this;
    ctx.fillStyle = INK.cipher;
    for (let k = Math.max(1, Math.round(this.cipher.length * 0.025)); k > 0; k--) {
      const i = this.cipher[Math.floor(Math.random() * this.cipher.length)];
      const [x, y] = this.place(i);
      this.code[i] = roll();
      ctx.clearRect(x, y, this.cw, this.ch);
      ctx.fillText(String.fromCharCode(this.code[i]), x, y + 1);
    }
  }
}

if (!still) setInterval(() => sheets.forEach((sheet) => sheet.tick()), 150);
document.fonts?.ready.then(() => sheets.forEach((sheet) => sheet.layout()));

// Stacked columns. items[i] is a list of parts {v, style, text}, bottom first.
function columns(sheet, items, max, marks = []) {
  const { cols, rows } = sheet;
  const n = items.length;
  const spaced = cols >= n * 3;
  sheet.index = new Int16Array(cols).fill(-1);
  for (let c = 0; c < cols; c++) {
    const a = Math.min(n - 1, Math.floor((c * n) / cols));
    const next = Math.floor(((c + 1) * n) / cols);
    sheet.index[c] = a;
    if (spaced && next !== a) continue; // a one-cell gap between bars
    const b = spaced ? a + 1 : Math.max(a + 1, Math.min(n, next));
    let sum = 0;
    for (let p = 0; p < items[a].length; p++) {
      let v = 0;
      for (let i = a; i < b; i++) v += items[i][p].v;
      const from = Math.round((sum / max) * rows);
      sum += v / (b - a);
      const to = Math.round((sum / max) * rows);
      for (let r = from; r < to; r++) sheet.put(c, r, items[a][p]);
    }
    const mark = marks.find((m) => m.index === a && sheet.index[c - 1] !== a);
    if (mark) {
      mark.left = (c * sheet.cw) / sheet.w;
      for (let r = Math.round((sum / max) * rows) + 1; r < rows; r++) sheet.put(c, r, { style: "mark" });
    }
  }
}

// Plays a chart through time: a cursor sweeps left to right and the chart is drawn behind it.
function playback(box, canvas, sheet, label, marks, button) {
  const SECONDS = 4.5;
  const SLOPE = 0.12; // width of the rising edge, as a share of the chart
  const cursor = document.createElement("div");
  cursor.className = "cursor";
  cursor.innerHTML = "<span></span>";
  box.append(cursor);
  const markBox = box.querySelector(".marks");
  let raf = 0;
  const set = (p) => {
    // Everything left of a slanted line is shown: a column starts at its foot and is whole once
    // the sweep has moved on by SLOPE, so the chart grows to the right and upwards together.
    const foot = p * (1 + SLOPE) * 100;
    const head = foot - SLOPE * 100;
    canvas.style.clipPath = `polygon(0 0, ${head.toFixed(2)}% 0, ${foot.toFixed(2)}% 100%, 0 100%)`;
    cursor.style.left = `${Math.min(100, foot).toFixed(2)}%`;
    cursor.classList.toggle("flip", p > 0.5);
    const i = sheet.index?.[Math.max(0, Math.min(sheet.cols - 1, Math.floor(Math.min(1, foot / 100) * sheet.cols)))];
    if (i != null && i >= 0) cursor.firstChild.innerHTML = label(i);
    markBox?.classList.toggle("shown", marks.every((m) => m.left == null || foot / 100 >= m.left));
  };
  const run = () => {
    cancelAnimationFrame(raf);
    box.classList.remove("done");
    const from = performance.now();
    const step = (ms) => {
      const p = Math.min(1, (ms - from) / (SECONDS * 1000));
      set(p);
      if (p < 1) raf = requestAnimationFrame(step);
      else box.classList.add("done");
    };
    raf = requestAnimationFrame(step);
  };
  if (still) {
    set(1);
    box.classList.add("done");
    return;
  }
  set(0);
  new IntersectionObserver(([entry], watch) => {
    if (!entry.isIntersecting) return;
    watch.disconnect();
    run();
  }, { threshold: 0.35 }).observe(box);
  button?.addEventListener("click", run);
}

function plot(id, items, max, { tip, marks = [], play, cell } = {}) {
  const box = document.querySelector(`#${id} .plot`);
  const canvas = box.querySelector("canvas");
  const tipBox = box.querySelector(".tip");
  const markBox = box.querySelector(".marks");
  const sheet = new Sheet(canvas, (s) => {
    columns(s, items, max, marks);
    if (markBox) markBox.innerHTML = marks.filter((m) => m.left != null).map((m) => `<span style="left:${(m.left * 100).toFixed(2)}%">${m.label}</span>`).join("");
  }, cell);
  if (play) playback(box, canvas, sheet, play, marks, document.querySelector(`#${id} .replay`));
  else box.classList.add("reveal");
  if (tip) {
    box.addEventListener("pointermove", (event) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const i = sheet.index?.[Math.max(0, Math.min(sheet.cols - 1, Math.floor(x / sheet.cw)))];
      if (i == null || i < 0) return;
      tipBox.innerHTML = tip(i);
      tipBox.style.display = "block";
      const width = tipBox.offsetWidth;
      tipBox.style.left = `${Math.max(0, Math.min(rect.width - width, x > rect.width / 2 ? x - width - 14 : x + 14))}px`;
    });
    box.addEventListener("pointerleave", () => { tipBox.style.display = "none"; });
  }
  return sheet;
}

// Horizontal bars whose glyphs flow: the words drift slowly through each bar at 60 fps.
const flows = new Set();
const DRIFT = 9; // CSS pixels a second

class Flow {
  constructor(canvas, parts) {
    this.canvas = canvas;
    this.parts = parts;
    this.ctx = canvas.getContext("2d");
    this.seen = false;
    flows.add(this);
    new ResizeObserver(() => this.layout()).observe(canvas);
    new IntersectionObserver(([entry]) => { this.seen = entry.isIntersecting; }).observe(canvas);
  }

  layout() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    if (!w || !h) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.w = w;
    this.h = h;
    this.cols = Math.floor(w / CW);
    this.rows = Math.floor(h / CH);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.ctx.font = `8px "JetBrains Mono", ui-monospace, Menlo, monospace`;
    this.ctx.textBaseline = "top";
    this.frame(performance.now());
  }

  frame(ms) {
    if (!this.w) return;
    const { ctx } = this;
    ctx.clearRect(0, 0, this.w, this.h);
    ctx.fillStyle = INK.faint;
    for (let c = 0; c < this.cols; c += 2) ctx.fillText(".", c * CW, this.h - CH + 1);
    const moved = still ? 0 : (ms / 1000) * DRIFT;
    const base = Math.floor(moved / CW);
    const part = moved - base * CW;
    let top = 0;
    for (const bar of this.parts) {
      const lines = bar.rows || this.rows;
      const wide = Math.max(bar.share > 0 ? 1 : 0, Math.round(bar.share * this.cols));
      const text = bar.text || "#";
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, top, wide * CW, lines * CH);
      ctx.clip();
      ctx.clearRect(0, top, wide * CW, lines * CH);
      ctx.fillStyle = INK[bar.style];
      for (let r = 0; r < lines; r++) {
        for (let k = 0; k <= wide; k++) {
          const code = bar.style === "ghost" ? RAMP.charCodeAt(2 + (hash(k + base, r) % 8)) : text.charCodeAt((k + base + r * 2) % text.length);
          if (code !== 32) ctx.fillText(String.fromCharCode(code), k * CW - part, top + r * CH + 1);
        }
      }
      ctx.restore();
      top += lines * CH;
    }
  }
}

if (!still) {
  const loop = (ms) => {
    flows.forEach((flow) => flow.seen && flow.frame(ms));
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}
document.fonts?.ready.then(() => flows.forEach((flow) => flow.layout()));

function bars(id, rows) {
  const box = document.querySelector(`#${id} .bars`);
  box.innerHTML = "";
  for (const row of rows) {
    const el = document.createElement("div");
    el.className = `bar reveal side${row.parts.length > 1 ? " two" : ""}`;
    el.innerHTML = `<span title="${row.label}">${row.label}</span><div><canvas aria-hidden="true"></canvas></div><span>${row.value}</span>`;
    box.append(el);
    new Flow(el.querySelector("canvas"), row.parts);
  }
}

// ---------- words and numbers ----------

const usd = (x) => {
  const a = Math.abs(x);
  if (a >= 1e9) return `$${(x / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `$${(x / 1e6).toFixed(a >= 1e8 ? 0 : 1)}M`;
  if (a >= 1e4) return `$${Math.round(x / 1e3)}K`;
  return `$${Math.round(x).toLocaleString("en-US")}`;
};
const pct = (x, digits = 0) => `${(x * 100).toFixed(digits)}%`;
const int = (x) => Math.round(x).toLocaleString("en-US");
const date = (iso) => new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const shortDate = (iso) => new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
const NAMES = { swapkit: "SwapKit", lifi: "LI.FI", "(none)": "no label", zodl: "Zodl", rango: "Rango", trustwallet: "Trust Wallet" };
const nice = (name) => NAMES[name] || name.replace(/\.near$/, "");
const word = (name) => `${nice(name).toLowerCase().replace(/[^a-z0-9.]/g, "")} `;
const fill = (key, html) => document.querySelectorAll(`[data-f="${key}"]`).forEach((el) => { el.innerHTML = html; });

const data = await (await fetch("data.json", { cache: "no-store" })).json();
const { partner: p, official: o, dark, history, daily, model } = data;
const kind = Object.fromEntries(data.kinds.map((k) => [k.name, k]));
const win = data.window;

fill("window", `${date(win.from)} to ${date(win.to)}`);
fill("built", data.built);
fill("winFrom", shortDate(win.from));
fill("winTo", shortDate(win.to));

// ---------- the opening lines ----------
{
  const lead = p.top_front_by_fees;
  const mo = data.monthly || [];
  const month = (m) => new Date(`${m}-01T00:00:00Z`).toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });
  fill("briefWhat", "Someone with a hardware wallet swaps Bitcoin for dollars and never learns which chain did the work. It was NEAR.");
  fill("briefFor", `<b>${int(p.done)}</b> partner swaps in ${win.days} days. Bitcoin holders pay <b>${kind.Bitcoin.bps.toFixed(0)} bps</b> for them. Then in about a week <b>${pct(dark.share_last)}</b> of the volume went private, and nobody left.`);
  fill("briefAgainst", `One integrator, ${nice(lead.name)}, produces <b>${pct(lead.fee_share)}</b> of partner fees. A NEAR wallet is named on <b>${pct(p.near_cut)}</b> of them.`);
  fill("briefWatch", mo.length > 1
    ? `The cut. NEAR kept <b>${pct(mo[0].capture)}</b> of gross fees in ${month(mo[0].month)} and <b>${pct(mo[mo.length - 1].capture)}</b> in ${month(mo[mo.length - 1].month)}.`
    : `The cut. NEAR's own schedule says half of partner fees; the records show <b>${pct(p.near_cut)}</b>.`);
  // The rule under the headline: a line of glyphs, the first stretch of it still cipher.
  new Sheet(document.querySelector(".rule"), (sheet) => {
    for (let c = 0; c < sheet.cols; c++) sheet.put(c, 0, { style: c < sheet.cols * 0.18 ? "cipher" : "faint" });
  });
  // The four lines are linked: the first time they are on screen the line is drawn down from one to the next.
  const terms = document.querySelector(".terms");
  if (still) terms.classList.add("in");
  else new IntersectionObserver(([entry], watch) => {
    if (!entry.isIntersecting) return;
    terms.classList.add("in");
    watch.disconnect();
  }, { threshold: 0.2 }).observe(terms);
}

// ---------- the week it went dark ----------
{
  const days = dark.days.filter((d) => d.day >= "2026-08-01");
  const max = Math.max(...days.map((d) => d.public + d.confidential));
  plot("dark", days.map((d) => [
    { v: d.public, style: "clear", text: "public " },
    { v: d.confidential, style: "cipher" },
  ]), max, {
    marks: [{ index: days.findIndex((d) => d.day === "2026-10-27"), label: "27 Oct<br>partner swaps start<br>settling confidentially" }],
    play: (i) => `<b>${shortDate(days[i].day)}</b> · ${pct(days[i].confidential / (days[i].public + days[i].confidential))} confidential`,
    cell: { w: 3.6, h: 6.4, font: 6 },
    tip: (i) => `<b>${date(days[i].day)}</b><br>public ${usd(days[i].public)}<br>confidential ${usd(days[i].confidential)} · ${pct(days[i].confidential / (days[i].public + days[i].confidential))}`,
  });
  fill("darkLine", `Confidential volume was <b>${pct(dark.share_before)}</b> of the total in late October. From ${shortDate(dark.switch_day)} it's <b>${pct(dark.share_after)}</b>. Daily volume went from ${usd(dark.per_day_before)} to <b>${usd(dark.per_day_after)}</b>. Nobody left.`);
  fill("darkScale", `top of chart ${usd(max)} a day`);
  fill("darkFrom", shortDate(days[0].day));
  fill("darkTo", `${shortDate(dark.last.day)} · ${pct(dark.share_last)} confidential`);
}

// ---------- who pays ----------
{
  const rows = [...data.kinds].sort((a, b) => b.fee_share - a.fee_share);
  const top = Math.max(...rows.map((k) => Math.max(k.volume_share, k.fee_share)));
  bars("kinds", rows.map((k) => ({
    label: k.name,
    value: `<b>${k.bps.toFixed(0)}</b> bps`,
    parts: [
      { share: k.volume_share / top, style: "ghost", rows: 2 },
      { share: k.fee_share / top, style: "clear", text: word(k.name), rows: 3 },
    ],
  })));
  const b = kind.Bitcoin, s = kind["Stablecoin pair"];
  fill("kindsLine", `Bitcoin is <b>${pct(b.volume_share)}</b> of partner volume and <b>${pct(b.fee_share)}</b> of the fees, at ${b.bps.toFixed(0)} bps. Stablecoin pairs do ${pct(s.volume_share)} of the volume and pay ${s.bps.toFixed(0)}. Guess which customer you want.`);
}

// ---------- where it happens ----------
{
  const rows = data.front_ends.slice(0, 8);
  bars("fronts", rows.map((f) => ({
    label: nice(f.name),
    value: `<b>${f.bps.toFixed(0)}</b> bps · <i>${f.near_bps.toFixed(1)}</i>`,
    parts: [{ share: f.volume_share / rows[0].volume_share, style: "clear", text: word(f.name) }],
  })));
  const f = p.top_front;
  fill("frontsLine", `${nice(f.name)} (its fee accounts are named for Ledger, Trust, Tangem and Trezor) carries <b>${pct(f.volume_share)}</b> of partner volume at <b>${f.bps.toFixed(0)} bps</b>. NEAR is named on ${f.to_near < 1 ? "none" : usd(f.to_near)} of it. Everyone plugging into one venue instead of building their own: Hyperliquid ran that play for perps.`);
}

// ---------- the cut is rising: month by month ----------
if (data.monthly && data.monthly.length > 2) {
  const mo = data.monthly;
  const name = (m) => new Date(`${m}-01T00:00:00Z`).toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });
  const top = Math.max(...mo.map((r) => r.fees));
  plot("monthly", mo.map((r) => [
    { v: r.revenue, style: "near", text: "near" },
    { v: r.fees - r.revenue, style: "ghost" },
  ]), top, {
    tip: (i) => `<b>${name(mo[i].month)}</b><br>gross fees ${usd(mo[i].fees)}<br>NEAR kept ${usd(mo[i].revenue)} · ${pct(mo[i].capture)}`,
  });
  const first = mo[0], last = mo[mo.length - 1];
  fill("monthlyLine", `NEAR kept <b>${pct(first.capture)}</b> of gross fees in ${name(first.month)} and <b>${pct(last.capture)}</b> in ${name(last.month)}. Its revenue went from ${usd(first.revenue)} to <b>${usd(last.revenue)}</b> a month. Nobody announced a new fee policy. The number just kept going up.`);
  fill("monthlyScale", `top of chart ${usd(top)} a month`);
  fill("monthlyFrom", name(first.month));
  fill("monthlyTo", name(last.month));
} else {
  document.querySelector("#monthly").closest("section").remove();
}

// ---------- where the fees go ----------
{
  const rows = data.recipients.slice(0, 9);
  bars("recipients", rows.map((r) => ({
    label: r.name,
    value: `<b>${usd(r.usd)}</b> · ${pct(r.share)}`,
    parts: [{ share: r.usd / rows[0].usd, style: r.near ? "near" : "clear", text: `${r.name.replace(/\.near$/, "")} ` }],
  })));
  fill("recipientsLine", `Partners charged <b>${usd(p.fees)}</b> in ${win.days} days. A NEAR wallet is named on <b>${usd(p.to_near)}</b> of it. That's ${pct(p.near_cut)}. The published schedule says half.`);
}

// ---------- from nothing, and the mix ----------
{
  const label = (h) => (h.average ? "last 30 days, daily average" : date(h.day));
  plot("growth", history.map((h) => [{ v: h.fees, style: "clear", text: "fees" }]), Math.max(...history.map((h) => h.fees)), {
    tip: (i) => `<b>${label(history[i])}</b><br>fees ${usd(history[i].fees)} · ${int(history[i].swaps)} swaps<br>${history[i].front_ends} front-ends · ${nice(history[i].top)} ${pct(history[i].top_share)}`,
  });
  const g = data.growth;
  fill("growthLine", `<b>${usd(g.from_fees)}</b> in fees on ${date(g.from_day)}. Not a typo. It's <b>${usd(g.to_fees)}</b> a day now, and front-ends active in a day went from ${g.from_fronts} to ${g.to_fronts}.`);
  fill("growthScale", `top of chart ${usd(Math.max(...history.map((h) => h.fees)))} a day`);
  fill("growthFrom", shortDate(history[0].day) + " " + history[0].day.slice(0, 4));

  const part = (h, name) => h.kinds[name] || 0;
  plot("mix", history.map((h) => [
    { v: part(h, "Bitcoin"), style: "clear", text: "btc" },
    { v: part(h, "Zcash"), style: "cipher" },
    { v: part(h, "Stablecoin pair"), style: "ghost" },
    { v: 1 - part(h, "Bitcoin") - part(h, "Zcash") - part(h, "Stablecoin pair"), style: "faint" },
  ]), 1, {
    tip: (i) => `<b>${label(history[i])}</b><br>Bitcoin ${pct(part(history[i], "Bitcoin"))} · Zcash ${pct(part(history[i], "Zcash"))}<br>stablecoin pairs ${pct(part(history[i], "Stablecoin pair"))}`,
  });
  const peak = (name) => history.filter((h) => !h.average).reduce((a, h) => (part(h, name) > part(a, name) ? h : a));
  const now = history[history.length - 1];
  fill("mixLine", `Bitcoin was <b>${pct(part(peak("Bitcoin"), "Bitcoin"))}</b> of the volume on ${date(peak("Bitcoin").day)}, Zcash <b>${pct(part(peak("Zcash"), "Zcash"))}</b> on ${date(peak("Zcash").day)}, and stablecoin pairs are <b>${pct(part(now, "Stablecoin pair"))}</b> now. The story keeps changing. The fees keep showing up.`);
}

// ---------- it breaks sometimes, and the part we can count ----------
{
  const worst = p.worst_day;
  plot("broken", daily.map((d) => [{ v: d.not_done_share, style: "clear", text: "fail" }]), worst.not_done_share, {
    tip: (i) => `<b>${date(daily[i].day)}</b><br>${int(daily[i].not_done)} of ${int(daily[i].swaps)} swaps did not complete · ${pct(daily[i].not_done_share, 1)}`,
  });
  fill("brokenLine", `On ${shortDate(worst.day)}, switch week, <b>${pct(worst.not_done_share)}</b> of swaps were refunded or failed. Ugly. On the other days it's <b>${pct(p.not_done_share_calm, 1)}</b>.`);
  fill("brokenScale", `top of chart ${pct(worst.not_done_share)}`);

  const max = Math.max(...daily.map((d) => d.official));
  plot("share", daily.map((d) => [
    { v: d.both_sides, style: "clear", text: "swap" },
    { v: Math.max(0, d.official - d.both_sides), style: "ghost" },
  ]), max, {
    tip: (i) => `<b>${date(daily[i].day)}</b><br>partner swaps, both sides ${usd(daily[i].both_sides)} · ${pct(daily[i].share)}<br>official volume ${usd(daily[i].official)}`,
  });
  fill("shareLine", `The official figure counts both sides of every swap, so we count ours the same way: partner swaps are <b>${pct(p.share_of_official)}</b> of official volume and <b>${pct(p.fee_share_of_official)}</b> of official fees. The other ${pct(1 - p.share_of_official)} is mostly stablecoins, paying about <b>${o.rest_bps.toFixed(0)} bps</b>.`);
  fill("shareScale", `top of chart ${usd(max)} a day`);
}

// ---------- the other side of the ledger: token by token ----------
if (data.tokens) {
  const t = data.tokens;
  const rows = t.rows.slice(0, 8);
  const top = rows[0].official;
  bars("tokens", rows.map((r) => ({
    label: r.symbol,
    value: `<b>${pct(r.share)}</b> · ${usd(r.official)}`,
    parts: [
      { share: r.official / top, style: "ghost", rows: 2 },
      { share: r.partner / top, style: "clear", text: `${r.symbol.toLowerCase()} `, rows: 3 },
    ],
  })));
  const pick = (symbol) => t.rows.find((r) => r.symbol === symbol);
  const x = pick("XRP"), b = pick("BTC"), u = pick("USDT");
  const mine = data.capture ? data.capture.front_end / (data.capture.front_end + data.capture.partners + data.capture.quote_improvement) : null;
  fill("tokensLine", `Token by token, partner swaps are <b>${pct(b.share)}</b> of official Bitcoin volume${x ? " and " + pct(x.share) + " of XRP" : ""}, but only <b>${pct(u.share)}</b> of USDT. <b>${pct(t.stable_gap_share)}</b> of the gap is USDT and USDC moving outside the partner API, at about ${o.rest_bps.toFixed(0)} bps${mine ? "; NEAR's own dashboard credits its front-end with " + pct(mine) + " of what NEAR keeps" : ""}. NEAR earns more from the half it owns than from the half that made it famous.`);
} else {
  document.querySelector("#tokens").closest("section").remove();
}

// ---------- the scorecard: groups on the left, one group opened on the right ----------
{
  const show = (k) => {
    const v = k.value;
    if (k.kind === "usd") return usd(v);
    if (k.kind === "pct") return pct(v, v < 0.1 || v > 1 ? 1 : 0);
    if (k.kind === "bps") return `${v.toFixed(v < 10 ? 1 : 0)} bps`;
    if (k.kind === "x") return `${v.toFixed(1)}×`;
    if (k.kind === "near") return `${int(v)} NEAR`;
    if (k.kind === "bytes") return `${(v / 1e6).toFixed(0)} MB`;
    return int(v);
  };
  const daily = data.daily;
  const span = (rows) => [shortDate(rows[0].day), shortDate(rows[rows.length - 1].day)];
  const shares = (rows) => rows.slice().sort((a, b) => b.fee_share - a.fee_share).slice(0, 5).map((r) => ({ name: nice(r.name), share: r.fee_share }));
  const darkDays = dark.days.filter((d) => d.day >= "2026-09-01" && d.public != null && d.confidential != null);
  const inflow = (data.chain_history?.days || []).filter((d) => d.inflow != null);
  const past = (data.history || []).filter((d) => d.fees != null);

  // What each group opens with: its mark, its lead figure, a picture, and where the numbers come from.
  const GROUPS = {
    Scale: {
      tile: ["  !", " !!", "!!!"], lead: "Swap value settled", see: ["#share", "The part we can count"],
      trace: () => ({ items: daily.map((d) => [{ v: d.volume, style: "clear", text: "swaps " }]), cap: "Partner swap value, a day", range: span(daily) }),
      trail: ["Explorer API, DefiLlama", "Each partner swap counted once", "python3 build.py"],
    },
    Take: {
      tile: ["$$$", "$$.", "$.."], lead: "Fees partners charge", see: ["#flow", "Follow the fee"],
      trace: () => ({ items: daily.map((d) => [{ v: d.to_near, style: "near", text: "near" }, { v: d.fees - d.to_near, style: "clear", text: "fees " }]), cap: "Partner fees, a day. Green is the part named to a NEAR wallet", range: span(daily) }),
      trail: ["Explorer API, DefiLlama fees", "Fees summed swap by swap", "python3 build.py"],
    },
    Customers: {
      tile: ["@.@", ".@.", "@.@"], lead: "Coins with no exchange at home", see: ["#kinds", "Who's paying?"],
      split: () => ({ rows: shares(data.kinds), cap: "Share of partner fees, by what is swapped" }),
      trail: ["Explorer API", "Grouped by the coins on each side", "python3 build.py"],
    },
    Concentration: {
      tile: [":::", ":@:", ":::"], lead: "Largest front-end, share of fees", see: ["#fronts", "Nobody opens a NEAR app"],
      split: () => ({ rows: shares(data.front_ends), cap: "Share of partner fees, by front-end" }),
      trail: ["Explorer API", "Grouped by referral name", "python3 build.py"],
    },
    Token: {
      tile: ["/-\\", "|*|", "\\-/"], lead: "Revenue against new issuance", see: ["#model", "What's the trade?"],
      trace: () => inflow.length ? { items: inflow.map((d) => [{ v: Math.max(0, d.inflow), style: "near", text: "near" }]), cap: "NEAR arriving in the revenue wallets, a day", range: span(inflow) } : null,
      trail: ["NEAR archive node", "Balances and supply at each day's end", "python3 -m pipeline.model"],
    },
    Privacy: {
      tile: ["%#&", "$@#", "&%$"], lead: "Confidential share of volume", see: ["#dark", "The week it went dark"],
      trace: () => ({ items: darkDays.map((d) => [{ v: d.public, style: "clear", text: "public " }, { v: d.confidential, style: "cipher" }]), cap: "Official volume, a day. Brass is confidential", range: span(darkDays) }),
      trail: ["NEAR's Dune query 5179085", "Confidential over total volume", "queries/01_public_vs_confidential.sql"],
    },
    Reliability: {
      tile: ["==/", " / ", "/=="], lead: "Swaps that fail or refund", see: ["#broken", "It breaks sometimes"],
      trace: () => ({ items: daily.map((d) => [{ v: d.not_done_share, style: "clear", text: "refund " }]), cap: "Share of swaps that fail or refund, a day", range: span(daily) }),
      trail: ["Explorer API", "Failed or refunded over all swaps", "python3 build.py"],
    },
    Growth: {
      tile: ["  /", " / ", "/  "], lead: "Partner fees a day, against a year ago", see: ["#growth", "From lunch money"],
      trace: () => past.length ? { items: past.map((d) => [{ v: d.fees, style: "clear", text: "fees " }]), cap: "Partner fees a day, on sampled days. The last bar is this window", range: [`${shortDate(past[0].day)} ${past[0].day.slice(0, 4)}`, `${shortDate(win.to)} ${win.to.slice(0, 4)}`] } : null,
      trail: ["Explorer API, DefiLlama", "The same days, a year apart", "python3 build.py"],
    },
  };
  const STEPS = ["From", "How", "Re-run"];
  const groups = Object.keys(GROUPS).map((name) => {
    const rows = data.kpis.filter((k) => k.group === name);
    const lead = rows.find((k) => k.name === GROUPS[name].lead) || rows[0];
    return { ...GROUPS[name], name, rows, lead };
  }).filter((g) => g.rows.length && document.querySelector(g.see[0]));

  const root = document.querySelector("#score");
  const list = root.querySelector(".scList");
  const panel = root.querySelector(".scPanel");
  const canvas = panel.querySelector("canvas");
  const splitBox = panel.querySelector(".scSplit");
  let at = 0;
  let picture = null;
  const narrow = matchMedia("(max-width: 860px)");

  list.innerHTML = `<span class="scGlow" aria-hidden="true"></span>` + groups.map((g, i) =>
    `<button type="button" role="tab" id="scTab${i}" aria-controls="scPanel"><pre class="scTile" aria-hidden="true">${g.tile.join("\n")}</pre><span>${g.name}</span><i>${show(g.lead)}</i></button>`).join("");
  const tabs = [...list.querySelectorAll("button")];
  const glow = list.querySelector(".scGlow");
  const note = panel.querySelector(".scNote");
  const cells = panel.querySelector(".scCells");
  let resting = "";

  // One highlight for the whole list. It slides to the open group; nothing blinks on and off.
  const place = (quiet) => {
    const tab = tabs[at];
    if (quiet) glow.style.transition = "none";
    glow.style.width = `${tab.offsetWidth}px`;
    glow.style.height = `${tab.offsetHeight}px`;
    glow.style.transform = `translate(${tab.offsetLeft}px, ${tab.offsetTop}px)`;
    if (quiet) requestAnimationFrame(() => { glow.style.transition = ""; });
  };
  // The line under the figures: the note of whichever figure is pointed at.
  const say = (html) => {
    if (note.innerHTML === html) return;
    note.innerHTML = html;
    if (still) return;
    note.classList.remove("fresh");
    void note.offsetWidth;
    note.classList.add("fresh");
  };
  const pointed = (event) => {
    const cell = event.target.closest?.(".scCells > div");
    say(cell ? `<b>${cell.querySelector("dt").textContent}</b> ${cell.querySelector("small").textContent}` : resting);
  };
  cells.addEventListener("pointerover", pointed);
  cells.addEventListener("focusin", pointed);
  cells.addEventListener("pointerleave", () => say(resting));
  cells.addEventListener("focusout", () => say(resting));

  const sheet = new Sheet(canvas, (s) => { if (picture) columns(s, picture.items, picture.max); }, { w: 4, h: 7, font: 6.5 });
  // A bar set in type: as many glyphs as fit the row, the share of them dense and the rest dots.
  const meter = (share, top, room) => {
    const on = Math.max(1, Math.round((share / top) * room));
    let text = "";
    for (let c = 0; c < on; c++) text += RAMP[9 + (hash(c, on) % 9)];
    return `<em>${text.replace(/&/g, "&amp;")}</em>${".".repeat(room - on)}`;
  };

  const open = (i, focus, quiet) => {
    const from = at;
    at = (i + groups.length) % groups.length;
    panel.style.setProperty("--dir", at < from ? -1 : 1); // new figures come in from the side the list moved to
    const g = groups[at];
    tabs.forEach((tab, n) => {
      tab.setAttribute("aria-selected", n === at);
      tab.tabIndex = n === at ? 0 : -1;
    });
    if (focus) tabs[at].focus();
    place(quiet);
    if (!quiet && list.scrollWidth > list.clientWidth) list.scrollTo({ left: tabs[at].offsetLeft - 16, behavior: still ? "auto" : "smooth" }); // the list is a row on a phone
    panel.setAttribute("aria-labelledby", `scTab${at}`);
    panel.querySelector("header .scTile").textContent = g.tile.join("\n");
    panel.querySelector("header h3").textContent = g.name;
    const out = panel.querySelector(".scOut");
    out.href = g.see[0];
    out.textContent = g.see[1];
    panel.querySelector(".scLead b").innerHTML = [...show(g.lead)].map((letter, n) => `<span style="--i:${n}">${letter === " " ? "&nbsp;" : letter}</span>`).join("");
    panel.querySelector(".scLead div span").textContent = g.lead.name;
    panel.querySelector(".scLead small").textContent = g.lead.note;

    const drawn = g.trace ? g.trace() : null;
    const parts = g.split ? g.split() : null;
    panel.classList.toggle("split", !drawn);
    const cap = panel.querySelectorAll(".scCap span");
    if (drawn) {
      picture = { items: drawn.items, max: Math.max(...drawn.items.map((item) => item.reduce((sum, part) => sum + part.v, 0))) || 1 };
      cap[0].textContent = drawn.cap;
      cap[1].textContent = `${drawn.range[0]} to ${drawn.range[1]}`;
      sheet.layout();
    } else if (parts) {
      const top = parts.rows[0].share;
      const fixed = narrow.matches ? 156 : 200; // the name, the figure and the gaps beside the bar
      const room = Math.max(8, Math.min(60, Math.floor((splitBox.clientWidth - fixed) / 6.95)));
      splitBox.innerHTML = parts.rows.map((r, n) => `<div style="--i:${n}"><span>${r.name}</span><code>${meter(r.share, top, room)}</code><b>${pct(r.share)}</b></div>`).join("");
      cap[0].textContent = parts.cap;
      cap[1].textContent = "30 days";
    }
    const others = g.rows.filter((k) => k !== g.lead);
    cells.innerHTML = others.map((k, n) => `<div tabindex="0" style="--i:${n}"><dd>${show(k)}</dd><dt>${k.name}</dt><small>${k.note}</small></div>`).join("");
    resting = others.length ? `${others.length} more ${others.length === 1 ? "figure" : "figures"}. Point at one for its note.` : "";
    note.innerHTML = resting;
    note.hidden = !others.length;
    panel.querySelector(".scTrail").innerHTML = g.trail.map((text, n) => `<li><span>${STEPS[n]}</span>${n === 2 ? `<code>${text.replace(/([/_])/g, "$1<wbr>")}</code>` : text}</li>`).join("");
    root.querySelector(".scCount").textContent = `${String(at + 1).padStart(2, "0")} / ${String(groups.length).padStart(2, "0")}`;
    if (!still && !quiet) {
      panel.classList.remove("fresh");
      void panel.offsetWidth;
      panel.classList.add("fresh");
    }
  };

  tabs.forEach((tab, i) => tab.addEventListener("click", () => open(i)));
  list.addEventListener("keydown", (event) => {
    const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    open(at + step, true);
  });
  root.querySelector(".scPrev").addEventListener("click", () => open(at - 1));
  root.querySelector(".scNext").addEventListener("click", () => open(at + 1));
  open(0, false, true);

  // The first time the scorecard is scrolled to, the open group plays in.
  if (!still) {
    const arrive = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      arrive.disconnect();
      open(at);
    }, { threshold: 0.3 });
    arrive.observe(panel);
  }

  // Every group opens at the height of the tallest one, so the page does not move when the group changes.
  const settle = () => {
    const was = at;
    panel.style.minHeight = "";
    if (narrow.matches) return;
    let tall = 0;
    for (let i = 0; i < groups.length; i++) {
      open(i, false, true);
      tall = Math.max(tall, panel.offsetHeight);
    }
    panel.style.minHeight = `${tall}px`;
    open(was, false, true);
  };
  let waiting = 0;
  new ResizeObserver(() => {
    clearTimeout(waiting);
    waiting = setTimeout(settle, 120);
  }).observe(root);
  document.fonts?.ready.then(settle);
}

// ---------- what the chain says ----------
if (data.chain_history && data.chain_history.days.some((d) => d.inflow != null)) {
  const ch = data.chain_history;
  const rows = ch.days.filter((d) => d.inflow != null);
  const top = Math.max(...rows.map((d) => d.inflow));
  plot("inflow", rows.map((d) => [{ v: Math.max(0, d.inflow), style: "near", text: "near" }]), top, {
    tip: (i) => `<b>${date(rows[i].day)}</b><br>${rows[i].inflow >= 0 ? "+" : ""}${int(rows[i].inflow)} NEAR · wallets hold ${int(rows[i].wallets)}${rows[i].issued != null ? `<br>net new NEAR that day ${int(rows[i].issued)}` : ""}`,
  });
  fill("inflowLine", ch.inflow_window != null && ch.issued_window != null
    ? `The three revenue wallets took in <b>${int(ch.inflow_window)} NEAR</b> over the window. The chain created <b>${int(ch.issued_window)}</b> net new NEAR in the same days. That's <b>${pct(ch.inflow_window / ch.issued_window, 1)}</b>, read from balances and supply alone: no prices, no dashboards.`
    : `NEAR arriving in the three revenue wallets each day, read from their balances at the last block of the day. ${rows.length} days so far.`);
  fill("inflowScale", `top of chart ${int(top)} NEAR a day`);
  fill("chainFrom", shortDate(rows[0].day));
  fill("chainTo", shortDate(rows[rows.length - 1].day));

  const grew = rows.filter((d) => d.state_growth != null);
  const peak = Math.max(...grew.map((d) => d.state_growth));
  const mean = (list) => list.reduce((sum, d) => sum + d.state_growth, 0) / (list.length || 1);
  const before = grew.filter((d) => d.day < "2026-11-01"), after = grew.filter((d) => d.day >= dark.switch_day);
  plot("state", grew.map((d) => [{ v: Math.max(0, d.state_growth), style: "clear", text: "bytes" }]), peak, {
    marks: [{ index: grew.findIndex((d) => d.day === "2026-10-27"), label: "27 Oct" }].filter((mark) => mark.index >= 0),
    tip: (i) => `<b>${date(grew[i].day)}</b><br>+${(grew[i].state_growth / 1e6).toFixed(1)} MB · ${(grew[i].state_bytes / 1e9).toFixed(2)} GB stored`,
  });
  document.querySelector("#state .marks")?.classList.add("shown");
  const last = grew[grew.length - 1];
  fill("stateLine", `The contract has to remember every account, key and balance, and it stores <b>${(last.state_bytes / 1e9).toFixed(1)} GB</b> of it on chain.${before.length && after.length ? ` It grew <b>${(mean(before) / 1e6).toFixed(0)} MB</b> a day before the switch and <b>${(mean(after) / 1e6).toFixed(0)} MB</b> a day after.` : ""} Nobody reports this number; anyone can read it.`);
  fill("stateScale", `top of chart ${(peak / 1e6).toFixed(0)} MB a day`);
} else {
  document.querySelector("#chain").remove();
}

// ---------- the neighbours ----------
if (data.peers) {
  const rows = data.peers.rows;
  bars("peers", rows.map((r) => ({
    label: r.name,
    value: `<b>${usd(r.volume)}</b> · ${r.near ? "one side" : "as reported"}`,
    parts: [{ share: r.volume / rows[0].volume, style: r.near ? "near" : "clear", text: `${r.name.toLowerCase().replace(/[^a-z]/g, "")} ` }],
  })));
  const rank = rows.findIndex((r) => r.near) + 1;
  const others = rows.filter((r) => !r.near).map((r) => `${r.name} ${usd(r.volume)}`).join(", ");
  fill("peersLine", `These are the venues a wallet can route a Bitcoin swap to. Over the same ${win.days} days DefiLlama shows ${others}. NEAR Intents reports ${usd(data.peers.reported)}, which is <b>${usd(o.swap_value)}</b> once each swap is counted once: number <b>${rank}</b> of ${rows.length}.`);
} else {
  document.querySelector("#peers").closest("section").remove();
}

// ---------- the tape under the header ----------

// The tape: label, value, a knot of glyphs, and on to the next, drifting slowly to the left.
const tape = (() => {
  const canvas = document.querySelector(".tape canvas");
  const ctx = canvas.getContext("2d");
  const FONT = `11.5px "JetBrains Mono", ui-monospace, Menlo, monospace`;
  const DRIFT_TAPE = 26; // CSS pixels a second
  const KNOTS = ["/:+:/", "\\=*=\\", ";'-';", "|!*!|", "+%#%+"];
  let parts = [];
  let length = 0;
  let w = 0, h = 0, seen = true;
  const live = {};

  function compose() {
    const items = [
      live.block && ["block", int(live.block)],
      live.price && ["NEAR", `$${live.price.toFixed(2)}`],
      live.held && ["revenue wallets", `${int(live.held)} NEAR`],
      ["swap value, 30 days", usd(o.swap_value)],
      ["partner swaps", int(p.done)],
      ["partner fees", `${usd(p.fees)} at ${p.bps.toFixed(0)} bps`],
      ["named to NEAR", pct(p.near_cut, 1)],
      data.monthly?.length && ["NEAR's share of gross fees", pct(data.monthly[data.monthly.length - 1].capture)],
      ["confidential", pct(dark.share_last)],
      ["revenue against new issuance", pct(model.today.covered, 1)],
      ["tripwires tripped", `${data.tripwires.filter((t) => t.tripped).length} of ${data.tripwires.length}`],
    ].filter(Boolean);
    ctx.font = FONT;
    parts = [];
    length = 0;
    items.forEach(([label, value], i) => {
      for (const [text, ink] of [[`${label}  `, "rgba(236,231,222,0.42)"], [value, "rgba(236,231,222,0.92)"], [`    ${KNOTS[i % KNOTS.length]}    `, "rgba(200,164,106,0.7)"]]) {
        const wide = ctx.measureText(text).width;
        parts.push({ text, ink, at: length });
        length += wide;
      }
    });
  }

  function frame(ms) {
    if (!w || !length) return;
    ctx.clearRect(0, 0, w, h);
    ctx.font = FONT;
    ctx.textBaseline = "middle";
    const moved = still ? 0 : ((ms / 1000) * DRIFT_TAPE) % length;
    for (let start = -moved; start < w; start += length) {
      for (const part of parts) {
        const x = start + part.at;
        if (x > w || x < -400) continue;
        ctx.fillStyle = part.ink;
        ctx.fillText(part.text, x, h / 2 + 0.5);
      }
    }
  }

  function layout() {
    w = canvas.clientWidth;
    h = canvas.clientHeight;
    if (!w || !h) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    compose();
    frame(performance.now());
  }

  new ResizeObserver(layout).observe(canvas);
  new IntersectionObserver(([entry]) => { seen = entry.isIntersecting; }).observe(canvas);
  document.fonts?.ready.then(layout);
  if (!still) {
    const loop = (ms) => {
      if (seen && !document.hidden) frame(ms);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }
  return { set(values) { Object.assign(live, values); compose(); if (still) frame(0); } };
})();

// ---------- live: read the chain and the price in the browser, now ----------
{
  const box = document.querySelector("#live");
  const text = document.querySelector("#liveText");
  const RPC = "https://rpc.mainnet.fastnear.com";
  const call = async (method, params) => {
    const reply = await fetch(RPC, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
    return (await reply.json()).result;
  };
  const built = data.chain.wallets.reduce((sum, w) => sum + w.now, 0);
  const read = async () => {
    try {
      const [block, price, ...accounts] = await Promise.all([
        call("block", { finality: "final" }),
        fetch("https://coins.llama.fi/prices/current/coingecko:near").then((r) => r.json()),
        ...data.chain.wallets.map((w) => call("query", { request_type: "view_account", finality: "final", account_id: w.account })),
      ]);
      const held = accounts.reduce((sum, a) => sum + Number(BigInt(a.amount) / 10n ** 18n) / 1e6, 0);
      const moved = held - built;
      text.innerHTML = `live · block <b>${int(block.header.height)}</b> · NEAR <b>$${price.coins["coingecko:near"].price.toFixed(2)}</b> · revenue wallets <b>${int(held)} NEAR</b> (${Math.abs(moved) < 0.5 ? "unchanged" : `${moved > 0 ? "+" : ""}${int(moved)}`} since this page was built) · supply <b>${int(Number(BigInt(block.header.total_supply) / 10n ** 24n))}</b>`;
      box.classList.add("on");
      tape.set({ block: block.header.height, price: price.coins["coingecko:near"].price, held });
    } catch {
      text.textContent = `built ${data.built}; live reads are unavailable right now`;
      box.classList.remove("on");
    }
  };
  read();
  setInterval(() => { if (!document.hidden) read(); }, 60000);
}

// ---------- the model ----------
{
  const m = model.inputs;
  const cutNow = m.fees_to_near / m.partner_fees;
  const cut = document.querySelector("#cut");
  const rest = document.querySelector("#rest");
  const grow = document.querySelector("#grow");
  const cap = document.querySelector("#cap");
  const issuedNear = m.issued_near || m.supply * m.max_inflation * m.days / 365;
  const issuance = issuedNear * m.price;
  const issuanceAt = () => issuance * (cap.value / (m.max_inflation * 100));
  const run = () => {
    const c = cut.value / 100, g = +grow.value;
    const revenue = (m.revenue - m.fees_to_near) * g + c * m.partner_fees * g + (rest.value / 1e4) * m.rest_volume * g;
    return { revenue, covered: revenue / issuanceAt() };
  };
  let meter;
  const show = () => {
    const out = run();
    document.querySelector("#cutOut").textContent = `${(+cut.value).toFixed(1)}%`;
    document.querySelector("#restOut").textContent = `${(+rest.value).toFixed(1)} bps`;
    document.querySelector("#growOut").textContent = `${(+grow.value).toFixed(2)}×`;
    document.querySelector("#covered").textContent = pct(out.covered, out.covered < 1 ? 1 : 0);
    document.querySelector("#revYear").textContent = usd(out.revenue * 365 / m.days);
    document.querySelector("#capOut").textContent = `${(+cap.value).toFixed(1)}%`;
    document.querySelector("#multiple").textContent = `${int(m.supply * m.price / (out.revenue * 365 / m.days))}×`;
    document.querySelector("#issYear").textContent = usd(issuanceAt() * 365 / m.days);
    meter?.layout();
  };
  meter = new Sheet(document.querySelector(".meter canvas"), (s) => {
    const now = Math.round(Math.min(1, model.today.covered) * s.cols);
    const to = Math.round(Math.min(1, run().covered) * s.cols);
    for (let c = 0; c < s.cols; c++) {
      for (let r = 0; r < s.rows; r++) {
        if (c < Math.min(now, to)) s.put(c, r, { style: "clear", text: "today " });
        else if (c < to) s.put(c, r, { style: "near", text: "more " });
        else if (r === 0 && c % 2 === 0) s.put(c, r, { style: "faint" });
      }
    }
  });
  const reset = () => { cut.value = (cutNow * 100).toFixed(1); rest.value = 0; grow.value = 1; cap.value = (m.max_inflation * 100).toFixed(1); show(); };
  [cut, rest, grow, cap].forEach((el) => el.addEventListener("input", show));
  document.querySelector("#reset").addEventListener("click", reset);
  reset();

  fill("modelLine", `Intents revenue was <b>${usd(m.revenue)}</b> in ${m.days} days. ${m.issued_near ? `The chain created <b>${int(m.issued_near)}</b> net new NEAR in that time (read from total supply), worth` : `New NEAR at the protocol's ${pct(m.max_inflation, 1)} setting was worth`} about <b>${usd(issuance)}</b>. The cap falls to 1.6% over two years; that vote passed on 2 Nov. Now move the levers.`);
  const even = model.breakeven;
  fill("evenLine", even.cut > 1
    ? `To match issuance at today's volume NEAR would need ${pct(even.cut)} of partner fees, which is more than all of them. At the published half it needs ${even.growth_at_half.toFixed(1)}× the volume; at today's cut, ${even.growth_at_todays_cut.toFixed(1)}×.`
    : `To match issuance at today's volume NEAR would need ${pct(even.cut)} of partner fees.`);

  const c = data.chain;
  document.querySelector("#wallets").innerHTML = `<tr><th>Revenue wallet</th><th>${c.window_days} days ago</th><th>Now</th><th>Change</th></tr>` +
    c.wallets.map((w) => `<tr><td>${w.account.split(".")[0]}</td><td>${int(w.before)}</td><td>${int(w.now)}</td><td><b>${w.now - w.before >= 0 ? "+" : ""}${int(w.now - w.before)}</b></td></tr>`).join("") +
    `<tr><td>NEAR, read from chain</td><td></td><td></td><td><b>+${int(c.moved)}</b></td></tr>`;
}

// ---------- against, tripwires, checks ----------
{
  const zec = history.filter((h) => !h.average).reduce((a, h) => ((h.kinds.Zcash || 0) > (a.kinds.Zcash || 0) ? h : a));
  const failed = p.refund_reasons.INTENT_SUBMIT_FAILED || 0;
  const issuance = model.today.issuance;
  document.querySelector("#againstList").innerHTML = [
    `<b>It's one integrator.</b> ${nice(p.top_front_by_fees.name)} produces ${pct(p.top_front_by_fees.fee_share)} of partner fees. That's ${pct(p.top_front_fee_share_of_official)} of every fee NEAR Intents reports.`,
    `<b>The cut may be thin for a reason.</b> NEAR is named on ${pct(p.near_cut)} of partner fees, and on ${p.top_front_by_fees.to_near < 1 ? "none" : usd(p.top_front_by_fees.to_near)} of ${nice(p.top_front_by_fees.name)}'s. Whoever owns the customer sets the terms.`,
    `<b>Half the volume is thin.</b> ${pct(1 - p.share_of_official)} of official volume isn't a partner swap. It's mostly stablecoins at about ${o.rest_bps.toFixed(0)} bps: NEAR's own, but not a margin that carries a token.`,
    `<b>Whales.</b> The largest 1% of swaps carry ${pct(p.top_1pct_share)} of partner volume.`,
    ...(data.kpis.find((k) => k.group === "Growth") ? [`<b>The last year was slower.</b> Partner fees a day are ${data.kpis.find((k) => k.group === "Growth").value.toFixed(1)}× what they were a year ago. Most of the climb happened before that.`] : []),
    `<b>The switch broke things.</b> ${pct(p.worst_day.not_done_share)} of swaps didn't complete on ${shortDate(p.worst_day.day)}. ${int(failed)} refunds in the window read INTENT_SUBMIT_FAILED.`,
    `<b>"Private" has an asterisk.</b> Private from the chain, not from the operator. Every swap on this page was read from NEAR's own Explorer API, after the switch.`,
    `<b>The customers move.</b> Zcash was ${pct(zec.kinds.Zcash)} of a day's volume on ${date(zec.day)}. It's ${pct(kind.Zcash.volume_share)} now.`,
    `<b>Small next to issuance.</b> ${usd(model.inputs.revenue)} of revenue in ${win.days} days against about ${usd(issuance)} of new NEAR.`,
    `<b>The official series moved the goalposts.</b> It counts confidential volume only from 1 Sep 2026, which flatters growth across that date.`,
  ].map((line) => `<li>${line}</li>`).join("");

  document.querySelector("#wires").innerHTML = data.tripwires.map((w) =>
    `<li class="${w.tripped ? "hit" : ""}"><code>${w.tripped ? "[trip]" : "[ ok ]"}</code><span>${w.name}</span><span>${pct(w.now, 1)}</span></li>`).join("");

  document.querySelector("#checks").innerHTML = data.checks.map((check) => `<div><h3>${check.name}</h3><p>${check.detail}</p>${
    check.rows ? `<table><tr><th>Day</th><th>Counted from swaps</th><th>Official fees</th></tr>${check.rows.map((r) => `<tr><td>${date(r.day)}</td><td>${usd(r.counted)}</td><td>${usd(r.official)}</td></tr>`).join("")}</table>` : ""}${
    check.tokens ? `<table><tr><th>Token</th><th>Partner swaps touching it</th><th>Official volume</th><th></th></tr>${check.tokens.map((r) => `<tr><td>${r.symbol}</td><td>${usd(r.partner)}</td><td>${usd(r.official)}</td><td><b>${pct(r.share)}</b></td></tr>`).join("")}</table>` : ""}</div>`).join("");
}

// ---------- the field behind the page ----------
glyphField(document.querySelector("#field"), { quiet: quietEllipse({ x: 0.5, y: 0.5, rx: 0.46, ry: 0.5, inner: 0.5 }) });
swapCoin(document.querySelector("#solid"));

// ---------- follow the fee: a moving picture, painted small and read back as glyphs ----------
// Each frame the scene is painted on a hidden canvas with one pixel per glyph cell, so the browser
// averages every cell; brightness picks the glyph, and coloured paint keeps its hue.
function movie(canvas, draw) {
  const cell = { w: 4, h: 7 };
  const ctx = canvas.getContext("2d");
  const small = document.createElement("canvas");
  const paint = small.getContext("2d", { willReadFrequently: true });
  const inks = new Map();
  const levels = 8;
  const inkFor = (rgb) => inks.get(rgb) ?? (inks.set(rgb, Array.from({ length: levels }, (_, i) => `rgba(${rgb},${(0.22 + (0.78 * (i + 1)) / levels).toFixed(2)})`)), inks.get(rgb));
  let w = 0, h = 0, cols = 0, rows = 0, seen = false;

  function frame(ms) {
    if (!cols) return;
    paint.setTransform(1, 0, 0, 1, 0, 0);
    paint.fillStyle = "#000";
    paint.fillRect(0, 0, cols, rows);
    paint.setTransform(cols / w, 0, 0, rows / h, 0, 0);
    paint.save();
    draw(paint, w, h, still ? 0 : ms / 1000);
    paint.restore();
    const px = paint.getImageData(0, 0, cols, rows).data;
    ctx.clearRect(0, 0, w, h);
    let last = "";
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const i = (r * cols + c) * 4;
        const R = px[i], G = px[i + 1], B = px[i + 2];
        const top = Math.max(R, G, B);
        const light = top / 255;
        if (light < 0.07) continue;
        const rgb = top - Math.min(R, G, B) > 14
          ? `${Math.round((R / top) * 8) * 32 - (R === top ? 1 : 0)},${Math.round((G / top) * 8) * 32 - (G === top ? 1 : 0)},${Math.round((B / top) * 8) * 32 - (B === top ? 1 : 0)}`
          : "236,231,222";
        const ink = inkFor(rgb)[Math.min(levels - 1, Math.floor(light * levels))];
        if (ink !== last) { ctx.fillStyle = ink; last = ink; }
        const at = Math.max(0, Math.min(RAMP.length - 1, Math.floor(light * RAMP.length) + (hash(c, r) % 3) - 1));
        ctx.fillText(RAMP[at], c * cell.w + cell.w / 2, r * cell.h + cell.h / 2);
      }
    }
  }

  function layout() {
    w = canvas.clientWidth;
    h = canvas.clientHeight;
    if (!w || !h) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    cols = Math.floor(w / cell.w);
    rows = Math.floor(h / cell.h);
    small.width = cols;
    small.height = rows;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.font = `7px ui-monospace, "SF Mono", Menlo, monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    frame(performance.now());
  }

  new ResizeObserver(layout).observe(canvas);
  new IntersectionObserver(([entry]) => { seen = entry.isIntersecting; }).observe(canvas);
  if (!still) {
    const loop = (ms) => {
      if (seen && !document.hidden) frame(ms);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }
}

{
  const GREEN = [0, 236, 151];
  const BRAND = { Bitcoin: [247, 147, 26], Zcash: [244, 183, 40] };
  const SHORT = { "Everything else": "Other", "Stablecoin pair": "Stables", "Other UTXO coin": "LTC, DOGE" };
  const left = [...data.kinds].sort((a, b) => b.fee_share - a.fee_share).map((k) => ({ name: k.name, share: k.fee_share, ink: BRAND[k.name] }));
  const named = data.recipients.slice(0, 7);
  const nearShare = p.near_cut;
  const right = named.filter((r) => !r.near).slice(0, 5).map((r) => ({ name: r.name.replace(/\.near$/, ""), share: r.share }));
  right.push({ name: "NEAR", share: nearShare, near: true });
  right.sort((a, b) => b.share - a.share);
  right.push({ name: "everyone else", share: Math.max(0, 1 - right.reduce((sum, r) => sum + r.share, 0)) });

  const grey = (v) => { const n = Math.round(v * 255); return `rgb(${n},${n},${n})`; };
  const tint = (v, [r, g, b]) => `rgb(${Math.round(r * v)},${Math.round(g * v)},${Math.round(b * v)})`;

  // Where everything sits, for a box of w by h. Used by the picture and by the labels.
  const plan = (w, h) => {
    const narrow = w < 560;
    const side = narrow ? 0.27 : 0.2;
    const gap = 9, pad = 6, node = 9;
    const body = h - pad * 2 - gap * (Math.max(left.length, right.length) - 1);
    const stack = (list, x) => {
      let y = pad + (h - pad * 2 - body - gap * (list.length - 1)) / 2;
      return list.map((item) => {
        const tall = Math.max(3, item.share * body);
        const out = { ...item, x, y, tall, mid: y + tall / 2 };
        y += tall + gap;
        return out;
      });
    };
    const through = body * 0.44; // everything squeezes through the venue
    const box = { x: w * 0.47, w: w * 0.06, y: (h - through) / 2, h: through };
    const dock = (list) => {
      let y = box.y;
      return list.map((item) => { const from = y; y += item.share * through; return [from, y]; });
    };
    return { narrow, side, node, box, left: stack(left, w * side), right: stack(right, w * (1 - side) - node), inL: dock(left), outR: dock(right) };
  };

  const draw = (ctx, w, h, t) => {
    const s = plan(w, h);
    const band = (xa, a0, a1, xb, b0, b1, ink, phase) => {
      const bend = (xb - xa) * 0.5;
      ctx.beginPath();
      ctx.moveTo(xa, a0);
      ctx.bezierCurveTo(xa + bend, a0, xb - bend, b0, xb, b0);
      ctx.lineTo(xb, b1);
      ctx.bezierCurveTo(xb - bend, b1, xa + bend, a1, xa, a1);
      ctx.closePath();
      ctx.fillStyle = ink ? tint(0.3, ink) : grey(0.17);
      ctx.fill();
      ctx.save();
      ctx.clip();
      ctx.fillStyle = ink ? tint(1, ink) : grey(0.66);
      const top = Math.min(a0, b0) - 2, tall = Math.max(a1, b1) - top + 2;
      for (let x = xa - 56 + ((t * 30 + phase) % 56); x < xb; x += 56) ctx.fillRect(x, top, 20, tall);
      ctx.restore();
    };
    s.left.forEach((n, i) => band(n.x + s.node, n.y, n.y + n.tall, s.box.x, s.inL[i][0], Math.max(s.inL[i][1], s.inL[i][0] + 1.5), null, i * 19));
    s.right.forEach((n, i) => band(s.box.x + s.box.w, s.outR[i][0], Math.max(s.outR[i][1], s.outR[i][0] + 1.5), n.x, n.y, n.y + n.tall, n.near ? GREEN : null, i * 23 + 11));
    // the venue: a dark box with a bright rim
    ctx.fillStyle = grey(0.1);
    ctx.fillRect(s.box.x, s.box.y - 4, s.box.w, s.box.h + 8);
    ctx.strokeStyle = grey(1);
    ctx.lineWidth = 8;
    ctx.strokeRect(s.box.x + 4, s.box.y - 4, s.box.w - 8, s.box.h + 8);
    for (const n of s.left) { ctx.fillStyle = n.ink ? tint(1, n.ink) : grey(1); ctx.fillRect(n.x, n.y, s.node, n.tall); }
    for (const n of s.right) { ctx.fillStyle = n.near ? tint(1, GREEN) : grey(1); ctx.fillRect(n.x, n.y, s.node, n.tall); }
  };

  const box = document.querySelector("#flow .flowBox");
  const canvas = box.querySelector("canvas");
  const labels = box.querySelector(".flowLabels");
  const write = () => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w) return;
    const s = plan(w, h);
    const width = `calc(${(s.side * 100).toFixed(1)}% - 12px)`;
    const spread = (list) => { // keep neighbouring labels from touching
      let floor = -99;
      return list.map((n) => { const y = Math.max(n.mid, floor + 15); floor = y; return y; });
    };
    const yl = spread(s.left), yr = spread(s.right);
    labels.innerHTML =
      s.left.map((n, i) => `<span class="l" style="top:${yl[i].toFixed(1)}px;width:${width}">${s.narrow ? SHORT[n.name] || n.name : n.name} <b>${pct(n.share)}</b></span>`).join("") +
      s.right.map((n, i) => `<span class="r${n.near ? " near" : ""}" style="top:${yr[i].toFixed(1)}px;width:${width}"><b>${pct(n.share)}</b> ${n.name}</span>`).join("");
  };
  new ResizeObserver(write).observe(canvas);
  movie(canvas, draw);
  fill("flowLine", `Every fee dollar partners charged in ${win.days} days: <b>${usd(p.fees)}</b>. Over half is Bitcoin holders paying up. NEAR's cut? <b>${pct(p.near_cut)}</b>.`);
}

// ---------- slow reveal as charts scroll into view ----------
{
  const watch = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add("in");
      watch.unobserve(entry.target);
    }
  }, { threshold: 0.2 });
  document.querySelectorAll(".reveal").forEach((el) => watch.observe(el));
}
