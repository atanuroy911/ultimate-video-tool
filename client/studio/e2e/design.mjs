// Design Studio, the "Type a script" tab and the Local AI settings, in the real Studio.
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("response", (r) => r.status() >= 400 && errors.push(r.status() + " " + r.url()));

let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { if (cond) { pass++; console.log("  ok  ", name); } else { fail++; console.log("  FAIL", name, extra); } };
const api = async (p, opts) => (await fetch(base + p, opts)).json();
const bgOf = async () => {
  const sf = page.frames().find((f) => f.url().includes("/.specimen/"));
  return sf ? sf.evaluate(() => ({ blobs: document.querySelectorAll(".bg-blob").length, pat: document.querySelectorAll(".bg-pat").length, accent: getComputedStyle(document.getElementById("root")).getPropertyValue("--accent").trim() })) : null;
};

console.log("Design Studio");
await page.goto(base + "/", { waitUntil: "networkidle" });
check("navigation says Design Studio", (await page.getByRole("link", { name: "Design Studio" }).count()) === 1);
await page.goto(base + "/themes/paper", { waitUntil: "networkidle" });
await page.waitForSelector(".design-studio");
await page.waitForTimeout(2500);
check("10 looks and 18 palettes are offered", (await page.locator(".ds-style").count()) === 10 && (await page.locator(".ds-palette").count()) === 18);
const before = await bgOf();
await page.locator(".ds-style", { hasText: "Neon glow" }).click();
await page.waitForTimeout(1200);
const neon = await bgOf();
check("choosing Neon glow shows a moving aurora live", neon && before.blobs === 0 && neon.blobs === 3, JSON.stringify([before, neon]));
await page.locator(".ds-palette", { hasText: "Mint" }).click();
await page.waitForTimeout(900);
const mint = await bgOf();
check("choosing a palette recolours it", mint && mint.accent === "#12a36b", JSON.stringify(mint));
const pick = () => page.evaluate(() => (document.querySelector(".ds-style.on")?.textContent || "") + "|" + (document.querySelector(".ds-palette.on")?.textContent || ""));
const beforeSurprise = await pick();
for (let i = 0; i < 3 && (await pick()) === beforeSurprise; i++) {   // a random pick may rarely repeat the same pair
  await page.getByRole("button", { name: /Surprise me/ }).click();
  await page.waitForTimeout(900);
}
check("Surprise me changes the look", (await pick()) !== beforeSurprise);
await page.getByRole("button", { name: /Undo/ }).click();
await page.waitForTimeout(700);
check("Undo returns to the previous look", (await bgOf()).accent === "#12a36b");
await page.locator(".ds-style", { hasText: "Sticker pop" }).click();
await page.waitForTimeout(1000);
check("a dotted pattern background renders", (await bgOf()).pat >= 1);
await page.screenshot({ path: out + "/d1-design-studio.png" });
await page.getByRole("button", { name: /Save as new/ }).click();
await page.locator(".modal input").fill("test-design");
await page.locator(".modal").getByRole("button", { name: "Save" }).click();
await page.waitForTimeout(1500);
const saved = (await api("/api/themes")).find((x) => x.name === "test-design");
check("saved with its style and palette recorded", saved && saved.style === "sticker" && saved.palette === "mint" && saved.background.kind === "dots", JSON.stringify(saved && [saved.style, saved.palette]));
await fetch(base + "/api/themes/test-design", { method: "DELETE" });

console.log("Type a script");
await page.goto(base + "/new", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
await page.screenshot({ path: out + "/d2-script.png" });
const made = await api("/api/projects/from-script", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "e2e-script", script: "One. Two.", language: "en", engine: "edge", voice: "en-US-AriaNeural", start: false }) });
check("a script project is created (source=script)", made.project?.source === "script");
if (made.project) await fetch(`${base}/api/projects/${made.project.id}`, { method: "DELETE" });
check("empty script is refused", (await fetch(base + "/api/projects/from-script", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ script: "  " }) })).status === 400);

console.log("Local AI settings");
await page.goto(base + "/settings", { waitUntil: "networkidle" });
await page.waitForSelector("[aria-label='Local AI']");
const st = await api("/api/llm/status");
check("the card shows the configured server and a model", (await page.locator("[aria-label='Local AI'] input[type=text]").inputValue()) === st.ollama_url);
if (st.reachable) check("it reports Ready when the server has a model", (await page.locator("[aria-label='Local AI'] .chip", { hasText: "Ready" }).count()) === 1);
await page.screenshot({ path: out + "/d3-settings.png" });

console.log(`\n${pass} passed, ${fail} failed`);
console.log("ERRORS:", errors.length ? "\n" + errors.join("\n") : "none");
await browser.close();
process.exit(fail ? 1 : 0);
