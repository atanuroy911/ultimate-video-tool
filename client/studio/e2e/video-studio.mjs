// O4 (docs/plans/PLAN-OPENMOTION.MD): the whole video in the HyperFrames Studio, in a real browser. The editor's Studio button bakes the video and
// opens the Studio in its own window; the scenes are clips and the parts are layers; a part retyped with the Studio's own Design panel reaches the
// export, which says it drew the Studio's edits. Then the Studio is closed and the sample put back.
//   VT_URL=http://localhost:5174 VT_PROJECT=c2-mix VT_PART=s4-defn-term node e2e/video-studio.mjs
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "c2-mix", part = process.env.VT_PART || "s4-defn-term";
const projects = process.env.VT_PROJECTS || "E:/UltimateVideoTool/scratch/c2-projects";
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };
const api = async (method, url, body) => { const r = await fetch(base + url, { method, headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined }); return r.json(); };
const label = part.split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ");          // "s4-defn-term" is shown as "S4 Defn Term"

fs.rmSync(path.join(projects, pid, "studio-9x16"), { recursive: true, force: true });
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
await page.waitForSelector(".wb .wb-viewer", { timeout: 45000 });

const popup = ctx.waitForEvent("page", { timeout: 120000 }).catch(() => null);
await page.getByRole("button", { name: "Edit in HyperFrames" }).click();
const studio = await popup;
check("the Studio button opens the whole video in the Studio's own window", !!studio);
if (!studio) { await browser.close(); process.exit(1); }
await studio.setViewportSize({ width: 1600, height: 1000 });
await studio.waitForLoadState("load").catch(() => {});
await studio.waitForTimeout(6000);
const text = await studio.locator("body").innerText();
check("its timeline shows each scene as a clip of its own composition", /Scene S2/.test(text) && /Scene S4/.test(text), (text.match(/Scene S\d+/g) || []).slice(0, 6).join(", "));
check("the editor shows the Studio is open", await page.getByRole("button", { name: "HyperFrames open" }).isVisible());

const at = Number(process.env.VT_AT || 15);                  // Layers opens the scene under the playhead: put it in the part's scene (ruler: 0 s at x 85, 41.7 px a second here)
await studio.mouse.click(85 + at * 41.7, 723);
await studio.waitForTimeout(1500);
await studio.getByText("Layers", { exact: true }).first().click();
await studio.waitForTimeout(1500);
const layer = studio.getByText(label, { exact: true }).first();
let found = await layer.count();
for (let i = 0; i < 40 && !found; i++) {                    // the panel draws only the rows on screen: scroll it down until the part shows
  await studio.mouse.move(1380, 400);
  await studio.mouse.wheel(0, 500);
  await studio.waitForTimeout(250);
  found = await layer.count();
}
check(`the part is a layer (${label})`, found > 0);
const marker = `Each minute ${Date.now() % 1000}`;
if (found) {
  await layer.click();
  await studio.waitForTimeout(1200);
  await studio.getByText("Design", { exact: true }).first().click().catch(() => {});
  await studio.waitForTimeout(800);
  const box = studio.locator("textarea").first();
  await box.fill(marker);
  await box.press("Tab");
  await studio.waitForTimeout(2500);
}
await studio.screenshot({ path: "e2e/out/o4-video-in-studio.png" }).catch(() => {});
const scenePage = path.join(projects, pid, "studio-9x16", "scenes", part.split("-")[0] + ".html");          // S4: a scene part lives in its scene's own page
const page0 = fs.existsSync(scenePage) ? fs.readFileSync(scenePage, "utf8") : "";
check("retyping in the Studio's Design panel writes the video's Studio copy", page0.includes(marker));
const st = await api("GET", `/api/projects/${pid}/studio`);
check("the server sees Studio edits that fit the current video", st.edited === true && st.current === true, JSON.stringify(st));

// export: it must draw the Studio's edits
const job = await api("POST", `/api/projects/${pid}/export`, { aspects: ["9:16"], quality: "draft" });
let j = null;
for (let i = 0; i < 240; i++) {
  await new Promise((r) => setTimeout(r, 2500));
  j = await api("GET", `/api/jobs/${job.id || job.job_id || job.jid}`);
  if (["done", "error", "failed"].includes(j.status || j.state)) break;
}
const log = await (await fetch(`${base}/api/jobs/${job.id || job.job_id || job.jid}/log`)).text();
check("the export finished", (j?.status || j?.state) === "done", JSON.stringify(j).slice(0, 200));
check("the export drew the video as edited in the Studio", /edited in the Studio/.test(log) || /edited in the Studio/.test(JSON.stringify(j)));

await page.getByRole("button", { name: "HyperFrames open" }).click();
await page.getByRole("menuitem", { name: "Close the Studio" }).click();
await page.waitForTimeout(2000);
check("closing stops the Studio", (await api("GET", `/api/projects/${pid}/studio`)).open === false);
fs.rmSync(path.join(projects, pid, "studio-9x16"), { recursive: true, force: true });       // the sample exports as before again
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
