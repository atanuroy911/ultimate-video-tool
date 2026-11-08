// Settings, Directors: "What every director is told" lists the house rules (GET /api/house-rules, the same as `vt rules` and MCP house_rules),
// each with what it is for and the reason. VT_URL=http://127.0.0.1:5178 node e2e/house_rules.mjs
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { base, chromePath } from "./common.mjs";

const OUT = "e2e/out/house-rules";
mkdirSync(OUT, { recursive: true });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const want = await (await fetch(base + "/api/house-rules")).json();
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
for (const [w, h, scheme] of [[1280, 900, "light"], [400, 860, "dark"]]) {
  const tag = `${w}px ${scheme}`;
  const page = await (await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme })).newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base + "/settings?s=directors", { waitUntil: "networkidle" });
  const box = page.getByTestId("house-rules");
  await box.scrollIntoViewIfNeeded();
  check(`${tag}: the section is in Settings, closed at first`, await box.isVisible() && !(await box.evaluate((d) => d.open)));
  await box.locator("summary").click();
  const items = box.locator("li");
  check(`${tag}: it lists every rule (${want.length})`, (await items.count()) === want.length && want.length > 0);
  check(`${tag}: each says why`, (await items.first().innerText()).includes("Why:"));
  check(`${tag}: no sideways scroll`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  check(`${tag}: no page errors`, errors.length === 0, errors.join("; "));
  await box.screenshot({ path: `${OUT}/${w}-${scheme}.png` });
  await page.context().close();
}
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
