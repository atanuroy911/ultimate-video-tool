// Accessibility sweep with axe-core (the engine Lighthouse uses): every main screen, light and dark, wide and narrow.
// axe-core is not a project dependency: AXE=<path to axe.min.js> node e2e/a11y.mjs   (npm i axe-core in any folder)
import { chromium } from "playwright-core";
import fs from "node:fs";
import { base, chromePath } from "./common.mjs";

const axePath = process.env.AXE;
if (!axePath || !fs.existsSync(axePath)) { console.log("skip: set AXE to axe.min.js (npm i axe-core)"); process.exit(0); }
const axe = fs.readFileSync(axePath, "utf8");
const pid = process.env.VT_PROJECT || "reference";
const pages = [["projects", "/"], ["new", "/new"], ["review", `/p/${pid}`], ["export", `/p/${pid}/export`], ["themes", "/themes"], ["settings", "/settings"], ["shorts", "/shorts"], ["social", "/social"], ["result", `/p/${pid}/result`]];
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
let bad = 0;
const impactOrder = { critical: 4, serious: 3, moderate: 2, minor: 1 };
for (const scheme of ["light", "dark"]) for (const [w, h] of [[1440, 900], [390, 800]]) {
  const page = await (await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme })).newPage();
  for (const [name, url] of pages) {
    await page.goto(base + url, { waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(900);
    await page.evaluate(axe);
    const res = await page.evaluate(() => window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "best-practice"] }, resultTypes: ["violations"] }));
    const v = res.violations.filter((x) => impactOrder[x.impact] >= 3);
    for (const x of v) { bad++; console.log(`  ${name} ${scheme} ${w}: [${x.impact}] ${x.id} x${x.nodes.length}: ${x.help} :: ${x.nodes[0].target.join(" ")}`); }
    const minor = res.violations.filter((x) => impactOrder[x.impact] < 3).map((x) => x.id);
    if (minor.length) console.log(`  (${name} ${scheme} ${w}: moderate/minor: ${[...new Set(minor)].join(", ")})`);
  }
}
await browser.close();
console.log(bad ? `\n${bad} serious/critical violations` : "\nno serious or critical violations");
process.exit(bad ? 1 : 0);
