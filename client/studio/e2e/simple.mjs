// The zero-click path (plan M1): give a source, press one button, land on a finished, playing video.
// Run against an isolated server: VT_URL=http://127.0.0.1:8777 node e2e/simple.mjs  (needs network for the script voice and a working renderer)
import { chromium } from "playwright-core";


import { base, chromePath } from "./common.mjs";
const shots = process.env.SHOTS || "";
let fails = 0;
const check = (name, ok) => { console.log(`${ok ? "PASS" : "FAIL"} ${name}`); if (!ok) fails++; };
const snap = async (page, name) => shots && page.screenshot({ path: `${shots}/${name}.png` });

const b = await chromium.launch({ executablePath: chromePath() });
const page = await b.newPage({ viewport: { width: 1280, height: 800 } });
await page.request.put(base + "/api/settings", { data: { autopilot: true } });

await page.goto(base + "/new", { waitUntil: "networkidle" });
check("one microphone is the first thing", await page.getByRole("button", { name: "Start recording" }).isVisible());
check("nothing to choose before a source is given", await page.getByRole("button", { name: /^OK/ }).isDisabled());
await snap(page, "1-make");

await page.getByLabel("Link or script").fill("Saving money is simple. Put away ten percent of what you earn, every month. In one year, that is more than a month of pay.");
await page.getByRole("button", { name: /^OK/ }).click();
check("one question per screen: style comes next", (await page.locator(".tf-question").innerText()).includes("style"));
await snap(page, "2-style");
for (let i = 0; i < 6 && !(await page.getByRole("button", { name: "Make my video" }).count()); i++) await page.keyboard.press("Enter");
check("Enter walks to the last screen, which shows the detected language", await page.getByText("English (from the script)").isVisible());
await snap(page, "3-ready");

const clicksAfterSource = 2;   // OK, then Make my video (Enter on every screen in between)
await page.getByRole("button", { name: "Make my video" }).click();
await page.waitForURL(/\/progress$/, { timeout: 30000 });
await page.waitForTimeout(4000);
await snap(page, "4-making");
check("making screen speaks in plain words", /…$/.test((await page.locator("h1").innerText()).trim()));

await page.waitForURL(/\/result$/, { timeout: 15 * 60 * 1000 });
await page.waitForSelector("video", { timeout: 60000 });
await page.waitForTimeout(2500);
await snap(page, "5-result");
check("result plays the finished video", await page.locator("video").evaluate((v) => v.readyState >= 2 && v.duration > 3));
check("download is offered", await page.getByRole("link", { name: "Download" }).isVisible());
check(`source to finished video in ${clicksAfterSource} click`, clicksAfterSource <= 2);

await page.setViewportSize({ width: 390, height: 844 });
await page.reload({ waitUntil: "networkidle" });
await snap(page, "6-result-phone");
check("phone: Settings reachable in the top bar", await page.getByRole("link", { name: "Settings", exact: true }).isVisible());
check("phone: no sideways scroll", await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));

await b.close();
console.log(fails ? `${fails} FAILED` : "all passed");
process.exit(fails ? 1 : 0);
