// Screenshots of the client UI against a running processing server, to judge it as a whole: desktop and phone width, every Settings section, the Server page.
//   VT_URL=http://127.0.0.1:5173 VT_KEY=<paired key> VT_CHROME=<chrome.exe> node e2e/settings_audit.mjs [outDir]
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://127.0.0.1:5173";
const out = process.argv[2] || path.join("e2e", "out", "ux-audit");
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath(), headless: true, args: ["--disable-gpu"] });
const errors = [];
for (const [tag, viewport, scheme] of [["desktop", { width: 1440, height: 900 }, "light"], ["phone", { width: 400, height: 760 }, "light"], ["dark", { width: 1440, height: 900 }, "dark"]]) {
  const ctx = await browser.newContext({ viewport, colorScheme: scheme });
  if (process.env.VT_KEY) await ctx.addCookies([{ name: "vt_token", value: process.env.VT_KEY, url: base }]);
  const page = await ctx.newPage();
  page.on("console", (m) => { if (m.type() === "error" && !/404/.test(m.text())) errors.push(`${tag}: ${m.text().slice(0, 140)}`); });
  page.on("pageerror", (e) => errors.push(`${tag}: pageerror ${String(e).slice(0, 140)}`));
  const shot = async (name, full = true) => { await page.waitForTimeout(1500); await page.screenshot({ path: path.join(out, `${tag}-${name}.png`), fullPage: full }); };
  const pages = tag === "desktop" ? [["home", "/"], ["server", "/server"], ["settings", "/settings"], ["settings-directors", "/settings?s=directors"], ["settings-voice", "/settings?s=voice"], ["settings-help", "/settings?s=help"]]
    : [["server", "/server"], ["settings", "/settings"]];
  for (const [name, url] of pages) { await page.goto(base + url, { waitUntil: "networkidle" }); await shot(name); }
  // keyboard: Tab through the sidebar, report what receives focus
  if (tag === "desktop") {
    await page.goto(base + "/", { waitUntil: "networkidle" });
    const order = [];
    for (let i = 0; i < 14; i++) { await page.keyboard.press("Tab"); order.push(await page.evaluate(() => { const e = document.activeElement; return (e?.getAttribute("aria-label") || e?.textContent || e?.tagName || "").trim().slice(0, 28); })); }
    console.log("tab order:", JSON.stringify(order));
    const focusRing = await page.evaluate(() => { const e = document.activeElement; const s = e ? getComputedStyle(e) : null; return s ? { outline: s.outlineStyle + " " + s.outlineWidth, shadow: s.boxShadow.slice(0, 60) } : null; });
    console.log("focus ring on", "the last focused control:", JSON.stringify(focusRing));
    // 44 px targets in the sidebar and tab bar
    const small = await page.evaluate(() => [...document.querySelectorAll("nav a, nav button, .pill, aside button")].map((e) => { const r = e.getBoundingClientRect(); return { t: (e.textContent || "").trim().slice(0, 22), w: Math.round(r.width), h: Math.round(r.height) }; }).filter((x) => x.h && x.h < 32));
    console.log("controls shorter than 32 px:", JSON.stringify(small.slice(0, 8)));
  }
  await ctx.close();
}
console.log("console errors:", errors.length, errors.slice(0, 6));
await browser.close();
