// The New page's finer choices each have one place a person can reach (they were stranded in a Fine tuning panel nothing opened):
// Purpose and Listening are tiles on the choices screen, the microphone sits beside the record button, and free sample voices are on
// the first screen. What is picked is what the server receives. The create call is intercepted: nothing is downloaded or made.
// VT_URL=http://127.0.0.1:5178 node e2e/new_moved_choices.mjs
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { base, chromePath, walkToReady } from "./common.mjs";

const OUT = "e2e/out/new-moved-choices";
mkdirSync(OUT, { recursive: true });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });

for (const [w, h, scheme] of [[1280, 900, "light"], [400, 860, "dark"]]) {
  const tag = `${w}px ${scheme}`;
  const page = await (await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, permissions: ["microphone"] })).newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let sent = null;
  await page.route("**/api/projects/from-link", (r) => { sent = r.request().postDataJSON(); r.fulfill({ status: 400, json: { detail: "test stop" } }); });

  // first screen
  await page.goto(base + "/new", { waitUntil: "networkidle" });
  const samples = page.locator("details.sample-voices > summary");
  check(`${tag}: free sample voices are offered on the first screen`, await samples.isVisible());
  await samples.click();
  await page.getByRole("button", { name: "Look for new free media" }).waitFor({ timeout: 8000 }).then(() => check(`${tag}: opening it shows the list and its refresh button`, true), () => check(`${tag}: opening it shows the list and its refresh button`, false));
  await page.screenshot({ path: `${OUT}/${w}-${scheme}-first.png`, fullPage: true });
  const mics = await page.evaluate(async () => (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "audioinput").length);
  if (mics > 1) check(`${tag}: a microphone choice is beside the record button (${mics} microphones)`, await page.getByLabel("Microphone").isVisible());
  else check(`${tag}: one microphone, so no microphone choice is shown`, !(await page.getByLabel("Microphone").count()));

  // a link: both tiles
  await walkToReady(page, "https://www.youtube.com/watch?v=abc123");
  const tile = (name) => page.locator(".opt-tile", { has: page.locator(".opt-tile-title", { hasText: new RegExp(`^${name}$`) }) });
  check(`${tag}: a Purpose tile is on the choices screen`, await tile("Purpose").isVisible());
  check(`${tag}: a Listening tile is on the choices screen`, await tile("Listening").isVisible());
  check(`${tag}: no Fine tuning leftover`, !(await page.getByText("Fine tuning").count()));

  await tile("Purpose").click();
  const purposes = page.getByRole("radiogroup", { name: "Purpose" }).getByRole("radio");
  check(`${tag}: Purpose offers the kinds of video (${await purposes.count()})`, (await purposes.count()) >= 3);
  const second = purposes.nth(1);
  const picked = (await second.locator(".vcard-title").innerText()).trim();
  await second.click();
  check(`${tag}: picking one marks it`, (await second.getAttribute("aria-checked")) === "true");
  await page.screenshot({ path: `${OUT}/${w}-${scheme}-purpose.png`, fullPage: true });
  await page.getByRole("button", { name: /Done/ }).click();
  check(`${tag}: the tile shows the choice`, (await tile("Purpose").locator(".opt-tile-value").innerText()).trim() === picked, picked);

  await tile("Listening").click();
  await page.getByRole("radiogroup", { name: "Speakers" }).getByRole("radio", { name: /One speaker/ }).click();
  await page.getByRole("radiogroup", { name: "Subtitles from the link" }).getByRole("radio", { name: /Listen only/ }).click();
  await page.getByRole("radiogroup", { name: "English words in Bangla speech" }).getByRole("radio", { name: /Bangla script/ }).click();
  const models = page.getByRole("radiogroup", { name: "Speech model" }).getByRole("radio");
  check(`${tag}: Listening offers the speech models (${await models.count()})`, (await models.count()) >= 1);
  const lastModel = models.nth((await models.count()) - 1);
  const modelKey = (await lastModel.locator(".vcard-title").innerText()).trim().replace(/Default$/, "").trim();
  await lastModel.click();
  await page.screenshot({ path: `${OUT}/${w}-${scheme}-listening.png`, fullPage: true });
  check(`${tag}: no sideways scroll on the Listening page`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await page.getByRole("button", { name: /Done/ }).click();
  check(`${tag}: the Listening tile says what was chosen`, /One speaker/.test(await tile("Listening").locator(".opt-tile-value").innerText()));
  await page.screenshot({ path: `${OUT}/${w}-${scheme}-hub.png`, fullPage: true });

  await page.getByRole("button", { name: /Make my video/ }).click();
  for (let i = 0; i < 40 && !sent; i++) await page.waitForTimeout(100);
  check(`${tag}: the server receives the purpose`, sent && sent.usecase && sent.usecase !== "auto", JSON.stringify(sent?.usecase));
  const o = sent?.options || {};
  check(`${tag}: and the listening choices`, o.speakers === "off" && o.use_subtitles === "off" && o.script_policy === "bangla" && o.asr_model === modelKey, JSON.stringify({ speakers: o.speakers, subs: o.use_subtitles, policy: o.script_policy, model: o.asr_model, want: modelKey }));

  // a typed script has nothing to listen to
  await page.goto(base + "/new", { waitUntil: "networkidle" });
  await walkToReady(page, "Hello. This is a short test about saving money.");
  check(`${tag}: a typed script has no Listening tile`, !(await tile("Listening").count()));
  check(`${tag}: but keeps Purpose`, await tile("Purpose").isVisible());
  check(`${tag}: no page errors`, errors.length === 0, errors.join("; "));
  await page.context().close();
}
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
