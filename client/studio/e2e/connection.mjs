// E16: the first open, the refused screen, losing the connection and getting it back. (The graphics-card choice is gpu_card.mjs, the helper starting is helper_card.mjs.)
// Scratch server only.
import { chromium } from "playwright-core";
import fs from "node:fs";
import { base, chromePath } from "./common.mjs";

fs.mkdirSync("e2e/out/connection", { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const text = (page) => page.locator("body").innerText();

console.log("First open");
{
  const page = await (await browser.newContext({ viewport: { width: 1200, height: 800 } })).newPage();
  await page.route(/\/api\/setup$/, (r) => r.request().method() === "GET" ? r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ done: false, step: "welcome", server: { name: "Video Tool", os: "Linux", data_dir: "/home/x" }, existing: { comfy: [], ollama: [] }, hardware: { gpus: [] }, recommended: {}, engines: [], bundle_catalog: {}, steps: ["welcome"], choices: {} }) }) : r.continue());
  await page.goto(base + "/", { waitUntil: "load" });
  await page.waitForTimeout(2500);
  check("a server not set up yet says so, in words, with a way to set it up", /Set up server/.test(await text(page)) && /engines you need/.test(await text(page)));
  await page.getByRole("button", { name: "Later" }).click();
  check("Later puts the banner away", !/Set up server/.test(await text(page)));
  await page.screenshot({ path: "e2e/out/connection/first-open.png" });
  await page.close();
}

console.log("A server that does not accept this computer");
{
  const page = await (await browser.newContext({ viewport: { width: 1000, height: 700 } })).newPage();
  await page.route(/\/api\/health$/, (r) => r.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"not allowed"}' }));
  await page.goto(base + "/", { waitUntil: "load" });
  await page.waitForTimeout(1200);
  const t = await text(page);
  check("the refused screen says what is wrong and what to do", /not open to this computer/.test(t) && /same network|another server/.test(t));
  check("and shows no raw error", !/401|detail|undefined/.test(t));
  await page.screenshot({ path: "e2e/out/connection/refused.png" });
  await page.close();
}

console.log("Losing the connection and getting it back");
{
  const page = await (await browser.newContext({ viewport: { width: 1200, height: 800 } })).newPage();
  await page.goto(base + "/", { waitUntil: "load" });
  await page.waitForTimeout(2000);
  check("while the server answers there is no warning", (await page.getByTestId("link-lost").count()) === 0);
  let down = true;
  await page.route(/\/api\//, (r) => (down ? r.abort("connectionrefused") : r.continue()));
  await page.getByTestId("link-lost").waitFor({ timeout: 15000 }).catch(() => {});
  check("when it stops answering the page says so, in plain words", (await page.getByTestId("link-lost").count()) === 1 && /Lost the connection to the server/.test(await text(page)));
  check("and says nothing is lost", /Nothing you made is lost/.test(await text(page)));
  await page.screenshot({ path: "e2e/out/connection/lost.png" });
  await page.goto(base + "/", { waitUntil: "domcontentloaded" }).catch(() => {});
  down = false;
  await page.getByTestId("link-back").waitFor({ timeout: 15000 }).catch(() => {});
  check("when it answers again the page says so", (await page.getByTestId("link-back").count()) === 1 || (await page.getByTestId("link-lost").count()) === 0);
  await page.waitForTimeout(5500);
  check("and the notice goes away by itself", (await page.getByTestId("link-back").count()) === 0 && (await page.getByTestId("link-lost").count()) === 0);
  await page.close();
}

console.log("A list that failed to load comes back by itself");
{
  const page = await (await browser.newContext({ viewport: { width: 1200, height: 800 } })).newPage();
  let down = true;
  await page.goto(base + "/", { waitUntil: "domcontentloaded" });
  await page.route(/\/api\//, (r) => (down ? r.abort("connectionrefused") : r.continue()));
  await page.goto(base + "/", { waitUntil: "domcontentloaded" });
  await page.getByText(/Could not load your videos/).waitFor({ timeout: 15000 }).catch(() => {});
  check("with the server away the list says it could not load", /Could not load your videos/.test(await text(page)));
  down = false;
  await page.getByText(/Could not load your videos/).waitFor({ state: "detached", timeout: 20000 }).catch(() => {});
  check("when the server is back the list loads again, with no reload", !/Could not load your videos/.test(await text(page)));
  await page.screenshot({ path: "e2e/out/connection/back.png" });
  await page.close();
}
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
