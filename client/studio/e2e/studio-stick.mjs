// Stick figures in the HyperFrames Studio (O8 prerequisite). A stick-figure video used to be refused (its figures are drawn by code every frame);
// now each stick scene is a composition that runs the stick engine, so the Studio opens the video, draws the figures at any moment, and a part of a
// stick scene can be selected like any other.
//   VT_SERVER=http://127.0.0.1:8791 VT_PROJECT=e2e-stick node e2e/studio-stick.mjs
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const server = process.env.VT_SERVER || "http://127.0.0.1:8791", pid = process.env.VT_PROJECT || "e2e-stick";
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };
const opened = await (await fetch(`${server}/api/projects/${pid}/studio?fresh=1`, { method: "POST" })).json();
check("a stick-figure video opens in HyperFrames", !!opened.url && !opened.lost_count, JSON.stringify(opened).slice(0, 160));
const parts = await (await fetch(`${server}/api/projects/${pid}/studio/parts?scene=s1`)).json();
check("its stick scene has a page of its own with its parts", Array.isArray(parts) && parts.some((p) => /^scenes\//.test(p.file)), (parts.map?.((p) => p.file)[0]) || JSON.stringify(parts).slice(0, 120));

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
const drawnAt = async (t) => {
  await page.evaluate((t) => { location.hash = location.hash.split("?")[0] + `?t=${t}`; }, t);
  await page.waitForTimeout(2500);
  for (const f of page.frames()) {
    if (!f.url().includes("/preview")) continue;
    return f.evaluate(() => { const s = document.querySelector(".stk-svg"); return s ? s.querySelectorAll("path, line, circle, ellipse").length : -1; });
  }
  return -2;
};
await page.goto(opened.url, { waitUntil: "load" });
await page.waitForTimeout(9000);
const a = await drawnAt(1.5), b = await drawnAt(4.5);
check("the Studio draws the stick figures (the engine runs in the scene's page)", a > 10 && b > 10, JSON.stringify([a, b]));
await page.screenshot({ path: "e2e/out/studio-stick.png" });
await browser.close();
await fetch(`${server}/api/projects/${pid}/studio`, { method: "DELETE" });
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
