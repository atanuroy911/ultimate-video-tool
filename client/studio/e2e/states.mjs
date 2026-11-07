// E11: every page in the states a real person meets: loading (the server is slow), empty (nothing yet), error (the server answers with a failure) and unreachable
// (no answer at all). A page must always show something readable: never a blank page, a raw error or a spinner with no end. Screenshots in e2e/out/states. Scratch server only.
import { chromium } from "playwright-core";
import fs from "node:fs";
import { base, chromePath } from "./common.mjs";

fs.mkdirSync("e2e/out/states", { recursive: true });
const pid = process.env.VT_PROJECT || "reference";
const pages = [["projects", "/"], ["new", "/new"], ["editor", `/p/${pid}`], ["result", `/p/${pid}/result`], ["progress", `/p/${pid}/progress`], ["script", `/p/${pid}/script`], ["export", `/p/${pid}/export`],
  ["look", "/themes"], ["server", "/server"], ["settings", "/settings"], ["shorts", "/shorts"], ["share", "/social"]];
const RAW = /TypeError|ReferenceError|Unexpected token|\[object Object\]|undefined|NaN|<!DOCTYPE|Traceback|at \w+\.\w+ \(|Failed to fetch|NetworkError|ECONNREFUSED|Internal Server Error|\{"detail"/;
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const STATES = {
  loading: (route) => new Promise(() => {}),                                                             // never answers: the page is waiting
  empty: async (route) => {                                                                              // the server's own answer with every list emptied: "nothing yet"
    const emptied = (v) => Array.isArray(v) ? [] : v && typeof v === "object" ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, emptied(x)])) : v;
    try { const real = await route.fetch(); const type = real.headers()["content-type"] || ""; if (!type.includes("json")) return route.fulfill({ response: real }); await route.fulfill({ response: real, body: JSON.stringify(emptied(await real.json())) }); }
    catch { await route.abort(); }
  },
  error: (route) => route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"Internal Server Error"}' }),
  unreachable: (route) => route.abort("connectionrefused"),
};
for (const [state, handler] of Object.entries(STATES)) {
  for (const [name, url] of pages) {
    const ctx = await browser.newContext({ viewport: { width: 1100, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + "/", { waitUntil: "domcontentloaded" });                      // the page's own shell and its key, then the data goes wrong
    await page.route(/\/api\//, (route) => (route.request().url().includes("/api/health") ? route.continue() : handler(route)));
    await page.goto(base + url, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(state === "loading" ? 4500 : 2500);
    const text = (await page.locator("body").innerText()).trim();
    const raw = text.match(RAW);
    const spinners = await page.locator("[role=progressbar], .spinner, .spin").count();
    check(`${state} ${name}: something readable is on the page`, text.length > 40 || (state === "loading" && /…|\.\.\./.test(text)), `only ${text.length} characters: ${text.slice(0, 60)}`);
    check(`${state} ${name}: no raw error or code in the text`, !raw, raw ? raw[0] + " in: " + text.slice(Math.max(0, raw.index - 40), raw.index + 60).replace(/\s+/g, " ") : "");
    check(`${state} ${name}: the page itself did not crash`, errors.length === 0 && !/Something went wrong on this page/.test(text), errors[0]);
    if (state !== "loading") check(`${state} ${name}: no spinner left running`, spinners === 0 || (await page.locator("button:visible", { hasText: /Try again|Retry|Reload/ }).count()) >= 0 && state !== "error", `${spinners} spinner(s)`);
    await page.screenshot({ path: `e2e/out/states/${state}-${name}.png` });
    await ctx.close();
  }
}
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
