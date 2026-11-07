// E8: the New page's choices. All 14 stay visible, no value is cut off with "…", at a wide window and a phone. Screenshots in e2e/out/new-tiles. Scratch server only.
import { chromium } from "playwright-core";
import fs from "node:fs";
import { base, chromePath, walkToReady } from "./common.mjs";

fs.mkdirSync("e2e/out/new-tiles", { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
for (const [width, height] of [[1440, 1000], [400, 900]]) {
  for (const scheme of ["light", "dark"]) {
    const page = await (await browser.newContext({ viewport: { width, height }, colorScheme: scheme })).newPage();
    await page.goto(base + "/new", { waitUntil: "domcontentloaded" });
    await page.locator("textarea[aria-label='Link or script']").waitFor();
    await walkToReady(page, "Hello. This is a short test about saving money.");
    const tiles = page.locator(".opt-tile");
    check(`${width} ${scheme}: all 14 choices are visible`, (await tiles.count()) === 14 && (await tiles.evaluateAll((all) => all.every((t) => t.getBoundingClientRect().width > 0))));
    const cut = await page.locator(".opt-tile-value").evaluateAll((all) => all.filter((v) => v.scrollWidth > v.clientWidth + 1 || getComputedStyle(v).textOverflow === "ellipsis").map((v) => v.textContent));
    check(`${width} ${scheme}: no value is cut off`, cut.length === 0, cut.join(" | "));
    const sideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    check(`${width} ${scheme}: nothing scrolls sideways`, !sideways);
    await page.screenshot({ path: `e2e/out/new-tiles/${width}-${scheme}.png`, fullPage: true });
    await page.close();
  }
}
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
