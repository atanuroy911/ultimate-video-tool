// Click-everything crawler: on every screen, activate every visible button, tab, link, checkbox, radio and select option, and record any
// HTTP error (4xx/5xx), failed request, page error or console error each click causes. It checks that nothing blows up; what each control
// must DO is checked by the focused suites (flows, editor, timeline, stick, dashboard, export, phase2, modes).
// Run against a scratch server:  VT_PROJECT=reference VT_STICK=dbg node e2e/crawl.mjs
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const pid = process.env.VT_PROJECT || "reference";
const stick = process.env.VT_STICK || "";
const SKIP = /delete|remove|revoke|start recording|stop recording|connect claude desktop|open folder|show exports folder|record\b/i;   // destructive, or needs a microphone / the desktop
const routes = [["projects", "/"], ["new", "/new"], ["new-script", "/new?tab=script"], ["new-link", "/new?tab=link"], ["themes", "/themes"], ["settings", "/settings"],
  ["review", `/p/${pid}`], ["export", `/p/${pid}/export`], ...(stick ? [["review-stick", `/p/${stick}`]] : [])];

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 }, permissions: ["microphone"], acceptDownloads: true });
const page = await ctx.newPage();
let current = "";
const problems = [];
let clicks = 0;
const note = (kind, what) => problems.push(`${current} :: ${kind} :: ${what}`);
page.on("pageerror", (e) => note("pageerror", e.message.slice(0, 160)));
page.on("console", (m) => m.type() === "error" && !/Failed to load resource/.test(m.text()) && note("console", m.text().slice(0, 160)));
page.on("response", (r) => { if (r.status() >= 400 && !(r.status() === 422 && /\/audio\//.test(r.url())) && !/favicon|\.map$/.test(r.url())) note(`HTTP ${r.status()} ${r.request().method()}`, r.url().replace(base, "").slice(0, 120)); });
page.on("requestfailed", (r) => !/aborted|ERR_ABORTED/.test(r.failure()?.errorText || "") && note("requestfailed", `${r.method()} ${r.url().replace(base, "").slice(0, 100)} ${r.failure()?.errorText}`));
page.on("dialog", (d) => d.dismiss().catch(() => {}));

const SEL = "button:visible, [role=tab]:visible, [role=radio]:visible, [role=menuitem]:visible, a:visible, input[type=checkbox]:visible, summary:visible";
for (const [name, url] of routes) {
  current = name;
  await page.goto(base + url, { waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(1200);
  const n = await page.locator(SEL).count();
  for (let i = 0; i < Math.min(n, 140); i++) {
    const el = page.locator(SEL).nth(i);
    let label = "";
    try { label = ((await el.getAttribute("aria-label")) || (await el.innerText({ timeout: 800 })) || (await el.getAttribute("title")) || "").trim().replace(/\s+/g, " ").slice(0, 40); } catch { continue; }
    if (SKIP.test(label)) continue;
    const before = page.url();
    try { await el.click({ timeout: 2500, trial: false }); clicks++; } catch { continue; }
    await page.waitForTimeout(220);
    // a modal or menu opened by the click: look inside it once, then close it
    const dlg = page.locator("[role=dialog]:visible");
    if (await dlg.count()) {
      const inner = dlg.first().locator("button:visible");
      const m = await inner.count();
      for (let k = 0; k < Math.min(m, 12); k++) {
        const t = ((await inner.nth(k).getAttribute("aria-label")) || (await inner.nth(k).innerText().catch(() => "")) || "").trim();
        if (SKIP.test(t) || /^(delete|apply|save|accept|render|generate|start|re-cut|send)/i.test(t)) continue;
        await inner.nth(k).click({ timeout: 1500 }).catch(() => {});
        clicks++;
        await page.waitForTimeout(120);
        if (!(await dlg.count())) break;
      }
      await page.keyboard.press("Escape");
      await page.waitForTimeout(120);
    }
    await page.keyboard.press("Escape");
    if (page.url() !== before) { await page.goto(base + url, { waitUntil: "networkidle" }).catch(() => {}); await page.waitForTimeout(600); }
  }
  console.log(`  ${name}: ${n} controls found`);
}
// selects: choose every option once
for (const [name, url] of routes) {
  current = name + " (selects)";
  await page.goto(base + url, { waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(900);
  const sels = page.locator("select:visible");
  const n = await sels.count();
  for (let i = 0; i < n; i++) {
    const opts = await sels.nth(i).locator("option").evaluateAll((os) => os.map((o) => o.value));
    const orig = await sels.nth(i).inputValue();
    for (const v of opts.slice(0, 8)) { await sels.nth(i).selectOption(v).catch(() => {}); clicks++; await page.waitForTimeout(150); }
    await sels.nth(i).selectOption(orig).catch(() => {});
  }
}
await browser.close();
const uniq = [...new Set(problems)];
console.log(`\n${clicks} interactions, ${uniq.length} distinct problems`);
uniq.forEach((p) => console.log("  PROBLEM", p));
fs.writeFileSync(path.join(out, "crawl.txt"), uniq.join("\n"));
process.exit(uniq.length ? 1 : 0);
