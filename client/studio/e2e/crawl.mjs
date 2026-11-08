// Read-only control sweep. Focused suites exercise actions that change a project or start a job.
// Use an isolated Studio: VT_URL=<scratch Studio> VT_PROJECT=reference VT_STICK=dbg node e2e/crawl.mjs
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const pid = process.env.VT_PROJECT || "reference";
const stick = process.env.VT_STICK || "";
if (!process.env.VT_URL) throw new Error("Set VT_URL to an isolated Studio before running the crawl.");
const origin = new URL(base).origin;
const socketOrigin = origin.replace(/^http/, "ws");
const SKIP = /delete|remove|revoke|record\b|connect claude desktop|open folder|show exports folder|^(?:render|generate|download|export|install|restart|stop|start|send|publish|test ai|make (?:a|my) video)\b/i;
const ACTIVE_GET = /\/(?:script-review\/render-check|themes\/[^/]+\/export)$/;
const ACTION_TIMEOUT = 1000;
const NAVIGATION_TIMEOUT = 4500;
const ROUTE_BUDGET = 14000;
const REVIEW_BUDGET = 28000;
const routes = [["projects", "/"], ["new", "/new"], ["new-script", "/new?tab=script"], ["new-link", "/new?tab=link"], ["themes", "/themes"], ["settings", "/settings"],
  ["review", `/p/${pid}`], ["export", `/p/${pid}/export`], ...(stick ? [["review-stick", `/p/${stick}`]] : [])];

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
try {
const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 }, serviceWorkers: "block", acceptDownloads: false });
ctx.setDefaultTimeout(ACTION_TIMEOUT);
let blocked = 0;
// Labels can drift. Fence the network even when an ordinary-looking control
// starts an export, requests a model, writes settings or opens a remote URL.
await ctx.route("**/*", (route) => {
  const req = route.request();
  const url = new URL(req.url());
  if (url.origin === origin && ["GET", "HEAD"].includes(req.method()) && !ACTIVE_GET.test(url.pathname)) return route.continue();
  blocked++;
  return route.abort("blockedbyclient");
});
await ctx.routeWebSocket("**/*", (socket) => {
  if (new URL(socket.url()).origin !== socketOrigin) {
    blocked++;
    return socket.close();
  }
  socket.connectToServer();
  socket.onMessage(() => { blocked++; }); // server updates arrive normally; the page cannot send commands
});
const page = await ctx.newPage();
let current = "";
const problems = [];
let clicks = 0;
const note = (kind, what) => problems.push(`${current} :: ${kind} :: ${what}`);
page.on("pageerror", (e) => note("pageerror", e.message.slice(0, 160)));
page.on("console", (m) => m.type() === "error" && !/Failed to load resource/.test(m.text()) && note("console", m.text().slice(0, 160)));
page.on("response", (r) => { if (r.status() >= 400 && !(r.status() === 422 && /\/audio\//.test(r.url())) && !/favicon|\.map$/.test(r.url())) note(`HTTP ${r.status()} ${r.request().method()}`, r.url().replace(base, "").slice(0, 120)); });
page.on("requestfailed", (r) => !/aborted|ERR_ABORTED|ERR_BLOCKED_BY_CLIENT/i.test(r.failure()?.errorText || "") && note("requestfailed", `${r.method()} ${r.url().replace(base, "").slice(0, 100)} ${r.failure()?.errorText}`));
page.on("dialog", (d) => d.dismiss().catch(() => {}));

const SEL = "button:visible, [role=tab]:visible, [role=radio]:visible, [role=menuitem]:visible, a:visible, input[type=checkbox]:visible, summary:visible";
const controls = page.locator(SEL);
const readLabel = (el) => el.evaluate(node => (node.getAttribute("aria-label") || node.innerText || node.getAttribute("title") || "").trim().replace(/\s+/g, " ").slice(0, 80)).catch(() => null);
async function open(url, deadline) {
  const remaining = deadline - Date.now();
  if (remaining <= 0) return false;
  try {
    await page.goto(new URL(url, base).href, { waitUntil: "domcontentloaded", timeout: Math.min(NAVIGATION_TIMEOUT, remaining) });
    await controls.first().waitFor({ state: "visible", timeout: Math.min(NAVIGATION_TIMEOUT, deadline - Date.now()) });
    return true;
  } catch (e) {
    note("navigation", e.message.split("\n")[0].slice(0, 160));
    return false;
  }
}
for (const [name, url] of routes) {
  current = name;
  const budget = name.startsWith("review") ? REVIEW_BUDGET : ROUTE_BUDGET;
  const deadline = Date.now() + budget;
  const within = () => {
    if (Date.now() < deadline) return true;
    note("budget", `stopped after ${budget / 1000}s; some controls could not be checked`);
    return false;
  };
  if (!await open(url, deadline)) continue;
  const n = await controls.count();
  for (let i = 0; i < Math.min(n, 140) && within(); i++) {
    if (i >= await controls.count()) break; // a menu or filter can remove controls during the sweep
    const el = controls.nth(i);
    const label = await readLabel(el);
    if (label === null || SKIP.test(label)) continue;
    const before = page.url();
    try { await el.click(); clicks++; } catch { continue; }
    await page.waitForTimeout(60); // let the click's UI update settle without waiting for unrelated polling
    // a modal or menu opened by the click: look inside it once, then close it
    const dlg = page.locator("[role=dialog]:visible");
    if (await dlg.count()) {
      const inner = dlg.first().locator("button:visible");
      const m = await inner.count();
      for (let k = 0; k < Math.min(m, 12) && within(); k++) {
        if (!(await dlg.count()) || k >= await inner.count()) break;
        const button = inner.nth(k);
        const label = await readLabel(button);
        if (label === null || SKIP.test(label) || /^(apply|save|accept|re-cut)\b/i.test(label)) continue;
        try { await button.click(); clicks++; } catch { continue; }
      }
    }
    await page.keyboard.press("Escape");
    if (page.url() !== before && !await open(url, deadline)) break;
  }
  console.log(`  ${name}: ${n} controls found`);

  // Return to the original screen before choosing values. Open details or
  // menus can replace the select list, so check the count again as we go.
  if (!within() || !await open(url, deadline)) continue;
  current = name + " (selects)";
  const sels = page.locator("select:visible");
  const selectCount = await sels.count();
  for (let i = 0; i < selectCount && within(); i++) {
    if (i >= await sels.count()) break;
    const select = sels.nth(i);
    const opts = await select.locator("option:enabled").evaluateAll(options => options.map(option => option.value));
    const original = await select.inputValue().catch(() => null);
    if (original === null) continue;
    for (const value of opts.slice(0, 8)) {
      if (!within() || i >= await sels.count()) break;
      try { await select.selectOption(value); clicks++; } catch { continue; }
    }
    await select.selectOption(original).catch(() => {});
  }
}
const uniq = [...new Set(problems)];
console.log(`\n${clicks} interactions, ${uniq.length} distinct problems`);
console.log(`${blocked} requests or WebSocket commands blocked by the read-only fence`);
uniq.forEach((p) => console.log("  PROBLEM", p));
fs.writeFileSync(path.join(out, "crawl.txt"), uniq.join("\n"));
process.exitCode = uniq.length ? 1 : 0;
} finally {
  await browser.close();
}
