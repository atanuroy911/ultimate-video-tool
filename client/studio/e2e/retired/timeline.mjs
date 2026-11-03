// The timeline as an editor: smooth zoom, moving playhead, voice clips with waveform, range select, ripple cut, trim, blade, mute, volume, restore, undo.
// Edits the voice of VT_PROJECT (a project with real audio, e.g. a copy) and puts it back with undo. Run against a scratch server.
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const pid = process.env.VT_PROJECT || "demo";
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--autoplay-policy=no-user-gesture-required"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("response", (r) => r.status() >= 500 && errors.push(r.status() + " " + r.url()));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p) => (await fetch(base + p)).json();
const audio = () => api(`/api/projects/${pid}/audio`);
const settle = (ms = 1800) => page.waitForTimeout(ms);

console.log("Timeline");
await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
await page.waitForSelector(".tl-aclip");
const a0 = await audio();
check("the voice is drawn as clips with a waveform", (await page.locator(".tl-aclip").count()) === a0.keep.length && (await page.locator(".tl-aclip path").first().getAttribute("d")).length > 100);

// smooth zoom around the pointer
const sc = page.locator(".tl-scroll");
const box = await sc.boundingBox();
const px = box.x + 700;
const timeAt = () => page.evaluate(({ px, dur }) => { const s = document.querySelector(".tl-scroll"); const w = document.querySelector(".tl-inner").getBoundingClientRect().width; const pps = (w - 86) / dur; return (px - s.getBoundingClientRect().left + s.scrollLeft - 62) / pps; }, { px, dur: a0.duration });
const tBefore = await timeAt();
await page.mouse.move(px, box.y + 60);
await page.keyboard.down("Control");
for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, -120); await page.waitForTimeout(40); }
await page.keyboard.up("Control");
await page.waitForTimeout(700);
const tAfter = await timeAt();
const wide = await page.locator(".tl-inner").evaluate((e) => e.getBoundingClientRect().width);
check("ctrl+wheel zooms in smoothly", wide > box.width * 1.8, `${wide}`);
check("the moment under the pointer stays under the pointer", Math.abs(tAfter - tBefore) < 0.25, `${tBefore.toFixed(2)} -> ${tAfter.toFixed(2)}`);
await page.getByRole("button", { name: "Fit the whole video" }).click();
await page.waitForTimeout(700);
check("Fit brings the whole video back", (await page.locator(".tl-inner").evaluate((e) => e.getBoundingClientRect().width)) <= box.width + 5);

// the playhead moves with the audio, outside React
const head = () => page.locator(".tl-head").evaluate((e) => new DOMMatrix(getComputedStyle(e).transform).m41);
const h0 = await head();
await page.getByRole("toolbar", { name: "Playback" }).getByRole("button").click();
await page.waitForTimeout(1200);
const h1 = await head();
await page.getByRole("toolbar", { name: "Playback" }).getByRole("button").click();
check("the playhead glides while playing", h1 > h0 + 20, `${h0} -> ${h1}`);

// range select + ripple delete
const lane = page.getByRole("group", { name: "Audio" });
const lb = await lane.boundingBox();
const scale = ((await page.locator(".tl-inner").evaluate((e) => e.getBoundingClientRect().width)) - 86) / a0.duration;
const xAt = (t) => lb.x + 62 + t * scale;
await page.keyboard.press("n");                                   // snapping off: exact seconds
await page.mouse.move(xAt(3.2), lb.y + 24);
await page.mouse.down();
await page.mouse.move(xAt(4.2), lb.y + 24, { steps: 10 });
await page.mouse.up();
check("dragging on the voice selects a range", (await page.getByLabel("Selected range").count()) === 1);
await page.keyboard.press("Delete");
await settle();
const a1 = await audio();
check("Delete cuts the range out and the gap closes", Math.abs(a1.duration - (a0.duration - 1.0)) < 0.12 && a1.cuts.length === 1, `${a0.duration} -> ${a1.duration}`);
check("a cut marker appears", (await page.locator(".tl-cutmark").count()) === 1);
const scenes1 = (await api(`/api/projects/${pid}/scenes`)).plan.scenes.length;
check("scenes survive the cut", scenes1 >= 4, String(scenes1));
await page.screenshot({ path: out + "/t1-after-cut.png" });
await page.locator(".tl-cutmark").click();
await settle();
check("clicking the cut marker brings the audio back", Math.abs((await audio()).duration - a0.duration) < 0.12);
await page.keyboard.press("Control+z");                           // undo the restore
await settle();
check("undo goes back through voice edits", (await audio()).cuts.length === 1);
await page.keyboard.press("Control+z");
await settle();
check("and again to the original", Math.abs((await audio()).duration - a0.duration) < 0.12 && (await audio()).cuts.length === 0);
await page.keyboard.press("Control+Shift+z");
await settle();
check("redo brings the cut back", (await audio()).cuts.length === 1);
await page.keyboard.press("Control+z");
await settle();

// trim: drag the right edge of a clip inward (cut) and back out (restore)
const clip = page.locator(".tl-aclip").nth(2);
const cb = await clip.boundingBox();
await page.mouse.move(cb.x + cb.width - 3, cb.y + cb.height / 2);
await page.mouse.down();
await page.mouse.move(cb.x + cb.width - 3 - 50, cb.y + cb.height / 2, { steps: 8 });
check("trimming shows a red ghost of what will be cut", (await page.locator(".tl-ghost.cut").count()) === 1);
await page.mouse.up();
await settle();
const a2 = await audio();
check("trim inward cuts the end of the clip", a2.cuts.length === 1 && a2.duration < a0.duration - 0.3, JSON.stringify(a2.cuts));
const clip2 = page.locator(".tl-aclip").nth(2);
const cb2 = await clip2.boundingBox();
await page.mouse.move(cb2.x + cb2.width - 3, cb2.y + cb2.height / 2);
await page.mouse.down();
await page.mouse.move(cb2.x + cb2.width - 3 + 25, cb2.y + cb2.height / 2, { steps: 6 });
await page.mouse.up();
await settle();
const a3 = await audio();
check("trim outward brings part of it back", a3.duration > a2.duration + 0.1, `${a2.duration} -> ${a3.duration}`);
await page.keyboard.press("Control+z"); await settle(1500);
await page.keyboard.press("Control+z"); await settle(1500);

// blade
const nClips = await page.locator(".tl-aclip").count();
await page.keyboard.press("b");
await page.mouse.click(xAt(1.0), lb.y + 24);
await settle(900);
check("the blade splits a clip in two", (await page.locator(".tl-aclip").count()) === nClips + 1);
await page.keyboard.press("v");
await page.keyboard.press("Control+z"); await settle(900);
check("undo removes the split", (await page.locator(".tl-aclip").count()) === nClips);

// mute and volume of a selected clip
await page.locator(".tl-aclip").nth(1).click({ position: { x: 20, y: 20 } });
await page.keyboard.press("m");
await settle();
check("M mutes the selected clip", (await audio()).mutes.length === 1 && (await page.locator(".tl-aclip.muted").count()) >= 1);
await page.keyboard.press("m");
await settle();
check("M again unmutes it", (await audio()).mutes.length === 0);
const slider = page.getByLabel("Volume of the selection in decibels");
await slider.focus();
for (let i = 0; i < 8; i++) await page.keyboard.press("ArrowLeft");        // 8 x 0.5 dB steps down
await settle();
const gains = (await audio()).gains;
check("the volume slider sets the level of the clip", gains.length >= 1 && gains[0].db <= -3.9, JSON.stringify(gains));
await page.locator(".tl-aclip").nth(1).click({ button: "right", position: { x: 20, y: 20 } });
check("right-click offers cut, mute, volume and split", (await page.getByRole("button", { name: "Cut out (ripple delete)" }).count()) === 1);
await page.keyboard.press("Escape");
await page.mouse.click(5, 5);
for (let i = 0; i < 4; i++) { await page.keyboard.press("Control+z"); await settle(1300); }
const aEnd = await audio();
check("everything is undone: the voice is as it was", Math.abs(aEnd.duration - a0.duration) < 0.05 && aEnd.cuts.length === 0 && aEnd.mutes.length === 0 && aEnd.gains.length === 0 && aEnd.splits.length === 0, JSON.stringify(aEnd.edits));
await page.screenshot({ path: out + "/t2-timeline.png" });

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
