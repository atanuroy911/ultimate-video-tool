// Screenshots of one Studio page, light and dark, at the sizes given. Usage:
//   VT_URL=http://127.0.0.1:8771 node scripts/dev/shot.mjs <path> <outPrefix> [WxH,WxH...]
//   (Git Bash rewrites a leading "/" in arguments: put MSYS_NO_PATHCONV=1 in front.)
//   node scripts/dev/shot.mjs /p/reference docs/dev/shots/before-editor 1440x900,1280x720
// Writes <outPrefix>-<WxH>-light.png and <outPrefix>-<WxH>-dark.png. Chrome: VT_CHROME, else Chrome or Edge in their usual places.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { chromium } = createRequire(path.join(repo, "client", "studio", "package.json"))("playwright-core");
const [urlPath = "/", prefix = "shot", sizes = "1440x900"] = process.argv.slice(2);
const base = process.env.VT_URL || "http://127.0.0.1:8765";

function chrome() {
  const found = [process.env.VT_CHROME, "C:/Program Files/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean).find((p) => fs.existsSync(p));
  if (!found) throw new Error("No Chrome or Edge found. Set VT_CHROME.");
  return found;
}

fs.mkdirSync(path.dirname(prefix), { recursive: true });
const browser = await chromium.launch({ executablePath: chrome(), args: ["--disable-gpu"] });
for (const size of sizes.split(",")) {
  const [w, h] = size.split("x").map(Number);
  for (const scheme of ["light", "dark"]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme });
    const page = await ctx.newPage();
    await page.addInitScript((s) => { try { localStorage.setItem("vt-theme", s); } catch {} }, scheme);
    await page.goto(base + urlPath, { waitUntil: "load" }).catch(() => {});
    await page.waitForFunction(() => document.body && document.body.innerText.trim().length > 20, null, { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2500);                       // let the picture and fonts settle; the preview streams audio, so the network never goes quiet
    const file = `${prefix}-${size}-${scheme}.png`;
    await page.screenshot({ path: file });
    console.log("wrote", file);
    await ctx.close();
  }
}
await browser.close();
