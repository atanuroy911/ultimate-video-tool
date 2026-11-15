// A change to the plan made outside the editor's own edit calls (an assistant over MCP, a picture drawn again) becomes an undo step of its own,
// and the editor's own edits are still exactly one step each (src/review/useReview.ts).
// MUTATING (every change is undone at the end): run against a scratch server.  VT_URL=<studio> VT_PROJECT=reference node e2e/outside_change_undo.mjs
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://localhost:5291";
const pid = process.env.VT_PROJECT || "reference";
let pass = 0, fail = 0;
const check = (name, ok, detail = "") => { if (ok) { pass++; console.log("  ok  ", name); } else { fail++; console.log(`  FAIL ${name}${detail ? " :: " + detail : ""}`); } };
const until = async (fn, ms = 15000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await fn()) return true; await new Promise((r) => setTimeout(r, 250)); } return false; };

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await ctx.addInitScript(() => { try { localStorage.setItem("vt-timeline", "classic"); } catch {} });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
const undo = page.getByRole("button", { name: "Undo", exact: true });
const redo = page.getByRole("button", { name: "Redo", exact: true });
await undo.waitFor({ timeout: 20000 });
await page.waitForTimeout(1500);
// the page's own session reaches the server (the dev proxy adds the key): requests made from inside the page are the "outside" writer
const api = (path, method = "GET", body) => page.evaluate(async ([path, method, body]) => {
  const r = await fetch(path, { method, headers: body ? { "content-type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  return { status: r.status, json: await r.json().catch(() => null) };
}, [path, method, body]);
const plan = async () => (await api(`/api/projects/${pid}/scenes`)).json.plan;
const captionY = async (i = 0) => (await plan()).scenes[i].caption?.y ?? null;

console.log("Nothing has been edited yet");
check("Undo is off when the editor opens", await undo.isDisabled());
const start = await plan();
const sid = start.scenes[0].id;
const y0 = start.scenes[0].caption?.y ?? null;

console.log("A change from outside the editor (the same call an assistant's update_scene makes)");
const res = await api(`/api/projects/${pid}/scenes/${sid}`, "PATCH", { caption: { ...(start.scenes[0].caption ?? { highlight_words: [] }), y: 0.27 } });
check("the outside change is saved", res.status === 200 && (await captionY()) === 0.27, `status ${res.status}`);
check("the editor offers to undo it", await until(async () => !(await undo.isDisabled())));
await undo.click();
check("Undo puts the plan back as it was before the outside change", await until(async () => (await captionY()) === y0), `caption.y ${await captionY()}`);
check("that was the only step: Undo is off again", await until(async () => await undo.isDisabled()));
check("Redo brings the outside change back", await (async () => { await redo.click(); return until(async () => (await captionY()) === 0.27); })());
await undo.click();
await until(async () => (await captionY()) === y0);

console.log("The editor's own edit is still one step");
await page.keyboard.press("Escape");
const count = async () => (await plan()).scenes.reduce((n, s) => n + s.elements.length, 0);
const before = await count();
const chip = page.locator(".tl-element-name").first();
if (await chip.count()) {
  await chip.click();
  await page.keyboard.press("Delete");
  check("an element deleted on the timeline is removed", await until(async () => (await count()) === before - 1), `${before} -> ${await count()}`);
  await page.waitForTimeout(1200);                              // the change event from the server arrives after the edit's own reload
  await page.keyboard.press("Control+z");
  check("one Ctrl+Z brings it back", await until(async () => (await count()) === before), `${await count()} vs ${before}`);
  check("and nothing else is left to undo", await until(async () => await undo.isDisabled(), 4000));
} else {
  console.log("  (no element chip found on the classic timeline: own-edit check skipped)");
}

check("no page errors", errors.length === 0, errors.join(" | "));
check("the plan is as it was at the start", JSON.stringify(await plan()) === JSON.stringify(start));
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
