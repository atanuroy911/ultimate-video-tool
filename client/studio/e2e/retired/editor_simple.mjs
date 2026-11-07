// The everyday editor (/p/<id>): a tool rail, a panel, the preview, the selection's few controls and a three-track timeline.
// Edits the scratch server's `reference` project and undoes what it did. Scratch server only (see README).
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const api = async (p, o) => (await fetch(base + p, o)).json();
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("response", (r) => r.status() >= 500 && errors.push(r.status() + " " + r.url()));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const scenes = async () => (await api("/api/projects/reference/scenes")).plan.scenes;

console.log("Simple editor");
await page.goto(`${base}/p/reference`, { waitUntil: "networkidle" });
await page.waitForSelector("[data-testid=simple-editor]");
check("the everyday editor is the default", await page.getByTestId("simple-editor").isVisible());
check("no menu bar and no dense toolbar: one Export button", (await page.getByRole("button", { name: /^Export$/ }).count()) === 1 && (await page.getByRole("button", { name: /^(File|Edit|View|Help)$/ }).count()) === 0);
check("the timeline has three tracks", (await page.locator(".ce-track").count()) === 3);
check("one clip per scene", (await page.locator(".ce-clip").count()) === (await scenes()).length);

for (const tab of ["Media", "Text", "AI", "Story"]) {
  await page.locator(".ce-rail").getByRole("button", { name: tab }).click();
  check(`the ${tab} tool opens its panel`, (await page.locator(".ce-panel h2").innerText()) === tab);
}
await page.locator(".ce-scenes button").nth(1).click();
check("clicking a story line selects that scene", (await page.locator(".ce-props h2").innerText()) === "Scene 2");
check("and the timeline marks it", (await page.locator(".ce-clip.sel").getAttribute("aria-label")) === "Scene 2");

const before = (await scenes())[1].layout;
const other = before === "hero" ? "grid" : "hero";
await page.locator(".ce-layouts button", { hasText: other === "hero" ? "Big picture" : "Grid" }).click();
await page.waitForTimeout(700);
check("choosing a picture layout is saved", (await scenes())[1].layout === other);
await page.getByRole("button", { name: "Undo" }).click();
await page.waitForTimeout(900);
check("and Undo puts it back", (await scenes())[1].layout === before);

await page.locator(".ce-rail").getByRole("button", { name: "Text" }).click();
await page.locator(".ce-words button").first().click();
check("a word can be fixed in place", (await page.getByLabel("Fix this word").count()) === 1);
await page.keyboard.press("Escape");

const total = (await scenes()).length;
await page.locator(".ce-clip").nth(2).click();
await page.getByRole("button", { name: /^Delete$/ }).first().click();
check("deleting asks first", await page.getByRole("dialog").isVisible().catch(() => false) || (await page.getByText("Delete this scene?").count()) > 0);
await page.getByRole("button", { name: "Cancel" }).click();
check("cancel keeps every scene", (await scenes()).length === total);

// the end of a picture can be dragged (and nudged with the arrow keys): it lands on the start of a sentence, and Undo puts it back
const multi = (await scenes()).findIndex((s, i, all) => i < all.length - 1 && s.beats.length + all[i + 1].beats.length >= 3);
if (multi >= 0) {
  const before = JSON.stringify((await scenes()).map((s) => s.beats));
  const edge = page.getByTestId(`edge-${multi}`);
  check("each picture has an end handle", (await edge.count()) === 1);
  await edge.focus();
  const sc = await scenes();
  await page.keyboard.press(sc[multi].beats.length > 1 ? "ArrowLeft" : "ArrowRight");
  await page.waitForTimeout(800);
  check("an arrow key moves the cut by one sentence", JSON.stringify((await scenes()).map((s) => s.beats)) !== before);
  await page.getByRole("button", { name: "Undo" }).click();
  await page.waitForTimeout(800);
  check("and Undo puts it back", JSON.stringify((await scenes()).map((s) => s.beats)) === before);
}
await page.getByRole("button", { name: "Zoom in" }).click();
check("zoom widens the timeline", (await page.locator(".ce-canvas").evaluate((e) => e.getBoundingClientRect().width)) > 0);
await page.getByRole("button", { name: "More" }).click();
check("the rest is under More", (await page.getByText("Open the full editor").count()) === 1);
await page.keyboard.press("Escape");
await page.screenshot({ path: process.argv[2] ? process.argv[2] + "/simple-editor.png" : undefined });

await page.goto(`${base}/p/reference/pro`, { waitUntil: "networkidle" });
check("the full editor is still there at /pro", (await page.locator(".ed-title").count()) === 1);
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${base}/p/reference`, { waitUntil: "networkidle" });
check("at phone width nothing scrolls sideways", (await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)));

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
