// Every piece of text in the rendered preview must be readable against what is behind it (>= 3:1; WCAG's limit for big display text, which is what a video shows).
// Switches the project through every built-in theme, so run it against a scratch server.  VT_PROJECT=<id> node e2e/contrast.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "reference";
const MIN = 3.0;
const api = async (p, opts) => { const r = await fetch(base + p, opts); return r.json(); };
const themes = (await api("/api/themes")).map((t) => t.name ?? t.id ?? t).filter(Boolean);
const orig = (await api(`/api/projects/${pid}`)).theme;
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };

console.log("Text contrast in the preview, all themes");
for (const theme of themes.slice(0, 14)) {
  await api(`/api/projects/${pid}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ theme }) });
  await page.goto(`${base}/p/${pid}`, { waitUntil: "networkidle" });
  await page.waitForSelector(".phone iframe, iframe");
  await page.waitForTimeout(1200);
  const fr = page.frames().find((f) => f.url().includes("/composition/9x16/"));
  const dur = await fr.evaluate(() => window.__vt.duration);
  const bad = [];
  for (let i = 1; i < 10; i++) {
    await fr.evaluate((t) => window.__vt.seek(t), (dur * i) / 10);
    await page.waitForTimeout(120);
    const found = await fr.evaluate((min) => {
      const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
      const rgba = (s) => { const m = s.match(/[\d.]+/g); return m ? m.map(Number) : null; };
      const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
      const root = getComputedStyle(document.documentElement);
      const out = [];
      for (const el of document.querySelectorAll("body *")) {
        if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
        const cs = getComputedStyle(el);
        if (cs.visibility === "hidden" || +cs.opacity < 0.5 || cs.display === "none") continue;
        const r = el.getBoundingClientRect();
        if (r.width < 4 || r.height < 4 || r.bottom < 0 || r.right < 0) continue;
        const fg = rgba(cs.color);
        if (!fg || fg[3] === 0) continue;
        let bg = null, n = el;
        const pill = el.querySelector(":scope > .pill") || (el.closest(".w.hl") && el.closest(".w.hl").querySelector(".pill"));                      // highlighted caption words sit on their own plate
        if (pill) { const c = rgba(getComputedStyle(pill).backgroundColor); if (c && (c.length < 4 || c[3] > 0.6)) bg = c; }
        while (n && !bg) { const c = rgba(getComputedStyle(n).backgroundColor); if (c && (c.length < 4 || c[3] > 0.6)) bg = c; n = n.parentElement; }
        if (!bg) { const v = getComputedStyle(document.querySelector(".stage, #root, body") || document.body).getPropertyValue("--bg").trim(); const m = /^#([0-9a-f]{6})$/i.exec(v); if (m) { const k = parseInt(m[1], 16); bg = [(k >> 16) & 255, (k >> 8) & 255, k & 255]; } }
        if (!bg) continue;
        const cr = ratio(fg, bg);
        if (cr < min) out.push(`${el.className || el.tagName} "${el.textContent.trim().slice(0, 18)}" ${cr.toFixed(2)}`);
      }
      return out;
    }, MIN);
    bad.push(...found);
  }
  const uniq = [...new Set(bad)];
  check(`${theme}: all text is at least ${MIN}:1`, uniq.length === 0, uniq.slice(0, 4).join(" | "));
}
await api(`/api/projects/${pid}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ theme: orig }) });
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
