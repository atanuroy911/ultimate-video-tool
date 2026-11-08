// Look, the "Type a script" tab and the Local AI settings, in the real Studio.
import { chromium } from "playwright-core";
import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath, repo } from "./common.mjs";

const out = process.argv[2] || path.join(repo, "studio", "e2e", "out");
const settingsOnly = process.env.VT_DESIGN_SETTINGS_ONLY === "1";
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
function watch(page) {
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("response", (r) => r.status() >= 400 && errors.push(r.status() + " " + new URL(r.url()).pathname));
}
watch(page);

let pass = 0, fail = 0;
const check = (name, cond, extra = "") => { if (cond) { pass++; console.log("  ok  ", name); } else { fail++; console.log("  FAIL", name, extra); } };
const request = (p, opts) => fetch(base + p, { signal: AbortSignal.timeout(8000), ...opts });
const api = async (p, opts) => {
  const response = await request(p, opts);
  if (!response.ok) throw new Error(`${p} returned HTTP ${response.status}`);
  return response.json();
};
const bgOf = async () => {
  const sf = page.frames().find((f) => f.url().includes("/.specimen/"));
  return sf ? sf.evaluate(() => ({ blobs: document.querySelectorAll(".bg-blob").length, pat: document.querySelectorAll(".bg-pat").length, accent: getComputedStyle(document.getElementById("root")).getPropertyValue("--accent").trim() })) : null;
};

const themeName = `test-design-${randomUUID().slice(0, 8)}`;
let themeAttempted = false;
let scriptId = "";
try {
if (!settingsOnly) {
console.log("Look");
await page.goto(base + "/", { waitUntil: "networkidle" });
check("navigation says Look", (await page.getByRole("link", { name: "Look" }).count()) === 1);
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
await page.locator(".modal input").fill(themeName);
themeAttempted = true;
await page.locator(".modal").getByRole("button", { name: "Save" }).click();
await page.waitForURL(`**/themes/${themeName}`);
const saved = (await api("/api/themes")).find((x) => x.name === themeName);
check("saved with its style and palette recorded", saved && saved.style === "sticker" && saved.palette === "mint" && saved.background.kind === "dots", JSON.stringify(saved && [saved.style, saved.palette]));

console.log("Type a script");
await page.goto(base + "/new", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
await page.screenshot({ path: out + "/d2-script.png" });
const made = await api("/api/projects/from-script", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "e2e-script", script: "One. Two.", language: "en", engine: "edge", voice: "en-US-AriaNeural", start: false }) });
scriptId = made.project?.id || "";
check("a script project is created (source=script)", made.project?.source === "script");
check("empty script is refused", (await request("/api/projects/from-script", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ script: "  ", start: false }) })).status === 400);
}
await checkLocalAiSettings();
} finally {
  await browser.close();
  const created = [scriptId && `/api/projects/${encodeURIComponent(scriptId)}`, themeAttempted && `/api/themes/${themeName}`].filter(Boolean);
  for (const resource of created) {
    try {
      const response = await request(resource, { method: "DELETE" });
      check(`removed temporary ${resource.split("/")[2] === "themes" ? "theme" : "script project"}`, response.ok || response.status === 404);
    } catch (e) {
      check("removed the temporary resource", false, e.message);
    }
  }
}

console.log(`\n${pass} passed, ${fail} failed`);
console.log("ERRORS:", errors.length ? "\n" + errors.join("\n") : "none");
process.exit(fail ? 1 : 0);

async function checkLocalAiSettings() {
  console.log("Local AI settings");
  const [llm, status, originalSettings] = await Promise.all([
    api("/api/llm/status"), api("/api/ai/status"), api("/api/settings"),
  ]);
  const origin = new URL(base).origin;
  const context = await browser.newContext({ viewport: { width: 1500, height: 950 }, serviceWorkers: "block" });
  context.setDefaultTimeout(6000);
  let provider = status.settings?.ai_provider ?? "auto";
  try {
    // Select the Local AI card in this browser only. The real Settings record
    // may use Claude or an API key and should not change for a display check.
    await context.route("**/*", async (route) => {
      const req = route.request();
      const url = new URL(req.url());
      if (url.origin !== origin) return route.abort("blockedbyclient");
      if (url.pathname === "/api/settings") {
        if (req.method() === "PUT") {
          const patch = req.postDataJSON();
          if (Object.keys(patch).length === 1 && patch.ai_provider === "auto") provider = "auto";
          else return route.abort("blockedbyclient");
        } else if (req.method() !== "GET") return route.abort("blockedbyclient");
        return route.fulfill({ json: { ...originalSettings, ai_provider: provider } });
      }
      if (req.method() !== "GET" && req.method() !== "HEAD") return route.abort("blockedbyclient");
      if (url.pathname === "/api/ai/status") return route.fulfill({ json: { ...status, settings: { ...status.settings, ai_provider: provider } } });
      if (url.pathname === "/api/llm/status") return route.fulfill({ json: llm });
      return route.continue();
    });

    const settingsPage = await context.newPage();
    watch(settingsPage);
    await settingsPage.goto(base + "/settings", { waitUntil: "domcontentloaded", timeout: 10000 });
    await settingsPage.getByRole("button", { name: "Directors & assistants", exact: true }).click();
    const details = settingsPage.getByTestId("server-details");
    await details.getByText("Language AI on the server", { exact: true }).click();
    await details.getByRole("region", { name: "Server AI connection" }).locator(".row > .chip").first().waitFor();
    const local = details.getByRole("radio", { name: "Local AI (Ollama)", exact: true });
    const card = details.locator("#provider-auto");
    await card.locator(".chip").waitFor();
    if ((await local.getAttribute("aria-checked")) !== "true") await local.click();
    const address = card.getByRole("textbox", { name: "Ollama address", exact: true });
    check("the card shows the configured server address", (await address.inputValue()) === llm.ollama_url);
    const expectedStatus = llm.llm_mode === "off" ? "Off" : !llm.reachable ? "Not running" : llm.model_ready ? "Ready" : "Model not ready";
    check(`the card reports ${expectedStatus}`, (await card.locator(".chip").innerText()).trim() === expectedStatus);
    if (llm.models?.length) {
      const model = card.getByRole("combobox");
      await model.waitFor();
      const installed = await model.locator("option").evaluateAll(options => options.map(option => option.value).filter(Boolean));
      check("the card lists the installed model choices", llm.models.every(name => installed.includes(name)));
    } else {
      check("the card says when there are no models", await card.getByText(/No models found/).isVisible());
    }
    await settingsPage.screenshot({ path: path.join(out, "d3-settings.png") });
  } finally {
    await context.close();
  }
}
