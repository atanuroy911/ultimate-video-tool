// debug: screenshot the editor; optionally open the Characters tab and the first character
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";
const [, , base, id, out, chars] = process.argv;
const b = await chromium.launch({ executablePath: chromePath() });
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
p.on("pageerror", (e) => errors.push(e.message));
await p.goto(`${base}/p/${id}`);
await p.waitForTimeout(3500);
await p.screenshot({ path: out + "-elements.png" });
if (chars) {
  await p.locator(".inspector").getByText(/^Characters/).click();
  await p.locator(".cast-head").first().click();
  await p.waitForTimeout(500);
  await p.screenshot({ path: out + "-characters.png" });
  await p.locator(".cast-card").getByText("Cartoon", { exact: true }).click();
  await p.waitForTimeout(3000);
  await p.screenshot({ path: out + "-cartoon.png" });
}
console.log(JSON.stringify({ errors }));
await b.close();
