// The plan review (docs/plans/PLAN-DIRECTOR-MODULES.MD section 8): a reel waits for the person, who reads the plan, changes it and presses Start; nothing is drawn before that.
// Scratch server only (see README). It needs VT_DATA, the scratch server's data folder (the runner passes it), to put the demo project in the "waiting for the plan" state.
import { chromium } from "playwright-core";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { base, chromePath } from "./common.mjs";

const data = process.env.VT_DATA;
if (!data || !fs.existsSync(path.join(data, "projects", "reference", "project.json"))) { console.log("skip: set VT_DATA to the scratch server's data folder (with the reference project)"); process.exit(0); }
const out = path.resolve("e2e/out/plan");
fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p, o) => { const r = await fetch(base + p, o && { method: o.method || "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(o.body ?? {}) }); return r.json(); };
const free = () => new Promise((res) => { const s = net.createServer().listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => res(p)); }); });

// a reel that waits for its plan: a picture server that does not exist (a closed port), no old scenes, the setting "always"
const dir = path.join(data, "projects", "reference");
const meta = JSON.parse(fs.readFileSync(path.join(dir, "project.json"), "utf8"));
meta.options = { ...meta.options, look: "reel" };
meta.status = "review";
fs.writeFileSync(path.join(dir, "project.json"), JSON.stringify(meta));
fs.rmSync(path.join(dir, "scenes.json"), { force: true });
fs.rmSync(path.join(dir, "plan_doc.json"), { force: true });
await api("/api/settings", { method: "PUT", body: { plan_review: "always", comfy_url: `http://127.0.0.1:${await free()}` } });
const made = await api("/api/projects/reference/plan/make", {});
check("the plan is written with no picture drawn", made.plan && made.plan.state === "draft" && made.plan.moments.length >= 2 && made.plan.moments.every((m) => !m.media));

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const errors = [];
const axeSource = process.env.AXE && fs.existsSync(process.env.AXE) ? fs.readFileSync(process.env.AXE, "utf8") : "";
async function axeCheck(page, label) {                         // accessibility: no serious or critical findings on the sheet (AXE=<path to axe.min.js>)
  if (!axeSource) return;
  await page.waitForTimeout(700);                              // the sheet slides in: measure it at rest
  await page.evaluate(axeSource);
  const res = await page.evaluate(() => window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "best-practice"] }, resultTypes: ["violations"] }));
  const bad = res.violations.filter((v) => ["serious", "critical"].includes(v.impact));
  check(`no serious accessibility findings: ${label}`, bad.length === 0, bad.map((v) => `${v.id} x${v.nodes.length} ${v.nodes[0].target.join(" ")}`).join("; "));
}
async function open(vp, scheme) {
  const ctx = await browser.newContext({ viewport: vp, colorScheme: scheme });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  return { ctx, page };
}

console.log("Plan review");
{
  const { ctx, page } = await open({ width: 1280, height: 900 }, "light");
  await page.goto(`${base}/p/reference/progress`, { waitUntil: "domcontentloaded" });
  const sheet = page.getByRole("dialog", { name: "Your plan" });
  await sheet.waitFor({ timeout: 15000 });
  check("a reel that waits opens its plan by itself", await sheet.isVisible() && (await page.getByRole("heading", { name: "Your plan is ready to look at" }).isVisible()));
  check("step 1 says what the video is for", (await sheet.getByTestId("goal").inputValue()).length > 0);
  await page.screenshot({ path: `${out}/step1-1280-light.png` });

  // change the pace: the number of moments changes, and the change is in the log as the person's call
  const before = (await api("/api/projects/reference/plan")).plan.moments.length;
  await sheet.getByRole("button", { name: "Punchy" }).click();
  await page.waitForTimeout(800);
  const after = (await api("/api/projects/reference/plan")).plan;
  check("a punchier pace is saved on the plan", after.idea.pace === "punchy" && after.moments.length >= before, `${before} -> ${after.moments.length}`);

  // ask the director in words
  await sheet.getByTestId("ask-director").fill("fewer pictures");
  await sheet.getByRole("button", { name: "Ask", exact: true }).click();
  await page.waitForTimeout(900);
  const asked = (await api("/api/projects/reference/plan")).plan;
  check("asking for fewer pictures lowers how many are made", asked.estimate.made < asked.moments.length, `${asked.estimate.made}/${asked.moments.length}`);
  await page.getByRole("button", { name: "Continue" }).click();

  // step 2: tap a change, move it to another word
  await sheet.getByRole("group", { name: "Where the picture changes" }).waitFor();
  check("step 2 shows a pin for every change", (await sheet.getByRole("group", { name: "Where the picture changes" }).getByRole("button").count()) === asked.moments.length);
  check("and says in a sentence how the rhythm is", /First change at .* shortest .* longest/.test(await sheet.getByTestId("change-summary").innerText()));
  await sheet.getByRole("button", { name: /^Change 2 at/ }).click();
  const m2 = (await api("/api/projects/reference/plan")).plan.moments[1];
  const other = m2.words.find((w) => w.id !== m2.beat.word_id);
  await sheet.getByRole("group", { name: "Choose the word the picture changes on" }).getByRole("button").filter({ hasText: other.text }).first().click();
  await page.waitForTimeout(700);
  check("choosing another word moves the change", (await api("/api/projects/reference/plan")).plan.moments[1].beat.word_id === other.id);
  await page.screenshot({ path: `${out}/step2-1280-light.png` });
  await page.getByRole("button", { name: "Continue" }).click();

  // step 3: a moment card
  const pick = (await api("/api/projects/reference/plan")).plan.moments.find((m, i) => i > 0 && m.medium === "made").id;
  await sheet.getByTestId(`moment-${pick}`).waitFor();
  await sheet.getByTestId(`moment-${pick}`).getByRole("radio", { name: /Word card/ }).click();
  await page.waitForTimeout(700);
  const p3 = (await api("/api/projects/reference/plan")).plan;
  check("choosing a word card changes the medium and takes the time away", p3.moments.find((m) => m.id === pick).medium === "card" && p3.estimate.made === asked.estimate.made - 1);
  await sheet.getByTestId("lock-s3").click();
  await page.waitForTimeout(600);
  check("locking a moment protects it", (await api("/api/projects/reference/plan")).plan.moments[2].locked === true && await sheet.getByTestId("moment-s3").getByRole("radio", { name: /Made for you/ }).isDisabled());
  const draw = sheet.getByTestId("draw-s1");
  await draw.fill("a dragon of pure Atlantis gold");
  await draw.blur();
  await page.waitForTimeout(700);
  check("words the speech never says are kept but flagged", /not in what is said/.test(await sheet.getByTestId("moment-s1").innerText()));
  await page.screenshot({ path: `${out}/step3-1280-light.png` });
  await axeCheck(page, "the moment cards");
  await page.getByRole("button", { name: "Continue" }).click();

  // step 4: time and cost; nothing has been made
  await sheet.getByTestId("cost-meter").waitFor();
  const tot = await sheet.getByTestId("cost-meter").innerText();
  check("the time and cost are shown before anything is made", /About/.test(tot) && /Made for you/.test(tot));
  const st = await api("/api/projects/reference");
  const calls = (await api("/api/projects/reference/calls")).entries ?? [];
  check("nothing expensive ran before Start", st.status === "review" && (await api("/api/projects/reference/plan")).plan.state === "draft");
  await sheet.getByTestId("fewer").click();
  await page.waitForTimeout(600);
  check("making one fewer picture changes the time at once", (await api("/api/projects/reference/plan")).plan.estimate.made === p3.estimate.made - 1);
  await page.screenshot({ path: `${out}/step4-1280-light.png` });
  await axeCheck(page, "the last step");

  // it survives a reload
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("dialog", { name: "Your plan" }).waitFor({ timeout: 15000 });
  check("the plan survives a reload, still waiting", (await api("/api/projects/reference")).status === "review");
  await ctx.close();
}

console.log("Start");
{
  const { ctx, page } = await open({ width: 1280, height: 900 }, "light");
  await page.goto(`${base}/p/reference/progress`, { waitUntil: "domcontentloaded" });
  const sheet = page.getByRole("dialog", { name: "Your plan" });
  await sheet.waitFor({ timeout: 15000 });
  for (let i = 0; i < 3; i++) await sheet.getByRole("button", { name: "Continue" }).click();
  await sheet.getByRole("button", { name: "Start making" }).click();
  let state = "";
  for (let i = 0; i < 90 && state !== "done"; i++) { await page.waitForTimeout(1000); state = (await api("/api/projects/reference/plan")).plan.state; }
  for (let i = 0; i < 60; i++) { const jobs = await api("/api/jobs"); if (!jobs.some((j) => j.project === "reference" && ["queued", "running"].includes(j.status))) break; await page.waitForTimeout(1000); }      // and the whole job, compose included
  const done = (await api("/api/projects/reference/plan")).plan;
  check("Start makes exactly what was approved", done.state === "done" && done.approved_by === "person", done.state);
  check("without the picture server every picture moment says so and a word card is shown", done.moments.filter((m) => m.medium === "made").every((m) => m.status === "failed" && m.problem));
  check("the card moment was never asked for a picture", done.moments.filter((m) => m.medium === "card").every((m) => m.status === "ready"));
  const scenes = await api("/api/projects/reference/scenes");
  check("the video has one scene for every moment", (scenes.plan?.scenes ?? scenes.scenes ?? []).length === done.moments.length);
  const log = await api("/api/projects/reference/calls");
  const rows = Array.isArray(log) ? log : log.entries ?? log.calls ?? [];
  check("the person's edits are in the director's log", rows.some((r) => r.module === "plan.edit") && rows.some((r) => r.module === "plan.approve"));
  await page.screenshot({ path: `${out}/board-1280-light.png` });
  await ctx.close();
}

console.log("Looks");
for (const [vp, scheme] of [[{ width: 390, height: 844 }, "light"], [{ width: 390, height: 844 }, "dark"], [{ width: 1280, height: 900 }, "dark"]]) {
  // a fresh draft each time, so the sheet can be photographed on every size
  fs.rmSync(path.join(dir, "plan_doc.json"), { force: true });
  const m = JSON.parse(fs.readFileSync(path.join(dir, "project.json"), "utf8"));
  m.status = "review";
  fs.writeFileSync(path.join(dir, "project.json"), JSON.stringify(m));
  fs.rmSync(path.join(dir, "scenes.json"), { force: true });
  await api("/api/projects/reference/plan/make", {});
  const { ctx, page } = await open(vp, scheme);
  await page.goto(`${base}/p/reference/progress`, { waitUntil: "domcontentloaded" });
  const sheet = page.getByRole("dialog", { name: "Your plan" });
  await sheet.waitFor({ timeout: 15000 });
  const tag = `${vp.width}-${scheme}`;
  await page.screenshot({ path: `${out}/step1-${tag}.png` });
  await axeCheck(page, `step 1 at ${tag}`);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.screenshot({ path: `${out}/step3-${tag}.png` });
  await axeCheck(page, `the cards at ${tag}`);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.screenshot({ path: `${out}/step4-${tag}.png` });
  const box = await sheet.boundingBox();
  check(`the sheet fits the screen at ${tag}`, box.width <= vp.width + 1 && box.height <= vp.height + 1);
  const sideways = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check(`no sideways scroll at ${tag}`, sideways <= 0, String(sideways));
  await ctx.close();
}

console.log("From the editor");
{
  // a reel that is already made: the editor offers to change its look or pictures, as a plan first
  await api("/api/projects/reference/plan/approve", {});                      // make it first (the last draft of the loop above), so there is a video to change
  for (let i = 0; i < 90; i++) {
    const done = (await api("/api/projects/reference/plan")).plan.state === "done";
    const busy = (await api("/api/jobs")).some((j) => j.project === "reference" && ["queued", "running"].includes(j.status));
    if (done && !busy) break;
    await new Promise((r) => setTimeout(r, 1000));
  }
  const { ctx, page } = await open({ width: 1280, height: 900 }, "light");
  await page.goto(`${base}/p/reference`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "AI", exact: true }).click();
  const btn = page.getByTestId("reel-plan");
  await btn.waitFor({ timeout: 15000 });
  await btn.click();
  const sheet = page.getByRole("dialog", { name: "Your plan" });
  await sheet.waitFor({ timeout: 15000 });
  const fresh = (await api("/api/projects/reference/plan")).plan;
  check("the editor opens a fresh plan to change the look or the pictures", fresh.state === "draft" && (await sheet.getByRole("button", { name: "Cinematic photo" }).isVisible()));
  await page.getByRole("button", { name: "Later" }).click();
  check("closing it leaves the video as it is", (await api("/api/projects/reference")).status === "planned");
  await ctx.close();
}

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
