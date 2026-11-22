// O2 (docs/plans/PLAN-OPENMOTION.MD): a shot edited in the HyperFrames Studio, in a real browser. Opens the shot editor, switches to the Studio tab,
// checks the Studio loads with the shot's layers, edits the shot through the Studio's own file (what its editor writes), saves, and checks the shot's
// code changed while our added theme block never reached it. Closing the editor stops the Studio.
//   VT_URL=http://localhost:5174 VT_PROJECT=c2-mix VT_SCENE=s1 VT_SHOT=hook node e2e/shot-studio.mjs
import { chromium } from "playwright-core";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "c2-mix", scene = process.env.VT_SCENE || "s1", shot = process.env.VT_SHOT || "hook";
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };
const shotApi = `${base}/api/projects/${pid}/shots/${shot}`;

const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
const api = async (method, url, body) => page.evaluate(async ([m, u, b]) => { const r = await fetch(u, { method: m, headers: { "content-type": "application/json" }, body: b ? JSON.stringify(b) : undefined }); return r.json(); }, [method, url, body]);

await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
await page.waitForSelector(".wb .wb-viewer", { timeout: 45000 });
const before = await api("GET", shotApi);
await page.evaluate((s) => window.dispatchEvent(new CustomEvent("vt-select-scene", { detail: s })), scene);
await page.getByRole("button", { name: "Edit shot" }).click();
await page.waitForSelector(".shot-canvas iframe", { timeout: 15000 });

const popup = page.context().waitForEvent("page", { timeout: 60000 }).catch(() => null);
await page.getByRole("tab", { name: "Studio" }).click();
const studio = await popup;
if (studio) { studio.on("requestfailed", (r) => console.log("  (studio request failed)", r.url().slice(0, 120), r.failure()?.errorText)); await studio.waitForLoadState("load").catch(() => {}); await studio.waitForTimeout(1500); }
check("the Studio tab opens the HyperFrames Studio in its own window", !!studio);
const url = studio ? studio.url() : "";
check("the Studio runs on this computer only", /^http:\/\/127\.0\.0\.1:\d+\/#project\/studio(\?.*)?$/.test(url), url);
let layers = false;
if (studio) {
  await studio.setViewportSize({ width: 1500, height: 950 });
  await studio.waitForLoadState("load").catch(() => {});
  await studio.getByText("Layers", { exact: true }).first().click({ timeout: 30000 }).catch(() => {});
  await studio.waitForTimeout(3000);
  const ids = before.ids.slice(0, 6);
  const body = (await studio.locator("body").innerText().catch(() => "")).toLowerCase();
  layers = ids.some((id) => body.includes(id.toLowerCase()));
  check("the Studio lists the shot's parts as layers", layers, ids.join(","));
  await studio.screenshot({ path: "e2e/out/o2-studio-window.png" }).catch(() => {});
}
await page.screenshot({ path: "e2e/out/o2-studio-pane.png" }).catch(() => {});

const st = await api("GET", `${shotApi}/studio`);
check("the server reports the Studio open for this shot", st.open === true, JSON.stringify(st));
const fs = await import("node:fs");
const path = await import("node:path");
const work = path.join(process.env.VT_PROJECTS || "E:/UltimateVideoTool/scratch/c2-projects", pid, "shots", shot, "studio", "index.html");
check("the Studio's copy shows the video's theme", fs.readFileSync(work, "utf8").includes("vt:studio-begin"));
// A real edit with the Studio's own controls: pick the first part from its timeline, retype it in the Design panel.
const marker = `Edited in Studio ${Date.now() % 100000}`;
const label = before.ids[0][0].toUpperCase() + before.ids[0].slice(1);
await studio.getByText(label, { exact: true }).last().click();
await studio.waitForTimeout(1200);
const box = studio.locator("textarea").first();
await box.fill(marker);
await box.press("Tab");
await studio.waitForTimeout(2500);
check("retyping in the Studio's Design panel writes the Studio's copy", fs.readFileSync(work, "utf8").includes(marker));
await studio.screenshot({ path: "e2e/out/o2-studio-edited.png" }).catch(() => {});
await page.getByRole("button", { name: "Save to video" }).click();
await page.waitForFunction(() => /Saved into the video|Nothing new/.test(document.querySelector(".shot-bar [role=status]")?.textContent || ""), null, { timeout: 15000 }).catch(() => {});
const after = await api("GET", shotApi);
check("Save to video puts the Studio's edit into the shot's code", after.html.includes(marker), marker);
check("our theme block never reaches the shot's code", !after.html.includes("vt:studio-begin") && !after.html.includes('id="vt-theme"'));

await page.getByRole("button", { name: "Close the shot editor" }).click();
await page.waitForTimeout(2500);
check("closing the editor stops the Studio", (await api("GET", `${shotApi}/studio`)).open === false);
let reachable = true;
try { await fetch(url.replace(/#.*/, ""), { signal: AbortSignal.timeout(2000) }); } catch { reachable = false; }
check("the Studio's port is closed", !reachable);

await api("PUT", shotApi, { html: before.html });                 // leave the sample as it was
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
