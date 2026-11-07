// The quality card on the finished-video page: the automatic checks, and the ten-question rating that is saved on the project.
// Scratch server only (see README).
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };

console.log("Quality checks");
await page.goto(`${base}/p/reference/result`, { waitUntil: "networkidle" });
await page.locator('.result-quality > summary').click();
check("the card is there", await page.getByTestId("quality").isVisible());
check("nothing is claimed before a video exists", (await page.getByTestId("quality").innerText()).includes("Not checked yet"));
await page.getByTestId("quality-rate").click();
await page.waitForSelector("[data-testid=rate-hook-yes]");
check("the ten questions are listed", (await page.locator("[role=radiogroup]").count()) === 10);
await page.getByTestId("rate-hook-yes").click();
await page.getByTestId("rate-post-no").click();
await page.getByLabel(/What is wrong: Would you post/).fill("the ending is flat");
await page.getByTestId("rate-save").click();
await page.waitForTimeout(500);
const saved = await (await fetch(`${base}/api/projects/reference/checklist`)).json();
check("the answers are saved on the project", saved.answers.hook === "yes" && saved.answers.post === "no" && saved.notes.post === "the ending is flat", JSON.stringify(saved));
await page.getByTestId("quality-rate").click();
await page.waitForSelector("[data-testid=rate-hook-yes]");
check("they come back when it is opened again", (await page.getByTestId("rate-post-no").getAttribute("aria-checked")) === "true");
await page.goto(`${base}/p/reference`, { waitUntil: "networkidle" });
await page.getByRole("button", { name: "Text" }).click();
check("the caption looks are offered", (await page.locator("[data-testid=caption-looks] button").count()) === 5);
await page.getByRole("button", { name: "One big word" }).click();
await page.waitForTimeout(1500);
const meta = await (await fetch(`${base}/api/projects/reference`)).json();
check("choosing one is saved on the project", meta.options.caption_style === "word", JSON.stringify(meta.options.caption_style));
check("and shown as chosen", (await page.getByRole("button", { name: "One big word" }).getAttribute("aria-pressed")) === "true");
await page.getByRole("button", { name: "Automatic" }).click();
await page.waitForTimeout(1000);
await page.getByRole("button", { name: "Media" }).click();
check("music and sounds are in the Media tool", await page.getByTestId("sound-panel").isVisible());
await page.getByLabel("Music loudness").fill("30").catch(() => {});
await page.getByRole("button", { name: "Some" }).click().catch(() => {});
check("no page errors", errors.length === 0, errors.join("; "));
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
