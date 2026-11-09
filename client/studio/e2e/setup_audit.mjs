// Measured checks of the setup wizard and the server's /manage page (the UI audit of 2026-11-09), so its findings cannot come back:
// readable text (WCAG contrast), 44 px targets for fingers, the keyboard stays inside the setup window, one main button per screen,
// nothing squeezed on a long step, arrow keys in radio groups and tabs, and the server's pages following the app's theme.
// Needs a running server (VT_SERVER, default the Studio's proxy) and the Studio (VT_URL). Nothing is changed on the server: every write is refused.
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const base = process.env.VT_URL || "http://localhost:5291";
const server = process.env.VT_SERVER || base;
const out = path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1")), "out", "setup-audit");
fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0;
const check = (name, ok, detail = "") => { if (ok) pass++; else { fail++; console.log(`  FAIL ${name}${detail ? " :: " + detail : ""}`); } };

// contrast, small text and small targets inside a root, computed in the page (disabled controls are exempt from contrast, as in WCAG)
const measure = (root, opts) => {
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const blend = (t, u) => ({ r: t.r * t.a + u.r * (1 - t.a), g: t.g * t.a + u.g * (1 - t.a), b: t.b * t.a + u.b * (1 - t.a), a: 1 });
  const dark = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
  const bgOf = (el) => {
    const stack = [];
    for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0) stack.push(c); if (c && c.a >= 1) break; }
    let bg = dark ? { r: 0, g: 0, b: 0, a: 1 } : { r: 255, g: 255, b: 255, a: 1 };
    for (const c of stack.reverse()) bg = blend(c, bg);
    return bg;
  };
  const opacityOf = (el) => { let o = 1; for (let e = el; e && e !== document.body; e = e.parentElement) o *= Number(getComputedStyle(e).opacity); return o; };
  const name = (el) => (el.getAttribute("aria-label") || el.textContent || el.getAttribute("placeholder") || el.tagName).trim().replace(/\s+/g, " ").slice(0, 50);
  const low = [], tiny = [], small = [];
  for (const el of root.querySelectorAll("*")) {
    const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
    const st = getComputedStyle(el); if (st.visibility === "hidden") continue;
    if ([...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && !el.closest("[disabled], [aria-disabled=true]")) {
      const fg = parse(st.color), bg = bgOf(el);
      if (fg) {
        const f = blend({ ...fg, a: fg.a * opacityOf(el) }, bg), L1 = lum(f), L2 = lum(bg), ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
        const size = parseFloat(st.fontSize), need = size >= 24 || (size >= 18.66 && Number(st.fontWeight) >= 600) ? 3 : 4.5;
        if (ratio < need) low.push(`${ratio.toFixed(2)}:1 ${size}px "${name(el)}"`);
        if (size < 12) tiny.push(`${size}px "${name(el)}"`);
      }
    }
    if (opts.targets && el.matches("button, a[href], input:not([type=hidden]):not([type=radio]):not([type=checkbox]), select, summary, [role=radio], [role=tab], label.model-opt")) {
      const hit = el.matches(".ios-dots button") ? { width: r.width, height: r.height } : r;          // the dots draw 8 px inside a 44 px button
      if (hit.height < 43.5) small.push(`${Math.round(hit.width)}x${Math.round(hit.height)} "${name(el)}"`);
    }
  }
  return { low: [...new Set(low)], tiny: [...new Set(tiny)], small: [...new Set(small)] };
};

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const errors = [];
async function open(w, h, scheme, url) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, reducedMotion: "reduce", hasTouch: w < 500 });
  await ctx.addInitScript((th) => { try { localStorage.setItem("vt-theme", th); } catch {} }, scheme);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/**", (r) => (["GET", "HEAD"].includes(r.request().method()) ? r.continue() : r.fulfill({ json: {} })));
  await page.goto(url, { waitUntil: "load" });
  return { ctx, page };
}

console.log("The setup wizard");
for (const [w, h, scheme] of [[1280, 900, "light"], [1280, 900, "dark"], [400, 860, "light"], [400, 860, "dark"]]) {
  const tag = `${w}-${scheme}`, phone = w < 500;
  const { ctx, page } = await open(w, h, scheme, base + "/server");
  await page.getByRole("button", { name: /^Set up/ }).first().click();
  const sheet = page.getByRole("dialog"); await sheet.waitFor();
  const first = sheet.getByRole("tab", { name: /^1\./ }); await first.click(); await page.waitForTimeout(2000);
  const titles = [];
  for (const n of [1, 2, 3]) {
    const tab = sheet.getByRole("tab", { name: new RegExp("^" + n + "\\.") });
    if (await tab.isDisabled()) { check(`${tag}: a locked step says why`, /\(.+\)/.test(await tab.getAttribute("aria-label")), await tab.getAttribute("aria-label")); continue; }
    await tab.click(); await page.waitForTimeout(1200);
    const title = await sheet.locator(".ios-title").innerText(); titles.push(title);
    const m = await sheet.evaluate(measure, { targets: phone });
    check(`${tag} step ${n} (${title}): all text readable (4.5:1, large 3:1)`, !m.low.length, m.low.join(" | "));
    check(`${tag} step ${n}: no text below 12 px`, !m.tiny.length, m.tiny.join(" | "));
    if (phone) check(`${tag} step ${n}: every control at least 44 px tall`, !m.small.length, m.small.join(" | "));
    const primaries = await sheet.locator(".btn.primary:visible").count();
    check(`${tag} step ${n}: one main (blue) button`, primaries <= 1, String(primaries));
    const icon = await sheet.locator(".ios-icon").boundingBox();
    check(`${tag} step ${n}: the step icon is not squeezed`, !icon || (Math.abs(icon.width - icon.height) < 1 && icon.height >= 55), JSON.stringify(icon));
    const tall = await sheet.locator(".ios-body .btn").evaluateAll((els) => els.filter((e) => e.offsetParent && e.getBoundingClientRect().height < 29).map((e) => e.textContent.trim().slice(0, 30)));
    check(`${tag} step ${n}: no button squeezed flat`, !tall.length, tall.join(" | "));
    await page.screenshot({ path: path.join(out, `wizard-step${n}-${tag}.png`) });
  }
  // the keyboard stays inside the window
  await first.click(); await page.waitForTimeout(800);
  await sheet.locator(".ios-body").focus();
  const left = [];
  for (let i = 0; i < 30; i++) { await page.keyboard.press("Tab"); if (!(await page.evaluate(() => !!document.activeElement?.closest("[role=dialog]")))) left.push(i); }
  for (let i = 0; i < 6; i++) { await page.keyboard.press("Shift+Tab"); if (!(await page.evaluate(() => !!document.activeElement?.closest("[role=dialog]")))) left.push("back" + i); }
  check(`${tag}: Tab and Shift+Tab never leave the setup window`, !left.length, left.join(","));
  const rings = await page.evaluate(() => { const e = document.activeElement; const s = getComputedStyle(e); return (s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== "none"; });
  check(`${tag}: the focused control shows it`, rings);
  // radio groups answer to the arrow keys, and only the chosen one is a Tab stop
  await sheet.getByRole("button", { name: /Choose myself/ }).click(); await page.waitForTimeout(500);
  const group = sheet.locator(".choice-pills").first();
  const before = await group.locator("[aria-checked=true]").innerText();
  await group.locator("[aria-checked=true]").focus(); await page.keyboard.press("ArrowRight"); await page.waitForTimeout(200);
  const after = await group.locator("[aria-checked=true]").innerText();
  const focused = await page.evaluate(() => document.activeElement?.getAttribute("aria-checked"));
  check(`${tag}: arrow keys move the choice and the focus with it`, before !== after && focused === "true", `${before} -> ${after}, focus ${focused}`);
  check(`${tag}: only the chosen option is a Tab stop`, (await group.locator("[tabindex='0']").count()) === 1);
  await ctx.close();
}

console.log("The server's AI programs page (/manage)");
for (const [w, scheme] of [[900, "light"], [900, "dark"], [420, "light"], [420, "dark"]]) {
  const tag = `${w}-${scheme}`, phone = w < 500;
  const { ctx, page } = await open(w, 900, scheme, `${server}/manage?embedded=1&theme=${scheme}`);
  await page.waitForTimeout(1800);
  check(`${tag}: the page takes the app's theme`, (await page.evaluate(() => document.documentElement.dataset.theme)) === scheme);
  for (const t of ["engines", "install", "cards"]) {
    await page.locator(`[data-tab=${t}]`).click(); await page.waitForTimeout(1200);
    const mm = await page.locator("main").evaluate(measure, { targets: phone });
    check(`${tag} ${t}: all text readable`, !mm.low.length, mm.low.join(" | "));
    check(`${tag} ${t}: no text below 12 px`, !mm.tiny.length, mm.tiny.join(" | "));
    if (phone) check(`${tag} ${t}: every control at least 44 px tall`, !mm.small.length, mm.small.join(" | "));
    await page.screenshot({ path: path.join(out, `manage-${t}-${tag}.png`), fullPage: true });
  }
  await page.locator("[data-tab=engines]").click(); await page.locator("[data-tab=engines]").focus(); await page.keyboard.press("ArrowRight");
  check(`${tag}: arrow keys move between the tabs`, (await page.evaluate(() => document.activeElement?.dataset.tab)) === "install" && (await page.locator("[data-tab=install]").getAttribute("aria-selected")) === "true");
  await page.locator("[data-tab=engines]").click(); await page.waitForTimeout(300);
  const notSet = page.locator("#engines section").filter({ hasText: "Not set up" });
  if (await notSet.count()) check(`${tag}: a program that is not set up offers Install`, (await notSet.first().getByRole("button", { name: /Install/ }).count()) === 1);
  await ctx.close();
}
check("no page errors", !errors.length, errors.join(" | ").slice(0, 400));
await browser.close();
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
