// How smooth is the editor's timeline? Records every animation frame and every long main-thread task while it scrubs the playhead,
// zooms in and out, scrolls the timeline and plays the video. Read-only (nothing is saved).
//   VT_URL=http://127.0.0.1:8771 VT_PROJECT=<id> node e2e/perf_timeline.mjs [--cpu-slowdown 4]
// Targets (60 Hz screen): median frame <= 17 ms, 95th percentile <= 25 ms, janky frames (> 33 ms) under 5 %, no long task over 100 ms.
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT;
const slow = Number((process.argv.find((a) => a.startsWith("--cpu-slowdown=")) || "").split("=")[1] || 1);
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 } });
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await cdp.send("Performance.enable");
if (slow > 1) await cdp.send("Emulation.setCPUThrottlingRate", { rate: slow });   // an older laptop
const metrics = async () => Object.fromEntries((await cdp.send("Performance.getMetrics")).metrics.map((m) => [m.name, m.value]));
let mark = null;
await page.goto(`${base}/p/${pid}/pro`, { waitUntil: "networkidle" });
await page.waitForSelector(".tl-clip", { timeout: 30000 });
await page.waitForTimeout(800);

await page.evaluate(() => {
  window.__perf = { frames: [], long: [] };
  let last = performance.now();
  const tick = (t) => { window.__perf.frames.push(t - last); last = t; window.__perf.raf = requestAnimationFrame(tick); };
  window.__perf.raf = requestAnimationFrame(tick);
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__perf.long.push(e.duration); }).observe({ type: "longtask", buffered: false });
});
const take = async () => {
  const p = await page.evaluate(() => { const p = { ...window.__perf }; window.__perf.frames = []; window.__perf.long = []; return p; });
  const m = await metrics();
  if (mark) p.cost = { scriptMs: Math.round((m.ScriptDuration - mark.ScriptDuration) * 1000), styleMs: Math.round((m.RecalcStyleDuration - mark.RecalcStyleDuration) * 1000),
                       layoutMs: Math.round((m.LayoutDuration - mark.LayoutDuration) * 1000), layouts: m.LayoutCount - mark.LayoutCount, styles: m.RecalcStyleCount - mark.RecalcStyleCount };
  mark = m;
  return p;
};
const stats = (p) => {
  const f = p.frames.slice(1).sort((a, b) => a - b);
  const q = (x) => f[Math.min(f.length - 1, Math.floor(x * f.length))] || 0;
  return { frames: f.length, p50: +q(0.5).toFixed(1), p95: +q(0.95).toFixed(1), max: +(f[f.length - 1] || 0).toFixed(1),
           jank: +(100 * f.filter((x) => x > 33.4).length / Math.max(1, f.length)).toFixed(1), longTasks: p.long.length, longest: +Math.max(0, ...p.long).toFixed(0), ...(p.cost || {}) };
};
const results = {};
const area = await page.locator(".tl-clip").first().boundingBox();
const lane = { x: area.x, y: area.y + area.height / 2 };

// 1. scrub the playhead across the timeline (the ruler above the clips)
await take();
const ruler = page.locator('[aria-label="Timeline ruler"], .tl-ruler').first();
const rb = (await ruler.count()) ? await ruler.boundingBox() : { x: lane.x, y: lane.y - 30, width: 1100, height: 20 };
await page.mouse.move(rb.x + 5, rb.y + rb.height / 2);
await page.mouse.down();
for (let i = 0; i <= 90; i++) { await page.mouse.move(rb.x + 5 + (rb.width - 10) * (i / 90), rb.y + rb.height / 2); await page.waitForTimeout(16); }
await page.mouse.up();
results.scrub = stats(await take());

// 2. zoom in and out
for (let r = 0; r < 3; r++) {
  for (let i = 0; i < 4; i++) { await page.getByRole("button", { name: "Zoom in" }).click(); await page.waitForTimeout(60); }
  for (let i = 0; i < 4; i++) { await page.getByRole("button", { name: "Zoom out" }).click(); await page.waitForTimeout(60); }
}
results.zoom = stats(await take());

// 3. scroll the zoomed timeline sideways
for (let i = 0; i < 4; i++) await page.getByRole("button", { name: "Zoom in" }).click();
await page.mouse.move(lane.x + 300, lane.y);
for (let i = 0; i < 40; i++) { await page.mouse.wheel(60, 0); await page.waitForTimeout(16); }
for (let i = 0; i < 40; i++) { await page.mouse.wheel(-60, 0); await page.waitForTimeout(16); }
results.scroll = stats(await take());
await page.getByRole("button", { name: "Fit the whole video" }).click().catch(() => {});

// 4. play for five seconds (the playhead and the preview move together)
await page.keyboard.press("Space");
await page.waitForTimeout(5000);
await page.keyboard.press("Space");
results.play = stats(await take());

const dom = await page.evaluate(() => ({ nodes: document.getElementsByTagName("*").length, clips: document.querySelectorAll(".tl-clip").length,
  chips: document.querySelectorAll(".tl-chip").length }));
console.log(JSON.stringify({ project: pid, cpuSlowdown: slow, dom, ...results }, null, 1));
await browser.close();
