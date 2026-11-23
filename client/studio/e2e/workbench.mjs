// The editor's workbench in a real browser: the five panes, dragging a divider, hiding and showing panes with the buttons and the keys, and the sizes
// surviving a reload. Needs the Studio (dev server or desktop) and a project with a plan.
//   VT_URL=http://localhost:5173 VT_PROJECT=<project id> VT_CHROME=<chrome.exe> node e2e/workbench.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "reference";
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));

const box = async (pane) => page.evaluate((p) => { const e = document.querySelector(`.wb-${p}`); if (!e || e.hidden) return null; const r = e.getBoundingClientRect(); return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) }; }, pane);
const open = async () => {
  await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
  await page.waitForSelector(".wb .wb-viewer", { timeout: 45000 });
  await page.waitForTimeout(800);
};

await open();
await page.evaluate(() => localStorage.removeItem("vt.workbench.v1.editor"));
await page.reload({ waitUntil: "load" });
await page.waitForSelector(".wb .wb-viewer");
await page.waitForTimeout(800);

// 1. the layout of OpenFilm's editor
let lib = await box("library"), view = await box("viewer"), insp = await box("inspector"), tl = await box("timeline"), asst = await box("assistant");
check("all five panes are there", !!(lib && view && insp && tl && asst));
check("library | viewer | inspector across the top, left to right", lib.x < view.x && view.x < insp.x, JSON.stringify({ lib: lib.x, view: view.x, insp: insp.x }));
check("the timeline is under them and the assistant is the full height on the right", tl.y >= view.y + view.h - 1 && asst.h > view.h + tl.h - 4 && asst.x > insp.x);
check("the default sizes (library 280, inspector 300, assistant 400, timeline 300)", lib.w === 280 && insp.w === 300 && asst.w === 400 && tl.h === 300, JSON.stringify({ lib: lib.w, insp: insp.w, asst: asst.w, tl: tl.h }));
const clipped = await page.evaluate(() => [".ed-left", ".ed-right", ".ed-canvas", ".ed-timeline"].filter((s) => { const e = document.querySelector(s), p = e?.parentElement; return e && p && e.getBoundingClientRect().width < p.getBoundingClientRect().width - 2; }));
check("every panel fills its pane (no old width caps)", clipped.length === 0, clipped.join(","));

// 2. drag the divider between the library and the viewer
const seams = page.locator(".wb-seam-x");
const libSeam = seams.nth(await page.evaluate(() => [...document.querySelectorAll(".wb-seam-x")].findIndex((s) => Math.abs(s.getBoundingClientRect().left - 280) < 3)));
const sb = await libSeam.boundingBox();
await page.mouse.move(sb.x + 0.5, sb.y + 200);
await page.mouse.down();
await page.mouse.move(sb.x + 100, sb.y + 200, { steps: 6 });
await page.mouse.up();
await page.waitForTimeout(300);
lib = await box("library");
check("dragging the divider makes the library about 100 px wider", lib.w >= 370 && lib.w <= 390, `width ${lib.w}`);
view = await box("viewer");
check("the viewer gave up that room", view.x === lib.x + lib.w + 1 && view.w > 100);

// 3. the sizes are remembered
await page.reload({ waitUntil: "load" });
await page.waitForSelector(".wb .wb-viewer");
await page.waitForTimeout(800);
check("after a reload the library is still the width it was dragged to", (await box("library")).w === lib.w, `width ${(await box("library")).w}`);

// 4. hide and show with the buttons
const press = (name) => page.getByRole("button", { name }).first().click();
await press(/Assistant/);
await page.waitForTimeout(250);
check("the Assistant button hides the assistant, and the others take its room", (await box("assistant")) === null && (await box("timeline")).w === 1440);
await press(/Assistant/);
await page.waitForTimeout(250);
check("and shows it again at the same width", (await box("assistant"))?.w === 400);
await press(/Timeline/);
await page.waitForTimeout(250);
check("the Timeline button hides the timeline; the viewer grows downwards", (await box("timeline")) === null && (await box("viewer")).h > 600);
await press(/Timeline/);
await page.waitForTimeout(250);
check("and brings it back", (await box("timeline"))?.h === 300);

// 5. the keys (not while typing)
await page.locator(".ed-canvas").click({ position: { x: 5, y: 5 } }).catch(() => {});
await page.keyboard.press("Control+j");
await page.waitForTimeout(250);
check("Ctrl+J hides the timeline", (await box("timeline")) === null);
await page.keyboard.press("Control+j");
await page.keyboard.press("Control+Alt+b");
await page.waitForTimeout(250);
check("Ctrl+Alt+B hides the assistant", (await box("assistant")) === null);
await page.keyboard.press("Control+l");
await page.waitForTimeout(400);
check("Ctrl+L shows the assistant and puts the cursor in its message box", !!(await box("assistant")) && (await page.evaluate(() => document.activeElement?.tagName === "TEXTAREA" && !!document.activeElement.closest(".wb-assistant"))));
await page.keyboard.type("hello");
await page.keyboard.press("Control+j");
await page.waitForTimeout(250);
check("while typing in a field, Ctrl+J does not hide the timeline", !!(await box("timeline")));
check("what was typed is still there", (await page.evaluate(() => document.activeElement?.value)) === "hello");

// 6. the divider by keyboard, and double-click resets
const asstIndex = await page.evaluate(() => { const a = document.querySelector(".wb-assistant").getBoundingClientRect().left; return [...document.querySelectorAll(".wb-seam-x")].findIndex((s) => Math.abs(s.getBoundingClientRect().left - (a - 1)) < 3); });
await page.locator(".wb-seam-x").nth(asstIndex).focus();
const before = (await box("assistant")).w;
await page.keyboard.press("ArrowLeft");
await page.waitForTimeout(250);
check("a focused divider moves with the arrow keys (16 px)", (await box("assistant")).w === before + 16, `${before} -> ${(await box("assistant")).w}`);

// 7. a small window
await page.setViewportSize({ width: 1000, height: 700 });
await page.waitForTimeout(500);
const v2 = await box("viewer");
check("in a small window the viewer keeps a usable size", v2.w >= 320 && v2.h >= 200, JSON.stringify(v2));

check("no page errors", errors.length === 0, errors.join(" | "));
await browser.close();
console.log(`\nWorkbench: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
