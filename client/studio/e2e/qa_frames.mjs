// AI panel, Check the frames: each scene that needs a look shows the frame that was checked (GET /api/projects/{id}/qa/frame/{name}).
// The check's result is intercepted (running it renders frames); the frame is served by the intercept too. Needs `reference`.
// VT_URL=http://127.0.0.1:5178 node e2e/qa_frames.mjs
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { base, chromePath } from "./common.mjs";

const OUT = "e2e/out/qa-frames";
mkdirSync(OUT, { recursive: true });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAFoAAACgCAIAAAADw+wqAAABPElEQVR4nO3SMRGAMAAEwSRqkBiJyEoFw6Fht/r65ue178FjvQs5/rwj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpAj5Ag5Qo6QI+QIOUKOkCPkCDlCjpBjfB3FGAKoD1lxJAAAAABJRU5ErkJggg==", "base64");
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
for (const [w, h, scheme] of [[1280, 900, "light"], [400, 860, "dark"]]) {
  const tag = `${w}px ${scheme}`;
  const page = await (await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme })).newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let frameAsked = "";
  await page.route("**/api/projects/reference/qa", (r) => r.request().method() === "GET"
    ? r.fulfill({ json: { at: "2026-11-07T23:00:00", model: "", scenes: [{ id: "s1", ok: false, problems: ["text_cut_off"], fix_hint: "Shorter title", source: "pixels", frame: "s1.png" }, { id: "s2", ok: true, problems: [], fix_hint: "", source: "pixels", frame: "s2.png" }], bad: ["s1"] } })
    : r.continue());
  await page.route("**/api/projects/reference/qa/frame/**", (r) => { frameAsked = r.request().url(); r.fulfill({ body: png, contentType: "image/png" }); });
  await page.goto(`${base}/p/reference`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "AI assistant" }).click();
  const img = page.locator("img.qa-frame");
  await img.first().waitFor({ timeout: 8000 }).catch(() => {});
  check(`${tag}: the scene that needs a look shows its frame`, (await img.count()) === 1 && /qa\/frame\/s1\.png/.test(frameAsked), frameAsked);
  check(`${tag}: the picture loaded`, await img.first().evaluate((i) => i.complete && i.naturalWidth > 0).catch(() => false));
  await img.first().scrollIntoViewIfNeeded().catch(() => {});
  await page.screenshot({ path: `${OUT}/${w}-${scheme}.png` });
  check(`${tag}: no page errors`, errors.length === 0, errors.join("; "));
  await page.context().close();
}
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
