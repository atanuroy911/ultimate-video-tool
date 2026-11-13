// The director chat beside the timeline (docs/plans/PLAN-OPENCHATCUT.MD phase 4), for real: a note goes to the director (the AI chosen in
// Settings), its steps show while it works, its reply says what changed, and the timeline is rebuilt from the changed project.
// MUTATING and uses the AI (a minute or two): a scratch server and a copy.   VT_PROJECT=<copy> node e2e/occ_director_chat.mjs
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://localhost:5291";
const pid = process.env.VT_PROJECT;
const note = process.env.VT_NOTE || "In the first scene, show a big title that says: Tiny habits, big change.";
if (!pid) { console.log("set VT_PROJECT to a copy"); process.exit(2); }
const out = path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1")), "out", "occ-director");
fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0;
const check = (name, ok, detail = "") => { if (ok) { pass++; console.log("  ok  ", name); } else { fail++; console.log(`  FAIL ${name}${detail ? " :: " + detail : ""}`); } };

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await ctx.addInitScript(() => { try { localStorage.setItem("vt-timeline", "new"); } catch {} });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
await page.getByTestId("occ-timeline").waitFor({ timeout: 20000 });
await page.getByRole("button", { name: "Director", exact: true }).click();
const chat = page.getByTestId("director-chat");
await chat.waitFor();
check("the Director tab opens the chat beside the preview and the timeline", await page.getByTestId("occ-timeline").isVisible());
const planOf = async () => JSON.stringify((await (await fetch(`${base}/api/projects/${pid}/scenes`)).json()).plan);
  const scriptOf = async () => JSON.stringify((await (await fetch(`${base}/api/projects/${pid}/script`)).json()).script);
const planBefore = await planOf();
  const scriptBefore = await scriptOf();
await chat.getByRole("textbox", { name: "Message to the director" }).fill(note);
await chat.getByRole("button", { name: "Send" }).click();
check("the note shows in the conversation at once", await chat.getByText(note).first().isVisible());
await page.waitForTimeout(4000);
check("while it works, the chat says so and the box waits", await chat.getByRole("button", { name: "Working…" }).isVisible());
check("nothing covers the editor while it works (no full-screen progress window)", !(await page.getByText("The director is working on your note").isVisible().catch(() => false)));
check("the AI gradient shields timeline edits while the Director owns the plan", await page.getByTestId("director-timeline-block").isVisible());
check("the timeline stays visible underneath the shield", (await page.locator(".cc-timeline-clip").count()) > 0);
await page.screenshot({ path: path.join(out, "working.png") });
const done = await chat.getByRole("button", { name: "Send" }).waitFor({ timeout: 600000 }).then(() => true).catch(() => false);
check("the director finishes (within 10 minutes)", done);
await page.waitForTimeout(2500);
check("timeline editing unlocks when the Director finishes", !(await page.getByTestId("director-timeline-block").isVisible().catch(() => false)));
const text = await chat.innerText();
const lastReply = text.split(note).pop() ?? "";
check("its reply says what it did", /Changed|now has|Nothing needed|could not/i.test(lastReply), lastReply.slice(0, 200));
const planAfter = await planOf();
  const scriptAfter = await scriptOf();
check("the video itself changed (saved on the server)", planAfter !== planBefore || /Nothing needed/.test(lastReply));
check("the timeline is there and shows the video after the change", (await page.locator(".cc-timeline-clip").count()) > 0);
  if (planAfter !== planBefore) {
    const changedLinks = chat.getByRole("group", { name: "Scenes changed by the Director" }).getByRole("button");
    check("the reply names the changed scenes as buttons", await changedLinks.count() > 0);
    check("changed scene and element clips are marked on the timeline", await page.locator(".cc-timeline-clip.is-director-changed").count() > 0);
    const history = chat.getByTestId("director-history");
    check("the reply offers to undo the Director's change", await history.isVisible() && /Undo/.test(await history.innerText()));
    await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
    await page.keyboard.press("Control+Z");
    await page.waitForFunction(async ({ base, pid, before }) => JSON.stringify((await (await fetch(`${base}/api/projects/${pid}/scenes`)).json()).plan) === before,
      { base, pid, before: planBefore }, { timeout: 30000 });
    check("Ctrl+Z undoes the Director as one editor step", await planOf() === planBefore);
    check("undo restores the Director script with the plan", await scriptOf() === scriptBefore);
    await history.filter({ hasText: "Redo" }).waitFor({ timeout: 10000 });
    await history.click();
    await page.waitForFunction(async ({ base, pid, after }) => JSON.stringify((await (await fetch(`${base}/api/projects/${pid}/scenes`)).json()).plan) === after,
      { base, pid, after: planAfter }, { timeout: 30000 });
    check("the reply button can redo the Director's change", await planOf() === planAfter);
    check("redo restores the changed Director script with the plan", await scriptOf() === scriptAfter);
    await history.filter({ hasText: "Undo" }).waitFor({ timeout: 10000 });
    await history.click();
    await page.waitForFunction(async ({ base, pid, before }) => JSON.stringify((await (await fetch(`${base}/api/projects/${pid}/scenes`)).json()).plan) === before,
      { base, pid, before: planBefore }, { timeout: 30000 });
    check("the reply button restores the exact plan from before the Director", await planOf() === planBefore);
    check("the final state keeps script and plan on the same version", await scriptOf() === scriptBefore);
    await changedLinks.first().click();
    check("a changed-scene button jumps to its scene", await page.locator('.cc-timeline-clip.is-selected[data-item-id^="scene:"]').count() > 0);
  }
await page.screenshot({ path: path.join(out, "done.png") });
check("no page errors", !errors.length, errors.join(" | ").slice(0, 300));
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
