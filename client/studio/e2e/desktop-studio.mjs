// O5 (docs/plans/PLAN-OPENMOTION.MD): the HyperFrames Studio inside the desktop app's editor, with the assistant docked beside it. The desktop app,
// started from source and connected to a server on this computer, opens the whole video in the Studio: it loads inside the canvas pane (the app lifts
// the Studio's no-framing rule for this one local page), the assistant stays open, "Back to Video Tool's editor" returns, and closing stops it.
// Needs the client built (npm --prefix client/studio run build) and a server: VT_SERVER=http://127.0.0.1:8791 VT_PROJECT=c2-mix node e2e/desktop-studio.mjs
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { _electron as electron } from "playwright-core";
import { repo } from "./common.mjs";

const server = process.env.VT_SERVER || "http://127.0.0.1:8791", pid = process.env.VT_PROJECT || "c2-mix";
const desktop = path.join(repo, "desktop");
const exe = createRequire(path.join(desktop, "package.json"))("electron");
const home = fs.mkdtempSync(path.join(os.tmpdir(), "vt-desktop-studio-"));
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
  await page.setViewportSize({ width: 1700, height: 1000 }).catch(() => {});
  const origin = new URL(page.url()).origin;
  await page.goto(`${origin}/p/${pid}`, { waitUntil: "load" });
  await page.waitForSelector(".wb .wb-viewer", { timeout: 60000 });

  await page.getByRole("button", { name: "Edit in the Studio" }).click();
  const frameEl = await page.waitForSelector(".studio-embed iframe", { timeout: 120000 }).catch(() => null);
  check("the Studio opens inside the editor's canvas pane", !!frameEl);
  const frame = frameEl ? await frameEl.contentFrame() : null;
  let text = "";
  for (let i = 0; frame && i < 30 && !/S\d Scene/.test(text); i++) { await page.waitForTimeout(1000); text = await frame.locator("body").innerText().catch(() => ""); }
  check("the Studio loads there (its timeline shows the scenes)", /S\d Scene/.test(text), text.slice(0, 80).replace(/\s+/g, " "));
  const shown = async (t) => frame.getByRole("button", { name: t, exact: true }).first().isVisible().catch(() => false);
  check("the Studio's cloud and product buttons are hidden inside the app", frame && !(await shown("Share")) && !(await shown("Install the desktop app")) && !(await shown("Export")));
  check("the assistant stays docked beside it", await page.locator(".wb-assistant-body").isVisible());
  check("the editor's own panels step aside", (await page.locator(".ed-left").count()) === 0 || !(await page.locator(".ed-left").isVisible()));
  await page.screenshot({ path: path.join(repo, "studio", "e2e", "out", "o5-studio-in-the-app.png") });

  await page.getByRole("button", { name: "Studio open" }).click();
  await page.getByRole("menuitem", { name: "Back to Video Tool's editor" }).click();
  await page.waitForTimeout(800);
  check("Back to the editor shows Video Tool's canvas again", (await page.locator(".studio-embed").count()) === 0);
  await page.getByRole("button", { name: "Studio open" }).click();
  await page.getByRole("menuitem", { name: "Close the Studio" }).click();
  await page.waitForTimeout(2000);
  const st = await page.evaluate(async (u) => (await fetch(u)).json(), `/api/projects/${pid}/studio`);
  check("closing stops the Studio", st.open === false, JSON.stringify(st).slice(0, 120));
  console.log(errors.length ? "ERRORS:\n" + [...new Set(errors)].join("\n") : "ERRORS: none");
} finally {
  await app.close();
}
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
