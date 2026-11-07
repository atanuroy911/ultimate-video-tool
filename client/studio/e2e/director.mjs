// Talking to the director from the Result screen (plan M3). Needs a working AI (Ollama, Claude login or key) and a rendered project:
// VT_URL=http://127.0.0.1:8777 VT_PROJECT=<id> node e2e/director.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT;
const shots = process.env.SHOTS || "";
let fails = 0;
const check = (name, ok, extra = "") => { console.log(`${ok ? "PASS" : "FAIL"} ${name} ${ok ? "" : extra}`); if (!ok) fails++; };

const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await b.newPage({ viewport: { width: 1280, height: 900 } });
await page.goto(`${base}/p/${pid}/result`, { waitUntil: "networkidle" });
await page.waitForSelector("video");
const before = await page.locator("video").getAttribute("src");
check("the director card is on the Result screen", await page.getByLabel("Talk to the director").isVisible());
await page.getByLabel("Talk to the director").locator(':scope > summary').click();
await page.getByLabel("Note for the director").fill("Less talking: the saver should drop a coin and chase it");
await page.getByRole("button", { name: "Send" }).click();
await page.waitForFunction(() => document.querySelector("[aria-label='Talk to the director']")?.textContent?.includes("🎬"), null, { timeout: 10 * 60 * 1000 });
const card = await page.getByLabel("Talk to the director").innerText();
check("the director answers in plain words", /Scene|Changed|Nothing needed/.test(card), card);
await page.waitForFunction((src) => { const v = document.querySelector("video"); return v && v.getAttribute("src") !== src; }, before, { timeout: 10 * 60 * 1000 }).catch(() => {});
check("the video was rendered again", (await page.locator("video").getAttribute("src")) !== before);
shots && (await page.screenshot({ path: `${shots}/director-result.png` }));
await b.close();
console.log(fails ? `${fails} FAILED` : "all passed");
process.exit(fails ? 1 : 0);
