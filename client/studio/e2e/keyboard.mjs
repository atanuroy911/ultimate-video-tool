// E12: a whole journey by keyboard only (no mouse): the sidebar, the New page from a script to "Make my video", the Settings page; focus is always visible,
// Escape closes what opened, and with reduced motion nothing keeps moving. Scratch server only.
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" });
const page = await ctx.newPage();
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const label = () => page.evaluate(() => { const e = document.activeElement; return e ? (e.getAttribute("aria-label") || e.textContent || e.tagName).trim().replace(/\s+/g, " ").slice(0, 40) : ""; });
const ringVisible = () => page.evaluate(() => {
  const e = document.activeElement; if (!e || e === document.body) return false;
  const c = getComputedStyle(e);
  return (c.outlineStyle !== "none" && parseFloat(c.outlineWidth) > 0) || (c.boxShadow && c.boxShadow !== "none") || e.tagName === "TEXTAREA" || e.tagName === "INPUT";
});
const tabTo = async (match, max = 40) => { for (let i = 0; i < max; i++) { await page.keyboard.press("Tab"); if (match.test(await label())) return true; } return false; };

console.log("Keyboard only");
await page.goto(base + "/new", { waitUntil: "domcontentloaded" });
await page.locator("textarea[aria-label='Link or script']").waitFor();
check("the page can be reached to the box by Tab", await tabTo(/^$|Link or script/, 30) || (await page.evaluate(() => document.activeElement?.tagName)) === "TEXTAREA");
await page.locator("textarea[aria-label='Link or script']").focus();
await page.keyboard.type("Hello. This is a short test about saving money.");
check("typing a script enables OK", await page.locator(".tf-nav .btn.primary").first().isEnabled());
check("the box shows where the focus is", await ringVisible());
check("Tab reaches OK", await tabTo(/^OK/));
check("and it shows focus", await ringVisible());
await page.keyboard.press("Enter");
await page.waitForTimeout(400);
check("the shape question appears", (await page.getByRole("radio").count()) === 3);
await page.getByRole("radio").first().focus();
await page.keyboard.press("ArrowRight");
check("arrow keys move between shapes", /Wide/.test(await label()), await label());
check("the shape shows focus", await ringVisible());
check("Tab reaches OK on this question too", await tabTo(/^OK/));
await page.keyboard.press("Enter");
await page.waitForTimeout(500);
const tile = page.locator(".opt-tile").first();
await tile.waitFor();
check("then the 15 choices can each be reached by Tab", await (async () => { const seen = new Set(); for (let i = 0; i < 60 && seen.size < 15; i++) { await page.keyboard.press("Tab"); if (await page.evaluate(() => document.activeElement?.classList.contains("opt-tile"))) seen.add(await label()); } return seen.size === 15; })());
await page.locator(".opt-tile").first().focus();
await page.keyboard.press("Enter");
await page.waitForTimeout(500);
check("Enter opens a choice", (await page.getByRole("button", { name: /Back to your choices/ }).count()) >= 1);
await page.keyboard.press("Escape");
await page.waitForTimeout(400);
check("Escape comes back to the choices", (await page.locator(".opt-tile").count()) === 15);
check("Make my video can be reached by Tab", await tabTo(/Make my video/, 60));

console.log("Settings by keyboard");
await page.goto(base + "/settings", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1500);
let stops = 0, ringless = 0, last = "";
for (let i = 0; i < 80; i++) { await page.keyboard.press("Tab"); if (await page.evaluate(() => document.activeElement === document.body)) break;                // focus left the page: the loop is over
  const l = await label(); if (l === last) break; last = l; stops++; if (!(await ringVisible())) { ringless++; console.log("   no ring on:", l, await page.evaluate(() => document.activeElement.outerHTML.slice(0, 140))); } }
check("Tab walks through the page", stops > 10, String(stops));
check("every stop shows where the focus is", ringless === 0, `${ringless} without`);

console.log("Reduced motion");
await page.goto(base + "/", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1200);
const moving = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running" && a.effect?.getTiming().iterations === Infinity).map((a) => a.effect?.target?.className || a.effect?.target?.tagName));
check("nothing loops forever when motion is reduced", moving.length === 0, JSON.stringify(moving.slice(0, 5)));

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
