// The Script tab: every sentence in a box, a pasted correction keeps the words' times, the whole text can be pasted with a preview, undo works.
// Mutating (then undone): scratch server only.  VT_PROJECT=<id> node e2e/script.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "reference";
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p) => (await fetch(base + p)).json();
const words = async () => (await api(`/api/projects/${pid}/transcript`)).transcript.words;

console.log("Script tab");
await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
await page.getByRole("button", { name: "Script", exact: true }).click();
const boxes = page.getByRole("listitem").locator("textarea");
const n = await boxes.count();
const beats = (await api(`/api/projects/${pid}/transcript`)).beats.beats;
check("one box per sentence", n === beats.length && n >= 2, `${n} vs ${beats.length}`);
const w0 = await words();
const t0 = w0[0].start;
const first = await boxes.nth(0).inputValue();
check("the box shows the sentence's words", first.split(" ")[0] === w0[0].text, first);

// paste a correction into sentence 1 and leave the box
await boxes.nth(0).click();
const fixed = first.split(" ");
fixed[1] = "বাড়তি";                                                   // a wrong word in the middle of the sentence
await boxes.nth(0).fill(fixed.join(" "));
await page.keyboard.press("Control+Enter");
await page.waitForTimeout(2500);
const w1 = await words();
check("the correction reached the words", w1.some((w) => w.text === "বাড়তি"));
check("and the word times are untouched", Math.abs(w1[0].start - t0) < 0.001);
await page.waitForFunction(() => document.querySelector('[aria-label="Sentence 1"]')?.value.includes("বাড়তি"), null, { timeout: 8000 }).catch(() => {});
check("the box shows the corrected sentence", (await boxes.nth(0).inputValue()).includes("বাড়তি"));

// undo
await page.getByRole("button", { name: "Undo the last text change" }).click();
await page.waitForTimeout(2500);
check("undo brings the old text back", !(await words()).some((w) => w.text === "বাড়তি"));

// whole text with a preview
await page.getByRole("button", { name: "Paste all text" }).click();
const all = (await words()).map((w) => w.text);
all[1] = "পরিবর্তিত";
await page.getByRole("textbox", { name: "The correct text" }).fill(all.join(" "));
await page.getByRole("button", { name: "Show what changes" }).click();
await page.waitForTimeout(800);
check("the preview lists the one changed word", await page.getByText(/1 word will change/).isVisible());
check("nothing is applied before Apply", !(await words()).some((w) => w.text === "পরিবর্তিত"));
await page.getByRole("button", { name: /^Apply/ }).click();
await page.waitForTimeout(2500);
check("Apply changes it", (await words()).some((w) => w.text === "পরিবর্তিত"));
await page.getByRole("button", { name: "Undo the last text change" }).click();
await page.waitForTimeout(2500);
check("and undo restores it", !(await words()).some((w) => w.text === "পরিবর্তিত"));

// the current sentence follows the playhead
await page.evaluate(() => 0);
await page.keyboard.press("Escape");
const row = page.getByRole("button", { name: /^Go to sentence 2/ });
await row.click();
await page.waitForTimeout(600);
check("clicking the time jumps the preview there", (await page.locator(".script-row.cur").count()) === 1);

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
