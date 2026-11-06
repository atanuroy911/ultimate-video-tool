// Fixing one element by hand (plan step E17, human in the loop): the Position tab's transform controls, the handles on the picture (move, size, turn, pin the four corners), the arrow keys,
// the motion points that hold the new values, reset, undo, and the same at phone width in light and dark.
// A scratch server only: it changes the project it runs on.
//   VT_DATA=<scratch dir> python -m vt.cli server --host 127.0.0.1 --port 8771 --comfy off --ollama off --voicestudio off     (with samples/build_reference.py reference built there)
//   cd client/studio && VT_SERVER_URL=http://127.0.0.1:8771 npx vite --port 5177 --strictPort --host 127.0.0.1
//   VT_URL=http://127.0.0.1:5177 node e2e/transform.mjs [out dir]
import fs from "node:fs";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://127.0.0.1:5177";
const pid = process.env.VT_PROJECT || "reference";
const out = process.argv[2] || "e2e/out/transform";
fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const api = async (path, init) => (await fetch(base + path, init)).json();
const plan = async () => (await api(`/api/projects/${pid}/scenes`)).plan.scenes;
const element = async (scene = 0, index = 0) => (await plan())[scene].elements[index];
const near = (a, b, t = 0.02) => Math.abs(a - b) <= t;

async function clean() {                                           // every section starts from the same elements: nothing placed, nothing transformed, no motion
  const scene = (await plan())[0];
  const els = scene.elements.map((e) => ({ ...e, start: null, end: null, x: null, y: null, scale: 1, rotation: 0, opacity: 1, transform: null, keyframes: [] }));
  const r = await fetch(base + `/api/projects/${pid}/scenes/${scene.id}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ elements: els }) });
  if (!r.ok) throw new Error("could not clean the scene: " + r.status + " " + (await r.text()).slice(0, 200));
}
const group = async (page, id) => {                                // open a fold if it is shut (it is open already when something in it is set)
  const g = page.getByTestId(`group-${id}`);
  if (!(await g.evaluate((e) => e.open))) await g.locator("summary").click();
  return g;
};

async function open(viewport = { width: 1500, height: 950 }, scheme = "light") {
  await clean();
  const ctx = await browser.newContext({ viewport, colorScheme: scheme });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("console", (m) => m.type() === "error" && errors.push("console: " + m.text()));
  await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
  await page.waitForSelector(".scene-card", { state: "attached" });
  return { ctx, page, errors };
}
const frameOf = (page) => page.frames().find((f) => f.url().includes("/composition/9x16/"));

/** Click the last element of scene 1 on the picture, the way a person does, and open its Position tab. */
async function pick(page) {
  await page.locator(".scene-card").nth(0).click();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(900);
  const fr = frameOf(page);
  await fr.waitForSelector(".el");
  const scenes = (await api(`/api/projects/${pid}/scenes`)).timing.scenes;
  await fr.evaluate((t) => window.__vt.seek(t), Math.max(0.5, scenes[0].end - 0.4));
  await page.waitForTimeout(700);
  const phone = await page.locator(".phone").boundingBox();
  const info = await fr.evaluate(() => [...document.querySelectorAll(".scene[data-scene='s1'] .el")].map((e) => { const b = e.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2, e.getAttribute("data-el")]; }));
  const target = info[info.length - 1];
  await page.mouse.click(phone.x + (target[0] * phone.width) / 1080, phone.y + (target[1] * phone.width) / 1080);
  await page.waitForTimeout(800);
  const index = Number(target[2]);
  const card = page.locator(".el-card.picked");
  await card.getByRole("radio", { name: "Position" }).click().catch(async () => card.getByText("Position", { exact: true }).click());
  await page.waitForTimeout(300);
  return { index, phone, fr };
}
const saved = async (page) => { await page.waitForTimeout(1200); await page.keyboard.press("Escape").catch(() => {}); };

console.log("Per-element transform controls");
{
  const { page, errors, ctx } = await open();
  const { index, phone, fr } = await pick(page);
  const groups = ["stretch-slant-and-flip", "tilt-in-3d", "pivot", "crop", "corner-pin-warp", "blur-and-blend"];
  for (const g of groups) check(`the ${g.replace(/-/g, " ")} group is there`, (await page.getByTestId(`group-${g}`).count()) === 1);
  const before = await fr.evaluate((i) => { const b = document.querySelector(`.scene[data-scene='s1'] .el[data-el='${i}']`).getBoundingClientRect(); return [b.width, b.height]; }, index);

  // typing a number: the saved element, the composition and the picture all follow
  await group(page, "stretch-slant-and-flip");
  const stretch = page.getByRole("spinbutton", { name: "Stretch across, as a number" });
  await stretch.waitFor({ timeout: 5000 }).catch(async () => { await page.screenshot({ path: `${out}/debug-stretch.png` }); console.log("  (no stretch field; screenshot saved)"); });
  await stretch.fill("200");
  await page.waitForTimeout(1500);
  const el = await element(0, index);
  check("the element is saved with the stretch", el.transform && near(el.transform.stretch_x, 2), JSON.stringify(el.transform));
  check("and nothing else of the transform is set", el.transform.stretch_y === 1 && el.transform.skew_x === 0 && el.transform.flip_x === false && el.transform.blur === 0 && el.transform.blend === "normal", JSON.stringify(el.transform));
  const data = await api(`/media/${pid}/composition/9x16/data.json`);
  const composed = data.scenes.flatMap((s) => s.elements).find((e) => e._i === index);
  check("the composition has it as a hand-placed element", composed && composed.free === true && near(composed.transform.stretch_x, 2));
  const after = await fr.evaluate((i) => { const b = document.querySelector(`.scene[data-scene='s1'] .el[data-el='${i}']`).getBoundingClientRect(); return [b.width, b.height]; }, index);
  check("the picture is twice as wide", after[0] > before[0] * 1.8 && near(after[1] / before[1], 1, 0.15), `${before} -> ${after}`);
  await page.screenshot({ path: `${out}/position-wide.png` });

  // undo and redo cover it
  await page.getByRole("button", { name: "Undo" }).click();
  await page.waitForTimeout(1500);
  check("undo takes the stretch back", (await element(0, index)).transform == null, JSON.stringify((await element(0, index)).transform));
  await page.getByRole("button", { name: "Redo" }).click();
  await page.waitForTimeout(1500);
  check("redo puts it back", near((await element(0, index)).transform?.stretch_x ?? 1, 2));
  await page.getByRole("slider", { name: "Stretch across" }).dblclick();
  await page.waitForTimeout(1500);
  check("double-clicking a slider takes it back to normal", (await element(0, index)).transform == null);
  await stretch.fill("200");
  await page.waitForTimeout(1200);

  // a slider, the way back, and a mirrored toggle
  await page.getByRole("button", { name: "Reset Stretch across" }).click();
  await page.waitForTimeout(1500);
  check("the way back sets it to normal and takes the transform away", (await element(0, index)).transform == null, JSON.stringify((await element(0, index)).transform));
  await page.getByRole("button", { name: "Mirror left ↔ right" }).click();
  await page.waitForTimeout(1500);
  check("a mirror is a toggle that is saved", (await element(0, index)).transform?.flip_x === true);
  await page.getByRole("button", { name: "Mirror left ↔ right" }).click();

  // the other groups
  await group(page, "tilt-in-3d");
  await page.getByRole("spinbutton", { name: "Lean back or forward, as a number" }).fill("40");
  await group(page, "crop");
  await page.getByRole("spinbutton", { name: "Crop the top, as a number" }).fill("10");
  await page.getByRole("spinbutton", { name: "Rounded corners, as a number" }).fill("50");
  await group(page, "blur-and-blend");
  await page.getByRole("spinbutton", { name: "Blur, as a number" }).fill("6");
  await page.getByRole("combobox").filter({ hasText: "Normal" }).selectOption("multiply");
  await page.waitForTimeout(1500);
  const many = (await element(0, index)).transform;
  check("tilt, crop, rounded corners, blur and blend are saved together", many.tilt_x === 40 && near(many.crop[0], 0.1) && near(many.crop_radius, 0.5) && many.blur === 6 && many.blend === "multiply", JSON.stringify(many));
  const look = await fr.evaluate((i) => { const w = document.querySelector(`.scene[data-scene='s1'] .el[data-el='${i}']`); const p = w.closest(".free-position"), s = w.parentElement; return { filter: getComputedStyle(p).filter, blend: getComputedStyle(p).mixBlendMode, clip: getComputedStyle(s).clipPath }; }, index);
  check("the picture is blurred, blended and cropped", look.filter.includes("blur(6px)") && look.blend === "multiply" && look.clip.startsWith("inset("), JSON.stringify(look));

  await page.getByRole("button", { name: "Reset stretch, tilt, crop, corners and effects" }).click();
  await page.waitForTimeout(1500);
  check("one button takes all of it away", (await element(0, index)).transform == null);
  const cardNow = page.locator(".el-card.picked");
  await cardNow.getByText("Content", { exact: true }).click();
  await page.waitForTimeout(300);
  check("the Content tab does not list the transform as one of the element's own fields", !(await cardNow.innerText()).toLowerCase().includes("transform"));
  check("no page errors", errors.length === 0, errors.join("; "));
  await ctx.close();
}

console.log("Handles on the picture");
{
  const { page, errors, ctx } = await open();
  const { index, phone, fr } = await pick(page);
  const start = await element(0, index);
  check("the handles are drawn over the selected picture", await page.getByTestId("transform-handles").isVisible());
  const grab = async (id) => { const b = await page.getByTestId(id).boundingBox(); return [b.x + b.width / 2, b.y + b.height / 2]; };

  // move
  const move = page.getByTestId("handle-move");
  const mb = await move.boundingBox();
  const px = [mb.x + mb.width / 2, mb.y + mb.height / 2];
  await page.mouse.move(...px); await page.mouse.down(); await page.mouse.move(px[0] + 30, px[1] + 20, { steps: 5 }); await page.mouse.up();
  await page.waitForTimeout(1500);
  const moved = await element(0, index);
  const k = 1080 / phone.width;
  check("dragging the picture moves it by what the hand moved", moved.x != null && moved.y != null && (start.x == null || near(moved.x - start.x, (30 * k) / 1080, 0.01)) && (start.y == null || near(moved.y - start.y, (20 * k) / 1920, 0.01)), JSON.stringify([start.x, start.y, moved.x, moved.y]));

  // size: drag the bottom right corner away from the middle
  const c2 = await grab("handle-scale-2");
  const mid = [mb.x + mb.width / 2, mb.y + mb.height / 2];
  await page.mouse.move(...c2); await page.mouse.down();
  await page.mouse.move(c2[0] + (c2[0] - mid[0]) * 0.5, c2[1] + (c2[1] - mid[1]) * 0.5, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(1500);
  const bigger = await element(0, index);
  check("dragging a corner outward makes it bigger", (bigger.scale ?? 1) > (moved.scale ?? 1) * 1.2, `${moved.scale} -> ${bigger.scale}`);

  // turn: drag the knob sideways
  const kn = await grab("handle-rotate");
  const nb = await page.getByTestId("handle-move").boundingBox();
  const centre = [nb.x + nb.width / 2, nb.y + nb.height / 2];
  await page.mouse.move(...kn); await page.mouse.down();
  await page.mouse.move(centre[0] + Math.hypot(kn[0] - centre[0], kn[1] - centre[1]), centre[1], { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(1500);
  const turned = await element(0, index);
  check("dragging the knob turns it", Math.abs(turned.rotation ?? 0) > 20, String(turned.rotation));
  await page.screenshot({ path: `${out}/handles-wide.png` });

  // pin the four corners
  await group(page, "corner-pin-warp");
  await page.getByRole("button", { name: "Pin the corners on the picture" }).click();
  await page.waitForTimeout(300);
  check("the pins replace the resize handles", (await page.getByTestId("handle-pin-0").count()) === 1 && (await page.getByTestId("handle-scale-0").count()) === 0);
  const pin = await grab("handle-pin-1");
  await page.mouse.move(...pin); await page.mouse.down(); await page.mouse.move(pin[0] + 40, pin[1] - 30, { steps: 6 }); await page.mouse.up();
  await page.waitForTimeout(1500);
  const pinned = (await element(0, index)).transform;
  check("dragging a pin moves that corner only", pinned?.warp && pinned.warp.length === 4 && (Math.abs(pinned.warp[1][0]) > 0.01 || Math.abs(pinned.warp[1][1]) > 0.01) && pinned.warp.filter((c, i) => i !== 1).every((c) => c[0] === 0 && c[1] === 0), JSON.stringify(pinned?.warp));
  const warped = await fr.evaluate((i) => getComputedStyle(document.querySelector(`.scene[data-scene='s1'] .el[data-el='${i}']`).parentElement).transform, index);
  check("the picture is warped on the page", warped.startsWith("matrix3d"), warped);
  await page.getByRole("button", { name: "Done pinning" }).click();

  // the arrow keys
  const before = await element(0, index);
  await page.locator(".phone").focus();
  await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(1200);
  const nudged = await element(0, index);
  check("an arrow key nudges it by one percent", near(nudged.x - before.x, 0.01, 0.003), `${before.x} -> ${nudged.x}`);
  await page.keyboard.press("Shift+ArrowDown");
  await page.waitForTimeout(1200);
  check("shift and an arrow key by ten", near((await element(0, index)).y - nudged.y, 0.1, 0.01));
  check("no page errors", errors.length === 0, errors.join("; "));
  await ctx.close();
}

console.log("Motion points hold the new values");
{
  const { page, errors, ctx } = await open();
  const { index } = await pick(page);
  const card = page.locator(".el-card.picked");
  await card.getByRole("radio", { name: "Motion" }).click().catch(async () => card.getByText("Motion", { exact: true }).click());
  await page.getByRole("button", { name: "Save a point here" }).click();
  await page.getByRole("spinbutton", { name: "Motion Stretch across, as a number" }).fill("150");
  await page.waitForTimeout(1500);
  const el = await element(0, index);
  check("a motion point keeps the stretch", el.keyframes?.length >= 1 && near(el.keyframes[el.keyframes.length - 1].stretch_x ?? 1, 1.5), JSON.stringify(el.keyframes));
  check("and every point holds all the new values", el.keyframes.every((p) => ["stretch_x", "stretch_y", "skew_x", "skew_y", "tilt_x", "tilt_y", "blur"].every((key) => typeof p[key] === "number")));
  await card.getByRole("button", { name: "Clear motion" }).click();
  await page.waitForTimeout(1200);
  check("no page errors", errors.length === 0, errors.join("; "));
  await ctx.close();
}

console.log("Phone width, light and dark");
for (const [name, scheme] of [["phone-light", "light"], ["phone-dark", "dark"]]) {
  const { page, errors, ctx } = await open({ width: 400, height: 860 }, scheme);
  const pageErrors = errors;
  // on a phone the panels are folded away: Details brings the inspector up; open the first element
  await page.getByRole("button", { name: "Details" }).click().catch(() => {});
  await page.waitForTimeout(500);
  const card = page.locator(".el-card").first();
  const tab = card.getByText("Position", { exact: true });
  if (!(await tab.isVisible().catch(() => false))) await card.locator(".el-head").click();
  await tab.click({ timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(300);
  const row = page.locator(".value-row").first();
  check(`${name}: a value row is there and does not spill sideways`, (await row.count()) > 0 && (await row.evaluate((e) => e.scrollWidth - e.clientWidth)) <= 1);
  const small = await page.locator(".value-row .btn.icon").evaluateAll((els) => els.filter((e) => { const b = e.getBoundingClientRect(); return b.width && (b.width < 43.5 || b.height < 43.5); }).length);
  check(`${name}: the reset buttons are a finger wide`, small === 0, String(small));
  const nums = await page.locator(".value-row .num").first().boundingBox();
  check(`${name}: a number to type is a finger tall`, nums && nums.height >= 43.5, JSON.stringify(nums));
  check(`${name}: the page does not scroll sideways`, (await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)) <= 1);
  await page.screenshot({ path: `${out}/position-${name}.png` });
  check(`${name}: no page errors`, pageErrors.length === 0, pageErrors.join("; "));
  await ctx.close();
}
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
