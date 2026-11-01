// The New flow, one question per screen: walk it with a script (keyboard only) and with a talking-head video (the mode
// screen must appear and say a person is talking), and save a screenshot of every screen. Usage: VT_URL=... node e2e/flow.mjs <out dir> [video]
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://127.0.0.1:8777";
const [, , outDir, videoPath] = process.argv;
const browser = await chromium.launch({ executablePath: chromePath() });
const errors = [];
const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
page.on("pageerror", (e) => errors.push(e.message));
const shot = (name) => page.screenshot({ path: `${outDir}/${name}.png` });
const question = () => page.locator(".tf-question").innerText();

await page.goto(base + "/");
await page.waitForSelector(".dash2-new");
await page.waitForFunction(() => !document.body.innerText.includes("Loading…"));
await shot("00-dashboard");
await page.click(".dash2-new");
await page.waitForSelector(".tf-question");
await shot("01-source");

// a script, keyboard only
await page.fill("textarea[aria-label='Link or script']", "Once upon a time a lion slept under a tree. A little mouse ran over his nose. The lion woke up angry.");
const seen = [await question()];
await page.click(".tf-nav .btn.primary");
for (let i = 0; i < 8; i++) {
  await page.waitForTimeout(250);
  const q = await question();
  if (seen.includes(q)) break;
  seen.push(q);
  await shot(`02-script-${i}`);
  if (await page.locator(".tf-nav").count() === 0) break;
  await page.keyboard.press("b");   // a letter picks the second answer where there is one
  await page.keyboard.press("Enter");
}
const ready = await page.locator("text=Make my video").count();

// a video: the mode screen
let mode = null;
if (videoPath) {
  await page.goto(base + "/new");
  await page.setInputFiles("input[aria-label='Choose a file']", videoPath);
  await page.waitForFunction(() => !document.body.innerText.includes("Looking at it"), null, { timeout: 60000 });
  await shot("03-video-source");
  await page.click(".tf-nav .btn.primary");
  await page.waitForTimeout(300);
  mode = await question();
  await shot("04-video-mode");
}

// in Bangla: the questions follow the interface language
await page.goto(base + "/new");
await page.getByRole("button", { name: "বাং" }).first().click().catch(() => {});
await page.evaluate(() => localStorage.setItem("vt-lang", "bn"));
await page.reload();
await page.waitForSelector(".tf-question");
const bangla = await question();
await shot("06-bangla");
await page.evaluate(() => localStorage.setItem("vt-lang", "en"));

// phone width
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(base + "/");
await page.waitForSelector(".dash2-new");
await page.waitForFunction(() => !document.body.innerText.includes("Loading…"));
await shot("05-dashboard-phone");
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);

console.log(JSON.stringify({ questions: seen, ready: ready > 0, mode, bangla, overflow, errors }));
await browser.close();
process.exit(errors.length || !ready || overflow || !/[ঀ-৿]/.test(bangla) ? 1 : 0);
