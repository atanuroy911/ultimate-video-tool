// Dragging clip edges follows the pointer: scene end and start, voice clip trim (live edge, size label, outward hint), Escape cancels, a drag that leaves the window keeps working.
// Mutating (then undone): run against a scratch server.  VT_PROJECT=<id> node e2e/timeline3.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "reference";
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p) => (await fetch(base + p)).json();

console.log("Edge dragging");
await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
await page.waitForSelector(".tl-clip");
await page.waitForTimeout(600);

// ---- scene end: the clip's right edge is within 2 px of the pointer on every frame
const sceneRight = async () => { const b = await page.locator(".tl-clip").nth(0).boundingBox(); return b.x + b.width; };
const grab = page.locator('[aria-label="Move the end of scene 1"]').first();
const gb = await grab.boundingBox();
const y = gb.y + gb.height / 2;
let px = gb.x + gb.width - 3;
await page.mouse.move(px, y);
await page.mouse.down();
let worst = 0;
const startR = await sceneRight();
for (let i = 1; i <= 20; i++) {
  px += 6;
  await page.mouse.move(px, y);
  await page.waitForTimeout(30);
  worst = Math.max(worst, Math.abs((await sceneRight()) - px));
}
check("scene end stays under the pointer on every frame", worst <= 2.5, `worst offset ${worst.toFixed(1)} px`);
check("a marker shows the sentence it will settle on", (await page.locator(".tl-snap.land").count()) === 1);
await page.keyboard.press("Escape");
await page.mouse.up();
await page.waitForTimeout(400);
check("Escape cancels: the scene is back where it was", Math.abs((await sceneRight()) - startR) < 2, `${startR} -> ${await sceneRight()}`);
const plan = (await api(`/api/projects/${pid}/scenes`)).plan.scenes;
check("and nothing was changed in the plan", plan.length >= 2);

// ---- scene start handle of scene 2 moves the same edge
check("scene 2 has a start handle", (await page.locator('[aria-label="Move the start of scene 2"]').count()) === 1);

// ---- voice clip: right edge shrinks with the pointer, a label shows the length, outward with nothing to restore gives a hint
const vclip = page.locator(".tl-aclip").first();
const vb = await vclip.boundingBox();
const trimR = vclip.locator(".trim.r");
const tb = await trimR.boundingBox();
let tx = tb.x + 6, ty = tb.y + tb.height / 2;
await page.mouse.move(tx, ty);
await page.mouse.down();
let vworst = 0;
for (let i = 1; i <= 16; i++) {
  tx -= 8;
  await page.mouse.move(tx, ty);
  await page.waitForTimeout(30);
  const nb = await vclip.boundingBox();
  vworst = Math.max(vworst, Math.abs(nb.x + nb.width - tx - 6));
}
check("the voice clip's end follows the pointer while trimming", vworst <= 14, `worst ${vworst.toFixed(1)} px`);
const nb = await vclip.boundingBox();
check("the clip is visibly shorter during the drag", nb.width < vb.width - 60, `${vb.width} -> ${nb.width}`);
check("a label shows how much is being cut", /−\d/.test((await page.locator(".tl-hint").innerText().catch(() => "")) || ""));
await page.keyboard.press("Escape");
await page.mouse.up();
await page.waitForTimeout(300);
const nb2 = await vclip.boundingBox();
check("Escape puts the voice clip back", Math.abs(nb2.width - vb.width) < 2, `${vb.width} -> ${nb2.width}`);
check("and no cut was made", (await api(`/api/projects/${pid}/audio`)).cuts.length === (await api(`/api/projects/${pid}/audio`)).cuts.length);

const tb2 = await trimR.boundingBox();
let ox = tb2.x + 6, oy = tb2.y + tb2.height / 2;
await page.mouse.move(ox, oy);
await page.mouse.down();
for (let i = 1; i <= 6; i++) { ox += 10; await page.mouse.move(ox, oy); await page.waitForTimeout(30); }
check("dragging out where nothing was cut explains why nothing happens", /Nothing was cut/.test((await page.locator(".tl-hint").innerText().catch(() => "")) || ""));
await page.mouse.up();

// ---- a real trim, with the pointer leaving the window: the drag still ends cleanly
const outLen = async () => (await api(`/api/projects/${pid}/audio`)).keep.at(-1).o1;
const before = await outLen();
const tb3 = await trimR.boundingBox();
let lx = tb3.x + 6, ly = tb3.y + tb3.height / 2;
await page.mouse.move(lx, ly);
await page.mouse.down();
for (let i = 1; i <= 12; i++) { lx -= 12; await page.mouse.move(lx, ly); await page.waitForTimeout(25); }
await page.mouse.move(lx, 940);
await page.mouse.up();
await page.waitForTimeout(2500);
const after = await outLen();
check("a trim released outside the timeline still applies", after < before - 0.3, `${before} -> ${after}`);
await page.mouse.click(5, 5);
await page.keyboard.press("Control+z");
await page.waitForTimeout(1500);
check("and undo brings it back", Math.abs((await outLen()) - before) < 0.05);

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
