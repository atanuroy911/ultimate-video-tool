import { chromium } from "playwright-core";
import { pathToFileURL } from "node:url";
import { chromePath } from "./common.mjs";
const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
for (const which of ["old", "new"]) {
  const p = await b.newPage({ viewport: { width: 540, height: 960 } });
  await p.goto(pathToFileURL(`${process.argv[2]}/${which}/index.html`).href);
  await p.waitForTimeout(2500);
  const out = await p.evaluate(() => {
    const tl = Object.values(window.__timelines)[0], D = window.__VT__;
    let best = { t: 0, n: 0 }, peak = 0;
    for (let t = 0.3; t < Math.min(D.duration, 40); t += 0.2) {
      tl.time(t);
      const n = [...document.querySelectorAll(".mouth-group")].filter((m) => getComputedStyle(m).display !== "none" && +getComputedStyle(m).opacity > 0.5).length;
      peak = Math.max(peak, n);
      if (n && !best.n) best = { t, n };
    }
    return { firstWithMouths: best, peakVisibleAtOnce: peak };
  });
  console.log(which, JSON.stringify(out));
  const t = out.firstWithMouths.t || 1;
  await p.evaluate((t) => Object.values(window.__timelines)[0].time(t), t + 0.3);
  await p.screenshot({ path: `${process.argv[2]}/${which}.png` });
  await p.close();
}
await b.close();
