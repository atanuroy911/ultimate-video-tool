// Generated motion clips in the Studio: the Settings card shows the live server and engines; the media bin offers "Generate motion clip" for a project's pictures.
// Read-only (it never presses Make the clip). Usage: VT_URL=... VT_PROJECT=<id> node e2e/comfy.mjs <out dir>
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const out = process.argv[2] || ".";
const pid = process.env.VT_PROJECT || "reference";
let fails = 0;
const check = (name, ok, extra = "") => { console.log(`${ok ? "PASS" : "FAIL"} ${name} ${ok ? "" : extra}`); if (!ok) fails++; };
const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await b.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));

await page.goto(base + "/settings", { waitUntil: "networkidle" });
const card = page.getByLabel("ComfyUI", { exact: true });
await card.waitFor();
await page.waitForFunction(() => document.body.innerText.includes("Connected"), null, { timeout: 30000 });
check("Settings shows the server connected", await card.getByText(/Connected/).isVisible());
check("Settings names the V100 and its queue", /V100/.test(await card.innerText()) && /running/.test(await card.innerText()));
check("both engines are listed and installed", (await card.getByText("Not installed").count()) === 0 && /Wan 2\.2/.test(await card.innerText()) && /LTX-2\.3/.test(await card.innerText()));
await card.scrollIntoViewIfNeeded();
await page.screenshot({ path: `${out}/comfy-settings.png` });

await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
await page.getByRole("menuitem", { name: /Media bin/ }).click().catch(async () => { await page.getByText("File", { exact: true }).click(); await page.getByRole("menuitem", { name: /Media bin/ }).click(); });
const section = page.getByLabel("Generate motion clip");
await section.waitFor({ timeout: 20000 });
check("the media bin offers Generate motion clip", await section.isVisible());
check("the Make the clip button waits for a picture and words", await section.getByRole("button", { name: /Make the clip/ }).isDisabled().catch(() => true));
await section.getByLabel("What should happen").fill("The astronaut leans on the car, slow push-in");
// the framing window: click where the subject is (far left of this picture) and the request must carry that point
const frame = section.getByLabel("Click where the subject is");
if (await frame.count()) {
  const box = await frame.boundingBox();
  await frame.click({ position: { x: box.width * 0.12, y: box.height * 0.55 } });
  await section.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${out}/comfy-mediabin.png` });
  let sent = null;
  await page.route("**/comfy/generate", async (route) => { sent = JSON.parse(route.request().postData()); await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "fake", kind: "comfy", project: pid, label: "x", status: "queued", stage: "", frac: 0, msg: "", result: null, error: "" }) }); });
  await section.getByRole("button", { name: /Make the clip/ }).click();
  await page.waitForTimeout(400);
  check("the request carries the subject point the person clicked", !!sent && Math.abs(sent.focus_x - 0.12) < 0.03 && Math.abs(sent.focus_y - 0.55) < 0.03, JSON.stringify(sent));
  check("and the picture, words, engine, shape and length", !!sent && sent.prompt.includes("astronaut") && sent.workflow && sent.aspect === "9:16" && sent.seconds === 3, JSON.stringify(sent));
} else {
  console.log("SKIP framing checks: this project has no picture in its media bin");
}
check("no page errors", errors.length === 0, errors.join(" | "));
await b.close();
console.log(fails ? `${fails} FAILED` : "all passed");
process.exit(fails ? 1 : 0);
