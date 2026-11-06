// Screenshots of every Studio screen, light and dark, wide and narrow, for design review. Usage: node e2e/shots.mjs [outDir]
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out", "shots");
fs.mkdirSync(out, { recursive: true });
const pid = process.env.VT_PROJECT || "reference";
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const pages = [["projects", "/"], ["new", "/new"], ["review", `/p/${pid}`], ["export", `/p/${pid}/export`], ["themes", "/themes"], ["settings", "/settings"]];
const sizes = [["wide", 1440, 900], ["narrow", 760, 900], ["phone", 390, 800]];
const overflow = [];
for (const scheme of ["light", "dark"]) for (const [sn, w, h] of sizes) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme });
  const page = await ctx.newPage();
  for (const [name, url] of pages) {
    await page.goto(base + url, { waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(900);
    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (over > 1) overflow.push(`${name} ${scheme} ${sn}: page scrolls sideways by ${over}px`);
    await page.screenshot({ path: path.join(out, `${name}-${scheme}-${sn}.png`) });
  }
  await ctx.close();
}
await browser.close();
console.log(overflow.length ? overflow.join("\n") : "no sideways scroll anywhere");
