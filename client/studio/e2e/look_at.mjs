// What is left to look at, in the Quality check on the finished-video page (PLAN-PERFECT B2): the facts a director's last look left standing, or what the layout guard changed on a plan the rules made.
// The server's answer is stood in for by the script below (an older server has no such answer, and then nothing is shown), so this changes nothing on any server:
//   cd client/studio && VT_SERVER_URL=http://<a server> npx vite --port 5176 --strictPort --host 127.0.0.1
//   VT_URL=http://127.0.0.1:5176 VT_PROJECT=<a project id> node e2e/look_at.mjs [out dir]
import fs from "node:fs";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://127.0.0.1:5176";
const project = process.env.VT_PROJECT || "reference";
const out = process.argv[2] || "e2e/out/look_at";
fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };

const TAG = "element 1 (tag) has letters too small to read on a phone.";
const LEFT = { planner: "claude", looked: true, current: true, guard_current: false, changed: [], left: [{ scene: "s2", number: 2, at: 3, facts: [TAG, "element 3 (sticker) is 40% outside the frame."] }, { scene: "s5", number: 5, at: 9, facts: ["There is no free room beside the person in the picture for this scene's elements: they sit on the picture."] }] };
const CLEAN = { ...LEFT, left: [] };
const STALE = { ...LEFT, current: false };
const NEVER = { ...LEFT, looked: false, left: [] };
const RULES = { planner: "rules", looked: false, current: false, left: [], guard_current: true, changed: [{ scene: "s3", number: 3, says: ["the tag had letters too small to read on a phone, so it was hidden", "the keyword ran off the frame, so it was made smaller to fit"] }] };

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
async function open(answer, viewport = { width: 1280, height: 900 }, scheme = "light") {
  const ctx = await browser.newContext({ viewport, colorScheme: scheme });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/projects/*/look-at", (route) => (answer === 404 ? route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not found" }) }) : route.fulfill({ json: answer })));
  await page.goto(`${base}/p/${project}/result`, { waitUntil: "networkidle" });
  await page.locator('.result-quality > summary').click();
  await page.getByTestId("quality").waitFor();
  await page.waitForTimeout(300);
  return { page, ctx, errors };
}
const text = (page) => page.getByTestId("quality").innerText();

console.log("What is left to look at");
{
  const { page, ctx, errors } = await open(LEFT);
  const box = page.getByTestId("look-left");
  check("what the director left is listed", await box.isVisible());
  const t = await box.innerText();
  check("each finding names its scene by number", t.includes("Scene 2: " + TAG) && t.includes("Scene 2: element 3 (sticker)") && t.includes("Scene 5: There is no free room"), t);
  check("it is called what it is", t.startsWith("Left to look at"));
  check("a plan the director looked at and the person has not changed has no warning", !t.includes("has changed since"));
  check("nothing is claimed to be fixed", !(await text(page)).includes("nothing is left to fix"));
  await page.screenshot({ path: `${out}/left-wide.png` });
  check("no page errors", errors.length === 0, errors.join("; "));
  await ctx.close();
}
{
  const { page, ctx } = await open(CLEAN);
  check("a clean cut says so", (await page.getByTestId("look-none").innerText()).includes("nothing is left to fix"));
  check("and lists nothing", (await page.getByTestId("look-left").count()) === 0);
  await ctx.close();
}
{
  const { page, ctx } = await open(STALE);
  check("a plan the person changed since is said to have changed", (await page.getByTestId("look-left").innerText()).includes("the plan has changed since the director looked"));
  await ctx.close();
}
{
  const { page, ctx } = await open(NEVER);
  check("a cut nobody measured claims nothing", (await page.getByTestId("look-none").count()) === 0 && (await page.getByTestId("look-left").count()) === 0 && (await page.getByTestId("look-changed").count()) === 0);
  await ctx.close();
}
{
  const { page, ctx, errors } = await open(RULES);
  const t = await page.getByTestId("look-changed").innerText();
  check("what the layout guard changed on a rule plan is listed", t.startsWith("Changed by the layout guard") && t.includes("Scene 3: the tag had letters too small to read on a phone, so it was hidden; the keyword ran off the frame, so it was made smaller to fit."), t);
  check("it says an AI's plan is not changed this way", t.includes("never changed this way"));
  check("a guard reading of the plan as it stands has no warning", !t.includes("has changed since"));
  check("no page errors", errors.length === 0, errors.join("; "));
  await ctx.close();
}
{
  const { page, ctx } = await open({ ...RULES, guard_current: false });
  check("a plan changed since the guard was read is said so", (await page.getByTestId("look-changed").innerText()).includes("(the plan has changed since)"));
  await ctx.close();
}
{
  const { page, ctx, errors } = await open(404);
  const t = await text(page);
  check("an older server (no such answer) shows the card as before", t.includes("Quality checks") && !t.includes("Left to look at") && !t.includes("layout guard"), t);
  check("and nothing breaks", errors.length === 0, errors.join("; "));
  await ctx.close();
}
for (const [name, viewport, scheme] of [["phone-dark", { width: 400, height: 860 }, "dark"], ["phone-light", { width: 400, height: 860 }, "light"]]) {
  const { page, ctx } = await open(LEFT, viewport, scheme);
  const card = page.getByTestId("quality");
  const overflow = await card.evaluate((el) => el.scrollWidth - el.clientWidth);
  check(`${name}: the card does not scroll sideways`, overflow <= 1, String(overflow));
  const page_overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check(`${name}: the page does not scroll sideways`, page_overflow <= 1, String(page_overflow));
  await card.screenshot({ path: `${out}/left-${name}.png` });
  await ctx.close();
}
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
