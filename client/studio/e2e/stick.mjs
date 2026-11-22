// Stick-figure videos in the editor: characters panel, action list, dragging an action to another word, undo.
// Needs a project with a stick-figure plan:  VT_PROJECT=<id> node e2e/stick.mjs
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const pid = process.env.VT_PROJECT;
if (!pid) { console.log("skip: set VT_PROJECT to a stick-figure project"); process.exit(0); }
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
await page.addInitScript(() => { try { localStorage.setItem("vt-timeline", "classic"); } catch {} });          // this suite tests the Classic timeline (the New one is the default since W11.2)
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("response", (r) => r.status() >= 500 && errors.push(r.status() + " " + r.url()));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p) => (await fetch(base + p)).json();

console.log("Stick figures in the editor");
await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
await page.waitForSelector(".scene-card");
const plan0 = (await api(`/api/projects/${pid}/scenes`)).plan.scenes;
check("the plan has stick-figure scenes", plan0.every((s) => s.stick && s.stick.actions.length > 0));
check("the timeline has an Actions lane with chips", (await page.getByRole("group", { name: "Actions" }).getByRole("button").count()) >= 3);
await page.locator(".inspector").getByText(/^Characters/).click();          // characters and their actions have their own tab
check("stick actions are listed in the inspector", (await page.getByText(/Actions & Poses \(\d+\)/).count()) === 1);
await page.locator(".cast-head").first().click();

// characters
const col = page.getByLabel(/^Accessory of /).first();
const cid = (plan0[0].stick.cast[0]).id;
await col.selectOption("hat");
await page.waitForTimeout(1500);
let cast = (await api(`/api/projects/${pid}/scenes`)).plan.scenes[0].stick.cast.find((c) => c.id === cid);
check("changing the accessory is saved for the character", cast.style.accessory === "hat", JSON.stringify(cast));
const data = await api(`/media/${pid}/composition/9x16/data.json`);
check("the composition carries the new look", data.scenes[0].stick.cast.find((c) => c.id === cid).style.accessory === "hat");
await page.keyboard.press("Control+z");
await page.waitForTimeout(1500);
cast = (await api(`/api/projects/${pid}/scenes`)).plan.scenes[0].stick.cast.find((c) => c.id === cid);
check("undo restores the look", cast.style.accessory === (plan0[0].stick.cast.find((c) => c.id === cid).style.accessory ?? "none"), JSON.stringify(cast));

// drag the first action chip of scene 1 to a later word
const chip = page.getByRole("group", { name: "Actions" }).getByRole("button").first();
const b = await chip.boundingBox();
await page.mouse.move(b.x + 4, b.y + b.height / 2);
await page.mouse.down();
await page.mouse.move(b.x + 160, b.y + b.height / 2, { steps: 8 });
await page.mouse.up();
await page.waitForTimeout(1500);
const plan1 = (await api(`/api/projects/${pid}/scenes`)).plan.scenes;
const before = plan0[0].stick.actions[0], after = plan1[0].stick.actions.find((a) => a.do === before.do && a.who === before.who);
check("dragging an action chip re-timed it to a later word", after && after.start > before.start + 0.2, `${before.start} -> ${after && after.start}`);
await page.keyboard.press("Control+z");
await page.waitForTimeout(1500);
const plan2 = (await api(`/api/projects/${pid}/scenes`)).plan.scenes;
check("undo puts the action back", Math.abs(plan2[0].stick.actions.find((a) => a.do === before.do).start - before.start) < 0.01);

// delete from the list
const n = plan2[0].stick.actions.length;
await page.locator("[data-scene]").nth(0).click();          // undo may have moved the selection: delete from scene 1, which is what is counted
await page.waitForTimeout(500);
await page.getByRole("button", { name: /^Delete action/ }).first().click();
await page.waitForTimeout(1500);
check("deleting an action from the list works", (await api(`/api/projects/${pid}/scenes`)).plan.scenes[0].stick.actions.length === n - 1);
await page.keyboard.press("Control+z");
await page.waitForTimeout(1200);
await page.screenshot({ path: out + "/k1-stick-editor.png" });
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
