// O6 (docs/plans/PLAN-OPENMOTION.MD): Claude Code changes what the person selected in the HyperFrames Studio. The desktop app opens the video in the
// Studio inside the editor; the person selects a part in the Studio's Layers panel and asks Claude Code (docked beside it) to change "the selected part".
// Claude Code reads the selection (studio_selection) and edits the Studio copy (studio_edit); the Studio shows the new words without a reload by hand.
// Uses Claude (the plan's usage). VT_SERVER=http://127.0.0.1:8791 VT_PROJECT=c2-mix node e2e/desktop-studio-agent.mjs
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { _electron as electron } from "playwright-core";
import { closeDesktop, repo } from "./common.mjs";

const server = process.env.VT_SERVER || "http://127.0.0.1:8791", pid = process.env.VT_PROJECT || "c2-mix";
const projects = process.env.VT_PROJECTS || "E:/UltimateVideoTool/scratch/c2-projects";
const desktop = path.join(repo, "desktop");
const exe = createRequire(path.join(desktop, "package.json"))("electron");
const home = fs.mkdtempSync(path.join(os.tmpdir(), "vt-desktop-studio-agent-"));
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };
const env = { ...process.env, UVT_DEV_HOME: home };
delete env.ELECTRON_RUN_AS_NODE;
const words = "Every minute counts";
const app = await electron.launch({ executablePath: exe, args: [desktop, "--server", server], env });
try {
  const page = await app.firstWindow();
  await page.waitForLoadState("load");
  await page.setViewportSize({ width: 1700, height: 1000 }).catch(() => {});
  const origin = new URL(page.url()).origin;
  await page.goto(`${origin}/p/${pid}`, { waitUntil: "load" });
  await page.waitForSelector(".wb .wb-viewer", { timeout: 60000 });
  // O8: the video opens in HyperFrames by itself in the app
  const frameEl = await page.waitForSelector(".studio-embed iframe", { timeout: 120000 });
  const studio = await frameEl.contentFrame();
  for (let i = 0; i < 30 && !/S\d Scene/.test(await studio.locator("body").innerText().catch(() => "")); i++) await page.waitForTimeout(1000);

  // the person picks the definition's term: the Studio's Layers panel lists a scene's parts when the playhead is in that scene
  const ruler = await studio.locator("text=00:15").first().boundingBox().catch(() => null);
  if (ruler) await studio.locator("text=00:15").first().click({ position: { x: 2, y: 4 } }).catch(() => {});
  await page.waitForTimeout(1200);
  await studio.getByText("Layers", { exact: true }).first().click();
  await page.waitForTimeout(1200);
  await studio.getByText("S4 Defn Term", { exact: true }).first().click();
  await page.waitForTimeout(1500);
  const sel = await page.evaluate(async (u) => (await fetch(u)).json(), `/api/projects/${pid}/studio`);
  check("the Studio is open on the video", sel.open === true);

  await page.getByRole("tab", { name: "Claude Code" }).click();
  const box = page.getByLabel("Message to Claude Code");
  await box.waitFor({ timeout: 20000 });
  await box.fill(`In the HyperFrames Studio I selected a part of the video. Change its words to "${words}". Use the studio tools; do not use any other way to edit.`);
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Send" }).waitFor({ timeout: 300000 });
  await page.locator(".agent-turn.agent").last().waitFor({ timeout: 300000 });
  const steps = (await page.locator(".agent-steps li").allTextContents()).join(" | ");
  check("Claude Code looked at the selection", /studio selection/i.test(steps), steps.slice(0, 200));
  const dir = path.join(projects, pid, "studio-9x16");                    // the root page and each scene's own page (S4)
  const copy = [path.join(dir, "index.html"), ...(fs.existsSync(path.join(dir, "scenes")) ? fs.readdirSync(path.join(dir, "scenes")).map((f) => path.join(dir, "scenes", f)) : [])].map((f) => fs.readFileSync(f, "utf8")).join("\n");
  check("Claude Code changed the selected part in the Studio copy", copy.includes(`>${words}<`));
  let shown = "";
  for (let i = 0; i < 15 && !shown.includes(words); i++) { await page.waitForTimeout(1000); shown = await studio.frameLocator("iframe").first().locator("body").innerText().catch(() => "") + (await studio.locator("body").innerText().catch(() => "")); }
  check("the Studio shows the new words without a reload by hand", shown.includes(words));
  await page.screenshot({ path: path.join(repo, "studio", "e2e", "out", "o6-claude-in-the-studio.png") });
  await page.getByRole("button", { name: "HyperFrames open" }).click();
  await page.getByRole("menuitem", { name: "Close the Studio" }).click();
  await page.waitForTimeout(1500);
} finally {
  await closeDesktop(app, home);
}
fs.rmSync(path.join(projects, pid, "studio-9x16"), { recursive: true, force: true });          // the sample exports as before again
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
