// Timeline smoothness and layout: dragging a scene's end follows the pointer frame by frame and stays put on drop; chips in Elements and Actions never overlap.
// Mutating (moves a scene boundary, then undoes it): run against a scratch server.  VT_PROJECT=<id> node e2e/timeline2.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "reference";
const browser = await chromium.launch({ executablePath: chromePath() });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const scenes = async () => (await (await fetch(`${base}/api/projects/${pid}/scenes`)).json()).plan.scenes;

console.log("Timeline smoothness and layout");
await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
await page.waitForSelector(".tl-clip");

// ---- no overlaps in the Elements and Actions lanes
const overlaps = async (lane) => page.evaluate((name) => {
  const boxes = [...document.querySelectorAll(`[aria-label="${name}"] .tl-chip`)].map((e) => e.getBoundingClientRect()).filter((b) => b.width > 0);
  let n = 0;
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const a = boxes[i], b = boxes[j];
    if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) n++;
  }
  return { n, count: boxes.length };
}, lane);
for (const z of [1, 3]) {
  if (z === 3) for (let i = 0; i < 3; i++) await page.getByRole("button", { name: "Zoom out" }).click();    // crowd everything together
  const e = await overlaps("Elements");
  check(`no two element chips overlap (${e.count} chips${z === 3 ? ", zoomed out" : ""})`, e.n === 0, JSON.stringify(e));
  if (await page.locator('[aria-label="Actions"]').count()) { const a = await overlaps("Actions"); check("no two action chips overlap", a.n === 0, JSON.stringify(a)); }
}
await page.getByRole("button", { name: "Fit the whole video" }).click();
await page.waitForTimeout(700);

// ---- drag the end of scene 1 to the right: it follows in many small steps and stays where dropped
const before = await scenes();
const grab = page.locator('[aria-label="Move the end of scene 1"]').first();
const gb = await grab.boundingBox();
const clip = page.locator(".tl-clip").nth(0);
const w0 = (await clip.boundingBox()).width;
const widths = [];
await page.mouse.move(gb.x + gb.width / 2, gb.y + gb.height / 2);
await page.mouse.down();
const targetX = gb.x + Math.min(260, ((await page.locator(".tl-clip").nth(1).boundingBox()).width) * 0.8);
for (let i = 1; i <= 24; i++) {
  await page.mouse.move(gb.x + ((targetX - gb.x) * i) / 24, gb.y + 4);
  await page.waitForTimeout(24);
  widths.push((await clip.boundingBox()).width);
}
check("while dragging, scene 1 grows as the pointer moves", widths[widths.length - 1] > w0 + 10, `${w0} -> ${widths.at(-1)}`);
const steps = new Set(widths.map((w) => Math.round(w))).size;
check("the growth is gradual (more than a couple of distinct sizes)", steps >= 3, `${steps} sizes`);
const wDrop = widths.at(-1);
await page.mouse.up();
await page.waitForTimeout(80);
const wAfterUp = (await clip.boundingBox()).width;
check("on drop the clip settles on its sentence and does not jump back", wAfterUp > w0 + 10 && Math.abs(wAfterUp - wDrop) < 45, `${w0} / ${wDrop} -> ${wAfterUp}`);
await page.waitForTimeout(2200);
const after = await scenes();
check("the plan really moved the boundary", after[0].beats.length !== before[0].beats.length || after[0].beats.at(-1) !== before[0].beats.at(-1), JSON.stringify(after[0].beats));
const wFinal = (await clip.boundingBox()).width;
check("and the final clip matches what was dropped", Math.abs(wFinal - wDrop) < 30, `${wDrop} -> ${wFinal}`);
await page.mouse.click(5, 5);
await page.keyboard.press("Control+z");
await page.waitForTimeout(1500);

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
