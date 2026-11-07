// E15: the Server page in plain words: no "Video Tool server 1", every card says what it is doing and for whom, a card the person chose not to use says so. Scratch server only.
import { chromium } from "playwright-core";
import fs from "node:fs";
import { base, chromePath } from "./common.mjs";

fs.mkdirSync("e2e/out/server-page", { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
for (const [w, h] of [[1280, 1000], [400, 900]]) for (const scheme of ["light", "dark"]) {
  const page = await (await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme })).newPage();
  await page.goto(base + "/server", { waitUntil: "load" });
  await page.waitForTimeout(3500);
  const text = (await page.locator("body").innerText());
  check(`${w} ${scheme}: no "server 1"-style internal numbers in the first line`, !/server \d\b/i.test(text), text.match(/.{20}server \d\b.{10}/i)?.[0]);
  check(`${w} ${scheme}: the page says what this server is`, /Server/.test(text) && /(Connected|This computer|Ready|Not connected|Working)/i.test(text));
  check(`${w} ${scheme}: nothing scrolls sideways`, !(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)));
  check(`${w} ${scheme}: no raw words (undefined, NaN, null, [object])`, !/undefined|NaN|\bnull\b|\[object/.test(text));
  await page.screenshot({ path: `e2e/out/server-page/${w}-${scheme}.png`, fullPage: true });
  await page.close();
}
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
