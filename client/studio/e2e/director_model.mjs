// Which Claude directs (plan step B8, decision 3): a labelled choice on Settings, Directors: "Sonnet: faster" and "Opus: slower, the most careful". Saved on the server, kept after a reload,
// readable on a phone, light and dark. A scratch server only (it changes the server's settings):
//   VT_DATA=<scratch dir> python -m vt.cli server --host 127.0.0.1 --port 8771 --comfy off --ollama off --voicestudio off
//   cd client/studio && VT_SERVER_URL=http://127.0.0.1:8771 npx vite --port 5177 --strictPort --host 127.0.0.1
//   VT_URL=http://127.0.0.1:5177 node e2e/director_model.mjs [out dir]
import fs from "node:fs";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://127.0.0.1:5177";
const out = process.argv[2] || "e2e/out/director_model";
fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const saved = async () => (await (await fetch(`${base}/api/settings`)).json()).director_model;
await fetch(`${base}/api/settings`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ director_model: "sonnet" }) });

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
for (const [name, viewport, scheme] of [["wide-light", { width: 1280, height: 900 }, "light"], ["phone-dark", { width: 400, height: 860 }, "dark"]]) {
  console.log(name);
  const ctx = await browser.newContext({ viewport, colorScheme: scheme });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${base}/settings?s=directors`, { waitUntil: "networkidle" });
  const pick = page.getByTestId("director-model");
  await pick.waitFor();
  check(`${name}: it is labelled in plain words`, (await page.getByText("Which Claude directs").count()) === 1);
  const options = await pick.locator("option").allInnerTexts();
  check(`${name}: the two choices say what they cost`, options.join("|") === "Sonnet: faster|Opus: slower, the most careful", options.join("|"));
  check(`${name}: Sonnet is the default`, (await pick.inputValue()) === "sonnet" && (await saved()) === "sonnet");
  await pick.selectOption("opus");
  await page.waitForTimeout(800);
  check(`${name}: choosing Opus is saved on the server`, (await saved()) === "opus", String(await saved()));
  await page.reload({ waitUntil: "networkidle" });
  check(`${name}: and still chosen after a reload`, (await page.getByTestId("director-model").inputValue()) === "opus");
  await page.getByTestId("director-model").scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${out}/${name}.png` });
  check(`${name}: the page does not scroll sideways`, (await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)) <= 1);
  await page.getByTestId("director-model").selectOption("sonnet");
  await page.waitForTimeout(800);
  check(`${name}: and back to Sonnet`, (await saved()) === "sonnet");
  check(`${name}: no page errors`, errors.length === 0, errors.join("; "));
  await ctx.close();
}
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
