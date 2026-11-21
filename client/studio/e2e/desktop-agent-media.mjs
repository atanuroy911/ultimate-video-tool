// C7: in the desktop app, Claude Code makes a picture with the local ComfyUI and speaks a line with Kokoro through our tools. Uses Claude and the card.
//   VT_SERVER=http://127.0.0.1:8791 VT_PROJECT=c6-shot VT_SCENE=s2 node e2e/desktop-agent-media.mjs
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { _electron as electron } from "playwright-core";
import { repo } from "./common.mjs";

const server = process.env.VT_SERVER || "http://127.0.0.1:8791", pid = process.env.VT_PROJECT || "c6-shot", scene = process.env.VT_SCENE || "s2";
const desktop = path.join(repo, "desktop");
const exe = createRequire(path.join(desktop, "package.json"))("electron");
const home = fs.mkdtempSync(path.join(os.tmpdir(), "vt-desktop-media-"));
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
  await box.fill("Use your Video Tool tools. First make_picture of a red kettle on a wooden table, soft morning light. Then speak the sentence 'The kettle is ready.' in the default voice. Reply in one short sentence with the media id and the audio file name.");
  await page.keyboard.press("Enter");
  await page.locator(".agent-steps li").first().waitFor({ timeout: 120000 });
  await page.waitForFunction(() => !!document.querySelector(".agent-turn.agent p") && !!document.querySelector('button[aria-label="Send"]'), null, { timeout: 900000 });
  await page.waitForTimeout(1500);
  const dir = path.join(process.env.VT_PROJECTS || "", pid);
  const before = Number(process.env.VT_MEDIA_BEFORE || 0);
  const wavs = fs.existsSync(path.join(dir, "agent_audio")) ? fs.readdirSync(path.join(dir, "agent_audio")).filter((f) => /kettle-is-ready/.test(f)) : [];
  check("it spoke the sentence with Kokoro (a WAV was saved)", wavs.length > 0, wavs.join(","));
  const media = await api("GET", `/api/projects/${pid}/media`);
  check("a picture is in the project's media bin", (Array.isArray(media) ? media : media.media || []).length > before);
  const answer = await page.locator(".agent-turn.agent p").last().textContent();
  check("it answered", answer.length > 5, answer.slice(0, 120));
  check("our own tools asked nothing", await page.getByRole("alertdialog").count() === 0);
  check("no page errors", errors.length === 0, errors.join(" | "));
} finally {
  await app.close().catch(() => {});
  fs.rmSync(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
