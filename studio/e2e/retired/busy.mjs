// The full-screen loading layer: nothing for fast operations; for slow ones a modal with the title, the step, progress, time, Cancel / Keep working; focus inside and the page behind inert;
// a failing job shows its reason with a Close button. The behaviour cases use a stand-in job answered by the browser (page.route); the last case follows a REAL export job of the scratch project.
//   VT_URL=http://127.0.0.1:8771 VT_PROJECT=reference node e2e/busy.mjs
import { chromium } from "playwright-core";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "reference";
const browser = await chromium.launch({ executablePath: chromePath() });
const page = await (await browser.newContext({ viewport: { width: 1300, height: 900 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const layer = page.locator(".busy-layer");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const json = (route, body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

console.log("Loading layer");
await page.goto(`${base}/settings`, { waitUntil: "networkidle" });
const testBtn = page.getByRole("button", { name: "Test the AI" });

// 1. a fast operation never shows it
await page.route("**/api/ai/test", async (route) => { await sleep(120); json(route, { ok: true, message: "fast", sample: "x" }); });
await testBtn.click();
let seen = false;
for (let i = 0; i < 14; i++) { if (await layer.count()) seen = true; await sleep(50); }
check("a fast operation shows no layer", !seen);
await page.unroute("**/api/ai/test");

// 2. a slow plain request shows it after a moment, as a modal with focus inside and the page behind inert, then removes it
await page.route("**/api/ai/test", async (route) => { await sleep(2200); json(route, { ok: true, message: "slow", sample: "y" }); });
const t0 = Date.now();
await testBtn.click();
await layer.waitFor({ state: "visible", timeout: 3000 });
const appeared = Date.now() - t0;
check("a slow operation shows the layer after about 0.4 s", appeared > 300 && appeared < 1200, String(appeared));
const dlg = page.getByRole("alertdialog");
check("it is a modal alert dialog with a title that says what is happening", (await dlg.getAttribute("aria-modal")) === "true" && /Testing the AI/.test(await dlg.innerText()));
check("focus is inside it and the page behind is inert", (await page.evaluate(() => !!document.activeElement?.closest(".busy-card"))) && (await page.evaluate(() => document.getElementById("root").hasAttribute("inert"))));
check("a spinner or bar and the elapsed time are shown", (await dlg.locator(".busy-indeterminate, [role=progressbar]").count()) === 1 && /passed/.test(await dlg.innerText()));
await layer.waitFor({ state: "detached", timeout: 6000 });
check("it goes away when the operation ends and the page is usable again", !(await page.evaluate(() => document.getElementById("root").hasAttribute("inert"))));
check("focus returns to where it was", await page.evaluate(() => document.activeElement?.textContent?.includes("Test the AI") ?? false));
await page.unroute("**/api/ai/test");

// 3. a job: its own title, step and progress; the step changes; Cancel is offered; a failure shows the reason with Close
let polls = 0;
await page.route("**/api/ai/test", (route) => json(route, { id: "fake1", kind: "x", status: "running", frac: 0.25, msg: "Drawing scene 2 of 8", label: "Planning the scenes", project: null, stage: "", result: null, error: "" }));
await page.route("**/api/jobs/fake1", (route) => {
  polls++;
  if (polls < 5) return json(route, { id: "fake1", kind: "x", status: "running", frac: 0.25 + polls * 0.1, msg: polls < 3 ? "Drawing scene 2 of 8" : "Drawing scene 5 of 8", label: "Planning the scenes", result: null, error: "" });
  json(route, { id: "fake1", kind: "x", status: "error", frac: 0.6, msg: "", label: "Planning the scenes", result: null, error: "the model ran out of memory" });
});
await testBtn.click();
await layer.waitFor({ state: "visible", timeout: 3000 });
const d3 = page.getByRole("alertdialog");
await sleep(500);
check("a job shows its own title, its step and a real progress bar", /Planning the scenes/.test(await d3.innerText()) && /Drawing scene \d of 8/.test(await d3.innerText()) && (await d3.getByRole("progressbar").count()) === 1);
check("Cancel and Keep working are offered for a job", (await d3.getByRole("button", { name: "Cancel" }).count()) === 1 && (await d3.getByRole("button", { name: /Keep working/ }).count()) === 1);
await page.waitForFunction(() => /did not work/.test(document.querySelector(".busy-card")?.textContent || ""), null, { timeout: 8000 });
check("a failing job keeps the layer with the reason and a Close button", /ran out of memory/.test(await d3.innerText()) && (await d3.getByRole("button", { name: "Close" }).count()) === 1);
await d3.getByRole("button", { name: "Close" }).click();
await layer.waitFor({ state: "detached", timeout: 3000 });
check("Close removes it", true);
await page.unroute("**/api/ai/test"); await page.unroute("**/api/jobs/fake1");

// 4. Cancel asks the server to cancel the job; Escape does the same; Keep working hides the layer while the job goes on
let cancelled = 0, status = "running";
await page.route("**/api/ai/test", (route) => json(route, { id: "fake2", kind: "x", status: "running", frac: 0.1, msg: "Working", label: "Making the voice", result: null, error: "" }));
await page.route("**/api/jobs/fake2", (route) => json(route, { id: "fake2", kind: "x", status, frac: 0.1, msg: "Working", label: "Making the voice", result: null, error: "" }));
await page.route("**/api/jobs/fake2/cancel", (route) => { cancelled++; status = "cancelled"; json(route, { ok: true }); });
await testBtn.click();
await layer.waitFor({ state: "visible", timeout: 3000 });
await page.keyboard.press("Escape");
await layer.waitFor({ state: "detached", timeout: 4000 });
check("Escape cancels a cancellable job (the server was asked) and the layer ends", cancelled === 1);
status = "running";
await testBtn.click();
await layer.waitFor({ state: "visible", timeout: 3000 });
await page.getByRole("button", { name: /Keep working/ }).click();
await sleep(300);
check("Keep working hides the layer while the job continues", (await layer.count()) === 0);
status = "done";
await sleep(1500);
await page.unroute("**/api/ai/test"); await page.unroute("**/api/jobs/fake2"); await page.unroute("**/api/jobs/fake2/cancel");
check("a finished background job says so in a toast", /finished/.test(await page.locator("body").innerText()));

// 5. Tab stays inside the layer
await page.route("**/api/ai/test", async (route) => { await sleep(2500); json(route, { ok: true, message: "slow", sample: "y" }); });
await testBtn.click();
await layer.waitFor({ state: "visible", timeout: 3000 });
for (let i = 0; i < 4; i++) await page.keyboard.press("Tab");
check("Tab never leaves the layer", await page.evaluate(() => !!document.activeElement?.closest(".busy-card")));
await layer.waitFor({ state: "detached", timeout: 6000 });
await page.unroute("**/api/ai/test");

// 5b. work the Studio asks for by itself (thumbnails) is slow but nobody waits for it: it must never raise the layer
let thumbs = 0;
await page.route("**/api/projects/*/thumbnails**", async (route) => { thumbs++; await sleep(2000); json(route, { ok: true }); });
await page.goto(`${base}/p/${pid}`, { waitUntil: "domcontentloaded" });
let blocked = false;
for (let i = 0; i < 40; i++) { if (await layer.count()) blocked = true; await sleep(100); }
check("a slow background request (thumbnails) never shows the layer", thumbs >= 1 && !blocked, `requests ${thumbs}`);
await page.unroute("**/api/projects/*/thumbnails**");

// 6. a REAL job: an export of the scratch project, started from the Export page
await page.goto(`${base}/p/${pid}/export`, { waitUntil: "networkidle" });
await page.getByRole("button", { name: /Make|Export|Render/i }).first().click();
await layer.waitFor({ state: "visible", timeout: 6000 });
const dr = page.getByRole("alertdialog");
await sleep(2500);
const txt = await dr.innerText();
check("a real export shows a title, a step in words and the time", /video|Making|Export|Rendering/i.test(txt) && /passed/.test(txt), txt.replace(/\n/g, " | ").slice(0, 160));
await page.screenshot({ path: path.join(path.dirname(fileURLToPath(import.meta.url)), "out", "busy-real-export.png") });
const cancelBtn = dr.getByRole("button", { name: "Cancel" });
if (await cancelBtn.count()) { await cancelBtn.click(); await layer.waitFor({ state: "detached", timeout: 20000 }); check("Cancel stops the real export and the layer ends", true); }
else check("the real export offered Cancel", false);

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
