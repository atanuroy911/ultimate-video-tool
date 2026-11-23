// G1 (docs/plans/PLAN-SCENE-TOOLS.MD): the pictures panel for one scene, in a real browser. Opened from the scene's menu; with no picture engine on
// this computer it says so in one sentence; a picture already made for the scene shows in the grid, opens large, and "Use" makes the scene show it.
//   VT_URL=http://localhost:5174 VT_PROJECT=c2-mix VT_SCENE=s4 node e2e/scene-pictures.mjs
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { base, chromePath } from "./common.mjs";

const pid = process.env.VT_PROJECT || "c2-mix", sid = process.env.VT_SCENE || "s4";
const projects = process.env.VT_PROJECTS || "E:/UltimateVideoTool/scratch/c2-projects";
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };
const browser = await chromium.launch({ executablePath: chromePath(), args: ["--disable-gpu"] });
const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
await page.goto(`${base}/p/${pid}`, { waitUntil: "load" });
await page.waitForSelector(".wb .wb-viewer", { timeout: 45000 });
const api = (m, u, body) => page.evaluate(async ([m, u, body]) => { const r = await fetch(u, { method: m, headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined }); return { status: r.status, body: await r.json().catch(() => null) }; }, [m, u, body]);
const plan0 = (await api("GET", `/api/projects/${pid}/scenes`)).body.plan;

// a picture in the media bin (as the engine would leave it), listed as made for this scene
const media = await page.evaluate(async (pid) => {
  const c = document.createElement("canvas"); c.width = 180; c.height = 320;
  const g = c.getContext("2d"); g.fillStyle = "#2d66f2"; g.fillRect(0, 0, 180, 320); g.fillStyle = "#ffb703"; g.beginPath(); g.arc(90, 160, 60, 0, 7); g.fill();
  const blob = await new Promise((r) => c.toBlob(r, "image/png"));
  const fd = new FormData(); fd.append("file", blob, "made-for-scene.png");
  const r = await fetch(`/api/projects/${pid}/media`, { method: "POST", body: fd });
  const j = await r.json(); return (Array.isArray(j) ? j[0] : j.item || j).id;
}, pid);
const genFile = path.join(projects, pid, "gen", `${sid}.json`);
fs.mkdirSync(path.dirname(genFile), { recursive: true });
fs.writeFileSync(genFile, JSON.stringify({ runs: [{ id: "e2e", prompt: "a blue card with a sun", recipe: "", model: "Test model", count: 1, made_at: Date.now() / 1000, items: [{ media, seed: 7, seconds: 9 }] }] }));

// open from the scene's menu
await page.evaluate((s) => window.dispatchEvent(new CustomEvent("vt-scene-pictures", { detail: s })), sid);
const panel = page.getByRole("dialog", { name: /Pictures for scene/ });
await panel.waitFor({ timeout: 15000 });
check("the pictures panel opens for the scene", await panel.isVisible());
await panel.locator(".scene-pics-cards [role=listitem]").first().waitFor({ timeout: 15000 }).catch(() => {});
check("its prompt starts from the scene (or the last run)", (await panel.getByLabel("What the picture shows").inputValue()).length > 5);
check("the picture made for the scene is in the grid", (await panel.getByRole("list", { name: "Pictures made for this scene" }).getByRole("listitem").count()) === 1);
await panel.locator(".scene-pics-view img").waitFor({ timeout: 10000 }).catch(() => {});
check("it shows large on the left", await panel.locator(".scene-pics-view img").isVisible());

// no picture engine here: one plain sentence
await panel.getByRole("radio", { name: "1" }).click();
await panel.getByRole("button", { name: /Generate 1/ }).click();
const alert = panel.getByRole("alert");
await alert.waitFor({ timeout: 60000 }).catch(() => {});
check("with no picture engine it says so plainly", /picture engine|ComfyUI|not reachable/i.test(await alert.textContent().catch(() => "")), (await alert.textContent().catch(() => "")).slice(0, 120));
await page.screenshot({ path: "e2e/out/g1-scene-pictures.png" });

// G2: a picture can be made to move; with no engine it says so the same way
check("each picture offers Make it move, with a clip model and length", await panel.getByRole("button", { name: /Make it move/ }).first().isVisible() && await panel.getByLabel("Clip model").isVisible() && (await panel.getByRole("radiogroup", { name: "Clip length" }).getByRole("radio").count()) === 2);
await panel.getByRole("button", { name: /Make it move/ }).first().click();
await page.waitForTimeout(500);
await alert.waitFor({ timeout: 60000 }).catch(() => {});
check("Make it move with no picture engine says so plainly", /picture engine/i.test(await alert.textContent().catch(() => "")), (await alert.textContent().catch(() => "")).slice(0, 120));

// G3: the AI writes different prompts for the scene (Claude through this PC's login, set on the scratch server for this call), each editable
const settingsFile = path.join(process.env.VT_DATA || "E:/UltimateVideoTool/scratch/c2-data", "settings.json");
const settings0 = fs.readFileSync(settingsFile, "utf8");
fs.writeFileSync(settingsFile, JSON.stringify({ ...JSON.parse(settings0), ai_provider: "claude_cli", claude_cli_model: "sonnet" }, null, 2));
try {
  await panel.getByRole("radio", { name: "4" }).click();
  await panel.getByRole("button", { name: "Write 4 prompts for me" }).click();
  const ideas = panel.getByRole("list", { name: "Written prompts" }).getByRole("listitem");
  await ideas.first().waitFor({ timeout: 180000 }).catch(() => {});
  const n = await ideas.count();
  const texts = await Promise.all(Array.from({ length: n }, (_, i) => ideas.nth(i).locator("textarea").inputValue()));
  check("Write prompts for me gives different, editable prompts", n >= 3 && new Set(texts).size === n && texts.every((t) => t.length > 20), `${n}: ${texts[0]?.slice(0, 70)}`);
  await ideas.first().locator("textarea").fill("a calm wrist with a smartwatch, close-up");
  await ideas.first().getByRole("button", { name: "Use" }).click();
  check("an idea, edited, goes into the prompt", (await panel.getByLabel("What the picture shows").inputValue()) === "a calm wrist with a smartwatch, close-up");
  check("Draw all offers one picture per idea", await panel.getByRole("button", { name: `Draw all ${n}` }).isVisible());
  await page.screenshot({ path: "e2e/out/g3-written-prompts.png" });
} finally {
  fs.writeFileSync(settingsFile, settings0);
}

// use it
await panel.getByRole("button", { name: "Use for this scene" }).click();
await page.waitForTimeout(2500);
const sc = (await api("GET", `/api/projects/${pid}/scenes`)).body.plan.scenes.find((x) => x.id === sid);
check("Use makes the scene show the picture", JSON.stringify(sc).includes(media));
await panel.getByRole("button", { name: "Forget this picture" }).click();
await page.waitForTimeout(800);
check("Forget takes it out of the list", (await panel.getByRole("list", { name: "Pictures made for this scene" }).getByRole("listitem").count()) === 0);
await panel.getByRole("button", { name: "Close the pictures" }).click();

await api("PUT", `/api/projects/${pid}/scenes`, plan0);                  // the sample as it was
fs.rmSync(genFile, { force: true });
await api("DELETE", `/api/projects/${pid}/media/${media}`);
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
process.exit(fail ? 1 : 0);
