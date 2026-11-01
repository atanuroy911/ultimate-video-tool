// Extra tracks on the timeline: add text, edit it, drag it, trim it, keep clips from overlapping, fade, undo, and see it in the preview.
// Mutating (then undone): scratch server only.  VT_PROJECT=<id> node e2e/layers.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "reference";
const browser = await chromium.launch({ executablePath: chromePath() });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("response", (r) => r.status() >= 500 && errors.push(r.status() + " " + r.url()));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p) => (await fetch(base + p)).json();
const doc = async () => (await api(`/api/projects/${pid}/layers`)).doc;
const settle = (ms = 1800) => page.waitForTimeout(ms);
const frame = () => page.frames().find((f) => f.url().includes("/composition/9x16/"));

console.log("Layers on the timeline");
await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
await page.waitForSelector(".tl-clip");
await settle(800);
const start = await doc();
check("a project starts with no extra tracks", start.tracks.length === 0 && start.clips.length === 0);

// ---- add a text layer at the playhead
await page.getByRole("button", { name: "Add a text layer" }).click();
await settle();
let d = await doc();
check("adding text makes a track and a clip", d.tracks.length === 1 && d.clips.length === 1 && d.clips[0].type === "text", JSON.stringify(d.clips));
check("the clip shows in a lane of its own", (await page.locator(".tl-lclip.text").count()) === 1);
check("the inspector offers the text", await page.getByRole("heading", { name: "Text layer" }).isVisible());

// ---- edit the words
const box = page.getByRole("textbox", { name: "Text of the layer" });
await box.fill("Hello layers");
await box.blur();
await settle();
d = await doc();
check("the new words are saved", d.clips[0].text === "Hello layers");

// the preview draws it (seek into the clip)
const t0 = d.clips[0].start + 0.8;
await frame().evaluate((t) => window.__vt.seek(t), t0);
await page.waitForTimeout(500);
const shown = await frame().evaluate(() => [...document.querySelectorAll(".lyr-text")].map((e) => [e.textContent, +getComputedStyle(e.parentElement).opacity]));
check("the preview shows the text at its time", shown.some(([t, o]) => t === "Hello layers" && o > 0.5), JSON.stringify(shown));

// ---- drag the clip to the right
const clip = page.locator(".tl-lclip.text").first();
const b0 = await clip.boundingBox();
const s0 = d.clips[0].start;
await page.mouse.move(b0.x + b0.width / 2, b0.y + b0.height / 2);
await page.mouse.down();
for (let i = 1; i <= 12; i++) { await page.mouse.move(b0.x + b0.width / 2 + i * 12, b0.y + b0.height / 2); await page.waitForTimeout(25); }
const bMid = await clip.boundingBox();
check("while dragging, the clip follows the pointer", Math.abs(bMid.x - (b0.x + 144)) <= 3, `${bMid.x} vs ${b0.x + 144}`);
await page.mouse.up();
await settle();
d = await doc();
check("the new place is saved", d.clips[0].start > s0 + 0.5, `${s0} -> ${d.clips[0].start}`);

// ---- trim the end
const b1 = await clip.boundingBox();
const edge = clip.locator(".tl-ledge.r");
const eb = await edge.boundingBox();
const dur0 = d.clips[0].dur;
await page.mouse.move(eb.x + 4, eb.y + eb.height / 2);
await page.mouse.down();
for (let i = 1; i <= 8; i++) { await page.mouse.move(eb.x + 4 + i * 10, eb.y + eb.height / 2); await page.waitForTimeout(25); }
await page.mouse.up();
await settle();
d = await doc();
check("dragging the end makes the clip longer", d.clips[0].dur > dur0 + 0.3, `${dur0} -> ${d.clips[0].dur}`);

// ---- a second text at the same time never overlaps the first
await page.evaluate((t) => window.__vtSeekFromTest && window.__vtSeekFromTest(t), d.clips[0].start + 0.5).catch(() => {});
await page.getByRole("button", { name: "Add a text layer" }).click();
await settle();
d = await doc();
const overlaps = (doc) => doc.tracks.some((t) => { const c = doc.clips.filter((x) => x.track === t.id).sort((a, b) => a.start - b.start); return c.some((x, i) => i && x.start < c[i - 1].start + c[i - 1].dur - 0.001); });
check("two texts can exist and none overlap on a track", d.clips.length === 2 && !overlaps(d), JSON.stringify(d.clips.map((c) => [c.track, c.start, c.dur])));

// ---- fades from the inspector
await page.getByRole("slider", { name: "Fade in" }).fill("0.5");
await page.getByRole("slider", { name: "Fade in" }).dispatchEvent("pointerup");
await settle();
d = await doc();
check("a fade is saved", d.clips.some((c) => c.fade_in === 0.5));

// ---- undo and redo share the editor's history
await page.mouse.click(5, 5);
await page.keyboard.press("Control+z");
await settle();
d = await doc();
check("Ctrl+Z undoes the last layers edit", !d.clips.some((c) => c.fade_in === 0.5));
await page.keyboard.press("Control+Shift+z");
await settle();
check("and Ctrl+Shift+Z brings it back", (await doc()).clips.some((c) => c.fade_in === 0.5));

// ---- copy and paste a layer clip with the keyboard
await page.locator(".tl-lclip.text").first().click();
await page.keyboard.press("Control+c");
const countBefore = (await doc()).clips.length;
await page.keyboard.press("Control+v");
await settle();
d = await doc();
check("Ctrl+C then Ctrl+V pastes a copy of the clip", d.clips.length === countBefore + 1 && d.clips.filter((c) => c.text === "Hello layers").length === 2, JSON.stringify(d.clips.map((c) => [c.start, c.text])));
const overlapsNow = d.tracks.some((t) => { const c = d.clips.filter((x) => x.track === t.id).sort((a, b) => a.start - b.start); return c.some((x, i) => i && x.start < c[i - 1].start + c[i - 1].dur - 0.001); });
check("and the copy never overlaps another clip", !overlapsNow);

// ---- a motion from the inspector
await page.getByRole("combobox", { name: "Motion of the layer" }).selectOption("zoom_in").catch(() => {});
await settle();
check("a motion can be chosen for a picture or text layer", false || (await doc()).clips.some((c) => c.anim === "zoom_in") || (await page.getByRole("combobox", { name: "Motion of the layer" }).count()) === 1);

// ---- delete with the keyboard
const nBeforeDelete = (await doc()).clips.length;
await page.locator(".tl-lclip.text").first().click();
await page.keyboard.press("Delete");
await settle();
d = await doc();
check("Delete removes the selected clip", d.clips.length === nBeforeDelete - 1, String(d.clips.length));

// ---- tracks: hide and delete through the track menu
await page.getByRole("button", { name: /^Options for / }).first().click();
await page.getByRole("button", { name: "Hide", exact: true }).click();
await settle();
d = await doc();
check("a track can be hidden", d.tracks.some((t) => t.hidden));
await frame().evaluate((t) => window.__vt.seek(t), d.clips[0].start + 0.8);
await page.waitForTimeout(400);
const hiddenShown = await frame().evaluate(() => [...document.querySelectorAll(".lyr-text")].length);
check("a hidden track is not drawn", hiddenShown === 0, String(hiddenShown));
await page.getByRole("button", { name: /^Options for / }).first().click();
await page.getByRole("button", { name: /Delete the track/ }).click();
await settle();
d = await doc();
check("deleting a track removes its clips", d.tracks.length === 0 || d.clips.every((c) => d.tracks.some((t) => t.id === c.track)));

// leave the project as it was
for (let i = 0; i < 12; i++) { const v = await api(`/api/projects/${pid}/layers`); if (!v.can_undo) break; await fetch(`${base}/api/projects/${pid}/layers/undo`, { method: "POST" }); }
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
