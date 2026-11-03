// Screenshots of the settings sections, the export sheet and the setup wizard (desktop + phone, light).
import { chromium } from "playwright-core";
import fs from "node:fs";
import { base, chromePath } from "./common.mjs";
fs.mkdirSync("e2e/out/ui", { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath() });
for (const [vn, vp] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  const page = await (await browser.newContext({ viewport: vp, colorScheme: "light" })).newPage();
  await page.goto(base + "/settings", { waitUntil: "networkidle" });
  const links = await page.locator(".settings-nav a, .settings-nav button").allInnerTexts();
  for (const [i, name] of links.entries()) {
    await page.locator(".settings-nav a, .settings-nav button").nth(i).click().catch(() => {});
    await page.waitForTimeout(600);
    await page.screenshot({ path: `e2e/out/ui/settings-${i}-${vn}.png` });
  }
  await page.goto(base + "/p/reference/export", { waitUntil: "networkidle" });
  await page.getByTestId("export-more").click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `e2e/out/ui/export-sheet-${vn}.png` });
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.getByText("Set up", { exact: true }).first().click().catch(() => {});
  await page.waitForTimeout(600);
  await page.screenshot({ path: `e2e/out/ui/wizard-${vn}.png` });
  console.log(vn, links.join(" | "));
}
await browser.close();
