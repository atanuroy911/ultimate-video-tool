// D7: the credits the licences ask for (a Bensound track, stock media, a link's source) are shown on the Export page with a Copy
// button, and fill the Share description when no publishing text was written. The exports list is intercepted with one export that
// has credits (nothing is rendered). Needs the `reference` project (vt demo). VT_URL=http://127.0.0.1:5178 node e2e/credits.mjs
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { base, chromePath } from "./common.mjs";

const OUT = "e2e/out/credits";
mkdirSync(OUT, { recursive: true });
const PID = process.env.VT_PROJECT || "reference";
const CREDITS = "Media credits\n- Music: Hope by Benjamin Tissot, Bensound.com https://www.bensound.com/royalty-free-music/track/hope\n";
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });

for (const [w, h, scheme] of [[1280, 900, "light"], [400, 860, "dark"]]) {
  const tag = `${w}px ${scheme}`;
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, permissions: ["clipboard-read", "clipboard-write"] });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const exp = { name: `${PID}-9x16-1.mp4`, size: 1_200_000, url: "/no-such-video.mp4", srt: null, credits: CREDITS, modified: "2026-11-07 22:00", path: "C:/x.mp4", retention: null, judges: null };
  await page.route(`**/api/projects/${PID}/exports`, (r) => r.fulfill({ json: [exp] }));
  await page.route(`**/api/projects/${PID}/publish`, (r) => r.request().method() === "GET" ? r.fulfill({ json: { kit: null } }) : r.continue());

  await page.goto(`${base}/p/${PID}/export`, { waitUntil: "networkidle" });
  const box = page.getByRole("region", { name: "Credits" });
  await box.waitFor({ timeout: 10000 }).catch(() => {});
  check(`${tag}: the Export page shows the credits`, await box.isVisible() && /Bensound\.com/.test(await box.innerText()));
  await box.scrollIntoViewIfNeeded().catch(() => {});
  await page.screenshot({ path: `${OUT}/${w}-${scheme}-export.png` });
  await box.getByRole("button", { name: "Copy credits" }).click();
  const clip = await page.evaluate(() => navigator.clipboard.readText()).catch(() => "");
  check(`${tag}: Copy credits puts them on the clipboard`, clip.includes("Bensound.com"), clip.slice(0, 60));
  check(`${tag}: no sideways scroll`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));

  await page.route(`**/api/projects/${PID}/exports`, (r) => r.fulfill({ json: [{ ...exp, credits: "" }] }));
  await page.goto(`${base}/p/${PID}/export`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  check(`${tag}: no Credits section when nothing needs a credit`, !(await page.getByRole("region", { name: "Credits" }).count()));

  await page.route(`**/api/projects/${PID}/exports`, (r) => r.fulfill({ json: [exp] }));
  await page.goto(`${base}/p/${PID}/result`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const desc = page.locator("textarea").filter({ hasText: /Bensound/ });
  const descs = await page.locator("textarea").evaluateAll((all) => all.map((t) => t.value));
  check(`${tag}: Share's description starts with the credits when no publishing text exists`, descs.some((v) => v.includes("Bensound.com")), JSON.stringify(descs).slice(0, 160));
  await page.screenshot({ path: `${OUT}/${w}-${scheme}-result.png`, fullPage: true });
  check(`${tag}: no page errors`, errors.length === 0, errors.join("; "));
  void desc;
  await ctx.close();
}
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
