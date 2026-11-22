// The real thing (docs/plans/PLAN-WORKBENCH.MD W12.6): the desktop app, started from source, connected to a server, with the person's own Claude Code
// answering in the Assistant pane. Uses Claude (the plan's usage). Needs: the Studio built (npm --prefix client/studio run build), a server with /mcp
// (`vt server --host 0.0.0.0 --port 8791`), Claude Code signed in.
//   VT_SERVER=http://127.0.0.1:8791 VT_PROJECT=c2-mix node e2e/desktop-agent.mjs
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { _electron as electron } from "playwright-core";
import { repo } from "./common.mjs";

const server = process.env.VT_SERVER || "http://127.0.0.1:8791", pid = process.env.VT_PROJECT || "c2-mix";
const desktop = path.join(repo, "desktop");      // repo here is the client folder
const exe = createRequire(path.join(desktop, "package.json"))("electron");
const home = fs.mkdtempSync(path.join(os.tmpdir(), "vt-desktop-agent-"));
let pass = 0, fail = 0;
const check = (name, ok, extra = "") => { (ok ? pass++ : fail++); console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? "  " + extra : ""}`); };

// VT_PACKAGED=<path to the built app's exe> runs the packaged app (W12.6) with its own AppData folder, so it never shares the installed app's settings
const packaged = process.env.VT_PACKAGED || "";
const env = { ...process.env, UVT_DEV_HOME: home, ...(packaged ? { APPDATA: path.join(home, "appdata") } : {}) };
delete env.ELECTRON_RUN_AS_NODE;
const app = packaged ? await electron.launch({ executablePath: packaged, args: ["--server", server], env })
  : await electron.launch({ executablePath: exe, args: [desktop, "--server", server], env });
try {
  const page = await app.firstWindow();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
  await page.waitForLoadState("load");
  const origin = new URL(page.url()).origin;
  await page.goto(`${origin}/p/${pid}`, { waitUntil: "load" });
  await page.waitForSelector(".wb .wb-assistant-body", { timeout: 60000 });
  await page.getByRole("tab", { name: "Claude Code" }).click();
  const box = page.getByLabel("Message to Claude Code");
  await box.waitFor({ timeout: 15000 });
  check("the desktop app offers Claude Code (installed and signed in)", await box.isVisible());

  await box.fill("Using your Video Tool tools, tell me the title of this video and how many scenes it has. One short sentence.");
  await page.keyboard.press("Enter");
  await page.locator(".agent-steps li").first().waitFor({ timeout: 120000 });
  check("a step shows while it works, named in plain words", /[A-Z][a-z]+( [a-z]+)*/.test(await page.locator(".agent-steps li").first().textContent()), await page.locator(".agent-steps li").first().textContent());
  await page.locator(".agent-turn.agent p").first().waitFor({ timeout: 180000 });
  await page.getByRole("button", { name: "Send" }).waitFor({ timeout: 180000 });
  const answer = await page.locator(".agent-turn.agent p").last().textContent();
  check("it answered from the video", /scene/i.test(answer) && /\d/.test(answer), answer.slice(0, 120));
  check("our own tools asked nothing", await page.getByRole("alertdialog").count() === 0);

  await box.fill("Run the shell command: echo hi > vt_probe.txt");
  await page.keyboard.press("Enter");
  const card = page.getByRole("alertdialog", { name: "Permission needed" });
  await card.waitFor({ timeout: 120000 });
  check("a shell command asks first", (await card.textContent()).includes("wants to run a command"), (await card.textContent()).slice(0, 100));
  await page.getByRole("button", { name: "Deny" }).click();
  await page.getByRole("button", { name: "Send" }).waitFor({ timeout: 120000 });
  const probe = packaged ? path.join(home, "appdata", "Video Tool", "agents", pid, "vt_probe.txt") : path.join(home, "client", "agents", pid, "vt_probe.txt");
  check("Deny was respected: nothing was written", !fs.existsSync(probe));
  await page.screenshot({ path: process.env.VT_SHOT_PNG || "desktop-agent.png" });
  check("no page errors", errors.length === 0, errors.join(" | "));
} finally {
  await app.close().catch(() => {});
  fs.rmSync(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
