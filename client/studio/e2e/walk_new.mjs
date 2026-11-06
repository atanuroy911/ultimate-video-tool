// The New flow, screen by screen, phone and desktop: types a script, presses OK until the last screen, screenshots each. Does not submit.
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";
const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
for (const [vn, vp] of [["phone", { width: 390, height: 844 }], ["desktop", { width: 1440, height: 900 }]]) {
  const page = await (await b.newContext({ viewport: vp })).newPage();
  await page.goto(base + "/new", { waitUntil: "networkidle" });
  await page.locator("textarea").first().fill("Most people lose money on savings because of inflation. Here is a simple way to keep up. Put your emergency fund in a high-yield account. Invest the rest every month, whatever the market does.");
  let n = 0;
  for (; n < 8; n++) {
    await page.waitForTimeout(600);
    await page.screenshot({ path: `e2e/out/ui/walk-${vn}-${n}.png` });
    const ok = page.getByRole("button", { name: /^(OK|Continue|Next)/ }).first();
    if (!(await ok.count()) || !(await ok.isEnabled())) break;
    await ok.click();
  }
  console.log(vn, "screens:", n + 1);
}
await b.close();
