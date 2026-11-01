// The New page as it is now (one question per screen): what it accepts, what it refuses, and that three quick clicks make one video. Replaces the old `link`, `design` (the New part), `edge`
// (the New part) and `busy` suites, which drove a single-page form that no longer exists. Scratch server only (see README).
import { chromium } from "playwright-core";
import { base, chromePath, walkToReady } from "./common.mjs";

const browser = await chromium.launch({ executablePath: chromePath() });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const call = async (p, body, method = "POST") => { const r = await fetch(base + p, { method, headers: { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }); let j = null; try { j = await r.json(); } catch {} return { status: r.status, j }; };
const box = () => page.locator("textarea[aria-label='Link or script']");
const ok = () => page.locator(".tf-nav .btn.primary").first();

console.log("What the first screen accepts");
await page.goto(base + "/new", { waitUntil: "domcontentloaded" });
await box().waitFor();
check("the first screen has one box for a link or a script", await box().isVisible());
check("OK waits until something is typed", await ok().isDisabled());
await box().fill("   ");
check("spaces are not enough", await ok().isDisabled());
await box().fill("Hello. This is a short test about saving money.");
check("a script enables OK", await ok().isEnabled());
const make = await walkToReady(page, "Hello. This is a short test about saving money.");
check("the last screen says what it has understood: a script, with its sentences", /A script · 2 sentences/.test(await page.locator(".tf-val").first().innerText()));
check("and offers Make my video", await make.isVisible());

console.log("A link is understood as a link");
await page.goto(base + "/new", { waitUntil: "domcontentloaded" });
await box().waitFor();
const mk2 = await walkToReady(page, "https://www.youtube.com/watch?v=abc123");
check("a YouTube address is a YouTube video", /YouTube video/.test(await page.locator(".tf-val").first().innerText()));
check("and has the same last screen", await mk2.isVisible());

check("a link carries the rights note", await page.getByTestId("rights").isVisible() && /free to reuse/.test(await page.getByTestId("rights").innerText()));

console.log("The kind of video, and reading from a script");
{
  await page.goto(base + "/new", { waitUntil: "domcontentloaded" });
  await box().waitFor();
  const go = await walkToReady(page, "Hello. This is a short test about saving money.");
  await page.getByRole("button", { name: /Fine tuning/ }).click();
  const kind = page.getByTestId("usecase");
  await kind.waitFor();
  const options = await kind.locator("option").allInnerTexts();
  check("Fine tuning offers the kind of video, Auto first", options.length >= 3 && /auto/i.test(options[0]), options.join(","));
  await page.keyboard.press("Escape");
  void go;
  // reading from a script: a browser with a fake microphone; the script stays in view, large, while recording
  const mic = await chromium.launch({ executablePath: chromePath(), args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
  const p2 = await (await mic.newContext({ viewport: { width: 1280, height: 900 }, permissions: ["microphone"] })).newPage();
  await p2.goto(base + "/new", { waitUntil: "domcontentloaded" });
  await p2.locator("textarea[aria-label='Link or script']").fill("Never put your money in one place. Keep three months of bills in savings.");
  await p2.getByRole("button", { name: "Start recording" }).click();
  await p2.getByTestId("prompter").waitFor({ timeout: 8000 });
  check("while recording, the script is shown to read from", /Never put your money in one place/.test(await p2.getByTestId("prompter").innerText()));
  const size = await p2.getByTestId("prompter").evaluate((e) => parseFloat(getComputedStyle(e).fontSize));
  check("and it is large", size >= 19, String(size));
  await p2.getByRole("button", { name: "Stop recording" }).click();
  await mic.close();
}
console.log("What the server refuses");
const local = await call("/api/projects/from-link", { url: "http://127.0.0.1:8765/secret" });
check("a link to this computer is refused (400)", local.status === 400, JSON.stringify(local));
check("a link that is not a web address is refused (400)", (await call("/api/projects/from-link", { url: "ftp://example.com/a.mp3" })).status === 400);
check("an empty script is refused (400)", (await call("/api/projects/from-script", { script: "", title: "x" })).status === 400);
check("a script over the limit is refused (400)", (await call("/api/projects/from-script", { script: "word ".repeat(20000), title: "x" })).status === 400);
check("an unknown project is a 404", (await call("/api/projects/does-not-exist", undefined, "GET")).status === 404);
const bad = await call("/api/projects/..%2F..%2Fetc", undefined, "GET");
check("a path-like project id is refused", bad.status === 400 || bad.status === 404);
const ids = (await call("/api/projects", undefined, "GET")).j.map((p) => p.id);
check("the demo project is there to export", ids.includes("reference"));
const noShape = await call("/api/projects/reference/export", { aspects: ["4:3"], quality: "looks" });
check("an unknown shape in export is refused (400 or 409 when there is no plan)", [400, 409].includes(noShape.status), String(noShape.status));
const noQuality = await call("/api/projects/reference/export", { aspects: ["9:16"], quality: "ultra" });
check("an unknown quality in export is refused", [400, 409].includes(noQuality.status), String(noQuality.status));

console.log("Three quick clicks make one video");
const before = (await call("/api/projects", undefined, "GET")).j.length;
await page.goto(base + "/new", { waitUntil: "domcontentloaded" });
await box().waitFor();
const go = await walkToReady(page, "Hello. This is a very short test about saving money.");
await go.evaluate((b) => { b.click(); b.click(); b.click(); });                     // three clicks in the same instant
await page.waitForURL(/\/p\/[^/]+\/progress/, { timeout: 60000 }).catch(() => {});
await page.waitForTimeout(1500);
const after = (await call("/api/projects", undefined, "GET")).j;
check("exactly one project was made", after.length === before + 1, `${before} -> ${after.length}`);
for (const p of after.filter((p) => p.id !== "reference" && !ids.includes(p.id))) await fetch(`${base}/api/projects/${p.id}`, { method: "DELETE" });

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
