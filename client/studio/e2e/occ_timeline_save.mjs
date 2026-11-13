// Edits made on the new (OpenChatCut) timeline are saved to the project, and undo brings them back (docs/plans/PLAN-OPENCHATCUT.MD phase 2).
// MUTATING (each change is undone at the end): run against a scratch server, on a copy.  VT_PROJECT=<copy with scene elements> node e2e/occ_timeline_save.mjs
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://localhost:5291";
const pid = process.env.VT_PROJECT;
if (!pid) { console.log("set VT_PROJECT to a copy"); process.exit(2); }
let pass = 0, fail = 0;
const check = (name, ok, detail = "") => { if (ok) { pass++; console.log("  ok  ", name); } else { fail++; console.log(`  FAIL ${name}${detail ? " :: " + detail : ""}`); } };
const api = async (p) => (await fetch(`${base}${p}`)).json();
const scenes = async () => (await api(`/api/projects/${pid}/scenes`));
const elementCount = async () => (await scenes()).plan.scenes.reduce((n, s) => n + s.elements.length, 0);
const until = async (fn, ms = 15000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await fn()) return true; await new Promise((r) => setTimeout(r, 250)); } return false; };

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await ctx.addInitScript(() => { try { localStorage.setItem("vt-timeline", "new"); } catch {} });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
const tl = page.getByTestId("occ-timeline");
await tl.waitFor({ timeout: 20000 });
await page.waitForTimeout(1500);

console.log("Delete an element on the timeline, then undo");
const before = await elementCount();
const chip = tl.locator(".cc-timeline-clip").filter({ hasText: /Value card|Keyword|Tag|Question|Title|Icons/ }).first();
const chipName = (await chip.innerText()).split("\n").pop();
await chip.click();
await page.keyboard.press("Delete");
check(`"${chipName}" is removed from the project`, await until(async () => (await elementCount()) === before - 1), `${before} -> ${await elementCount()}`);
check("the timeline says it saved", await until(async () => /Saved/.test(await page.getByTestId("occ-status").innerText().catch(() => ""))));
await page.waitForTimeout(800);
await page.keyboard.press("Control+z");
check("Ctrl+Z on the timeline brings it back (our project's undo)", await until(async () => (await elementCount()) === before), `${await elementCount()} vs ${before}`);

console.log("Move a scene's edge on the timeline, then undo");
// after an undo the project reloads and the timeline is rebuilt from it: wait until it shows the restored element again
await until(async () => (await tl.locator(".cc-timeline-clip").filter({ hasText: chipName }).count()) > 0);
await page.waitForTimeout(1500);
const s0 = (await scenes()).timing.scenes;
// scene 2's start dragged later: our edge rule moves the shared edge (and snaps it to a word); scene 1 grows to meet it
const second = tl.locator(".cc-timeline-clip").filter({ hasText: "Scene 2" }).first();
await second.scrollIntoViewIfNeeded();                                             // more element rows push the scenes below the fold
await page.waitForTimeout(300);
const box = await second.boundingBox();
await page.mouse.move(box.x + 4, box.y + box.height / 2);                          // the trim handle (the outer 1-2 px move the clip)
await page.mouse.down();
await page.mouse.move(box.x + Math.min(box.width * 0.5, 160), box.y + box.height / 2, { steps: 10 });
await page.mouse.up();
const moved = await until(async () => Math.abs((await scenes()).timing.scenes[0].end - s0[0].end) > 0.05);
const s1 = (await scenes()).timing.scenes;
check("scene 2 starts later and scene 1 ends there (one shared edge, snapped to a word)", moved && Math.abs(s1[0].end - s1[1].start) < 0.001, `${s0[0].end} -> ${s1[0].end}`);
await page.waitForTimeout(800);
await page.keyboard.press("Control+z");
check("Ctrl+Z puts the edge back", await until(async () => Math.abs((await scenes()).timing.scenes[0].end - s0[0].end) < 0.01), `${(await scenes()).timing.scenes[0].end} vs ${s0[0].end}`);
check("no page errors", !errors.length, errors.join(" | ").slice(0, 300));
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
