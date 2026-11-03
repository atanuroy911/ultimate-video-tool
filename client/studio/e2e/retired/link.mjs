// The "From a link" tab: validation, refusal of local addresses, option wiring. (Real downloads are covered by pytest tests/test_ingest_network.py.)
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath() });
const page = await (await browser.newContext({ viewport: { width: 1300, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { if (cond) { pass++; console.log("  ok  ", name); } else { fail++; console.log("  FAIL", name, extra); } };

await page.goto(base + "/new");
const box = page.getByLabel("Link or script");
const go = page.getByRole("button", { name: /Make my video|Downloading|Contacting/i });
check("the one box is shown", await box.isVisible());
check("the button waits for something to make a video from", (await go.count()) === 0);
await box.fill("not a link");
check("text that is not a link is read as a script", (await page.getByRole("status").first().innerText()).includes("A script"));
await box.fill("http://127.0.0.1:8765/api/projects");
check("a link is understood as a link", (await page.getByRole("status").first().innerText()).includes("A link"));
check("a link enables the button", await go.isEnabled());
await page.getByRole("button", { name: /More options/ }).click();
await page.getByRole("tab", { name: /Voice and speech/ }).click();
check("the rights note is in the last step", await page.getByText("free to reuse").isVisible());
await page.getByRole("button", { name: "Listen only" }).click();
check("the subtitle choice can be changed", (await page.getByRole("button", { name: "Listen only" }).getAttribute("aria-pressed")) === "true");
await page.keyboard.press("Escape");
await page.waitForTimeout(900);
await page.screenshot({ path: path.join(out, "link-tab.png") });
await go.click();
await page.waitForFunction(() => /not allowed/i.test(document.body.innerText), null, { timeout: 8000 }).catch(() => {});
check("a local address is refused with a plain message", /not allowed/i.test(await page.evaluate(() => document.body.innerText)));
check("the form is usable again afterwards", (await box.isEnabled()) && (await go.isEnabled()));

// narrow screens: no sideways scroll on this tab
await page.setViewportSize({ width: 390, height: 800 });
check("no sideways scroll on a phone", (await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)) <= 1);
await page.screenshot({ path: path.join(out, "link-tab-phone.png") });
check("no page errors", errors.length === 0, errors.join("; "));
console.log(`${pass} passed, ${fail} failed`);
await browser.close();
process.exit(fail ? 1 : 0);
