// Card menus on the dashboard must be fully visible (they were clipped by the card, 2026-10-23). Read-only: opens menus, clicks nothing in them.
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const shots = process.env.SHOTS || "";
let fails = 0;
const check = (name, ok, extra = "") => { console.log(`${ok ? "PASS" : "FAIL"} ${name} ${ok ? "" : extra}`); if (!ok) fails++; };
const b = await chromium.launch({ executablePath: chromePath() });
for (const [w, h] of [[1280, 800], [390, 844]]) {
  const page = await b.newPage({ viewport: { width: w, height: h } });
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.waitForSelector(".dash2-card");
  const btns = page.getByRole("button", { name: /^Actions for/ });
  const n = Math.min(await btns.count(), 3);
  for (const i of [0, n - 1]) {
    await btns.nth(i).scrollIntoViewIfNeeded();
    await btns.nth(i).click();
    const last = page.getByRole("menuitem", { name: "Delete…" });
    await last.waitFor();
    const box = await last.boundingBox();
    const hit = await page.evaluate(([x, y]) => document.elementFromPoint(x, y)?.textContent || "", [box.x + box.width / 2, box.y + box.height / 2]);
    check(`${w}px card ${i + 1}: the whole menu is visible`, box.y >= 0 && box.y + box.height <= h && box.x >= 0 && box.x + box.width <= w && hit.includes("Delete"), JSON.stringify(box) + " hit=" + hit);
    shots && (await page.screenshot({ path: `${shots}/menu-${w}-${i}.png` }));
    await page.keyboard.press("Escape");
  }
  await page.close();
}
await b.close();
console.log(fails ? `${fails} FAILED` : "all passed");
process.exit(fails ? 1 : 0);
