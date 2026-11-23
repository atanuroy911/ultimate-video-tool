// The headline scenario (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD): in the desktop app, ask Claude Code in the Assistant pane to draw a scene itself as a shot,
// then open that shot in the visual editor. Uses Claude. Same set-up as desktop-agent.mjs.
//   VT_SERVER=http://127.0.0.1:8791 VT_PROJECT=c6-shot VT_SCENE=s2 node e2e/desktop-agent-shot.mjs
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { _electron as electron } from "playwright-core";
import { closeDesktop, repo } from "./common.mjs";

const server = process.env.VT_SERVER || "http://127.0.0.1:8791", pid = process.env.VT_PROJECT || "c6-shot", scene = process.env.VT_SCENE || "s2";
const desktop = path.join(repo, "desktop");
const exe = createRequire(path.join(desktop, "package.json"))("electron");
const home = fs.mkdtempSync(path.join(os.tmpdir(), "vt-desktop-shot-"));
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };
const env = { ...process.env, UVT_DEV_HOME: home };
delete env.ELECTRON_RUN_AS_NODE;
const app = await electron.launch({ executablePath: exe, args: [desktop, "--server", server], env });
try {
  const page = await app.firstWindow();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
  await page.waitForLoadState("load");
  const origin = new URL(page.url()).origin;
  const api = (method, url, body) => page.evaluate(async ([m, u, b]) => { const r = await fetch(u, { method: m, headers: { "content-type": "application/json" }, body: b ? JSON.stringify(b) : undefined }); return r.json(); }, [method, url, body]);
  await page.goto(`${origin}/p/${pid}`, { waitUntil: "load" });
  await page.waitForSelector(".wb .wb-assistant-body", { timeout: 60000 });
  await page.getByRole("tab", { name: "Claude Code" }).click();
  const box = page.getByLabel("Message to Claude Code");
  await box.waitFor({ timeout: 15000 });
  await box.fill(`Draw scene ${scene} yourself as a shot. Use write_shot to make a shot with id "battery": an animated drawing of a phone battery that drains from green to red, with the word "Battery" above it, 1080x1920, as long as the scene. Follow the shot rules in write_shot's description: data-vt-id on the text and shapes, a paused GSAP timeline in window.__timelines, no network. Fix any errors it returns. Then show it behind the scene with set_scene_shot, and look at one frame with get_shot_frame. Reply in one sentence.`);
  await page.keyboard.press("Enter");
  await page.locator(".agent-steps li").first().waitFor({ timeout: 120000 });
  await page.getByRole("button", { name: "Send" }).waitFor({ timeout: 600000 });
  const steps = await page.locator(".agent-steps li").allTextContents();
  console.log("steps:", steps.join(" | "));
  check("it wrote the shot and put it behind the scene", steps.some((s) => /Write shot/i.test(s)) && steps.some((s) => /Set scene shot/i.test(s)), "");
  const shot = await api("GET", `/api/projects/${pid}/shots/battery`);
  check("the shot exists on the server with things a person can select", Array.isArray(shot.ids) && shot.ids.length >= 2, JSON.stringify(shot.ids));
  const plan = await api("GET", `/api/projects/${pid}/scenes`);
  check(`scene ${scene} shows it`, JSON.stringify(plan).includes('"shot":"battery"') || JSON.stringify(plan).includes('"shot": "battery"'));
  await page.evaluate((s) => window.dispatchEvent(new CustomEvent("vt-select-scene", { detail: s })), scene);
  const open = page.getByRole("button", { name: "Edit shot" });
  await open.waitFor({ timeout: 30000 });
  await open.click();
  await page.waitForSelector(".shot-canvas iframe", { timeout: 20000 });
  await page.waitForFunction(() => document.querySelector(".shot-side")?.textContent?.includes("Selectable:"), null, { timeout: 20000 });
  check("the shot Claude drew opens in the visual editor", await page.locator(".shot-side").textContent().then((t) => /Selectable: \w/.test(t)));
  await page.screenshot({ path: process.env.VT_SHOT_PNG || "desktop-agent-shot.png" });
  check("no page errors", errors.length === 0, errors.join(" | "));
} finally {
  await closeDesktop(app, home);
  fs.rmSync(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
