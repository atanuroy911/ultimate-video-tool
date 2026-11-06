import { chromium } from "playwright-core";
import { pathToFileURL } from "node:url";
import { chromePath } from "./common.mjs";
const [, , src, t] = process.argv;
const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 0.3 });
await p.goto(pathToFileURL(src).href);
await p.waitForTimeout(2500);
console.log(JSON.stringify(await p.evaluate((t) => {
  const tl = Object.values(window.__timelines)[0]; tl.time(+t);
  return Array.from(document.querySelectorAll(".scene")).map((el, i) => ({ i, id: window.__VT__.scenes[i].id, tx: window.__VT__.scenes[i].tx, op: getComputedStyle(el).opacity, types: Array.from(el.querySelectorAll(".stage .el")).map((w) => w.className.replace("el el-", "")).join(",") })).filter((x) => +x.op > 0.01);
}, t)));
await b.close();
