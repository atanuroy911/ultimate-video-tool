// Regression: playing across scene changes must not scroll the page or move the preview (the transcript scrolls inside itself).
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const id = process.env.VT_PROJECT || "2026-10-21-sample-audio";
const list = await (await fetch(base + "/api/projects")).json();
if (!list.some((p) => p.id === id)) { console.log(`skip: project ${id} not found (set VT_PROJECT)`); process.exit(0); }

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu", "--autoplay-policy=no-user-gesture-required"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
await page.addInitScript(() => { try { localStorage.setItem("vt-timeline", "classic"); } catch {} });          // this suite tests the Classic timeline (the New one is the default since W11.2)
let pass = 0, fail = 0;
const check = (n, c, x = "") => { c ? (pass++, console.log("  ok  ", n)) : (fail++, console.log("  FAIL", n, x)); };

await page.goto(`${base}/p/${id}`, { waitUntil: "networkidle" });
await page.waitForSelector(".scene-card");
await page.getByRole("button", { name: "Captions", exact: true }).click();
await page.waitForTimeout(1500);
const phone0 = await page.locator(".phone").boundingBox();
const wrap = page.locator(".transcript-wrap");
const metrics = () => page.evaluate(() => {
  const c = document.querySelector(".ed-canvas");
  const t = document.querySelector(".transcript-wrap");
  return { windowY: window.scrollY, pageTop: document.querySelector(".page")?.scrollTop ?? 0, centerTop: c.scrollTop, wrapTop: t.scrollTop, wrapMax: t.scrollHeight - t.clientHeight };
});
check("layout fits the window (no outer scrolling)", (await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight + 2)));
check("transcript has its own scroll area", (await metrics()).wrapMax > 200);

await page.getByRole("toolbar", { name: "Playback" }).getByRole("button", { name: /^(Play|Pause)$/ }).click();           // play
let maxShift = 0, scenesSeen = new Set();
for (let i = 0; i < 24; i++) {                   // ~12 s: crosses at least two scene boundaries
  await page.waitForTimeout(500);
  const b = await page.locator(".phone").boundingBox();
  maxShift = Math.max(maxShift, Math.abs(b.y - phone0.y));
  scenesSeen.add(await page.locator(".tl-clip.sel").getAttribute("aria-label"));
}
const m1 = await metrics();
await page.getByRole("toolbar", { name: "Playback" }).getByRole("button", { name: /^(Play|Pause)$/ }).click();           // pause
check(`playback crossed scenes (${[...scenesSeen].join(",")})`, scenesSeen.size >= 2);
check("preview never moved while scenes changed (max shift " + maxShift + "px)", maxShift < 1.5);
check("page and centre column never scrolled", m1.windowY === 0 && m1.pageTop === 0 && m1.centerTop === 0, JSON.stringify(m1));
check("transcript followed the speech inside itself", m1.wrapTop > 20, JSON.stringify(m1));

// reading elsewhere: manual scroll stops auto-follow and offers a way back
await wrap.hover();
await page.mouse.wheel(0, -4000);            // a real user scroll, moments after an automatic one
await page.waitForTimeout(900);
check("manual scroll shows the Follow playback pill", (await page.getByRole("button", { name: "Follow playback" }).count()) === 1);
await page.getByRole("toolbar", { name: "Playback" }).getByRole("button", { name: /^(Play|Pause)$/ }).click(); await page.waitForTimeout(2500);
const m2 = await metrics(); await page.getByRole("toolbar", { name: "Playback" }).getByRole("button", { name: /^(Play|Pause)$/ }).click();
check("playing again resumes following (the pill goes away)", (await page.getByRole("button", { name: "Follow playback" }).count()) === 0, JSON.stringify(m2));
await page.screenshot({ path: out + "/s1-review.png" });

console.log(`\n${pass} passed, ${fail} failed`);
await browser.close();
process.exit(fail ? 1 : 0);
