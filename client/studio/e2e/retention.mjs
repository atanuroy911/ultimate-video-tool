// The Export page's Quality check: after a render it shows a score, a verdict and the moments to look at; a moment's button jumps the video there.
// Renders a draft export of the project (scratch server only).  VT_PROJECT=<id> node e2e/retention.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "reference";
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1400, height: 1000 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { cond ? (pass++, console.log("  ok  ", name)) : (fail++, console.log("  FAIL", name, extra)); };
const api = async (p, o) => { const r = await fetch(base + p, o); return r.json(); };

console.log("Quality check");
const j = await api(`/api/projects/${pid}/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ aspects: ["16:9"], quality: "draft", music: "none", gpu: true, captions: true, sfx_level: "off" }) });
for (let i = 0; i < 200; i++) { const s = await api(`/api/jobs/${j.id}`); if (s.status !== "running" && s.status !== "queued") { check("the export finished", s.status === "done", s.error); break; } await new Promise((r) => setTimeout(r, 1500)); }
const files = await api(`/api/projects/${pid}/exports`);
check("the export came with a retention summary (computed after the render)", !!files[0]?.retention && typeof files[0].retention.score === "number", JSON.stringify(files[0]?.retention)?.slice(0, 100));
await page.goto(`${base}/p/${pid}/export`, { waitUntil: "networkidle" });
const card = page.getByRole("region", { name: "Quality check" });
check("the Export page shows the Quality check", await card.isVisible());
check("with a score out of 100", /Score \d+\/100/.test(await card.innerText()));
check("a progress bar for it", (await card.getByRole("progressbar").count()) === 1);
const moments = card.getByRole("list", { name: "Moments to look at" }).getByRole("button");
const n = await moments.count();
check("and the moments to look at, each with a time", n > 0 && /\d+\.\d s/.test(await moments.first().innerText()), String(n));
if (n) {
  await moments.first().click();
  await page.waitForTimeout(600);
  const t = await page.locator("video.video-out").evaluate((v) => v.currentTime);
  const want = files[0].retention.worst[0].t0;
  check("clicking a moment jumps the video to it", Math.abs(t - want) < 1.5, `${t} vs ${want}`);
}
await card.getByRole("button", { name: /Check again/ }).click();
await page.waitForTimeout(3500);
check("Check again works and the card stays", await card.isVisible() && /Score \d+\/100/.test(await card.innerText()));
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
