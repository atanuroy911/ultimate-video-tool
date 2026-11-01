import { chromium } from "playwright-core";
import { pathToFileURL } from "node:url";
import { chromePath } from "./common.mjs";
const b = await chromium.launch({ executablePath: chromePath() });
for (const src of process.argv.slice(2)) {
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 0.25 });
  await p.goto(pathToFileURL(src).href);
  await p.waitForTimeout(3000);
  const g = await p.evaluate(() => window.__guard || []);
  const by = {};
  g.forEach((x) => { const k = x.rule + "/" + x.fix + "/" + x.type; by[k] = (by[k] || 0) + 1; });
  console.log(src.split("/projects/")[1].split("/")[0], JSON.stringify(by));
  await p.close();
}
await b.close();
