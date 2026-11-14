// Prints docs/thesis.html to the PDF of the paper, with Chrome's own print engine.
// usage: node tools/make_pdf.mjs [url] [out]      (needs Google Chrome; serve docs/ first)
//   python3 -m http.server -d docs 8787 &
//   node tools/make_pdf.mjs http://localhost:8787/thesis.html docs/exhibit-a-thesis.pdf
import { spawn } from "node:child_process";
import { writeFileSync, mkdtempSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [url = "http://localhost:8787/thesis.html", out = "docs/exhibit-a-thesis.pdf"] = process.argv.slice(2);
const paths = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"];
const binary = process.env.CHROME || paths.find((path) => existsSync(path));
if (!binary) throw new Error("Chrome not found; set CHROME to its path");
const port = 9341;
const chrome = spawn(binary, ["--headless=new", "--disable-gpu", ...(process.env.CI ? ["--no-sandbox"] : []), `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "pdf-"))}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  await sleep(200);
  try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page"); } catch {}
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((done) => (ws.onopen = done));
let id = 0;
const pending = new Map();
ws.onmessage = (event) => { const m = JSON.parse(event.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise((done) => { const i = ++id; pending.set(i, done); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Page.enable");
await send("Page.navigate", { url });
await sleep(4000); // fonts and figures
const pdf = await send("Page.printToPDF", { printBackground: true, preferCSSPageSize: true, displayHeaderFooter: false });
writeFileSync(out, Buffer.from(pdf.data, "base64"));
console.log(`wrote ${out}`);
ws.close();
chrome.kill();
