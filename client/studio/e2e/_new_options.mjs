import { chromium } from "playwright-core";
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", args: ["--disable-gpu"] });
const ctx = await b.newContext({ viewport: { width: 1100, height: 900 }, colorScheme: process.env.SCHEME || "dark" });
await ctx.addCookies([{ name: "vt_token", value: process.env.VT_KEY, url: "http://127.0.0.1:5173" }]);
const p = await ctx.newPage();
p.setDefaultTimeout(6000);
const step = async (n, f) => { try { await f(); console.log("ok", n); } catch (e) { console.log("FAIL", n, String(e).split("\n")[0]); } };
await step("goto", () => p.goto("http://127.0.0.1:5173/new", { waitUntil: "domcontentloaded", timeout: 20000 }));
await p.waitForTimeout(4000);
await step("fill", () => p.locator("textarea").first().fill("Why do some habits stick while others fade? Here are three simple rules that work."));
const nextBtn = () => p.getByRole("button", { name: /Continue|^OK|Next/ }).first();
await step("next1", async () => { await nextBtn().click(); await p.waitForTimeout(900); });
await step("next2", async () => { await nextBtn().click(); await p.waitForTimeout(1200); });
await p.screenshot({ path: "e2e/out/ux-audit/new-ready.png", fullPage: true });
for (const [name, file] of [["Captions", "captions"], ["Music", "music"], ["Sound effects", "sfx"], ["Pace", "pace"], ["AI director", "director"], ["Look", "look"], ["Visual style", "style"], ["Clean up", "cleanup"], ["Your own pictures", "pictures"], ["Director.s script", "script"]]) {
  await step("tile " + name, async () => { await p.locator(".opt-tile", { hasText: name }).first().click(); await p.waitForTimeout(600); });
  await p.screenshot({ path: `e2e/out/ux-audit/new-opt-${file}${process.env.SCHEME ? "-" + process.env.SCHEME : ""}.png`, fullPage: true });
  await p.getByRole("button", { name: /Back to your choices/ }).click().catch(() => {});
  await p.waitForTimeout(300);
}
await b.close();
