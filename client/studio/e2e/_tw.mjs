import { chromium } from "playwright-core";
import { pathToFileURL } from "node:url";
import { chromePath } from "./common.mjs";
const [, , src, id] = process.argv;
const b = await chromium.launch({ executablePath: chromePath() });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 0.3 });
await p.goto(pathToFileURL(src).href);
await p.waitForTimeout(2500);
console.log(JSON.stringify(await p.evaluate((id) => {
  const i = window.__VT__.scenes.findIndex((s) => s.id === id);
  const el = document.querySelectorAll(".scene")[i];
  const s = window.__VT__.scenes;
  return { me: { start: s[i].start, end: s[i].end, tx: s[i].tx, tr: s[i].transition_in }, next: { id: s[i + 1].id, start: s[i + 1].start, tx: s[i + 1].tx, tr: s[i + 1].transition_in },
    tweens: gsap.getTweensOf(el).map((t) => ({ start: +t.startTime().toFixed(2), dur: +t.duration().toFixed(2), vars: Object.keys(t.vars).filter((k) => !k.startsWith("_") && k !== "parent").map((k) => k + "=" + String(t.vars[k]).slice(0, 30)).join(" ") })) };
}, id)));
await b.close();
