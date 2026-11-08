// "Look for new free media": the button runs the same job as `vt catalog refresh` (POST /api/catalog/refresh),
// shows its progress, reloads the list and never tells the person to type a command.
// The refresh call is intercepted (a real one downloads every file); everything else is the real server.
// VT_URL=http://127.0.0.1:5178 node e2e/catalog_refresh.mjs
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";
import { mkdirSync } from "node:fs";

const URL = process.env.VT_URL || "http://127.0.0.1:5173";
const OUT = "e2e/out/catalog-refresh";
mkdirSync(OUT, { recursive: true });
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log("  ok  ", m); } else { fail++; console.log("  FAIL", m); } };

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
for (const [w, h, scheme] of [[1280, 860, "light"], [400, 860, "dark"]]) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, colorScheme: scheme });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let polls = 0, refreshes = 0, lists = 0;
  await page.route("**/api/catalog/refresh*", (r) => { refreshes++; r.fulfill({ json: { id: "jcat", kind: "catalog", status: "running", msg: "Checking 3 of 40", frac: 0.1 } }); });
  await page.route("**/api/jobs/jcat", (r) => { polls++; r.fulfill({ json: polls < 2 ? { id: "jcat", status: "running", msg: "Checking 20 of 40" } : { id: "jcat", status: "done", msg: "", result: {} } }); });
  page.on("request", (q) => { if (/\/api\/catalog\?kind=audio/.test(q.url())) lists++; });
  await page.goto(URL + "/new", { waitUntil: "networkidle" });
  await page.locator("details.sample-voices > summary").click();   // "No recording yet? Make a video from a free sample voice"
  const btn = page.getByRole("button", { name: "Look for new free media" });
  await btn.first().scrollIntoViewIfNeeded().catch(() => {});
  ok(await btn.count() > 0, `${w}px ${scheme}: the button is on the New page`);
  ok(!(await page.getByText("vt catalog").count()), `${w}px ${scheme}: no command for the person to type`);
  await page.screenshot({ path: `${OUT}/${w}-${scheme}-before.png` });
  const listsBefore = lists;
  await btn.first().click();
  await page.getByRole("status").filter({ hasText: /Checking/ }).first().waitFor({ timeout: 5000 }).then(() => ok(true, `${w}px ${scheme}: progress shown`), () => ok(false, `${w}px ${scheme}: progress shown`));
  await page.screenshot({ path: `${OUT}/${w}-${scheme}-during.png` });
  await page.getByText("Free media updated.").waitFor({ timeout: 8000 }).then(() => ok(true, `${w}px ${scheme}: done message`), () => ok(false, `${w}px ${scheme}: done message`));
  ok(refreshes === 1, `${w}px ${scheme}: one refresh job started (${refreshes})`);
  ok(lists > listsBefore, `${w}px ${scheme}: the list reloaded`);
  ok(await btn.first().isEnabled(), `${w}px ${scheme}: button ready again`);
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `${w}px ${scheme}: no sideways scroll`);
  ok(errors.length === 0, `${w}px ${scheme}: no page errors ${errors.join("; ")}`);
  await page.screenshot({ path: `${OUT}/${w}-${scheme}-after.png` });
  await page.close();
}
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
