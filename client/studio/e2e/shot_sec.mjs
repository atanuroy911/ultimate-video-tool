import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";
const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await b.newContext({ viewport: { width: 1200, height: 900 } })).newPage();
// Settings shows one section at a time: each block is on its own section (?s=)
for (const [id, section] of [["ai", "directors"], ["stock", "libraries"], ["speech", "voice"], ["system", "help"]]) {
  await page.goto(`${base}/settings?s=${section}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.locator("#" + id).screenshot({ path: `e2e/out/ui/sec-${id}.png` });
}
await b.close();
