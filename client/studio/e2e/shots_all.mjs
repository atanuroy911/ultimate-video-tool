// Screenshots of every page at desktop and phone width, light and dark, into studio/e2e/out/ui/. Used for the design review (docs/UI-REVIEW.md).
//   VT_URL=http://127.0.0.1:8791 node e2e/shots_all.mjs [pageFilter]
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath } from "./common.mjs";

const out = path.resolve("e2e/out/ui");
fs.mkdirSync(out, { recursive: true });
const pages = {
  projects: "/", new: "/new", shorts: "/shorts", social: "/social", themes: "/themes", settings: "/settings",
  editor: "/p/reference", result: "/p/reference/result", export: "/p/reference/export", pro: "/p/reference/pro",
};
const only = process.argv[2];
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
for (const [vname, vp] of Object.entries({ desktop: { width: 1440, height: 900 }, phone: { width: 390, height: 844 } })) {
  for (const scheme of ["light", "dark"]) {
    const ctx = await browser.newContext({ viewport: vp, colorScheme: scheme, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const errs = [];
    page.on("pageerror", (e) => errs.push(e.message));
    for (const [name, url] of Object.entries(pages)) {
      if (only && !name.includes(only)) continue;
      await page.goto(base + url, { waitUntil: "load" }).catch(() => {});   // not "networkidle": the editor preview streams audio
      await page.waitForTimeout(1500);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      await page.screenshot({ path: path.join(out, `${name}-${vname}-${scheme}.png`) });
      if (overflow > 0) console.log(`  sideways scroll: ${name} ${vname} ${scheme} (+${overflow}px)`);
    }
    if (errs.length) console.log("errors", scheme, vname, errs.slice(0, 3));
    await ctx.close();
  }
}
await browser.close();
console.log("done ->", out);
