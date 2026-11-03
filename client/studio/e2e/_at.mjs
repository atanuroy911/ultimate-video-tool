import { chromium } from "playwright-core";
import { pathToFileURL } from "node:url";
import { chromePath } from "./common.mjs";
const [, , src, t, out] = process.argv;
const b = await chromium.launch({ executablePath: chromePath() });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 0.3 });
await p.goto(pathToFileURL(src).href);
await p.waitForTimeout(2500);
const info = await p.evaluate((t) => {
  const tl = Object.values(window.__timelines)[0]; tl.time(+t);
  const D = window.__VT__; const i = D.scenes.findIndex((s) => s.start <= t && t < s.end); const s = D.scenes[i];
  const el = document.querySelectorAll(".scene")[i];
  const cs = getComputedStyle(el);
  return { scene: s.id, start: s.start, end: s.end, tx: s.tx, moves: s.moves, sceneOpacity: cs.opacity, clip: cs.clipPath, transform: cs.transform,
    els: Array.from(el.querySelectorAll(".stage .el")).map((w, k) => ({ type: w.className, at: (s.elements[k] || {}).at, fx: (s.elements[k] || {}).fx, op: getComputedStyle(w).opacity, disp: getComputedStyle(w).display, tf: getComputedStyle(w).transform })) };
}, t);
console.log(JSON.stringify(info, null, 1));
if (out) await p.screenshot({ path: out });
await b.close();
