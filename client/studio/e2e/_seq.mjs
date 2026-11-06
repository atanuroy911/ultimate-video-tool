import { chromium } from "playwright-core";
import { pathToFileURL } from "node:url";
import { chromePath } from "./common.mjs";
const [, , src, t] = process.argv;
const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 0.3 });
await p.goto(pathToFileURL(src).href);
await p.waitForTimeout(2500);
console.log(JSON.stringify(await p.evaluate((T) => {
  const tl = Object.values(window.__timelines)[0];
  const seen = {};
  for (let f = 0; f <= T * 30; f++) {
    tl.time(f / 30);
    document.querySelectorAll(".scene").forEach((el, i) => { const s = window.__VT__.scenes[i]; if (+getComputedStyle(el).opacity > 0.05 && f / 30 > s.end + 0.8) seen[s.id] = seen[s.id] || +(f / 30).toFixed(2); });
  }
  return seen;
}, +t)));
await b.close();
