import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";
const b = await chromium.launch({ executablePath: chromePath() });
const page = await (await b.newContext({ viewport: { width: 1200, height: 900 } })).newPage();
await page.goto(base + "/settings", { waitUntil: "networkidle" });
await page.waitForTimeout(800);
for (const id of ["ai", "stock", "speech", "system"]) {
  await page.locator("#" + id).screenshot({ path: `e2e/out/ui/sec-${id}.png` });
}
await b.close();
