// Screenshots of every page, wide and phone-sized, light and dark: node e2e/_audit.mjs <out dir> [light|dark] [pages...]
import { chromium } from "playwright-core";
import fs from "node:fs";
import { chromePath } from "./common.mjs";
const base = process.env.VT_URL || "http://127.0.0.1:5174";
const [, , out = "e2e/out/audit", mode = "light", ...only] = process.argv;
const pid = process.env.VT_PROJECT || "2026-11-05-look-local";
const all = { projects: "/", new: "/new", shorts: "/shorts", share: "/social", styles: "/themes", server: "/server", settings: "/settings", editor: `/p/${pid}`, progress: `/p/${pid}/progress`, script: `/p/${pid}/script`, export: `/p/${pid}/export`, result: `/p/${pid}/result` };
fs.mkdirSync(out, { recursive: true });
const b = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
for (const [w, h, tag] of [[1440, 900, "wide"], [400, 860, "phone"]]) {
  const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: mode, extraHTTPHeaders: { Authorization: `Bearer ${fs.readFileSync("../../dist/recording-run/key.txt", "utf8").trim()}` } });
  await ctx.addInitScript((m) => { try { localStorage.setItem("vt-theme", m); } catch {} }, mode);
  const p = await ctx.newPage();
  const errors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  for (const [name, url] of Object.entries(all)) {
    if (only.length && !only.includes(name)) continue;
    await p.goto(base + url, { waitUntil: "load" }).catch(() => {});
    await p.waitForTimeout(2500);
    const over = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    await p.screenshot({ path: `${out}/${name}-${tag}-${mode}.png` });
    console.log(name, tag, mode, over > 1 ? `OVERFLOW ${over}px` : "ok", errors.splice(0).join(" | ").slice(0, 200));
  }
  await ctx.close();
}
await b.close();
