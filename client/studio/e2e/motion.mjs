// Every motion recipe runs without a script error and ends in the resting state: load a composition, step through its timeline,
// collect page errors, and save frames in the middle of transitions and entrances. Usage: node e2e/motion.mjs <composition index.html> [out dir]
import { chromium } from "playwright-core";
import { pathToFileURL } from "node:url";
import { chromePath } from "./common.mjs";

const [, , src, out] = process.argv;
const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const p = await b.newPage({ viewport: { width: 540, height: 960 } });
const errors = [];
p.on("pageerror", (e) => errors.push(e.message));
p.on("console", (m) => m.type() === "error" && errors.push(m.text()));
await p.goto(pathToFileURL(src).href);
await p.waitForTimeout(2500);
const info = await p.evaluate(() => {
  const D = window.__VT__;
  const tl = Object.values(window.__timelines || {})[0];
  const fx = [], tx = [], mv = [];
  D.scenes.forEach((s) => { (s.elements || []).forEach((e) => e.fx && fx.push(e.fx)); s.tx && tx.push(s.tx); (s.moves || []).forEach((m) => mv.push(m)); });
  return { dur: D.duration, fx: [...new Set(fx)], tx: [...new Set(tx)], mv: [...new Set(mv)], scenes: D.scenes.map((s) => [s.start, s.tx || null]), ok: !!tl };
});
const seek = (t) => p.evaluate((t) => { const tl = Object.values(window.__timelines)[0]; tl.time(t); }, t);
for (let t = 0; t < info.dur; t += 0.25) await seek(t);
// played forward frame by frame (as the renderer does), no scene stays visible after its end (a transition once left one at 40 %)
const stuck = await p.evaluate(() => {
  const tl = Object.values(window.__timelines)[0], D = window.__VT__, seen = {};
  for (let f = 0; f <= D.duration * 15; f++) {
    const t = f / 15;
    tl.time(t);
    document.querySelectorAll(".scene").forEach((el, i) => { const s = D.scenes[i]; if (t > s.end + 0.8 && +getComputedStyle(el).opacity > 0.05) seen[s.id] = seen[s.id] || +t.toFixed(2); });
  }
  return seen;
});
Object.entries(stuck).forEach(([id, t]) => errors.push(`scene ${id} still visible at ${t} s, after it ended`));
// nothing shows before its entrance: at (at - 0.06) every text of the element must be invisible
const early = [];
const plan = await p.evaluate(() => window.__VT__.scenes.flatMap((s, si) => (s.elements || []).map((e, i) => ({ si, i, at: e.at, type: e.type, start: s.start, id: s.src || s.id, el: e._i != null ? e._i : i })).filter((x) => x.at - x.start > 0.3)));
for (const x of plan) {
  await seek(x.at - 0.06);
  const shown = await p.evaluate((x) => {
    const sc = document.querySelectorAll(".scene")[x.si];
    const w = sc && sc.querySelectorAll(".stage .el")[x.i];
    if (!w) return null;
    const vis = (n) => { let o = 1; for (let e = n; e && e !== document.body; e = e.parentElement) { const cs = getComputedStyle(e); o *= +cs.opacity; if (cs.visibility === "hidden" || cs.display === "none") return 0; } return o; };
    const walk = document.createTreeWalker(w, NodeFilter.SHOW_TEXT);
    while (walk.nextNode()) { const t = walk.currentNode; if (t.nodeValue.trim() && vis(t.parentElement) > 0.3) return t.nodeValue.trim().slice(0, 30); }
    return null;
  }, x);
  if (shown) early.push(`${x.id}#${x.el} ${x.type} at ${x.at}: "${shown}"`);
}
if (early.length) errors.push(...early.slice(0, 12).map((e) => "shows before its entrance: " + e));
let shot = 0;
if (out) for (const [st, tx] of info.scenes.slice(1, 13)) { await seek(st + 0.2); await p.screenshot({ path: `${out}/m${String(shot++).padStart(2, "0")}-${tx || "plain"}.png` }); }
console.log(JSON.stringify({ timeline: info.ok, recipes: info.fx.length + info.tx.length + info.mv.length, fx: info.fx, tx: info.tx, moves: info.mv, errors }));
await b.close();
process.exit(errors.length ? 1 : 0);
