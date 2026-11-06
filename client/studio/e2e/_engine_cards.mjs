import { chromium } from "playwright-core";
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", args: ["--disable-gpu"] });
for (const scheme of ["dark", "light"]) {
  const ctx = await b.newContext({ viewport: { width: 700, height: 1100 }, colorScheme: scheme });
  await ctx.addCookies([{ name: "vt_token", value: process.env.VT_KEY, url: "http://127.0.0.1:5173" }]);
  const p = await ctx.newPage();
  await p.goto("http://127.0.0.1:5173/server", { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `e2e/out/ux-audit/server-top-${scheme}.png`, fullPage: false });
  await ctx.close();
}
await b.close();
